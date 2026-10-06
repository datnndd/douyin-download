# DISPATCH

## Objective
Mine authoritative API specifications, data models, endpoints, and behavioral contracts for the Douyin Web Downloader application.

## Scope & Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Inspect `config.yaml` and `src/` in `c:\Users\ddat2\Downloads\Projects\douyin-download`.
3. Produce a rigorous API and behavioral contract specification:
   - Full REST endpoints:
     - `POST /api/parse`: URL resolution, metadata extraction, preview payload.
     - `POST /api/download`: Task creation, configuration options, task ID returned.
     - `GET /api/tasks` & `GET /api/tasks/{task_id}`: Task status, metrics, thread states.
     - `GET /api/stream` or WebSocket `/ws/tasks`: Real-time streaming schema.
     - `GET /api/settings` & `POST /api/settings`: Read/write config.yaml.
     - `GET /api/media` & `GET /api/media/stream/{file_path}`: Media library listing and streaming.
     - `POST /api/open-folder`: Trigger opening folder in Windows Explorer.
   - Pydantic models for all requests and responses.
   - Task lifecycle state machine (IDLE -> PARSING -> DOWNLOADING -> COMPLETED / FAILED / CANCELLED).
   - Error handling contracts and HTTP status codes.
4. Output: Write complete specification report to `report.md` and final state to `handoff.md` in your directory.

## 2026-10-06T03:51:18Z
You are Specification Miner (API) for the Douyin Web Downloader project.
Your working directory is: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_spec_miner_survey_3\
The authoritative user request is in: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md
Your dispatch details are in: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_spec_miner_survey_3\DISPATCH.md
Project root: c:\Users\ddat2\Downloads\Projects\douyin-download

Instructions:
1. Read ORIGINAL_REQUEST.md and DISPATCH.md first.
2. Inspect config.yaml and src/ in c:\Users\ddat2\Downloads\Projects\douyin-download to understand existing data models and options.
3. Mine the authoritative API contracts and behavioral specification:
   - Full REST endpoints:
     - POST /api/parse: URL resolution, metadata extraction, preview payload.
     - POST /api/download: Task creation, configuration options, task ID returned.
     - GET /api/tasks & GET /api/tasks/{task_id}: Task status, metrics, thread states.
     - SSE (/api/stream) or WebSocket (/ws/tasks): Real-time streaming schema.
     - GET /api/settings & POST /api/settings: Read/write config.yaml.
     - GET /api/media & GET /api/media/stream/{file_path}: Media library listing and streaming.
     - POST /api/open-folder: Trigger opening folder in Windows Explorer.
   - Pydantic models for all requests and responses.
   - Task lifecycle state machine (IDLE -> PARSING -> DOWNLOADING -> COMPLETED / FAILED / CANCELLED).
   - Error handling contracts and HTTP status codes.
4. Write your comprehensive report to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_spec_miner_survey_3\report.md.
5. Write your handoff report to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_spec_miner_survey_3\handoff.md.
6. When complete, send a message to your orchestrator reporting completion and summarizing key findings.

## 2026-10-06T03:56:15Z
System notification: Stream interrupted, resuming task execution.
