# Douyin Web Downloader — Backend Codebase Survey & Architecture Report

**Author**: Codebase Explorer (Backend)  
**Date**: 2026-10-06  
**Target Repository**: `c:\Users\ddat2\Downloads\Projects\douyin-download`  
**Reference Design System**: `c:\Users\ddat2\Downloads\Projects\pyvideotrans`  

---

## 1. Executive Summary

This investigation surveys the existing Douyin download engine and CLI implementation in `douyin-download` to establish the architectural foundation for converting it into a modern FastAPI web service. The target architecture supports:
- Two-step download flow (Link Preview -> Selective Download Execution).
- Real-time progress monitoring via Server-Sent Events (SSE) and WebSocket.
- Configurable multi-threaded worker pools with HTTP Range resume capability.
- Full Douyin URL support (`aweme` single videos/notes, `user` posts/likes/mixes, `mix` collections, `music`, `live`).
- Disk hierarchy compliance (`folderstyle` true/false).
- Media library scanning and browser preview playback.
- Dynamic cookie and settings configuration backed by `config.yaml`.
- Single-command launcher (`python webui.py`) serving both FastAPI APIs and the production-built React frontend.

---

## 2. Codebase Structure & Inventory

```
douyin-download/
├── config.yaml               # User configuration (cookies, path, toggles, filters)
├── config.example.yml        # Example configuration template
├── douyinCommand.py          # Existing CLI entrypoint & DouyinClient orchestrator
├── main.py                   # Stub script ("Hello from douyin-download!")
├── pyproject.toml            # Project metadata (Python >= 3.11)
├── requirements.txt          # Python dependencies (requests, pyyaml, tqdm, gmssl, etc.)
├── src/
│   ├── __init__.py           # Default User-Agent string
│   ├── common/
│   │   ├── abogus.py         # A-Bogus algorithm implementation for API detail endpoints
│   │   └── utils.py          # X-Bogus, ttwid registration, string sanitization, helpers
│   └── douyin/
│       ├── __init__.py       # Default douyin_headers with dynamic random msToken & ttwid
│       ├── database.py       # SQLite WAL database schema and upsert queries (dim_user, fact_aweme)
│       ├── douyinapi.py      # Core Douyin API wrapper (URL parsing, pagination, data conversion)
│       ├── download.py       # Multi-threaded download engine with HTTP Range resume
│       ├── result.py         # Data mapping schemas (awemeDict, authorDict, videoDict, liveDict)
│       └── urls.py           # Douyin Web API endpoint constants
└── Downloaded/               # Default output directory
```

---

## 3. Deep Dive: `DouyinApi` Architecture & Link Parsing

### 3.1. Link Extraction & URL Normalization
- **Share Link Parsing** (`src/douyin/douyinapi.py:63-65`):
  ```python
  def getShareLink(self, string):
      return re.findall(r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+', string)[0]
  ```
  Extracts raw URLs from noisy mobile share strings (e.g., `7.41 复制打开抖音... https://v.douyin.com/xxx/`).
- **Key & Type Extraction** (`src/douyin/douyinapi.py:69-117`):
  Performs an initial HTTP `GET` through `self.session.get(url=url, headers=douyin_headers)` to follow redirects (such as `v.douyin.com` -> `www.douyin.com/video/...`).
  It inspects both `r.request.path_url` and `r.url` to classify links:

  | Target Type | URL Pattern | Key Extracted | Output Key Type |
  | :--- | :--- | :--- | :--- |
  | Single Video | `/video/(\d+)` | `aweme_id` | `aweme` |
  | Single Picture Album | `/note/(\d+)` | `aweme_id` | `aweme` |
  | User Profile | `/user/([\d\D]*?)(?:\?|$)` | `sec_uid` | `user` |
  | Collection / Mix | `/mix/detail/(\d+)` or `/collection/(\d+)` | `mix_id` | `mix` |
  | Music Audio | `/music/(\d+)` | `music_id` | `music` |
  | Livestream | `/webcast/reflow/` or `live.douyin.com/<web_rid>` | `web_rid` | `live` |

### 3.2. Douyin API Endpoints & Data Processing
- **Single Work Detail** (`getAwemeInfoApi`):
  - Uses `POST_DETAIL` (`https://www.douyin.com/aweme/v1/web/aweme/detail/?`) signed with `a_bogus` from `ABogus` (`src/common/abogus.py`).
  - Normalizes raw response into a clean dictionary via `self.result.dataConvert()` (`src/douyin/result.py`).
  - Distinguishes video (`awemeType=0`), image carousel (`awemeType=1`), and extracts 1080p video URLs (preferring `bit_rate[0]` over default `play_addr`).
- **User Posts and Likes** (`getUserInfoApi`):
  - Pagination via `max_cursor` on `USER_POST` or `USER_FAVORITE_A/B` signed with `X-Bogus` (`src/common/utils.py`).
  - Supports incremental update checks against SQLite `database.py`.
- **Collection / Mix** (`getMixInfoApi` and `getUserAllMixInfoApi`):
  - Iterates over mix items using `USER_MIX` and `USER_MIX_LIST`.
- **Music & Live** (`getMusicInfo`, `getLiveInfoApi`):
  - Fetches original audio tracks and livestream status/FLV pull URLs.

### 3.3. Link Preview Integration (Two-Step Workflow)
In the existing CLI, `douyinCommand.py:314` uses a peek call:
```python
peek = self.api.getUserInfoApi(sec_uid, "post", 1, 1)
```
For the FastAPI web application, a unified `/api/parse` endpoint can execute link resolution and return a standardized preview object:
- **Single Video / Note**: Video title (`desc`), author nickname, avatar thumbnail, cover thumbnail, duration, like/play counts.
- **User Profile**: Author nickname, avatar, signature, follower count, total likes, estimated post count.
- **Mix / Collection**: Mix name, cover image, update status, author nickname.
- **Music**: Music title, cover, owner nickname.
- **Live**: Room title, broadcaster nickname, avatar, live status, viewer count.

---

## 4. Deep Dive: Download Engine Architecture

### 4.1. Core Download Class (`src/douyin/download.py`)
- **Session Management**: Thread-local `requests.Session` with `HTTPAdapter(max_retries=2, pool_connections=100, pool_maxsize=100)` avoids socket exhaustion during concurrent requests.
- **HTTP Range & Resume Mechanism** (`download_with_resume`, lines 377-436):
  1. Checks if target file already exists on disk and reads its current size: `file_size = filepath.stat().st_size`.
  2. If `file_size > 0`, adds HTTP header `Range: bytes={file_size}-`.
  3. Server responses:
     - `HTTP 206 Partial Content`: Stream chunks and append (`mode = 'ab'`). `total_size = content_length + file_size`.
     - `HTTP 200 OK`: Server does not support Range or starts from beginning; overwrites (`mode = 'wb'`).
  4. Chunk streaming loop: Reads chunks of `chunk_size = 8192` (8 KB), writes to disk, and updates progress bar.
  5. Exponential retry: On socket error or connection drop, retries up to 5 times (`retry_times = 5`) with exponential backoff (`min(2**(attempt+1), 10) + jitter`), resetting the thread-local session on retry to purge dead connections.

### 4.2. Threading Model & Concurrency Analysis
In the current implementation:
- Outer level: `userDownload` spawns `min(self.thread, total_count)` workers to download different videos concurrently.
- Inner level: `awemeDownload` spawns another `ThreadPoolExecutor(max_workers=self.thread)` to download video, music, cover, and avatar assets concurrently.

**Critical Concurrency Observation**:
If a user sets `thread: 10`, downloading a creator's posts can spawn $10 \times 10 = 100$ concurrent network threads! This can lead to:
1. Thread explosion and CPU/GIL contention.
2. Douyin rate-limiting (HTTP 429 or empty response bodies).
3. Disk I/O bottlenecks.

**Web Architecture Solution**:
Unify the thread pool or configure the inner worker pool with a small cap (e.g., 2-3 workers per video for sub-assets), or use a single global bounded `ThreadPoolExecutor` (e.g. 8-16 workers total) managed by the FastAPI backend `JobManager`.

---

## 5. Real-Time Progress Hooks: SSE & WebSocket Architecture

### 5.1. The Progress Gap in Existing Code
Existing `Download` has hardcoded `tqdm` progress bars in three locations:
1. `download_with_resume` (`tqdm(total=total_size, unit='B', ...)`).
2. `_download_media_files_threaded` (`tqdm(total=len(tasks), ...)`).
3. `userDownload` (`tqdm(total=total_count, desc="Processing videos")`).

These write directly to `sys.stderr` and cannot be consumed by web frontends.

### 5.2. Proposed Non-Invasive Progress Callback Interface
We introduce a lightweight, optional event listener protocol that attaches directly to `Download`:

```python
from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class DownloadProgressEvent:
    job_id: str
    event_type: str        # 'job_start', 'item_start', 'chunk', 'item_done', 'job_done', 'error'
    item_index: int        # 1-indexed current item
    item_total: int        # total items in job
    item_title: str        # description or video title
    asset_type: str        # 'video', 'image', 'music', 'cover', 'avatar'
    downloaded_bytes: int  # bytes transferred for current file
    total_bytes: int       # total file size
    speed_bps: float       # current transfer rate (bytes/sec)
    progress_pct: float    # 0.0 - 100.0 (overall or file level)
    active_threads: int
    message: str = ""

# Signature for listener
ProgressListener = Callable[[DownloadProgressEvent], None]
```

### 5.3. Throttled Chunk Progress & Speed Calculation
To prevent saturating the event loop with thousands of 8 KB chunk events per second:
- Track `last_emit_time = time.time()` and `last_emit_bytes = current_bytes`.
- Emit a `chunk` event only every 200ms–300ms, or when a file completes.
- Calculate smoothed speed:
  $$\text{speed} = \frac{\Delta \text{bytes}}{\Delta \text{time}}$$

### 5.4. Real-Time Streaming Endpoints in FastAPI
Adopting the battle-tested SSE architecture from `pyvideotrans` (`videotrans/api/routes/jobs.py`):
1. **SSE Endpoint (`/api/tasks/{task_id}/stream`)**:
   - Headers: `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, `Content-Type: text/event-stream`.
   - Uses `asyncio.Queue` subscribed to the job's progress listener.
   - Worker threads push events into the async queue via `loop.call_soon_threadsafe(queue.put_nowait, event)`.
   - Emits `: keep-alive\n\n` comments every 15s to prevent intermediate proxy timeout.
   - Disconnect detection: checks `await request.is_disconnected()` to unsubscribe and stop queuing.
2. **WebSocket Endpoint (`/ws/tasks/{task_id}`)**:
   - Optional bidirectional channel for interactive operations (e.g. pause/cancel signals from client).
3. **REST Polling (`/api/tasks/{task_id}`)**:
   - Snapshot endpoint returning current state for clients unable to maintain persistent streams.

---

## 6. Non-Blocking Execution Strategy for FastAPI

### 6.1. The Threading / Async Boundary
Because `requests`, `DouyinApi`, and `Download` are synchronous and perform blocking I/O:
- **Rule**: NEVER call `api.getAwemeInfoApi(...)` or `downloader.awemeDownload(...)` directly inside an `async def` FastAPI route without delegating to a worker thread.
- **Short Operations** (Preview / Resolve URL):
  ```python
  @router.post("/api/parse")
  async def parse_link(payload: ParseRequest):
      # Offload synchronous resolution to worker thread pool
      preview = await asyncio.to_thread(client.resolve_and_preview, payload.url)
      return preview
  ```
- **Long-Running Operations** (Download Tasks):
  - Use a centralized `TaskManager` / `JobManager` singleton.
  - When the user calls `POST /api/download`, the server:
    1. Generates a unique `task_id` (`uuid4().hex`).
    2. Initializes a `TaskRecord` with status `"queued"`.
    3. Submits task execution to a background `ThreadPoolExecutor`.
    4. Immediately returns HTTP 202 Accepted with `{ "task_id": task_id, "status": "queued" }`.
    5. The client connects to `/api/tasks/{task_id}/stream` to watch live execution.

### 6.2. Task Cancellation & Control
To support cancelling or pausing in-flight downloads:
- Attach a `threading.Event()` cancel token to each `TaskRecord`.
- Pass the token into the chunk read loop in `download_with_resume`:
  ```python
  if cancel_token and cancel_token.is_set():
      logger.info(f"Download cancelled by user: {desc}")
      return False
  ```

---

## 7. Storage Hierarchy & `folderstyle` Rules

### 7.1. Directory Structure Mapping
All media is stored under `cfg.path` (default `./Downloaded/`).

```
Downloaded/
├── aweme/                                # Single videos / notes
│   ├── [folderstyle=True]
│   │   └── 000029183likes_2025-09-02 22.09.04_Desc/
│   │       ├── 000029183likes_2025-09-02 22.09.04_Desc_video.mp4
│   │       ├── 000029183likes_2025-09-02 22.09.04_Desc_cover.jpeg
│   │       ├── 000029183likes_2025-09-02 22.09.04_Desc_avatar.jpeg
│   │       ├── 000029183likes_2025-09-02 22.09.04_Desc_music_Title.mp3
│   │       └── 000029183likes_2025-09-02 22.09.04_Desc_result.json
│   └── [folderstyle=False]
│       ├── 000029183likes_2025-09-02 22.09.04_Desc_video.mp4
│       └── 000029183likes_2025-09-02 22.09.04_Desc_cover.jpeg
├── user_Nickname_secUid/                 # User profiles
│   ├── post/                             # Published works
│   ├── like/                             # Liked works
│   └── mix/                              # User collections
│       └── CollectionName_mixId/
│           └── ...
├── CollectionName_mixId/                 # Mix downloaded directly
└── music_MusicTitle_musicId/             # Music downloaded directly
```

### 7.2. Dynamic Renaming Logic
In `src/douyin/download.py:189-272`, `_rename_if_exists` searches for existing downloaded files with the same creation timestamp and description suffix (`*likes_{suffix}`) but a different like count (`{digg_count:09d}likes_...`). When found, it automatically renames the folder/files to update the like count while preserving existing media files.

### 7.3. Media Library Endpoint Requirements
1. **Catalog API (`GET /api/media`)**:
   - Recursively traverses `./Downloaded/` (or queries SQLite `data.db`).
   - Identifies video (`.mp4`), audio (`.mp3`), images (`.jpeg`, `.jpg`, `.png`), and metadata (`_result.json`).
   - Returns structured records with filename, author, likes, size, duration, creation time, relative path, and playback URL.
2. **Streaming / Static Playback (`GET /api/media/stream/{path:path}`)**:
   - Supports HTTP Range headers for in-browser video/audio seeking.
3. **OS Explorer Integration (`POST /api/system/open-folder`)**:
   - On Windows: triggers `os.startfile(target_path)` or `subprocess.Popen(["explorer", str(target_path)])` to open File Explorer directly to the downloaded folder.

---

## 8. Settings & Configuration Management

### 8.1. `config.yaml` Structure & Dual-Cookie Format
The existing configuration in `config.yaml` supports two cookie formats:
1. Structured dictionary:
   ```yaml
   cookies:
     msToken: "..."
     ttwid: "..."
     odin_tt: "..."
     passport_csrf_token: "..."
     sid_guard: "..."
   ```
2. Raw header string:
   ```yaml
   cookie: "msToken=...; ttwid=...; ..."
   ```
When `cookies` dict exists, `Config.from_yaml` automatically joins them into a semicolon-delimited cookie string.

### 8.2. Settings API Endpoints
- `GET /api/settings`: Returns current configuration (path, thread count, asset preferences, cookies, filter defaults).
- `PUT /api/settings`: Validates and saves updated configuration back to `config.yaml` using atomic write (write to temp file then rename) to prevent file corruption.
- Applies updated cookies to the active `DouyinApi` instance immediately without restarting the server.

---

## 9. Frontend Integration & Design System Alignment

### 9.1. Design System & Palette (from `pyvideotrans`)
The web application frontend will match `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\src\index.css`:
- **Surface**: Warm ivory `#FAF8F5`
- **Surface Container**: Soft beige `#F3ECE2` (cards, sidebars)
- **Primary Accent**: Amber/terracotta `#8D4B00` (buttons, active states, progress indicators)
- **Primary Hover**: Dark amber `#743D00`
- **Primary Light Container**: Warm peach `#FFDCC3`
- **Border / Outline**: `#E5DED4` (subtle dividers)
- **Text / On-Surface**: `#1F2328` (charcoal), `#595E68` (muted grey)
- **Fonts**: `Plus Jakarta Sans` for UI copy; `JetBrains Mono` for IDs, metrics, and speeds.

### 9.2. Two-Step Interaction Workflow
```
[User pastes Douyin Link]
          │
          ▼
    POST /api/parse
          │
          ▼
[Preview Card Displays]
• Video Title / Desc
• Author Avatar & Nickname
• Cover Thumbnail Preview
• Work / Like / Collect Count
          │
          ▼
[Configuration Controls]
• Mode: Post / Like / Mix (if user profile)
• Asset Toggles: [x] Video  [x] Audio  [x] Cover  [x] Avatar  [x] JSON
• Filters: Sort by play_count / digg_count / create_time
• Threads: [ 10 ]
          │
          ▼
    POST /api/download
          │
          ▼
[Real-Time Progress Tracker]
• Live SSE Stream: Overall progress bar (%)
• Current item title & active asset badge
• Instantaneous download speed (e.g., 4.2 MB/s)
• Active worker threads count
• Cancel / Pause action buttons
```

---

## 10. Constraints, Bottlenecks & Risk Mitigation

| Area | Identified Issue / Bottleneck | Architectural Solution |
| :--- | :--- | :--- |
| **Concurrency** | Nested `ThreadPoolExecutor` (outer item pool $\times$ inner asset pool) can generate 100+ threads. | Cap sub-asset pool to 2-3 workers per item or use a shared bounded pool (8-16 workers max) in `TaskManager`. |
| **Blocking Event Loop** | Synchronous `requests` calls block FastAPI if run in async route handlers. | Always run parsing and downloads in `asyncio.to_thread` or background thread pool. |
| **Progress Flooding** | High-frequency chunk loops (8 KB chunks) could flood SSE/WS with 1,000+ msgs/sec. | Throttle chunk events to 250ms intervals with aggregated bytes and moving-average speed. |
| **Global State Mutation** | `douyin_headers["Cookie"]` is a global dict in `src.douyin`. Concurrent requests could race. | Instantiate session headers per task or protect updates with a threading lock. |
| **Cookie Invalidation** | Douyin tokens (`odin_tt`, `sid_guard`) expire, causing silent empty API responses. | Detect empty API responses and surface informative error cards guiding users to refresh cookies in Settings. |
| **Missing Dependencies** | Virtual environment has `requests`, `pyyaml`, `tqdm`, but lacks `fastapi`, `uvicorn`, `sse-starlette`. | Specify `fastapi>=0.115.0`, `uvicorn>=0.30.0` in `requirements.txt` / `pyproject.toml`. |
| **Production Packaging** | Need single-command start (`python webui.py`). | Mount production Vite build (`dist/`) under FastAPI static files with HTML5 history API fallback. |

---

## 11. Proposed Project Architecture for Implementation

```
douyin-download/
├── config.yaml
├── webui.py                    # Single-command launcher (uvicorn server + browser open)
├── src/
│   ├── api/                    # NEW: FastAPI web layer
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI app factory, CORS, static mount, NoCacheMiddleware
│   │   ├── task_manager.py     # Background thread pool, task queue, event subscription
│   │   ├── routes/
│   │   │   ├── parse.py        # /api/parse (Link resolution and preview)
│   │   │   ├── tasks.py        # /api/tasks (Download trigger, SSE /stream, cancel)
│   │   │   ├── media.py        # /api/media (Library scan, stream, open folder)
│   │   │   └── settings.py     # /api/settings (Config YAML read/write)
│   │   └── schemas.py          # Pydantic models for requests and responses
│   ├── douyin/                 # Existing core engine (enhanced with callbacks)
│   │   ├── douyinapi.py
│   │   ├── download.py         # Added ProgressListener support & cancel token check
│   │   ├── database.py
│   │   └── urls.py
│   └── common/
│       ├── abogus.py
│       └── utils.py
├── frontend/                   # NEW: Modern React 19 + Vite + Tailwind SPA
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── index.css           # Warm editorial theme matching pyvideotrans
│   │   ├── App.tsx
│   │   ├── components/         # PreviewCard, DownloadControls, ProgressModal, MediaDrawer
│   │   └── services/           # api.ts, sse.ts
│   └── dist/                   # Built production bundle served by FastAPI
```

This survey provides the complete roadmap and exact technical specifications for the implementer agent.
