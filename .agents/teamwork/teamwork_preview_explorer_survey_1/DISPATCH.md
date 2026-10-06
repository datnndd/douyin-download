# DISPATCH

## Objective
Survey existing Douyin download engine and CLI codebase in `c:\Users\ddat2\Downloads\Projects\douyin-download` to inform FastAPI web integration.

## Scope & Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Inspect `src/douyin/`, `main.py`, `config.yaml`, `requirements.txt` (or pyproject.toml) and all related modules.
3. Detail:
   - DouyinApi architecture, link parsing, supported URL formats (aweme, user post/like, mix, music, live).
   - Download engine architecture (`Download` class, threading model, resume/range requests, chunk downloads).
   - How progress callbacks or hooks can be attached to provide real-time metrics (speed, bytes, status) to SSE/WS.
   - Non-blocking execution strategy for FastAPI (ThreadPoolExecutor, asyncio.to_thread, task management).
   - File organization rules (`folderstyle`) and storage hierarchy.
   - Identified constraints, pitfalls, or potential bottlenecks.
4. Output: Write complete survey report to `report.md` and final state to `handoff.md` in your directory.
