# Handoff: M1 Iteration 2 Explorer 3 (TaskManager & Concurrency Remediation)

**Agent:** M1 Iteration 2 Explorer 3  
**Working Directory:** `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_3\`  
**Target Files:**  
- `src/web/services/task_manager.py`  
- `src/douyin/download.py`  
- `tests/test_m1_core.py`  
**Handoff Type:** Hard (Task Complete)  
**Date:** 2026-10-06  

---

## 1. Observation

1. **Test Failures Observed in Baseline**:
   - Command: `.venv\Scripts\python.exe -m pytest tests/test_m1_core.py tests/test_m1_concurrency_stress.py`
   - Output: `4 failed, 49 passed in 1.02s`
   - Specific Failures:
     - `test_unbounded_concurrent_execution_investigation`: `AssertionError: VULNERABILITY: max_concurrent_tasks=2 is UNENFORCED! Observed 4 concurrent tasks executing simultaneously.`
     - `test_cancel_on_paused_task_deadlock_vulnerability`: `AssertionError: ZOMBIE THREAD DETECTED: cancel_task failed to unblock worker waiting on pause_event!`
     - `test_subscriber_and_task_record_memory_retention`: `AssertionError: VULNERABILITY: TaskManager._subscribers leaks dictionary keys and sets for completed tasks!`
     - `test_task_manager_pipeline_execution_completion`: `AssertionError: assert <TaskStatus.DOWNLOADING: 'DOWNLOADING'> == <TaskStatus.COMPLETED: 'COMPLETED'>`

2. **Telemetry & Progress Undercounting**:
   - Command:
     ```python
     from src.web.services.task_manager import TaskManager, TaskRecord, DownloadRequest
     req = DownloadRequest(url='https://v.douyin.com/test', key='test', thread_count=2)
     rec = TaskRecord('test-id', req)
     tm = TaskManager()
     hook = tm.create_progress_hook(rec)
     hook({'event': 'file_start', 'worker_id': 1, 'filepath': 'test.mp4', 'filename': 'test.mp4', 'chunk_bytes': 0, 'downloaded_bytes': 0, 'total_bytes': 10000000})
     hook({'event': 'chunk', 'worker_id': 1, 'filepath': 'test.mp4', 'filename': 'test.mp4', 'chunk_bytes': 8192, 'downloaded_bytes': 5000000, 'total_bytes': 10000000})
     ```
   - Result: `downloaded_bytes=8192, total_bytes=0, progress_pct=0.0`.
   - Code: `src/web/services/task_manager.py` line 42 (`self.total_bytes = 0` never updated), line 417 (`record.downloaded_bytes += chunk_bytes` adds only single 8KB sample, discarding intermediate bytes).

3. **Silent Success on Download Failures**:
   - Code: `src/web/services/task_manager.py` lines 553–577:
     ```python
     downloader.awemeDownload(...)
     ...
     if record.cancel_event.is_set():
         self._finish_task(record, TaskStatus.CANCELLED)
     else:
         self._finish_task(record, TaskStatus.COMPLETED)
     ```
   - The boolean return of `downloader.awemeDownload` was discarded; failure to download files resulted in `TaskStatus.COMPLETED` with 100% progress.

4. **Zombie Thread Deadlock on Paused Task Cancellation**:
   - Code: `src/web/services/task_manager.py` line 410 (`record.pause_event.wait()`) and lines 271–274 (`cancel_task` only sets `cancel_event`, leaving `pause_event` cleared).
   - Paused worker threads stay blocked on `pause_event.wait()`, leaking worker threads and hanging `shutdown(wait=True)`.

5. **Concurrency Limit Dead Code**:
   - Code: `src/web/services/task_manager.py` line 146 (`self.max_concurrent_tasks = max_concurrent_tasks`), line 217 (`self._executor.submit(...)`).
   - `max_concurrent_tasks` is never checked; all submitted tasks run concurrently up to `max_total_workers` (16).

---

## 2. Logic Chain

1. **From Observation 1 & 2 to Telemetry Invariant**:
   - `TaskRecord.total_bytes` must be accumulated when file metadata is received from workers (`_file_totals_map`).
   - When callbacks are throttled (~250ms), byte progress must be tracked via cumulative delta (`delta = file_downloaded - prev_downloaded`), with fallback to `chunk_bytes`. In `download.py`, chunk bytes must be accumulated between throttled calls (`accumulated_chunk_bytes += size`). This restores accurate `downloaded_bytes`, `speed_bps`, and `progress_pct`.
2. **From Observation 3 to State Machine Correctness**:
   - Marking failed downloads as `COMPLETED` violates user acceptance criteria and state machine invariants. Storing `download_success = downloader.awemeDownload(...)` and transitioning to `FAILED` with `record.error` when false ensures state integrity.
3. **From Observation 4 to Deadlock Elimination**:
   - Calling `record.pause_event.set()` in `cancel_task` and `shutdown` immediately unblocks threads blocked on `record.pause_event.wait()`. Adding a timeout-and-cancel loop in `_hook` guarantees zero leaked threads.
4. **From Observation 5 to Bounded Concurrency**:
   - Enforcing `self._task_semaphore = threading.Semaphore(self.max_concurrent_tasks)` in `_run_task_pipeline` bounds active tasks to `max_concurrent_tasks` without starving or dropping submissions.
5. **From Baseline Failures to Verified Remediation**:
   - All proposed fixes were validated via `.agents/teamwork/teamwork_preview_explorer_m1_it2_3/test_verify_patches.py`, passing 100% of telemetry, pause-cancel unblock, subscriber pruning, and semaphore bounding checks.

---

## 3. Caveats

- **Read-Only Explorer Constraint**: Explorer did not modify production code in `src/` directly. The complete unified patches are documented in `report.md` for the implementer agent to apply.
- **REST Endpoints**: FastAPI endpoints (`src/web/api/`) and React frontend (`frontend/`) are Milestone 2 scope and remain untouched.

---

## 4. Conclusion

Remediation strategy and exact drop-in patches are fully formulated and validated:
- **Telemetry**: Fixed via `_file_totals_map`, delta tracking in `create_progress_hook`, and `accumulated_chunk_bytes` in `download.py`.
- **Download Failure Handling**: Fixed by checking `awemeDownload` and `userDownload` return values and failing with error descriptions.
- **Zombie Thread Hang**: Fixed by setting `record.pause_event.set()` in `cancel_task` and `shutdown`, plus cancel check in `_hook`.
- **Concurrency Bounding**: Fixed by introducing `self._task_semaphore` in `TaskManager`.
- **Subscriber Leak**: Fixed by pruning `_subscribers[task_id]` in `_finish_task`.
- **Test Flakiness**: Fixed by replacing `time.sleep(0.1)` with polling loop in `test_task_manager_pipeline_execution_completion`.

---

## 5. Verification Method

1. **Verify Unit Patches Script**:
   ```powershell
   $env:PYTHONPATH='.'; .venv\Scripts\python.exe .agents/teamwork/teamwork_preview_explorer_m1_it2_3/test_verify_patches.py
   ```
   *Expected*: Prints success for all 4 tests and exits with code 0.

2. **Verify Full Test Suite (Post-Implementation)**:
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/test_m1_core.py tests/test_m1_concurrency_stress.py -v
   ```
   *Expected*: 53 passed, 0 failed.
