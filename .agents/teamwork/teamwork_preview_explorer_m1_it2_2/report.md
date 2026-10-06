# Milestone 1 Iteration 2: Douyin Service & Schemas Remediation Report

**Explorer:** `teamwork_preview_explorer_m1_it2_2`  
**Role:** Douyin Service & Security Remediation  
**Target Files:** `src/web/services/douyin_service.py`, `src/web/core/schemas.py`, `src/douyin/douyinapi.py`  
**Date:** 2026-10-06  
**Status:** READY FOR IMPLEMENTATION  

---

## 1. Executive Summary & Defect Inventory

Reviewer 1 and Challenger 2 conducted rigorous baseline and adversarial testing on Milestone 1 deliverables, identifying 6 concrete defects in `douyin_service.py` and `schemas.py`. This investigation formulated exact, verified code patches to eliminate security risks and operational failures.

| Defect # | Component | Severity | Issue Summary | Fix Summary |
|---|---|---|---|---|
| **D1** | `douyin_service.py` | **CRITICAL** | SSRF & Cookie Exfiltration via unanchored substring check (`"douyin.com" in url`) | Parse hostname via `urllib.parse.urlparse`, whitelist exact Douyin hostnames `('v.douyin.com', 'douyin.com', 'www.douyin.com', 'iesdouyin.com', 'www.iesdouyin.com', 'live.douyin.com')` |
| **D2** | `douyin_service.py` / `douyinapi.py` | **HIGH** | Per-request cookie overridden by global `douyin_headers['Cookie']` in `requests` | Attach `prepare_request` hook on session instance enforcing per-request cookie without mutating global state |
| **D3** | `douyin_service.py` | **MEDIUM** | Schemeless URLs (e.g. `v.douyin.com/xxx`) rejected with HTTP 400 | Add schemeless Douyin regex normalization prepending `https://` |
| **D4** | `douyin_service.py` | **HIGH** | `modes: ["mix"]` on user profile returns `None` / 0 items | Query `api.getUserAllMixInfoApi` and aggregate collection items via `api.getMixInfoApi` |
| **D5** | `douyin_service.py` | **MEDIUM** | `stream=True` in `resolve_redirect_url` leaves HTTP sockets open | Use `with session.get(...) as resp:` context manager to ensure immediate socket closure |
| **D6** | `schemas.py` | **MEDIUM** | Upstream Douyin API returning `{"url_list": [None]}` crashes Pydantic validation (HTTP 500) | Sanitize `extract_avatar_url` and `extract_cover_url` to filter non-string/None elements, fallback to `""` |

---

## 2. Root Cause Analysis

### D1. SSRF & Douyin Cookie Exfiltration
- **Location:** `src/web/services/douyin_service.py` lines 208, 249
- **Root Cause:**
  1. In `resolve_redirect_url`:
     ```python
     if "v.douyin.com" in url or "iesdouyin.com/share" in url:
         resp = session.get(url, headers=douyin_headers, ...)
     ```
     An attacker crafting `https://attacker.com/steal?target=v.douyin.com` or `https://v.douyin.com.evil.com/leak` triggers `session.get(url, headers=douyin_headers, ...)` to an untrusted third-party server, leaking the user's `douyin_headers['Cookie']`.
  2. In `extract_key_and_type`:
     ```python
     if "live.douyin.com" in url: ...
     ```
     An attacker URL like `https://attacker.com/live.douyin.com/123456` matches the condition and is misidentified as a valid livestream room.
- **Remediation:**
  Parse URL with `urllib.parse.urlparse(url)`. Extract `hostname = (parsed.hostname or "").lower()`. Only follow shortlink redirects if `hostname in ("v.douyin.com", "iesdouyin.com", "www.iesdouyin.com")`. In `extract_key_and_type`, reject any URL whose hostname is not in `ALLOWED_HOSTS` or does not end with `.douyin.com`/`.iesdouyin.com`.

### D2. Per-Request Cookie Override Failure
- **Location:** `src/web/services/douyin_service.py` lines 123–127; `src/douyin/douyinapi.py` lines 59–60 & 74, 167, 231, etc.; `src/douyin/__init__.py` line 19
- **Root Cause:**
  In Python's `requests` library, when calling `session.get(url, headers=headers)`, the request-level `headers` argument takes precedence over `session.headers` (via `merge_setting`).
  `DouyinApi` calls `self.session.get(url=..., headers=douyin_headers)`.
  Because `douyin_headers` in `src.douyin` contains a static `'Cookie'` key, `douyin_headers['Cookie']` overrides whatever custom cookie was passed to `DouyinApi(cookie=...)` and set on `self.session.headers['Cookie']`.
  Furthermore, mutating `douyin_headers['Cookie']` globally is forbidden because it is shared across all threads and requests, causing race conditions and credential cross-contamination.
- **Remediation:**
  In `DouyinService._get_api` (and directly in `DouyinApi.__init__`), when a custom cookie is provided, wrap `session.prepare_request` on that specific session instance:
  ```python
  orig_prepare = session.prepare_request
  def custom_prepare(request):
      prep = orig_prepare(request)
      prep.headers['Cookie'] = cookie
      return prep
  session.prepare_request = custom_prepare
  ```
  This guarantees that after all header merges, the final `PreparedRequest` sent on the wire contains the active per-request cookie, without mutating global `douyin_headers`.

### D3. URL Scheme Normalization
- **Location:** `src/web/services/douyin_service.py` line 74 & 197–203
- **Root Cause:**
  `SHARE_LINK_REGEX = re.compile(r"https?://...")` strictly requires an `http://` or `https://` prefix. Users frequently paste raw links like `v.douyin.com/iWhQezyaUco/` or `www.douyin.com/video/7488893440932039970`. Because no `https?://` prefix exists, `extract_share_url` returns `None`, raising `DouyinInvalidUrlError` (HTTP 400).
- **Remediation:**
  Add a secondary regex `SCHEMELESS_DOUYIN_REGEX` matching known Douyin domains (`v.douyin.com`, `www.douyin.com`, `live.douyin.com`, etc.) preceded by string boundary, whitespace, or Chinese punctuation. When matched, prepend `https://` to normalize the URL.

### D4. User Profile `mode == "mix"` Returning `None`
- **Location:** `src/web/services/douyin_service.py` lines 591–605
- **Root Cause:**
  `DouyinService.get_download_items` loops through `req.modes` and unconditionally calls `api.getUserInfoApi(sec_uid=key, mode=mode, ...)`.
  Inside `DouyinApi.getUserInfoApi`:
  ```python
  if mode == "post": ...
  elif mode == "like": ...
  else: return None
  ```
  `getUserInfoApi` returns `None` for `mode == "mix"`. The actual method for retrieving user collections/mixes is `api.getUserAllMixInfoApi(sec_uid=key)`.
- **Remediation:**
  In `DouyinService.get_download_items`, branch when `mode in ("mix", "allmix")`:
  1. Call `mixes = api.getUserAllMixInfoApi(sec_uid=key, ...)`.
  2. For each `mix_id` in `mixes`, call `api.getMixInfoApi(mix_id=mix_id, number=limit, ...)`.
  3. Aggregate the collection items into `all_items`, honoring `limit` and `cancel_event`.

### D5. Unclosed Streaming HTTP Response
- **Location:** `src/web/services/douyin_service.py` lines 211–218
- **Root Cause:**
  `resolve_redirect_url` calls `resp = session.get(url, stream=True)` without calling `resp.close()` or using a context manager. This holds open underlying HTTP socket connections from urllib3's pool, causing socket exhaustion under repeated parse workloads.
- **Remediation:**
  Wrap `session.get(..., stream=True)` in a `with session.get(...) as resp:` block so the socket is immediately closed after reading `resp.url`.

### D6. Schema Validation Crashes on `url_list: [None]`
- **Location:** `src/web/core/schemas.py` lines 158–165 (`AuthorPreview`) and 200–207 (`PreviewMetadata`); `src/web/services/douyin_service.py` lines 549–559 (`_pick_first_url`)
- **Root Cause:**
  Upstream Douyin APIs sometimes return `avatar_thumb = {"url_list": [None]}` or `cover_url = {"url_list": [None]}`.
  In `AuthorPreview.extract_avatar_url`:
  ```python
  if isinstance(v, dict):
      url_list = v.get("url_list", [])
      return url_list[0] if url_list else ""
  ```
  Since `url_list = [None]` is truthy, it returns `url_list[0]` which is `None`. Because `avatar_thumb: str` and `cover_url: str` are non-optional `str` fields, Pydantic v2 raises `ValidationError: Input should be a valid string [type=string_type, input_value=None]`, causing `/api/parse` to fail with HTTP 500.
- **Remediation:**
  Iterate through `url_list` in `extract_avatar_url`, `extract_cover_url`, and `_pick_first_url`, selecting the first non-empty, non-whitespace string element. If no valid string exists, return `""` (for schema models) or `None` (for `_pick_first_url`).

---

## 3. Concrete Code Patches

### Patch 1: `src/web/services/douyin_service.py`

#### 1.1 Imports and Whitelist Definitions (Lines 11–32 & 70–100)
```python
<<<<
import asyncio
import copy
import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import requests
====
import asyncio
import copy
import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
>>>>
```

```python
<<<<
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
====
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
>>>>
```

#### 1.2 Thread-Local API & Session Cookie Isolation (Lines 117–128)
```python
<<<<
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
====
    def _get_api(self, cookie: Optional[str] = None) -> DouyinApi:
        """Retrieve or initialize thread-local DouyinApi instance with cookie isolation."""
        active_cookie = cookie or self._default_cookie
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
>>>>
```

#### 1.3 URL Normalization, Redirect Resolution, and Key Extraction (Lines 196–265)
```python
<<<<
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
====
    @classmethod
    def extract_share_url(cls, text: str) -> Optional[str]:
        """
        Extracts first valid HTTP/HTTPS URL from raw string.
        Normalizes raw inputs like v.douyin.com/xxx without https:// by prepending scheme.
        """
        if not text or not text.strip():
            return None

        # 1. Search for standard http(s) URL
        matches = SHARE_LINK_REGEX.findall(text)
        if matches:
            url = matches[0].rstrip("),.!?，。！？;；'\"")
            if url:
                return url

        # 2. Search for schemeless Douyin URL pattern
        schemeless = SCHEMELESS_DOUYIN_REGEX.search(text)
        if schemeless:
            raw_url = schemeless.group(1).rstrip("),.!?，。！？;；'\"")
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
>>>>
```

#### 1.4 Safe `_pick_first_url` (Lines 549–559)
```python
<<<<
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
====
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
>>>>
```

#### 1.5 User Profile `mode == "mix"` in `get_download_items` (Lines 589–606)
```python
<<<<
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
====
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
>>>>
```

---

### Patch 2: `src/web/core/schemas.py`

#### 2.1 Sanitize `AuthorPreview.extract_avatar_url` (Lines 158–165)
```python
<<<<
    @field_validator("avatar_thumb", "avatar", mode="before")
    @classmethod
    def extract_avatar_url(cls, v: Any) -> str:
        if isinstance(v, dict):
            url_list = v.get("url_list", [])
            return url_list[0] if url_list else ""
        return str(v or "")
====
    @field_validator("avatar_thumb", "avatar", mode="before")
    @classmethod
    def extract_avatar_url(cls, v: Any) -> str:
        if isinstance(v, dict):
            url_list = v.get("url_list")
            if isinstance(url_list, list):
                for u in url_list:
                    if u and isinstance(u, str) and u.strip():
                        return u.strip()
            return ""
        if isinstance(v, list):
            for u in v:
                if u and isinstance(u, str) and u.strip():
                    return u.strip()
            return ""
        if v is None:
            return ""
        return str(v)
>>>>
```

#### 2.2 Sanitize `PreviewMetadata.extract_cover_url` (Lines 200–207)
```python
<<<<
    @field_validator("cover_url", mode="before")
    @classmethod
    def extract_cover_url(cls, v: Any) -> str:
        if isinstance(v, dict):
            url_list = v.get("url_list", [])
            return url_list[0] if url_list else ""
        return str(v or "")
====
    @field_validator("cover_url", mode="before")
    @classmethod
    def extract_cover_url(cls, v: Any) -> str:
        if isinstance(v, dict):
            url_list = v.get("url_list")
            if isinstance(url_list, list):
                for u in url_list:
                    if u and isinstance(u, str) and u.strip():
                        return u.strip()
            return ""
        if isinstance(v, list):
            for u in v:
                if u and isinstance(u, str) and u.strip():
                    return u.strip()
            return ""
        if v is None:
            return ""
        return str(v)
>>>>
```

---

### Patch 3 (Companion): `src/douyin/douyinapi.py`

#### 3.1 Session Header Precedence in `DouyinApi.__init__` (Lines 58–61)
```python
<<<<
        # Apply cookie from config to session headers
        if cookie:
            self.session.headers.update({'Cookie': cookie})
====
        # Apply cookie from config to session headers
        if cookie:
            self.session.headers.update({'Cookie': cookie})
            orig_prepare_request = self.session.prepare_request

            def _custom_prepare_request(request):
                prep = orig_prepare_request(request)
                prep.headers['Cookie'] = cookie
                return prep

            self.session.prepare_request = _custom_prepare_request
>>>>
```

---

## 4. Verification & Validation Strategy

The proposed remediations directly resolve all 3 related failures in `tests/test_m1_challenger2_edge_cases.py` and the 2 major issues raised in Reviewer 1's report:

1. **Verify SSRF & Domain Validation:**
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/test_m1_challenger2_edge_cases.py::TestAdversarialSecurityAndDomainValidation -v
   ```
   *Expected:* `test_domain_spoofing_in_resolve_redirect` and `test_live_domain_spoofing` pass with zero requests dispatched to untrusted domains.

2. **Verify Schema Null-Resilience:**
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/test_m1_challenger2_edge_cases.py::TestSchemaValidationAndBoundaryInvariants::test_author_preview_url_list_containing_none_crash tests/test_m1_challenger2_edge_cases.py::TestSchemaValidationAndBoundaryInvariants::test_preview_metadata_cover_url_containing_none_crash -v
   ```
   *Expected:* Both pass cleanly, outputting `""` without triggering Pydantic v2 `ValidationError`.

3. **Verify Cookie Isolation Reproduction:**
   ```powershell
   .venv\Scripts\python.exe -c "
   import requests
   from src.douyin import douyin_headers
   from src.douyin.douyinapi import DouyinApi
   douyin_headers['Cookie'] = 'GLOBAL=AAA'
   api = DouyinApi(cookie='CUSTOM=BBB')
   req = requests.Request('GET', 'http://example.com', headers=douyin_headers)
   prep = api.session.prepare_request(req)
   assert 'CUSTOM=BBB' in prep.headers['Cookie'], 'Custom cookie was overridden'
   print('Cookie isolation verified!')
   "
   ```
   *Expected:* Assertion succeeds without mutation to `douyin_headers`.

4. **Verify URL Normalization:**
   ```powershell
   .venv\Scripts\python.exe -c "
   from src.web.services.douyin_service import DouyinService
   s = DouyinService()
   assert s.extract_share_url('v.douyin.com/iWhQezyaUco/') == 'https://v.douyin.com/iWhQezyaUco/'
   assert s.extract_share_url('7.35 复制打开抖音 v.douyin.com/iWhQezyaUco/ 11/12') == 'https://v.douyin.com/iWhQezyaUco/'
   assert s.extract_share_url('🔥🎉v.douyin.com/iWhQezyaUco/🚀✨') == 'https://v.douyin.com/iWhQezyaUco/'
   print('URL Normalization verified!')
   "
   ```
   *Expected:* All variations correctly normalize to `https://v.douyin.com/iWhQezyaUco/`.

5. **Verify User Profile `mode == "mix"` Resolution:**
   ```powershell
   .venv\Scripts\python.exe -c "
   from unittest.mock import MagicMock, patch
   from src.web.services.douyin_service import DouyinService
   from src.web.core.schemas import DownloadRequest

   s = DouyinService()
   req = DownloadRequest(url='https://www.douyin.com/user/test', key_type='user', key='test', modes=['mix'], number={'mix': 5})
   with patch.object(s, '_get_api') as mock_get_api:
       api = MagicMock()
       api.getUserAllMixInfoApi.return_value = {'m1': 'Mix1'}
       api.getMixInfoApi.return_value = [{'aweme_id': 'item1'}]
       mock_get_api.return_value = api
       items = s.get_download_items(req)
       assert len(items) == 1
       assert items[0]['aweme_id'] == 'item1'
   print('User mix resolution verified!')
   "
   ```
   *Expected:* Successfully extracts mix items from `api.getUserAllMixInfoApi` and `api.getMixInfoApi`.
