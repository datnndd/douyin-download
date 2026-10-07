# -*- coding: utf-8 -*-
"""
src/web/core/config.py
Configuration manager and YAML persistence for Douyin Web Downloader.
Supports dual cookie representations (dictionary vs raw semicolon string),
structure-preserving YAML reading and writing, and hot-reloading.
"""

import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from src.web.core.schemas import FilterOptions, SettingsModel

logger = logging.getLogger("DouyinWeb.Config")


# ==============================================================================
# Cookie Utilities
# ==============================================================================


def parse_raw_cookie(raw: Optional[str]) -> Dict[str, str]:
    """
    Parse raw cookie string ('name1=val1; name2=val2;') into a dictionary.
    Handles:
    - Extra whitespace around keys and values
    - Trailing and leading semicolons
    - Values containing '=' characters (e.g. base64 tokens: msToken=abc==)
    - Empty strings or malformed fragments
    """
    if not raw or not isinstance(raw, str):
        return {}

    cookies: Dict[str, str] = {}
    clean = raw.replace("\r", "").replace("\n", "").strip()
    if not clean:
        return {}

    for item in clean.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            key, val = item.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key:
                cookies[key] = val
        else:
            cookies[item] = ""

    return cookies


def format_cookie_dict(cookies: Optional[Dict[str, str]]) -> str:
    """
    Format a cookie dictionary into a semicolon-delimited cookie string.
    Example: {'msToken': 'abc', 'ttwid': '123'} -> 'msToken=abc; ttwid=123'
    """
    if not cookies or not isinstance(cookies, dict):
        return ""

    parts = []
    for k, v in cookies.items():
        k_clean = str(k).strip()
        v_clean = str(v).strip()
        if k_clean:
            parts.append(f"{k_clean}={v_clean}")

    return "; ".join(parts)


# ==============================================================================
# YAML Persistence & Round-Trip Helpers
# ==============================================================================


def _format_yaml_scalar(val: Any) -> str:
    """Safely format scalar values for YAML emission with proper quoting."""
    if isinstance(val, bool):
        return "True" if val else "False"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, str):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def replace_root_scalar(content: str, key: str, value: Any) -> str:
    """
    Replace a top-level scalar line matching key: value at column 0.
    Ensures nested keys (e.g., number.music or increase.music) are never clobbered.
    """
    pattern = rf"^({re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
    val_str = _format_yaml_scalar(value) if not isinstance(value, str) else value

    def repl(match: re.Match) -> str:
        prefix = match.group(1)
        comment = match.group(3)
        sep = (
            " "
            if (
                comment
                and comment.strip().startswith("#")
                and not comment.startswith(" ")
                and not val_str.endswith(" ")
            )
            else ""
        )
        return f"{prefix}{val_str}{sep}{comment}"

    return re.sub(pattern, repl, content, flags=re.MULTILINE)


def update_mapping_section(
    content: str,
    section_name: str,
    values: Dict[str, Any],
    default_indent: str = "  ",
) -> str:
    """
    Update a nested mapping section (e.g. number:, increase:, filter:) in-place.
    Preserves existing line comments and indentation inside the section block.
    If the section does not exist in content, it is appended to the bottom.
    """
    section_pattern = (
        rf"^(?P<header>{re.escape(section_name)}[ \t]*:[ \t]*(?:#[^\r\n]*)?\r?\n)"
        rf"(?P<body>(?:[ \t]+[^\r\n]*\r?\n|[ \t]*\r?\n)*)"
    )
    match = re.search(section_pattern, content, flags=re.MULTILINE)

    if match:
        header = match.group("header")
        body = match.group("body")
        for key, val in values.items():
            val_str = _format_yaml_scalar(val)
            key_pattern = rf"^([ \t]+{re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
            if re.search(key_pattern, body, flags=re.MULTILINE):
                def repl_key(km: re.Match) -> str:
                    prefix = km.group(1)
                    comment = km.group(3)
                    sep = (
                        " "
                        if (
                            comment
                            and comment.strip().startswith("#")
                            and not comment.startswith(" ")
                            and not val_str.endswith(" ")
                        )
                        else ""
                    )
                    return f"{prefix}{val_str}{sep}{comment}"

                body = re.sub(key_pattern, repl_key, body, flags=re.MULTILINE)
            else:
                body = body.rstrip() + f"\n{default_indent}{key}: {val_str}\n"

        start, end = match.span()
        return content[:start] + header + body + content[end:]
    else:
        # Append section at the end if missing
        lines = [f"{section_name}:"]
        for k, v in values.items():
            lines.append(f"{default_indent}{k}: {_format_yaml_scalar(v)}")
        return content.rstrip() + "\n\n" + "\n".join(lines) + "\n"


def update_sequence_section(
    content: str,
    section_name: str,
    values: List[str],
    default_indent: str = "  ",
) -> str:
    """
    Update a sequence section (e.g. mode: ['post', 'like']) in-place.
    Preserves section header and comments preceding the sequence block.
    """
    section_pattern = (
        rf"^(?P<header>{re.escape(section_name)}[ \t]*:[ \t]*(?:#[^\r\n]*)?\r?\n)"
        rf"(?P<body>(?:[ \t]+[^\r\n]*\r?\n|[ \t]*\r?\n)*)"
    )
    match = re.search(section_pattern, content, flags=re.MULTILINE)
    body_lines = [f"{default_indent}- {item}" for item in values]
    new_body = "\n".join(body_lines) + "\n" if body_lines else f"{default_indent}[]\n"

    if match:
        header = match.group("header")
        start, end = match.span()
        return content[:start] + header + new_body + content[end:]
    else:
        # Check flow sequence style: `mode: [...]`
        flow_pattern = rf"^({re.escape(section_name)}[ \t]*:[ \t]*)\[.*\](.*)$"
        if re.search(flow_pattern, content, flags=re.MULTILINE):
            def repl_flow(fm: re.Match) -> str:
                return f"{fm.group(1)}{json.dumps(values)}{fm.group(2)}"

            return re.sub(flow_pattern, repl_flow, content, flags=re.MULTILINE)
        else:
            return content.rstrip() + f"\n\n{section_name}:\n{new_body}"


def update_cookies_section(content: str, settings: SettingsModel) -> str:
    """
    Update cookies representation in YAML content.
    Handles:
    - Block mapping format (`cookies:`)
    - Scalar string format (`cookie: "..."`)
    - JSON-safe quoting preventing YAML syntax corruption on special tokens (@, *, {, [, \)
    - Synchronization when cookies are cleared
    """
    cookie_str = settings.raw_cookie or format_cookie_dict(settings.cookies)
    has_cookies_block = bool(re.search(r"^cookies:[ \t]*", content, flags=re.MULTILINE))
    has_cookie_scalar = bool(re.search(r"^cookie:[ \t]*", content, flags=re.MULTILINE))

    # 1. Update mapping block format if present
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
        content = re.sub(
            cookies_pattern, lambda m: new_block, content, flags=re.MULTILINE
        )

    # 2. Update scalar string format if present
    if has_cookie_scalar:
        escaped_cookie = json.dumps(cookie_str, ensure_ascii=False)
        content = replace_root_scalar(content, "cookie", escaped_cookie)

    # 3. If neither format exists in document, append whichever is defined
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


def _update_yaml_in_place_regex(original_text: str, settings: SettingsModel) -> str:
    """
    In-place line replacement that preserves 100% of existing comments and spacing
    without requiring third-party AST parsers.
    """
    text = original_text

    # 1. Update root-level scalars (strictly zero indentation)
    text = replace_root_scalar(text, "path", settings.path)
    text = replace_root_scalar(text, "music", settings.music)
    text = replace_root_scalar(text, "cover", settings.cover)
    text = replace_root_scalar(text, "avatar", settings.avatar)
    text = replace_root_scalar(text, "json", settings.json)
    text = replace_root_scalar(text, "folderstyle", settings.folderstyle)
    text = replace_root_scalar(text, "thread", settings.thread)
    text = replace_root_scalar(
        text, "filename_template", json.dumps(settings.filename_template or "{date}_{title}_{id}")
    )
    text = replace_root_scalar(text, "database", settings.database)
    text = replace_root_scalar(
        text, "start_time", json.dumps(settings.start_time or "")
    )
    text = replace_root_scalar(
        text, "end_time", json.dumps(settings.end_time or "")
    )

    # 2. Update mode sequence
    if settings.mode is not None:
        text = update_sequence_section(text, "mode", settings.mode)

    # 3. Update number dictionary
    if settings.number:
        text = update_mapping_section(text, "number", settings.number)

    # 4. Update increase dictionary
    if settings.increase:
        text = update_mapping_section(text, "increase", settings.increase)

    # 5. Update filter sub-keys
    if settings.filter:
        filter_dict = {
            "sort_by": settings.filter.sort_by,
            "reverse": settings.filter.reverse,
            "limit": settings.filter.limit,
        }
        text = update_mapping_section(text, "filter", filter_dict)

    # 6. Update cookies section
    text = update_cookies_section(text, settings)

    return text


def load_config_file(config_path: Union[str, Path] = "config.yaml") -> SettingsModel:
    """
    Load settings from YAML file. Missing or invalid file falls back to defaults.
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config file '{path}' not found — using default settings.")
        return SettingsModel()

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        # Parse cookies
        raw_cookie_val = None
        cookies_dict: Dict[str, str] = {}

        # 1. Check raw cookie string (higher priority if set in config.yaml)
        if "cookie" in raw_data and raw_data["cookie"]:
            raw_cookie_val = str(raw_data["cookie"]).strip()
            cookies_dict = parse_raw_cookie(raw_cookie_val)

        # 2. Check cookies mapping
        elif "cookies" in raw_data and isinstance(raw_data["cookies"], dict):
            cookies_dict = {str(k): str(v) for k, v in raw_data["cookies"].items()}
            raw_cookie_val = format_cookie_dict(cookies_dict)

        # Handle end_time special value "now"
        end_time_val = raw_data.get("end_time", "")
        if end_time_val == "now":
            end_time_val = time.strftime("%Y-%m-%d", time.localtime())

        # Build filter options
        filter_raw = raw_data.get("filter") or {}
        filter_opts = FilterOptions(
            sort_by=str(filter_raw.get("sort_by", "create_time")),
            reverse=bool(filter_raw.get("reverse", True)),
            limit=int(filter_raw.get("limit", 0)),
        )

        settings = SettingsModel(
            path=str(raw_data.get("path", "./Downloaded/")),
            music=bool(raw_data.get("music", True)),
            cover=bool(raw_data.get("cover", True)),
            avatar=bool(raw_data.get("avatar", False)),
            json=bool(raw_data.get("json", True)),
            folderstyle=bool(raw_data.get("folderstyle", True)),
            thread=max(1, min(32, int(raw_data.get("thread", 5)))),
            filename_template=str(raw_data.get("filename_template", "{date}_{title}_{id}")),
            cookies=cookies_dict,
            raw_cookie=raw_cookie_val,
            start_time=str(raw_data.get("start_time", "")),
            end_time=str(end_time_val),
            database=bool(raw_data.get("database", False)),
            mode=list(raw_data.get("mode", ["post"])),
            number=dict(
                raw_data.get(
                    "number", {"post": 0, "like": 0, "allmix": 0, "mix": 5, "music": 5}
                )
            ),
            increase=dict(
                raw_data.get(
                    "increase",
                    {
                        "post": False,
                        "like": False,
                        "allmix": False,
                        "mix": False,
                        "music": False,
                    },
                )
            ),
            filter=filter_opts,
        )
        return settings

    except Exception as e:
        logger.error(f"Failed to parse config file '{path}': {e} — using defaults.")
        return SettingsModel()


def save_config_file(
    settings: SettingsModel, config_path: Union[str, Path] = "config.yaml"
) -> bool:
    """
    Save settings to YAML file while preserving existing comments and structure.
    Tries ruamel.yaml first (if available); otherwise uses line-preserving regex updater.
    """
    path = Path(config_path)

    # Ensure parent directory exists
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    # Strategy 1: ruamel.yaml if available
    try:
        from ruamel.yaml import YAML

        ryaml = YAML()
        ryaml.preserve_quotes = True
        ryaml.indent(mapping=2, sequence=4, offset=2)

        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = ryaml.load(f) or {}
        else:
            data = {}

        data["path"] = settings.path
        data["music"] = settings.music
        data["cover"] = settings.cover
        data["avatar"] = settings.avatar
        data["json"] = settings.json
        data["folderstyle"] = settings.folderstyle
        data["thread"] = settings.thread
        data["filename_template"] = settings.filename_template
        data["database"] = settings.database
        data["start_time"] = settings.start_time
        data["end_time"] = settings.end_time
        data["mode"] = list(settings.mode)
        data["number"] = dict(settings.number)
        data["increase"] = dict(settings.increase)

        if "cookie" in data and not settings.cookies and settings.raw_cookie:
            data["cookie"] = settings.raw_cookie
        elif settings.cookies:
            data["cookies"] = dict(settings.cookies)
        elif settings.raw_cookie:
            data["cookie"] = settings.raw_cookie

        if settings.filter:
            data["filter"] = {
                "sort_by": settings.filter.sort_by,
                "reverse": settings.filter.reverse,
                "limit": settings.filter.limit,
            }

        with open(path, "w", encoding="utf-8") as f:
            ryaml.dump(data, f)
        logger.info(f"Successfully saved configuration to '{path}' via ruamel.yaml.")
        return True

    except ImportError:
        pass  # Fall back to Strategy 2
    except Exception as e:
        logger.warning(f"ruamel.yaml update failed: {e}; falling back to line updater.")

    # Strategy 2: Line-preserving regex updater (on existing file)
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                original_text = f.read()

            updated_text = _update_yaml_in_place_regex(original_text, settings)

            with open(path, "w", encoding="utf-8") as f:
                f.write(updated_text)
            logger.info(
                f"Successfully updated '{path}' preserving comments via regex updater."
            )
            return True

        # If file does not exist, write standard structure
        dump_dict = {
            "path": settings.path,
            "music": settings.music,
            "cover": settings.cover,
            "avatar": settings.avatar,
            "json": settings.json,
            "folderstyle": settings.folderstyle,
            "thread": settings.thread,
            "database": settings.database,
            "start_time": settings.start_time,
            "end_time": settings.end_time,
            "mode": settings.mode,
            "number": settings.number,
            "increase": settings.increase,
            "cookies": settings.cookies,
            "filter": settings.filter.model_dump(),
        }
        if settings.raw_cookie and not settings.cookies:
            dump_dict["cookie"] = settings.raw_cookie
            del dump_dict["cookies"]

        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(dump_dict, f, default_flow_style=False, allow_unicode=True)
        return True

    except Exception as e:
        logger.error(f"Failed to save configuration to '{path}': {e}")
        return False


# ==============================================================================
# ConfigManager Singleton
# ==============================================================================


class ConfigManager:
    """
    Central thread-safe configuration manager for Douyin Web Downloader.
    Maintains active in-memory settings, handles disk synchronization,
    and coordinates live hot-reloads of request headers.
    """

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self, config_path: Union[str, Path] = "config.yaml"):
        self.config_path = Path(config_path)
        self._settings_lock = threading.RLock()
        self._settings = load_config_file(self.config_path)
        self.apply_to_douyin_headers()

    @classmethod
    def get_instance(
        cls, config_path: Union[str, Path] = "config.yaml"
    ) -> "ConfigManager":
        """Singleton accessor."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config_path)
            return cls._instance

    def get_settings(self) -> SettingsModel:
        """Get copy of current settings."""
        with self._settings_lock:
            return self._settings.model_copy(deep=True)

    def update_settings(self, new_settings: SettingsModel) -> SettingsModel:
        """
        Update in-memory settings, synchronize cookie formats,
        persist to config.yaml, and hot-reload headers.
        """
        with self._settings_lock:
            # Bidirectional cookie synchronization
            old_raw = self._settings.raw_cookie
            old_cookies = self._settings.cookies

            raw_changed = new_settings.raw_cookie != old_raw
            cookies_changed = new_settings.cookies != old_cookies

            if raw_changed and not cookies_changed:
                new_settings.cookies = parse_raw_cookie(new_settings.raw_cookie)
            elif cookies_changed and not raw_changed:
                new_settings.raw_cookie = format_cookie_dict(new_settings.cookies)
            elif new_settings.raw_cookie and not new_settings.cookies:
                new_settings.cookies = parse_raw_cookie(new_settings.raw_cookie)
            elif new_settings.cookies and not new_settings.raw_cookie:
                new_settings.raw_cookie = format_cookie_dict(new_settings.cookies)
            elif raw_changed:
                new_settings.cookies = parse_raw_cookie(new_settings.raw_cookie)

            self._settings = new_settings
            save_config_file(self._settings, self.config_path)
            self.apply_to_douyin_headers()
            return self._settings.model_copy(deep=True)

    def reload(self) -> SettingsModel:
        """Force reload from disk."""
        with self._settings_lock:
            self._settings = load_config_file(self.config_path)
            self.apply_to_douyin_headers()
            return self._settings.model_copy(deep=True)

    @staticmethod
    def _load_auxiliary_security_cookies() -> Dict[str, str]:
        """Look for .cookies.json in current directory, project root, or sibling projects."""
        candidates = [
            Path(".cookies.json"),
            Path(__file__).resolve().parent.parent.parent.parent / ".cookies.json",
            Path.cwd() / ".cookies.json",
            Path.cwd().parent / "douyin-downloader" / ".cookies.json",
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                try:
                    data = json.loads(c.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return {str(k): str(v) for k, v in data.items() if v}
                except Exception as e:
                    logger.debug(f"Failed to load auxiliary cookies from {c}: {e}")
        return {}

    def get_cookie_header(self) -> str:
        """Retrieve active formatted cookie string for HTTP requests with security token enrichment."""
        with self._settings_lock:
            active_cookies: Dict[str, str] = dict(self._settings.cookies or {})
            if not active_cookies and self._settings.raw_cookie:
                active_cookies = parse_raw_cookie(self._settings.raw_cookie)

            # Auto-enrich missing Argus security tokens (UIFID, UIFID_TEMP, bd_ticket_guard, etc.) only if cookies are active
            if active_cookies and not active_cookies.get("UIFID") and not active_cookies.get("UIFID_TEMP"):
                aux_cookies = self._load_auxiliary_security_cookies()
                if aux_cookies:
                    merged = dict(aux_cookies)
                    merged.update(active_cookies)  # user tokens take precedence
                    active_cookies = merged

            if active_cookies:
                return format_cookie_dict(active_cookies)
            return self._settings.raw_cookie or ""

    def apply_to_douyin_headers(self) -> None:
        """Hot-reload cookies into global douyin_headers dict if available."""
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

    def resolve_download_path(self) -> Path:
        """Resolve and ensure the configured download directory."""
        with self._settings_lock:
            raw_path = self._settings.path or "./Downloaded/"

        target = Path(raw_path)
        if not target.is_absolute():
            # Resolve relative to current working directory or repo root
            target = (Path.cwd() / target).resolve()

        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create download directory '{target}': {e}")

        return target
