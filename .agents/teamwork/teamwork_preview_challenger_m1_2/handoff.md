# Milestone 1 Challenger 2 Handoff Report: Edge Cases & Fault Invariants

**Agent:** `teamwork_preview_challenger_m1_2`  
**Milestone:** Milestone 1 — Backend Engine & Task Concurrency  
**Date:** 2026-10-06  
**Verdict:** `REQUEST_CHANGES`  
**Overall Risk Assessment:** `CRITICAL`  

---

## 1. Observation

1. **Test Execution & Baseline Commands**:
   - Baseline command: `.venv\Scripts\python.exe -m pytest tests/test_m1_core.py -v` (43 passed initially in isolation).
   - Adversarial test command: `.venv\Scripts\python.exe -m pytest tests/test_m1_challenger2_edge_cases.py -v`
   - Output: 50 tests executed; 43 PASSED, 7 FAILED with reproducible faults:
     ```
     FAILED tests/test_m1_challenger2_edge_cases.py::TestAdversarialSecurityAndDomainValidation::test_domain_spoofing_in_resolve_redirect
     FAILED tests/test_m1_challenger2_edge_cases.py::TestYamlConfigPersistenceAndInvariants::test_save_config_cookie_format_persistence_bug
     FAILED tests/test_m1_challenger2_edge_cases.py::TestYamlConfigPersistenceAndInvariants::test_save_config_drops_mode_number_and_increase_fields
     FAILED tests/test_m1_challenger2_edge_cases.py::TestYamlConfigPersistenceAndInvariants::test_save_config_cookie_special_yaml_indicators_syntax_corruption
     FAILED tests/test_m1_challenger2_edge_cases.py::TestCookieParsingAndHeaderSync::test_cookie_clearing_header_sync_bug
     FAILED tests/test_m1_challenger2_edge_cases.py::TestSchemaValidationAndBoundaryInvariants::test_author_preview_url_list_containing_none_crash
     FAILED tests/test_m1_challenger2_edge_cases.py::TestSchemaValidationAndBoundaryInvariants::test_preview_metadata_cover_url_containing_none_crash
     ```
   - Concurrency Race Condition in `tests/test_m1_core.py:946`:
     ```
     FAILED tests/test_m1_core.py::TestPreviewsAndEndToEnd::test_task_manager_pipeline_execution_completion
     AssertionError: assert <TaskStatus.DOWNLOADING: 'DOWNLOADING'> == <TaskStatus.COMPLETED: 'COMPLETED'>
     ```

2. **Codebase Specific Observations**:
   - **Fault 1 (CRITICAL - SSRF & Cookie Exfiltration)**:
     - `src/web/services/douyin_service.py` line 208:
       ```python
       if "v.douyin.com" in url or "iesdouyin.com/share" in url:
           resp = session.get(
               url,
               headers=douyin_headers,
               allow_redirects=True,
               timeout=10,
               stream=True,
           )
       ```
       The condition uses an unanchored substring check (`"v.douyin.com" in url`). When supplied with `https://attacker.com/leak?target=v.douyin.com` or `https://v.douyin.com.evil.com/leak`, `session.get(url, headers=douyin_headers, ...)` transmits the user's Douyin session cookies to the external host.
   - **Fault 2 (HIGH - Cookie Persistence Failure on `cookie:` Format)**:
     - `src/web/core/config.py` lines 139–160:
       ```python
       if settings.cookies:
           ...
           cookies_pattern = r"^cookies:[ \t]*(?:\r?\n[ \t]+[^\r\n]+)*"
           if re.search(cookies_pattern, text, flags=re.MULTILINE):
               text = re.sub(cookies_pattern, lambda m: new_cookies_block, text, flags=re.MULTILINE)
       elif settings.raw_cookie:
           escaped_cookie = settings.raw_cookie.replace('"', '\\"')
           text = replace_scalar(text, "cookie", f'"{escaped_cookie}"')
       ```
       When `config.yaml` uses the single-string format `cookie: "..."`, `load_config_file` automatically populates `settings.cookies`. Subsequent saves take the `if settings.cookies:` branch, fail to find `^cookies:`, and skip the `elif settings.raw_cookie:` branch. Cookie edits are silently dropped on disk.
   - **Fault 3 (HIGH - Data Loss for `number`, `mode`, `increase`)**:
     - `src/web/core/config.py` lines 85–160: `_update_yaml_in_place_regex` completely lacks replacers for `mode`, `number`, and `increase`. Updates to work limits, modes, or incremental switches are lost on every save.
   - **Fault 4 (HIGH - YAML Corruption on Reserved Indicators)**:
     - `src/web/core/config.py` lines 142–146:
       ```python
       if ":" in clean_v or "#" in clean_v or "%" in clean_v:
           cookie_lines.append(f'  {k}: "{clean_v}"')
       else:
           cookie_lines.append(f"  {k}: {clean_v}")
       ```
       Cookie values starting with YAML indicator tokens (`@`, `*`, `{`, `[`, or ending in `\`) are emitted unquoted. On restart, `yaml.safe_load()` fails with `yaml.scanner.ScannerError` or `yaml.composer.ComposerError`, causing `load_config_file` to wipe configuration back to default.
   - **Fault 5 (MEDIUM - In-Memory Stale Cookie Leak on Clear)**:
     - `src/web/core/config.py` line 425:
       ```python
       cookie_str = self.get_cookie_header()
       if not cookie_str:
           return
       douyin_headers["Cookie"] = cookie_str
       ```
       When cookies are cleared (`{}` or `""`), `apply_to_douyin_headers` returns early without deleting `douyin_headers["Cookie"]`, leaving old credentials active in memory.
   - **Fault 6 & 7 (MEDIUM - Schema Validation Crashes on Null in `url_list`)**:
     - `src/web/core/schemas.py` lines 160–164 and 201–205:
       ```python
       if isinstance(v, dict):
           url_list = v.get("url_list", [])
           return url_list[0] if url_list else ""
       ```
       When Douyin API returns `url_list: [None]`, `url_list[0]` is `None`. Returning `None` triggers a Pydantic `ValidationError` on `avatar_thumb: str` and `cover_url: str`, causing `/api/parse` to crash with HTTP 500.
   - **Fault 8 (LOW - Test Concurrency Race Condition)**:
     - `tests/test_m1_core.py` lines 942–946: `time.sleep(0.1)` fails intermittently under multi-test execution due to scheduler delay.

---

## 2. Logic Chain

1. **Observation 1 & 2 -> Critical Security Hazard**:
   - `DouyinService.resolve_redirect_url` is intended to resolve Douyin shortlinks (`v.douyin.com`).
   - By using a raw string containment check (`"v.douyin.com" in url`) rather than parsed domain validation (`urlsplit(url).netloc == "v.douyin.com"`), any domain containing `v.douyin.com` anywhere in its URL or query parameters triggers an HTTP request with `douyin_headers`.
   - Because `douyin_headers` includes `Cookie`, any attacker who entices the web app to parse an adversarial link will receive the user's Douyin session cookies. This constitutes an immediate security vulnerability.
2. **Observation 1 & 2 -> Configuration Integrity Failure**:
   - The user request explicitly demands: *"Save and load settings reliably from `config.yaml` without corrupting file structure."*
   - Because `_update_yaml_in_place_regex` fails to quote YAML indicators, any cookie token containing `@`, `*`, `{`, etc., corrupts the YAML file.
   - Upon next startup, `yaml.safe_load` throws an exception, triggering `load_config_file`'s fallback, which resets user settings to defaults.
   - Furthermore, `cookie:` single-line format edits are completely ignored, and fields `mode`, `number`, and `increase` are never written to disk.
3. **Observation 1 & 2 -> Runtime Fragility Against Upstream Data**:
   - Douyin's internal JSON responses frequently return null or missing CDN mirrors (`"url_list": [None]`).
   - `AuthorPreview` and `PreviewMetadata` validators assume `url_list[0]` is a non-null string. When it is `None`, Pydantic validation fails and crashes the application.
4. **Conclusion Derivation**:
   - A critical security vulnerability, configuration corruption, silent setting drops, and schema crashes violate core system invariants and require targeted remediations before Milestone 1 can be approved for Milestone 2 API routing.

---

## 3. Adversarial Challenge Analysis

### Challenge 1 (CRITICAL): SSRF & Douyin Cookie Exfiltration
- **Assumption challenged**: Substring match `"v.douyin.com" in url` safely identifies legitimate Douyin shortlinks.
- **Attack scenario**: Attacker passes `https://attacker.com/steal?target=v.douyin.com` or `https://v.douyin.com.evil.com/leak` to `POST /api/parse`.
- **Blast radius**: `session.get(url, headers=douyin_headers)` fires with full user cookie headers to an untrusted domain.
- **Mitigation**: Parse domain using `urllib.parse.urlsplit(url).netloc.lower()`. Only follow redirects if the host is strictly in `{"v.douyin.com", "iesdouyin.com"}` or ends with `.douyin.com`. Do not forward session cookies on cross-origin redirects.

### Challenge 2 (HIGH): Config Corruption via Unquoted YAML Cookie Tokens
- **Assumption challenged**: Quoting only values with `:`, `#`, `%` is sufficient for valid YAML.
- **Attack scenario**: A user pastes a cookie token beginning with `@` (e.g. `@token`), `*`, `{`, or ending in `\`.
- **Blast radius**: Generates unparseable YAML on disk. On restart, `load_config_file` catches `YAMLError` and resets the user's entire config back to defaults.
- **Mitigation**: Use `json.dumps(val)` or `yaml.safe_dump` to generate properly quoted/escaped YAML scalar strings.

### Challenge 3 (HIGH): Dual Cookie Format Persistence Failure
- **Assumption challenged**: `save_config_file` handles both `cookies:` and `cookie:` representations.
- **Attack scenario**: Existing `config.yaml` uses `cookie: "msToken=abc;"`. User updates cookie in UI.
- **Blast radius**: `_update_yaml_in_place_regex` only looks for `^cookies:` mapping when `settings.cookies` is non-empty, skipping the `cookie:` scalar update. Cookie changes are silently lost.
- **Mitigation**: In `_update_yaml_in_place_regex`, check if `cookies:` or `cookie:` exists in the text. Update whichever is present.

### Challenge 4 (HIGH): Silent Dropping of `mode`, `number`, and `increase`
- **Assumption challenged**: `_update_yaml_in_place_regex` updates all settings in `SettingsModel`.
- **Attack scenario**: User updates download limits (`number.post = 10`), modes (`mode: ["post", "like"]`), or incremental toggles.
- **Blast radius**: `_update_yaml_in_place_regex` ignores these fields. Values are lost upon save.
- **Mitigation**: Implement scalar/dictionary regex updates for `mode`, `number`, and `increase` blocks in `_update_yaml_in_place_regex`.

### Challenge 5 (MEDIUM): Stale In-Memory Cookie on Clear
- **Assumption challenged**: Early return when `cookie_str` is empty is safe.
- **Attack scenario**: User clears cookies to log out.
- **Blast radius**: `douyin_headers["Cookie"]` retains old token in memory.
- **Mitigation**: If `not cookie_str`, set `douyin_headers.pop("Cookie", None)`.

### Challenge 6 (MEDIUM): Schema Crash on Null Element in `url_list`
- **Assumption challenged**: `url_list` elements are always valid strings.
- **Attack scenario**: Douyin CDN response returns `{"url_list": [None]}`.
- **Blast radius**: Pydantic `ValidationError` crashes preview parsing.
- **Mitigation**: In `extract_avatar_url` and `extract_cover_url`, verify `isinstance(url_list[0], str)` and fall back to `""`.

---

## 4. Caveats

- Milestone 1 tests were conducted against core engine files without FastAPI web server routes mounted (Milestone 2 scope).
- 43 standard functional tests in `test_m1_core.py` pass when isolated, confirming basic URL extraction and threading mechanics work when not subjected to edge cases or adversarial input.

---

## 5. Conclusion

**Verdict:** `REQUEST_CHANGES`

The Milestone 1 backend engine cannot be approved in its current state. The implementation exhibits:
1. One **CRITICAL** security vulnerability (SSRF and cookie credential exfiltration via unanchored domain check).
2. Three **HIGH** persistence/corruption defects in YAML config management (unquoted YAML token syntax crash, single-string `cookie:` persistence failure, and dropped `mode`/`number`/`increase` fields).
3. Two **MEDIUM** schema validation crashes on null CDN elements in raw Douyin responses.
4. One **MEDIUM** state synchronization defect when clearing cookies in memory.

Remediation of these 7 concrete faults is required before proceeding to Milestone 2.

---

## 6. Verification Method

To independently reproduce all empirical findings:

```powershell
# In project root: c:\Users\ddat2\Downloads\Projects\douyin-download
.venv\Scripts\python.exe -m pytest tests/test_m1_challenger2_edge_cases.py -v
```

Expected output:
- 50 test cases collected
- 43 passed (verifying supported variants)
- 7 failed (demonstrating exact confirmed failure modes with `FAULT CONFIRMED` messages)
