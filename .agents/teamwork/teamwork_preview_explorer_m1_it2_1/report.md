# M1 Iteration 2 Explorer 1 Report: Config & YAML Remediation

**Explorer:** `teamwork_preview_explorer_m1_it2_1`  
**Role:** Config & YAML Remediation  
**Target:** `src/web/core/config.py` & YAML Persistence Pipeline  
**Date:** 2026-10-06  
**Status:** Complete  

---

## Executive Summary

During Milestone 1 review and adversarial challenge (Reviewer 1 and Challenger 2), 5 distinct defects were identified in `src/web/core/config.py` related to configuration persistence, YAML formatting, and runtime state synchronization:

1. **Nested Key Collision**: Regex `replace_scalar` matched any indentation (`^[ \t]*key:`), clobbering nested keys (e.g., top-level `music: True` corrupted `number.music: 5` and `increase.music: False` to boolean `True`, which reloaded as integer limit `1`).
2. **Scalar Cookie Format Persistence**: When `config.yaml` utilized the single-string `cookie: "..."` format, saving via `_update_yaml_in_place_regex` only searched for mapping block `^cookies:`, silently dropping updates to `cookie:`.
3. **Missing Fields on Disk Save**: Fields `mode` (download mode list), `number` (work limits per category), and `increase` (incremental switches) in `SettingsModel` were never serialized back to `config.yaml` by `_update_yaml_in_place_regex` or fallback dumpers.
4. **YAML Special Characters & Syntax Corruption**: Cookie tokens containing YAML reserved indicators (`@`, `*`, `{`, `[`, or trailing `\`) were emitted unquoted, causing `yaml.safe_load` to raise `ScannerError` on restart and wipe configuration to defaults.
5. **In-Memory Cookie Leak on Clear**: `apply_to_douyin_headers()` exited early (`if not cookie_str: return`) when cookies were cleared in settings, leaving stale session credentials active in `douyin_headers["Cookie"]`.

All 5 defects have been thoroughly analyzed, reproduced, and remediated. A validated drop-in replacement (`proposed_config.py`), unified diff patch (`config_remediation.patch`), and lightweight verification test suite (`test_strategy.py`) have been constructed in this workspace.

---

## Defect Inventory & Root Cause Analysis

### Defect 1: Nested Key Collision (`music` vs `number.music`)
- **Location**: `src/web/core/config.py`, lines 93–115 & line 118
- **Root Cause**:
  ```python
  def replace_scalar(content: str, key: str, value: Any) -> str:
      pattern = rf"^([ \t]*{re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
  ```
  The pattern allows arbitrary leading whitespace `[ \t]*`. In `config.yaml`:
  - Line 25: `music: False` (root scalar)
  - Line 71: `  music: 5` (nested under `number:`)
  - Line 88: `  music: False` (nested under `increase:`)
  When updating `settings.music = True`, `re.sub` substituted both line 25 and line 71. Upon restart, `yaml.safe_load` loaded `number: music: True`. Python integer coercion casts `int(True) == 1`, silently reducing the user's music download limit from 5 to 1.
- **Remediation**:
  Define `replace_root_scalar` requiring strict zero leading indentation:
  ```python
  pattern = rf"^({re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
  ```
  Lines starting with indentation (spaces or tabs) are strictly excluded from root replacement.

---

### Defect 2: Scalar Cookie Format Persistence (`cookie:` vs `cookies:`)
- **Location**: `src/web/core/config.py`, lines 139–160
- **Root Cause**:
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
  When `config.yaml` starts with `cookie: "..."`, `load_config_file()` populates both `settings.cookies` (parsed dict) and `settings.raw_cookie`. Subsequent saves take `if settings.cookies:`. Because the document has no `^cookies:` block, `re.search` fails and skips. The `elif settings.raw_cookie:` branch is never reached. Changes are silently dropped.
- **Remediation**:
  In `update_cookies_section()`, inspect the document independently for `^cookies:[ \t]*` and `^cookie:[ \t]*`:
  1. If `^cookies:` is present, update the mapping block format.
  2. If `^cookie:` is present, update the scalar format using `replace_root_scalar("cookie", json.dumps(cookie_str))`.
  3. If neither is present, append whichever format is active.

---

### Defect 3: Missing Fields (`mode`, `number`, `increase`)
- **Location**: `src/web/core/config.py`, lines 85–160 & lines 319–335
- **Root Cause**:
  `_update_yaml_in_place_regex` only updated `path`, `music`, `cover`, `avatar`, `json`, `folderstyle`, `thread`, `database`, `start_time`, `end_time`, `filter`, and `cookies`. It completely lacked handling for `mode` (list), `number` (dict), and `increase` (dict). Furthermore, the fallback `dump_dict` in `save_config_file()` omitted all three fields.
- **Remediation**:
  1. Implement `update_mapping_section(content, section_name, values)` to update nested mappings (`number`, `increase`, `filter`) line-by-line while preserving existing indentation and inline comments. If missing, appends the section cleanly.
  2. Implement `update_sequence_section(content, section_name, values)` to update sequence blocks (`mode`).
  3. Include `mode`, `number`, and `increase` in `save_config_file()` fallback `dump_dict` and `ruamel.yaml` sync.

---

### Defect 4: YAML Special Characters & Syntax Corruption
- **Location**: `src/web/core/config.py`, lines 142–146
- **Root Cause**:
  ```python
  clean_v = str(v).replace('"', '\\"')
  if ":" in clean_v or "#" in clean_v or "%" in clean_v:
      cookie_lines.append(f'  {k}: "{clean_v}"')
  else:
      cookie_lines.append(f"  {k}: {clean_v}")
  ```
  Tokens starting with YAML indicator tokens (e.g. `@`, `*`, `{`, `[`, or ending in `\`) were output unquoted: `msToken: @adversarial_token`. In YAML, `@` is a reserved character and cannot start an unquoted scalar. `yaml.safe_load()` raised `yaml.scanner.ScannerError`, crashing startup and resetting configuration to default.
- **Remediation**:
  Use `json.dumps(str(val), ensure_ascii=False)` in `_format_yaml_scalar()`. Every valid JSON string scalar is guaranteed to be 100% compliant with YAML 1.2 double-quoted scalar syntax, escaping quotes, backslashes, and control characters safely.

---

### Defect 5: In-Memory Cookie Leak on Clear
- **Location**: `src/web/core/config.py`, lines 423–436
- **Root Cause**:
  ```python
  def apply_to_douyin_headers(self) -> None:
      cookie_str = self.get_cookie_header()
      if not cookie_str:
          return
      douyin_headers["Cookie"] = cookie_str
  ```
  When cookies were cleared in settings (`cookies = {}` and `raw_cookie = ""`), `get_cookie_header()` returned `""`. Because of `if not cookie_str: return`, `douyin_headers["Cookie"]` was never deleted, leaving sensitive session credentials active in memory.
- **Remediation**:
  ```python
  def apply_to_douyin_headers(self) -> None:
      cookie_str = self.get_cookie_header()
      try:
          from src.douyin import douyin_headers
          if cookie_str:
              douyin_headers["Cookie"] = cookie_str
              logger.debug("Successfully hot-reloaded douyin_headers['Cookie'].")
          else:
              douyin_headers.pop("Cookie", None)
              logger.debug("Successfully cleared douyin_headers['Cookie'].")
      except (ImportError, AttributeError, Exception) as e:
          logger.debug(f"Could not update src.douyin.douyin_headers: {e}")
  ```

---

## Architectural Design for YAML Remediation

### Section Matching Mechanics
YAML documents in this project maintain comment documentation for every setting. To preserve 100% of comments without third-party AST engines, the parser uses section-aware boundary matching:

```
+--------------------------------------------------------------+
| Root Scalar:  ^(key[ \t]*:[ \t]*)([^#\n]*)(.*)$               |
| -> Zero indentation required. Cannot match nested keys.     |
+--------------------------------------------------------------+
| Nested Mapping Section:                                      |
| Header:  ^(section_name[ \t]*:[ \t]*(?:#[^\r\n]*)?\r?\n)     |
| Body:    ([ \t]+[^\r\n]*\r?\n|[ \t]*\r?\n)*                  |
| -> Line replacement inside Body only.                        |
| -> Preserves exact comments (# Number of works...)           |
+--------------------------------------------------------------+
| Sequence Section:                                            |
| Header:  ^(mode[ \t]*:[ \t]*(?:#[^\r\n]*)?\r?\n)             |
| Body:    ([ \t]+-[ \t]*[^\r\n]*\r?\n)*                       |
| -> Replaces item lines while preserving header comments.     |
+--------------------------------------------------------------+
```

---

## Proposed Changes: Before & After Comparison

### 1. Root-Level vs Nested Scalar Replacement

#### Before:
```python
def replace_scalar(content: str, key: str, value: Any) -> str:
    pattern = rf"^([ \t]*{re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
    val_str = str(value)
    ...
```

#### After:
```python
def replace_root_scalar(content: str, key: str, value: Any) -> str:
    """Replace a top-level scalar line matching key: value at column 0."""
    pattern = rf"^({re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
    val_str = _format_yaml_scalar(value) if not isinstance(value, str) else value
    ...
```

### 2. Cookie Updating Logic

#### Before:
```python
if settings.cookies:
    cookie_lines = ["cookies:"]
    for k, v in settings.cookies.items():
        clean_v = str(v).replace('"', '\\"')
        if ":" in clean_v or "#" in clean_v or "%" in clean_v:
            cookie_lines.append(f'  {k}: "{clean_v}"')
        else:
            cookie_lines.append(f"  {k}: {clean_v}")
    new_cookies_block = "\n".join(cookie_lines)

    cookies_pattern = r"^cookies:[ \t]*(?:\r?\n[ \t]+[^\r\n]+)*"
    if re.search(cookies_pattern, text, flags=re.MULTILINE):
        text = re.sub(cookies_pattern, lambda m: new_cookies_block, text, flags=re.MULTILINE)
elif settings.raw_cookie:
    escaped_cookie = settings.raw_cookie.replace('"', '\\"')
    text = replace_scalar(text, "cookie", f'"{escaped_cookie}"')
```

#### After:
```python
def update_cookies_section(content: str, settings: SettingsModel) -> str:
    cookie_str = settings.raw_cookie or format_cookie_dict(settings.cookies)
    has_cookies_block = bool(re.search(r"^cookies:[ \t]*", content, flags=re.MULTILINE))
    has_cookie_scalar = bool(re.search(r"^cookie:[ \t]*", content, flags=re.MULTILINE))

    if has_cookies_block:
        if settings.cookies:
            lines = ["cookies:"]
            for k, v in settings.cookies.items():
                quoted_v = json.dumps(str(v), ensure_ascii=False)
                lines.append(f"  {k}: {quoted_v}")
            new_block = "\n".join(lines)
        else:
            new_block = "cookies: {}"
        cookies_pattern = r"^cookies:[ \t]*(?:\r?\n[ \t]+[^\r\n]+)*"
        content = re.sub(cookies_pattern, lambda m: new_block, content, flags=re.MULTILINE)

    if has_cookie_scalar:
        escaped_cookie = json.dumps(cookie_str, ensure_ascii=False)
        content = replace_root_scalar(content, "cookie", escaped_cookie)

    if not has_cookies_block and not has_cookie_scalar:
        if settings.cookies:
            lines = ["cookies:"]
            for k, v in settings.cookies.items():
                quoted_v = json.dumps(str(v), ensure_ascii=False)
                lines.append(f"  {k}: {quoted_v}")
            content = content.rstrip() + "\n\n" + "\n".join(lines) + "\n"
        elif settings.raw_cookie:
            escaped_cookie = json.dumps(settings.raw_cookie, ensure_ascii=False)
            content = content.rstrip() + f"\n\ncookie: {escaped_cookie}\n"

    return content
```

### 3. Adding Support for `mode`, `number`, `increase`

#### Added Functions:
```python
def update_mapping_section(
    content: str, section_name: str, values: Dict[str, Any], default_indent: str = "  "
) -> str: ...

def update_sequence_section(
    content: str, section_name: str, values: List[str], default_indent: str = "  "
) -> str: ...
```

Integrated into `_update_yaml_in_place_regex`:
```python
    # 2. Update mode sequence
    if settings.mode is not None:
        text = update_sequence_section(text, "mode", settings.mode)

    # 3. Update number dictionary
    if settings.number:
        text = update_mapping_section(text, "number", settings.number)

    # 4. Update increase dictionary
    if settings.increase:
        text = update_mapping_section(text, "increase", settings.increase)
```

---

## Verification & Empirical Proof

A comprehensive test script (`test_strategy.py`) was executed against the actual `config.yaml` file, reproducing each issue and validating the proposed fixes:

| Test Case | Scenario | Previous Behavior | Proposed Behavior | Result |
|---|---|---|---|---|
| **Test 1** | Nested Key Collision (`music: True`) | Overwrote `number.music: 5` to `1` | `music: True` saved at root; `number.music: 5` preserved | **PASS** |
| **Test 2** | Scalar Cookie Persistence | Ignored updates when file used `cookie: "..."` | Correctly updated `cookie: "..."` with new tokens | **PASS** |
| **Test 3** | Dropped Fields (`mode`, `number`, `increase`) | Fields dropped on disk save | Persisted `mode: ["post", "like"]`, `number: {"post": 50}`, and `increase` | **PASS** |
| **Test 4** | Special YAML Characters | `@token`, `*pointer`, `{val}` crashed `yaml.safe_load` | Quoted safely via `json.dumps`; parsed cleanly | **PASS** |
| **Test 5** | Stale Cookie Cleanup | Old credentials remained in `douyin_headers['Cookie']` | `douyin_headers.pop('Cookie')` executed; clean memory | **PASS** |

### Execution Command & Output:
```powershell
.venv\Scripts\python.exe .agents/teamwork/teamwork_preview_explorer_m1_it2_1/test_strategy.py
```
```
Running full verification suite...
[PASS] Test 1: Nested Key Collision resolved (music=True, number.music=5)
[PASS] Test 2: Scalar Cookie Format Persistence resolved
[PASS] Test 3: Mode, number, increase fields persisted successfully
[PASS] Test 4: YAML Special Characters properly quoted
[PASS] Test 5: In-Memory Cookie cleanup verified

ALL 5 DEFECT TEST SCENARIOS PASSED WITH 100% SUCCESS!
```

---

## Artifact Deliverables

The following files are available in this agent directory for application by the builder agent:
1. `proposed_config.py` (`c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_1\proposed_config.py`): Complete, verified replacement file for `src/web/core/config.py`.
2. `config_remediation.patch` (`c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_1\config_remediation.patch`): Exact unified diff patch ready to apply to `src/web/core/config.py`.
3. `test_strategy.py` (`c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_it2_1\test_strategy.py`): Standalone verification script verifying all 5 fixes without memory pressure.
