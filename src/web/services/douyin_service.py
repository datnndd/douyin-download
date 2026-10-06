# -*- coding: utf-8 -*-
"""
src/web/services/douyin_service.py
Thread-safe, non-blocking asynchronous service for resolving Douyin
links and generating rich content previews across all 5 key types.
"""

import asyncio
import copy
import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.douyin.douyinapi import DouyinApi
from src.douyin.urls import Urls
from src.douyin import douyin_headers
from src.common import utils
from src.web.core.schemas import (
    AuthorPreview,
    DownloadRequest,
    ParseResponse,
    PreviewMetadata,
    PreviewStatistics,
    StatisticsModel,
)

logger = logging.getLogger("DouyinWeb.Service")


# ==============================================================================
# Domain Exceptions
# ==============================================================================


class DouyinServiceError(Exception):
    """Base exception for Douyin service errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DouyinInvalidUrlError(DouyinServiceError):
    """HTTP 400: Malformed or unrecognized URL."""

    def __init__(self, message: str = "Invalid or unsupported Douyin URL"):
        super().__init__(message, status_code=400)


class DouyinNotFoundError(DouyinServiceError):
    """HTTP 404: Content or account deleted or private."""

    def __init__(self, message: str = "Douyin content not found or deleted"):
        super().__init__(message, status_code=404)


class DouyinUpstreamError(DouyinServiceError):
    """HTTP 502: Upstream rate limit, block, or captcha."""

    def __init__(
        self, message: str = "Douyin upstream service error or anti-bot block"
    ):
        super().__init__(message, status_code=502)


# ==============================================================================
# Regex Patterns
# ==============================================================================

SHARE_LINK_REGEX = re.compile(r"https?://[a-zA-Z0-9_./\-?&=%#+:@!~*]+")

AWEME_PATTERNS = [
    re.compile(r"/video/(\d+)"),
    re.compile(r"/note/(\d+)"),
    re.compile(r"/share/video/(\d+)"),
    re.compile(r"/share/note/(\d+)"),
]
USER_PATTERNS = [
    re.compile(r"/user/([a-zA-Z0-9_\-]+)"),
    re.compile(r"/share/user/([a-zA-Z0-9_\-]+)"),
]
MIX_PATTERNS = [
    re.compile(r"/mix/detail/(\d+)"),
    re.compile(r"/collection/(\d+)"),
]
MUSIC_PATTERNS = [
    re.compile(r"/music/(\d+)"),
]
LIVE_PATTERNS = [
    re.compile(r"live\.douyin\.com/([a-zA-Z0-9_]+)"),
    re.compile(r"/webcast/reflow/(\d+)"),
]


# ==============================================================================
# Service Implementation
# ==============================================================================


class DouyinService:
    """
    Thread-safe asynchronous service wrapping DouyinApi.
    Provides non-blocking link resolution and preview extraction.
    """

    def __init__(
        self, default_cookie: Optional[str] = None, database_path: Optional[str] = None
    ):
        self._default_cookie = default_cookie
        self._database_path = database_path
        self._local = threading.local()

    def _get_api(self, cookie: Optional[str] = None) -> DouyinApi:
        """Retrieve or initialize thread-local DouyinApi instance."""
        active_cookie = cookie or self._default_cookie
        api = getattr(self._local, "api", None)
        cached_cookie = getattr(self._local, "cookie", None)

        if api is None or cached_cookie != active_cookie:
            api = DouyinApi(database_path=self._database_path, cookie=active_cookie)
            self._local.api = api
            self._local.cookie = active_cookie
        return api

    # -------------------------------------------------------------------------
    # Public Async API
    # -------------------------------------------------------------------------

    async def parse_url(
        self, raw_input: str, cookie: Optional[str] = None
    ) -> ParseResponse:
        """
        Non-blocking URL parsing and preview metadata extraction.
        Offloaded to worker thread via asyncio.to_thread.
        """
        return await asyncio.to_thread(self._sync_parse_url, raw_input, cookie)

    def sync_parse_url(
        self, raw_input: str, cookie: Optional[str] = None
    ) -> ParseResponse:
        """Synchronous wrapper for parse_url."""
        return self._sync_parse_url(raw_input, cookie)

    # -------------------------------------------------------------------------
    # Synchronous Execution Core (Runs in worker thread)
    # -------------------------------------------------------------------------

    def _sync_parse_url(
        self, raw_input: str, cookie: Optional[str] = None
    ) -> ParseResponse:
        """Synchronously resolves URL and extracts rich preview metadata."""
        if not raw_input or not raw_input.strip():
            raise DouyinInvalidUrlError("URL input cannot be empty.")

        # 1. Extract HTTP link from clipboard/share text
        extracted_url = self.extract_share_url(raw_input)
        if not extracted_url:
            raise DouyinInvalidUrlError(f"No valid HTTP link found in: {raw_input}")

        api = self._get_api(cookie)

        # 2. Expand short link / follow redirect if necessary
        resolved_url = self.resolve_redirect_url(extracted_url, api.session)

        # 3. Match key_type and key
        key_type, key = self.extract_key_and_type(resolved_url, api.session)
        if not key_type or not key:
            raise DouyinInvalidUrlError(
                f"Unsupported Douyin link structure: {resolved_url}"
            )

        # 4. Canonical URL
        canonical_url = self.build_canonical_url(key_type, key)

        # 5. Extract rich preview metadata
        content_type, preview = self.fetch_preview_metadata(api, key_type, key)

        return ParseResponse(
            success=True,
            url=extracted_url,
            canonical_url=canonical_url,
            key_type=key_type,
            key=key,
            content_type=content_type,
            preview=preview,
        )

    # -------------------------------------------------------------------------
    # Link Resolution Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def extract_share_url(text: str) -> Optional[str]:
        """Extracts first valid HTTP/HTTPS URL from raw string."""
        matches = SHARE_LINK_REGEX.findall(text)
        if not matches:
            return None
        url = matches[0].rstrip("),.!?，。！？;；'\"")
        return url if url else None

    @staticmethod
    def resolve_redirect_url(url: str, session: requests.Session) -> str:
        """Follows HTTP redirects for short URLs (v.douyin.com) to find final destination."""
        if "v.douyin.com" in url or "iesdouyin.com/share" in url:
            try:
                # Use stream=True to avoid reading large response payloads
                resp = session.get(
                    url,
                    headers=douyin_headers,
                    allow_redirects=True,
                    timeout=10,
                    stream=True,
                )
                return str(resp.url)
            except Exception as e:
                logger.error(f"Failed to resolve short URL redirect for {url}: {e}")
                raise DouyinUpstreamError(f"Failed to follow short link redirect: {e}")
        return url

    def extract_key_and_type(
        self, url: str, session: requests.Session
    ) -> Tuple[Optional[str], Optional[str]]:
        """Matches URL against patterns for the 5 key types."""
        # 1. Aweme (Video/Note)
        for pattern in AWEME_PATTERNS:
            if match := pattern.search(url):
                return "aweme", match.group(1)

        # 2. User Profile
        for pattern in USER_PATTERNS:
            if match := pattern.search(url):
                return "user", match.group(1)

        # 3. Mix / Collection
        for pattern in MIX_PATTERNS:
            if match := pattern.search(url):
                return "mix", match.group(1)

        # 4. Music
        for pattern in MUSIC_PATTERNS:
            if match := pattern.search(url):
                return "music", match.group(1)

        # 5. Live Stream
        if "live.douyin.com" in url:
            clean = url.split("?")[0].rstrip("/")
            room_id = clean.split("/")[-1]
            if room_id and room_id != "live.douyin.com":
                return "live", room_id

        if "/webcast/reflow/" in url:
            if match := re.search(r"/webcast/reflow/(\d+)", url):
                reflow_room_id = match.group(1)
                web_rid = self._resolve_reflow_live_room(reflow_room_id, session)
                return "live", web_rid

        return None, None

    def _resolve_reflow_live_room(self, room_id: str, session: requests.Session) -> str:
        """Resolves mobile webcast reflow room ID to web_rid."""
        try:
            url = Urls.LIVE2 + utils.getXbogus(
                f"live_id=1&room_id={room_id}&app_id=1128"
            )
            resp = session.get(url, headers=douyin_headers, timeout=10)
            data = resp.json()
            return data["data"]["room"]["owner"]["web_rid"]
        except Exception as e:
            logger.error(f"Failed to resolve reflow live room {room_id}: {e}")
            raise DouyinUpstreamError(f"Failed to resolve live room ID: {e}")

    @staticmethod
    def build_canonical_url(key_type: str, key: str) -> str:
        """Builds standard desktop URL."""
        if key_type == "aweme":
            return f"https://www.douyin.com/video/{key}"
        elif key_type == "user":
            return f"https://www.douyin.com/user/{key}"
        elif key_type == "mix":
            return f"https://www.douyin.com/collection/{key}"
        elif key_type == "music":
            return f"https://www.douyin.com/music/{key}"
        elif key_type == "live":
            return f"https://live.douyin.com/{key}"
        return f"https://www.douyin.com/{key}"

    # -------------------------------------------------------------------------
    # Preview Metadata Fetchers
    # -------------------------------------------------------------------------

    def fetch_preview_metadata(
        self, api: DouyinApi, key_type: str, key: str
    ) -> Tuple[str, PreviewMetadata]:
        """Dispatches metadata fetch based on key_type."""
        if key_type == "aweme":
            return self._fetch_aweme_preview(api, key)
        elif key_type == "user":
            return self._fetch_user_preview(api, key)
        elif key_type == "mix":
            return self._fetch_mix_preview(api, key)
        elif key_type == "music":
            return self._fetch_music_preview(api, key)
        elif key_type == "live":
            return self._fetch_live_preview(api, key)
        raise DouyinInvalidUrlError(f"Unsupported key type: {key_type}")

    def _fetch_aweme_preview(
        self, api: DouyinApi, aweme_id: str
    ) -> Tuple[str, PreviewMetadata]:
        try:
            aweme = api.getAwemeInfoApi(aweme_id)
        except Exception as e:
            logger.error(f"Failed to query aweme {aweme_id}: {e}")
            raise DouyinUpstreamError(f"Douyin upstream query failed: {e}")

        if not aweme:
            raise DouyinNotFoundError(
                f"Video or note {aweme_id} not found or has been deleted."
            )

        is_video = aweme.get("awemeType", 0) == 0
        content_type = "video" if is_video else "image"

        author_data = aweme.get("author") or {}
        author = AuthorPreview(
            nickname=author_data.get("nickname") or "Douyin User",
            avatar_thumb=self._pick_first_url(author_data.get("avatar_thumb"))
            or self._pick_first_url(author_data.get("avatar")),
            sec_uid=author_data.get("sec_uid") or "",
            signature=author_data.get("signature") or "",
        )

        cover_url = ""
        if is_video:
            video_data = aweme.get("video") or {}
            cover_url = (
                self._pick_first_url(video_data.get("origin_cover"))
                or self._pick_first_url(video_data.get("cover"))
                or ""
            )
            raw_dur = video_data.get("duration")
            duration = (
                int(raw_dur / 1000)
                if raw_dur and raw_dur > 1000
                else (int(raw_dur) if raw_dur else None)
            )
        else:
            images = aweme.get("images") or []
            cover_url = self._pick_first_url(images[0]) if images else ""
            duration = None

        stats_data = aweme.get("statistics") or {}
        statistics = PreviewStatistics(
            digg_count=stats_data.get("digg_count", 0),
            comment_count=stats_data.get("comment_count", 0),
            share_count=stats_data.get("share_count", 0),
            play_count=stats_data.get("play_count", 0),
            collect_count=stats_data.get("collect_count", 0),
        )

        desc = aweme.get("desc") or ""
        title = desc[:60] if desc else f"Douyin {content_type.capitalize()} {aweme_id}"

        preview = PreviewMetadata(
            title=title,
            desc=desc,
            author=author,
            cover_url=cover_url,
            statistics=statistics,
            duration=duration,
            work_count=len(aweme.get("images", [])) if not is_video else 1,
        )
        return content_type, preview

    def _fetch_user_preview(
        self, api: DouyinApi, sec_uid: str
    ) -> Tuple[str, PreviewMetadata]:
        try:
            posts = api.getUserInfoApi(sec_uid=sec_uid, mode="post", count=1, number=1)
        except Exception as e:
            logger.error(f"Failed to query user {sec_uid}: {e}")
            raise DouyinUpstreamError(f"Douyin upstream query failed: {e}")

        author_data = {}
        if posts and isinstance(posts, list) and len(posts) > 0:
            author_data = posts[0].get("author") or {}

        nickname = author_data.get("nickname") or "Douyin User"
        avatar_thumb = (
            self._pick_first_url(author_data.get("avatar_thumb"))
            or self._pick_first_url(author_data.get("avatar"))
            or ""
        )
        signature = author_data.get("signature") or ""

        author = AuthorPreview(
            nickname=nickname,
            avatar_thumb=avatar_thumb,
            sec_uid=sec_uid,
            signature=signature,
        )
        cover_url = self._pick_first_url(author_data.get("cover_url")) or avatar_thumb

        statistics = PreviewStatistics(
            follower_count=author_data.get("follower_count", 0),
            total_favorited=author_data.get("total_favorited", 0),
            following_count=author_data.get("following_count", 0),
        )

        preview = PreviewMetadata(
            title=f"{nickname} 的个人主页",
            desc=signature or "暂无个人简介",
            author=author,
            cover_url=cover_url,
            statistics=statistics,
            work_count=author_data.get("aweme_count", 0) or 1,
        )
        return "user", preview

    def _fetch_mix_preview(
        self, api: DouyinApi, mix_id: str
    ) -> Tuple[str, PreviewMetadata]:
        try:
            aweme_list = api.getMixInfoApi(mix_id=mix_id, count=1, number=1)
        except Exception as e:
            logger.error(f"Failed to query mix {mix_id}: {e}")
            raise DouyinUpstreamError(f"Douyin upstream query failed: {e}")

        if not aweme_list or not isinstance(aweme_list, list) or len(aweme_list) == 0:
            raise DouyinNotFoundError(f"Mix collection {mix_id} not found or is empty.")

        first = aweme_list[0]
        mix_info = first.get("mix_info") or {}
        author_data = first.get("author") or {}

        mix_name = mix_info.get("mix_name") or f"合集 {mix_id}"
        statis = mix_info.get("statis") or {}
        updated_to = statis.get("updated_to_episode", "?")

        author = AuthorPreview(
            nickname=author_data.get("nickname") or "合集作者",
            avatar_thumb=self._pick_first_url(author_data.get("avatar_thumb")) or "",
            sec_uid=author_data.get("sec_uid") or "",
        )

        cover_url = (
            self._pick_first_url(mix_info.get("cover_url"))
            or self._pick_first_url((first.get("video") or {}).get("cover"))
            or ""
        )

        preview = PreviewMetadata(
            title=mix_name,
            desc=f"合集更新至第 {updated_to} 集",
            author=author,
            cover_url=cover_url,
            work_count=(
                int(updated_to) if str(updated_to).isdigit() else len(aweme_list)
            ),
        )
        return "mix", preview

    def _fetch_music_preview(
        self, api: DouyinApi, music_id: str
    ) -> Tuple[str, PreviewMetadata]:
        try:
            aweme_list = api.getMusicInfo(music_id=music_id, count=1, number=1)
        except Exception as e:
            logger.error(f"Failed to query music {music_id}: {e}")
            raise DouyinUpstreamError(f"Douyin upstream query failed: {e}")

        if not aweme_list or not isinstance(aweme_list, list) or len(aweme_list) == 0:
            raise DouyinNotFoundError(
                f"Music {music_id} not found or has no public works."
            )

        first = aweme_list[0]
        music_data = first.get("music") or {}

        title = music_data.get("title") or f"音乐 {music_id}"
        owner_nickname = music_data.get("owner_nickname") or "原声作者"

        author = AuthorPreview(
            nickname=owner_nickname,
            avatar_thumb=self._pick_first_url(music_data.get("cover_thumb")) or "",
            sec_uid=music_data.get("owner_id") or "",
        )

        cover_url = (
            self._pick_first_url(music_data.get("cover_hd"))
            or self._pick_first_url(music_data.get("cover_large"))
            or ""
        )

        preview = PreviewMetadata(
            title=title,
            desc=f"原声音乐 - {owner_nickname}",
            author=author,
            cover_url=cover_url,
            work_count=len(aweme_list),
        )
        return "music", preview

    def _fetch_live_preview(
        self, api: DouyinApi, web_rid: str
    ) -> Tuple[str, PreviewMetadata]:
        try:
            live_dict, _ = api.getLiveInfoApi(web_rid)
        except Exception as e:
            logger.error(f"Failed to query live {web_rid}: {e}")
            raise DouyinUpstreamError(f"Douyin upstream query failed: {e}")

        if not live_dict:
            raise DouyinNotFoundError(f"Livestream room {web_rid} not found.")

        is_live = live_dict.get("status") == "2"
        status_desc = "正在直播" if is_live else "直播已结束"
        partition = live_dict.get("partition") or "综合"

        author = AuthorPreview(
            nickname=live_dict.get("nickname") or "主播",
            avatar_thumb=live_dict.get("avatar") or "",
            sec_uid=live_dict.get("sec_uid") or "",
        )

        statistics = PreviewStatistics(
            play_count=(
                int(live_dict.get("user_count", 0) or 0)
                if str(live_dict.get("user_count", "")).isdigit()
                else 0
            ),
        )

        preview = PreviewMetadata(
            title=live_dict.get("title") or f"直播间 {web_rid}",
            desc=f"{status_desc} | 分区: {partition}",
            author=author,
            cover_url=live_dict.get("cover") or "",
            statistics=statistics,
            work_count=1,
        )
        return "live", preview

    @staticmethod
    def _pick_first_url(url_container: Any) -> Optional[str]:
        """Safely extracts first string from url_list in dictionary or list."""
        if isinstance(url_container, dict):
            url_list = url_container.get("url_list")
            if isinstance(url_list, list) and len(url_list) > 0:
                return url_list[0]
        elif isinstance(url_container, list) and len(url_container) > 0:
            return url_container[0]
        elif isinstance(url_container, str):
            return url_container
        return None

    # -------------------------------------------------------------------------
    # Download Items Resolution for TaskManager
    # -------------------------------------------------------------------------

    def get_download_items(
        self, req: DownloadRequest, cancel_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
        """
        Resolves media item list to download for a DownloadRequest.
        Used by TaskManager background pipeline.
        """
        api = self._get_api(req.cookie)

        key_type = req.key_type
        key = req.key

        if not key:
            share_url = self.extract_share_url(req.url) or req.url
            resolved_url = self.resolve_redirect_url(share_url, api.session)
            key_type, key = self.extract_key_and_type(resolved_url, api.session)

        if not key or (cancel_event and cancel_event.is_set()):
            return []

        if key_type == "aweme":
            aweme = api.getAwemeInfoApi(key)
            return [aweme] if aweme else []

        elif key_type == "user":
            all_items: List[Dict[str, Any]] = []
            for mode in req.modes:
                if cancel_event and cancel_event.is_set():
                    break
                limit = req.number.get(mode, 0) if req.number else 0
                data = api.getUserInfoApi(
                    sec_uid=key,
                    mode=mode,
                    count=35,
                    number=limit,
                    start_time=req.start_time,
                    end_time=req.end_time,
                )
                if data:
                    all_items.extend(data)
            return all_items

        elif key_type == "mix":
            limit = req.number.get("mix", 0) if req.number else 0
            data = api.getMixInfoApi(
                mix_id=key,
                count=35,
                number=limit,
                start_time=req.start_time,
                end_time=req.end_time,
            )
            return data or []

        elif key_type == "music":
            limit = req.number.get("music", 0) if req.number else 0
            data = api.getMusicInfo(
                music_id=key,
                count=35,
                number=limit,
                start_time=req.start_time,
                end_time=req.end_time,
            )
            return data or []

        return []
