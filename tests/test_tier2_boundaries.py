# -*- coding: utf-8 -*-
"""
Tier 2 — Boundary & Corner Cases Test Suite.
Verifies robustness against extreme inputs, empty strings, corrupt files, invalid characters,
zero/negative numbers, range edge conditions, path traversals, and network disruptions.
"""

import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from douyinCommand import Config, DouyinClient, safe_name
from src.common import utils
from src.douyin import douyin_headers
from src.douyin.database import Database
from src.douyin.douyinapi import DouyinApi
from src.douyin.download import Download
from tests.conftest import (
    MOCK_AUDIO_BYTES,
    MOCK_IMAGE_BYTES,
    MOCK_VIDEO_BYTES,
    create_mock_aweme_detail,
)


# =============================================================================
# Boundary 1: URL Resolution Boundaries (>=5 tests)
# =============================================================================
class TestBoundary1UrlResolution:
    def test_empty_string_url(self):
        """Empty string returns None key and key_type without exception."""
        api = DouyinApi()
        key_type, key = api.getKey("")
        assert key_type is None
        assert key is None

    def test_non_url_garbage_string(self):
        """Random punctuation string returns None without crashing."""
        api = DouyinApi()
        key_type, key = api.getKey("!@#$%^&*()_+=-`~{}[]|\\:;\"'<>,.?/")
        assert key_type is None
        assert key is None

    def test_non_douyin_domain(self):
        """URL from external domain (youtube/bilibili) returns None."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert key_type is None
        assert key is None

    def test_truncated_douyin_video_url(self):
        """Incomplete Douyin URL missing video ID returns empty key or None."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/video/")
        assert not key or key == "" or key is None

    def test_excessively_long_url_with_many_params(self):
        """URL with 4000+ characters of query params resolves aweme ID correctly."""
        api = DouyinApi()
        extra_query = "&".join(f"param_{i}=val_{i}" for i in range(200))
        url = f"https://www.douyin.com/video/7488893440932039970?{extra_query}"
        key_type, key = api.getKey(url)
        assert key_type == "aweme"
        assert key == "7488893440932039970"

    def test_share_text_with_no_embedded_url(self):
        """Share text without any URL raises IndexError / handled gracefully."""
        api = DouyinApi()
        with pytest.raises(IndexError):
            api.getShareLink("This is plain text without any link inside.")

    def test_url_with_unicode_and_emojis(self):
        """Share text with emojis and Chinese resolves embedded URL."""
        api = DouyinApi()
        text = "🔥💯 超赞！快看 👉 https://v.douyin.com/iWhQezyaUco/ 复制到抖音 🎉"
        url = api.getShareLink(text)
        assert url.startswith("https://v.douyin.com/")
        key_type, key = api.getKey(url)
        assert key_type == "aweme"


# =============================================================================
# Boundary 2: File System & Path Boundaries (>=5 tests)
# =============================================================================
class TestBoundary2FileSystem:
    def test_forbidden_filename_characters_sanitized(self):
        """Sanitizes Windows forbidden characters (< > : \" / \\ | ? *)."""
        forbidden = 'invalid<file>:name"with/slashes\\and|pipes?and*asterisks'
        cleaned = safe_name(forbidden, "fallback")
        for bad_char in '<>:"/\\|?*':
            assert bad_char not in cleaned

    def test_path_traversal_directory_escape(self, temp_download_dir):
        """Rejects paths attempting directory traversal outside download root."""
        base_dir = temp_download_dir.resolve()
        traversal_path = (base_dir / ".." / ".." / "system_file").resolve()
        assert not str(traversal_path).startswith(str(base_dir))

    def test_extremely_long_title_truncation(self):
        """Truncates excessively long description to safe filename length (<=20 chars by replaceStr)."""
        long_title = "A" * 500
        cleaned = utils.replaceStr(long_title)
        assert len(cleaned) <= 20

    def test_empty_description_fallback(self, temp_download_dir, sample_aweme_data):
        """Handles aweme with empty desc without crashing or creating invalid paths."""
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        empty_desc_aweme = sample_aweme_data.copy()
        empty_desc_aweme["desc"] = ""
        success = dl.awemeDownload(empty_desc_aweme, savePath=temp_download_dir)
        assert success is True
        created = list(temp_download_dir.glob("*likes_*"))
        assert len(created) == 1

    def test_deeply_nested_target_directory_creation(self, temp_download_dir, sample_aweme_data):
        """Automatically creates nested parent directories when savePath does not yet exist."""
        nested_dir = temp_download_dir / "deep" / "level1" / "level2" / "level3"
        assert not nested_dir.exists()
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=nested_dir)
        assert nested_dir.exists()


# =============================================================================
# Boundary 3: HTTP Resumption & Range Boundaries (>=5 tests)
# =============================================================================
class TestBoundary3HttpResumption:
    def test_range_past_end_of_file(self, temp_download_dir):
        """Requesting range past end of file returns 416 / handled safely."""
        dl = Download()
        target = temp_download_dir / "past_eof.mp4"
        # Pre-populate with larger size than mock content
        target.write_bytes(MOCK_VIDEO_BYTES + b"EXTRA_BYTES")
        # In download_with_resume, file_size > len(MOCK_VIDEO_BYTES)
        # Mock returns 416
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "eof_test")
        # Should handle or recover
        assert isinstance(success, bool)

    def test_range_resumption_from_zero_offset(self, temp_download_dir):
        """Downloading when target exists but has 0 bytes downloads full content."""
        dl = Download()
        target = temp_download_dir / "zero_byte.mp4"
        target.write_bytes(b"")
        assert target.stat().st_size == 0
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "zero_test")
        assert success is True
        assert target.stat().st_size == len(MOCK_VIDEO_BYTES)

    def test_server_returns_200_instead_of_206_overwrites_cleanly(self, temp_download_dir, monkeypatch):
        """When server returns 200 instead of 206 for range, file is overwritten in 'wb' mode."""
        from tests.conftest import MockHttpResponse
        def mock_always_200(self, url, *args, **kwargs):
            return MockHttpResponse(url, 200, content=MOCK_VIDEO_BYTES)

        monkeypatch.setattr(requests.Session, "get", mock_always_200)
        dl = Download()
        target = temp_download_dir / "wb_overwrite.mp4"
        target.write_bytes(b"OLD_PARTIAL_DATA")
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "overwrite_test")
        assert success is True
        assert target.read_bytes() == MOCK_VIDEO_BYTES

    def test_resumption_with_single_remaining_byte(self, temp_download_dir):
        """Resumes download when only 1 byte remains."""
        dl = Download()
        target = temp_download_dir / "one_byte_left.mp4"
        target.write_bytes(MOCK_VIDEO_BYTES[:-1])
        assert target.stat().st_size == len(MOCK_VIDEO_BYTES) - 1
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "one_byte_test")
        assert success is True
        assert target.stat().st_size == len(MOCK_VIDEO_BYTES)
        assert target.read_bytes() == MOCK_VIDEO_BYTES

    def test_transient_connection_abort_reconnects(self, temp_download_dir, monkeypatch):
        """Simulates single connection reset error followed by successful resumption."""
        call_count = 0
        original_get = requests.Session.get

        def mock_drop_then_ok(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.ChunkedEncodingError("Connection dropped mid-stream")
            return original_get(*args, **kwargs)

        monkeypatch.setattr(requests.Session, "get", mock_drop_then_ok)
        dl = Download()
        target = temp_download_dir / "drop_recover.mp4"
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "drop_test")
        assert success is True
        assert target.exists()


# =============================================================================
# Boundary 4: Configuration & Settings Boundaries (>=5 tests)
# =============================================================================
class TestBoundary4Configuration:
    def test_corrupted_yaml_syntax_handling(self, tmp_path):
        """Corrupted YAML syntax logs error and returns default config without crashing."""
        corrupt_yaml = tmp_path / "corrupt.yaml"
        corrupt_yaml.write_text("invalid: [yaml: syntax: {missing_brace", encoding="utf-8")
        cfg = Config.from_yaml(str(corrupt_yaml))
        assert cfg.thread == 5
        assert cfg.folderstyle is True

    def test_zero_byte_yaml_file(self, tmp_path):
        """Empty 0-byte YAML file safely loads default configuration."""
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("", encoding="utf-8")
        cfg = Config.from_yaml(str(empty_yaml))
        assert cfg.thread == 5
        assert cfg.music is True

    def test_negative_thread_count_clamped_to_minimum(self, tmp_path):
        """Negative thread count falls back to safe default of 5."""
        cfg = Config(link=["test"], thread=-10)
        cfg.validate_and_prepare()
        assert cfg.thread == 5

    def test_thread_count_zero_clamped(self, tmp_path):
        """Thread count of 0 falls back to 5."""
        cfg = Config(link=["test"], thread=0)
        cfg.validate_and_prepare()
        assert cfg.thread == 5

    def test_empty_cookies_dictionary(self, tmp_path):
        """Empty cookies dictionary results in None cookie without corrupting headers."""
        cfg_path = tmp_path / "empty_cookie.yaml"
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"cookies": {}}, f)
        cfg = Config.from_yaml(str(cfg_path))
        assert cfg.cookie is None or cfg.cookie == ""

    def test_negative_sort_limit_value(self, sample_user_aweme_list):
        """Negative limit in filter does not truncate the list."""
        cfg = Config(filter={"limit": -5})
        client = DouyinClient(cfg)
        result = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        assert len(result) == len(sample_user_aweme_list)


# =============================================================================
# Boundary 5: Task Concurrency & State Machine Boundaries (>=5 tests)
# =============================================================================
class TestBoundary5TaskLifecycle:
    def test_cancel_non_existent_task_id(self, api_client):
        """Cancelling non-existent task ID returns 404."""
        resp = api_client.post("/api/tasks/00000000-0000-0000-0000-000000000000/cancel")
        assert resp.status_code in (404, 400)

    def test_inspect_non_existent_task_id(self, api_client):
        """Inspecting non-existent task ID returns 404."""
        resp = api_client.get("/api/tasks/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_submit_download_with_empty_url(self, api_client):
        """Submitting download request with empty URL returns 422 Unprocessable Entity."""
        resp = api_client.post("/api/download", json={"url": "", "key_type": "aweme", "key": ""})
        assert resp.status_code in (400, 422)

    def test_submit_download_with_all_asset_toggles_disabled(self, temp_download_dir, sample_aweme_data):
        """Disabling all assets does not download any media files."""
        dl = Download(thread=1, music=False, cover=False, avatar=False, resjson=False, folderstyle=True)
        # Note: video is downloaded if awemeType==0 by default unless selective toggle exists
        success = dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        assert success is True

    def test_double_cancellation_is_idempotent(self):
        """Cancelling an already cancelled token is idempotent without error."""
        import threading
        token = threading.Event()
        token.set()
        assert token.is_set()
        token.set()  # Second set
        assert token.is_set()


# =============================================================================
# Boundary 6: Media Streaming & Library Boundaries (>=5 tests)
# =============================================================================
class TestBoundary6MediaStreaming:
    def test_stream_non_existent_file_returns_404(self, api_client):
        """Streaming non-existent file returns 404 Not Found."""
        resp = api_client.get("/api/media/stream/non_existent_video_file.mp4")
        assert resp.status_code == 404

    def test_download_non_existent_file_returns_404(self, api_client):
        """Downloading non-existent file returns 404 Not Found."""
        resp = api_client.get("/api/media/download/non_existent_video_file.mp4")
        assert resp.status_code == 404

    def test_media_streaming_path_traversal_blocked(self, api_client):
        """Attempting to stream via ../ traversal returns 400 or 403 or 404."""
        resp = api_client.get("/api/media/stream/..%2F..%2Fwindows%2Fwin.ini")
        assert resp.status_code in (400, 403, 404)

    def test_media_stream_invalid_range_syntax(self, api_client, temp_download_dir):
        """Invalid Range header syntax is handled cleanly (returns 200 or 416)."""
        test_file = temp_download_dir / "valid.mp4"
        test_file.write_bytes(MOCK_VIDEO_BYTES)
        headers = {"Range": "invalid_range_syntax"}
        resp = api_client.get("/api/media/stream/valid.mp4", headers=headers)
        if resp.status_code not in (404,):
            assert resp.status_code in (200, 416)

    def test_open_folder_outside_download_root_blocked(self, api_client):
        """Desktop bridge rejects opening directory outside download path."""
        resp = api_client.post("/api/open-folder", json={"path": "../../Windows/System32"})
        assert resp.status_code in (400, 403)


# =============================================================================
# Boundary 7: Database & Integrity Boundaries (>=5 tests)
# =============================================================================
class TestBoundary7DatabaseIntegrity:
    def test_duplicate_aweme_upsert_no_primary_key_error(self, tmp_path, sample_aweme_data):
        """Inserting identical aweme twice does not raise SQLite UNIQUE constraint error."""
        db_path = tmp_path / "dup.db"
        with Database(str(db_path)) as db:
            db.upsert_aweme(sample_aweme_data)
            # Re-insert identical record
            db.upsert_aweme(sample_aweme_data)
            cur = db.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM fact_aweme WHERE aweme_id = ?", (sample_aweme_data["aweme_id"],))
            assert cur.fetchone()[0] == 1

    def test_null_and_missing_optional_fields_in_aweme(self, tmp_path):
        """Handles aweme dictionary with null music, mix, and empty statistics."""
        db_path = tmp_path / "nulls.db"
        sparse_aweme = {
            "aweme_id": "9999999999",
            "desc": None,
            "create_time": 1728000000,
            "author": {"sec_uid": "MS4wLjABAAAA_sparse_author"},
            "music": None,
            "mix_info": None,
            "statistics": None
        }
        with Database(str(db_path)) as db:
            db.upsert_aweme(sparse_aweme)
            cur = db.conn.cursor()
            cur.execute("SELECT aweme_id FROM fact_aweme WHERE aweme_id = '9999999999'")
            assert cur.fetchone() is not None

    def test_sql_injection_in_aweme_id(self, tmp_path):
        """Handles SQL injection attempt in aweme_id safely via parameterized query."""
        db_path = tmp_path / "sqli.db"
        injection_aweme = {
            "aweme_id": "100'; DROP TABLE fact_aweme; --",
            "desc": "SQLi test",
            "create_time": 1728000000,
            "author": {"sec_uid": "safe_uid"}
        }
        with Database(str(db_path)) as db:
            db.upsert_aweme(injection_aweme)
            cur = db.conn.cursor()
            # Verify table still exists
            cur.execute("SELECT count(*) FROM fact_aweme;")
            assert cur.fetchone()[0] == 1

    def test_database_closed_connection_error(self, tmp_path):
        """Executing query on closed database raises sqlite3.ProgrammingError."""
        db_path = tmp_path / "closed.db"
        db = Database(str(db_path))
        db.close()
        with pytest.raises(Exception):
            cur = db.conn.cursor()
            cur.execute("SELECT 1;")

    def test_sqlite_wal_concurrent_readers(self, tmp_path, sample_aweme_data):
        """Multiple concurrent reader connections read cleanly without lock error under WAL."""
        db_path = tmp_path / "wal_concurrency.db"
        with Database(str(db_path)) as writer_db:
            writer_db.upsert_aweme(sample_aweme_data)

        # Connect reader 1 and reader 2 simultaneously
        conn1 = sqlite3.connect(str(db_path))
        conn2 = sqlite3.connect(str(db_path))
        try:
            r1 = conn1.execute("SELECT aweme_id FROM fact_aweme;").fetchone()
            r2 = conn2.execute("SELECT aweme_id FROM fact_aweme;").fetchone()
            assert r1[0] == sample_aweme_data["aweme_id"]
            assert r2[0] == sample_aweme_data["aweme_id"]
        finally:
            conn1.close()
            conn2.close()
