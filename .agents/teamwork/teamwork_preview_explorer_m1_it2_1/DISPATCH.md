# DISPATCH — M1 Iteration 2 Explorer 1: Config & YAML Persistence Fix Strategy

## Objective
Formulate the exact fix strategy and code patches for `src/web/core/config.py` based on Reviewer 1 and Challenger 2 feedback.

## Defect Inventory to Resolve
1. **Nested Key Collision**: `_update_yaml_in_place_regex` updating scalar `music: True` matches and overwrites `number.music: 5` to `True`. Regex must require root-level indentation (`^(\s*)music:` with zero indent).
2. **Scalar Cookie Format Persistence**: When `config.yaml` has `cookie: "..."` scalar rather than `cookies:` mapping, updates were silently dropped. Must detect which format is present and update accordingly.
3. **Missing Fields**: `mode`, `number`, and `increase` settings were not saved back to `config.yaml`.
4. **YAML Special Characters**: Cookies with `@`, `*`, `{` were unquoted, breaking YAML syntax.
5. **In-Memory Cleanup**: Clearing cookies in settings must also clear `douyin_headers["Cookie"]`.

## Scope & Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Inspect `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_reviewer_m1_1\handoff.md`.
3. Inspect `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_challenger_m1_2\handoff.md`.
4. Write concrete remediation recommendations and validated code patches in `report.md` and deliver `handoff.md`.


## 2026-10-06T05:00:39Z
You are M1 Iteration 2 Explorer 1 (Config & YAML Remediation) for the Douyin Web Downloader project.
Your working directory is: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_1\
The authoritative user request is in: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md
Master project plan: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\orchestrator_1\PROJECT.md
Milestone scope: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\sub_orch_m1\SCOPE.md
Your dispatch details: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_1\DISPATCH.md
Project root: c:\Users\ddat2\Downloads\Projects\douyin-download

Reviewer and Challenger handoffs to inspect:
- Reviewer 1: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_reviewer_m1_1\handoff.md
- Challenger 2: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_challenger_m1_2\handoff.md

Instructions:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, SCOPE.md, DISPATCH.md, and reviewer/challenger handoffs.
2. Formulate concrete code fixes for src/web/core/config.py resolving nested key collision (music vs number.music), scalar cookie format save, missing mode/number/increase save, YAML quoting, and memory cookie cleanup.
3. Write your report to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_1\report.md.
4. Write handoff to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_1\handoff.md.
5. Send a completion message to the orchestrator.
