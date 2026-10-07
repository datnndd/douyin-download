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
from urllib.parse import urlparse

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
# Domain Whitelist & Regex Patterns
# ==============================================================================

# Whitelist of legitimate Douyin hostnames for SSRF protection
ALLOWED_HOSTS = (
    "v.douyin.com",
    "douyin.com",
    "www.douyin.com",
    "iesdouyin.com",
    "www.iesdouyin.com",
    "live.douyin.com",
)

# Standard HTTP/HTTPS link regex
SHARE_LINK_REGEX = re.compile(r"https?://[a-zA-Z0-9_./\-?&=%#+:@!~*]+")

# Specific Douyin ecosystem link regex (prioritized for Kouling / share text extraction)
DOUYIN_SPECIFIC_LINK_REGEX = re.compile(
    r"(?:https?://)?(?:[a-zA-Z0-9\-]+\.)?(?:douyin\.com|iesdouyin\.com)/[a-zA-Z0-9_./\-?&=%#+:@!~*]*",
    re.IGNORECASE,
)

PUNCTUATION_STRIP = '),.!?，。！？;；:：\'"【】（）《》、~ \t\r\n'

# Schemeless Douyin URLs embedded in Chinese text, emojis, or punctuation
SCHEMELESS_DOUYIN_REGEX = re.compile(
    r"(?:^|[^\w./-])"
    r"((?:v\.douyin\.com|www\.douyin\.com|douyin\.com|live\.douyin\.com|iesdouyin\.com|www\.iesdouyin\.com)"
    r"(?:/[a-zA-Z0-9_./\-?&=%#+:@!~*]*)?)",
    re.IGNORECASE,
)

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
        """Retrieve or initialize thread-local DouyinApi instance with cookie isolation."""
        if cookie:
            active_cookie = cookie
        elif self._default_cookie:
            active_cookie = self._default_cookie
        else:
            try:
                from src.web.core.config import ConfigManager
                active_cookie = ConfigManager.get_instance().get_cookie_header() or None
            except Exception as e:
                logger.debug(f"Could not load cookie from ConfigManager: {e}")
                active_cookie = None

        if active_cookie:
            from src.douyin import douyin_headers
            douyin_headers["Cookie"] = active_cookie

        api = getattr(self._local, "api", None)
        cached_cookie = getattr(self._local, "cookie", None)

        if api is None or cached_cookie != active_cookie:
            api = DouyinApi(database_path=self._database_path, cookie=active_cookie)
            if active_cookie:
                self._isolate_session_cookie(api.session, active_cookie)
            self._local.api = api
            self._local.cookie = active_cookie
        return api

    @staticmethod
    def _isolate_session_cookie(session: requests.Session, cookie: Optional[str]) -> None:
        """
        Enforces per-request custom cookies on session headers without mutating global state.
        Overrides prepare_request so request-level douyin_headers['Cookie'] cannot clobber it.
        """
        if not cookie:
            return
        session.headers.update({"Cookie": cookie})
        orig_prepare_request = session.prepare_request

        def _custom_prepare_request(request: requests.Request) -> requests.PreparedRequest:
            prep = orig_prepare_request(request)
            prep.headers["Cookie"] = cookie
            return prep

        session.prepare_request = _custom_prepare_request  # type: ignore[method-assign]

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

    @classmethod
    def extract_share_url(cls, text: str) -> Optional[str]:
        """
        Extracts valid Douyin or HTTP/HTTPS URL from raw string or clipboard share text.
        Handles Kouling codes, emojis, surrounding Chinese text, and schemeless links.
        """
        if not text or not str(text).strip():
            return None

        # 1. Prioritize Douyin-specific links in share text
        douyin_match = DOUYIN_SPECIFIC_LINK_REGEX.search(text)
        if douyin_match:
            url = douyin_match.group(0).rstrip(PUNCTUATION_STRIP)
            if url:
                if not url.startswith(("http://", "https://")):
                    url = f"https://{url}"
                return url

        # 2. Search for standard http(s) URL
        matches = SHARE_LINK_REGEX.findall(text)
        if matches:
            url = matches[0].rstrip(PUNCTUATION_STRIP)
            if url:
                return url

        # 3. Search for schemeless Douyin URL pattern fallback
        schemeless = SCHEMELESS_DOUYIN_REGEX.search(text)
        if schemeless:
            raw_url = schemeless.group(1).rstrip(PUNCTUATION_STRIP)
            if raw_url:
                return f"https://{raw_url}"

        return None

    @classmethod
    def resolve_redirect_url(cls, url: str, session: requests.Session) -> str:
        """
        Follows HTTP redirects for short URLs (v.douyin.com) to find final destination.
        Validates hostname against allowed whitelist to prevent SSRF and cookie exfiltration.
        Properly closes streaming response with context manager.
        """
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
        except Exception:
            return url

        # Only follow redirects for known Douyin shortlink hosts
        if hostname == "v.douyin.com" or (
            hostname in ("iesdouyin.com", "www.iesdouyin.com") and "/share" in (parsed.path or "")
        ):
            try:
                # Use stream=True and context manager to avoid memory leaks and unclosed sockets
                with session.get(
                    url,
                    headers=douyin_headers,
                    allow_redirects=True,
                    timeout=10,
                    stream=True,
                ) as resp:
                    final_url = str(resp.url)
                    # Verify destination host belongs to Douyin ecosystem
                    dest_parsed = urlparse(final_url)
                    dest_host = (dest_parsed.hostname or "").lower()
                    if (
                        dest_host in ALLOWED_HOSTS
                        or dest_host.endswith(".douyin.com")
                        or dest_host.endswith(".iesdouyin.com")
                    ):
                        return final_url
                    logger.warning(f"Redirect destination {final_url} is outside allowed Douyin domains.")
                    return url
            except Exception as e:
                logger.error(f"Failed to resolve short URL redirect for {url}: {e}")
                raise DouyinUpstreamError(f"Failed to follow short link redirect: {e}")
        return url

    def extract_key_and_type(
        self, url: str, session: requests.Session
    ) -> Tuple[Optional[str], Optional[str]]:
        """Matches URL against patterns for the 5 key types, strictly validating hostname."""
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
        except Exception:
            return None, None

        if not hostname or (
            hostname not in ALLOWED_HOSTS
            and not hostname.endswith(".douyin.com")
            and not hostname.endswith(".iesdouyin.com")
        ):
            return None, None

        path = parsed.path or ""

        # 1. Aweme (Video/Note)
        for pattern in AWEME_PATTERNS:
            if match := pattern.search(path):
                return "aweme", match.group(1)

        # 2. User Profile
        for pattern in USER_PATTERNS:
            if match := pattern.search(path):
                return "user", match.group(1)

        # 3. Mix / Collection
        for pattern in MIX_PATTERNS:
            if match := pattern.search(path):
                return "mix", match.group(1)

        # 4. Music
        for pattern in MUSIC_PATTERNS:
            if match := pattern.search(path):
                return "music", match.group(1)

        # 5. Live Stream
        if hostname == "live.douyin.com":
            clean_path = path.strip("/")
            room_id = clean_path.split("/")[-1] if clean_path else ""
            if room_id and room_id != "live.douyin.com":
                return "live", room_id

        if "/webcast/reflow/" in path or "/webcast/reflow/" in url:
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

        is_video = (str(aweme.get("awemeType", "0")) == "0") and not bool(aweme.get("images"))
        content_type = "video" if is_video else "image"

        author_data = aweme.get("author") or {}
        author_avatar = self._pick_first_url(author_data.get("avatar"))
        author_thumb = self._pick_first_url(author_data.get("avatar_thumb")) or author_avatar or ""
        author = AuthorPreview(
            nickname=author_data.get("nickname") or "Douyin User",
            avatar_thumb=author_thumb,
            avatar=author_avatar or author_thumb,
            sec_uid=author_data.get("sec_uid") or "",
            signature=author_data.get("signature") or "",
            unique_id=author_data.get("unique_id") or "",
            short_id=author_data.get("short_id") or "",
        )

        cover_url = ""
        image_urls = []
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
            for img in images:
                u = self._pick_first_url(img)
                if u:
                    image_urls.append(u)
            cover_url = image_urls[0] if image_urls else ""
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
            work_count=len(image_urls) if not is_video else 1,
            images=image_urls,
            extra={
                "create_time": aweme.get("create_time", ""),
                "aweme_id": aweme_id,
            },
        )
        return content_type, preview

    def _fetch_user_preview(
        self, api: DouyinApi, sec_uid: str
    ) -> Tuple[str, PreviewMetadata]:
        author_data = {}
        # Try getUserDetailApi first if available
        if hasattr(api, "getUserDetailApi"):
            try:
                detail = api.getUserDetailApi(sec_uid)
                if isinstance(detail, dict) and detail.get("nickname"):
                    author_data = detail
            except Exception as e:
                logger.debug(f"getUserDetailApi fallback: {e}")

        # Fallback or supplement with getUserInfoApi
        if not author_data or not author_data.get("nickname"):
            try:
                posts = api.getUserInfoApi(sec_uid=sec_uid, mode="post", count=1, number=1)
            except Exception as e:
                if not author_data:
                    logger.error(f"Failed to query user {sec_uid}: {e}")
                    raise DouyinUpstreamError(f"Douyin upstream query failed: {e}")
                posts = None

            if posts and isinstance(posts, list) and len(posts) > 0:
                post_author = posts[0].get("author") or {}
                if not author_data:
                    author_data = post_author
                else:
                    for k, v in post_author.items():
                        if not author_data.get(k) and v:
                            author_data[k] = v

        nickname = author_data.get("nickname") or "Douyin User"
        avatar = self._pick_first_url(author_data.get("avatar"))
        avatar_thumb = (
            self._pick_first_url(author_data.get("avatar_thumb"))
            or avatar
            or ""
        )
        signature = author_data.get("signature") or ""

        author = AuthorPreview(
            nickname=nickname,
            avatar_thumb=avatar_thumb,
            avatar=avatar or avatar_thumb,
            sec_uid=sec_uid,
            signature=signature,
            unique_id=author_data.get("unique_id") or "",
            short_id=author_data.get("short_id") or "",
            follower_count=author_data.get("follower_count", 0),
            total_favorited=author_data.get("total_favorited", 0),
            following_count=author_data.get("following_count", 0),
        )
        cover_url = self._pick_first_url(author_data.get("cover_url")) or avatar or avatar_thumb

        statistics = PreviewStatistics(
            follower_count=author_data.get("follower_count", 0),
            total_favorited=author_data.get("total_favorited", 0),
            following_count=author_data.get("following_count", 0),
        )

        raw_work_count = author_data.get("aweme_count", 0)
        try:
            work_count = int(raw_work_count) if raw_work_count is not None and str(raw_work_count).strip() != "" else 0
        except (ValueError, TypeError):
            work_count = 0

        preview = PreviewMetadata(
            title=f"{nickname}'s Profile",
            desc=signature or "No bio available",
            author=author,
            cover_url=cover_url,
            statistics=statistics,
            work_count=work_count,
            extra={
                "unique_id": author_data.get("unique_id", ""),
                "short_id": author_data.get("short_id", ""),
                "aweme_count": work_count,
            },
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

        mix_name = mix_info.get("mix_name") or f"Collection {mix_id}"
        statis = mix_info.get("statis") or {}
        updated_to = statis.get("updated_to_episode", "?")

        author = AuthorPreview(
            nickname=author_data.get("nickname") or "Collection Author",
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
            desc=f"Collection updated to episode {updated_to}",
            author=author,
            cover_url=cover_url,
            work_count=(
                int(updated_to) if str(updated_to).isdigit() else len(aweme_list)
            ),
            extra={
                "updated_to_episode": updated_to,
                "current_episode": statis.get("current_episode", ""),
                "mix_id": mix_id,
            },
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

        title = music_data.get("title") or f"Music {music_id}"
        owner_nickname = music_data.get("owner_nickname") or "Original Artist"

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
            desc=f"Original Soundtrack - {owner_nickname}",
            author=author,
            cover_url=cover_url,
            work_count=len(aweme_list),
            extra={
                "music_id": music_id,
                "owner_nickname": owner_nickname,
                "owner_id": music_data.get("owner_id", ""),
            },
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
        status_desc = "Live Streaming" if is_live else "Stream Ended"
        partition = live_dict.get("partition") or "General"

        author = AuthorPreview(
            nickname=live_dict.get("nickname") or "Streamer",
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
            title=live_dict.get("title") or f"Live Room {web_rid}",
            desc=f"{status_desc} | Category: {partition}",
            author=author,
            cover_url=live_dict.get("cover") or "",
            statistics=statistics,
            work_count=1,
            extra={
                "is_live": is_live,
                "status": live_dict.get("status"),
                "partition": partition,
                "web_rid": web_rid,
                "user_count": live_dict.get("user_count"),
            },
        )
        return "live", preview

    @staticmethod
    def _pick_first_url(url_container: Any) -> Optional[str]:
        """Safely extracts first valid non-null string from url_list in dictionary or list."""
        if isinstance(url_container, dict):
            url_list = url_container.get("url_list")
            if isinstance(url_list, list):
                for u in url_list:
                    if u and isinstance(u, str) and u.strip():
                        return u.strip()
        elif isinstance(url_container, list):
            for u in url_container:
                if u and isinstance(u, str) and u.strip():
                    return u.strip()
        elif isinstance(url_container, str) and url_container.strip():
            return url_container.strip()
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
                if mode in ("mix", "allmix"):
                    mixes = api.getUserAllMixInfoApi(
                        sec_uid=key,
                        count=35,
                        start_time=req.start_time,
                        end_time=req.end_time,
                    )
                    if mixes and isinstance(mixes, dict):
                        for mix_id in mixes.keys():
                            if cancel_event and cancel_event.is_set():
                                break
                            mix_items = api.getMixInfoApi(
                                mix_id=mix_id,
                                count=35,
                                number=limit,
                                start_time=req.start_time,
                                end_time=req.end_time,
                            )
                            if mix_items:
                                all_items.extend(mix_items)
                                if limit > 0 and len(all_items) >= limit:
                                    all_items = all_items[:limit]
                                    break
                else:
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
