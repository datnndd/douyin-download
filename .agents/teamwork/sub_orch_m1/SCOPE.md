# Scope: Milestone 1 — Backend Engine & Task Concurrency

## Architecture
- Module: `src/web/core/` and `src/web/services/`
- Adapter around existing CLI engine (`src/douyin/douyinapi.py` and `src/douyin/download.py`).
- Non-blocking asynchronous service (`DouyinService`) with thread-pool offloading via `asyncio.to_thread`.
- `TaskManager` managing asynchronous background download jobs with unique UUIDs, thread-safe state tracking, and cancellation tokens (`threading.Event`).
- Progress listener hooks in `Download` (`src/douyin/download.py`) emitting throttled (250ms) `DownloadProgressEvent` pushed to `asyncio.Queue` subscribers for SSE streaming.
- Preserves all 5 URL types: single video (`aweme`), user profiles (`user` posts/likes/mixes), collections (`mix`), music (`music`), and livestreams (`live`).
- Enforces storage hierarchy (`folderstyle`) and like-count renaming (`_rename_if_exists`).
- Preserves HTTP Range resumption (`206 Partial Content`) and exponential backoff retry mechanics.
- Updates `requirements.txt` with required web dependencies (`fastapi`, `uvicorn`, `pydantic`, `pyyaml`).

## Feature Inventory Scope
- Feature 1: Single Aweme URL Resolution
- Feature 2: User Profile URL Resolution
- Feature 3: Mix / Collection URL Resolution
- Feature 4: Music URL Resolution
- Feature 5: Livestream Room Resolution
- Feature 7: Download Task Creation
- Feature 8: Task State Machine & Inspection
- Feature 10: Task Cancellation Lifecycle
- Feature 13: Selective Asset Downloading (video, music, cover, avatar, json)
- Feature 14: Multi-Mode User Scraping (post, like, mix)
- Feature 15: Work Limits & Pagination
- Feature 16: Metric Sorting & Filtering (sort by play/digg/comment/create_time)
- Feature 17: Incremental Updates (SQLite WAL deduplication)
- Feature 18: Directory Organization (`folderstyle` true/false)
- Feature 19: Dynamic File Renaming (`_rename_if_exists`)
- Feature 20: Resumable Downloads & Retry

## Interface Contracts
- See `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\orchestrator_1\PROJECT.md` § Interface Contracts.
- Models defined in `src/web/core/schemas.py`: `ParseRequest`, `ParseResponse`, `DownloadRequest`, `TaskResponse`, `TaskDetailResponse`, `DownloadProgressEvent`, `SettingsModel`.

## Code Layout Ownership
- `requirements.txt`
- `src/web/__init__.py`
- `src/web/core/__init__.py`
- `src/web/core/config.py`
- `src/web/core/schemas.py`
- `src/web/services/__init__.py`
- `src/web/services/douyin_service.py`
- `src/web/services/task_manager.py`
- `src/douyin/download.py` (non-breaking progress callback hooks)
