# DISPATCH — E2E Testing Track Orchestrator

## Objective
Orchestrate the design, implementation, and verification of the independent E2E test suite across Tiers 1-4 per `SCOPE.md` and `PROJECT.md`.

## Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md` and `SCOPE.md`.
2. Follow the Project Pattern 2B iteration loop:
   - Spawn Explorers / Spec Miners to establish test fixtures, mock servers (for upstream Douyin API responses), and test runners.
   - Spawn Test Writers (`teamwork_preview_test_writer` or workers) to implement test cases across Tiers 1-4 in `tests/`.
   - Spawn Reviewers to ensure opaque-box requirements compliance, tier coverage thresholds, and independence from internal classes.
   - Spawn Challengers to verify that tests correctly fail on broken behavior (assert sensitivity) and pass on valid behavior.
   - Spawn Forensic Auditor to verify test integrity.
3. Once all gate checks pass:
   - Publish `c:\Users\ddat2\Downloads\Projects\douyin-download\TEST_INFRA.md`.
   - Publish `c:\Users\ddat2\Downloads\Projects\douyin-download\TEST_READY.md`.
   - Submit `handoff.md` and report completion to parent orchestrator (`5e8a0791-8c15-483c-9053-9b4640dea1c2`).
