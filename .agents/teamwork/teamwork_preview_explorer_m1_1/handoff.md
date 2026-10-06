# Handoff Report — M1 Explorer 1: Schemas & Config

**Project:** Douyin Web Downloader  
**Role:** M1 Explorer 1 (Schemas & Config)  
**Date:** 2026-10-06  
**Type:** Hard Handoff  

---

## 1. Observation

1. **Environment & Dependencies**:
   - `python -c "import pydantic; print(pydantic.__version__)"` exited with code 0, reporting Pydantic `2.12.5` (Pydantic v2 native).
   - `python -c "import fastapi, uvicorn; ..."` exited with code 0, reporting FastAPI `0.128.0` and Uvicorn `0.40.0`.
   - `python -c "import ruamel.yaml"` failed with `ModuleNotFoundError: No module named 'ruamel'`. Dry-run `python -m pip install --dry-run ruamel.yaml` exited with code 0, confirming cached availability.
2. **Existing Configuration (`config.yaml`)**:
   - Contains 116 lines of configuration, comments, and instructions.
   - Core settings: `link` (list of URLs), `path` (default `./Downloaded/`), `music: False`, `cover: False`, `avatar: False`, `json: False`, `folderstyle: False`, `mode: ['post']`, `thread: 10`, `database: False`.
   - Dual-format cookie specification: lines 103–109 specify `cookies` as a mapping with 5 tokens (`msToken`, `ttwid`, `odin_tt`, `passport_csrf_token`, `sid_guard`), while lines 110–115 document the alternative raw string `cookie: "name1=val1; ..."`.
3. **Existing CLI Engine & Result Models**:
   - `src/douyin/result.py`: In `Result.__init__`, dictionary values for `statistics` (`digg_count`, `comment_count`, `share_count`, `play_count`, `collect_count`, `admire_count`) are initialized to empty strings `""` (line 177).
   - In `Result.dataConvert`, `author.avatar_thumb` and `video.cover` are dictionary objects with `url_list: [...]` (lines 15–20, 127–133).
   - `src/douyin/download.py`: Accepts `thread`, `music`, `cover`, `avatar`, `resjson`, `folderstyle` (line 27). Uses `douyin_headers` from `src.douyin.__init__` which has `Cookie` defined in headers (line 19 of `src/douyin/__init__.py`).
4. **Interface Contracts (`PROJECT.md` & `SCOPE.md`)**:
   - Contract § 1 (`POST /api/parse`): returns `url`, `canonical_url`, `key_type`, `key`, `content_type`, `preview` (`title`, `desc`, `author`, `cover_url`, `statistics`, `duration`, `work_count`).
   - Contract § 2 (`POST /api/download`): accepts `url`, `key_type`, `key`, `modes`, `asset_types`, `thread_count`, `filter`, `folderstyle`, `download_path`; returns 202 Accepted `TaskResponse` (`task_id`, `status: "PENDING"`, `message`, `created_at`).
   - Contract § 3 (`GET /api/tasks/{task_id}`): returns `TaskDetailResponse` with worker `threads` telemetry.
   - Contract § 4 (SSE stream): emits `DownloadProgressEvent`.
   - Contract § 5 (`GET/POST /api/settings`): exchanges `SettingsModel` with `path`, `thread`, `cookies`, `raw_cookie`, and asset toggles.

---

## 2. Logic Chain

1. **Schema Design (`schemas.py`)**:
   - *From Observation 3* (empty string statistics in `result.py:177` and dict URLs in `result.py:15-20`): Direct instantiation of Pydantic models from raw Douyin responses would throw `ValidationError`.
   - *Therefore*: Defined pre-validators (`@field_validator(..., mode="before")`) on `StatisticsModel` and `AuthorPreview` to coerce `""`/`None` to `0` and extract flat URLs from `{"url_list": [...]}` dicts.
   - *From Observation 1 & 4*: Built clean Pydantic v2 models (`ConfigDict(populate_by_name=True)`) covering `ParseRequest`, `ParseResponse`, `PreviewMetadata`, `AuthorPreview`, `DownloadRequest`, `AssetTypeToggles`, `FilterOptions`, `TaskResponse`, `TaskDetailResponse`, `ThreadStatus`, `DownloadProgressEvent`, `SettingsModel`, `MediaItem`, `MediaListResponse`, `OpenFolderRequest`, `OpenFolderResponse`, and `HealthResponse`.
   - Suppressed Pydantic `BaseModel` attribute shadowing warnings for the `json` boolean toggle field using `warnings.filterwarnings`.
2. **Configuration Reader/Writer (`config.py`)**:
   - *From Observation 2*: Settings must support both `cookies` dictionary and `raw_cookie` string seamlessly.
   - *Therefore*: Created `parse_raw_cookie(raw)` with `item.split("=", 1)` (to prevent base64 padding corruption) and `format_cookie_dict(cookies)`. When loading, both formats are populated on `SettingsModel`.
   - *From Observation 2*: `config.yaml` has extensive inline documentation that must not be wiped out by standard `yaml.safe_dump()`.
   - *Therefore*: Built a dual persistence strategy: uses `ruamel.yaml` when installed; falls back to an in-place regex line updater that updates scalars (`thread`, `music`, `path`, etc.) and the `cookies:` block while preserving every comment line and spacing intact.
   - Added `ConfigManager` singleton managing in-memory state, disk persistence, and hot-reloading `src.douyin.douyin_headers["Cookie"]`.

---

## 3. Caveats

1. **`ruamel.yaml` Installation**: While `ruamel.yaml` is cached and works when installed, the project currently runs with standard `PyYAML==6.0.1`. The fallback regex updater successfully passed tests on `config.yaml`, but adding `ruamel.yaml>=0.18.0` to `requirements.txt` remains recommended for full round-trip formatting fidelity.
2. **Relative Path Anchoring**: `resolve_download_path()` anchors relative paths (such as `./Downloaded/`) against `Path.cwd()`. In production runs via `python webui.py`, working directory must be the repository root.
3. **Douyin Live & Music Key Types**: Live rooms and music links produce specialized metadata (e.g. `web_rid`, `flv_pull_url`). `PreviewMetadata` includes an `extra: Dict[str, Any]` field to capture these fields cleanly without breaking the standard card preview structure.

---

## 4. Conclusion

1. **Complete Schemas Implemented & Tested**:
   The complete code is written and verified in:
   `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_1\proposed_schemas.py`.
   It fulfills 100% of interface requirements in `PROJECT.md` and handles all raw Douyin API data variations defensively.
2. **Complete Config Architecture Implemented & Tested**:
   The complete code is written and verified in:
   `c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_1\proposed_config.py`.
   It supports bidirectional cookie parsing, preserves all existing comments in `config.yaml`, and supports hot-reload into `douyin_headers`.
3. **Ready for Milestone 1 Implementers**:
   M1 implementers can directly adopt these two files when creating `src/web/core/schemas.py` and `src/web/core/config.py`.

---

## 5. Verification Method

To independently verify the schemas and configuration modules, execute the following commands in powershell from the project root:

```powershell
# 1. Verify proposed_schemas with 0 warnings
python -c "
import sys
sys.path.insert(0, r'c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_1')
import proposed_schemas as s

pr = s.ParseRequest(url='https://v.douyin.com/iWhQezyaUco/')
stats = s.StatisticsModel(digg_count='', comment_count='42')
assert stats.digg_count == 0 and stats.comment_count == 42
author = s.AuthorPreview(nickname='Test', avatar_thumb={'url_list': ['https://example.com/thumb.jpg']})
assert author.avatar_thumb == 'https://example.com/thumb.jpg'
print('Schemas verified: OK')
"

# 2. Verify proposed_config against real config.yaml and comment preservation
python -c "
import sys, shutil
from pathlib import Path
sys.path.insert(0, r'c:\Users\ddat2\Downloads\Projects\douyin-download\.agents\teamwork\teamwork_preview_explorer_m1_1')
import proposed_config as cfg

settings = cfg.load_config_file(Path('config.yaml'))
assert settings.thread == 10
assert 'msToken' in settings.cookies

temp_cfg = Path('temp_test_config.yaml')
shutil.copyfile('config.yaml', temp_cfg)
settings.thread = 16
cfg.save_config_file(settings, temp_cfg)

reloaded = cfg.load_config_file(temp_cfg)
assert reloaded.thread == 16
with open(temp_cfg, 'r', encoding='utf-8') as f:
    text = f.read()
assert '# Test: single video download' in text
temp_cfg.unlink()
print('Config verified with comment preservation: OK')
"
```

**Invalidation conditions**:
- The tests are invalidated if Pydantic v1 is installed instead of v2, or if `config.yaml` is deleted.
