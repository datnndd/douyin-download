# DISPATCH — M1 Iteration 2 Explorer 2: Douyin Service & Security Fix Strategy

## Objective
Formulate the exact fix strategy and code patches for `src/web/services/douyin_service.py` and `src/web/core/schemas.py`.

## Defect Inventory to Resolve
1. **SSRF & Credential Exfiltration**: `resolve_redirect_url` used substring check (`"douyin.com" in url`), allowing attacker domains like `https://attacker.com/steal?target=v.douyin.com` to receive Douyin cookies. Must parse hostname using `urllib.parse.urlparse` and whitelist exact hostnames: `('v.douyin.com', 'douyin.com', 'www.douyin.com', 'iesdouyin.com', 'live.douyin.com')`.
2. **Per-Request Cookie Isolation**: Per-request custom cookies were overridden by global `douyin_headers['Cookie']`. Custom cookies must be passed via session headers without mutating global state.
3. **URL Scheme Normalization**: Raw inputs like `v.douyin.com/xxx` without `https://` should be prepended with `https://`.
4. **User Profile `mode == "mix"`**: Support `mode == "mix"` in `get_download_items`.
5. **Unclosed HTTP Response**: Ensure response is closed properly.
6. **Schema Validation Crashes**: `url_list: [None]` in upstream API responses crashes `AuthorPreview` and `PreviewMetadata`. Pre-validator must filter out `None` items.

## Scope & Instructions
1. Read `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md`.
2. Inspect `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_reviewer_m1_1\handoff.md`.
3. Inspect `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_challenger_m1_2\handoff.md`.
4. Write concrete remediation recommendations and validated code patches in `report.md` and deliver `handoff.md`.


## 2026-10-06T05:00:39Z
You are M1 Iteration 2 Explorer 2 (Douyin Service & Security Remediation) for the Douyin Web Downloader project.
Your working directory is: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_2\
The authoritative user request is in: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\ORIGINAL_REQUEST.md
Master project plan: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\orchestrator_1\PROJECT.md
Milestone scope: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\sub_orch_m1\SCOPE.md
Your dispatch details: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_2\DISPATCH.md
Project root: c:\Users\ddat2\Downloads\Projects\douyin-download

Reviewer and Challenger handoffs to inspect:
- Reviewer 1: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_reviewer_m1_1\handoff.md
- Challenger 2: c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_challenger_m1_2\handoff.md

Instructions:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, SCOPE.md, DISPATCH.md, and reviewer/challenger handoffs.
2. Formulate concrete code fixes for src/web/services/douyin_service.py and src/web/core/schemas.py resolving SSRF/cookie leakage (strict hostname validation), per-request cookie isolation, URL scheme normalization, mode=="mix", unclosed responses, and url_list: [None] crashes.
3. Write your report to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_2\report.md.
4. Write handoff to c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_2\handoff.md.
5. Send a completion message to the orchestrator.
