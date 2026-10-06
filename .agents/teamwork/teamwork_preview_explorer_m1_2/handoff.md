# Handoff Report: DouyinService & Link Resolution Plan

**Agent**: M1 Explorer 2 (`teamwork_preview_explorer_m1_2`)  
**Recipient**: Sub-Orchestrator M1 (`sub_orch_m1` / `5e8a0791-8c15-483c-9053-9b4640dea1c2`)  
**Milestone**: M1 (Backend Engine & Task Concurrency)  
**Deliverable**: Plan for `src/web/services/douyin_service.py`  
**Date**: 2026-10-06  

---

## 1. Observation

1. **Shared Mutable State in `DouyinApi`**:
   - In `src/douyin/douyinapi.py:42`, `self.result = Result()` is instantiated once per `DouyinApi`.
   - In `src/douyin/douyinapi.py:184-186`, `getAwemeInfoApi()` executes:
     ```python
     # Clear existing data in self.awemeDict
     self.result.clearDict(self.result.awemeDict)
     ```
   - In `src/douyin/douyinapi.py:347`, `getLiveInfoApi()` executes:
     ```python
     self.result.clearDict(self.result.liveDict)
     ```
   - In `src/douyin/douyinapi.py:274, 441, 592`, pagination loops in `getUserInfoApi`, `getMixInfoApi`, and `getMusicInfo` continually call `self.result.clearDict(self.result.awemeDict)`.
   - In `src/douyin/result.py:156-184`, `awemeDict` is a shared dictionary attribute on `Result`. Concurrent execution on the same instance without thread isolation mutates and corrupts in-flight data.

2. **SQLite Thread Affinity in `Database`**:
   - In `src/douyin/database.py:20`, SQLite is initialized with `self.conn = sqlite3.connect(self.path)` without `check_same_thread=False`.
   - In `src/douyin/douyinapi.py:201`, `self.database.upsert_aweme()` calls this connection. If called across multiple threads in a thread pool, Python's SQLite driver throws `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.

3. **Link Extraction in Legacy `getKey()`**:
   - In `src/douyin/douyinapi.py:74-80`, `getKey(url)` performs:
     ```python
     r = self.session.get(url=url, headers=douyin_headers)
     urlstr = str(r.request.path_url)
     ```
   - If an unshortened desktop URL (e.g. `https://www.douyin.com/video/7488893440932039970`) is provided, `getKey()` issues a redundant, blocking HTTP GET to fetch the entire HTML page before inspecting `r.request.path_url`.
   - For messy clipboard text containing share captions and emoji, passing the string directly to `getKey()` fails because `r = self.session.get(url=url)` treats the entire text as a URL unless extracted first with `getShareLink()`.
   - Line 109 checks `elif "live.douyin.com" in r.url:`, while earlier branches check `urlstr = str(r.request.path_url)`.

4. **Existing Offline Test Fixtures**:
   - In `tests/conftest.py:151-297`, `mock_network_dispatch()` provides mock responses for `v.douyin.com` short links, `/aweme/v1/web/aweme/detail/`, `/aweme/v1/web/aweme/post/`, `/aweme/v1/web/mix/list/`, `/aweme/v1/web/mix/aweme/`, `/aweme/v1/web/music/aweme/`, and `/webcast/room/web/enter/`.

---

## 2. Logic Chain

1. **Thread-Safe Async Architecture**:
   - From Observation 1 and 2, concurrent FastAPI requests calling `DouyinApi` methods in worker threads without isolation will cause dictionary corruption in `Result.awemeDict` and `sqlite3.ProgrammingError` on shared database connections.
   - Using a global lock (`threading.Lock`) would serialize all link resolution requests, causing severe latency under concurrent usage.
   - Therefore, encapsulating `DouyinApi` within thread-local storage (`threading.local`) ensures that every worker thread in `asyncio.to_thread` possesses its own `DouyinApi` instance, its own `requests.Session` (retaining HTTP keep-alive connection reuse), its own `Result` instance, and its own isolated SQLite connection.

2. **Unified Link Resolution Engine**:
   - From Observation 3, input URLs can arrive in dirty formats (clipboard text with Chinese captions), short links (`v.douyin.com`), or canonical desktop URLs.
   - Running `SHARE_LINK_REGEX` first cleanly extracts the URL from arbitrary text.
   - If the URL is already an unshortened desktop link (`douyin.com/video/...`, `douyin.com/user/...`), matching regex patterns directly avoids unnecessary HTTP GET requests.
   - Only short links (`v.douyin.com`, `iesdouyin.com/share`) require following redirects via `session.get(url, stream=True, allow_redirects=True)` to retrieve `resp.url`.
   - Matching against the 5 compiled pattern sets (`aweme`, `user`, `mix`, `music`, `live`) covers 100% of Douyin content types.

3. **Rich Preview Card Extraction**:
   - Step 1 of the user experience (`PreviewCard.tsx`) requires displaying author nickname, high-resolution avatar, cover thumbnail, work counts, and engagement stats.
   - Mapping each key type to its corresponding Douyin API (`getAwemeInfoApi`, `getUserInfoApi`, `getMixInfoApi`, `getMusicInfo`, `getLiveInfoApi`) yields all required fields.
   - Graceful fallback rules (e.g. image notes using first image as cover, videos using `origin_cover`, user profiles without posts querying `USER_DETAIL`, live streams marked offline without raising errors) ensure high reliability.

4. **Error Classification**:
   - Invalid URLs raise `DouyinInvalidUrlError` -> HTTP 400.
   - Missing/deleted works raise `DouyinNotFoundError` -> HTTP 404.
   - Empty responses, captcha challenges, or timeouts raise `DouyinUpstreamError` -> HTTP 502 with guidance to configure cookies in Settings.

---

## 3. Caveats

1. **Livestream Status 4 (Offline)**:
   - When a livestream room is inactive (`status == "4"`), `DouyinService` intentionally returns HTTP 200 with `desc: "直播已结束"` and offline metadata rather than throwing a 404 or 502, allowing the user to view the streamer preview.
2. **Upstream Douyin Anti-Bot Evolution**:
   - While `ABogus` and `XBogus` algorithms are included in the repository, Douyin periodically updates its risk-control algorithms. Users must be able to input valid cookies via Settings (`/api/settings`) to bypass captcha challenges.
3. **Database Concurrency**:
   - If SQLite deduplication is enabled in `DouyinApi`, WAL mode is activated in `Database._prepare()`. However, thread-local connections are essential to prevent SQLite thread collision.

---

## 4. Conclusion

`src/web/services/douyin_service.py` is fully specified and ready for implementation. It will:
1. Provide an asynchronous, non-blocking interface (`await douyin_service.parse_url(url, cookie)`) via `asyncio.to_thread`.
2. Guarantee 100% thread safety using `threading.local` encapsulation of `DouyinApi`.
3. Support all 5 key Douyin URL types (`aweme`, `user`, `mix`, `music`, `live`) and clean extraction from mobile clipboard strings.
4. Extract rich preview card payloads matching the `ParseResponse` schema.
5. Provide structured error handling (400, 404, 502).

Detailed code designs and specifications are documented in:
`c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_2\report.md`

---

## 5. Verification Method

To independently verify the implementation once coded:

1. **Unit Test Verification**:
   Execute the offline test suite:
   ```powershell
   pytest tests/ -v
   ```
2. **Concurrency Verification**:
   Verify concurrent thread safety using `asyncio.gather`:
   ```python
   service = DouyinService()
   results = await asyncio.gather(*[
       service.parse_url("https://v.douyin.com/iWhQezyaUco/")
       for _ in range(10)
   ])
   assert len(results) == 10
   assert all(r.success for r in results)
   ```
3. **Files to Inspect**:
   - `src/web/services/douyin_service.py` (Implementation)
   - `src/web/core/schemas.py` (Pydantic models)
   - `tests/conftest.py` (Mock network dispatch)
