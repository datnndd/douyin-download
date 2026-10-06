# Comprehensive Analysis & Implementation Plan: DouyinService & Link Resolution

**Author**: M1 Explorer 2 (Douyin Service & Link Resolution)  
**Target File**: `src/web/services/douyin_service.py`  
**Milestone**: M1 (Backend Engine & Task Concurrency)  
**Date**: 2026-10-06  

---

## 1. Executive Summary

This report establishes the complete architectural and implementation specification for `src/web/services/douyin_service.py`. The service functions as the foundational gateway between the FastAPI asynchronous web layer and the underlying Douyin API/crawler mechanics (`src/douyin/douyinapi.py`, `src/common/abogus.py`, `src/common/utils.py`).

### Key Accomplishments & Deliverables in this Plan:
1. **Thread-Safe Asynchronous Concurrency**: Solves severe concurrency defects in legacy `DouyinApi` (shared mutable `Result.awemeDict`, non-thread-safe SQLite connection in `Database`, mutable `requests.Session` headers) by employing thread-local encapsulation (`threading.local`) coupled with non-blocking offloading via `asyncio.to_thread`.
2. **Unified 5-Type Link Resolution**: Formulates a link extraction and normalization engine capable of resolving dirty clipboard text containing Chinese share strings, short links (`v.douyin.com`), mobile share links (`iesdouyin.com`), and direct desktop URLs into canonical formats for all 5 key types:
   - `aweme` (single videos and image notes)
   - `user` (profile pages)
   - `mix` (collections / series)
   - `music` (audio tracks)
   - `live` (web livestreams and mobile webcast reflows)
3. **Rich Preview Card Generation**: Extracts structured metadata required by the React frontend (`PreviewCard.tsx`), including author profile (nickname, high-res avatar, sec_uid), cover image thumbnails, play/digg/comment statistics, video duration, and estimated work counts.
4. **Structured Error Hierarchy**: Maps network timeouts, upstream rate limits/captchas, missing resources, and invalid input strings into strongly-typed domain exceptions mapped to clean HTTP status codes (`400 Bad Request`, `404 Not Found`, `502 Bad Gateway`).

---

## 2. Legacy Engine Inspection & Concurrency Defect Analysis

### 2.1 Inspection of `src/douyin/douyinapi.py`
Inspection of `src/douyin/douyinapi.py` revealed several critical implementation details and thread-safety hazards:

1. **Shared Mutable `Result` State (Lines 42, 184–203, 347–382)**:
   ```python
   # Line 42
   self.result = Result()
   ...
   # Line 184-196 in getAwemeInfoApi:
   self.result.clearDict(self.result.awemeDict)
   ...
   self.result.dataConvert(awemeType, self.result.awemeDict, datadict['aweme_detail'])
   aweme_data = copy.deepcopy(self.result.awemeDict)
   return self.result.awemeDict
   ```
   **Hazard**: `self.result.awemeDict` and `self.result.liveDict` are instance variables on `self.result`. When multiple requests run concurrently, Thread A calling `clearDict()` immediately corrupts or wipes the dictionary being populated by Thread B.
2. **SQLite Thread Affinity in `Database` (Lines 45, 201, 311, `database.py:20`)**:
   ```python
   # database.py:20
   self.conn = sqlite3.connect(self.path)
   ```
   **Hazard**: In Python's standard `sqlite3` library, connections have thread affinity. If `DouyinApi` is instantiated on the main thread and its methods are later executed inside worker threads via `asyncio.to_thread`, SQLite will throw:
   `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
3. **Link Extraction Bottleneck in `getKey()` (Lines 69–117)**:
   ```python
   def getKey(self, url):
       try:
           r = self.session.get(url=url, headers=douyin_headers)
       except Exception as e:
           ...
       urlstr = str(r.request.path_url)
       if "/user/" in urlstr: ...
   ```
   **Deficiencies**:
   - For already unshortened desktop URLs (e.g. `https://www.douyin.com/video/7488893440932039970`), `getKey()` makes a redundant, blocking HTTP GET request to download the entire HTML page before inspecting the URL string.
   - It relies on `r.request.path_url`, which truncates full domain contexts needed for certain edge cases (e.g., `live.douyin.com` check on line 109).
   - If the input string contains share text (e.g. `"7.35 复制打开抖音... https://v.douyin.com/xyz/"`), passing it to `getKey()` without prior regex extraction fails with network exceptions.

### 2.2 Inspection of `src/common/abogus.py` & `src/common/utils.py`
- `src/common/abogus.py`: Contains pure Python cryptographic generation (`sm3`, `rc4_encrypt`, `get_value`) generating the `a_bogus` parameter for `POST_DETAIL` (`/aweme/v1/web/aweme/detail/`). It is stateless per call and thread-safe.
- `src/common/utils.py`: Contains `getXbogus(payload)` using MD5 and RC4-like permutations for user, mix, and music endpoints. It is also stateless and thread-safe.
- `Utils.getttwid()` (lines 60–70) sends a POST request to `ttwid.bytedance.com`. In test environments, `tests/conftest.py` monkeypatches this to avoid network calls.

---

## 3. Link Resolution & Normalization Specification

### 3.1 Input Extraction Pipeline
Users may paste raw mobile app share strings, short links, or full URLs:

```
[Raw Input String]
        │
        ▼
[Regex URL Matcher] ──► Extracts clean HTTP/HTTPS URL
        │
        ▼
[Short Link Check]
        ├─► If v.douyin.com / iesdouyin.com ──► Follow redirect (stream=True) ──► Final URL
        └─► If direct desktop URL ─────────────► Bypass network redirect ──────► Final URL
        │
        ▼
[Type & Key Matcher] ──► Extracts key_type & key (aweme, user, mix, music, live)
        │
        ▼
[Canonical URL Formatter] ──► Reconstructs clean standard URL
```

### 3.2 Regular Expression Matchers for All 5 Key Types

| Key Type | Pattern Regexes | Example Source URL | Extracted ID / Key |
|---|---|---|---|
| **aweme** (Video / Note) | `r'/video/(\d+)'`<br>`r'/note/(\d+)'`<br>`r'/share/video/(\d+)'`<br>`r'/share/note/(\d+)'` | `https://www.douyin.com/video/7488893440932039970`<br>`https://www.douyin.com/note/7488893440932039971` | `7488893440932039970`<br>`7488893440932039971` |
| **user** (Profile) | `r'/user/([a-zA-Z0-9_\-]+)'`<br>`r'/share/user/([a-zA-Z0-9_\-]+)'` | `https://www.douyin.com/user/MS4wLjABAAAA_test_author` | `MS4wLjABAAAA_test_author` (`sec_uid`) |
| **mix** (Collection) | `r'/mix/detail/(\d+)'`<br>`r'/collection/(\d+)'` | `https://www.douyin.com/collection/7488893440932039972` | `7488893440932039972` |
| **music** (Audio) | `r'/music/(\d+)'` | `https://www.douyin.com/music/7488893440932039973` | `7488893440932039973` |
| **live** (Stream) | `r'live\.douyin\.com/([a-zA-Z0-9_]+)'`<br>`r'/webcast/reflow/(\d+)'` | `https://live.douyin.com/7488893440932039974`<br>`https://www.douyin.com/webcast/reflow/12345` | `7488893440932039974`<br>(Requires reflow resolve -> `web_rid`) |

### 3.3 Special Case: Webcast Reflow Resolution
When a mobile livestream URL in the format `https://www.douyin.com/webcast/reflow/<room_id>` is encountered, the extracted ID is a internal `room_id`, but Douyin's web live API requires `web_rid`.
`DouyinService` resolves this via:
```python
def _resolve_reflow_live_room(self, room_id: str, session: requests.Session) -> str:
    url = Urls.LIVE2 + utils.getXbogus(f"live_id=1&room_id={room_id}&app_id=1128")
    resp = session.get(url, headers=douyin_headers, timeout=10)
    data = resp.json()
    return data["data"]["room"]["owner"]["web_rid"]
```

### 3.4 Canonical URL Normalization
Once the key type and key are resolved, `DouyinService` generates a deterministic canonical URL:
- `aweme`: `f"https://www.douyin.com/video/{key}"`
- `user`: `f"https://www.douyin.com/user/{key}"`
- `mix`: `f"https://www.douyin.com/collection/{key}"`
- `music`: `f"https://www.douyin.com/music/{key}"`
- `live`: `f"https://live.douyin.com/{key}"`

---

## 4. Thread-Safe Asynchronous Concurrency Architecture

### 4.1 Non-Blocking Execution via `asyncio.to_thread`
In FastAPI, route handlers execute on the async event loop. Any blocking HTTP call or retry sleep freezes the event loop for all connected clients.
All Douyin network interactions must be dispatched to worker threads:
```python
async def parse_url(self, url: str, cookie: Optional[str] = None) -> ParseResponse:
    return await asyncio.to_thread(self._sync_parse_url, url, cookie)
```

### 4.2 Thread-Local Engine Isolation (`threading.local`)
To guarantee complete isolation between worker threads without costly global mutexes:
1. `DouyinService` maintains a `threading.local()` store.
2. When a worker thread executes `_sync_parse_url`, it accesses its thread-local `DouyinApi` instance.
3. If no instance exists for the current thread or if the request specifies a different cookie, a fresh `DouyinApi(database_path=self._db_path, cookie=active_cookie)` instance is initialized for that thread.

**Benefits**:
- **Zero Race Conditions**: Each thread possesses its own `Result` instance, preventing `clearDict` corruption.
- **Connection Reuse**: Each thread maintains its own `requests.Session` with keep-alive HTTP connection pooling.
- **SQLite Concurrency**: If a database is used, each thread has its own SQLite connection, preventing `sqlite3.ProgrammingError`.
- **Dynamic Cookie Support**: Threads can safely handle per-request custom cookies without altering global session state.

---

## 5. Rich Preview Card Payload Extraction

The two-step download interaction requires a rich preview card returning author details, cover images, work counts, and engagement metrics.

### 5.1 Extraction Matrix by Key Type

#### A. Single Video or Note (`key_type: "aweme"`)
- **API Call**: `api.getAwemeInfoApi(aweme_id)`
- **`content_type`**: `"video"` if `awemeType == 0`, else `"image"`
- **`title`**: First 60 characters of `aweme["desc"]` or caption.
- **`desc`**: Full `aweme["desc"]`.
- **`author`**:
  - `nickname`: `aweme["author"]["nickname"]`
  - `avatar_thumb`: `aweme["author"]["avatar_thumb"]["url_list"][0]` (or large avatar `aweme["author"]["avatar"]["url_list"][0]`)
  - `sec_uid`: `aweme["author"]["sec_uid"]`
  - `signature`: `aweme["author"].get("signature", "")`
- **`cover_url`**:
  - If video: `aweme["video"]["origin_cover"]["url_list"][0]` or `aweme["video"]["cover"]["url_list"][0]`
  - If image note: `aweme["images"][0]["url_list"][0]`
- **`statistics`**:
  - `digg_count`: `int(aweme["statistics"].get("digg_count", 0))`
  - `comment_count`: `int(aweme["statistics"].get("comment_count", 0))`
  - `share_count`: `int(aweme["statistics"].get("share_count", 0))`
  - `play_count`: `int(aweme["statistics"].get("play_count", 0))`
  - `collect_count`: `int(aweme["statistics"].get("collect_count", 0))`
- **`duration`**: Integer seconds (`int(aweme["video"]["duration"] / 1000)` if milliseconds, or raw seconds).
- **`work_count`**: `1` (or number of images if image note).

#### B. User Profile (`key_type: "user"`)
- **API Call**: `api.getUserInfoApi(sec_uid, mode="post", count=1, number=1)`
- **`content_type`**: `"user"`
- **Fallback / Data Source**:
  - If posts exist: Extract `author = posts[0]["author"]`.
  - If no posts: Query `USER_DETAIL` (`/aweme/v1/web/user/profile/other/?`) with `sec_user_id`.
- **`title`**: `f"{author['nickname']} 的主页"`
- **`desc`**: `author.get("signature", "暂无简介")`
- **`author`**:
  - `nickname`: `author["nickname"]`
  - `avatar_thumb`: `author["avatar_thumb"]["url_list"][0]`
  - `sec_uid`: `sec_uid`
  - `signature`: `author.get("signature", "")`
- **`cover_url`**: `author.get("cover_url", {}).get("url_list", [None])[0]` or avatar.
- **`statistics`**:
  - `follower_count`: `author.get("follower_count", 0)`
  - `total_favorited`: `author.get("total_favorited", 0)`
  - `following_count`: `author.get("following_count", 0)`
- **`work_count`**: `author.get("aweme_count", 0)` or estimated posts count.

#### C. Collection / Series (`key_type: "mix"`)
- **API Call**: `api.getMixInfoApi(mix_id, count=1, number=1)`
- **`content_type`**: `"mix"`
- **Data Source**: Inspect first aweme's `mix_info` and `author`.
- **`title`**: `mix_info.get("mix_name", f"合集 {mix_id}")`
- **`desc`**: `f"合集更新至第 {mix_info.get('statis', {}).get('updated_to_episode', '?')} 集"`
- **`author`**: First aweme's author object.
- **`cover_url`**: `mix_info.get("cover_url", {}).get("url_list", [None])[0]` or first aweme's cover.
- **`statistics`**: Aggregate engagement of available episodes.
- **`work_count`**: `int(mix_info.get("statis", {}).get("updated_to_episode", 0))` or length of episodes.

#### D. Music Track (`key_type: "music"`)
- **API Call**: `api.getMusicInfo(music_id, count=1, number=1)`
- **`content_type`**: `"music"`
- **Data Source**: Inspect first aweme's `music` block.
- **`title`**: `music.get("title", f"音乐 {music_id}")`
- **`desc`**: `f"原声音乐 - {music.get('owner_nickname', '未知作者')}"`
- **`author`**:
  - `nickname`: `music.get("owner_nickname", "原声作者")`
  - `sec_uid`: `music.get("owner_id", "")`
  - `avatar_thumb`: `music.get("cover_thumb", {}).get("url_list", [None])[0]`
- **`cover_url`**: `music.get("cover_hd", {}).get("url_list", [None])[0]` or `music.get("cover_large", {}).get("url_list", [None])[0]`
- **`work_count`**: Estimated count of videos using track.

#### E. Livestream (`key_type: "live"`)
- **API Call**: `api.getLiveInfoApi(web_rid)`
- **`content_type`**: `"live"`
- **Returns**: `(liveDict, live_json)`
- **`title`**: `liveDict.get("title", f"直播间 {web_rid}")`
- **`desc`**: `f"{'正在直播' if liveDict.get('status') == '2' else '直播已结束'} | 分区: {liveDict.get('partition', '综合')}"`
- **`author`**:
  - `nickname`: `liveDict.get("nickname", "主播")`
  - `sec_uid`: `liveDict.get("sec_uid", "")`
  - `avatar_thumb`: `liveDict.get("avatar", "")`
- **`cover_url`**: `liveDict.get("cover", "")`
- **`statistics`**:
  - `user_count`: `liveDict.get("user_count", "0")`
  - `display_long`: `liveDict.get("display_long", "")`
- **`work_count`**: `1`

---

## 6. Error Handling & HTTP Status Classification

To avoid generic 500 crashes and provide clear guidance to the frontend user, `DouyinService` implements a dedicated domain exception hierarchy:

```
DouyinServiceError (Exception)
├── DouyinInvalidUrlError (status_code = 400)
├── DouyinNotFoundError (status_code = 404)
└── DouyinUpstreamError (status_code = 502)
```

### 6.1 Classification Criteria

```python
class DouyinServiceError(Exception):
    """Base exception for Douyin service errors."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class DouyinInvalidUrlError(DouyinServiceError):
    """Raised when URL is empty, unsupported, or malformed (HTTP 400)."""
    def __init__(self, message: str = "Invalid or unsupported Douyin URL"):
        super().__init__(message, status_code=400)

class DouyinNotFoundError(DouyinServiceError):
    """Raised when the target video, user, or mix was deleted or does not exist (HTTP 404)."""
    def __init__(self, message: str = "Douyin content not found or deleted"):
        super().__init__(message, status_code=404)

class DouyinUpstreamError(DouyinServiceError):
    """Raised when Douyin rate-limits, triggers anti-bot captchas, or blocks requests (HTTP 502)."""
    def __init__(self, message: str = "Douyin upstream service error or anti-bot block"):
        super().__init__(message, status_code=502)
```

### 6.2 Upstream Douyin Error Heuristics
1. **Bad URL (400)**:
   - No valid URL extracted by `SHARE_LINK_REGEX`.
   - Domain not belonging to Douyin (`douyin.com`, `iesdouyin.com`, `amemv.com`).
   - Path does not match any of the 5 key types.
2. **Deleted / Inaccessible (404)**:
   - `getAwemeInfoApi` returns empty or `datadict.get("aweme_detail") is None`.
   - API status code indicates deleted content (e.g. status code 2048: "作品已被删除", status code 2049: "视频不可见").
   - `getUserInfoApi` returns no user profile for an invalid `sec_uid`.
3. **Upstream Block / Rate Limit (502)**:
   - Upstream returns empty string (`len(response.text) == 0`).
   - Anti-bot risk control status (e.g. status code != 0 with captcha prompt).
   - Network timeouts (`requests.exceptions.Timeout`) connecting to Douyin endpoints.
   - User notification: `"Douyin anti-scraping risk control triggered. Please configure valid cookies in Settings."`
4. **Special Livestream Offline Graceful Handling**:
   - When `liveDict["status"] == "4"` (Stream ended), it is **not** treated as an error. The service returns HTTP 200 with `desc: "直播已结束"` and offline badges so the user sees the streamer profile rather than an error banner.

---

## 7. Complete Proposed Implementation Architecture

Below is the concrete design for `src/web/services/douyin_service.py`:

```python
# -*- coding: utf-8 -*-
"""
DouyinService: Thread-safe, non-blocking asynchronous service for resolving Douyin
links and generating rich content previews across all 5 key types.
"""

import asyncio
import copy
import logging
import re
import threading
from typing import Any, Dict, Optional, Tuple

import requests

from src.douyin.douyinapi import DouyinApi
from src.douyin.urls import Urls
from src.douyin import douyin_headers
from src.common import utils
from src.web.core.schemas import (
    ParseResponse,
    PreviewMetadata,
    AuthorPreview,
    PreviewStatistics,
)

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Domain Exceptions
# -----------------------------------------------------------------------------

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
    def __init__(self, message: str = "Douyin upstream service error or anti-bot block"):
        super().__init__(message, status_code=502)


# -----------------------------------------------------------------------------
# Regex Patterns
# -----------------------------------------------------------------------------

SHARE_LINK_REGEX = re.compile(r'https?://(?:[a-zA-Z0-9$-_@.&+!*(),]|%[0-9a-fA-F]{2})+')

AWEME_PATTERNS = [
    re.compile(r'/video/(\d+)'),
    re.compile(r'/note/(\d+)'),
    re.compile(r'/share/video/(\d+)'),
    re.compile(r'/share/note/(\d+)'),
]
USER_PATTERNS = [
    re.compile(r'/user/([a-zA-Z0-9_\-]+)'),
    re.compile(r'/share/user/([a-zA-Z0-9_\-]+)'),
]
MIX_PATTERNS = [
    re.compile(r'/mix/detail/(\d+)'),
    re.compile(r'/collection/(\d+)'),
]
MUSIC_PATTERNS = [
    re.compile(r'/music/(\d+)'),
]
LIVE_PATTERNS = [
    re.compile(r'live\.douyin\.com/([a-zA-Z0-9_]+)'),
    re.compile(r'/webcast/reflow/(\d+)'),
]


# -----------------------------------------------------------------------------
# Service Implementation
# -----------------------------------------------------------------------------

class DouyinService:
    """
    Thread-safe asynchronous service wrapping DouyinApi.
    Provides non-blocking link resolution and preview extraction.
    """

    def __init__(self, default_cookie: Optional[str] = None, database_path: Optional[str] = None):
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

    async def parse_url(self, raw_input: str, cookie: Optional[str] = None) -> ParseResponse:
        """
        Non-blocking URL parsing and preview metadata extraction.
        Offloaded to worker thread via asyncio.to_thread.
        """
        return await asyncio.to_thread(self._sync_parse_url, raw_input, cookie)

    # -------------------------------------------------------------------------
    # Synchronous Execution Core (Runs in worker thread)
    # -------------------------------------------------------------------------

    def _sync_parse_url(self, raw_input: str, cookie: Optional[str] = None) -> ParseResponse:
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
            raise DouyinInvalidUrlError(f"Unsupported Douyin link structure: {resolved_url}")

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
        return matches[0] if matches else None

    @staticmethod
    def resolve_redirect_url(url: str, session: requests.Session) -> str:
        """Follows HTTP redirects for short URLs (v.douyin.com) to find final destination."""
        if "v.douyin.com" in url or "iesdouyin.com/share" in url:
            try:
                # Use stream=True to avoid reading large response payloads
                resp = session.get(url, headers=douyin_headers, allow_redirects=True, timeout=10, stream=True)
                return str(resp.url)
            except Exception as e:
                logger.error(f"Failed to resolve short URL redirect for {url}: {e}")
                raise DouyinUpstreamError(f"Failed to follow short link redirect: {e}")
        return url

    def extract_key_and_type(self, url: str, session: requests.Session) -> Tuple[Optional[str], Optional[str]]:
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
            # Extract path segment
            clean = url.split("?")[0].rstrip("/")
            room_id = clean.split("/")[-1]
            if room_id and room_id != "live.douyin.com":
                return "live", room_id

        if "/webcast/reflow/" in url:
            if match := re.search(r'/webcast/reflow/(\d+)', url):
                reflow_room_id = match.group(1)
                web_rid = self._resolve_reflow_live_room(reflow_room_id, session)
                return "live", web_rid

        return None, None

    def _resolve_reflow_live_room(self, room_id: str, session: requests.Session) -> str:
        """Resolves mobile webcast reflow room ID to web_rid."""
        try:
            url = Urls.LIVE2 + utils.getXbogus(f"live_id=1&room_id={room_id}&app_id=1128")
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

    def fetch_preview_metadata(self, api: DouyinApi, key_type: str, key: str) -> Tuple[str, PreviewMetadata]:
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

    def _fetch_aweme_preview(self, api: DouyinApi, aweme_id: str) -> Tuple[str, PreviewMetadata]:
        aweme = api.getAwemeInfoApi(aweme_id)
        if not aweme:
            raise DouyinNotFoundError(f"Video or note {aweme_id} not found or has been deleted.")

        is_video = aweme.get("awemeType", 0) == 0
        content_type = "video" if is_video else "image"

        author_data = aweme.get("author") or {}
        author = AuthorPreview(
            nickname=author_data.get("nickname") or "Douyin User",
            avatar_thumb=self._pick_first_url(author_data.get("avatar_thumb")) or self._pick_first_url(author_data.get("avatar")),
            sec_uid=author_data.get("sec_uid") or "",
            signature=author_data.get("signature") or "",
        )

        # Cover selection
        cover_url = None
        if is_video:
            video_data = aweme.get("video") or {}
            cover_url = self._pick_first_url(video_data.get("origin_cover")) or self._pick_first_url(video_data.get("cover"))
            raw_dur = video_data.get("duration")
            duration = int(raw_dur / 1000) if raw_dur and raw_dur > 1000 else (int(raw_dur) if raw_dur else None)
        else:
            images = aweme.get("images") or []
            cover_url = self._pick_first_url(images[0]) if images else None
            duration = None

        stats_data = aweme.get("statistics") or {}
        statistics = PreviewStatistics(
            digg_count=int(stats_data.get("digg_count", 0) or 0),
            comment_count=int(stats_data.get("comment_count", 0) or 0),
            share_count=int(stats_data.get("share_count", 0) or 0),
            play_count=int(stats_data.get("play_count", 0) or 0),
            collect_count=int(stats_data.get("collect_count", 0) or 0),
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

    def _fetch_user_preview(self, api: DouyinApi, sec_uid: str) -> Tuple[str, PreviewMetadata]:
        # Peek at user's latest post to extract author metadata
        posts = api.getUserInfoApi(sec_uid=sec_uid, mode="post", count=1, number=1)
        author_data = {}
        if posts and isinstance(posts, list) and len(posts) > 0:
            author_data = posts[0].get("author") or {}

        nickname = author_data.get("nickname") or "Douyin User"
        avatar_thumb = self._pick_first_url(author_data.get("avatar_thumb")) or self._pick_first_url(author_data.get("avatar"))
        signature = author_data.get("signature") or ""

        author = AuthorPreview(
            nickname=nickname,
            avatar_thumb=avatar_thumb,
            sec_uid=sec_uid,
            signature=signature,
        )
        cover_url = self._pick_first_url(author_data.get("cover_url")) or avatar_thumb

        statistics = PreviewStatistics(
            follower_count=int(author_data.get("follower_count", 0) or 0),
            total_favorited=int(author_data.get("total_favorited", 0) or 0),
            following_count=int(author_data.get("following_count", 0) or 0),
        )

        preview = PreviewMetadata(
            title=f"{nickname} 的个人主页",
            desc=signature or "暂无个人简介",
            author=author,
            cover_url=cover_url,
            statistics=statistics,
            work_count=author_data.get("aweme_count", 0) or None,
        )
        return "user", preview

    def _fetch_mix_preview(self, api: DouyinApi, mix_id: str) -> Tuple[str, PreviewMetadata]:
        aweme_list = api.getMixInfoApi(mix_id=mix_id, count=1, number=1)
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
            avatar_thumb=self._pick_first_url(author_data.get("avatar_thumb")),
            sec_uid=author_data.get("sec_uid") or "",
        )

        cover_url = self._pick_first_url(mix_info.get("cover_url")) or self._pick_first_url((first.get("video") or {}).get("cover"))

        preview = PreviewMetadata(
            title=mix_name,
            desc=f"合集更新至第 {updated_to} 集",
            author=author,
            cover_url=cover_url,
            work_count=int(updated_to) if str(updated_to).isdigit() else len(aweme_list),
        )
        return "mix", preview

    def _fetch_music_preview(self, api: DouyinApi, music_id: str) -> Tuple[str, PreviewMetadata]:
        aweme_list = api.getMusicInfo(music_id=music_id, count=1, number=1)
        if not aweme_list or not isinstance(aweme_list, list) or len(aweme_list) == 0:
            raise DouyinNotFoundError(f"Music {music_id} not found or has no public works.")

        first = aweme_list[0]
        music_data = first.get("music") or {}

        title = music_data.get("title") or f"音乐 {music_id}"
        owner_nickname = music_data.get("owner_nickname") or "原声作者"

        author = AuthorPreview(
            nickname=owner_nickname,
            avatar_thumb=self._pick_first_url(music_data.get("cover_thumb")),
            sec_uid=music_data.get("owner_id") or "",
        )

        cover_url = self._pick_first_url(music_data.get("cover_hd")) or self._pick_first_url(music_data.get("cover_large"))

        preview = PreviewMetadata(
            title=title,
            desc=f"原声音乐 - {owner_nickname}",
            author=author,
            cover_url=cover_url,
            work_count=len(aweme_list),
        )
        return "music", preview

    def _fetch_live_preview(self, api: DouyinApi, web_rid: str) -> Tuple[str, PreviewMetadata]:
        live_dict, _ = api.getLiveInfoApi(web_rid)
        if not live_dict:
            raise DouyinNotFoundError(f"Livestream room {web_rid} not found.")

        is_live = live_dict.get("status") == "2"
        status_desc = "正在直播" if is_live else "直播已结束"
        partition = live_dict.get("partition") or "综合"

        author = AuthorPreview(
            nickname=live_dict.get("nickname") or "主播",
            avatar_thumb=live_dict.get("avatar"),
            sec_uid=live_dict.get("sec_uid") or "",
        )

        statistics = PreviewStatistics(
            play_count=int(live_dict.get("user_count", 0) or 0) if str(live_dict.get("user_count")).isdigit() else 0,
        )

        preview = PreviewMetadata(
            title=live_dict.get("title") or f"直播间 {web_rid}",
            desc=f"{status_desc} | 分区: {partition}",
            author=author,
            cover_url=live_dict.get("cover"),
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
```

---

## 8. Verification & Independent Test Strategy

The E2E testing infrastructure in `tests/conftest.py` has established deterministic offline mock responses for all Douyin API endpoints. The planned `DouyinService` seamlessly aligns with this testing framework:

### 8.1 Test Matrix

1. **Short Link Redirection Resolution**:
   - `https://v.douyin.com/iWhQezyaUco/` -> Resolves to `https://www.douyin.com/video/7488893440932039970`
   - `https://v.douyin.com/user_123/` -> Resolves to `https://www.douyin.com/user/MS4wLjABAAAA_test_author`
   - `https://v.douyin.com/mix_123/` -> Resolves to `https://www.douyin.com/collection/7488893440932039972`
   - `https://v.douyin.com/music_123/` -> Resolves to `https://www.douyin.com/music/7488893440932039973`
   - `https://v.douyin.com/live_123/` -> Resolves to `https://live.douyin.com/7488893440932039974`
2. **Raw Clipboard Text Extraction**:
   - Test text: `"7.35 复制打开抖音，看看【张三的作品】 https://v.douyin.com/iWhQezyaUco/ 11/12 l@w.pm :0pm"`
   - Asserts extraction of clean URL and subsequent successful resolution.
3. **5-Type Metadata Integrity**:
   - Asserts `key_type`, `key`, `canonical_url`, `content_type`, `preview.title`, `preview.author.nickname`, and `preview.cover_url` match expectations for video, image note, user, mix, music, and live.
4. **Error Mapping Verification**:
   - Passing `"invalid_url_with_no_http"` -> Asserts `DouyinInvalidUrlError` (HTTP 400).
   - Mocking empty API response or non-zero status code -> Asserts `DouyinNotFoundError` (HTTP 404).
   - Mocking connection error / timeout -> Asserts `DouyinUpstreamError` (HTTP 502).
5. **Thread Concurrency Verification**:
   - Run 10 concurrent calls to `DouyinService.parse_url()` using `asyncio.gather()`.
   - Verify all 10 complete successfully without dictionary collision, race condition, or SQLite thread affinity errors.
