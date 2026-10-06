# Handoff Report: Douyin Web Downloader Backend Architecture Survey

**Agent**: Codebase Explorer (Backend)  
**Working Directory**: `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_survey_1`  
**Handoff Type**: Hard Handoff (Investigation Complete)  
**Parent Agent**: `5e8a0791-8c15-483c-9053-9b4640dea1c2`  

---

## 1. Observation

1. **CLI Workflow & Entrypoint**:
   - `main.py:1-6` is currently a placeholder ("Hello from douyin-download!").
   - The CLI runner is in `douyinCommand.py:495-510` which sets up logging, parses arguments via `Config.from_args` / `Config.from_yaml`, instantiates `DouyinClient(cfg)`, and executes `client.process_all()`.
2. **API Parsing & Supported Links**:
   - In `src/douyin/douyinapi.py:63-117`, `getShareLink` extracts URLs via regex `r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+'`.
   - `getKey` follows redirects and extracts:
     - `/user/` -> `key_type = "user"`, `key = sec_uid` (line 84)
     - `/video/` -> `key_type = "aweme"`, `key = aweme_id` (line 88)
     - `/note/` -> `key_type = "aweme"`, `key = aweme_id` (line 91)
     - `/mix/detail/` & `/collection/` -> `key_type = "mix"`, `key = mix_id` (lines 94, 97)
     - `/music/` -> `key_type = "music"`, `key = music_id` (line 100)
     - `/webcast/reflow/` & `live.douyin.com` -> `key_type = "live"`, `key = web_rid` (lines 103, 110)
   - API endpoints use signature generators: `a_bogus` from `ABogus` (`src/common/abogus.py:30-60`) for single detail (`getAwemeInfoApi`), and `X-Bogus` from `Utils.getXbogus` (`src/common/utils.py:72-76`) for pagination (`getUserInfoApi`, `getMixInfoApi`, `getMusicInfo`).
3. **Download Engine & Resume Mechanics**:
   - In `src/douyin/download.py:27-54`, `Download` uses thread-local `requests.Session` with `HTTPAdapter(pool_connections=100, pool_maxsize=100)`.
   - In `src/douyin/download.py:377-436`, `download_with_resume` reads existing file size (`filepath.stat().st_size`), sends `Range: bytes={file_size}-`, handles HTTP 206 (`mode='ab'`) and HTTP 200 (`mode='wb'`), streams chunks of 8192 bytes, and retries up to 5 times with exponential backoff (`min(2**(attempt+1), 10)`).
   - In `src/douyin/download.py:150-188`, `_download_media_files_threaded` runs a `ThreadPoolExecutor(max_workers=self.thread)` for sub-assets (video, music, cover, avatar, image).
   - In `src/douyin/download.py:327-362`, `userDownload` runs a separate `ThreadPoolExecutor(max_workers=min(self.thread, total_count))` for videos.
4. **Existing Progress Reporting**:
   - `Download` currently outputs directly to terminal via `tqdm` in `download_with_resume` (line 405), `_download_media_files_threaded` (line 165), and `userDownload` (line 350). No callback or hook parameter currently exists in `Download.__init__`.
5. **Storage & Hierarchy**:
   - `config.yaml:21-57` defines default path `./Downloaded/` and `folderstyle`.
   - When `folderstyle=True`, `save_path / f"{digg_count:09d}likes_{create_time}_{desc}"` creates an isolated directory per video.
   - Dynamic renaming via `_rename_if_exists` (`src/douyin/download.py:189-272`) updates folder and file names if like counts change.
6. **Environment & Dependencies**:
   - `uv pip list` shows `requests 2.32.4`, `pyyaml 6.0.1`, `tqdm 4.67.1`, `gmssl 3.2.2`, `pytest 7.4.3`.
   - `fastapi` and `uvicorn` are not yet installed in `.venv`.
7. **Reference Design System in `pyvideotrans`**:
   - `pyvideotrans/frontend/src/index.css:4-23` specifies:
     - `--color-surface: #FAF8F5`
     - `--color-surface-container: #F3ECE2`
     - `--color-primary: #8D4B00`
     - `--font-sans: "Plus Jakarta Sans"`
     - `--font-mono: "JetBrains Mono"`
   - `pyvideotrans/videotrans/api/routes/jobs.py:169-247` demonstrates production FastAPI SSE streaming with `StreamingResponse(media_type="text/event-stream")`, `asyncio.Queue`, and keep-alive heartbeats.

---

## 2. Logic Chain

1. **Two-Step Interaction**: Because `DouyinApi.getAwemeInfoApi`, `getUserInfoApi(sec_uid, "post", 1, 1)`, and `getLiveInfoApi` retrieve author avatar, nickname, title/desc, cover, and follower/like counts without downloading heavy media files, an API endpoint `POST /api/parse` can resolve links and return rich preview cards before initiating downloads (Observation 2).
2. **Non-Blocking FastAPI Service**: Because `DouyinApi` and `Download` are synchronous blocking operations using `requests`, running them in the main asyncio event loop would freeze FastAPI and kill active SSE streams. Therefore, link previews must use `asyncio.to_thread` and long downloads must be managed by a background `TaskManager` / `JobManager` thread pool (Observations 1, 3).
3. **SSE Progress Stream**: Because the frontend needs live speed, item counts, and progress percentages, and existing code only uses `tqdm`, we must inject an optional `progress_callback: Optional[Callable[[DownloadProgressEvent], None]] = None` into `Download` and `download_with_resume`. The callback can be throttled to 250ms and bridged to an `asyncio.Queue` for the `/api/tasks/{task_id}/stream` SSE endpoint (Observations 3, 4, 7).
4. **Concurrency Safety & Rate Limiting**: The nested `ThreadPoolExecutor` structure ($N$ video workers $\times$ $N$ asset workers = up to $N^2$ threads) can trigger Douyin anti-scraping and socket exhaustion. The backend must bound worker threads (e.g., max 2 sub-asset threads per item, or a shared thread pool of 8–16 workers) (Observation 3).
5. **Cookie & Configuration Management**: `config.yaml` supports both `cookies` dictionary and raw `cookie` string. The settings API can read and atomically update `config.yaml` while immediately updating the runtime `DouyinApi` instance (Observations 1, 5).

---

## 3. Caveats

1. **Douyin Anti-Scraping Volatility**: Douyin Web APIs change frequently. The current `a_bogus` and `X-Bogus` implementations rely on valid web cookies (`odin_tt`, `sid_guard`, `msToken`, `ttwid`). If cookies expire, endpoints may return status code 0 with empty data. The web UI must provide explicit error messages and an easily accessible cookie configuration modal.
2. **Database Mode Dependency**: `database.py` requires SQLite and is enabled when `database: True`. If disabled, incremental downloads (`increase: True`) cannot detect previously downloaded videos.
3. **Live Stream Downloads**: `_handle_live` only extracts live metadata to JSON; it does not record continuous FLV video streams (it provides the FLV pull URL in the JSON). This conforms to the existing CLI behavior.

---

## 4. Conclusion

The existing Douyin download engine in `src/douyin/` is well-structured and fully functional. It is ready for integration into a FastAPI web application:
1. `src/douyin/douyinapi.py` and `src/douyin/urls.py` support all requested URL formats (`aweme`, `user`, `mix`, `music`, `live`).
2. `src/douyin/download.py` provides robust HTTP Range resuming, chunk streaming, and retry handling, and can be cleanly augmented with an optional event listener for real-time SSE progress tracking without breaking CLI backwards compatibility.
3. FastAPI backend architecture should follow the proven `pyvideotrans` patterns: `TaskManager` with background thread pools, SSE `/api/tasks/{id}/stream`, pure ASGI `NoCacheMiddleware`, and single-command launcher `webui.py` serving static React assets.
4. The frontend can cleanly adopt `pyvideotrans`'s warm editorial palette (`#FAF8F5`, `#8D4B00`, `#F3ECE2`) and Plus Jakarta Sans / JetBrains Mono typography for the two-step preview and download workflow.

---

## 5. Verification Method

1. **Verify Code Locations & Line References**:
   - Inspect `src/douyin/douyinapi.py:69-117` (`getKey` URL routing).
   - Inspect `src/douyin/download.py:377-436` (`download_with_resume` Range headers and retry logic).
   - Inspect `douyinCommand.py:229-245` (`DouyinClient` initialization).
2. **Verify Python Environment & Tooling**:
   - Run `uv pip list` to verify installed packages.
   - Run `python -c "from src.douyin.douyinapi import DouyinApi; print(DouyinApi)"` to verify import resolution.
3. **Invalidation Conditions**:
   - If `src/douyin/download.py` is refactored to remove HTTP Range support or thread pools.
   - If Douyin updates web security rejecting the existing `a_bogus` / `X-Bogus` algorithms in `src/common/`.
