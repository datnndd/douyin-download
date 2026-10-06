# Project: Douyin Web Downloader

## Architecture
The Douyin Web Downloader converts the existing Python CLI download engine into a desktop-grade web application.
The system is structured across four primary layers:
1. **Engine & Task Layer (`src/web/core/`, `src/web/services/`)**:
   - Wraps `src/douyin/douyinapi.py` and `src/douyin/download.py` in a non-blocking `DouyinService` and `TaskManager`.
   - Bounded thread pool (`ThreadPoolExecutor`) for multi-worker downloads without event loop blocking.
   - Throttled progress event hooks (250ms) publishing `DownloadProgressEvent` to `asyncio.Queue` subscribers.
   - HTTP Range resumption (`Range: bytes={offset}-`) with exponential backoff retries.
   - Storage organization adhering to `folderstyle` and dynamic like-count renaming (`_rename_if_exists`).
2. **FastAPI Web Service Layer (`src/web/api/`, `main_web.py`)**:
   - REST endpoints for link preview (`POST /api/parse`), task management (`/api/download`, `/api/tasks`, `/api/tasks/{task_id}/cancel`), settings (`/api/settings`), media library (`/api/media`), and system actions (`/api/open-folder`, `/api/health`).
   - Real-time streaming endpoints: Server-Sent Events (`GET /api/stream`, `GET /api/tasks/{task_id}/stream`) and WebSocket (`/ws/tasks`).
   - Range-capable media streaming (`GET /api/media/stream/{file_path}`) returning `206 Partial Content` for browser video/audio scrubbing.
   - Safe desktop bridge executing `os.startfile` on Windows with strict path validation against the configured download root.
3. **React 19 Frontend Application (`frontend/`)**:
   - Single-Page Application built with React 19, TypeScript, Vite 6, and Tailwind CSS.
   - Design system importing the warm editorial aesthetic from `pyvideotrans` (`#FAF8F5` surface, `#8D4B00` terracotta primary, `#F3ECE2` container, `#E7E4DC` borders, Plus Jakarta Sans, JetBrains Mono).
   - Two-step download interaction flow:
     - Step 1: Input link -> Content preview card (author avatar, nickname, title, cover thumbnail, estimated count).
     - Step 2: Configure options (mode: post/like/mix; asset toggles: video/music/cover/avatar/json; filters: sort by play/digg/date; thread count: 1..16) -> Launch download.
   - Real-time progress dashboard: global throughput (`MB/s`), total percentage, item progress, and active worker thread pool visualizer.
   - Storage & Media Library page/drawer: searchable file grid, in-browser video/audio playback player, download button, and "Open in Explorer" button.
   - Settings & Cookie modal: visual cookie token inputs and raw string format, interactive validation, and live `config.yaml` synchronization.
4. **Production & Packaging Layer (`webui.py`, static mount)**:
   - FastAPI mounts the compiled `frontend/dist/` assets to serve the entire application as a single cohesive unit.
   - Single-command launcher (`python webui.py`) initializes configuration, boots Uvicorn, and automatically opens the user's default browser.

---

## Feature Inventory

Every feature discovered during the survey phase is inventoried and assigned to a milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Single Aweme URL Resolution | Resolves video/note ID from short or web links | M1 | Survey |
| 2 | User Profile URL Resolution | Resolves `sec_user_id` from user homepage links | M1 | Survey |
| 3 | Mix / Collection URL Resolution | Extracts collection/mix ID from detail links | M1 | Survey |
| 4 | Music URL Resolution | Extracts music ID from audio links | M1 | Survey |
| 5 | Livestream Room Resolution | Resolves live room ID / `web_rid` | M1 | Survey |
| 6 | Link Preview Metadata Extraction | Extracts preview card info (avatar, title, thumb, stats) | M1, M2 | Survey |
| 7 | Download Task Creation | Asynchronous background task instantiation | M1, M2 | Survey |
| 8 | Task State Machine & Inspection | Query task progress, bytes, speed, thread states | M1, M2 | Survey |
| 9 | Task Listing & Filtering | List active, completed, and failed tasks | M2 | Survey |
| 10 | Task Cancellation Lifecycle | Graceful abort token checking in download loops | M1, M2 | Survey |
| 11 | Real-Time SSE Stream | Server-Sent Events stream for task progress & speed | M2 | Survey |
| 12 | Real-Time WebSocket | Full-duplex WebSocket channel for telemetry & actions | M2 | Survey |
| 13 | Selective Asset Downloading | Toggles for video, music, cover, avatar, json | M1 | Survey |
| 14 | Multi-Mode User Scraping | Scrape posts, likes, and user collections | M1 | Survey |
| 15 | Work Limits & Pagination | Enforce max item limits per mode | M1 | Survey |
| 16 | Metric Sorting & Filtering | Sort by play/digg/comment/create_time | M1 | Survey |
| 17 | Incremental Updates | Deduplicate against local SQLite database | M1 | Survey |
| 18 | Directory Organization | Support `folderstyle` hierarchy | M1 | Survey |
| 19 | Dynamic File Renaming | Handle like count changes via `_rename_if_exists` | M1 | Survey |
| 20 | Resumable Downloads & Retry | HTTP Range `206 Partial Content` & exponential retry | M1 | Survey |
| 21 | Configuration Read | Load settings from `config.yaml` | M2 | Survey |
| 22 | Configuration Write | Update `config.yaml` and hot-reload headers | M2 | Survey |
| 23 | Media Library Listing | Scan download directory tree with metadata | M2 | Survey |
| 24 | Media File Streaming (Range) | Stream MP4/MP3 with HTTP Range for browser playback | M2 | Survey |
| 25 | Media File Download | Attachment download for media library files | M2 | Survey |
| 26 | Open Folder in Explorer | Desktop bridge using `os.startfile` | M2 | Survey |
| 27 | Health & System Info | System status, disk space, active worker count | M2 | Survey |
| 28 | Warm Editorial Design System | Pyvideotrans aesthetic (`#FAF8F5`, `#8D4B00`, fonts) | M3 | Survey |
| 29 | Two-Step Download UI | Preview card -> configuration & launch workflow | M3 | Survey |
| 30 | Live Progress & Thread Visualizer | Real-time progress bars, speed, thread pool state | M3 | Survey |
| 31 | Media Library UI | In-browser player, media grid, Open in Explorer | M3 | Survey |
| 32 | Settings & Cookie Modal | Dual-format cookies, path, threads, YAML sync | M3 | Survey |
| 33 | Production Static Mount & Launcher | SPA static mount & `python webui.py` auto-launcher | M4 | Survey |
| 34 | E2E Opaque-Box Test Suite | Tiers 1-4 comprehensive test verification | M5 | Survey |
| 35 | Adversarial Coverage Hardening | White-box Tier 5 gap audit and fuzz testing | M5 | Survey |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Engine & Task Concurrency | Non-blocking service layer (`src/web/core/`, `src/web/services/`), Pydantic models, thread pool task manager, progress event hooks in `Download`, resume/range support, cancellation tokens, link resolution. | None | PLANNED |
| M2 | FastAPI REST & Real-Time APIs | REST endpoints (`/api/parse`, `/api/download`, `/api/tasks`, `/api/settings`, `/api/media`, `/api/open-folder`, `/api/health`), SSE & WebSocket streaming, HTTP 206 media streaming, config persistence. | M1 | PLANNED |
| M3 | Modern React 19 Frontend | SPA built with React 19, Vite, Tailwind CSS, warm editorial aesthetic (`#FAF8F5`, `#8D4B00`, `#F3ECE2`), 2-step preview/download flow, live progress & thread visualizer, media library player, settings modal. | M2 (interface contracts) | PLANNED |
| M4 | Production Mount & WebUI Launcher | Vite build configuration, FastAPI SPA static mount, `python webui.py` single-command launcher with browser auto-open, requirements updates. | M2, M3 | PLANNED |
| M5 | Final E2E Test Pass & Hardening | Phase 1: Pass 100% of E2E test suite (Tiers 1-4) published by E2E Testing Track; Phase 2: White-box adversarial coverage hardening (Tier 5). | M4, TEST_READY.md | PLANNED |

*Parallel Track*:
- **E2E Testing Track**: Dispatched in parallel with M1. Designs independent, requirement-driven opaque-box test suite across Tiers 1-4. Publishes `TEST_READY.md` upon completion.

---

## Interface Contracts

### 1. Link Resolution & Preview Contract (`POST /api/parse`)
**Request:**
```json
{
  "url": "https://v.douyin.com/iWhQezyaUco/",
  "cookie": "optional custom cookie string"
}
```
**Response (200 OK):**
```json
{
  "success": true,
  "url": "https://v.douyin.com/iWhQezyaUco/",
  "canonical_url": "https://www.douyin.com/video/7488893440932039970",
  "key_type": "aweme",
  "key": "7488893440932039970",
  "content_type": "video",
  "preview": {
    "title": "Video title or caption",
    "desc": "Full description",
    "author": {
      "nickname": "Author Name",
      "avatar_thumb": "https://p3.douyinpic.com/aweme/100x100/avatar.jpeg",
      "sec_uid": "MS4wLjAB..."
    },
    "cover_url": "https://p3.douyinpic.com/cover.jpeg",
    "statistics": {
      "digg_count": 12500,
      "comment_count": 840,
      "share_count": 320,
      "play_count": 150000
    },
    "duration": 45,
    "work_count": 1
  }
}
```

### 2. Download Task Contract (`POST /api/download`)
**Request:**
```json
{
  "url": "https://v.douyin.com/iWhQezyaUco/",
  "key_type": "aweme",
  "key": "7488893440932039970",
  "modes": ["post"],
  "asset_types": {
    "video": true,
    "music": true,
    "cover": true,
    "avatar": false,
    "json": true
  },
  "thread_count": 5,
  "filter": {
    "sort_by": "create_time",
    "reverse": true,
    "limit": 0
  },
  "folderstyle": true,
  "download_path": "./Downloaded/"
}
```
**Response (202 Accepted):**
```json
{
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "PENDING",
  "message": "Download task queued successfully",
  "created_at": "2026-10-06T04:10:00Z"
}
```

### 3. Task Status Contract (`GET /api/tasks/{task_id}`)
**Response (200 OK):**
```json
{
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "DOWNLOADING",
  "progress_pct": 64.5,
  "downloaded_bytes": 104857600,
  "total_bytes": 162529280,
  "speed_bps": 5242880.0,
  "current_item": "7488893440932039970",
  "completed_items": 3,
  "total_items": 5,
  "active_threads": 4,
  "threads": [
    {"thread_id": 1, "status": "DOWNLOADING", "current_file": "video.mp4", "pct": 72.0},
    {"thread_id": 2, "status": "DOWNLOADING", "current_file": "audio.mp3", "pct": 100.0},
    {"thread_id": 3, "status": "IDLE", "current_file": "", "pct": 0.0},
    {"thread_id": 4, "status": "DOWNLOADING", "current_file": "cover.jpeg", "pct": 45.0}
  ],
  "error": null,
  "created_at": "2026-10-06T04:10:00Z",
  "updated_at": "2026-10-06T04:10:30Z"
}
```

### 4. Real-time Telemetry Event (SSE `GET /api/stream` or `/api/tasks/{task_id}/stream`)
**Payload Format:**
```json
event: task_progress
data: {
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "DOWNLOADING",
  "progress_pct": 64.5,
  "speed_bps": 5242880.0,
  "downloaded_bytes": 104857600,
  "total_bytes": 162529280,
  "item_index": 3,
  "item_total": 5,
  "item_title": "Video title",
  "active_threads": 4,
  "threads": [ ... ]
}
```

### 5. Settings Contract (`GET /api/settings` and `POST /api/settings`)
**Payload:**
```json
{
  "path": "./Downloaded/",
  "music": true,
  "cover": true,
  "avatar": false,
  "json": true,
  "folderstyle": true,
  "thread": 5,
  "cookies": {
    "sessionid": "...",
    "passport_csrf_token": "..."
  },
  "raw_cookie": "sessionid=...; passport_csrf_token=..."
}
```

### 6. Media Library Contract (`GET /api/media`)
**Response (200 OK):**
```json
{
  "items": [
    {
      "id": "aweme_7488893440932039970",
      "filename": "7488893440932039970.mp4",
      "relative_path": "aweme/00012500likes_2026-10-05_title/video.mp4",
      "media_type": "video",
      "file_size": 24510200,
      "created_at": "2026-10-05T14:30:00Z",
      "preview_url": "/api/media/stream/aweme%2F00012500likes_2026-10-05_title%2Fvideo.mp4",
      "download_url": "/api/media/download/aweme%2F00012500likes_2026-10-05_title%2Fvideo.mp4"
    }
  ],
  "total": 1
}
```

### 7. Open Folder Contract (`POST /api/open-folder`)
**Request:**
```json
{
  "path": "optional relative subfolder path or empty for root"
}
```
**Response (200 OK):**
```json
{
  "success": true,
  "opened_path": "c:\\Users\\ddat2\\Downloads\\Projects\\douyin-download\\Downloaded"
}
```

---

## Code Layout

```
c:\Users\ddat2\Downloads\Projects\douyin-download\
├── config.yaml                    # Global configuration
├── webui.py                       # Single-command launcher (M4)
├── requirements.txt               # Updated with fastapi, uvicorn, etc. (M1)
├── src/
│   ├── douyin/                    # Preserved CLI download engine
│   │   ├── douyinapi.py           # Core Douyin API client
│   │   ├── download.py            # Enhanced with progress listener hooks (M1)
│   │   └── ...
│   └── web/                       # Web backend package (M1, M2)
│       ├── __init__.py
│       ├── main_web.py            # FastAPI application factory (M2, M4)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py          # Config loader and persistence (M1)
│       │   └── schemas.py         # Pydantic schemas and models (M1)
│       ├── services/
│       │   ├── __init__.py
│       │   ├── douyin_service.py  # Non-blocking wrapper for DouyinApi (M1)
│       │   ├── task_manager.py    # Job manager, thread pool, SSE queues (M1)
│       │   └── media_service.py   # Disk scanner, streaming, os.startfile (M2)
│       └── api/
│           ├── __init__.py
│           ├── router.py          # Unified APIRouter aggregator (M2)
│           ├── parse.py           # /api/parse endpoint (M2)
│           ├── download.py        # /api/download and /api/tasks endpoints (M2)
│           ├── stream.py          # /api/stream SSE and /ws/tasks WebSocket (M2)
│           ├── settings.py        # /api/settings endpoints (M2)
│           ├── media.py           # /api/media endpoints (M2)
│           └── system.py          # /api/open-folder and /api/health (M2)
├── frontend/                      # React 19 SPA frontend (M3)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.css              # Warm editorial theme tokens
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── types/                 # TypeScript interfaces matching schemas
│   │   ├── api/                   # API client (fetch & EventSource/WS)
│   │   ├── components/            # Header, Footer, Stepper, Tabs
│   │   │   ├── PreviewCard.tsx    # Step 1 preview card
│   │   │   ├── DownloadConfig.tsx # Step 2 configuration form
│   │   │   ├── ProgressTracker.tsx# Real-time progress & thread visualizer
│   │   │   ├── MediaLibrary.tsx   # Video/audio player & file list
│   │   │   └── SettingsModal.tsx  # Cookies and configuration editor
│   │   └── hooks/                 # useTaskStream, useMedia, useSettings
│   └── dist/                      # Production build output (M4)
└── tests/                         # E2E & Integration tests (E2E Track / M5)
    ├── e2e/
    ├── integration/
    └── run_tests.py
```
