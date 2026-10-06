# Original User Request

## 2026-10-06T03:48:34Z

Build a modern web application for Douyin video downloader, converting the existing CLI workflow into a FastAPI backend with multithreaded downloads and a responsive React frontend adopting the warm editorial aesthetic of pyvideotrans.

Working directory: c:\Users\ddat2\Downloads\Projects\douyin-download
Integrity mode: development

Reference design & color system: `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\src\index.css` (warm ivory surface `#FAF8F5`, terracotta/amber primary `#8D4B00`, neutral container `#F3ECE2`, fonts Plus Jakarta Sans and JetBrains Mono).

## Requirements

### R1. FastAPI Backend Service & Threaded Downloader
- Expose RESTful API endpoints and real-time streaming (SSE/WebSocket) for parsing links, managing download tasks, and querying system state.
- Retain the existing multi-threaded download engine (`Download` and `DouyinApi` in `src/douyin/`), preserving concurrent worker pools, resume/range requests, and retry mechanics.
- Support link resolution for all Douyin key types: single video (`aweme`), user profiles (`user` posts/likes), collections (`mix`), music (`music`), and livestreams (`live`).
- Allow dynamic control over download threads and selective downloading of media assets (video, audio, cover image, author avatar, and metadata JSON).

### R2. Modern React Frontend (pyvideotrans Style)
- Responsive Single-Page Application built with React 19, TypeScript, Vite, and Tailwind CSS.
- Color palette and aesthetic inspired by `pyvideotrans`: warm ivory background (`#FAF8F5`), amber/terracotta accent (`#8D4B00`), subtle borders, rounded containers, and modern typography.
- Two-step download interaction flow:
  1. Link Preview: User inputs link -> system previews content (author avatar/nickname, video title, cover thumbnail, estimated work count).
  2. Configuration & Download: User selects modes (post/like/mix), toggles asset types, configures filters (sort by play_count/digg_count/create_time), specifies thread count, and initiates download.
- Real-time progress tracker displaying overall progress, active thread tasks, download speed, and item completion status.

### R3. Storage & Media Library
- Persist downloaded media to a configurable directory (default `./Downloaded/`) honoring folder organization hierarchy (`folderstyle`).
- Interactive Media Library page/drawer to view downloaded files, preview video/audio playback directly in the browser, and download individual files locally.
- Action to open the download directory directly in Windows File Explorer via backend integration.

### R4. Settings & Cookie Management
- Settings interface to configure Douyin cookies (raw string or key-value dictionary), default download path, thread count, and asset preferences.
- Save and load settings reliably from `config.yaml` without corrupting file structure.

## Acceptance Criteria

### Backend & Concurrency
- [ ] FastAPI backend starts without error (`uvicorn main_web:app` or dedicated launcher script) on `http://127.0.0.1:8000` (or configurable port).
- [ ] API endpoints for URL parsing (`/api/parse`), starting download tasks (`/api/download`), task progress monitoring (`/api/tasks/{task_id}` or SSE/WS stream), settings management (`/api/settings`), and media library (`/api/media`) return proper JSON and status codes.
- [ ] Multi-threaded concurrent download engine executes downloads without blocking the FastAPI event loop.
- [ ] System handles single video, user profiles, and collection links, correctly saving files to disk.

### Frontend UI & User Experience
- [ ] Vite frontend builds cleanly with zero TypeScript or styling errors.
- [ ] Warm editorial styling matching `pyvideotrans` palette (`#FAF8F5`, `#8D4B00`, `#F3ECE2`) is applied consistently across all screens, inputs, badges, and modals.
- [ ] Two-step workflow works end-to-end: inputting a link generates a preview card before downloading.
- [ ] Real-time progress bars and status indicators accurately update as downloads progress.
- [ ] Media Library accurately lists downloaded items and supports in-browser playback/inspection.
- [ ] Settings modal successfully loads current `config.yaml` values, saves modifications, and applies new cookies/paths immediately.

### Production & Integration
- [ ] FastAPI backend serves the production-built React static files so the entire web app can be launched with a single command (e.g. `python webui.py`).
- [ ] Unit/integration tests verify API endpoints, config parsing, and job execution pipeline.
