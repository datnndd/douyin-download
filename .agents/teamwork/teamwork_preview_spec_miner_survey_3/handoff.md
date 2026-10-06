# Handoff Report: Specification Mining for Douyin Web Downloader API

## 1. Observation
- Inspected `c:\Users\ddat2\Downloads\Projects\douyin-download\ORIGINAL_REQUEST.md` (lines 1-56), which defines R1 (FastAPI backend service & threaded downloader), R2 (Modern React frontend with pyvideotrans editorial aesthetic), R3 (Storage & Media Library with Windows File Explorer integration), and R4 (Settings & Cookie management).
- Inspected `c:\Users\ddat2\Downloads\Projects\douyin-download\config.yaml` (lines 1-116), observing runtime options: `link`, `path` (`./Downloaded/`), `music`, `cover`, `avatar`, `json`, `start_time`, `end_time`, `folderstyle`, `mode` (`post`, `like`, `mix`), `number` (`post`, `like`, `allmix`, `mix`, `music`), `database`, `increase`, `thread` (10), `filter` (`sort_by`, `reverse`, `limit`), and `cookies` (`msToken`, `ttwid`, `odin_tt`, `passport_csrf_token`, `sid_guard`).
- Inspected `douyinCommand.py` (lines 69-96, 248-272, 289-450):
  - Line 291-294: `url = self.api.getShareLink(link); key_type, key = self.api.getKey(url)`
  - Line 296-307: handlers mapping `{"user": _handle_user, "mix": _handle_mix, "music": _handle_music, "aweme": _handle_aweme, "live": _handle_live}`
  - Line 248-272: `_apply_filter_and_sort` supporting `sort_by` on `play_count`, `digg_count`, `comment_count`, `share_count`, `collect_count`, and `create_time`.
- Inspected `src/douyin/douyinapi.py` (lines 63-118, 119-204, 205-317, 318-383, 384-469, 470-536, 537-622):
  - Extracted URL resolution regex in `getShareLink` and `getKey`.
  - Extracted API calls: `getAwemeInfoApi`, `getUserInfoApi`, `getLiveInfoApi`, `getMixInfoApi`, `getUserAllMixInfoApi`, `getMusicInfo`.
- Inspected `src/douyin/download.py` (lines 80-149, 150-188, 189-272, 273-317, 327-376, 377-436):
  - Multithreaded asset preparation and download (`_prepare_media_tasks`).
  - Suffix-based rename detection in `_rename_if_exists` (`*likes_{suffix}`).
  - Resumable download in `download_with_resume` with `Range: bytes={size}-` and `206 Partial Content`.
- Inspected `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\src\index.css` (lines 1-64), noting the color system: surface `#FAF8F5`, surface-container `#F3ECE2`, primary `#8D4B00`, fonts `Plus Jakarta Sans` and `JetBrains Mono`.

## 2. Logic Chain
1. *From observations in `ORIGINAL_REQUEST.md` (R1-R4) and `douyinCommand.py`*: The CLI architecture resolves links into 5 discrete key types (`aweme`, `user`, `mix`, `music`, `live`) and delegates to `DouyinApi` and `Download`. Exposing this via REST requires a unified `POST /api/parse` endpoint that can accept any link format, run key extraction and preview fetching, and return a typed payload.
2. *From observations in `src/douyin/download.py`*: Downloads are currently coordinated via `ThreadPoolExecutor` and logged using `tqdm`. In FastAPI, running blocking downloads directly in request handlers will freeze the async event loop. Therefore, `POST /api/download` must create an asynchronous task running in an off-thread worker pool, returning a `task_id` immediately.
3. *From observations in `ORIGINAL_REQUEST.md:26` & `DISPATCH.md`*: Tracking real-time download progress, worker thread states, and speeds requires both a polling endpoint (`GET /api/tasks/{task_id}`) and streaming interfaces (`GET /api/stream` via SSE and `/ws/tasks` via WebSocket).
4. *From observations in `src/douyin/download.py:189-272` & `377-436`*: The downloader already implements partial content range downloading and dynamic renaming based on like counts. In the web media library, `GET /api/media/stream/{file_path}` must similarly support HTTP Range requests (`206 Partial Content`) to enable in-browser HTML5 video seeking without downloading entire multi-gigabyte files.
5. *From observations in `ORIGINAL_REQUEST.md:31`*: Windows Explorer opening requires a dedicated endpoint `POST /api/open-folder` utilizing `os.startfile` and `explorer.exe /select,` with strict path traversal validation to prevent unauthorized system directory access.
6. *From observations in `config.yaml`*: Settings must support dual cookie formats (dictionary vs semicolon string) and hot-reload runtime headers (`douyin_headers["Cookie"]`) without restarting FastAPI.

## 3. Caveats
- Upstream Douyin API anti-scraping defenses: Requests depend on `X-Bogus` and `A-Bogus` cryptographic token generators in `src/common/utils.py` and `src/common/abogus.py`. While tested and functional in the CLI, frequent high-volume scraping may prompt Douyin to require updated cookies or slider captchas; the API contracts account for this via `502 Bad Gateway` and `UPSTREAM_API_ERROR` codes.
- Video duration metadata: The Douyin web API does not always return video duration in `aweme_detail` without inspecting the video bit_rate or analyzing file headers locally via `ffprobe`; duration is thus marked optional in the Pydantic models.

## 4. Conclusion
The API specification is completely mined and documented in `report.md`. It covers:
- Full REST endpoints: `POST /api/parse`, `POST /api/download`, `GET /api/tasks`, `GET /api/tasks/{task_id}`, `POST /api/tasks/{task_id}/cancel`, `GET /api/stream`, `/ws/tasks`, `GET /api/settings`, `POST /api/settings`, `GET /api/media`, `GET /api/media/stream/{file_path}`, `POST /api/open-folder`.
- Exhaustive Pydantic schemas for all request bodies and responses.
- Seven-stage task lifecycle state machine (`IDLE` -> `PENDING` -> `PARSING` -> `DOWNLOADING` -> `COMPLETED` / `FAILED` / `CANCELLED`).
- Error handling contracts and HTTP status codes (400, 403, 404, 409, 416, 422, 500, 502, 504).
- Safe integration seams for non-blocking execution, downloader progress callbacks, and cookie hot-reloading.

## 5. Verification Method
1. Inspect `report.md` in `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_spec_miner_survey_3\report.md` to confirm all 27 discovered features, 13 edge cases, and Pydantic models are documented.
2. Validate Pydantic schema syntax against Python 3.10+ / Pydantic v2 conventions.
3. Compare endpoint parameters against `config.yaml` keys to verify 100% option coverage.
