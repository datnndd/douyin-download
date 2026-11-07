# -*- coding: utf-8 -*-
"""
src/web/services/tracker_service.py
Lightweight Creator Tracker service managing change detection for Douyin creators,
filtering pinned videos (is_top == 1), minimal persistence, 1-Click Update task
dispatching via TaskManager, and optional background polling.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from src.douyin.database import Database
from src.douyin.douyinapi import DouyinApi
from src.douyin.urls import Urls
from src.common import utils
from src.web.core.config import ConfigManager
from src.web.core.schemas import (
    AssetTypeToggles,
    CheckAllResponse,
    DownloadRequest,
    TaskResponse,
    TaskStatus,
    TrackedCreatorResponse,
    TrackedVideoItem,
    TrackerStatsResponse,
)
from src.web.services.task_manager import TaskManager, TaskRecord

logger = logging.getLogger("DouyinWeb.TrackerService")


class TrackerService:
    """
    Central service for monitoring creator activity, detecting newly published videos,
    and triggering incremental downloads with minimal network and storage overhead.
    """

    _instance: Optional[TrackerService] = None
    _singleton_lock: threading.RLock = threading.RLock()

    def __init__(self, db_path: str = "data.db") -> None:
        if getattr(self, "_initialized", False):
            return

        self.db_path = db_path
        self.database = Database(db_path)
        self._lock = threading.RLock()
        self._bg_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._initialized = True

        # Check if background worker should be started from settings
        try:
            config = ConfigManager.get_instance().get_settings()
            if config.tracker_interval_hours > 0:
                self.start_background_worker(config.tracker_interval_hours)
        except Exception as e:
            logger.debug(f"Could not load initial background tracker settings: {e}")

    @classmethod
    def get_instance(cls, db_path: str = "data.db") -> TrackerService:
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    # -------------------------------------------------------------------------
    # Creator Enrollment & CRUD
    # -------------------------------------------------------------------------

    def track_creator(
        self,
        url: Optional[str] = None,
        sec_uid: Optional[str] = None,
        nickname: Optional[str] = None,
        avatar_thumb: Optional[str] = None,
        unique_id: Optional[str] = None,
        cookie: Optional[str] = None,
    ) -> TrackedCreatorResponse:
        """
        Enrolls a creator into tracking. Resolves sec_uid and profile if missing,
        inspects user posts to establish the latest non-pinned video baseline,
        and persists the creator in the database.
        """
        from src.web.core.config import ConfigManager
        eff_cookie = cookie or ConfigManager.get_instance().get_cookie_header() or None
        api = DouyinApi(database_path=self.db_path, cookie=eff_cookie)

        # 1. Resolve sec_uid if not provided directly
        if not sec_uid:
            if not url or not url.strip():
                raise ValueError("Either 'sec_uid' or 'url' must be provided.")
            share_url = api.getShareLink(url)
            key_type, resolved_id = api.getKey(share_url)
            if key_type != "user" or not resolved_id:
                raise ValueError(f"URL does not point to a Douyin creator profile: {url}")
            sec_uid = resolved_id

        # 2. Fetch profile info (nickname, avatar, unique_id) if missing
        if not nickname or not avatar_thumb:
            try:
                from src.web.services.douyin_service import DouyinService
                ds = DouyinService.get_instance()
                _, preview = ds.fetch_preview_metadata(api, "user", sec_uid)
                if preview and preview.author:
                    nickname = nickname or preview.author.nickname
                    avatar_thumb = (
                        avatar_thumb
                        or preview.author.avatar_thumb
                        or preview.author.avatar
                        or preview.cover_url
                    )
                    unique_id = unique_id or preview.author.unique_id or preview.author.short_id
            except Exception as e:
                logger.warning(f"Could not fetch full profile preview for {sec_uid}: {e}")

        # Fallback profile defaults
        nickname = nickname or "Douyin Creator"
        avatar_thumb = avatar_thumb or ""
        unique_id = unique_id or ""

        # 3. Query creator posts to establish initial latest video baseline (filtering pinned videos)
        last_aweme_id: Optional[str] = None
        last_aweme_time: Optional[int] = None

        try:
            posts = self._fetch_creator_feed_page(api, sec_uid, count=18)
            # Find the newest non-pinned video
            for item in posts:
                is_top = int(item.get("is_top", 0) or 0)
                if is_top == 1:
                    continue  # Pinned video; skip when determining chronological baseline
                last_aweme_id = str(item.get("aweme_id") or "")
                last_aweme_time = int(item.get("create_time", 0) or 0)
                break

            # If all were pinned or none found, fallback to the very first item if present
            if not last_aweme_id and posts:
                last_aweme_id = str(posts[0].get("aweme_id") or "")
                last_aweme_time = int(posts[0].get("create_time", 0) or 0)
        except Exception as e:
            logger.warning(f"Failed to fetch initial feed baseline for {sec_uid}: {e}")

        # 4. Save to database
        self.database.upsert_tracked_creator(
            sec_uid=sec_uid,
            unique_id=unique_id,
            nickname=nickname,
            avatar_thumb=avatar_thumb,
            last_aweme_id=last_aweme_id,
            last_aweme_time=last_aweme_time,
        )

        return self.get_creator(sec_uid, include_pending=True)  # type: ignore

    def get_creator(
        self, sec_uid: str, include_pending: bool = True
    ) -> Optional[TrackedCreatorResponse]:
        """Fetch details of a single tracked creator with optional pending videos list."""
        row = self.database.get_tracked_creator(sec_uid)
        if not row:
            return None

        pending_items: Optional[List[TrackedVideoItem]] = None
        if include_pending:
            p_rows = self.database.get_pending_videos(sec_uid)
            pending_items = [
                TrackedVideoItem(
                    aweme_id=r["aweme_id"],
                    sec_uid=r["sec_uid"],
                    create_time=r["create_time"],
                    title=r["title"],
                    status=r["status"],
                    downloaded_at=r["downloaded_at"],
                )
                for r in p_rows
            ]

        return TrackedCreatorResponse(
            sec_uid=row["sec_uid"],
            unique_id=row["unique_id"],
            nickname=row["nickname"],
            avatar_thumb=row["avatar_thumb"],
            last_aweme_id=row["last_aweme_id"],
            last_aweme_time=row["last_aweme_time"],
            pending_new_count=row["pending_new_count"] or 0,
            last_checked_at=row["last_checked_at"],
            last_downloaded_at=row["last_downloaded_at"],
            created_at=row["created_at"],
            pending_videos=pending_items,
        )

    def list_creators(self) -> List[TrackedCreatorResponse]:
        """List all tracked creators sorted by pending updates first."""
        rows = self.database.list_tracked_creators()
        return [
            TrackedCreatorResponse(
                sec_uid=r["sec_uid"],
                unique_id=r["unique_id"],
                nickname=r["nickname"],
                avatar_thumb=r["avatar_thumb"],
                last_aweme_id=r["last_aweme_id"],
                last_aweme_time=r["last_aweme_time"],
                pending_new_count=r["pending_new_count"] or 0,
                last_checked_at=r["last_checked_at"],
                last_downloaded_at=r["last_downloaded_at"],
                created_at=r["created_at"],
                pending_videos=None,
            )
            for r in rows
        ]

    def untrack_creator(self, sec_uid: str) -> bool:
        """Remove a creator and all associated tracking logs."""
        return self.database.delete_tracked_creator(sec_uid)

    # -------------------------------------------------------------------------
    # Change Detection Algorithm
    # -------------------------------------------------------------------------

    def check_creator_updates(
        self, sec_uid: str, cookie: Optional[str] = None
    ) -> Tuple[TrackedCreatorResponse, int]:
        """
        Polls Douyin upstream for newly published videos by this creator:
        - Filters out pinned items (is_top == 1) to evaluate true chronology.
        - Stops checking immediately as soon as last_aweme_id or an existing recorded ID is reached.
        - Records new videos in tracked_video_log with status='pending'.
        - Updates tracked_creators.pending_new_count.
        - Stores only lean metadata (<100 bytes/row, zero raw JSON dumps).
        """
        creator = self.database.get_tracked_creator(sec_uid)
        if not creator:
            raise ValueError(f"Creator {sec_uid} is not tracked.")

        last_aweme_id = creator["last_aweme_id"]
        last_aweme_time = creator["last_aweme_time"] or 0

        # Existing pending aweme IDs to avoid redundant inserts
        existing_pending = {
            r["aweme_id"] for r in self.database.get_pending_videos(sec_uid)
        }

        from src.web.core.config import ConfigManager
        eff_cookie = cookie or ConfigManager.get_instance().get_cookie_header() or None
        api = DouyinApi(database_path=self.db_path, cookie=eff_cookie)
        new_videos: List[Dict[str, Any]] = []
        newest_detected_id: Optional[str] = None
        newest_detected_time: Optional[int] = None

        try:
            posts = self._fetch_creator_feed_page(api, sec_uid, count=35)
        except Exception as e:
            logger.error(f"Failed to fetch posts feed for creator {sec_uid}: {e}")
            raise RuntimeError(f"Failed to fetch creator feed: {e}")

        # Walk through posts in reverse chronological order
        for item in posts:
            is_top = int(item.get("is_top", 0) or 0)
            if is_top == 1:
                # Pinned video: do NOT evaluate as a chronological upload
                continue

            aid = str(item.get("aweme_id") or "")
            ctime = int(item.get("create_time", 0) or 0)

            # Stopping condition 1: Reached previously recorded baseline last_aweme_id
            if last_aweme_id and aid == last_aweme_id:
                logger.debug(f"Reached baseline aweme_id {last_aweme_id} — stopping check.")
                break

            # Stopping condition 2: Reached already recorded pending video
            if aid in existing_pending:
                logger.debug(f"Reached existing pending video {aid} — stopping check.")
                break

            # Stopping condition 3: Creation time is older than baseline (fallback if baseline deleted)
            if last_aweme_id and last_aweme_time > 0 and ctime > 0 and ctime < last_aweme_time:
                logger.debug(f"Video {aid} create_time {ctime} < baseline {last_aweme_time} — stopping check.")
                break

            # If creator had no baseline (e.g. freshly enrolled with empty feed earlier):
            if not last_aweme_id:
                newest_detected_id = aid
                newest_detected_time = ctime
                break

            # Discovered a genuine newly published video!
            new_videos.append(item)
            if newest_detected_id is None:
                newest_detected_id = aid
                newest_detected_time = ctime

        # Persist newly found videos into database (lean metadata only)
        added_count = 0
        if new_videos:
            added_count = self.database.sync_tracked_videos(
                sec_uid=sec_uid,
                new_videos=new_videos,
                last_aweme_id=None,  # Keep baseline last_aweme_id intact until downloaded
                last_aweme_time=None,
            )
        elif not last_aweme_id and newest_detected_id:
            # Baseline initialization
            self.database.upsert_tracked_creator(
                sec_uid=sec_uid,
                last_aweme_id=newest_detected_id,
                last_aweme_time=newest_detected_time,
            )
        else:
            # Touch last_checked_at timestamp even if no new items found
            self.database.sync_tracked_videos(
                sec_uid=sec_uid,
                new_videos=[],
            )

        updated_creator = self.get_creator(sec_uid, include_pending=True)
        return updated_creator, added_count  # type: ignore

    def check_all_creators(self, cookie: Optional[str] = None) -> CheckAllResponse:
        """
        Poll updates across all tracked creators sequentially with polite delay jitter.
        """
        creators = self.list_creators()
        total_checked = 0
        new_videos_detected = 0
        creators_with_new = 0

        from src.web.core.config import ConfigManager
        eff_cookie = cookie or ConfigManager.get_instance().get_cookie_header() or None

        for c in creators:
            try:
                _, added = self.check_creator_updates(c.sec_uid, cookie=eff_cookie)
                total_checked += 1
                if added > 0:
                    new_videos_detected += added
                    creators_with_new += 1
            except Exception as e:
                logger.error(f"Error checking updates for creator {c.sec_uid}: {e}")

            # Polite jitter delay between requests (1.0 to 2.0s)
            time.sleep(random.uniform(1.0, 2.0))

        return CheckAllResponse(
            total_checked=total_checked,
            new_videos_detected=new_videos_detected,
            creators_with_new=creators_with_new,
        )

    # -------------------------------------------------------------------------
    # 1-Click Update Dispatcher
    # -------------------------------------------------------------------------

    def start_one_click_update(
        self, sec_uid: str, custom_settings: Optional[Dict[str, Any]] = None
    ) -> TaskResponse:
        """
        1-Click Update:
        - Resolves pending videos for the creator.
        - Constructs an incremental DownloadRequest targeting strictly those new aweme_ids.
        - Submits task to TaskManager using user defaults.
        - Attaches a completion callback that transitions status to 'downloaded'
          and updates last_aweme_id upon successful completion.
        """
        creator = self.database.get_tracked_creator(sec_uid)
        if not creator:
            raise ValueError(f"Creator {sec_uid} not found.")

        pending_videos = self.database.get_pending_videos(sec_uid)
        if not pending_videos:
            raise ValueError("No pending new videos to update for this creator.")

        pending_aweme_ids = [r["aweme_id"] for r in pending_videos]
        # Newest video will become the new last_aweme_id upon download completion
        newest_video = pending_videos[0]
        newest_aweme_id = newest_video["aweme_id"]
        newest_aweme_time = newest_video["create_time"]

        # Resolve download settings from ConfigManager
        config = ConfigManager.get_instance().get_settings()
        req_settings = custom_settings or {}

        download_path = req_settings.get("download_path") or config.path or "./Downloaded/"
        thread_count = req_settings.get("thread_count") or config.thread or 5
        filename_template = (
            req_settings.get("filename_template")
            or config.filename_template
            or "{date}_{title}_{id}"
        )
        cookie = req_settings.get("cookie") or config.raw_cookie

        download_request = DownloadRequest(
            url=f"https://www.douyin.com/user/{sec_uid}",
            key_type="user",
            key=sec_uid,
            modes=["post"],
            asset_types=AssetTypeToggles(
                video=req_settings.get("video", config.video if hasattr(config, "video") else True),
                music=req_settings.get("music", config.music if hasattr(config, "music") else True),
                cover=req_settings.get("cover", config.cover if hasattr(config, "cover") else True),
                avatar=req_settings.get("avatar", config.avatar if hasattr(config, "avatar") else False),
                json=req_settings.get("json", config.json if hasattr(config, "json") else True),
            ),
            thread_count=thread_count,
            folderstyle=config.folderstyle,
            download_path=download_path,
            filename_template=filename_template,
            database=True,
            cookie=cookie,
            aweme_ids=pending_aweme_ids,  # Explicitly target ONLY newly added videos!
        )

        task_manager = TaskManager.get_instance()
        from src.web.services.douyin_service import DouyinService
        ds = DouyinService.get_instance()

        task_response = task_manager.submit_task(download_request, douyin_service=ds)

        # Register completion callback to mark items as downloaded in SQLite
        def _on_task_finished(record: TaskRecord, final_status: TaskStatus) -> None:
            if final_status == TaskStatus.COMPLETED:
                logger.info(
                    f"Update task {record.task_id} completed. Marking {len(pending_aweme_ids)} videos as downloaded."
                )
                self.database.mark_tracked_videos_downloaded(
                    sec_uid=sec_uid,
                    aweme_ids=pending_aweme_ids,
                    new_last_aweme_id=newest_aweme_id,
                    new_last_aweme_time=newest_aweme_time,
                )
            else:
                logger.warning(
                    f"Update task {record.task_id} finished with status {final_status}. Pending videos retained."
                )

        task_manager.register_completion_callback(task_response.task_id, _on_task_finished)
        return task_response

    def update_all_creators(self) -> List[TaskResponse]:
        """Triggers 1-Click Update for all tracked creators that have pending videos."""
        creators = self.list_creators()
        responses: List[TaskResponse] = []
        for c in creators:
            if c.pending_new_count > 0:
                try:
                    resp = self.start_one_click_update(c.sec_uid)
                    responses.append(resp)
                except Exception as e:
                    logger.error(f"Failed to start update for creator {c.sec_uid}: {e}")
        return responses

    def get_summary_stats(self) -> TrackerStatsResponse:
        """Summary counts for UI navigation badge."""
        stats = self.database.get_tracker_summary()
        return TrackerStatsResponse(
            total_tracked_creators=stats.get("total_tracked_creators", 0),
            total_pending_videos=stats.get("total_pending_videos", 0),
        )

    # -------------------------------------------------------------------------
    # Background Periodic Worker
    # -------------------------------------------------------------------------

    def start_background_worker(self, interval_hours: int) -> None:
        """Starts background periodic polling thread."""
        with self._lock:
            if interval_hours <= 0:
                self.stop_background_worker()
                return

            if self._bg_thread and self._bg_thread.is_alive():
                logger.info(f"Background worker already active, updating interval to {interval_hours}h.")
                return

            self._stop_event.clear()

            def _worker_loop():
                logger.info(f"Creator Tracker background worker started (interval={interval_hours}h).")
                while not self._stop_event.is_set():
                    # Sleep in small slices to respond to cancellation promptly
                    wait_seconds = interval_hours * 3600
                    elapsed = 0
                    while elapsed < wait_seconds and not self._stop_event.is_set():
                        time.sleep(min(10, wait_seconds - elapsed))
                        elapsed += 10

                    if self._stop_event.is_set():
                        break

                    logger.info("Executing periodic creator update check...")
                    try:
                        self.check_all_creators()
                    except Exception as err:
                        logger.error(f"Periodic tracker check failed: {err}")

            self._bg_thread = threading.Thread(
                target=_worker_loop, name="CreatorTrackerWorker", daemon=True
            )
            self._bg_thread.start()

    def stop_background_worker(self) -> None:
        """Stops background periodic polling thread."""
        with self._lock:
            if self._bg_thread and self._bg_thread.is_alive():
                logger.info("Stopping Creator Tracker background worker...")
                self._stop_event.set()
                self._bg_thread.join(timeout=2.0)
            self._bg_thread = None

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _fetch_creator_feed_page(
        self, api: DouyinApi, sec_uid: str, count: int = 18
    ) -> List[Dict[str, Any]]:
        """
        Directly fetches raw post feed page for a creator.
        Preserves is_top and aweme_id flags.
        """
        detail_params = (
            f"sec_user_id={sec_uid}&count={count}&max_cursor=0&{api._COMMON_PARAMS}"
        )
        url = api.urls.USER_POST + utils.getXbogus(detail_params)
        headers = api._get_headers()

        response = api.session.get(url=url, headers=headers, timeout=api.timeout)
        if not response.text or len(response.text.strip()) == 0:
            logger.warning(f"Empty response when fetching feed page for {sec_uid}")
            return []

        if response.status_code in (403, 429) or "ArgusSecurity" in response.text:
            logger.warning(
                f"Douyin WAF risk control triggered on creator feed {sec_uid} (HTTP {response.status_code})"
            )
            return []

        try:
            datadict = json.loads(response.text)
        except Exception as e:
            logger.warning(f"Failed to parse feed JSON for {sec_uid}: {e}")
            return []
        if not datadict or datadict.get("status_code") != 0:
            logger.warning(f"Non-zero status when fetching feed for {sec_uid}: {datadict.get('status_code') if datadict else None}")
            return []

        return datadict.get("aweme_list") or []
