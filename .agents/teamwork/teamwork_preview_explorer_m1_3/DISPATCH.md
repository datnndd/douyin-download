# DISPATCH — M1 Explorer 3: Task Manager & Concurrency

## Objective
Plan the implementation of `src/web/services/task_manager.py` and progress callback hooks in `src/douyin/download.py`.

## Scope & Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Read master project plan `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\orchestrator_1\PROJECT.md`.
3. Read M1 scope `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\sub_orch_m1\SCOPE.md`.
4. Inspect `src/douyin/download.py` and `douyinCommand.py`.
5. Formulate precise implementation plan for:
   - `src/douyin/download.py` enhancements:
     - Add non-breaking optional `progress_callback` hook to `Download.__init__` and download loops (`download_with_resume`, `awemeDownload`, `userDownload`).
     - Emit `DownloadProgressEvent` throttled to ~250ms to prevent event loop flooding.
     - Support cancellation checks via a `cancel_event: threading.Event` token inside chunk loops.
   - `src/web/services/task_manager.py`:
     - Centralized `TaskManager` singleton managing background jobs.
     - ThreadPoolExecutor with bounded worker limits to prevent thread explosion.
     - Event subscriber queues (`asyncio.Queue`) for real-time SSE telemetry.
     - Thread states tracking (active thread id, file being downloaded, progress %).
     - Lifecycle states: `PENDING`, `PARSING`, `DOWNLOADING`, `COMPLETED`, `FAILED`, `CANCELLED`.
6. Output: Write detailed findings and implementation recommendations to `report.md` and summary in `handoff.md`.


## 2026-10-06T04:12:43Z
You are M1 Explorer 3 (Task Manager & Concurrency) for the Douyin Web Downloader project.
Your working directory is: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_3\
The authoritative user request is in: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md
Master project plan: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\orchestrator_1\PROJECT.md
Milestone scope: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\sub_orch_m1\SCOPE.md
Your dispatch details: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_3\DISPATCH.md
Project root: c:\Users\ddat2\Downloads\Projects\douyin-download

Instructions:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, SCOPE.md, and DISPATCH.md.
2. Inspect src/douyin/download.py and douyinCommand.py.
3. Plan src/web/services/task_manager.py and non-breaking progress hooks in src/douyin/download.py:
   - Add optional progress_callback hook emitting DownloadProgressEvent throttled to ~250ms.
   - Cancellation token (threading.Event) support in chunk download loops.
   - Centralized TaskManager with bounded ThreadPoolExecutor, job state machine, asyncio.Queue event distribution for SSE, and thread states visualizer tracking.
4. Write your comprehensive report to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_3\report.md.
5. Write your handoff report to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_3\handoff.md.
6. When complete, send a message to your orchestrator reporting completion and summarizing key findings.
