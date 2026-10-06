# DISPATCH — M1 Iteration 2 Explorer 3: TaskManager Telemetry & Concurrency Fix Strategy

## Objective
Formulate the exact fix strategy and code patches for `src/web/services/task_manager.py` and `src/douyin/download.py`.

## Defect Inventory to Resolve
1. **Telemetry Breakdown**: `record.total_bytes` was never updated (stayed 0) and progress stayed at 0.0% until jump to 100%. Intermediate chunks were lost in throttling. Throttling must accumulate chunk bytes so `downloaded_bytes` reflects the actual delta.
2. **False Success on Download Failures**: In `_run_aweme_download`, the boolean return of `downloader.awemeDownload` must be checked; if false, mark task as `FAILED`.
3. **Zombie Thread Deadlock on Pause/Cancel**: Cancelling a paused task leaves threads blocked on `pause_event.wait()`. `cancel_task` must set `pause_event.set()` to unblock worker threads immediately.
4. **Concurrency Cap Dead Code**: `max_concurrent_tasks` must be enforced via a `threading.Semaphore` before submitting jobs.
5. **Pending Cancel Race Condition**: Check `cancel_event.is_set()` before broadcasting `PARSING` status.
6. **Subscriber Memory Leak**: Unsubscribe or prune queues when task completes or fails.

## Scope & Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Inspect `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_reviewer_m1_2\handoff.md`.
3. Inspect `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_challenger_m1_1\handoff.md`.
4. Write concrete remediation recommendations and validated code patches in `report.md` and deliver `handoff.md`.


## 2026-10-06T05:00:39Z
You are M1 Iteration 2 Explorer 3 (TaskManager & Concurrency Remediation) for the Douyin Web Downloader project.
Your working directory is: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_3\
The authoritative user request is in: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md
Master project plan: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\orchestrator_1\PROJECT.md
Milestone scope: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\sub_orch_m1\SCOPE.md
Your dispatch details: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_3\DISPATCH.md
Project root: c:\Users\ddat2\Downloads\Projects\douyin-download

Reviewer and Challenger handoffs to inspect:
- Reviewer 2: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_reviewer_m1_2\handoff.md
- Challenger 1: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_challenger_m1_1\handoff.md

Instructions:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, SCOPE.md, DISPATCH.md, and reviewer/challenger handoffs.
2. Formulate concrete code fixes for src/web/services/task_manager.py and src/douyin/download.py resolving telemetry progress & chunk accumulation, false success on download failure, zombie thread deadlock on pause/cancel, max_concurrent_tasks enforcement, and subscriber queue pruning.
3. Write your report to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_3\report.md.
4. Write handoff to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_3\handoff.md.
5. Send a completion message to the orchestrator.
