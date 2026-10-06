# DISPATCH — Milestone 1: Backend Engine & Task Concurrency

## Objective
Orchestrate the development, verification, and forensic audit of Milestone 1 per `SCOPE.md` and `PROJECT.md`.

## Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md` and `SCOPE.md`.
2. Follow the Project Pattern 2B iteration loop:
   - Spawn 3 Explorers (`teamwork_preview_explorer`) to inspect existing `src/douyin/` files, design schemas, and formulate implementation strategy.
   - Spawn 1 Worker (`teamwork_preview_worker`) with Explorer findings to implement the service layer, schemas, task manager, and progress hooks, and run unit tests.
   - Spawn 2 Reviewers (`teamwork_preview_reviewer`) independently to inspect code quality, edge cases, and interface conformance.
   - Spawn 2 Challengers (`teamwork_preview_challenger`) to stress-test concurrency, cancellation, range resumption, and error handling.
   - Spawn 1 Forensic Auditor (`teamwork_preview_auditor`) to verify implementation authenticity and integrity.
   - Evaluate Gate verdicts in `GATE_STATUS.md`. Loop if needed until all pass.
3. Upon gate passing, submit `handoff.md` and send completion message to parent orchestrator (`5e8a0791-8c15-483c-9053-9b4640dea1c2`).
