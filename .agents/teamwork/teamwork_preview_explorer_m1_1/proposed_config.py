"""
src/web/core/config.py
Configuration manager and YAML persistence for Douyin Web Downloader.
Supports dual cookie representations (dictionary vs raw semicolon string),
structure-preserving YAML reading and writing, and hot-reloading.
"""

import os
import re
import time
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import yaml

# Import schemas
try:
    from .schemas import FilterOptions, SettingsModel
except (ImportError, ValueError):
    from proposed_schemas import FilterOptions, SettingsModel

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

def _update_yaml_in_place_regex(original_text: str, settings: SettingsModel) -> str:
    """
    In-place line replacement that preserves 100% of existing comments and spacing
    without requiring third-party AST parsers.
    """
    text = original_text

    # Helper for simple key: value scalars
    def replace_scalar(content: str, key: str, value: Any) -> str:
        pattern = rf"^([ \t]*{re.escape(key)}[ \t]*:[ \t]*)([^#\n]*)(.*)$"
        val_str = str(value)
        if isinstance(value, bool):
            val_str = "True" if value else "False"
        def repl(match: re.Match) -> str:
            prefix = match.group(1)
            comment = match.group(3)
            sep = " " if (comment and comment.strip().startswith("#") and not comment.startswith(" ") and not val_str.endswith(" ")) else ""
            return f"{prefix}{val_str}{sep}{comment}"
        return re.sub(pattern, repl, content, flags=re.MULTILINE)

    # 1. Update basic scalars
    text = replace_scalar(text, "path", settings.path)
    text = replace_scalar(text, "music", settings.music)
    text = replace_scalar(text, "cover", settings.cover)
    text = replace_scalar(text, "avatar", settings.avatar)
    text = replace_scalar(text, "json", settings.json)
    text = replace_scalar(text, "folderstyle", settings.folderstyle)
    text = replace_scalar(text, "thread", settings.thread)
    text = replace_scalar(text, "database", settings.database)
    text = replace_scalar(text, "start_time", f'"{settings.start_time}"' if settings.start_time else '""')
    text = replace_scalar(text, "end_time", f'"{settings.end_time}"' if settings.end_time else '""')

    # 2. Update filter sub-keys
    if settings.filter:
        text = replace_scalar(text, "sort_by", f'"{settings.filter.sort_by}"')
        text = replace_scalar(text, "reverse", settings.filter.reverse)
        text = replace_scalar(text, "limit", settings.filter.limit)

    # 3. Update cookies section
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

    # If raw_cookie is explicitly set and cookies dict is empty, update cookie: string
    elif settings.raw_cookie:
        escaped_cookie = settings.raw_cookie.replace('"', '\\"')
        text = replace_scalar(text, "cookie", f'"{escaped_cookie}"')

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
            cookies=cookies_dict,
            raw_cookie=raw_cookie_val,
            start_time=str(raw_data.get("start_time", "")),
            end_time=str(end_time_val),
            database=bool(raw_data.get("database", False)),
            mode=list(raw_data.get("mode", ["post"])),
            number=dict(raw_data.get("number", {"post": 0, "like": 0, "allmix": 0, "mix": 5, "music": 5})),
            increase=dict(raw_data.get("increase", {"post": False, "like": False, "allmix": False, "mix": False, "music": False})),
            filter=filter_opts,
        )
        return settings

    except Exception as e:
        logger.error(f"Failed to parse config file '{path}': {e} — using defaults.")
        return SettingsModel()


def save_config_file(settings: SettingsModel, config_path: Union[str, Path] = "config.yaml") -> bool:
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
        data["database"] = settings.database
        data["start_time"] = settings.start_time
        data["end_time"] = settings.end_time

        if settings.cookies:
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
            logger.info(f"Successfully updated '{path}' preserving comments via regex updater.")
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
            "cookies": settings.cookies,
            "filter": settings.filter.model_dump(),
        }
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
    def get_instance(cls, config_path: Union[str, Path] = "config.yaml") -> "ConfigManager":
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
            if new_settings.raw_cookie and not new_settings.cookies:
                new_settings.cookies = parse_raw_cookie(new_settings.raw_cookie)
            elif new_settings.cookies and not new_settings.raw_cookie:
                new_settings.raw_cookie = format_cookie_dict(new_settings.cookies)

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

    def get_cookie_header(self) -> str:
        """Retrieve active formatted cookie string for HTTP requests."""
        with self._settings_lock:
            if self._settings.raw_cookie:
                return self._settings.raw_cookie
            if self._settings.cookies:
                return format_cookie_dict(self._settings.cookies)
            return ""

    def apply_to_douyin_headers(self) -> None:
        """Hot-reload cookies into global douyin_headers dict if available."""
        cookie_str = self.get_cookie_header()
        if not cookie_str:
            return

        try:
            from src.douyin import douyin_headers
            douyin_headers["Cookie"] = cookie_str
            logger.debug("Successfully hot-reloaded douyin_headers['Cookie'].")
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
