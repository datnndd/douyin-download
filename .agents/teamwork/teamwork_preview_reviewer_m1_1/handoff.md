# Milestone 1 Review & Adversarial Challenge Report

**Reviewer:** `teamwork_preview_reviewer_m1_1`  
**Roles:** reviewer, critic  
**Target:** Milestone 1 Core Schemas, Config & Douyin Service  
**Date:** 2026-10-06  
**Verdict:** **REQUEST_CHANGES**  

---

## Review Summary

- **Integrity Assessment:** **PASS** (Zero integrity violations. No hardcoded mock results, no dummy facade implementations, and no fabricated verification artifacts detected).
- **Quality & Correctness Assessment:** **REQUEST_CHANGES** (Identified 3 Major functional defects and 3 Minor edge cases that lead to silent config corruption, ignored per-request cookies, and unhandled download modes).

---

## 1. Observation

### Observation 1: Automated Test Suite Execution
- **Command:** `.venv\Scripts\python.exe -m pytest tests/test_m1_core.py -v`
- **Result:**
  ```
  tests/test_m1_core.py::TestConfigAndCookies::test_parse_raw_cookie_basic PASSED [  2%]
  ...
  tests/test_m1_core.py::TestPreviewsAndEndToEnd::test_media_and_system_schemas PASSED [100%]
  ============================= 43 passed in 0.43s ==============================
  ```
  All 43 unit tests pass cleanly.

### Observation 2: Indentation Bug in `_update_yaml_in_place_regex` Corrupts Nested Keys
- **File:** `src/web/core/config.py`
- **Lines 93–94 & 118:**
  ```python
  def replace_scalar(content: str, key: str, value: Any) -> str:
      pattern = rf"^([ \t]*{re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
  ...
  text = replace_scalar(text, "music", settings.music)
  ```
- **File:** `config.yaml`
- **Lines 25, 71, 88:**
  ```yaml
  25: music: False
  ...
  71:   music: 5      # Number of works to download from music (original sound), default 0 = download all
  ...
  88:   music: False    # Enable incremental download for works under music (original sound) (True/False), default False
  ```
- **Reproduction Command & Result:**
  ```powershell
  .venv\Scripts\python.exe -c "
  from src.web.core.config import ConfigManager
  import tempfile, shutil
  tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.yaml')
  shutil.copy('config.yaml', tmp.name)
  mgr = ConfigManager(tmp.name)
  settings = mgr.get_settings()
  settings.music = True
  mgr.update_settings(settings)
  reloaded = mgr.reload()
  print('Initial number:', settings.number)
  print('Reloaded number:', reloaded.number)
  "
  ```
- **Verbatim Output:**
  ```
  Initial number: {'post': 0, 'like': 0, 'allmix': 0, 'mix': 5, 'music': 5}
  Reloaded number: {'post': 0, 'like': 0, 'allmix': 0, 'mix': 5, 'music': 1}
  ```
  Because `replace_scalar` uses `^[ \t]*`, `music: True` matches both top-level `music:` and indented `  music: 5`. The line `  music: 5` is replaced by `  music: True`. Upon reload, `yaml.safe_load` parses `True` as boolean, which is coerced to `int(True) == 1`, corrupting the user's music download limit from 5 to 1.

### Observation 3: Per-Request Custom Cookies Overridden by Global `douyin_headers['Cookie']`
- **File:** `src/web/services/douyin_service.py`
- **Lines 123–126:**
  ```python
  if api is None or cached_cookie != active_cookie:
      api = DouyinApi(database_path=self._database_path, cookie=active_cookie)
      self._local.api = api
      self._local.cookie = active_cookie
  ```
- **File:** `src/douyin/douyinapi.py`
- **Lines 59–60 & 167:**
  ```python
  if cookie:
      self.session.headers.update({'Cookie': cookie})
  ...
  response = self.session.get(url=jx_url, headers=douyin_headers, timeout=10)
  ```
- **File:** `src/douyin/__init__.py`
- **Line 19:**
  ```python
  douyin_headers = {
      ...
      'Cookie': f"msToken={utils.generate_random_str(107)}; ttwid={utils.getttwid()}; ..."
  }
  ```
- **Reproduction Command & Result:**
  ```powershell
  .venv\Scripts\python.exe -c "
  import requests
  from src.douyin import douyin_headers
  from src.douyin.douyinapi import DouyinApi
  douyin_headers['Cookie'] = 'GLOBAL_COOKIE=AAA'
  api = DouyinApi(cookie='PER_REQUEST_COOKIE=BBB')
  req = requests.Request('GET', 'http://example.com', headers=douyin_headers)
  prep = api.session.prepare_request(req)
  print('Actual sent cookie:', prep.headers.get('Cookie'))
  "
  ```
- **Verbatim Output:**
  ```
  Actual sent cookie: GLOBAL_COOKIE=AAA
  ```
  In `requests`, request-level `headers` overrides `session.headers`. Because every method in `DouyinApi` calls `self.session.get(url, headers=douyin_headers)`, the global `douyin_headers['Cookie']` overwrites `self.session.headers['Cookie']`. Custom cookies passed into `ParseRequest.cookie` or `DownloadRequest.cookie` are ignored on the wire.

### Observation 4: In-Place YAML Update Silently Fails When `config.yaml` Uses `cookie:` Scalar
- **File:** `src/web/core/config.py`
- **Lines 139–156:**
  ```python
  if settings.cookies:
      cookie_lines = ["cookies:"]
      ...
      cookies_pattern = r"^cookies:[ \t]*(?:\r?\n[ \t]+[^\r\n]+)*"
      if re.search(cookies_pattern, text, flags=re.MULTILINE):
          text = re.sub(
              cookies_pattern, lambda m: new_cookies_block, text, flags=re.MULTILINE
          )
  elif settings.raw_cookie:
      ...
  ```
- **Reproduction Command & Result:**
  ```powershell
  .venv\Scripts\python.exe -c "
  from src.web.core.config import _update_yaml_in_place_regex
  from src.web.core.schemas import SettingsModel
  text = 'path: ./Downloaded/\nthread: 5\ncookie: old_val\n'
  settings = SettingsModel(path='./Downloaded/', thread=5, cookies={'msToken': 'new'})
  print(_update_yaml_in_place_regex(text, settings))
  "
  ```
- **Verbatim Output:**
  ```
  path: ./Downloaded/
  thread: 5
  cookie: old_val
  ```
  If the YAML file has `cookie: "old_val"` (as described in `config.yaml` lines 110–116) and `settings.cookies` is non-empty, `cookies_pattern` matches nothing and the file is untouched; the new cookie is never written.

### Observation 5: User Profile `mode == "mix"` Returns `None`
- **File:** `src/web/services/douyin_service.py`
- **Lines 595–604:**
  ```python
  elif key_type == "user":
      all_items: List[Dict[str, Any]] = []
      for mode in req.modes:
          ...
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
  ```
- **File:** `src/douyin/douyinapi.py`
- **Lines 221–229:**
  ```python
  if mode == "post":
      url = self.urls.USER_POST + utils.getXbogus(detail_params)
  elif mode == "like":
      ...
  else:
      return None
  ```
  `api.getUserInfoApi` returns `None` when `mode == "mix"`. The dedicated method for user mixes is `api.getUserAllMixInfoApi(sec_uid=key)`. Consequently, requests with `modes: ["mix"]` silently produce 0 download items.

### Observation 6: Clipboard URL Extraction Rejects Links Without `http://` or `https://`
- **File:** `src/web/services/douyin_service.py`
- **Lines 74 & 197–203:**
  ```python
  SHARE_LINK_REGEX = re.compile(r"https?://[a-zA-Z0-9_./\-?&=%#+:@!~*]+")
  ```
  If a user pastes `v.douyin.com/iWhQezyaUco/` without `https://`, `extract_share_url` returns `None`, raising `DouyinInvalidUrlError` (HTTP 400).

### Observation 7: Unclosed Streaming Response in `resolve_redirect_url`
- **File:** `src/web/services/douyin_service.py`
- **Lines 211–218:**
  ```python
  resp = session.get(
      url,
      headers=douyin_headers,
      allow_redirects=True,
      timeout=10,
      stream=True,
  )
  return str(resp.url)
  ```
  Because `stream=True` is used without closing `resp` or using `with`, the underlying HTTP socket connection remains open until GC, which risks socket exhaustion under sustained parse workloads.

---

## 2. Logic Chain

1. **Test Suite Grounding (Observation 1)**: The test suite in `tests/test_m1_core.py` passes 100%, confirming that the basic interfaces, Pydantic coercions, and mocked worker pipelines operate as designed in isolation.
2. **Indentation Regex Vulnerability (Observation 2)**: `replace_scalar` lacks indentation anchoring for top-level keys. Because `music` exists as both a top-level boolean key (`music: False`) and a nested integer limit (`number: music: 5`), updating `settings.music` matches and clobbers `number.music` into a boolean, which reloads as integer 1. This is a severe silent corruption bug in `config.yaml`.
3. **HTTP Cookie Header Precedence (Observation 3)**: In `requests`, request-level `headers` argument overrides `session.headers`. `DouyinApi` passes `headers=douyin_headers` to every `session.get()` call, and `douyin_headers` has a global `'Cookie'` key. As a result, per-request cookies set in `session.headers` by `DouyinService._get_api` are ignored on the wire. This breaks the per-request cookie override requirement of `POST /api/parse` and `POST /api/download`.
4. **Cookie YAML Structure Incompatibility (Observation 4)**: The regex updater assumes the input YAML always has a `cookies:` block. If the user configured their YAML with `cookie: "..."`, the update logic skips writing the cookie entirely.
5. **Mode Support Gap (Observation 5)**: `ORIGINAL_REQUEST.md` line 25 specifies "User selects modes (post/like/mix)". Passing `mode="mix"` to `getUserInfoApi` returns `None`. Without calling `getUserAllMixInfoApi`, user collection downloading is broken.
6. **Overall Conclusion (Observations 2–5)**: While the architecture, thread isolation, and Pydantic validation are well-designed and free of integrity cheats, the 3 major functional defects require remediation before Milestone 2 can safely build upon them.

---

## 3. Findings

### [Major] Finding 1: Regex scalar replacement in `_update_yaml_in_place_regex` corrupts nested keys with identical names
- **What**: `replace_scalar` regex `rf"^([ \t]*{re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"` matches indented keys. When updating top-level `music`, it also updates `number.music` (5 -> True -> 1) and `increase.music`.
- **Where**: `src/web/core/config.py`, lines 93–114 & 118
- **Why**: Corrupts user configuration on disk every time settings are saved.
- **Suggestion**:
  Anchor top-level keys with zero leading whitespace:
  ```python
  # For root scalars:
  pattern = rf"^({re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
  ```
  And for nested keys (under `filter:`), match within their specific block or require leading indentation.

### [Major] Finding 2: Per-request cookie overrides are overridden by global `douyin_headers['Cookie']`
- **What**: `DouyinApi` calls `self.session.get(..., headers=douyin_headers)`. In `requests`, request-level `headers` overrides `session.headers`. Since `douyin_headers` contains global cookies, per-request cookies set on `session.headers` are clobbered.
- **Where**: `src/web/services/douyin_service.py`, lines 117–128; `src/douyin/douyinapi.py`, lines 59–60 & 167; `src/douyin/__init__.py`, line 19
- **Why**: Violates `PROJECT.md` API contracts where `/api/parse` and `/api/download` allow per-request cookie overrides.
- **Suggestion**:
  In `DouyinService`, when an active per-request cookie is present, ensure request headers carry that cookie. For example, attach a requests `RequestHook` or pass a customized headers dict to the session or adjust `douyinapi.py` so that `douyin_headers['Cookie']` does not overwrite `session.headers['Cookie']` when an explicit cookie is configured.

### [Major] Finding 3: In-place YAML cookie saving fails when `config.yaml` uses `cookie:` scalar format
- **What**: `_update_yaml_in_place_regex` checks `if settings.cookies:`, searching only for `cookies_pattern`. If the file uses `cookie: "..."`, it matches nothing and does not update the file.
- **Where**: `src/web/core/config.py`, lines 139–160
- **Why**: Prevents saving cookies for users whose `config.yaml` is configured with `cookie: "..."`.
- **Suggestion**:
  If `settings.cookies` is non-empty and `cookies_pattern` is not found, check if `cookie:` exists and replace it, or append `cookies:` to the document.

### [Minor] Finding 4: `get_download_items` does not support `mode == "mix"` for user profiles
- **What**: `api.getUserInfoApi` returns `None` when `mode == "mix"`. User collections require `api.getUserAllMixInfoApi`.
- **Where**: `src/web/services/douyin_service.py`, lines 595–605
- **Why**: When a user selects `modes: ["mix"]` for a user profile, 0 items are returned.
- **Suggestion**:
  In `get_download_items`, branch when `mode in ("mix", "allmix")` to call `api.getUserAllMixInfoApi(sec_uid=key)`.

### [Minor] Finding 5: URL extraction rejects URLs without `http://` or `https://` prefix
- **What**: `SHARE_LINK_REGEX` requires `https?://`. Pasting `v.douyin.com/...` returns HTTP 400.
- **Where**: `src/web/services/douyin_service.py`, lines 74 & 197–203
- **Why**: Poor user experience when users copy clean URLs without protocol scheme.
- **Suggestion**:
  If no URL matches `SHARE_LINK_REGEX`, check if the string contains `douyin.com/` and prepend `https://`.

### [Minor] Finding 6: Unclosed streaming response in `resolve_redirect_url`
- **What**: `session.get(..., stream=True)` does not close the response or use a context manager.
- **Where**: `src/web/services/douyin_service.py`, lines 212–218
- **Why**: Risk of connection/socket leak under high request volumes.
- **Suggestion**:
  Use `with session.get(..., stream=True) as resp: return str(resp.url)`.

---

## 4. Verified Claims

| Claim | Method | Result |
|---|---|---|
| 43 unit tests pass in `.venv` | Run pytest `tests/test_m1_core.py` | PASS (43 passed in 0.43s) |
| Schemas support Pydantic v2 validation and coercions | Verified via `TestPydanticSchemas` | PASS |
| Single Aweme, User, Mix, Music, and Live URL resolution | Verified via `TestDouyinService` | PASS |
| `ConfigManager` singleton thread-safety | Inspected `threading.RLock()` and singleton pattern | PASS |
| `DouyinService` thread isolation | Inspected `threading.local` for `DouyinApi` instances | PASS |
| Zero integrity violations (no hardcoded/facade logic) | Source audit of `schemas.py`, `config.py`, `douyin_service.py` | PASS |

---

## 5. Coverage Gaps

- Live network requests against Douyin servers: Not tested live due to sandbox network constraints; tested via mock fixtures in pytest. Risk level: LOW (unit test coverage is comprehensive).

---

## 6. Caveats

- Milestone 1 exclusively implements backend schemas, config persistence, and the Douyin service adapter. The REST routes and FastAPI application factory (`src/web/api/`, `main_web.py`) are Milestone 2 deliverables.
- Reviewer is constrained to read-only operation; fixes must be performed by the worker agent.

---

## 7. Conclusion

Milestone 1 shows solid foundational architecture: clean Pydantic v2 schemas, good thread isolation via `threading.local()`, smooth speed calculations, and non-blocking download hooks. However, due to:
1. Data corruption of `number.music` during YAML in-place updates,
2. Ineffective per-request cookie overrides caused by global `douyin_headers['Cookie']` precedence, and
3. Silently skipped `mode="mix"` downloads for user profiles,

the verdict is **REQUEST_CHANGES**. These defects must be corrected before advancing to Milestone 2.

---

## 8. Verification Method

To verify these findings and reproduce the issues independently:

1. **Run full unit test suite:**
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/test_m1_core.py -v
   ```
2. **Reproduce Finding 1 (YAML `number.music` corruption):**
   ```powershell
   .venv\Scripts\python.exe -c "
   from src.web.core.config import ConfigManager
   import tempfile, shutil
   tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.yaml')
   shutil.copy('config.yaml', tmp.name)
   mgr = ConfigManager(tmp.name)
   settings = mgr.get_settings()
   settings.music = True
   mgr.update_settings(settings)
   reloaded = mgr.reload()
   assert reloaded.number['music'] == 5, f'Corrupted to {reloaded.number[\"music\"]}'
   "
   ```
   *Expected result:* Assertion fails because `reloaded.number['music'] == 1`.
3. **Reproduce Finding 2 (Cookie header clobbering):**
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
   "
   ```
   *Expected result:* Assertion fails because `'GLOBAL=AAA'` was sent instead of `'CUSTOM=BBB'`.
