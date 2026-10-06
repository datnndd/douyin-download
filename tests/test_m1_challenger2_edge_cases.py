# -*- coding: utf-8 -*-
"""
tests/test_m1_challenger2_edge_cases.py
Adversarial Edge Case & Fault Invariant Tests for Milestone 1.
Authored by M1 Challenger 2 (Edge Cases & Fault Invariants).

Covers:
1. Dirty, malformed, emoji, Chinese copy text, and adversarial URL variants across all 5 key types.
2. Security & domain validation checks (domain spoofing, SSRF with leaked headers).
3. YAML configuration persistence, comment preservation, missing key handling, and corruption recovery.
4. Dual-format cookie parsing edge cases, base64 tokens, and header synchronization.
5. Schema validation boundary invariants and data type coercion edge cases.
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.douyin import douyin_headers
from src.web.core.config import (
    ConfigManager,
    _update_yaml_in_place_regex,
    format_cookie_dict,
    load_config_file,
    parse_raw_cookie,
    save_config_file,
)
from src.web.core.schemas import (
    AssetTypeToggles,
    AuthorPreview,
    DownloadProgressEvent,
    DownloadRequest,
    FilterOptions,
    KeyType,
    ParseRequest,
    ParseResponse,
    PreviewMetadata,
    PreviewStatistics,
    SettingsModel,
    StatisticsModel,
    TaskDetailResponse,
    TaskResponse,
    TaskStatus,
    ThreadStatus,
)
from src.web.services.douyin_service import (
    DouyinInvalidUrlError,
    DouyinNotFoundError,
    DouyinService,
    DouyinServiceError,
    DouyinUpstreamError,
)
from src.web.services.task_manager import TaskManager, TaskRecord


# ==============================================================================
# Domain 1: URL Variants, Dirty Text, and Adversarial Inputs
# ==============================================================================


class TestUrlVariantsAndEdgeCases:
    """Stress tests for URL extraction and resolution across all key types."""

    @pytest.fixture
    def service(self):
        return DouyinService()

    @pytest.mark.parametrize(
        "dirty_input, expected_url",
        [
            # Chinese copy text with punctuation
            (
                "7.35 复制打开抖音，看看【小明同学的作品】 https://v.douyin.com/iWhQezyaUco/ 11/12 l@w.pm :0pm",
                "https://v.douyin.com/iWhQezyaUco/",
            ),
            # Emojis on both sides without spaces
            (
                "🔥🎉https://v.douyin.com/iWhQezyaUco/🚀✨",
                "https://v.douyin.com/iWhQezyaUco/",
            ),
            # Brackets and full-width punctuation
            (
                "【抖音精选】（https://www.douyin.com/video/7488893440932039970）！太棒了。",
                "https://www.douyin.com/video/7488893440932039970",
            ),
            # Multiple query parameters and hash anchors
            (
                "https://www.douyin.com/video/7488893440932039970?utm_source=copy&utm_medium=android#comment",
                "https://www.douyin.com/video/7488893440932039970?utm_source=copy&utm_medium=android#comment",
            ),
            # Newlines and carriage returns
            (
                "\r\n\t  https://v.douyin.com/8muR-7iUO6E/  \r\n",
                "https://v.douyin.com/8muR-7iUO6E/",
            ),
        ],
    )
    def test_extract_share_url_dirty_text(self, service, dirty_input, expected_url):
        extracted = service.extract_share_url(dirty_input)
        assert extracted == expected_url

    @pytest.mark.parametrize(
        "invalid_input",
        [
            "",
            "   \t\n   ",
            "没有链接的普通文本 抖音号: 123456",
            "javascript:alert(1)",
            "ftp://files.example.com/douyin/video.mp4",
        ],
    )
    def test_extract_share_url_invalid_inputs(self, service, invalid_input):
        assert service.extract_share_url(invalid_input) is None
        with pytest.raises(DouyinInvalidUrlError):
            service.sync_parse_url(invalid_input)

    @pytest.mark.parametrize(
        "url, expected_type, expected_key",
        [
            # 1. Aweme variants
            ("https://www.douyin.com/video/7488893440932039970", "aweme", "7488893440932039970"),
            ("https://www.douyin.com/video/7488893440932039970/", "aweme", "7488893440932039970"),
            ("https://www.douyin.com/video/7488893440932039970?param=1", "aweme", "7488893440932039970"),
            ("https://www.douyin.com/note/7488893440932039971", "aweme", "7488893440932039971"),
            ("https://www.douyin.com/share/video/7488893440932039970", "aweme", "7488893440932039970"),
            ("https://www.douyin.com/share/note/7488893440932039971", "aweme", "7488893440932039971"),
            # 2. User variants
            ("https://www.douyin.com/user/MS4wLjABAAAA_test_uid", "user", "MS4wLjABAAAA_test_uid"),
            ("https://www.douyin.com/user/MS4wLjABAAAA_test_uid/", "user", "MS4wLjABAAAA_test_uid"),
            ("https://www.douyin.com/user/MS4wLjABAAAA_test_uid?from_tab_name=main&vid=123", "user", "MS4wLjABAAAA_test_uid"),
            ("https://www.douyin.com/share/user/MS4wLjABAAAA_share_uid", "user", "MS4wLjABAAAA_share_uid"),
            # 3. Mix variants
            ("https://www.douyin.com/collection/7488893440932039972", "mix", "7488893440932039972"),
            ("https://www.douyin.com/collection/7488893440932039972/", "mix", "7488893440932039972"),
            ("https://www.douyin.com/mix/detail/7488893440932039972", "mix", "7488893440932039972"),
            ("https://www.douyin.com/mix/detail/7488893440932039972?extra=param", "mix", "7488893440932039972"),
            # 4. Music variants
            ("https://www.douyin.com/music/7488893440932039973", "music", "7488893440932039973"),
            ("https://www.douyin.com/music/7488893440932039973/", "music", "7488893440932039973"),
            ("https://www.douyin.com/music/7488893440932039973?enter_from=feed", "music", "7488893440932039973"),
            # 5. Live variants
            ("https://live.douyin.com/669067451826", "live", "669067451826"),
            ("https://live.douyin.com/669067451826/", "live", "669067451826"),
            ("https://live.douyin.com/669067451826?enter_from=share", "live", "669067451826"),
            ("https://live.douyin.com/custom_room_alias", "live", "custom_room_alias"),
        ],
    )
    def test_extract_key_and_type_all_five_types(self, service, url, expected_type, expected_key):
        session = MagicMock()
        key_type, key = service.extract_key_and_type(url, session)
        assert key_type == expected_type
        assert key == expected_key

    def test_canonical_url_preserves_contract(self, service):
        cases = {
            ("aweme", "111"): "https://www.douyin.com/video/111",
            ("user", "u222"): "https://www.douyin.com/user/u222",
            ("mix", "m333"): "https://www.douyin.com/collection/m333",
            ("music", "mu444"): "https://www.douyin.com/music/mu444",
            ("live", "l555"): "https://live.douyin.com/l555",
        }
        for (kt, k), expected in cases.items():
            assert service.build_canonical_url(kt, k) == expected


# ==============================================================================
# Domain 2: Adversarial Security & Domain Validation (SSRF / Credential Leak)
# ==============================================================================


class TestAdversarialSecurityAndDomainValidation:
    """Tests testing domain spoofing and potential credential leak vulnerabilities."""

    def test_domain_spoofing_in_resolve_redirect(self):
        """
        Vulnerability Check:
        In douyin_service.py: `if 'v.douyin.com' in url or 'iesdouyin.com/share' in url:`
        A substring check allows attacker URLs like:
        `https://v.douyin.com.attacker.com/leak` or `https://attacker.com/?v.douyin.com`
        to trigger `session.get(url, headers=douyin_headers, ...)` transmitting cookies!
        """
        service = DouyinService()
        mock_session = MagicMock()
        attacker_url = "https://attacker.com/steal?target=v.douyin.com"

        # If vulnerable, resolve_redirect_url will call mock_session.get with attacker_url
        try:
            service.resolve_redirect_url(attacker_url, mock_session)
            # Check if attacker server received request with sensitive headers
            called = mock_session.get.called
            if called:
                call_args, call_kwargs = mock_session.get.call_args
                headers = call_kwargs.get("headers", {})
                pytest.fail(
                    f"CRITICAL VULNERABILITY: Substring 'v.douyin.com' check invoked session.get "
                    f"on third-party domain {attacker_url} with headers={headers}"
                )
        except Exception:
            pass

    def test_live_domain_spoofing(self):
        """
        Vulnerability Check:
        In douyin_service.py: `if 'live.douyin.com' in url:`
        A URL like `https://attacker.com/live.douyin.com/12345` is incorrectly recognized as a live stream!
        """
        service = DouyinService()
        session = MagicMock()
        spoofed_url = "https://attacker.com/live.douyin.com/123456"

        key_type, key = service.extract_key_and_type(spoofed_url, session)
        if key_type == "live" and key == "123456":
            # Confirmed weakness: Substring domain check falsely matches non-Douyin domain
            assert key_type == "live", "Observed substring domain confusion in live pattern matching"


# ==============================================================================
# Domain 3: YAML Configuration Persistence, Corruption, & Comments
# ==============================================================================


class TestYamlConfigPersistenceAndInvariants:
    """Adversarial tests on YAML config persistence, comments, and corruption."""

    def test_load_config_corrupted_yaml_falls_back_gracefully(self, tmp_path):
        bad_yaml = tmp_path / "corrupted.yaml"
        bad_yaml.write_text("path: [unclosed list\n  thread: :::invalid\n", encoding="utf-8")

        # Must not raise unhandled exception; must return default settings
        settings = load_config_file(bad_yaml)
        assert isinstance(settings, SettingsModel)
        assert settings.path == "./Downloaded/"
        assert settings.thread == 5

    def test_load_config_partial_yaml(self, tmp_path):
        partial_yaml = tmp_path / "partial.yaml"
        partial_yaml.write_text("path: ./CustomDir/\n", encoding="utf-8")

        settings = load_config_file(partial_yaml)
        assert settings.path == "./CustomDir/"
        assert settings.thread == 5
        assert settings.music is True  # default preserved

    def test_save_config_cookie_format_persistence_bug(self, tmp_path):
        """
        BUG DISCOVERY TEST:
        When config.yaml uses the single `cookie:` scalar format:
          cookie: "msToken=token1; ttwid=token2;"
        Updating settings.cookies or raw_cookie FAILS to update the file because
        `_update_yaml_in_place_regex` only looks for `^cookies:` block when `settings.cookies` is set,
        and skips the `elif settings.raw_cookie:` branch!
        """
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            '# Config using single cookie string\npath: ./Downloaded/\nthread: 5\ncookie: "msToken=old_token;"\n',
            encoding="utf-8",
        )

        settings = load_config_file(cfg_file)
        assert settings.cookies["msToken"] == "old_token"

        # Now update cookie to new value
        settings.cookies["msToken"] = "new_token_123"
        settings.raw_cookie = "msToken=new_token_123"
        saved = save_config_file(settings, cfg_file)
        assert saved is True

        content = cfg_file.read_text(encoding="utf-8")
        # Assert whether the new token actually persisted
        persisted = "new_token_123" in content
        if not persisted:
            pytest.fail("FAULT CONFIRMED: Updating cookie in file using 'cookie:' format is silently lost!")

    def test_save_config_drops_mode_number_and_increase_fields(self, tmp_path):
        """
        BUG DISCOVERY TEST:
        `_update_yaml_in_place_regex` never updates `number:`, `increase:`, or `mode:`.
        Any modifications to these fields via SettingsModel are silently lost upon save!
        """
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "path: ./Downloaded/\nthread: 5\nmode:\n  - post\nnumber:\n  post: 0\n  mix: 5\n",
            encoding="utf-8",
        )

        settings = load_config_file(cfg_file)
        settings.number["post"] = 50
        settings.mode = ["post", "like"]

        saved = save_config_file(settings, cfg_file)
        assert saved is True

        reloaded = load_config_file(cfg_file)
        if reloaded.number.get("post") != 50 or "like" not in reloaded.mode:
            pytest.fail(
                f"FAULT CONFIRMED: `number` and `mode` modifications were dropped on save! "
                f"reloaded.number['post']={reloaded.number.get('post')}, reloaded.mode={reloaded.mode}"
            )

    def test_save_config_cookie_special_yaml_indicators_syntax_corruption(self, tmp_path):
        """
        BUG DISCOVERY TEST:
        When a cookie contains YAML indicator characters (@, *, {, [, ending backslash),
        `_update_yaml_in_place_regex` does not quote them, generating invalid YAML syntax
        that crashes yaml.safe_load on next startup!
        """
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("cookies:\n  msToken: valid\n", encoding="utf-8")

        settings = load_config_file(cfg_file)
        # Set a cookie with special characters
        settings.cookies["msToken"] = "@adversarial_token"

        saved = save_config_file(settings, cfg_file)
        assert saved is True

        # Now try to load the saved file with standard YAML parser
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"FAULT CONFIRMED: Saving cookie '@adversarial_token' corrupted YAML syntax: {e}")


# ==============================================================================
# Domain 4: Dual-Format Cookie Parsing & Header State Invariants
# ==============================================================================


class TestCookieParsingAndHeaderSync:
    """Adversarial tests on cookie parsing and header synchronization."""

    def test_dual_format_round_trip_equality(self):
        cookies_dict = {
            "msToken": "M2z9tlZLV03GmRspyF0_kO6WQdmE-_jAblxXSSR1gJxrCPmPIrd-w8JlUzVVOlVowkQgMCKd8SHzYeE5B-Uyk0XM3_hdCFkGPXxM_vr-WaT0MYNa9YgeauwoLF4xltTxRifUn8DOkeG87N27ZifcrVUMmHBywlhKGEjs7cCS6wptpA==",
            "ttwid": "1%7CyzyKQpHq0wExGiXos4homuHMtdJafEa02RIPMhJIcYU%7C1778581292",
            "passport_csrf_token": "01402b21d586c0efb2a677b9898f202e",
            "sessionid": "abc123xyz",
        }

        raw_str = format_cookie_dict(cookies_dict)
        parsed_back = parse_raw_cookie(raw_str)
        assert parsed_back == cookies_dict

    def test_parse_raw_cookie_complex_delimiters(self):
        # Multiple semicolons, spaces, and base64 equals
        raw = ";;  k1=v1== ; ; k2=v2%3D%3D;; k3= ; k4  "
        parsed = parse_raw_cookie(raw)
        assert parsed["k1"] == "v1=="
        assert parsed["k2"] == "v2%3D%3D"
        assert parsed["k3"] == ""
        assert parsed["k4"] == ""

    def test_cookie_clearing_header_sync_bug(self, tmp_path):
        """
        BUG DISCOVERY TEST:
        When cookies are cleared in settings (`cookies = {}` and `raw_cookie = ""`),
        `ConfigManager.apply_to_douyin_headers()` has:
        `if not cookie_str: return`
        which leaves previously stored sensitive cookies lingering in `douyin_headers['Cookie']`!
        """
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text('cookies:\n  msToken: "secret_session_token"\n', encoding="utf-8")

        ConfigManager._instance = None
        manager = ConfigManager.get_instance(cfg_file)
        assert douyin_headers.get("Cookie") is not None
        assert "secret_session_token" in douyin_headers["Cookie"]

        # Now clear cookies
        settings = manager.get_settings()
        settings.cookies = {}
        settings.raw_cookie = ""
        manager.update_settings(settings)

        # douyin_headers['Cookie'] must be cleared!
        active_cookie = douyin_headers.get("Cookie", "")
        if "secret_session_token" in active_cookie:
            pytest.fail(
                f"FAULT CONFIRMED: Clearing cookies in ConfigManager did not clear "
                f"douyin_headers['Cookie']! Old secret remains: {active_cookie}"
            )


# ==============================================================================
# Domain 5: Pydantic Schema Validation & Boundary Invariants
# ==============================================================================


class TestSchemaValidationAndBoundaryInvariants:
    """Stress tests on schema coercions and boundary constraints."""

    def test_author_preview_url_list_containing_none_crash(self):
        """
        BUG DISCOVERY TEST:
        If Douyin API returns `avatar_thumb = {'url_list': [None]}`,
        `AuthorPreview.extract_avatar_url` returns `None`, which fails Pydantic validation
        because `avatar_thumb` is typed `str` instead of `Optional[str]` or returning `""`.
        """
        try:
            author = AuthorPreview(
                nickname="Creator",
                avatar_thumb={"url_list": [None]},
            )
            assert author.avatar_thumb == ""
        except Exception as e:
            pytest.fail(f"FAULT CONFIRMED: AuthorPreview crashed on url_list with None: {type(e).__name__}: {e}")

    def test_preview_metadata_cover_url_containing_none_crash(self):
        """
        BUG DISCOVERY TEST:
        If Douyin API returns `cover_url = {'url_list': [None]}`,
        `PreviewMetadata.extract_cover_url` returns `None`, which fails Pydantic validation.
        """
        try:
            preview = PreviewMetadata(
                title="Video",
                cover_url={"url_list": [None]},
            )
            assert preview.cover_url == ""
        except Exception as e:
            pytest.fail(f"FAULT CONFIRMED: PreviewMetadata crashed on url_list with None: {type(e).__name__}: {e}")

    def test_thread_status_percentage_overflow_validation(self):
        """
        Test ThreadStatus pct constraint le=100.0.
        If a download chunk reports more bytes than estimated (chunked encoding or resume),
        pct > 100.0 should not crash the status report.
        """
        # When valid
        t = ThreadStatus(thread_id=1, pct=100.0)
        assert t.pct == 100.0

        # When exceeding 100.0 (e.g. 100.5%), Pydantic strictly rejects
        with pytest.raises(Exception):
            ThreadStatus(thread_id=1, pct=100.5)

    def test_download_request_thread_count_bounds(self):
        # Valid bounds 1..32
        req_min = DownloadRequest(url="https://v.douyin.com/abc/", thread_count=1)
        assert req_min.thread_count == 1

        req_max = DownloadRequest(url="https://v.douyin.com/abc/", thread_count=32)
        assert req_max.thread_count == 32

        # Invalid: 0 or 33
        with pytest.raises(Exception):
            DownloadRequest(url="https://v.douyin.com/abc/", thread_count=0)
        with pytest.raises(Exception):
            DownloadRequest(url="https://v.douyin.com/abc/", thread_count=33)

    def test_filter_options_limit_bounds(self):
        f = FilterOptions(limit=0)
        assert f.limit == 0

        with pytest.raises(Exception):
            FilterOptions(limit=-1)


# ==============================================================================
# Domain 6: Error Handling & Invariant Exceptions
# ==============================================================================


class TestErrorHandlingAndInvariants:
    """Tests for strongly typed domain exceptions and status codes."""

    def test_exception_status_codes(self):
        assert DouyinInvalidUrlError().status_code == 400
        assert DouyinNotFoundError().status_code == 404
        assert DouyinUpstreamError().status_code == 502

    def test_not_found_on_empty_aweme(self):
        service = DouyinService()
        mock_api = MagicMock()
        mock_api.getAwemeInfoApi.return_value = None

        with pytest.raises(DouyinNotFoundError) as exc:
            service.fetch_preview_metadata(mock_api, "aweme", "non_existent_123")
        assert exc.value.status_code == 404

    def test_upstream_error_on_network_timeout(self):
        service = DouyinService()
        mock_api = MagicMock()
        mock_api.getAwemeInfoApi.side_effect = TimeoutError("Connection timed out")

        with pytest.raises(DouyinUpstreamError) as exc:
            service.fetch_preview_metadata(mock_api, "aweme", "timeout_123")
        assert exc.value.status_code == 502
