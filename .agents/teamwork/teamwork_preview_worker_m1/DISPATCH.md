# DISPATCH — Milestone 1 Worker: Backend Engine & Task Concurrency

## Objective
Implement Milestone 1: Backend Engine & Task Concurrency per `SCOPE.md` and Explorer findings.

## Explorer Deliverables to Integrate
1. Explorer 1 (`teamwork_preview_explorer_m1_1`):
   - `proposed_schemas.py` -> `src/web/core/schemas.py`
   - `proposed_config.py` -> `src/web/core/config.py`
2. Explorer 2 (`teamwork_preview_explorer_m1_2`):
   - `report.md` -> `src/web/services/douyin_service.py`
3. Explorer 3 (`teamwork_preview_explorer_m1_3`):
   - `download_progress_cancel.patch` -> `src/douyin/download.py`
   - `proposed_task_manager.py` -> `src/web/services/task_manager.py`

## Exclusive File Ownership
- `requirements.txt`
- `src/web/__init__.py`
- `src/web/core/__init__.py`
- `src/web/core/config.py`
- `src/web/core/schemas.py`
- `src/web/services/__init__.py`
- `src/web/services/douyin_service.py`
- `src/web/services/task_manager.py`
- `src/douyin/download.py`
- `tests/test_m1_core.py`

## Instructions
1. Read `ORIGINAL_REQUEST.md`, `PROJECT.md`, `SCOPE.md`.
2. Inspect the 3 Explorer handoffs and reference files.
3. Update `requirements.txt` to include `fastapi>=0.110.0`, `uvicorn>=0.28.0`, `pydantic>=2.6.0`, `pyyaml>=6.0.1`, `python-multipart>=0.0.9`.
4. Apply the progress and cancel hooks to `src/douyin/download.py` while ensuring backward compatibility with CLI.
5. Create `src/web/core/schemas.py` and `src/web/core/config.py`.
6. Create `src/web/services/douyin_service.py` and `src/web/services/task_manager.py`.
7. Write and run unit tests in `tests/test_m1_core.py` verifying:
   - Config loading, cookie parsing, YAML preservation.
   - Pydantic schema validation for requests and responses.
   - DouyinService link extraction and parsing logic.
   - TaskManager job creation, status progression, SSE queue events, throttled updates, and cancellation.
8. Document exact build and test commands and results in your `handoff.md`.

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## 2026-10-06T04:27:47Z
You are Milestone 1 Worker for the Douyin Web Downloader project.
Your working directory is: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_worker_m1\
The authoritative user request is in: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md
Master project plan: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\orchestrator_1\PROJECT.md
Milestone scope: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\sub_orch_m1\SCOPE.md
Your dispatch details: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_worker_m1\DISPATCH.md
Project root: c:\Users\ddat2\Downloads\Projects\douyin-download

Explorer Findings and Artifacts to inspect:
- Explorer 1: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_1\ (report.md, proposed_schemas.py, proposed_config.py)
- Explorer 2: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_2\ (report.md, handoff.md)
- Explorer 3: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_3\ (report.md, download_progress_cancel.patch, proposed_task_manager.py)

Exclusive File Ownership:
- requirements.txt
- src/web/__init__.py
- src/web/core/__init__.py
- src/web/core/config.py
- src/web/core/schemas.py
- src/web/services/__init__.py
- src/web/services/douyin_service.py
- src/web/services/task_manager.py
- src/douyin/download.py (applying progress & cancellation hooks)
- tests/test_m1_core.py
