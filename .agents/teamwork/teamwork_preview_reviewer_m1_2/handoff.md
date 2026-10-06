# Milestone 1 Review & Adversarial Challenge Report

**Reviewer:** M1 Reviewer 2 (Task Manager & Concurrency)  
**Roles:** Reviewer, Adversarial Critic  
**Working Directory:** `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_reviewer_m1_2\`  
**Target Files:** `src/web/services/task_manager.py`, `src/douyin/download.py`  
**Date:** 2026-10-06  
**Verdict:** **`REQUEST_CHANGES`**  
**Risk Assessment:** **HIGH**

---

## 1. Observation

1. **Test Suite Execution**:
   - Command: `.venv\Scripts\python.exe -m pytest tests/test_m1_core.py -v`
   - Result: 43 passed in 0.50s.
   - Observation: All unit tests in `tests/test_m1_core.py` pass cleanly. However, in `tests/test_m1_core.py::TestTaskManager::test_progress_hook_throttling_and_force_emit` (line 607), the test manually hardcodes `record.total_bytes = 10000` to pass assertions, rather than testing real pipeline telemetry accumulation.
2. **`TaskRecord.total_bytes` and `progress_pct` Calculation**:
   - File: `src/web/services/task_manager.py`, line 42:
     ```python
     self.total_bytes: int = 0
     ```
   - Lines 447–455:
     ```python
     # 5. Calculate overall progress %
     if record.total_bytes > 0:
         record.progress_pct = min(
             100.0, (record.downloaded_bytes / record.total_bytes) * 100.0
         )
     elif record.total_items > 0:
         record.progress_pct = min(
             100.0, (record.completed_items / record.total_items) * 100.0
         )
     ```
   - Observation: `record.total_bytes` is never updated anywhere in `src/web/services/task_manager.py`. It remains `0` for the lifetime of every task. Consequently, line 447 is never true.
   - Lines 553–571:
     ```python
     downloader.awemeDownload(...)
     with record._lock:
         record.completed_items = 1
     ...
     downloader.userDownload(...)
     with record._lock:
         record.completed_items = len(items)
     ```
   - Observation: `record.completed_items` is initialized to 0 and is only incremented AFTER the download call finishes. Throughout the entire download process, `completed_items` is 0. Thus, `record.progress_pct` evaluates to `0 / total_items * 100.0 = 0.0%` until the entire task finishes and snaps to 100.0%.
3. **Throttled Chunk Byte Accounting & Throughput Corruption**:
   - File: `src/douyin/download.py`, lines 593–610:
     ```python
     size = f.write(chunk)
     pbar.update(size)
     downloaded_so_far += size
     if eff_callback:
         now = time.monotonic()
         if now - last_emit_time >= 0.25: # ~250ms throttle
             eff_callback({
                 "event": "chunk",
                 "worker_id": worker_id,
                 "filepath": str(filepath),
                 "filename": filepath.name,
                 "chunk_bytes": size,
                 "downloaded_bytes": downloaded_so_far,
                 "total_bytes": total_size,
                 "desc": desc,
             })
             last_emit_time = now
     ```
   - File: `src/web/services/task_manager.py`, lines 416–418:
     ```python
     # 1. Update downloaded byte metrics
     if chunk_bytes > 0:
         record.downloaded_bytes += chunk_bytes
     ```
   - Observation: `chunk_bytes` passed by `download.py` is only `size` (the single 8KB chunk written in the current loop iteration), while all chunks written during the 250ms interval are omitted. `task_manager.py` increments `record.downloaded_bytes += chunk_bytes`, resulting in massive byte undercounting (e.g. 160 KB recorded for a 100 MB file). In `TaskRecord.update_speed()` (line 116), `speed_bps` calculates throughput based on this undercounted delta, reporting ~32 KB/s on high-speed downloads. `TaskRecord._file_bytes_map` was declared at line 71 but is completely unused.
4. **Silent Success on Download Failures**:
   - File: `src/web/services/task_manager.py`, lines 553–577:
     ```python
     downloader.awemeDownload(
         awemeDict=aweme_dict,
         savePath=save_out,
         cancel_event=record.cancel_event,
         progress_callback=progress_hook,
     )
     with record._lock:
         record.completed_items = 1
     ...
     # Check if cancelled during download
     if record.cancel_event.is_set():
         self._finish_task(record, TaskStatus.CANCELLED)
     else:
         self._finish_task(record, TaskStatus.COMPLETED)
     ```
   - Observation: `downloader.awemeDownload` returns a boolean indicating whether the download succeeded or failed. The return value is discarded. If `awemeDownload` fails (e.g., all 5 retries fail), the task is unconditionally marked as `TaskStatus.COMPLETED`, `completed_items` is set to 1, and `progress_pct` is set to 100.0%.
5. **Thread Deadlock when Cancelling or Shutting Down a Paused Task**:
   - File: `src/web/services/task_manager.py`, line 410:
     ```python
     # Check pause state (block worker thread if paused)
     record.pause_event.wait()
     ```
   - Lines 271–274 (`cancel_task`):
     ```python
     record.cancel_event.set()
     record.status = TaskStatus.CANCELLED
     record.updated_at = datetime.now(timezone.utc)
     ```
   - Lines 681–684 (`shutdown`):
     ```python
     for task in self._tasks.values():
         task.cancel_event.set()
     self._executor.shutdown(wait=wait)
     ```
   - Observation: Worker threads blocked in `record.pause_event.wait()` are never unblocked by `cancel_task` or `shutdown` because neither function calls `record.pause_event.set()`. Threads remain permanently blocked, leaking workers, and `shutdown(wait=True)` hangs indefinitely.
6. **Unenforced `max_concurrent_tasks` and Thread Explosion**:
   - File: `src/web/services/task_manager.py`, line 146:
     ```python
     self.max_concurrent_tasks: int = max_concurrent_tasks
     ```
   - Observation: `self.max_concurrent_tasks` is never referenced anywhere else in `task_manager.py`. `submit_task` immediately dispatches all submitted tasks into `self._executor.submit()`. When combined with nested thread pools in `userDownload` (`ThreadPoolExecutor(max_workers=min(self.thread, total_count))`) and `awemeDownload` (`ThreadPoolExecutor(max_workers=self.thread)`), 16 concurrent tasks can spawn up to $16 \times 5 \times 5 = 400$ OS threads.
7. **Race Condition Resurrecting Cancelled Tasks to `PARSING`**:
   - File: `src/web/services/task_manager.py`, lines 493–505:
     ```python
     parsing_status = getattr(TaskStatus, "PARSING", TaskStatus.DOWNLOADING)
     with record._lock:
         record.status = parsing_status
         record.updated_at = datetime.now(timezone.utc)
     self._broadcast_event(record.to_progress_event(), task_id=task_id, force=True)

     if record.cancel_event.is_set():
         self._finish_task(record, TaskStatus.CANCELLED)
         return
     ```
   - Observation: If a task was cancelled while in `PENDING` state, `_run_task_pipeline` begins by unconditionally setting `record.status = PARSING` and broadcasting that state before checking `cancel_event.is_set()`. The state transitions `PENDING -> CANCELLED -> PARSING -> CANCELLED`.
8. **Thread Visualizer Worker Slot Collisions**:
   - File: `src/douyin/download.py`, line 244:
     ```python
     for i, task in enumerate(tasks):
         task["worker_id"] = (i % self.thread) + 1
     ```
   - File: `src/web/services/task_manager.py`, lines 420–422:
     ```python
     slot_idx = max(0, min(worker_id - 1, len(record.threads) - 1))
     slot = record.threads[slot_idx]
     ```
   - Observation: When `userDownload` runs multiple videos concurrently, each aweme labels its tasks starting at `worker_id = 1`. Multiple parallel video downloads write to `slot_idx = 0` concurrently, causing visualizer slots to overwrite each other and flicker erratically.
9. **Resume Byte Counter Corruption on HTTP 200 Fallback**:
   - File: `src/douyin/download.py`, lines 550–575:
     If a range request is sent for an existing partial file (`file_size > 0`), but the upstream server returns HTTP 200 (full content), `mode` becomes `"wb"`, but `downloaded_so_far` remains initialized to `file_size` and `tqdm` is initialized with `initial=file_size`. The resulting `downloaded_bytes` telemetry exceeds `total_size` by `file_size`.

---

## 2. Logic Chain

1. **Observation 1 & 2 -> Real-Time Telemetry Breakdown**:
   - The user requirements (R1, R2, Acceptance Criteria line 49) mandate real-time progress indicators displaying overall download percentage, speed, and active thread tasks.
   - Because `record.total_bytes` remains 0 and `record.completed_items` is only incremented upon full completion, `record.progress_pct` is locked at 0.0% throughout the entire download duration. It only jumps to 100% when `_finish_task` runs. The user experience is broken (progress bar remains frozen at 0% until completion).
2. **Observation 3 -> Metric Integrity Failure**:
   - When downloading media files, throttling the callback is necessary to protect the event loop. However, sending `chunk_bytes: size` (only the last chunk) without tracking cumulative bytes per file means that intermediate chunks are dropped from the task's byte total.
   - This corrupts `record.downloaded_bytes` and causes `speed_bps` to report an artificially suppressed throughput (~30 KB/s), rendering the telemetry untrustworthy.
3. **Observation 4 -> State Machine Integrity Violation**:
   - Discarding the return value of `downloader.awemeDownload` causes failed downloads (e.g. HTTP 403 Forbidden, 404 Not Found, dropped connections) to be reported as `TaskStatus.COMPLETED` with 100% progress.
   - A system that marks failed operations as successful violates core state machine invariants.
4. **Observation 5 -> Deadlock & Worker Starvation**:
   - Blocking worker threads on `record.pause_event.wait()` without unblocking them in `cancel_task` or `shutdown` causes orphaned threads that permanently hold resources in the ThreadPoolExecutor. Calling `shutdown(wait=True)` hangs the server process.
5. **Observation 6 -> Resource Exhaustion Attack Surface**:
   - Claiming a bounded concurrency model with `max_concurrent_tasks: int = 4` while never enforcing this parameter leaves the system vulnerable to resource exhaustion. Spawning 16 background tasks results in up to 400 OS threads due to nested thread pools in `userDownload` and `awemeDownload`.
6. **Observations 1–6 -> Verdict Determination**:
   - These findings represent critical functional failures in task lifecycle management, telemetry accuracy, and concurrency control. Therefore, the work product cannot be approved in its current state, and the verdict must be `REQUEST_CHANGES`.

---

## 3. Caveats

- Unit tests in `tests/test_m1_core.py` pass 100% (43/43), but this was achieved using isolated mock fixtures where `total_bytes` was manually populated in the test rather than by the runtime pipeline.
- REST endpoints and WebSocket handlers (`src/web/api/`) belong to Milestone 2 and were not evaluated.
- No modifications were made to implementation code, adhering to the review-only constraint.

---

## 4. Conclusion & Review Summary

**Verdict**: **`REQUEST_CHANGES`**

### Summary of Findings

| ID | Severity | Area | Summary |
|---|---|---|---|
| F1 | **Critical** | `task_manager.py` / `download.py` | `total_bytes` is never set; `downloaded_bytes` severely undercounted; `progress_pct` frozen at 0.0% until completion. |
| F2 | **Critical** | `task_manager.py` | Discarded return value of `awemeDownload` causes failed downloads to be reported as `COMPLETED` 100%. |
| F3 | **Major** | `task_manager.py` | Worker thread deadlock when cancelling or shutting down a paused task. |
| F4 | **Major** | `task_manager.py` / `download.py` | `max_concurrent_tasks` is unused; nested thread pools cause unconstrained thread explosion (up to 400 threads). |
| F5 | **Major** | `task_manager.py` | Race condition resurrects cancelled pending tasks back to `PARSING`. |
| F6 | **Minor** | `task_manager.py` / `download.py` | Multi-item downloads assign duplicate `worker_id` values, colliding on thread visualizer slot 0. |
| F7 | **Minor** | `download.py` | `downloaded_so_far` corrupts byte totals when resuming on servers returning HTTP 200 instead of 206. |
| F8 | **Minor** | `download.py` | Music filename suffix `{name}_music_{music_name}.mp3` diverges from Tier 1 test expectation `{name}_music.mp3`. |

---

## 5. Detailed Review Findings

### [Critical] Finding 1: Telemetry Failure — `total_bytes` Missing and `progress_pct` Stuck at 0.0%
- **What**: Overall download progress percentage stays at 0.0% for the entire duration of a download, and throughput (`speed_bps`) is off by orders of magnitude.
- **Where**: `src/web/services/task_manager.py`: lines 42, 416–418, 447–455, 559–570; `src/douyin/download.py`: lines 594–610.
- **Why**: 
  1. `record.total_bytes` is initialized to 0 and never accumulated when files start downloading.
  2. `record.completed_items` only increments after the download functions finish, remaining 0 while downloading.
  3. `record.downloaded_bytes` only increments by single 8KB chunks emitted every 250ms, dropping all intermediate chunks.
- **Suggestion**:
  1. In `create_progress_hook`: use `record._file_bytes_map` to track cumulative bytes per file. On each chunk/file update, calculate `delta = file_downloaded - record._file_bytes_map.get(filepath, 0)`, update `record._file_bytes_map[filepath] = file_downloaded`, and increment `record.downloaded_bytes += delta`.
  2. On `file_start`: accumulate `record.total_bytes += file_total` if `filepath` is new.
  3. For multi-item downloads: emit item completion callbacks or update `record.completed_items` after each aweme in `userDownload`.

### [Critical] Finding 2: False Success on Download Errors (State Machine Invariant)
- **What**: A task that completely fails to download files is marked as `TaskStatus.COMPLETED` with 100% progress.
- **Where**: `src/web/services/task_manager.py`: lines 553–577.
- **Why**: `downloader.awemeDownload` returns `False` on failure, but `_run_task_pipeline` ignores this return value and unconditionally transitions to `self._finish_task(record, TaskStatus.COMPLETED)`.
- **Suggestion**: Check `success = downloader.awemeDownload(...)`. If `not success`, transition to `self._finish_task(record, TaskStatus.FAILED)` with `record.error = "Download failed"`. For `userDownload`, track success counts and fail if 0 items succeeded.

### [Major] Finding 3: Thread Deadlock on Cancel / Shutdown while Paused
- **What**: Cancelling a paused task or shutting down the task manager leaks worker threads and hangs `shutdown(wait=True)` indefinitely.
- **Where**: `src/web/services/task_manager.py`: lines 248–284, 410, 678–685.
- **Why**: Worker threads wait on `record.pause_event.wait()`. `cancel_task()` and `shutdown()` set `cancel_event`, but never set `pause_event`.
- **Suggestion**: In `cancel_task()` and `shutdown()`, ensure `record.pause_event.set()` is called so paused threads immediately wake up, observe `record.cancel_event.is_set()`, and terminate cleanly.

### [Major] Finding 4: Dead Parameter `max_concurrent_tasks` & Thread Explosion
- **What**: `max_concurrent_tasks` is initialized and never used. 16 tasks run concurrently, spawning up to 400 OS threads.
- **Where**: `src/web/services/task_manager.py`: line 146; `src/douyin/download.py`: lines 251, 471.
- **Why**: `TaskManager` lacks an active task queue or semaphore. Every submitted task is submitted immediately to `ThreadPoolExecutor(max_workers=16)`. Combined with nested pools in `Download`, this creates severe thread contention.
- **Suggestion**: Introduce a `threading.Semaphore(self.max_concurrent_tasks)` in `_run_task_pipeline` or manage an internal FIFO task queue where only `max_concurrent_tasks` are dispatched to `_executor` simultaneously.

### [Major] Finding 5: Race Condition Resurrecting Cancelled Tasks
- **What**: Cancelling a pending task causes it to momentarily revert to `PARSING` and emit misleading SSE telemetry.
- **Where**: `src/web/services/task_manager.py`: lines 493–505.
- **Why**: `_run_task_pipeline` sets `record.status = PARSING` and broadcasts it before checking `if record.cancel_event.is_set()`.
- **Suggestion**: Check `if record.cancel_event.is_set(): return` as the very first line of `_run_task_pipeline`.

---

## 6. Adversarial Challenge Report

### Challenge Summary
**Overall Risk Assessment:** **HIGH**

### Challenges

#### [High] Challenge 1: Pipeline Starvation and Event Loop Flood Under High Bandwidth
- **Assumption Challenged**: Throttled callback with `chunk_bytes: size` accurately represents progress and throughput.
- **Attack Scenario**: Fast 50 MB/s connection downloads 500 MB video. Chunks stream at ~6,000 chunks/sec. Callback fires every 250ms with `size=8192`.
- **Blast Radius**: User sees 0% progress bar, reported download speed of 32 KB/s, and downloaded bytes showing 160 KB when 500 MB is already written to disk.
- **Mitigation**: Use delta calculation from cumulative `downloaded_bytes` per file via `_file_bytes_map`.

#### [High] Challenge 2: Zombie Thread Exhaustion via Pause-Cancel Sequence
- **Assumption Challenged**: Tasks can be cleanly paused and subsequently cancelled.
- **Attack Scenario**: User starts 4 downloads, pauses all 4, then clicks "Cancel All".
- **Blast Radius**: All 16–20 worker threads remain permanently stuck on `pause_event.wait()`. Subsequent download tasks cannot be executed because the thread pool is exhausted. Uvicorn server cannot exit cleanly on SIGTERM/SIGINT.
- **Mitigation**: `record.pause_event.set()` must be invoked whenever `cancel_event` is set.

#### [Medium] Challenge 3: Unbounded Nested Thread Pool Spawning
- **Assumption Challenged**: Bounded `ThreadPoolExecutor(max_workers=16)` in `TaskManager` bounds system concurrency.
- **Attack Scenario**: User queues 10 user profiles with 100 videos each.
- **Blast Radius**: 10 tasks run concurrently in `TaskManagerWorker`. Each spawns 5 threads in `userDownload`. Each video spawns 5 threads in `_download_media_files_threaded`. Total threads = $10 \times 5 \times 5 = 250$ threads. Windows thread limits / socket handles exhausted, causing `OSError: [Errno 24] Too many open files` or connection resets.
- **Mitigation**: Enforce `max_concurrent_tasks` and limit `Download` worker concurrency hierarchically.

---

## 7. Verified Claims & Coverage Gaps

### Verified Claims
- `test_m1_core.py` 43/43 tests pass via `pytest` $\rightarrow$ **PASS**
- `src/douyin/download.py` backward compatibility with CLI signatures $\rightarrow$ **PASS**
- Resumable HTTP Range header generation (`bytes={offset}-`) $\rightarrow$ **PASS**
- Thread-safe SSE fan-out via `loop.call_soon_threadsafe` $\rightarrow$ **PASS**

### Coverage Gaps
- **Real download pipeline execution with non-mocked progress tracking**: The existing test mocked `awemeDownload` to return `True` without exercising actual progress callbacks in pipeline execution. (Risk Level: HIGH).

---

## 8. Verification Method for Rework

To independently verify the required changes once addressed:

```powershell
# 1. Verify standard unit tests
.venv\Scripts\python.exe -m pytest tests/test_m1_core.py -v

# 2. Verify progress and byte tracking under throttling
.venv\Scripts\python.exe -c "
from src.web.services.task_manager import TaskManager, TaskRecord, DownloadRequest
req = DownloadRequest(url='https://v.douyin.com/test', key='test', thread_count=2)
rec = TaskRecord('test-id', req)
tm = TaskManager()
hook = tm.create_progress_hook(rec)
# Simulate file start of 10MB
hook({'event': 'file_start', 'worker_id': 1, 'filepath': 'test.mp4', 'filename': 'test.mp4', 'chunk_bytes': 0, 'downloaded_bytes': 0, 'total_bytes': 10000000})
# Simulate chunk update after 5MB downloaded
hook({'event': 'chunk', 'worker_id': 1, 'filepath': 'test.mp4', 'filename': 'test.mp4', 'chunk_bytes': 8192, 'downloaded_bytes': 5000000, 'total_bytes': 10000000})
assert rec.downloaded_bytes == 5000000, f'Expected 5000000 but got {rec.downloaded_bytes}'
assert rec.progress_pct == 50.0, f'Expected 50.0% but got {rec.progress_pct}'
print('Progress tracking verified successfully!')
"

# 3. Verify pause-cancel unblock
.venv\Scripts\python.exe -c "
from src.web.services.task_manager import TaskManager, DownloadRequest
tm = TaskManager()
resp = tm.submit_task(DownloadRequest(url='https://v.douyin.com/test', key='test'))
tm.pause_task(resp.task_id)
assert tm.cancel_task(resp.task_id) is True
rec = tm._tasks[resp.task_id]
assert rec.pause_event.is_set(), 'pause_event must be set on cancellation to prevent worker thread deadlock'
print('Pause-cancel unblock verified successfully!')
"
```
