# Execution Plan: Unified Single-Screen Downloader with Custom Naming and Filters

Date: 2026-10-07

## Status

Completed

## Outcome

Eliminated the sequential multi-step wizard in the Douyin downloader frontend. Delivered a unified, single-screen download workspace with:
1. Direct URL input with auto-preview (debounced 600ms) and an immediate "TẢI XUỐNG NGAY" (Download Now) action.
2. Immediate configuration panel for save directory, media assets (video, audio, cover, avatar, json), thread count, and subfolder grouping.
3. Configurable file naming pattern (Filename Template) with presets (`{date}_{title}_{id}`, `{likes}likes_{date}_{title}`, `{title}_{id}`, `{author}_{title}_{id}`, `{id}`, etc.) and custom pattern inputs with live filename preview.
4. Dynamic filters for user profile / creator downloads: start date (`start_time`), end date (`end_time`), and work limit (`number`), automatically highlighted when a user link is detected and toggleable at any time.
5. Real-time telemetry and task tracker directly integrated on the same page.
6. Backend schema and download engine support for filename templates with placeholder resolution and filename sanitization.

## Context

- `frontend/src/App.tsx`: Replaced two-step wizard with `UnifiedDownloader.tsx`.
- `frontend/src/components/UnifiedDownloader.tsx`: Created unified workspace component.
- `src/web/core/schemas.py`: Added `filename_template` to `DownloadRequest` and `SettingsModel`.
- `src/douyin/download.py`: Downloader engine formats output filenames according to `filename_template` while retaining backward-compatibility with fallback naming.
- `src/web/core/config.py`: Persistence for `filename_template` in `config.yaml`.
- Aesthetic reference: `pyvideotrans` warm ivory palette (`#FAF8F5`, `#8D4B00`, `#F3ECE2`).

## Scope

In scope:
- Refactor frontend components into a unified single-screen component `UnifiedDownloader.tsx` (replacing Step1 & Step2 wizard).
- Add filename pattern selector with presets and custom template input in frontend and backend.
- Add user profile date range picker (`start_time`, `end_time`) and video limit (`number`) with auto-reveal for user links.
- Add save path selector with Windows Explorer opening action.
- Update `DownloadRequest` in `src/web/core/schemas.py`, `src/web/services/task_manager.py`, and `src/douyin/download.py`.
- Update and pass all frontend and backend tests.

Out of scope:
- Modifying Douyin WAF security mechanisms (already solved with `.cookies.json` and `ConfigManager`).
- Breaking CLI backward compatibility (`douyinCommand.py` continues to work with default naming).

## Approach

1. **Backend Schema & Downloader Engine Extension**:
   - Added `filename_template: Optional[str] = "{date}_{title}_{id}"` to `DownloadRequest` in `src/web/core/schemas.py`.
   - Updated `Download` class in `src/douyin/download.py` to accept `filename_template` and implemented `_format_file_name(...)` replacing `{date}`, `{title}`, `{id}`, `{author}`, `{likes}`, `{type}` with sanitized strings.
   - Passed `filename_template` in `TaskManager._run_task_pipeline` to `Download`.
2. **Frontend Unified Screen Implementation**:
   - Created `frontend/src/components/UnifiedDownloader.tsx`.
   - Updated `frontend/src/App.tsx` to render `UnifiedDownloader` and `TaskTracker` directly on one single screen.
   - Updated `frontend/src/types/api.ts` to include `filename_template` in `DownloadRequest` and `SettingsModel`.
3. **Verification**:
   - Ran `npm run build` in `frontend/` (0 TypeScript / JSX errors, built in 3.83s).
   - Ran python test suite `tests/run_tests.py` (194/194 passed, 100%).
   - Ran unit test suite `tests/test_filename_template.py` (7/7 passed, 100%).

## Progress

- [x] Update backend `DownloadRequest` schema with `filename_template`.
- [x] Implement `filename_template` rendering in `src/douyin/download.py`.
- [x] Update `TaskManager` in `src/web/services/task_manager.py`.
- [x] Update frontend types in `frontend/src/types/api.ts`.
- [x] Implement `frontend/src/components/UnifiedDownloader.tsx`.
- [x] Integrate into `frontend/src/App.tsx`.
- [x] Run Vite frontend build and Python test suite.

## Decisions

- 2026-10-07: Default filename template selected as `{date}_{title}_{id}` (per user confirmation), with full user choice and custom pattern input in UI.
- 2026-10-07: Auto-preview on link paste/input with debounce 600ms; "TẢI XUỐNG NGAY" can be clicked immediately without waiting for preview.
- 2026-10-07: Date filters (`start_time`, `end_time`) and video limit (`number`) auto-expand for user profile links and can be toggled anytime.

## Validation

- Focused proof: `pytest tests/test_filename_template.py` - 7 passed in 0.06s.
- Integration proof: `python tests/run_tests.py` - 194 passed in 3.97s (100%).
- UI build proof: `npm run build` completed cleanly (dist/ generated with 0 errors).

## Result

Unified single-screen interface fully implemented and verified. All requirements satisfied with 100% test pass rate.
