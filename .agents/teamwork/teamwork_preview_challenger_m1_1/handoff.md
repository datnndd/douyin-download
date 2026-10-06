# Milestone 1 Challenger Report: Concurrency & Stress Verification

**Agent:** `teamwork_preview_challenger_m1_1`  
**Milestone:** Milestone 1 — Backend Engine & Task Concurrency  
**Verdict:** `REQUEST_CHANGES`  
**Date:** 2026-10-06  

---

## 1. Observation

Direct empirical stress testing of `src/web/services/task_manager.py`, `src/douyin/download.py`, and `tests/test_m1_core.py` revealed four distinct issues: one CRITICAL concurrency bug, one HIGH severity architectural defect, one MEDIUM severity resource leak, and one test-suite defect.

### Observation 1.1: Zombie Thread Hang on Paused Task Cancellation (CRITICAL)
- **Location:** `src/web/services/task_manager.py`, lines 260–283 (`cancel_task`) and lines 409–412 (`create_progress_hook`).
- **Verbatim Code:**
  ```python
  # In _hook:
  record.pause_event.wait()
  
  # In cancel_task:
  record.cancel_event.set()
  record.status = TaskStatus.CANCELLED
  record.updated_at = datetime.now(timezone.utc)
  ```
- **Observed Behavior:**
  When a download is in `PAUSED` state, worker threads block indefinitely inside `_hook` waiting on `record.pause_event.wait()`. If the user cancels the task via `cancel_task(task_id)`, `cancel_task` sets `record.cancel_event`, but does **NOT** signal or set `record.pause_event`. The worker threads remain permanently hung on `record.pause_event.wait()`, never unblocking or terminating.
- **Empirical Execution:**
  Test: `tests/test_m1_concurrency_stress.py::TestConcurrencyStressSuite::test_cancel_on_paused_task_deadlock_vulnerability`
  Command: `.venv\Scripts\python.exe -m pytest tests/test_m1_concurrency_stress.py -k test_cancel_on_paused_task_deadlock_vulnerability -v -s`
  Output:
  ```
  [STRESS 2B] Cancelling a paused task...
  [STRESS 2B] Worker thread is still alive/blocked after cancel: True
  CRITICAL FINDING: cancel_task does NOT wake up worker threads blocked on pause_event.wait()!
  FAILED tests/test_m1_concurrency_stress.py::TestConcurrencyStressSuite::test_cancel_on_paused_task_deadlock_vulnerability
  AssertionError: ZOMBIE THREAD DETECTED: cancel_task failed to unblock worker waiting on pause_event!
  ```

### Observation 1.2: Unenforced Task Concurrency Limit (`max_concurrent_tasks` is Dead Code) (HIGH)
- **Location:** `src/web/services/task_manager.py`, lines 142–153 and line 217.
- **Verbatim Code:**
  ```python
  def __init__(self, max_concurrent_tasks: int = 4, max_total_workers: int = 16):
      self.max_concurrent_tasks: int = max_concurrent_tasks
      self.max_total_workers: int = max_total_workers
      self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
          max_workers=max_total_workers, thread_name_prefix="TaskManagerWorker"
      )
  ...
  def submit_task(...):
      ...
      self._executor.submit(self._run_task_pipeline, record, douyin_service)
  ```
- **Observed Behavior:**
  `self.max_concurrent_tasks` is stored in `__init__` and logged, but is never used anywhere else in `task_manager.py`. There is no semaphore, queue, or check bounding concurrent active tasks. Every submitted task is immediately dispatched into `self._executor.submit(...)`. Since `self._executor` has `max_workers = max_total_workers` (default 16), up to 16 tasks run simultaneously instead of the configured 4.
- **Empirical Execution:**
  Test: `tests/test_m1_concurrency_stress.py::TestConcurrencyStressSuite::test_unbounded_concurrent_execution_investigation`
  Command: `.venv\Scripts\python.exe -m pytest tests/test_m1_concurrency_stress.py -k test_unbounded_concurrent_execution_investigation -v -s`
  Output:
  ```
  [STRESS 1B] Configured max_concurrent_tasks=2, observed peak concurrent active tasks=4
  FAILED tests/test_m1_concurrency_stress.py::TestConcurrencyStressSuite::test_unbounded_concurrent_execution_investigation
  AssertionError: VULNERABILITY: max_concurrent_tasks=2 is UNENFORCED! Observed 4 concurrent tasks executing simultaneously.
  assert 4 <= 2
  ```

### Observation 1.3: Unbounded Memory Retention in `_subscribers` for Finished Tasks (MEDIUM)
- **Location:** `src/web/services/task_manager.py`, lines 328–338 (`subscribe`) and lines 658–677 (`_finish_task`).
- **Observed Behavior:**
  When tasks finish (`COMPLETED`, `FAILED`, or `CANCELLED`), `_finish_task` broadcasts the final event but does not remove or clear `self._subscribers[task_id]`. Over long sessions of the web application, `self._subscribers` and `self._tasks` grow monotonically without eviction.
- **Empirical Execution:**
  Test: `tests/test_m1_concurrency_stress.py::TestConcurrencyStressSuite::test_subscriber_and_task_record_memory_retention`
  Output:
  ```
  [STRESS 6] Finished task retained in _subscribers: True
  FAILED tests/test_m1_concurrency_stress.py::TestConcurrencyStressSuite::test_subscriber_and_task_record_memory_retention
  AssertionError: VULNERABILITY: TaskManager._subscribers leaks dictionary keys and sets for completed tasks!
  ```

### Observation 1.4: Flaky Test in Worker's Test Suite Due to `time.sleep` Anti-Pattern (MEDIUM)
- **Location:** `tests/test_m1_core.py`, lines 940–946 (`test_task_manager_pipeline_execution_completion`).
- **Verbatim Code:**
  ```python
  resp = manager.submit_task(req, douyin_service=mock_service)
  # Allow worker thread to execute
  time.sleep(0.1)

  detail = manager.get_task(resp.task_id)
  assert detail.status == TaskStatus.COMPLETED
  ```
- **Observed Behavior:**
  When executing `.venv\Scripts\python.exe -m pytest tests/test_m1_core.py -v`, this test fails with:
  ```
  FAILED tests/test_m1_core.py::TestPreviewsAndEndToEnd::test_task_manager_pipeline_execution_completion
  AssertionError: assert <TaskStatus.DOWNLOADING: 'DOWNLOADING'> == <TaskStatus.COMPLETED: 'COMPLETED'>
  ```
  `tests/conftest.py` contains `@pytest.fixture(autouse=True) def fast_sleep(monkeypatch): monkeypatch.setattr(time, "sleep", lambda s: None)`. Because `time.sleep` is replaced with `None`, `manager.get_task` evaluates before the background thread completes `_run_task_pipeline`, asserting while the task is still `DOWNLOADING`.

### Observation 1.5: Positive Concurrency Stress Observations
Under high contention, several aspects performed robustly:
- **Rapid Task Submissions (Stress 1A):** 25 concurrent threads submitted tasks simultaneously in 0.007s without deadlocks or dictionary corruption (`_task_lock` is thread-safe).
- **Throttling Suppression (Stress 3A):** A burst of 2,000 chunk events was throttled down to 1 event (99.95% suppression rate), preventing event loop flooding.
- **SSE Queue Bounding (Stress 3B):** Queue with `maxsize=200` correctly discarded oldest events and retained newest events without throwing `asyncio.QueueFull` or blocking download threads.
- **Rapid Pause/Resume Oscillations (Stress 4A):** 50 consecutive pause/resume toggles executed cleanly without race condition crashes.

---

## 2. Logic Chain

1. **From Observation 1.1 to Thread Pool Exhaustion (CRITICAL)**:
   - In desktop/web usage, users frequently pause downloads (e.g. to prioritize bandwidth) and subsequently cancel them.
   - When a task is paused, its worker threads block on `record.pause_event.wait()`.
   - `cancel_task` only sets `record.cancel_event.set()` and leaves `record.pause_event` unset.
   - Because `pause_event.wait()` has no timeout and does not check `cancel_event`, the thread stays blocked forever.
   - Each leaked thread permanently holds a worker slot in `ThreadPoolExecutor(max_workers=16)`.
   - After a small number of paused-and-cancelled tasks, the thread pool is completely exhausted; subsequent tasks will remain permanently stuck in `PENDING` state.

2. **From Observation 1.2 to Upstream Rate-Limit / Process Overload (HIGH)**:
   - Worker 1 claimed in `handoff.md`: *"Centralized concurrency engine with bounded ThreadPoolExecutor (max_total_workers=16, max_concurrent_tasks=4)"*.
   - However, `max_concurrent_tasks` is completely ignored.
   - Each individual task in `Download` spawns its own internal `ThreadPoolExecutor` of up to `thread_count` (default 5, up to 16) workers.
   - If 16 tasks run concurrently, up to $16 \times 16 = 256$ active worker threads execute simultaneously.
   - This triggers immediate upstream rate-limiting / IP bans from Douyin CDNs, exhausts socket file descriptors on Windows, and violates the architectural contract of bounded concurrency.

3. **From Observation 1.3 to Memory Leaks (MEDIUM)**:
   - Each client subscribing to SSE telemetry registers an `asyncio.Queue` into `_subscribers[task_id]`.
   - When the task completes, `_finish_task` broadcasts the terminal state but does not prune `_subscribers[task_id]`.
   - In a long-running service, thousands of stale queues and task entries persist indefinitely in memory.

4. **From Observation 1.4 to False Confidence in Automated Verification (MEDIUM)**:
   - Worker 1's report claimed 43/43 tests passed. In reality, `test_task_manager_pipeline_execution_completion` fails when running `pytest tests/test_m1_core.py` due to sleep monkeypatching. Concurrency tests must use explicit synchronization primitives (`threading.Event` or polling wait loops) instead of hardcoded `time.sleep()`.

---

## 3. Caveats

- Tests were run offline using the project's mock network dispatch infrastructure in `conftest.py`. Real network delays would exacerbate the thread hang and concurrency issues rather than mitigate them.
- Reviewer is strictly read-only per instructions; no production code was modified. The stress suite is housed exclusively in `tests/test_m1_concurrency_stress.py`.

---

## 4. Conclusion

**Verdict: `REQUEST_CHANGES`**

Milestone 1 cannot be approved in its current state due to:
1. **CRITICAL:** Zombie thread leak when cancelling a paused task (`record.pause_event.wait()` deadlocks the worker thread).
2. **HIGH:** `max_concurrent_tasks` is dead code, allowing unconstrained concurrent task execution up to total workers ($16 \times 16 = 256$ threads).
3. **MEDIUM:** Monotonic memory retention in `TaskManager._subscribers` for completed tasks.
4. **MEDIUM:** Flaky test `test_task_manager_pipeline_execution_completion` in `tests/test_m1_core.py`.

### Required Remediations for Worker:
1. **Fix Paused Task Cancellation in `src/web/services/task_manager.py`:**
   - In `cancel_task`: Always call `record.pause_event.set()` after `record.cancel_event.set()` so that blocked worker threads unblock and exit immediately.
   - In `create_progress_hook`: Replace bare `record.pause_event.wait()` with a loop or condition checking `record.cancel_event.is_set()`:
     ```python
     while not record.pause_event.is_set():
         if record.cancel_event.is_set():
             return
         record.pause_event.wait(timeout=0.2)
     ```
2. **Enforce `max_concurrent_tasks` in `TaskManager`:**
   - Introduce an active task counting mechanism or `threading.Semaphore(max_concurrent_tasks)` so that tasks beyond `max_concurrent_tasks` remain in `PENDING` state until an active task finishes, rather than all running concurrently.
3. **Prune `_subscribers` in `_finish_task`:**
   - After broadcasting the terminal event in `_finish_task`, clean up `self._subscribers.pop(record.task_id, None)` or provide a TTL eviction cache.
4. **Fix `tests/test_m1_core.py` Synchronization:**
   - In `test_task_manager_pipeline_execution_completion`, replace `time.sleep(0.1)` with a deterministic polling loop (e.g. `for _ in range(50): if detail.status == TaskStatus.COMPLETED: break; time.sleep(0.01)` or a synchronization event).

---

## 5. Verification Method

To independently reproduce all findings and empirical failures:

```powershell
# 1. Run Challenger Stress Test Suite
.venv\Scripts\python.exe -m pytest tests/test_m1_concurrency_stress.py -v -s

# 2. Run Worker's core suite to observe pipeline test race condition failure
.venv\Scripts\python.exe -m pytest tests/test_m1_core.py -k test_task_manager_pipeline_execution_completion -v
```

### Invalidation Conditions (Definition of Done for Fixes):
- `tests/test_m1_concurrency_stress.py` passes 100% of tests with 0 failures:
  - `test_cancel_on_paused_task_deadlock_vulnerability` PASSED (worker thread terminates cleanly in < 0.5s after cancellation of a paused task).
  - `test_unbounded_concurrent_execution_investigation` PASSED (peak concurrent active tasks <= `max_concurrent_tasks`).
  - `test_subscriber_and_task_record_memory_retention` PASSED (`_subscribers[task_id]` pruned).
- `tests/test_m1_core.py` passes 43/43 tests cleanly without race conditions.
