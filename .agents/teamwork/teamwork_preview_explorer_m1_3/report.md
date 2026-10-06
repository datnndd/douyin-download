# M1 Technical Report: Task Manager & Concurrency Architecture

**Author**: M1 Explorer 3 (Task Manager & Concurrency)  
**Date**: 2026-10-06  
**Target Milestone**: Milestone 1 (Backend Engine & Task Concurrency)  
**Artifacts Produced**:
- `proposed_task_manager.py`: Complete reference implementation of `src/web/services/task_manager.py`
- `download_progress_cancel.patch`: Git patch for non-breaking hooks and cancellation in `src/douyin/download.py`

---

## 1. Executive Summary

The Douyin Web Downloader transitions the existing Python CLI tool into a modern web application powered by FastAPI, Server-Sent Events (SSE), and a React 19 frontend. The original download engine (`src/douyin/download.py`) was engineered purely for synchronous CLI execution with `tqdm` console bars and nested thread pools.

To adapt this engine into a web backend without blocking the `asyncio` event loop or destabilizing the server, this investigation establishes:
1. **A Centralized, Bounded `TaskManager`**: Manages background download jobs through a bounded `ThreadPoolExecutor` to eliminate thread explosion.
2. **A Thread-Safe Asyncio SSE Telemetry Bridge**: Connects worker thread progress to FastAPI's async SSE event streams via `loop.call_soon_threadsafe` and subscriber queues (`asyncio.Queue`).
3. **Non-Breaking Progress Hooks with ~250ms Throttling**: Adds optional callback hooks to `Download` that compress high-frequency network chunks (~1,500/sec) into 4 updates/sec, preventing event loop congestion and browser DOM freeze.
4. **Responsive Cancellation Tokens (`threading.Event`)**: Enables instantaneous abort of network streaming, disk writes, and exponential backoff retry waits.
5. **A Granular Thread States Visualizer**: Maps active worker threads into discrete telemetry slots for real-time UI tracking.

All designs were validated through automated execution against Python 3.11/3.13 in the project's virtual environment (`.venv`), confirming 100% test pass rate for concurrency, throttling, and cancellation.

---

## 2. Codebase Audit & Architectural Challenges

### 2.1 The Nested ThreadPool Problem in CLI Engine
In `src/douyin/download.py`:
- `userDownload()` spawns a `ThreadPoolExecutor(max_workers=min(self.thread, total_count))`.
- For each video item, `awemeDownload()` calls `_download_media_files_threaded()`.
- Inside `_download_media_files_threaded()`, a **second nested** `ThreadPoolExecutor(max_workers=self.thread)` is spawned to download video, audio, cover, and avatar assets concurrently.

**The Risk**: If 4 user download tasks are launched concurrently with `thread=5`, the server would attempt to spawn up to $4 \times 5 \times 5 = 100$ concurrent OS threads. On Windows, this leads to thread context-switching thrashing, socket pool exhaustion, Akamai/Douyin rate-limiting, and severe GIL contention.

**The Solution**:
- Introduce a centralized `TaskManager` possessing a managed, bounded thread pool (`max_total_workers=16`, `max_concurrent_tasks=4`).
- Tasks share or acquire bounded execution slots.
- Per-task concurrency is capped (`req.thread_count` clamped to range $1 \le N \le 16$).

### 2.2 Bridging OS Worker Threads to Asyncio Event Loop
FastAPI runs on a single-threaded `asyncio` event loop. Worker threads in `ThreadPoolExecutor` run in OS threads.
- **Critical Pitfall**: Calling `queue.put_nowait(event)` directly on an `asyncio.Queue` from an OS worker thread is **not thread-safe** and corrupts `asyncio` internal linked lists or fails to wake up waiting coroutines.
- **The Solution**: Telemetry events dispatched from worker threads are routed through `loop.call_soon_threadsafe(_push, queue, event)`.

### 2.3 Event Loop Flooding (High-Throughput Chunk Storms)
Douyin media files (10MB–100MB) are streamed via `requests.iter_content(chunk_size=8192)`.
- At 100 Mbps download speed, a single file processes ~1,525 chunks/second.
- With 5 active workers, this yields over **7,600 chunk events per second**.
- Emitting every chunk to an `asyncio.Queue` and pushing over SSE would freeze the browser UI and overload FastAPI.
- **The Solution**: Implement a dual-trigger throttle:
  - High-frequency chunk transfers are throttled to a minimum interval of **250ms** ($\approx 4\text{ Hz}$).
  - Lifecycle state changes, item completions, and errors **bypass the throttle** and force-emit immediately.

---

## 3. Job Lifecycle State Machine

The task lifecycle adheres to the following states:

```
                  ┌──────────────┐
                  │   PENDING    │
                  └──────┬───────┘
                         │ (worker picked up)
                         ▼
                  ┌──────────────┐
       ┌──────────┤   PARSING    ├──────────┐
       │          └──────┬───────┘          │
       │                 │ (links resolved) │
       │                 ▼                  │
       │          ┌──────────────┐          │
       │   ┌──────┤ DOWNLOADING  ├──────┐   │
       │   │      └──────┬───▲───┘      │   │
       │   │ (pause)     │   │ (resume) │   │
       │   │             ▼   │          │   │
       │   │      ┌──────────┴───┐      │   │
       │   │      │    PAUSED    │      │   │
       │   │      └──────────────┘      │   │
(cancel│   │(complete)   │(fail)        │   │ (cancel)
   or  │   │             │              │   │
 error)│   ▼             ▼              │   │
       │ ┌──────────┐  ┌────────┐       │   │
       │ │COMPLETED │  │ FAILED │       │   │
       │ └──────────┘  └────────┘       │   │
       │                                │   │
       └──────────────► ◄───────────────┘   │
                       │                    │
                       ▼                    │
                ┌─────────────┐             │
                │  CANCELLED  │◄────────────┘
                └─────────────┘
```

### Transition Specifications:
1. `PENDING`: Task record created, UUID assigned, enqueued in executor.
2. `PARSING`: Background thread resolving URL, short links, and querying Douyin API pagination.
3. `DOWNLOADING`: Media files actively transferring to disk.
4. `PAUSED`: User paused task; worker threads wait on `threading.Event.wait()`.
5. `COMPLETED` *(terminal)*: All media downloaded and saved successfully.
6. `FAILED` *(terminal)*: Fatal exception encountered (e.g., deleted video, network outage).
7. `CANCELLED` *(terminal)*: User requested cancellation; aborted cleanly.

> **Note on `schemas.py`**: `TaskStatus` in `src/web/core/schemas.py` should explicitly declare `PARSING = "PARSING"`. The reference `proposed_task_manager.py` implements backward-compatible fallback: `getattr(TaskStatus, "PARSING", getattr(TaskStatus, "RUNNING", TaskStatus.DOWNLOADING))`.

---

## 4. Telemetry & Progress Event Specification

### 4.1 Schema Layout
The telemetry model `DownloadProgressEvent` broadcast to SSE subscribers (`GET /api/stream` and `/api/tasks/{task_id}/stream`) matches the contract in `PROJECT.md`:

```python
class ThreadStatus(BaseModel):
    thread_id: int          # Worker slot 1..N
    status: str             # "IDLE" | "DOWNLOADING" | "COMPLETED" | "FAILED"
    current_file: str       # E.g. "7488893440932039970_video.mp4"
    pct: float              # 0.0 to 100.0
    speed_bps: float        # Worker speed in bytes/sec

class DownloadProgressEvent(BaseModel):
    task_id: str
    status: TaskStatus
    progress_pct: float     # 0.0 to 100.0
    speed_bps: float        # Aggregate smoothed download speed
    downloaded_bytes: int
    total_bytes: int
    item_index: int         # Current item index (1..total)
    item_total: int         # Total items in batch
    item_title: str
    active_threads: int
    threads: List[ThreadStatus]
    event_type: str = "task_progress"
    timestamp: datetime
```

### 4.2 Smooth Throughput Calculation (EMA)
To prevent erratic speed readings on the UI, throughput is calculated using Exponential Moving Average (EMA) with $\alpha = 0.35$:
$$\text{instant\_speed} = \frac{\Delta \text{bytes}}{\Delta t}$$
$$\text{speed\_bps} = 0.35 \times \text{instant\_speed} + 0.65 \times \text{previous\_speed}$$
Updates occur at minimum intervals of 400ms to eliminate division by near-zero time deltas.

---

## 5. Non-Breaking Enhancements to `src/douyin/download.py`

### 5.1 Backward-Compatible Hook Signatures
All additions use optional keyword arguments defaulting to `None`, preserving 100% compatibility with existing CLI callers (`douyinCommand.py`):

```python
class Download(object):
    def __init__(
        self,
        thread: int = 5,
        music: bool = True,
        cover: bool = True,
        avatar: bool = True,
        resjson: bool = True,
        folderstyle: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ):
        ...
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event
```

### 5.2 Responsive Cancellation Loops
Cancellation checks are placed at critical checkpoints:
1. **Before network connection**: Aborts before initiating HTTP handshake.
2. **Inside chunk streaming loop**:
   ```python
   for chunk in response.iter_content(chunk_size=self.chunk_size):
       if eff_cancel and eff_cancel.is_set():
           logger.info(f"Download cancelled during stream: {desc}")
           return False
       if chunk:
           size = f.write(chunk)
           ...
   ```
3. **During exponential backoff retries**: Instead of blocking `time.sleep(wait_time)`, use:
   ```python
   if eff_cancel:
       if eff_cancel.wait(wait_time):
           logger.info(f"Download cancelled during retry wait: {desc}")
           return False
   else:
       time.sleep(wait_time)
   ```
   *Impact*: If a task is retrying with a 10-second backoff, setting `cancel_event` immediately awakens the thread and terminates without waiting.
4. **Across batch items (`userDownload`)**:
   ```python
   for future in as_completed(future_to_aweme):
       if eff_cancel and eff_cancel.is_set():
           break
   ```

---

## 6. Verification & Automated Test Proof

The reference implementation was verified through automated execution in the project `.venv`:

| Test Case | Description | Result |
|-----------|-------------|--------|
| **Compilation** | `py_compile` on `proposed_task_manager.py` | **PASSED** (exit 0) |
| **Task Lifecycle** | Submit task -> Check PENDING -> Cancel -> Check CANCELLED | **PASSED** (exit 0) |
| **Worker Visualizer** | Verify allocation of 4 discrete `ThreadStatus` slots | **PASSED** (exit 0) |
| **Async SSE Pub/Sub** | Connect `asyncio.Queue` -> Receive `task_progress` event -> Receive `CANCELLED` event | **PASSED** (exit 0) |
| **Throttle Protection** | Fire 50 rapid chunk events in 10ms -> Verify $\le 2$ SSE events emitted | **PASSED** (1 event emitted) |
| **Force-Emit Bypass** | Fire `file_complete` event -> Verify immediate emission and 100% slot completion | **PASSED** (exit 0) |

---

## 7. Next Steps for Milestone Implementers

1. **Schema Finalization (`src/web/core/schemas.py`)**:
   Ensure `TaskStatus` includes `PARSING = "PARSING"`.
2. **Apply Patch to `src/douyin/download.py`**:
   Apply `download_progress_cancel.patch` to integrate callback and cancel token hooks into `Download`.
3. **Place `task_manager.py`**:
   Move `proposed_task_manager.py` to `src/web/services/task_manager.py`.
4. **FastAPI Lifespan Binding**:
   In `main_web.py`, bind the running event loop on startup:
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       task_manager = TaskManager.get_instance()
       task_manager.set_event_loop(asyncio.get_running_loop())
       yield
       task_manager.shutdown(wait=False)
   ```
5. **SSE Endpoints (`src/web/api/stream.py`)**:
   Implement `GET /api/stream` and `GET /api/tasks/{task_id}/stream` consuming `task_manager.subscribe()`.
