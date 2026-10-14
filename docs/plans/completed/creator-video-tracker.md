# Execution Plan: Creator Video Tracking & One-Click Update Mechanism

Date: 2026-10-14

## Status

Completed

## Outcome

Build a change tracking system for Douyin creators that detects new video uploads using minimal storage and bandwidth, and provides a 1-Click "Update" button in the Web UI to download only the newly added videos.

## Context

- `AGENTS.md` & `docs/WORKFLOW.md`: Repository workflow and system of record.
- `src/douyin/database.py`: SQLite persistence layer.
- `src/web/services/douyin_service.py`: Douyin API integration and preview extraction.
- `src/web/services/task_manager.py`: Download task execution engine.
- `frontend/src/components/UnifiedDownloader.tsx`: Main download workspace and Creator Hero card.
- `frontend/src/components/Header.tsx` & `frontend/src/App.tsx`: Navigation and layout.

## Scope

In scope:
- Ultra-lightweight database tables (`tracked_creators`, `tracked_video_log`) storing strictly identifiers and timestamps (<100 bytes per record; zero raw JSON dumps).
- Incremental change detection algorithm filtering pinned videos (`is_top`) and terminating early at the last seen `aweme_id`.
- 1-Click Update action submitting download tasks directly for newly detected items with default settings.
- "Tracked Creators" navigation tab and grid view with real-time pending update badge counter.
- Creator Hero card enhancements in Unified Downloader with "+ Track Creator" and "UPDATE (X NEW VIDEOS)" buttons.
- On-demand and optional background interval checks.
- Comprehensive automated test suite (`tests/test_tracker_service.py`) and passing full test suite.

Out of scope:
- Scraping comments or heavy statistical engagement curves over time.
- Modifying Douyin upstream bot protection or cookies.

## Approach

1. **Database Extension (`src/douyin/database.py`)**:
   - Add `tracked_creators` and `tracked_video_log` tables and minimal CRUD methods.
2. **Service Layer (`src/web/services/tracker_service.py`)**:
   - Implement incremental checking, pinned video handling, and one-click update task dispatcher.
3. **API Layer (`src/web/api/tracker.py`)**:
   - Expose endpoints for creator tracking, checking updates, 1-click update triggering, and stats.
   - Mount router in `src/web/api/router.py`.
4. **Configuration & Schemas (`src/web/core/schemas.py`, `src/web/core/config.py`)**:
   - Add tracker request/response models and settings persistence.
5. **Frontend Implementation**:
   - Update `types/api.ts` and `services/api.ts`.
   - Add "Tracked Creators" tab and badge counter in `Header.tsx` and `App.tsx`.
   - Create `TrackedCreators.tsx` component.
   - Add "+ Track Creator" and "UPDATE (X NEW VIDEOS)" to Creator Hero card in `UnifiedDownloader.tsx`.
6. **Automated Verification**:
   - Write unit tests in `tests/test_tracker_service.py`.
   - Run `tests/run_tests.py` and frontend `npm run build`.

## Risks And Recovery

- *Risk*: Pinned videos (`is_top == 1`) appearing at the top of the feed despite having older create dates could trick naive cursor checks into thinking there are new videos.
  *Mitigation*: Filter out pinned videos when evaluating the newest video baseline.
- *Risk*: Excessive API calls if many creators are tracked.
  *Mitigation*: Rate-limit background checks with delay jitter and stop pagination on the very first page (18 items) as soon as `last_aweme_id` is seen.

## Progress

- [x] Add `tracked_creators` and `tracked_video_log` tables to `src/douyin/database.py`.
- [x] Implement `src/web/services/tracker_service.py`.
- [x] Add `src/web/api/tracker.py` and mount in `src/web/api/router.py`.
- [x] Add schemas and config options.
- [x] Implement frontend tracker API and types.
- [x] Create `frontend/src/components/TrackedCreators.tsx`.
- [x] Update `Header.tsx`, `App.tsx`, and `UnifiedDownloader.tsx`.
- [x] Write tests in `tests/test_tracker_service.py` and verify all tests pass.

## Decisions

- 2026-10-14: Dedicated 'Tracked Creators' tab in navigation with pending badge counter, plus 'Update' action on Creator card when pasting tracked URLs.
- 2026-10-14: '+ Track Creator' button on preview card, setting current latest video as baseline.
- 2026-10-14: 1-Click Update immediately submits background download task using default settings without modal hurdles.
- 2026-10-14: Store minimal metadata only (IDs, timestamps, status, titles truncated for UI), zero raw API dumps.

## Validation

- Focused proof: `pytest tests/test_tracker_service.py` (8 passed in 0.57s)
- Integration proof: `python tests/run_tests.py` (all 202 offline tests across Tiers 1-5 passing in 5.01s)
- UI build proof: `npm run build` in `frontend/` (built cleanly with 0 TypeScript/Vite errors in 4.64s)

## Result

Implementation complete and verified. Creator tracking and 1-Click Update mechanism successfully built across backend, API, database, and frontend.
