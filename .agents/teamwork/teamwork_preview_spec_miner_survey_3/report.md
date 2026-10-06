# Specification Mining Report: Douyin Web Downloader API & Behavioral Contracts

## Executive Summary
This document provides the authoritative API specifications, behavioral contracts, data models, state machines, and integration protocols for transforming the Douyin Downloader CLI engine into a modern, production-grade FastAPI web application.

The analysis is synthesized directly from:
1. User requirements in `ORIGINAL_REQUEST.md` and `DISPATCH.md`.
2. Existing codebase implementations in `douyinCommand.py`, `src/douyin/douyinapi.py`, `src/douyin/download.py`, `src/douyin/result.py`, `src/douyin/urls.py`, `src/douyin/database.py`, and `src/common/utils.py`.
3. Configuration specifications in `config.yaml`.
4. Visual design & UX system in `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\src\index.css`.

---

## Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Link Parsing | Single Aweme URL Resolution | Extracts video or note ID from short link (`v.douyin.com`) or direct web URL (`douyin.com/video/`, `douyin.com/note/`). | Raw link or mobile share text | Resolved canonical URL, `key_type="aweme"`, `aweme_id` | Returns 400 Bad Request if no valid URL found | `src/douyin/douyinapi.py:getKey`, `getShareLink` |
| 2 | Link Parsing | User Profile URL Resolution | Resolves `sec_user_id` from user homepage link (`douyin.com/user/<sec_uid>`). | Homepage link or share token | Canonical URL, `key_type="user"`, `sec_uid` | Returns 400 if user path missing or malformed | `src/douyin/douyinapi.py:getKey` |
| 3 | Link Parsing | Mix / Collection URL Resolution | Extracts collection ID from `/mix/detail/<id>` or `/collection/<id>`. | Mix album share link | Canonical URL, `key_type="mix"`, `mix_id` | Returns 400 if mix ID not extractable | `src/douyin/douyinapi.py:getKey` |
| 4 | Link Parsing | Music URL Resolution | Extracts original sound music ID from `/music/<id>`. | Music share link | Canonical URL, `key_type="music"`, `music_id` | Returns 400 if music ID missing | `src/douyin/douyinapi.py:getKey` |
| 5 | Link Parsing | Livestream Room Resolution | Resolves live room ID or `web_rid` from `live.douyin.com/<id>` or `/webcast/reflow/<id>`. | Livestream URL or reflow link | Canonical URL, `key_type="live"`, `web_rid` | Returns 400 if room offline or invalid | `src/douyin/douyinapi.py:getKey` |
| 6 | Link Parsing | Metadata Extraction & Preview (`POST /api/parse`) | Resolves link and returns preview card payload: author avatar, nickname, title, cover thumbnail, statistics, content type, estimated work count. | `ParseRequest(url, cookie=None)` | `ParseResponse(url, key_type, key, preview)` | 400 on invalid URL, 502 if upstream Douyin API blocked/fails | `ORIGINAL_REQUEST.md`, `douyinCommand.py:311-450` |
| 7 | Task Engine | Download Task Creation (`POST /api/download`) | Creates an asynchronous background download job configured with asset toggles, modes, limits, and thread counts. | `DownloadRequest` payload | `TaskResponse(task_id, status="PENDING", message)` | 400 on invalid config, 422 on schema violation | `ORIGINAL_REQUEST.md`, `douyinCommand.py:Config` |
| 8 | Task Engine | Task State Machine & Inspection (`GET /api/tasks/{task_id}`) | Inspects lifecycle state, overall progress %, downloaded bytes, speed, thread states, and logs. | `task_id` (UUID string) | `TaskDetailResponse` | 404 if `task_id` not found | `ORIGINAL_REQUEST.md`, `src/douyin/download.py` |
| 9 | Task Engine | Task Listing (`GET /api/tasks`) | Lists all current, completed, or failed download tasks with summary metrics. | Query params: `status`, `limit`, `offset` | `TaskListResponse(tasks, total)` | 200 with empty list if no tasks | `ORIGINAL_REQUEST.md` |
| 10 | Task Engine | Task Cancellation (`POST /api/tasks/{task_id}/cancel`) | Signals background workers and downloader to abort active operations and set state to CANCELLED. | `task_id` | `TaskCancelResponse(task_id, status="CANCELLED")` | 404 if not found, 409 if already completed/failed | `ORIGINAL_REQUEST.md:R1` |
| 11 | Streaming | Real-Time SSE Stream (`GET /api/stream`) | Server-Sent Events stream emitting task progress, byte counters, speed, active thread states, and log messages. | Query param: optional `task_id` filter | SSE event stream (`text/event-stream`) | Auto-reconnect on network drop | `ORIGINAL_REQUEST.md:R1`, `DISPATCH.md` |
| 12 | Streaming | Real-Time WebSocket (`/ws/tasks`) | Full-duplex WebSocket channel for subscribing to task events, receiving worker telemetry, and sending cancel signals. | WebSocket frames (`subscribe`, `unsubscribe`, `cancel`) | JSON event frames (`task_progress`, `thread_state`, `log`) | 1008 on policy error, automatic ping/pong keepalive | `ORIGINAL_REQUEST.md:R1`, `DISPATCH.md` |
| 13 | Asset Control | Selective Asset Downloading | Selectively downloads video MP4, image album JPEGs, music MP3, video cover JPEG, author avatar JPEG, and metadata JSON. | Flags: `video`, `music`, `cover`, `avatar`, `json` | Downloaded files on disk in `./Downloaded/` | Omits unselected assets gracefully | `src/douyin/download.py:80-149`, `config.yaml` |
| 14 | Asset Control | Multi-Mode User Scraping | Allows choosing between posted works (`post`), liked works (`like`), and all user collections (`mix`). | `mode: ["post", "like", "mix"]` | Downloaded works organized per mode | Skips empty modes with log warning | `douyinCommand.py:311-356`, `config.yaml` |
| 15 | Asset Control | Work Limits & Pagination | Enforces maximum items to download (`number.post`, `number.like`, `number.mix`, 0=all). | `number: {"post": int, ...}` | Clamped work list | Stops fetching immediately upon reaching limit | `douyinCommand.py:335`, `douyinapi.py:271` |
| 16 | Asset Control | Metric Sorting & Filtering | Sorts works by `play_count`, `digg_count`, `comment_count`, `share_count`, or `create_time`, with `reverse` and `limit`. | `filter: {sort_by, reverse, limit}` | Sorted and sliced aweme list | Unknown sort metric logs warning and keeps default | `douyinCommand.py:248-272`, `config.yaml` |
| 17 | Asset Control | Incremental Updates | Deduplicates against local SQLite DB (`data.db`), stopping pagination once an existing top/normal work is hit. | `increase: {"post": true, ...}` | Delta awemes only | Requires `database: true`; falls back to full if DB off | `src/douyin/douyinapi.py:281-290`, `database.py` |
| 18 | Storage | Directory Organization (`folderstyle`) | `folderstyle=True` creates dedicated subfolders per work; `folderstyle=False` places media directly into user/mode folder. | `folderstyle: bool` | Organized disk hierarchy | Fallback to safe directory names | `src/douyin/download.py:296`, `config.yaml` |
| 19 | Storage | Dynamic File Renaming (`_rename_if_exists`) | Automatically detects existing local downloads when like count changes and renames files/folders (`0000100likes_...` -> `0000250likes_...`). | Save path, target filename, time/desc suffix | Renamed file/folder preserving data | Catches `OSError` without aborting download | `src/douyin/download.py:189-272` |
| 20 | Storage | Resumable Downloads & Retry | Uses HTTP Range header (`Range: bytes={size}-`) and 206 Partial Content with up to 5 exponential backoff retries. | Media URL, destination path, desc | Completed file on disk | Returns False after 5 failed attempts | `src/douyin/download.py:377-436` |
| 21 | Configuration | Configuration Read (`GET /api/settings`) | Loads current settings from `config.yaml`, formatting cookies and directory paths for web display. | None | `SettingsModel` (path, thread, cookies, asset flags) | 500 if YAML unparseable, falls back to defaults | `douyinCommand.py:98-140`, `config.yaml` |
| 22 | Configuration | Configuration Write (`POST /api/settings`) | Updates `config.yaml` without corrupting file structure and hot-reloads runtime client configuration and headers. | `SettingsModel` | Updated `SettingsModel` | 400 on invalid paths or invalid thread counts | `ORIGINAL_REQUEST.md:R4`, `config.yaml` |
| 23 | Media Library | Media Library Listing (`GET /api/media`) | Scans download directory tree, returning media files with types, file sizes, thumbnails, and preview URLs. | Query params: `subfolder`, `type`, `search`, `page`, `page_size` | `MediaListResponse(items, total)` | 404 if subfolder not found, 403 on traversal attempt | `ORIGINAL_REQUEST.md:R3` |
| 24 | Media Library | Media File Streaming (`GET /api/media/stream/{file_path}`) | Streams MP4 video and MP3 audio files with HTTP Range Request (`206 Partial Content`) support for browser playback. | `file_path` (relative to download path), `Range` header | Binary stream with `Accept-Ranges`, `Content-Type: video/mp4` | 404 if file missing, 403 on path traversal, 416 on invalid range | `ORIGINAL_REQUEST.md:R3` |
| 25 | Media Library | Media File Download (`GET /api/media/download/{file_path}`) | Serves file with `Content-Disposition: attachment; filename="..."` for direct browser download. | `file_path` | Binary download stream | 404 if file missing, 403 on path traversal | `ORIGINAL_REQUEST.md:R3` |
| 26 | OS Integration | Open Folder in Explorer (`POST /api/open-folder`) | Triggers native Windows Explorer to open download root directory or highlight specific downloaded file. | `OpenFolderRequest(path=None)` | `OpenFolderResponse(success, opened_path)` | 400 if path does not exist, 403 if path outside download root | `ORIGINAL_REQUEST.md:R3:31` |
| 27 | System | Health & System Info (`GET /api/health`) | Returns system operational status, active thread pools, download directory disk space, and version. | None | `HealthResponse(status="ok", uptime, disk_free, active_tasks)` | 200 OK | Standard operational contract |

---

## Edge Cases

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | URL Resolution | Share text containing noise: `7.21 复制打开抖音，看看【xxx】 https://v.douyin.com/iWhQezyaUco/ 02/09 j@y.Nq :1pm` | `re.findall` successfully extracts `https://v.douyin.com/iWhQezyaUco/`, follows 302 redirect, and returns valid `sec_uid`. |
| 2 | URL Resolution | Plain text with no URL: `"Great video!"` | `DouyinApi.getShareLink` raises `IndexError` on empty match list. Must be caught by API layer and converted to HTTP 400 Bad Request with message `"No valid URL found in input string"`. |
| 3 | URL Resolution | Expired / Deleted Aweme ID: `POST /api/parse` with dead link | Upstream Douyin API returns empty payload or `status_code != 0`. `getAwemeInfoApi` loop times out or returns `{}`. Handled as HTTP 404 Not Found (`"Post not found or has been deleted"`). |
| 4 | URL Resolution | Offline Livestream URL: `live.douyin.com/669067451826` | Upstream returns `status_str == "4"`. `getLiveInfoApi` returns `status: "4"` ("Stream ended!"). Preview card must display "Livestream is currently offline" badge. |
| 5 | Link Parsing | Note / Gallery post with multiple images (e.g. 15 slides) | `awemeType == 1`. Code creates separate image download tasks `[Image 1]..[Image 15]` saving as `{name}_image_{i}.jpeg`. |
| 6 | File Naming | Caption with forbidden Windows filesystem chars (`/ \ : * ? " < > |`) and emojis | `utils.replaceStr` filters out illegal characters, keeping only alphanumeric and Chinese characters, and truncates length to 20 characters. Safe for Windows paths. |
| 7 | Storage | Downloaded file already exists on disk | `_download_media` checks `path.exists()`, logs `File Exited`, and returns `True` immediately without re-downloading. |
| 8 | Storage | Existing file has changed like count (e.g. from 1,000 to 2,500 likes) | `_rename_if_exists` matches suffix `create_time_desc`, discovers old file `000001000likes_...`, and renames it to `000002500likes_...` before downloading any new assets. |
| 9 | Network Resiliency | Network drop mid-download of large video (e.g. 50MB downloaded out of 100MB) | `download_with_resume` catches connection exception, reads local file size (50MB), sends header `Range: bytes=52428800-`, receives `HTTP 206 Partial Content`, and appends in `ab` mode. |
| 10 | Security | Malicious path in `POST /api/open-folder` or `/api/media/stream/..%2F..%2FWindows%2FSystem32` | Path resolution normalizes `Path(path).resolve()`. If it does not start with `config.path.resolve()`, request is rejected with HTTP 403 Forbidden. |
| 11 | Concurrency | Thread count configured as `0` or negative number | `validate_and_prepare` clamps to minimum of 1 or falls back to default 5. Pydantic validation enforces `ge=1, le=32`. |
| 12 | Cookie Parsing | Cookies specified as raw semicolon string vs dictionary in YAML | `Config.from_yaml` checks both: merges `cookies: {k:v}` into string `"k=v; ..."` or reads `cookie: "..."`. Both formats are supported seamlessly. |
| 13 | Task Cancellation | User cancels task while fetching 500 posts from a user profile | Task manager sets cancellation event. Worker thread pool shuts down without executing remaining jobs, state transitions to `CANCELLED`, partial files are preserved or cleaned up. |

---

## Detailed REST API Specification

### Base URL
All API routes are served under prefix `/api`:
- Base: `http://127.0.0.1:8000/api`
- WebSocket: `ws://127.0.0.1:8000/ws`

---

### Endpoint 1: Link Resolution & Preview
`POST /api/parse`

Resolves any Douyin link (single video, gallery note, user profile, collection mix, music, or livestream), extracts rich metadata, and formats a link preview card payload.

#### Request Schema (`ParseRequest`)
```json
{
  "url": "https://v.douyin.com/8muR-7iUO6E/",
  "cookie": "optional custom cookie override"
}
```

#### Response Schema (`ParseResponse`)
```json
{
  "success": true,
  "url": "https://v.douyin.com/8muR-7iUO6E/",
  "canonical_url": "https://www.douyin.com/video/7488893440932039970",
  "key_type": "aweme",
  "key": "7488893440932039970",
  "content_type": "video",
  "preview": {
    "title": "Amazing scenery in western Sichuan",
    "cover_url": "https://p3-pc.douyinpic.com/tos-cn-p-0015/...",
    "dynamic_cover_url": "https://p3-pc.douyinpic.com/tos-cn-p-0015/...~c5_300x400.jpeg",
    "create_time": "2026-03-15 14:30:22",
    "author": {
      "nickname": "Traveler_Zhang",
      "sec_uid": "MS4wLjABAAAA...",
      "uid": "10493820293",
      "avatar_url": "https://p3-pc.douyinpic.com/aweme/1080x1080/...",
      "signature": "Exploring nature worldwide",
      "follower_count": 48200,
      "total_favorited": 1290000
    },
    "statistics": {
      "digg_count": 28400,
      "play_count": 350000,
      "comment_count": 1420,
      "share_count": 890,
      "collect_count": 4500
    },
    "estimated_work_count": 1,
    "available_modes": ["post"],
    "has_video": true,
    "has_images": false,
    "has_music": true
  }
}
```

#### Error Responses
- `400 Bad Request`: `{ "error": { "code": "INVALID_URL", "message": "No valid Douyin link found in input string." } }`
- `404 Not Found`: `{ "error": { "code": "CONTENT_NOT_FOUND", "message": "Content has been removed or is inaccessible." } }`
- `502 Bad Gateway`: `{ "error": { "code": "UPSTREAM_FAILURE", "message": "Douyin API returned an error or blocked the request." } }`

---

### Endpoint 2: Download Task Creation
`POST /api/download`

Spawns an asynchronous background download job. Returns immediately with a unique `task_id`.

#### Request Schema (`DownloadRequest`)
```json
{
  "url": "https://v.douyin.com/8muR-7iUO6E/",
  "key_type": "aweme",
  "key": "7488893440932039970",
  "download_dir": "./Downloaded/",
  "thread": 5,
  "assets": {
    "video": true,
    "music": false,
    "cover": true,
    "avatar": true,
    "json": true
  },
  "folderstyle": true,
  "mode": ["post"],
  "number": {
    "post": 0,
    "like": 0,
    "allmix": 0,
    "mix": 5,
    "music": 5
  },
  "increase": {
    "post": false,
    "like": false,
    "allmix": false,
    "mix": false,
    "music": false
  },
  "start_time": "",
  "end_time": "",
  "filter": {
    "sort_by": "play_count",
    "reverse": true,
    "limit": 0
  }
}
```

#### Response Schema (`TaskResponse`)
```json
{
  "success": true,
  "task_id": "8f3b23e1-95cd-4b72-bb2d-7848f10b7ea1",
  "status": "PENDING",
  "message": "Download task queued successfully.",
  "created_at": "2026-10-06T04:00:00Z"
}
```

---

### Endpoint 3: Task Status & Detailed Inspection
`GET /api/tasks/{task_id}`

Retrieves task progress, real-time download speed, worker thread allocation, and completed items.

#### Response Schema (`TaskDetailResponse`)
```json
{
  "task_id": "8f3b23e1-95cd-4b72-bb2d-7848f10b7ea1",
  "status": "DOWNLOADING",
  "progress_percentage": 45.2,
  "metrics": {
    "total_items": 10,
    "completed_items": 4,
    "failed_items": 0,
    "total_files": 30,
    "completed_files": 14,
    "failed_files": 0,
    "downloaded_bytes": 145892100,
    "total_bytes": 322400000,
    "speed_bytes_sec": 5242880,
    "speed_human": "5.0 MB/s",
    "eta_seconds": 33
  },
  "current_item": "000028400likes_2026-03-15 14.30.22_Amazing scenery",
  "threads": [
    {
      "thread_id": 1,
      "status": "DOWNLOADING",
      "target_file": "000028400likes_..._video.mp4",
      "file_type": "video",
      "downloaded_bytes": 12582912,
      "total_bytes": 25165824,
      "percentage": 50.0
    },
    {
      "thread_id": 2,
      "status": "DOWNLOADING",
      "target_file": "000028400likes_..._cover.jpeg",
      "file_type": "cover",
      "downloaded_bytes": 352100,
      "total_bytes": 352100,
      "percentage": 100.0
    },
    {
      "thread_id": 3,
      "status": "IDLE",
      "target_file": null,
      "file_type": null,
      "downloaded_bytes": 0,
      "total_bytes": 0,
      "percentage": 0.0
    }
  ],
  "logs": [
    { "timestamp": "2026-10-06T04:00:01Z", "level": "INFO", "message": "Link resolved: aweme 7488893440932039970" },
    { "timestamp": "2026-10-06T04:00:03Z", "level": "INFO", "message": "Starting download of 10 items using 5 threads" }
  ],
  "error": null,
  "created_at": "2026-10-06T04:00:00Z",
  "started_at": "2026-10-06T04:00:01Z",
  "completed_at": null
}
```

---

### Endpoint 4: Task Listing
`GET /api/tasks`

Query parameters:
- `status`: Optional filter (`PENDING`, `PARSING`, `DOWNLOADING`, `COMPLETED`, `FAILED`, `CANCELLED`)
- `limit`: Default 20
- `offset`: Default 0

#### Response Schema (`TaskListResponse`)
```json
{
  "total": 3,
  "tasks": [
    {
      "task_id": "8f3b23e1-95cd-4b72-bb2d-7848f10b7ea1",
      "title": "Traveler_Zhang (10 posts)",
      "status": "DOWNLOADING",
      "progress_percentage": 45.2,
      "total_items": 10,
      "completed_items": 4,
      "speed_human": "5.0 MB/s",
      "created_at": "2026-10-06T04:00:00Z"
    }
  ]
}
```

---

### Endpoint 5: Task Cancellation
`POST /api/tasks/{task_id}/cancel`

Signals background workers to halt downloading and sets task status to `CANCELLED`.

#### Response Schema
```json
{
  "success": true,
  "task_id": "8f3b23e1-95cd-4b72-bb2d-7848f10b7ea1",
  "status": "CANCELLED",
  "message": "Task cancellation initiated."
}
```

---

### Endpoint 6: Real-time Streaming (SSE)
`GET /api/stream` or `GET /api/tasks/{task_id}/stream`

Server-Sent Events endpoint broadcasting live telemetry updates to the frontend without polling.

#### Stream Protocol Headers
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

#### Event Frames
```text
event: task_progress
data: {"task_id":"8f3b23e1...","progress":45.2,"speed_human":"5.0 MB/s","completed_items":4,"total_items":10}

event: thread_state
data: {"task_id":"8f3b23e1...","threads":[{"thread_id":1,"status":"DOWNLOADING","percentage":50.0}]}

event: task_log
data: {"task_id":"8f3b23e1...","timestamp":"2026-10-06T04:00:10Z","message":"Saved video: ..._video.mp4"}

event: task_complete
data: {"task_id":"8f3b23e1...","status":"COMPLETED","total_downloaded_bytes":322400000}
```

---

### Endpoint 7: Settings Management
`GET /api/settings` and `POST /api/settings`

Reads and persists application configuration in `config.yaml`. Upon update, modifications immediately apply to the runtime client and headers (`douyin_headers["Cookie"]`).

#### Schema (`SettingsModel`)
```json
{
  "path": "./Downloaded/",
  "thread": 10,
  "music": false,
  "cover": false,
  "avatar": false,
  "json": false,
  "folderstyle": true,
  "database": true,
  "mode": ["post"],
  "number": {
    "post": 0,
    "like": 0,
    "allmix": 0,
    "mix": 5,
    "music": 5
  },
  "increase": {
    "post": false,
    "like": false,
    "allmix": false,
    "mix": false,
    "music": false
  },
  "filter": {
    "sort_by": "play_count",
    "reverse": true,
    "limit": 0
  },
  "cookies": {
    "msToken": "...",
    "ttwid": "...",
    "odin_tt": "...",
    "passport_csrf_token": "...",
    "sid_guard": "..."
  },
  "cookie": ""
}
```

---

### Endpoint 8: Media Library Listing
`GET /api/media`

Scans `./Downloaded/` (or configured path) and presents an indexed media catalog for browsing.

#### Query Parameters
- `subfolder`: Optional path relative to root
- `type`: Optional filter (`video`, `audio`, `image`, `json`, `directory`, `all`)
- `search`: Search query string
- `sort_by`: `name`, `date`, `size` (default `date`)
- `order`: `asc` or `desc` (default `desc`)
- `page`: int (default 1)
- `page_size`: int (default 50)

#### Response Schema (`MediaListResponse`)
```json
{
  "total": 24,
  "current_path": "",
  "items": [
    {
      "id": "dXNlcl9UcmF2ZWxlcl9aaGFuZw==",
      "name": "user_Traveler_Zhang_MS4wLjABAAAA...",
      "relative_path": "user_Traveler_Zhang_MS4wLjABAAAA...",
      "type": "directory",
      "size_bytes": 0,
      "size_human": "-",
      "item_count": 12,
      "modified_at": "2026-10-06T04:02:10Z"
    },
    {
      "id": "MDAwMDI4NDAwbGlrZXNfdmlkZW8ubXA0",
      "name": "000028400likes_2026-03-15 14.30.22_Scenery_video.mp4",
      "relative_path": "user_.../post/000028400likes_..._video.mp4",
      "type": "video",
      "size_bytes": 28419200,
      "size_human": "27.1 MB",
      "thumbnail_url": "/api/media/stream/user_.../cover.jpeg",
      "stream_url": "/api/media/stream/user_.../000028400likes_..._video.mp4",
      "download_url": "/api/media/download/user_.../000028400likes_..._video.mp4",
      "modified_at": "2026-10-06T04:01:45Z"
    }
  ]
}
```

---

### Endpoint 9: Media Streaming (HTTP Range Support)
`GET /api/media/stream/{file_path:path}`

Streams media files directly to the browser. Crucially supports `HTTP 206 Partial Content` with `Range: bytes=start-end` headers to enable instant video seeking, scrubbing, and audio playback in HTML5 players (`<video controls>` and `<audio controls>`).

#### Security Constraint
Strict path traversal prevention:
`resolved_path = (ROOT_DIR / file_path).resolve()`
Must satisfy: `resolved_path.is_relative_to(ROOT_DIR.resolve())`. If not, raises `403 Forbidden`.

---

### Endpoint 10: Trigger Native Windows Explorer
`POST /api/open-folder`

Invokes Windows Explorer to reveal the download root directory or highlight a specific downloaded file.

#### Request Schema (`OpenFolderRequest`)
```json
{
  "path": "optional relative subfolder or file path"
}
```

#### Response Schema (`OpenFolderResponse`)
```json
{
  "success": true,
  "opened_path": "C:\\Users\\ddat2\\Downloads\\Projects\\douyin-download\\Downloaded\\user_Zhang",
  "message": "Opened directory in File Explorer."
}
```

#### OS Execution Semantics
- On Windows:
  - If target is a directory: `os.startfile(folder_path)`
  - If target is a file: `subprocess.Popen(['explorer.exe', '/select,', str(file_path)])`
- Cross-platform fallbacks:
  - macOS: `subprocess.Popen(['open', str(path)])`
  - Linux: `subprocess.Popen(['xdg-open', str(path)])`

---

## Task Lifecycle State Machine

```
              ┌───────────────┐
              │     IDLE      │
              └───────┬───────┘
                      │ POST /api/download
                      ▼
              ┌───────────────┐
       ┌─────▶│    PENDING    │
       │      └───────┬───────┘
       │              │ Worker dequeues
       │              ▼
       │      ┌───────────────┐
Cancel │      │    PARSING    │───────────────┐
       │      └───────┬───────┘               │
       │              │ Resolved & Items      │ Upstream Error /
       │              │ Queued                │ Empty Response
       │              ▼                       │
       │      ┌───────────────┐               │
       │      │  DOWNLOADING  │────────┐      │
       │      └───────┬───────┘        │      │
       │              │ All tasks      │ Fail │
       │              │ finished       │      │
       │              ▼                ▼      ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│  CANCELLED   ││  COMPLETED   ││    FAILED    │
└──────────────┘└──────────────┘└──────────────┘
```

### State Definitions
1. `IDLE`: Initial state before task submission.
2. `PENDING`: Task accepted by API, placed in background queue awaiting execution.
3. `PARSING`: Resolving short URLs, extracting Douyin IDs, and querying upstream APIs for item lists.
4. `DOWNLOADING`: Media files actively downloading via worker pool with chunked streaming and resume.
5. `COMPLETED`: All queued items and media files successfully downloaded (or existing files verified).
6. `FAILED`: Fatal error encountered (network unavailable, auth failure, upstream ban).
7. `CANCELLED`: Interrupted by user cancellation request via `/api/tasks/{task_id}/cancel`.

---

## Complete Pydantic Models Specification

```python
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class KeyType(str, Enum):
    AWEME = "aweme"
    USER = "user"
    MIX = "mix"
    MUSIC = "music"
    LIVE = "live"


class ContentType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    USER = "user"
    MIX = "mix"
    MUSIC = "music"
    LIVE = "live"


class TaskStatus(str, Enum):
    IDLE = "IDLE"
    PENDING = "PENDING"
    PARSING = "PARSING"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# --- Link Parsing & Preview ---

class ParseRequest(BaseModel):
    url: str = Field(..., description="Douyin share link or URL string")
    cookie: Optional[str] = Field(None, description="Optional cookie override")


class AuthorPreview(BaseModel):
    nickname: str
    sec_uid: str
    uid: Optional[str] = None
    avatar_url: Optional[str] = None
    signature: Optional[str] = None
    follower_count: Optional[int] = None
    total_favorited: Optional[int] = None


class StatisticsData(BaseModel):
    digg_count: int = 0
    play_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    collect_count: int = 0


class ContentPreview(BaseModel):
    title: str
    cover_url: Optional[str] = None
    dynamic_cover_url: Optional[str] = None
    create_time: Optional[str] = None
    author: AuthorPreview
    statistics: Optional[StatisticsData] = None
    estimated_work_count: int = 1
    available_modes: List[str] = Field(default_factory=lambda: ["post"])
    has_video: bool = True
    has_images: bool = False
    has_music: bool = False


class ParseResponse(BaseModel):
    success: bool = True
    url: str
    canonical_url: str
    key_type: KeyType
    key: str
    content_type: ContentType
    preview: ContentPreview


# --- Download Task Management ---

class AssetOptions(BaseModel):
    video: bool = True
    music: bool = False
    cover: bool = True
    avatar: bool = True
    json: bool = True


class FilterOptions(BaseModel):
    sort_by: Optional[str] = Field(
        None, description="play_count, digg_count, comment_count, share_count, create_time"
    )
    reverse: bool = True
    limit: int = 0


class DownloadRequest(BaseModel):
    url: str
    key_type: Optional[KeyType] = None
    key: Optional[str] = None
    download_dir: Optional[str] = "./Downloaded/"
    thread: int = Field(default=5, ge=1, le=32)
    assets: AssetOptions = Field(default_factory=AssetOptions)
    folderstyle: bool = True
    mode: List[str] = Field(default_factory=lambda: ["post"])
    number: Dict[str, int] = Field(
        default_factory=lambda: {
            "post": 0, "like": 0, "allmix": 0, "mix": 5, "music": 5
        }
    )
    increase: Dict[str, bool] = Field(
        default_factory=lambda: {
            "post": False, "like": False, "allmix": False, "mix": False, "music": False
        }
    )
    start_time: Optional[str] = ""
    end_time: Optional[str] = ""
    filter: FilterOptions = Field(default_factory=FilterOptions)


class TaskResponse(BaseModel):
    success: bool = True
    task_id: str
    status: TaskStatus
    message: str
    created_at: str


class ThreadStateModel(BaseModel):
    thread_id: int
    status: str  # IDLE, DOWNLOADING, RETRYING, COMPLETED, FAILED
    target_file: Optional[str] = None
    file_type: Optional[str] = None  # video, image, music, cover, avatar
    downloaded_bytes: int = 0
    total_bytes: int = 0
    percentage: float = 0.0


class TaskMetricsModel(BaseModel):
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_bytes_sec: float = 0.0
    speed_human: str = "0 B/s"
    eta_seconds: Optional[int] = None


class TaskLogModel(BaseModel):
    timestamp: str
    level: str
    message: str


class TaskDetailResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress_percentage: float
    metrics: TaskMetricsModel
    current_item: Optional[str] = None
    threads: List[ThreadStateModel] = Field(default_factory=list)
    logs: List[TaskLogModel] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskSummaryItem(BaseModel):
    task_id: str
    title: str
    status: TaskStatus
    progress_percentage: float
    total_items: int
    completed_items: int
    speed_human: str
    created_at: str


class TaskListResponse(BaseModel):
    total: int
    tasks: List[TaskSummaryItem]


# --- Settings ---

class SettingsModel(BaseModel):
    path: str = "./Downloaded/"
    thread: int = Field(default=5, ge=1, le=32)
    music: bool = False
    cover: bool = False
    avatar: bool = False
    json: bool = False
    folderstyle: bool = True
    database: bool = True
    mode: List[str] = Field(default_factory=lambda: ["post"])
    number: Dict[str, int] = Field(default_factory=dict)
    increase: Dict[str, bool] = Field(default_factory=dict)
    filter: Dict[str, Any] = Field(default_factory=dict)
    cookies: Optional[Dict[str, str]] = None
    cookie: Optional[str] = None


# --- Media Library ---

class MediaItemType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    JSON = "json"
    DIRECTORY = "directory"


class MediaItem(BaseModel):
    id: str
    name: str
    relative_path: str
    type: MediaItemType
    size_bytes: int
    size_human: str
    item_count: Optional[int] = None
    thumbnail_url: Optional[str] = None
    stream_url: Optional[str] = None
    download_url: Optional[str] = None
    modified_at: str


class MediaListResponse(BaseModel):
    total: int
    current_path: str
    items: List[MediaItem]


# --- OS Integration ---

class OpenFolderRequest(BaseModel):
    path: Optional[str] = Field(None, description="Optional subpath or file path")


class OpenFolderResponse(BaseModel):
    success: bool
    opened_path: str
    message: str


# --- Error Response Contract ---

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    timestamp: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
```

---

## Error Handling Contracts & HTTP Status Code Matrix

| Status Code | Code String | Condition | Standard Response Payload |
|-------------|-------------|-----------|---------------------------|
| **400 Bad Request** | `INVALID_URL` | User provided empty string or text without HTTP links. | `{"error":{"code":"INVALID_URL","message":"No valid URL found in input string.","timestamp":"..."}}` |
| **400 Bad Request** | `INVALID_PATH` | Download path or target folder does not exist or is invalid. | `{"error":{"code":"INVALID_PATH","message":"Path does not exist.","timestamp":"..."}}` |
| **403 Forbidden** | `PATH_TRAVERSAL` | Attempt to access, stream, or open files outside `./Downloaded/`. | `{"error":{"code":"PATH_TRAVERSAL","message":"Access to path outside download root is forbidden.","timestamp":"..."}}` |
| **404 Not Found** | `TASK_NOT_FOUND` | Specified `task_id` does not exist in memory or storage. | `{"error":{"code":"TASK_NOT_FOUND","message":"Task ID not found.","timestamp":"..."}}` |
| **404 Not Found** | `FILE_NOT_FOUND` | Target video/audio file does not exist on disk. | `{"error":{"code":"FILE_NOT_FOUND","message":"Requested media file does not exist.","timestamp":"..."}}` |
| **404 Not Found** | `POST_NOT_FOUND` | Douyin post ID was deleted or does not exist. | `{"error":{"code":"POST_NOT_FOUND","message":"Douyin content not found.","timestamp":"..."}}` |
| **409 Conflict** | `TASK_ALREADY_FINISHED` | Attempted to cancel a task that is already completed or failed. | `{"error":{"code":"TASK_ALREADY_FINISHED","message":"Task is not active.","timestamp":"..."}}` |
| **416 Range Not Satisfiable** | `INVALID_RANGE` | Byte range in `Range` header exceeds total media file length. | `{"error":{"code":"INVALID_RANGE","message":"Requested byte range exceeds file size.","timestamp":"..."}}` |
| **422 Unprocessable** | `VALIDATION_ERROR` | Request payload fails Pydantic type, range, or regex constraints. | Standard FastAPI 422 JSON validation error details |
| **500 Internal Error** | `SERVER_ERROR` | Unhandled runtime exception inside FastAPI or OS subsystem. | `{"error":{"code":"SERVER_ERROR","message":"Internal server error.","timestamp":"..."}}` |
| **502 Bad Gateway** | `UPSTREAM_API_ERROR` | Upstream Douyin API returned status error, anti-scraping block, or empty text. | `{"error":{"code":"UPSTREAM_API_ERROR","message":"Douyin upstream API rejected request or returned empty response.","timestamp":"..."}}` |
| **504 Gateway Timeout** | `UPSTREAM_TIMEOUT` | Upstream Douyin request exceeded timeout (default 60s). | `{"error":{"code":"UPSTREAM_TIMEOUT","message":"Upstream Douyin API timed out.","timestamp":"..."}}` |

---

## Architectural Seams & Integration Points

1. **Non-blocking Task Manager (`src/web/task_manager.py`)**:
   - `TaskManager` runs as a singleton service in the FastAPI app lifespan.
   - It maintains an internal `dict[str, TaskState]` and executes downloads via an `asyncio.to_thread` / dedicated thread pool worker.
   - Emits progress events to an asynchronous event bus (`asyncio.Queue` per client connection).

2. **Downloader Observer / Progress Callback Hook (`src/douyin/download.py`)**:
   - The existing `Download` class relies on terminal `tqdm`.
   - Add an optional `progress_callback(item_idx, total_items, file_desc, bytes_downloaded, total_bytes, thread_id)` parameter to `awemeDownload`, `userDownload`, and `download_with_resume`.
   - If callback is `None`, falls back cleanly to existing `tqdm` console output (preserves CLI compatibility).

3. **In-Memory Configuration & Cookie Hot Reloading (`src/web/config_service.py`)**:
   - When `POST /api/settings` writes to `config.yaml`, it calls:
     ```python
     douyin_headers["Cookie"] = new_cookie_str
     ```
   - In-memory `DouyinApi` instances and sessions immediately inherit the new cookies without restarting the server.

4. **Static File Serving for React Single Page Application**:
   - FastAPI mounts static build directory: `app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")`.
   - HTML5 history mode fallback: any unmatched route returns `frontend/dist/index.html`.

5. **Windows Explorer Subprocess Wrapper**:
   - Native execution:
     ```python
     if sys.platform == "win32":
         import os, subprocess
         if file_path.is_file():
             subprocess.Popen(["explorer.exe", f"/select,{file_path}"])
         else:
             os.startfile(folder_path)
     ```
