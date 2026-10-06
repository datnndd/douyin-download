# Milestone 1 Iteration 2: TaskManager & Concurrency Remediation Report

**Explorer:** M1 Iteration 2 Explorer 3 (TaskManager & Concurrency Remediation)  
**Date:** 2026-10-06  
**Target Files:**  
- `src/web/services/task_manager.py`  
- `src/douyin/download.py`  
- `tests/test_m1_core.py`  
**Working Directory:** `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_3\`  
**Status:** Remediations Fully Formulated & Empirically Verified

---

## 1. Executive Summary

Adversarial stress testing and review of Milestone 1 identified critical defects in `TaskManager` and `Download`:
1. **Telemetry & Progress Freezing**: `record.total_bytes` was never initialized from stream payloads (stayed `0`), throttled chunk emissions dropped intermediate bytes, and `progress_pct` remained frozen at `0.0%` until snapping to `100.0%`.
2. **False Success on Download Failures**: In `_run_task_pipeline`, the boolean return of `downloader.awemeDownload` was discarded; tasks where all network downloads failed were marked as `TaskStatus.COMPLETED` with 100% progress.
3. **Zombie Worker Thread Deadlock on Pause/Cancel**: Worker threads blocked on `record.pause_event.wait()` were never unblocked when cancelling a paused task or during shutdown, permanently leaking thread pool workers and deadlocking `shutdown(wait=True)`.
4. **Dead Parameter `max_concurrent_tasks`**: Concurrency was unconstrained; all submitted tasks were dispatched immediately into the thread pool, violating the architectural contract and causing thread explosions.
5. **Pending Cancel Race Condition**: Tasks cancelled while `PENDING` were momentarily reverted to `PARSING` before terminating.
6. **Subscriber Memory Retention**: `_subscribers[task_id]` sets were never pruned upon task completion, leaking memory monotonically.
7. **HTTP 200 Resumption Counter Corruption**: When falling back from HTTP 206 to HTTP 200, `downloaded_so_far` remained set to `file_size`, corrupting byte accounting.
8. **Test Flakiness**: `test_task_manager_pipeline_execution_completion` failed due to `conftest.py` monkeypatching `time.sleep` to `None`.

All defects have been analyzed to root cause, validated empirically with reproduced failures, and resolved with concrete, minimal, drop-in code patches below.

---

## 2. Root Cause Analysis & Empirical Evidence

### Defect 1: Telemetry Breakdown (`total_bytes` 0, Undercounted `downloaded_bytes`, Frozen `progress_pct`)
- **Locations**: `src/web/services/task_manager.py` lines 42, 416–418, 447–455; `src/douyin/download.py` lines 593–610.
- **Root Cause**:
  1. `record.total_bytes` is initialized to 0 and was never updated from `file_start` or `chunk` events (`payload["total_bytes"]`).
  2. In `download.py`, `eff_callback` emits only every ~250ms, passing `chunk_bytes: size` (only the 8KB chunk of that single iteration). All intermediate chunks written during the 250ms interval were lost.
  3. In `task_manager.py`, `record.downloaded_bytes += chunk_bytes` added only the 8KB sample, reporting e.g. 160 KB downloaded for a 100 MB file, and throttling `speed_bps` to ~32 KB/s.
  4. Because `record.total_bytes` was 0 and `record.completed_items` only incremented after the download completed, `progress_pct` remained locked at `0.0%`.
- **Remediation**:
  - In `download.py`: accumulate `accumulated_chunk_bytes += size` between callback emissions, passing `chunk_bytes: accumulated_chunk_bytes` and resetting to 0 on emit.
  - In `task_manager.py`: track `_file_totals_map` and `_file_bytes_map` per `filepath`/`filename`. On each event:
    - If `file_total > 0`, calculate `delta_total = file_total - prev_total`, update `record.total_bytes += delta_total`.
    - If `file_downloaded > 0`, calculate `delta_downloaded = file_downloaded - prev_downloaded`, update `record.downloaded_bytes += delta_downloaded`.
    - Fallback: if `delta_downloaded <= 0` and `chunk_bytes > 0`, add `chunk_bytes`.

### Defect 2: False Success on Download Failures
- **Location**: `src/web/services/task_manager.py` lines 553–577.
- **Root Cause**:
  `downloader.awemeDownload(...)` returns `True` on success or `False` on failure (e.g. all 5 retries exhausted). The pipeline discarded this boolean and executed `self._finish_task(record, TaskStatus.COMPLETED)`.
- **Remediation**:
  Store `success = downloader.awemeDownload(...)`. If `not success`, record error message `record.error = "Download failed for aweme item"` and transition to `self._finish_task(record, TaskStatus.FAILED)`. For `userDownload`, return `success_count > 0` and fail if 0 items succeeded.

### Defect 3: Zombie Worker Thread Deadlock on Pause/Cancel
- **Locations**: `src/web/services/task_manager.py` lines 271–274, 409–412, 681–684.
- **Root Cause**:
  When a task is `PAUSED`, worker threads block on `record.pause_event.wait()`. Calling `cancel_task(task_id)` sets `record.cancel_event`, but does **not** set `record.pause_event`. The worker threads remain permanently blocked inside `_hook` waiting for `pause_event`, leaking threads. Calling `shutdown(wait=True)` hangs forever.
- **Remediation**:
  - In `cancel_task`: unconditionally call `record.pause_event.set()` to immediately unblock any paused worker threads.
  - In `shutdown`: iterate all tasks and call `task.pause_event.set()`.
  - In `create_progress_hook`: replace bare `record.pause_event.wait()` with a loop checking `record.cancel_event.is_set()` with timeout:
    ```python
    while not record.pause_event.is_set():
        if record.cancel_event.is_set():
            return
        record.pause_event.wait(timeout=0.2)
    if record.cancel_event.is_set():
        return
    ```

### Defect 4: Unenforced Concurrency Limit (`max_concurrent_tasks` Dead Code)
- **Locations**: `src/web/services/task_manager.py` lines 146, 217.
- **Root Cause**:
  `self.max_concurrent_tasks` was stored in `__init__` but never used anywhere. All tasks were immediately submitted to `_executor.submit(...)`.
- **Remediation**:
  Introduce `self._task_semaphore: threading.Semaphore = threading.Semaphore(max_concurrent_tasks)` in `TaskManager.__init__`. In `_run_task_pipeline`, acquire the semaphore before entering the active pipeline, holding it until task completion via `try...finally`:
  ```python
  acquired = False
  while not record.cancel_event.is_set():
      acquired = self._task_semaphore.acquire(timeout=0.1)
      if acquired:
          break
  if not acquired or record.cancel_event.is_set():
      if acquired:
          self._task_semaphore.release()
      self._finish_task(record, TaskStatus.CANCELLED)
      return
  try:
      ...
  finally:
      self._task_semaphore.release()
  ```

### Defect 5: Pending Cancel Race Condition (Resurrection to `PARSING`)
- **Locations**: `src/web/services/task_manager.py` lines 493–505.
- **Root Cause**:
  `_run_task_pipeline` unconditionally broadcasted `PARSING` before checking `record.cancel_event.is_set()`.
- **Remediation**:
  Check `if record.cancel_event.is_set(): self._finish_task(record, TaskStatus.CANCELLED); return` before changing status to `PARSING`.

### Defect 6: Monotonic Memory Leak in `_subscribers`
- **Locations**: `src/web/services/task_manager.py` lines 658–677 (`_finish_task`).
- **Root Cause**:
  `_subscribers[task_id]` was never deleted upon task terminal state.
- **Remediation**:
  In `_finish_task`, after broadcasting the final event:
  ```python
  with self._sub_lock:
      self._subscribers.pop(record.task_id, None)
  ```

### Defect 7: HTTP 200 Resumption Counter Corruption
- **Locations**: `src/douyin/download.py` lines 546–575.
- **Root Cause**:
  When a Range request fallback returns HTTP 200, `downloaded_so_far` remained initialized to `file_size`, causing total reported bytes to exceed file size by `file_size`.
- **Remediation**:
  ```python
  initial_bytes = file_size if response.status_code == 206 else 0
  downloaded_so_far = initial_bytes
  ```

### Defect 8: Test Flakiness in `test_task_manager_pipeline_execution_completion`
- **Locations**: `tests/test_m1_core.py` lines 942–946.
- **Root Cause**:
  `tests/conftest.py` replaces `time.sleep` with `lambda s: None`. Calling `time.sleep(0.1)` returned instantly before background thread finished.
- **Remediation**:
  Use polling wait loop checking `detail.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)` with timeout deadline.

---

## 3. Concrete Code Patches

### Patch 1: `src/web/services/task_manager.py`

```diff
--- a/src/web/services/task_manager.py
+++ b/src/web/services/task_manager.py
@@ -70,6 +70,7 @@ class TaskRecord:
         self._last_speed_bytes: int = 0
         self._last_telemetry_emit_time: float = 0.0
         self._file_bytes_map: Dict[str, int] = {}  # filepath -> downloaded bytes
+        self._file_totals_map: Dict[str, int] = {}  # filepath -> total file bytes
 
     def to_detail_response(self) -> TaskDetailResponse:
@@ -147,6 +148,7 @@ class TaskManager:
         self.max_concurrent_tasks: int = max_concurrent_tasks
         self.max_total_workers: int = max_total_workers
 
+        self._task_semaphore: threading.Semaphore = threading.Semaphore(max_concurrent_tasks)
         # Bounded executor pool for all background tasks
         self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
             max_workers=max_total_workers, thread_name_prefix="TaskManagerWorker"
@@ -270,6 +272,7 @@ class TaskManager:
                 return False
 
             record.cancel_event.set()
+            record.pause_event.set()  # Unblock any paused worker threads immediately
             record.status = TaskStatus.CANCELLED
             record.updated_at = datetime.now(timezone.utc)
 
@@ -406,14 +409,47 @@ class TaskManager:
             chunk_bytes = payload.get("chunk_bytes", 0)
             file_downloaded = payload.get("downloaded_bytes", 0)
             file_total = payload.get("total_bytes", 0)
+            file_key = payload.get("filepath") or file_name or f"worker_{worker_id}"
 
-            # Check pause state (block worker thread if paused)
-            record.pause_event.wait()
+            # Check pause state (block worker thread if paused, unblock on cancel)
+            while not record.pause_event.is_set():
+                if record.cancel_event.is_set():
+                    return
+                record.pause_event.wait(timeout=0.2)
+
+            if record.cancel_event.is_set():
+                return
 
             with record._lock:
                 record.updated_at = datetime.now(timezone.utc)
 
-                # 1. Update downloaded byte metrics
-                if chunk_bytes > 0:
+                # 1. Update total bytes dynamically from discovered file sizes
+                if file_total > 0 and file_key:
+                    prev_total = record._file_totals_map.get(file_key, 0)
+                    if file_total != prev_total:
+                        record.total_bytes += (file_total - prev_total)
+                        record._file_totals_map[file_key] = file_total
+
+                # 2. Update downloaded byte metrics accurately via delta
+                if file_key and (file_downloaded > 0 or file_key in record._file_bytes_map):
+                    prev_downloaded = record._file_bytes_map.get(file_key, 0)
+                    delta = file_downloaded - prev_downloaded
+                    if delta > 0:
+                        record.downloaded_bytes += delta
+                        record._file_bytes_map[file_key] = file_downloaded
+                    elif delta < 0:
+                        record._file_bytes_map[file_key] = file_downloaded
+                    elif chunk_bytes > 0:
+                        record.downloaded_bytes += chunk_bytes
+                elif chunk_bytes > 0:
                     record.downloaded_bytes += chunk_bytes
+
+                # Handle item_complete event in multi-item downloads
+                if event_kind == "item_complete":
+                    record.completed_items = payload.get("item_index", record.completed_items)
+                    if payload.get("item_total"):
+                        record.total_items = payload["item_total"]
 
                 # 2. Update worker slot in visualizer
@@ -492,6 +528,24 @@ class TaskManager:
         logger.info(f"Starting execution for task {task_id}")
 
+        if record.cancel_event.is_set():
+            self._finish_task(record, TaskStatus.CANCELLED)
+            return
+
+        # Enforce max_concurrent_tasks bound
+        acquired = False
+        while not record.cancel_event.is_set():
+            acquired = self._task_semaphore.acquire(timeout=0.1)
+            if acquired:
+                break
+
+        if not acquired or record.cancel_event.is_set():
+            if acquired:
+                self._task_semaphore.release()
+            self._finish_task(record, TaskStatus.CANCELLED)
+            return
+
         try:
             # ----------------- Phase 1: PARSING -----------------
             parsing_status = getattr(TaskStatus, "PARSING", TaskStatus.DOWNLOADING)
@@ -549,27 +603,34 @@ class TaskManager:
             # Process items
+            download_success = True
             if req.key_type == "aweme" and len(items) == 1:
                 aweme_dict = items[0]
                 save_out = destination / "aweme"
-                downloader.awemeDownload(
+                download_success = downloader.awemeDownload(
                     awemeDict=aweme_dict,
                     savePath=save_out,
                     cancel_event=record.cancel_event,
                     progress_callback=progress_hook,
                 )
                 with record._lock:
-                    record.completed_items = 1
+                    if download_success:
+                        record.completed_items = 1
             else:
                 # User / Mix / Multiple items
-                downloader.userDownload(
+                download_success = downloader.userDownload(
                     awemeList=items,
                     savePath=destination,
                     cancel_event=record.cancel_event,
                     progress_callback=progress_hook,
                 )
                 with record._lock:
-                    record.completed_items = len(items)
+                    if download_success:
+                        record.completed_items = len(items)
 
             # Check if cancelled during download
             if record.cancel_event.is_set():
                 self._finish_task(record, TaskStatus.CANCELLED)
+            elif not download_success:
+                record.error = "Download failed for task items"
+                self._finish_task(record, TaskStatus.FAILED)
             else:
                 self._finish_task(record, TaskStatus.COMPLETED)
@@ -581,6 +642,8 @@ class TaskManager:
             self._finish_task(record, TaskStatus.FAILED)
+        finally:
+            self._task_semaphore.release()
 
@@ -675,6 +738,10 @@ class TaskManager:
         self._broadcast_event(
             record.to_progress_event(), task_id=record.task_id, force=True
         )
+        # Prune subscriber queues to prevent memory leak
+        with self._sub_lock:
+            self._subscribers.pop(record.task_id, None)
 
     def shutdown(self, wait: bool = True) -> None:
@@ -682,5 +749,6 @@ class TaskManager:
         with self._task_lock:
             for task in self._tasks.values():
                 task.cancel_event.set()
+                task.pause_event.set()  # Unblock paused workers
         self._executor.shutdown(wait=wait)
```

---

### Patch 2: `src/douyin/download.py`

```diff
--- a/src/douyin/download.py
+++ b/src/douyin/download.py
@@ -232,6 +232,7 @@ class Download:
         cancel_event: Optional[threading.Event] = None,
         progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
+        worker_offset: int = 0,
     ) -> bool:
         tasks = self._prepare_media_tasks(aweme, path, name, desc)
         eff_cancel = cancel_event or self.cancel_event
@@ -242,5 +243,5 @@ class Download:
 
         for i, task in enumerate(tasks):
-            task["worker_id"] = (i % self.thread) + 1
+            task["worker_id"] = ((worker_offset + i) % self.thread) + 1
             task["cancel_event"] = eff_cancel
             task["progress_callback"] = progress_callback or self.progress_callback
@@ -370,6 +371,7 @@ class Download:
         cancel_event: Optional[threading.Event] = None,
         progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
+        worker_offset: int = 0,
     ) -> bool:
         """Download 1 aweme video/image"""
@@ -422,5 +424,6 @@ class Download:
                 cancel_event=eff_cancel,
                 progress_callback=progress_callback or self.progress_callback,
+                worker_offset=worker_offset,
             )
 
             if success:
@@ -451,7 +454,7 @@ class Download:
         cancel_event: Optional[threading.Event] = None,
         progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
-    ):
+    ) -> bool:
         """Download all aweme of user with threading"""
         eff_cancel = cancel_event or self.cancel_event
         if not awemeList:
-            return
+            return True
 
@@ -472,6 +475,6 @@ class Download:
             future_to_aweme = {
                 executor.submit(
-                    self.awemeDownload, aweme, save_path, eff_cancel, progress_callback
-                ): aweme
-                for aweme in awemeList
+                    self.awemeDownload, aweme, save_path, eff_cancel, progress_callback, idx % self.thread
+                ): aweme
+                for idx, aweme in enumerate(awemeList)
             }
@@ -494,4 +497,10 @@ class Download:
                     finally:
                         pbar.update(1)
+                        if progress_callback:
+                            progress_callback({
+                                "event": "item_complete",
+                                "item_index": success_count,
+                                "item_total": total_count,
+                            })
 
@@ -509,2 +518,3 @@ class Download:
             logger.warning(f"{total_count - success_count} video download failed")
+        return success_count > 0 or total_count == 0
 
@@ -550,4 +560,5 @@ class Download:
                 if response.status_code == 206:
                     total_size += file_size
                 mode = "ab" if file_size > 0 and response.status_code == 206 else "wb"
+                initial_bytes = file_size if response.status_code == 206 else 0
 
@@ -561,5 +572,5 @@ class Download:
                             "filename": filepath.name,
                             "chunk_bytes": 0,
-                            "downloaded_bytes": file_size,
+                            "downloaded_bytes": initial_bytes,
                             "total_bytes": total_size,
                             "desc": desc,
@@ -568,6 +579,7 @@ class Download:
 
                 last_emit_time = time.monotonic()
-                downloaded_so_far = file_size
+                downloaded_so_far = initial_bytes
+                accumulated_chunk_bytes = 0
                 with open(filepath, mode) as f:
                     with tqdm(
                         total=total_size,
-                        initial=file_size,
+                        initial=initial_bytes,
                         unit="B",
@@ -590,4 +602,5 @@ class Download:
                                     size = f.write(chunk)
                                     pbar.update(size)
                                     downloaded_so_far += size
+                                    accumulated_chunk_bytes += size
                                     if eff_callback:
                                         now = time.monotonic()
@@ -602,5 +615,5 @@ class Download:
                                                     "worker_id": worker_id,
                                                     "filepath": str(filepath),
                                                     "filename": filepath.name,
-                                                    "chunk_bytes": size,
+                                                    "chunk_bytes": accumulated_chunk_bytes,
                                                     "downloaded_bytes": downloaded_so_far,
                                                     "total_bytes": total_size,
                                                     "desc": desc,
                                                 }
                                             )
+                                            accumulated_chunk_bytes = 0
                                             last_emit_time = now
@@ -629,5 +642,5 @@ class Download:
                             "worker_id": worker_id,
                             "filepath": str(filepath),
                             "filename": filepath.name,
-                            "chunk_bytes": 0,
+                            "chunk_bytes": accumulated_chunk_bytes,
                             "downloaded_bytes": downloaded_so_far,
                             "total_bytes": total_size,
                             "desc": desc,
                         }
                     )
+                    accumulated_chunk_bytes = 0
```

---

### Patch 3: `tests/test_m1_core.py`

```diff
--- a/tests/test_m1_core.py
+++ b/tests/test_m1_core.py
@@ -941,6 +941,12 @@ class TestPreviewsAndEndToEnd:
             resp = manager.submit_task(req, douyin_service=mock_service)
-            # Allow worker thread to execute
-            time.sleep(0.1)
-
-            detail = manager.get_task(resp.task_id)
+            # Allow worker thread to execute (polling wait because time.sleep is monkeypatched)
+            deadline = time.monotonic() + 2.0
+            detail = manager.get_task(resp.task_id)
+            while time.monotonic() < deadline and detail.status not in (
+                TaskStatus.COMPLETED,
+                TaskStatus.FAILED,
+            ):
+                detail = manager.get_task(resp.task_id)
+
             assert detail.status == TaskStatus.COMPLETED
             assert detail.completed_items == 1
```

---

## 4. Rollout & Application Order for Implementer

1. Apply **Patch 2** to `src/douyin/download.py` first (enables `accumulated_chunk_bytes`, `worker_offset`, `initial_bytes`, and `userDownload` return type).
2. Apply **Patch 1** to `src/web/services/task_manager.py` (enforces `_task_semaphore`, `pause_event.set()` on cancel, delta telemetry tracking, and subscriber pruning).
3. Apply **Patch 3** to `tests/test_m1_core.py` (resolves monkeypatched sleep race condition).
4. Run full test suite:
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/test_m1_core.py tests/test_m1_concurrency_stress.py -v
   ```
   Expected: 53 passed, 0 failed.

---

## 5. Verification Method

- **Command**:
  ```powershell
  $env:PYTHONPATH='.'; .venv\Scripts\python.exe .agents/teamwork/teamwork_preview_explorer_m1_it2_3/test_verify_patches.py
  ```
  Returns exit code 0 and verifies telemetry delta calculation, pause-cancel unblock, subscriber queue pruning, and semaphore concurrency bounding.
