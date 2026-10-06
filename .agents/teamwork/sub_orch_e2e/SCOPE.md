# Scope: E2E Testing Track

## Architecture
- Independent, requirement-driven, opaque-box test track.
- Derive test cases directly from `ORIGINAL_REQUEST.md` and `PROJECT.md`, without coupling to internal implementation classes.
- Exercised via standard entry points:
  - CLI / module entry points
  - REST endpoints (`/api/*`)
  - Real-time streaming (`/api/stream`, `/ws/tasks`)
  - Storage artifacts (`./Downloaded/`)
  - Settings persistence (`config.yaml`)

## Feature Inventory Scope
All 35 inventoried features in `PROJECT.md § Feature Inventory` must be verified.

## Test Case Design Methodology (4 Tiers)
- **Tier 1 — Feature Coverage (>=5 per feature)**:
  - Happy-path tests verifying each feature in isolation using representative inputs.
  - Exit code and structured output verification.
- **Tier 2 — Boundary & Corner Cases (>=5 per feature)**:
  - Extreme inputs, empty strings, invalid characters, missing files, 0/negative numbers, max-size inputs, network disconnect simulation, range boundaries.
- **Tier 3 — Cross-Feature Combinations (Pairwise)**:
  - Concurrency + cancellation, incremental updates + like renaming, range resume + rate-limiting, custom cookies + multi-mode scraping.
- **Tier 4 — Real-World Application Scenarios (>=5)**:
  - Full end-to-end user workflows: parse link -> preview -> configure modes -> download multiple works -> verify files on disk -> query media library -> inspect settings -> open folder.

## Minimum Thresholds
- Tier 1: ≥5 per feature
- Tier 2: ≥5 per feature
- Tier 3: pairwise combinations of major features
- Tier 4: ≥5 realistic end-to-end workflows

## Deliverables
1. `TEST_INFRA.md` at project root outlining test runner, architecture, and feature coverage matrix.
2. Complete test suite in `tests/` with standalone test runner (`python -m pytest tests/` or dedicated runner script).
3. `TEST_READY.md` signaling that the E2E test suite is complete and ready for Implementation Track verification.
