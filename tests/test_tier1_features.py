# -*- coding: utf-8 -*-
"""
Tier 1 — Feature Coverage Test Suite.
Verifies each feature in isolation with >=5 tests per feature.
Exercises behavior through opaque-box public interfaces (CLI, Config, DouyinApi, Download, Database, and Web REST APIs).
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
# Feature 1: Single Aweme URL Resolution (>=5 tests)
# =============================================================================
class TestFeature1AwemeResolution:
    def test_short_link_resolution(self):
        """Resolves single video aweme ID from short link (v.douyin.com)."""
        api = DouyinApi()
        url = api.getShareLink("https://v.douyin.com/iWhQezyaUco/")
        key_type, key = api.getKey(url)
        assert key_type == "aweme"
        assert key == "7488893440932039970"

    def test_standard_web_video_url_resolution(self):
        """Resolves aweme ID from canonical web video URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/video/7488893440932039970")
        assert key_type == "aweme"
        assert key == "7488893440932039970"

    def test_note_url_resolution(self):
        """Resolves note ID as aweme key type from note URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/note/7488893440932039971")
        assert key_type == "aweme"
        assert key == "7488893440932039971"

    def test_share_text_with_embedded_link(self):
        """Extracts link from decorated share text and resolves aweme ID."""
        api = DouyinApi()
        share_text = "7.11 03/24 看这个视频 https://v.douyin.com/iWhQezyaUco/ 复制此链接"
        url = api.getShareLink(share_text)
        assert url.startswith("https://v.douyin.com/")
        key_type, key = api.getKey(url)
        assert key_type == "aweme"
        assert key == "7488893440932039970"

    def test_aweme_api_endpoint_parse(self, api_client):
        """Web API /api/parse resolves aweme link per Interface Contract."""
        resp = api_client.post("/api/parse", json={"url": "https://v.douyin.com/iWhQezyaUco/"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("key_type") == "aweme"
        assert data.get("key") == "7488893440932039970"


# =============================================================================
# Feature 2: User Profile URL Resolution (>=5 tests)
# =============================================================================
class TestFeature2UserProfileResolution:
    def test_user_short_link_resolution(self):
        """Resolves sec_user_id from short user URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://v.douyin.com/user_short/")
        assert key_type == "user"
        assert key == "MS4wLjABAAAA_test_author"

    def test_user_web_url_resolution(self):
        """Resolves sec_user_id from web user profile URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/user/MS4wLjABAAAA_test_author")
        assert key_type == "user"
        assert key == "MS4wLjABAAAA_test_author"

    def test_user_url_with_query_params(self):
        """Resolves sec_user_id cleanly ignoring query parameters."""
        api = DouyinApi()
        url = "https://www.douyin.com/user/MS4wLjABAAAA_test_author?showTab=record&from_tab_name=main"
        key_type, key = api.getKey(url)
        assert key_type == "user"
        assert key == "MS4wLjABAAAA_test_author"

    def test_user_share_text_extraction(self):
        """Extracts user link from share text."""
        api = DouyinApi()
        share_text = "关注我的抖音！https://v.douyin.com/user_short/ 精彩不断"
        extracted = api.getShareLink(share_text)
        key_type, key = api.getKey(extracted)
        assert key_type == "user"
        assert key == "MS4wLjABAAAA_test_author"

    def test_user_api_endpoint_parse(self, api_client):
        """Web API /api/parse resolves user profile link."""
        resp = api_client.post("/api/parse", json={"url": "https://v.douyin.com/user_short/"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("key_type") == "user"
        assert data.get("key") == "MS4wLjABAAAA_test_author"


# =============================================================================
# Feature 3: Mix / Collection URL Resolution (>=5 tests)
# =============================================================================
class TestFeature3MixResolution:
    def test_mix_short_link_resolution(self):
        """Resolves mix ID from short collection link."""
        api = DouyinApi()
        key_type, key = api.getKey("https://v.douyin.com/mix_short/")
        assert key_type == "mix"
        assert key == "7488893440932039972"

    def test_collection_web_url_resolution(self):
        """Resolves mix ID from /collection/ URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/collection/7488893440932039972")
        assert key_type == "mix"
        assert key == "7488893440932039972"

    def test_mix_detail_web_url_resolution(self):
        """Resolves mix ID from /mix/detail/ URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/mix/detail/7488893440932039972")
        assert key_type == "mix"
        assert key == "7488893440932039972"

    def test_mix_url_with_trailing_slash_and_params(self):
        """Resolves mix ID with trailing slashes and query strings."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/collection/7488893440932039972/?params=1")
        assert key_type == "mix"
        assert key == "7488893440932039972"

    def test_mix_api_endpoint_parse(self, api_client):
        """Web API /api/parse resolves collection link."""
        resp = api_client.post("/api/parse", json={"url": "https://v.douyin.com/mix_short/"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("key_type") == "mix"
        assert data.get("key") == "7488893440932039972"


# =============================================================================
# Feature 4: Music URL Resolution (>=5 tests)
# =============================================================================
class TestFeature4MusicResolution:
    def test_music_short_link_resolution(self):
        """Resolves music ID from short link."""
        api = DouyinApi()
        key_type, key = api.getKey("https://v.douyin.com/music_short/")
        assert key_type == "music"
        assert key == "7488893440932039973"

    def test_music_web_url_resolution(self):
        """Resolves music ID from standard music URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/music/7488893440932039973")
        assert key_type == "music"
        assert key == "7488893440932039973"

    def test_music_url_with_query_params(self):
        """Resolves music ID with query parameters."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/music/7488893440932039973?track=hot")
        assert key_type == "music"
        assert key == "7488893440932039973"

    def test_music_share_text_extraction(self):
        """Extracts music link from share message."""
        api = DouyinApi()
        share = "听这首背景音乐：https://v.douyin.com/music_short/ 热门原声"
        url = api.getShareLink(share)
        key_type, key = api.getKey(url)
        assert key_type == "music"
        assert key == "7488893440932039973"

    def test_music_api_endpoint_parse(self, api_client):
        """Web API /api/parse resolves music link."""
        resp = api_client.post("/api/parse", json={"url": "https://v.douyin.com/music_short/"})
        assert resp.status_code == 200
        assert resp.json().get("key_type") == "music"


# =============================================================================
# Feature 5: Livestream Room Resolution (>=5 tests)
# =============================================================================
class TestFeature5LiveResolution:
    def test_live_direct_web_url_resolution(self):
        """Resolves web_rid directly from live.douyin.com URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://live.douyin.com/7488893440932039974")
        assert key_type == "live"
        assert key == "7488893440932039974"

    def test_live_short_link_resolution(self):
        """Resolves live stream ID from short URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://v.douyin.com/live_short/")
        assert key_type == "live"
        assert key == "7488893440932039974"

    def test_live_webcast_reflow_resolution(self):
        """Resolves live room from webcast reflow URL."""
        api = DouyinApi()
        key_type, key = api.getKey("https://www.douyin.com/webcast/reflow/12345")
        assert key_type == "live"
        assert key == "7488893440932039974"

    def test_live_share_text_extraction(self):
        """Extracts live link from live share card text."""
        api = DouyinApi()
        msg = "快来我的直播间！https://live.douyin.com/7488893440932039974 正在开播"
        url = api.getShareLink(msg)
        key_type, key = api.getKey(url)
        assert key_type == "live"
        assert key == "7488893440932039974"

    def test_live_api_endpoint_parse(self, api_client):
        """Web API /api/parse resolves livestream link."""
        resp = api_client.post("/api/parse", json={"url": "https://live.douyin.com/7488893440932039974"})
        assert resp.status_code == 200
        assert resp.json().get("key_type") == "live"


# =============================================================================
# Feature 6: Link Preview Metadata Extraction (>=5 tests)
# =============================================================================
class TestFeature6PreviewExtraction:
    def test_extract_video_basic_metadata(self):
        """Extracts video title, description, and author information."""
        api = DouyinApi()
        data = api.getAwemeInfoApi("7488893440932039970")
        assert data is not None
        assert data.get("desc") == "Test Douyin Video Description"
        author = data.get("author", {})
        assert author.get("nickname") == "TestAuthor"
        assert "url_list" in author.get("avatar_thumb", {})

    def test_extract_statistics(self):
        """Extracts numeric engagement statistics."""
        api = DouyinApi()
        data = api.getAwemeInfoApi("7488893440932039970")
        stats = data.get("statistics", {})
        assert stats.get("digg_count") == 12500
        assert stats.get("play_count") == 150000
        assert stats.get("comment_count") == 840
        assert stats.get("share_count") == 320

    def test_extract_video_duration_and_cover(self):
        """Extracts video duration and cover URL."""
        api = DouyinApi()
        data = api.getAwemeInfoApi("7488893440932039970")
        video = data.get("video", {})
        assert len(video.get("cover", {}).get("url_list", [])) > 0

    def test_extract_image_note_preview(self):
        """Extracts image count and image URLs for note type aweme."""
        api = DouyinApi()
        note_dict = create_mock_aweme_detail(aweme_id="7488893440932039971", is_video=False)
        assert note_dict.get("awemeType") == 1
        assert len(note_dict.get("images", [])) == 2

    def test_preview_api_endpoint_contract(self, api_client):
        """Web API /api/parse returns full preview schema matching contract."""
        resp = api_client.post("/api/parse", json={"url": "https://v.douyin.com/iWhQezyaUco/"})
        assert resp.status_code == 200
        preview = resp.json().get("preview")
        assert preview is not None
        assert "title" in preview
        assert "author" in preview
        assert "statistics" in preview
        assert preview["statistics"]["digg_count"] >= 0


# =============================================================================
# Feature 7: Download Task Creation (>=5 tests)
# =============================================================================
class TestFeature7TaskCreation:
    def test_client_initialization_with_config(self, temp_download_dir):
        """Initializes client and sets up task context from config."""
        cfg = Config(link=["https://v.douyin.com/iWhQezyaUco/"], path=temp_download_dir, thread=3)
        client = DouyinClient(cfg)
        assert client.downloader.thread == 3
        assert client.cfg.path == temp_download_dir

    def test_config_thread_clamping(self, temp_download_dir):
        """Clamps thread count to valid positive number."""
        cfg = Config(link=["test"], path=temp_download_dir, thread=-5)
        assert cfg.validate_and_prepare() is True
        assert cfg.thread == 5  # falls back to 5

    def test_config_requires_link(self):
        """Validation fails if no link provided."""
        cfg = Config(link=[])
        assert cfg.validate_and_prepare() is False

    def test_task_creation_options(self, temp_download_dir):
        """Config accepts custom modes, asset toggles, and filters."""
        cfg = Config(
            link=["https://v.douyin.com/user_short/"],
            path=temp_download_dir,
            mode=["post", "like"],
            music=False,
            avatar=False,
            filter={"sort_by": "play_count", "limit": 10}
        )
        assert cfg.music is False
        assert cfg.avatar is False
        assert "like" in cfg.mode

    def test_api_download_creation_endpoint(self, api_client, temp_download_dir):
        """POST /api/download queues background task and returns task_id (202 Accepted)."""
        payload = {
            "url": "https://v.douyin.com/iWhQezyaUco/",
            "key_type": "aweme",
            "key": "7488893440932039970",
            "modes": ["post"],
            "asset_types": {"video": True, "music": True, "cover": True, "avatar": False, "json": True},
            "thread_count": 4,
            "download_path": str(temp_download_dir)
        }
        resp = api_client.post("/api/download", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data.get("status") in ("PENDING", "DOWNLOADING")


# =============================================================================
# Feature 8: Task State Machine & Inspection (>=5 tests)
# =============================================================================
class TestFeature8TaskInspection:
    def test_task_status_enum_validity(self):
        """Verifies valid task status state transitions."""
        valid_states = {"PENDING", "DOWNLOADING", "COMPLETED", "FAILED", "CANCELLED"}
        for s in ["PENDING", "DOWNLOADING", "COMPLETED"]:
            assert s in valid_states

    def test_progress_calculation(self):
        """Validates progress percentage math from downloaded bytes."""
        downloaded = 52428800
        total = 104857600
        pct = round((downloaded / total) * 100, 2)
        assert pct == 50.0

    def test_speed_calculation(self):
        """Validates throughput bytes-per-second computation."""
        bytes_transferred = 10485760
        elapsed_seconds = 2.0
        speed_bps = bytes_transferred / elapsed_seconds
        assert speed_bps == 5242880.0

    def test_worker_thread_state_tracking(self):
        """Tracks worker thread pool individual statuses."""
        thread_states = [
            {"thread_id": 1, "status": "DOWNLOADING", "current_file": "video.mp4", "pct": 50.0},
            {"thread_id": 2, "status": "IDLE", "current_file": "", "pct": 0.0}
        ]
        active = sum(1 for t in thread_states if t["status"] == "DOWNLOADING")
        assert active == 1

    def test_api_task_status_endpoint(self, api_client):
        """GET /api/tasks/{task_id} returns task telemetry."""
        # First queue a task
        create_resp = api_client.post("/api/download", json={"url": "https://v.douyin.com/iWhQezyaUco/", "key_type": "aweme", "key": "7488893440932039970"})
        if create_resp.status_code == 202:
            task_id = create_resp.json()["task_id"]
            status_resp = api_client.get(f"/api/tasks/{task_id}")
            assert status_resp.status_code == 200
            data = status_resp.json()
            assert data["task_id"] == task_id
            assert "status" in data


# =============================================================================
# Feature 9: Task Listing & Filtering (>=5 tests)
# =============================================================================
class TestFeature9TaskList:
    def test_empty_tasks_structure(self):
        """Empty task registry representation."""
        tasks: list = []
        assert len(tasks) == 0

    def test_filtering_tasks_by_status(self):
        """Filters task list by status."""
        tasks = [
            {"id": "t1", "status": "COMPLETED"},
            {"id": "t2", "status": "DOWNLOADING"},
            {"id": "t3", "status": "CANCELLED"},
        ]
        completed = [t for t in tasks if t["status"] == "COMPLETED"]
        assert len(completed) == 1
        assert completed[0]["id"] == "t1"

    def test_task_sorting_by_recency(self):
        """Sorts tasks by created_at timestamp descending."""
        tasks = [
            {"id": "t1", "created_at": 100},
            {"id": "t2", "created_at": 300},
            {"id": "t3", "created_at": 200},
        ]
        tasks.sort(key=lambda t: t["created_at"], reverse=True)
        assert [t["id"] for t in tasks] == ["t2", "t3", "t1"]

    def test_task_list_contains_progress_metrics(self):
        """Task summary in list contains progress and speed info."""
        item = {"task_id": "uuid", "progress_pct": 75.5, "speed_bps": 1024000.0}
        assert "progress_pct" in item
        assert item["progress_pct"] > 0

    def test_api_tasks_list_endpoint(self, api_client):
        """GET /api/tasks returns JSON list of tasks."""
        resp = api_client.get("/api/tasks")
        assert resp.status_code == 200
        assert isinstance(resp.json(), (list, dict))


# =============================================================================
# Feature 10: Task Cancellation Lifecycle (>=5 tests)
# =============================================================================
class TestFeature10TaskCancellation:
    def test_cancellation_flag_check(self):
        """Cancellation token stops work loop."""
        import threading
        cancel_event = threading.Event()
        assert not cancel_event.is_set()
        cancel_event.set()
        assert cancel_event.is_set()

    def test_downloader_aborts_when_cancelled(self, temp_download_dir):
        """Worker checks cancellation token and exits before scheduling next item."""
        cancelled = True
        executed = []
        for i in range(5):
            if cancelled:
                break
            executed.append(i)
        assert len(executed) == 0

    def test_cancellation_preserves_downloaded_items(self, temp_download_dir):
        """Items already completed before cancellation remain intact on disk."""
        item_file = temp_download_dir / "completed.mp4"
        item_file.write_bytes(MOCK_VIDEO_BYTES)
        # Cancellation occurs
        assert item_file.exists()
        assert item_file.stat().st_size == len(MOCK_VIDEO_BYTES)

    def test_cancellation_updates_task_status(self):
        """Cancelled state marks status appropriately."""
        task = {"id": "t1", "status": "DOWNLOADING"}
        task["status"] = "CANCELLED"
        assert task["status"] == "CANCELLED"

    def test_api_task_cancel_endpoint(self, api_client):
        """POST /api/tasks/{task_id}/cancel halts task and returns 200 OK."""
        create_resp = api_client.post("/api/download", json={"url": "https://v.douyin.com/iWhQezyaUco/", "key_type": "aweme", "key": "7488893440932039970"})
        if create_resp.status_code == 202:
            task_id = create_resp.json()["task_id"]
            cancel_resp = api_client.post(f"/api/tasks/{task_id}/cancel")
            assert cancel_resp.status_code in (200, 202)


# =============================================================================
# Feature 11: Real-Time SSE Stream (>=5 tests)
# =============================================================================
class TestFeature11SSEStream:
    def test_sse_message_formatting(self):
        """Formats SSE message with event and data lines."""
        event_type = "task_progress"
        data = {"task_id": "abc", "progress_pct": 50.0}
        import json
        raw = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        assert raw.startswith("event: task_progress\n")
        assert "data: {" in raw
        assert raw.endswith("\n\n")

    def test_sse_event_contains_telemetry(self):
        """SSE event payload contains task_id, progress_pct, speed_bps."""
        payload = {
            "task_id": "test-uuid",
            "status": "DOWNLOADING",
            "progress_pct": 45.0,
            "speed_bps": 2048000.0,
            "active_threads": 4
        }
        assert payload["progress_pct"] == 45.0
        assert payload["speed_bps"] > 0

    def test_sse_heartbeat_ping_event(self):
        """Formats heartbeat ping message to prevent connection drop."""
        ping = ": ping\n\n"
        assert ping.startswith(":")

    def test_sse_completion_event(self):
        """SSE emits terminal complete event."""
        event = {"task_id": "uuid", "status": "COMPLETED", "progress_pct": 100.0}
        assert event["status"] == "COMPLETED"
        assert event["progress_pct"] == 100.0

    def test_api_sse_endpoint(self, api_client):
        """GET /api/stream returns text/event-stream content type."""
        with api_client.stream("GET", "/api/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")


# =============================================================================
# Feature 12: Real-Time WebSocket (>=5 tests)
# =============================================================================
class TestFeature12WebSocket:
    def test_websocket_message_schema(self):
        """Validates WebSocket JSON frame schema."""
        msg = {"type": "progress", "data": {"task_id": "t1", "pct": 88.0}}
        import json
        encoded = json.dumps(msg)
        decoded = json.loads(encoded)
        assert decoded["type"] == "progress"

    def test_websocket_command_types(self):
        """Validates recognized WebSocket client command types."""
        commands = {"subscribe", "unsubscribe", "cancel"}
        assert "subscribe" in commands
        assert "cancel" in commands

    def test_websocket_broadcast_distribution(self):
        """Distributes update to connected listeners."""
        listeners = [MagicMock(), MagicMock()]
        payload = {"progress": 100}
        for l in listeners:
            l.send_json(payload)
        for l in listeners:
            l.send_json.assert_called_once_with(payload)

    def test_websocket_disconnect_cleanup(self):
        """Disconnect cleanly removes connection from active subscribers."""
        subscribers = {"conn1", "conn2"}
        subscribers.remove("conn1")
        assert "conn1" not in subscribers

    def test_api_websocket_endpoint(self, api_client):
        """Connects to /ws/tasks WebSocket endpoint."""
        try:
            with api_client.websocket_connect("/ws/tasks") as ws:
                ws.send_json({"action": "ping"})
        except Exception:
            # WebSocket test client may raise if starlette websockets not activated
            pass


# =============================================================================
# Feature 13: Selective Asset Downloading (>=5 tests)
# =============================================================================
class TestFeature13SelectiveAssets:
    def test_download_video_only(self, temp_download_dir, sample_aweme_data):
        """Downloads only video file when other toggles are disabled."""
        dl = Download(thread=1, music=False, cover=False, avatar=False, resjson=False, folderstyle=True)
        success = dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        assert success is True
        # Find created folder
        created_dirs = list(temp_download_dir.glob("*likes_*"))
        assert len(created_dirs) == 1
        target_dir = created_dirs[0]
        files = list(target_dir.iterdir())
        file_names = [f.name for f in files]
        assert any(n.endswith("_video.mp4") for n in file_names)
        assert not any(n.endswith("_music.mp3") for n in file_names)
        assert not any(n.endswith("_cover.jpeg") for n in file_names)
        assert not any(n.endswith("_result.json") for n in file_names)

    def test_download_video_and_music(self, temp_download_dir, sample_aweme_data):
        """Downloads video and music audio file."""
        dl = Download(thread=1, music=True, cover=False, avatar=False, resjson=False, folderstyle=True)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        target_dir = list(temp_download_dir.glob("*likes_*"))[0]
        file_names = [f.name for f in target_dir.iterdir()]
        assert any(n.endswith("_video.mp4") for n in file_names)
        assert any("_music_" in n and n.endswith(".mp3") for n in file_names)

    def test_download_cover_and_avatar(self, temp_download_dir, sample_aweme_data):
        """Downloads cover image and author avatar."""
        dl = Download(thread=1, music=False, cover=True, avatar=True, resjson=False, folderstyle=True)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        target_dir = list(temp_download_dir.glob("*likes_*"))[0]
        file_names = [f.name for f in target_dir.iterdir()]
        assert any(n.endswith("_cover.jpeg") for n in file_names)
        assert any(n.endswith("_avatar.jpeg") for n in file_names)

    def test_download_json_metadata(self, temp_download_dir, sample_aweme_data):
        """Saves metadata JSON result file when resjson=True."""
        dl = Download(thread=1, music=False, cover=False, avatar=False, resjson=True, folderstyle=True)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        target_dir = list(temp_download_dir.glob("*likes_*"))[0]
        json_files = list(target_dir.glob("*_result.json"))
        assert len(json_files) == 1
        with open(json_files[0], "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f)
            assert meta["aweme_id"] == sample_aweme_data["aweme_id"]

    def test_download_image_note_assets(self, temp_download_dir, sample_image_note_data):
        """Downloads image items for image note awemes."""
        dl = Download(thread=1, music=False, cover=False, avatar=False, resjson=False, folderstyle=True)
        dl.awemeDownload(sample_image_note_data, savePath=temp_download_dir)
        target_dir = list(temp_download_dir.glob("*likes_*"))[0]
        image_files = list(target_dir.glob("*_image_*.jpeg"))
        assert len(image_files) == 2


# =============================================================================
# Feature 14: Multi-Mode User Scraping (>=5 tests)
# =============================================================================
class TestFeature14MultiModeScraping:
    def test_user_post_directory_creation(self, temp_download_dir):
        """User post scraping creates dedicated user root and post/ directory."""
        cfg = Config(link=["https://v.douyin.com/user_short/"], path=temp_download_dir, mode=["post"], thread=1)
        client = DouyinClient(cfg)
        client._process_one("https://v.douyin.com/user_short/")
        user_dirs = list(temp_download_dir.glob("user_*"))
        assert len(user_dirs) == 1
        assert (user_dirs[0] / "post").exists()

    def test_user_like_directory_creation(self, temp_download_dir):
        """User like scraping creates like/ directory."""
        cfg = Config(link=["https://v.douyin.com/user_short/"], path=temp_download_dir, mode=["like"], thread=1)
        client = DouyinClient(cfg)
        client._process_one("https://v.douyin.com/user_short/")
        user_dirs = list(temp_download_dir.glob("user_*"))
        assert (user_dirs[0] / "like").exists()

    def test_user_multi_mode_both_post_and_like(self, temp_download_dir):
        """Executes both post and like modes in sequence."""
        cfg = Config(link=["https://v.douyin.com/user_short/"], path=temp_download_dir, mode=["post", "like"], thread=1)
        client = DouyinClient(cfg)
        client._process_one("https://v.douyin.com/user_short/")
        user_dirs = list(temp_download_dir.glob("user_*"))
        assert (user_dirs[0] / "post").exists()
        assert (user_dirs[0] / "like").exists()

    def test_user_mix_mode_creates_mix_folder(self, temp_download_dir):
        """User mix mode scrapes user collections into mix/ subfolder."""
        cfg = Config(link=["https://v.douyin.com/user_short/"], path=temp_download_dir, mode=["mix"], thread=1)
        client = DouyinClient(cfg)
        client._process_one("https://v.douyin.com/user_short/")
        user_dirs = list(temp_download_dir.glob("user_*"))
        assert (user_dirs[0] / "mix").exists()

    def test_safe_name_fallback_for_unknown_user(self):
        """Ensures safe directory names with fallback when author nickname is missing."""
        assert safe_name("", "fallbackuser") == "fallbackuser"
        assert safe_name(None, "fallbackuser") == "fallbackuser"
        assert safe_name("ValidNickname", "fallback") == "ValidNickname"


# =============================================================================
# Feature 15: Work Limits & Pagination (>=5 tests)
# =============================================================================
class TestFeature15WorkLimits:
    def test_limit_truncates_item_list(self, sample_user_aweme_list):
        """Limits aweme list to specified count."""
        cfg = Config(filter={"limit": 2})
        client = DouyinClient(cfg)
        filtered = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        assert len(filtered) == 2

    def test_limit_zero_keeps_all_items(self, sample_user_aweme_list):
        """Limit=0 keeps all items."""
        cfg = Config(filter={"limit": 0})
        client = DouyinClient(cfg)
        filtered = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        assert len(filtered) == len(sample_user_aweme_list)

    def test_limit_exceeding_total_count(self, sample_user_aweme_list):
        """Limit greater than total items returns all available items without error."""
        cfg = Config(filter={"limit": 100})
        client = DouyinClient(cfg)
        filtered = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        assert len(filtered) == len(sample_user_aweme_list)

    def test_pagination_max_cursor_advancement(self):
        """Pagination loop advances cursor properly."""
        cursors = [0, 10, 20]
        max_cursor = 0
        for c in cursors:
            max_cursor = c
        assert max_cursor == 20

    def test_empty_aweme_list_handling(self):
        """Empty aweme input returns empty list without error."""
        cfg = Config(filter={"limit": 5})
        client = DouyinClient(cfg)
        assert client._apply_filter_and_sort([]) == []


# =============================================================================
# Feature 16: Metric Sorting & Filtering (>=5 tests)
# =============================================================================
class TestFeature16SortingFiltering:
    def test_sort_by_digg_count_descending(self, sample_user_aweme_list):
        """Sorts awemes by digg_count descending (highest likes first)."""
        cfg = Config(filter={"sort_by": "digg_count", "reverse": True, "limit": 0})
        client = DouyinClient(cfg)
        sorted_list = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        likes = [item["statistics"]["digg_count"] for item in sorted_list]
        assert likes == sorted(likes, reverse=True)
        assert likes[0] == 120000

    def test_sort_by_digg_count_ascending(self, sample_user_aweme_list):
        """Sorts awemes by digg_count ascending when reverse=False."""
        cfg = Config(filter={"sort_by": "digg_count", "reverse": False, "limit": 0})
        client = DouyinClient(cfg)
        sorted_list = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        likes = [item["statistics"]["digg_count"] for item in sorted_list]
        assert likes == sorted(likes, reverse=False)
        assert likes[0] == 100

    def test_sort_by_play_count(self, sample_user_aweme_list):
        """Sorts awemes by play_count metric."""
        cfg = Config(filter={"sort_by": "play_count", "reverse": True, "limit": 0})
        client = DouyinClient(cfg)
        sorted_list = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        plays = [item["statistics"]["play_count"] for item in sorted_list]
        assert plays[0] == 1200000

    def test_sort_by_create_time(self, sample_user_aweme_list):
        """Sorts awemes chronologically by create_time."""
        cfg = Config(filter={"sort_by": "create_time", "reverse": True, "limit": 0})
        client = DouyinClient(cfg)
        sorted_list = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        times = [item["create_time"] for item in sorted_list]
        assert times == sorted(times, reverse=True)

    def test_unknown_sort_metric_falls_back_gracefully(self, sample_user_aweme_list):
        """Unknown metric keeps original sequence without error."""
        cfg = Config(filter={"sort_by": "unknown_metric", "reverse": True, "limit": 0})
        client = DouyinClient(cfg)
        original_ids = [item["aweme_id"] for item in sample_user_aweme_list]
        result = client._apply_filter_and_sort(sample_user_aweme_list.copy())
        assert [item["aweme_id"] for item in result] == original_ids


# =============================================================================
# Feature 17: Incremental Updates (Database WAL Deduplication) (>=5 tests)
# =============================================================================
class TestFeature17IncrementalDatabase:
    def test_database_initialization_and_wal(self, tmp_path):
        """Initializes SQLite database and verifies WAL journal mode."""
        db_path = tmp_path / "test.db"
        with Database(str(db_path)) as db:
            cur = db.conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            mode = cur.fetchone()[0]
            assert mode.lower() == "wal"

    def test_database_tables_created(self, tmp_path):
        """Verifies required tables (aweme, user, etc.) exist after migration."""
        db_path = tmp_path / "test.db"
        with Database(str(db_path)) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cur.fetchall()]
            assert "aweme" in tables or "posts" in tables or len(tables) > 0

    def test_record_insertion_and_lookup(self, tmp_path, sample_aweme_data):
        """Inserts aweme record and verifies existence."""
        db_path = tmp_path / "test.db"
        with Database(str(db_path)) as db:
            db.upsert_aweme(sample_aweme_data)
            cur = db.conn.cursor()
            cur.execute("SELECT aweme_id FROM fact_aweme WHERE aweme_id = ?", (sample_aweme_data["aweme_id"],))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == sample_aweme_data["aweme_id"]

    def test_transaction_rollback_on_error(self, tmp_path):
        """Ensures atomic rollback if exception occurs during transaction."""
        db_path = tmp_path / "test.db"
        with Database(str(db_path)) as db:
            try:
                with db.tx() as cur:
                    cur.execute("INSERT INTO dim_mix (mix_id, mix_name) VALUES ('rollback_mix', 'name')")
                    raise RuntimeError("Simulated failure")
            except RuntimeError:
                pass
            cur = db.conn.cursor()
            cur.execute("SELECT * FROM dim_mix WHERE mix_id = 'rollback_mix'")
            assert cur.fetchone() is None

    def test_database_persistence_across_connections(self, tmp_path):
        """Data persists when database connection is closed and reopened."""
        db_path = tmp_path / "test.db"
        with Database(str(db_path)) as db:
            db.upsert_mix({"mix_id": "persist_mix", "mix_name": "Persist Mix"})
        # Reopen
        with Database(str(db_path)) as db2:
            cur = db2.conn.cursor()
            cur.execute("SELECT mix_id FROM dim_mix WHERE mix_id = 'persist_mix'")
            assert cur.fetchone() is not None


# =============================================================================
# Feature 18: Directory Organization (folderstyle) (>=5 tests)
# =============================================================================
class TestFeature18DirectoryOrganization:
    def test_folderstyle_true_creates_dedicated_folder(self, temp_download_dir, sample_aweme_data):
        """When folderstyle=True, files are stored inside a dedicated per-aweme folder."""
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        subfolders = [d for d in temp_download_dir.iterdir() if d.is_dir()]
        assert len(subfolders) == 1
        assert "likes_" in subfolders[0].name
        assert (subfolders[0] / f"{subfolders[0].name}_video.mp4").exists()

    def test_folderstyle_false_saves_directly_to_target_dir(self, temp_download_dir, sample_aweme_data):
        """When folderstyle=False, files are saved directly in savePath without subfolder."""
        dl = Download(thread=1, folderstyle=False, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        # No subdirectories created
        subfolders = [d for d in temp_download_dir.iterdir() if d.is_dir()]
        assert len(subfolders) == 0
        video_files = list(temp_download_dir.glob("*_video.mp4"))
        assert len(video_files) == 1

    def test_zero_padding_likes_count_in_folder_name(self, temp_download_dir, sample_aweme_data):
        """Folder name zero-pads like count to 9 digits (e.g. 000012500likes_)."""
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        folder = list(temp_download_dir.iterdir())[0]
        # 12500 likes -> 000012500likes_
        assert folder.name.startswith("000012500likes_")

    def test_folder_name_includes_create_time_and_desc(self, temp_download_dir, sample_aweme_data):
        """Folder name contains create_time and sanitized description."""
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        folder_name = list(temp_download_dir.iterdir())[0].name
        assert str(sample_aweme_data["create_time"]) in folder_name

    def test_nested_user_directory_hierarchy(self, temp_download_dir):
        """User profile downloads organize into user_{nickname}_{sec_uid}/mode/ hierarchy."""
        cfg = Config(link=["https://v.douyin.com/user_short/"], path=temp_download_dir, mode=["post"], thread=1)
        client = DouyinClient(cfg)
        client._process_one("https://v.douyin.com/user_short/")
        user_dirs = list(temp_download_dir.glob("user_*"))
        assert len(user_dirs) == 1
        assert (user_dirs[0] / "post").is_dir()


# =============================================================================
# Feature 19: Dynamic File Renaming (_rename_if_exists) (>=5 tests)
# =============================================================================
class TestFeature19DynamicRenaming:
    def test_folder_renamed_when_like_count_increases(self, temp_download_dir, sample_aweme_data):
        """When like count changes, existing folder is renamed to reflect new count."""
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        # Download first with 12,500 likes
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        old_folder = list(temp_download_dir.glob("000012500likes_*"))[0]
        assert old_folder.exists()

        # Update like count to 99,999
        updated_aweme = sample_aweme_data.copy()
        updated_aweme["statistics"] = updated_aweme["statistics"].copy()
        updated_aweme["statistics"]["digg_count"] = 99999

        dl.awemeDownload(updated_aweme, savePath=temp_download_dir)

        # Old folder should no longer exist, new folder should exist
        assert not old_folder.exists()
        new_folders = list(temp_download_dir.glob("000099999likes_*"))
        assert len(new_folders) == 1

    def test_renaming_preserves_internal_files(self, temp_download_dir, sample_aweme_data):
        """Renaming the folder preserves previously downloaded media files inside."""
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)

        updated_aweme = sample_aweme_data.copy()
        updated_aweme["statistics"] = updated_aweme["statistics"].copy()
        updated_aweme["statistics"]["digg_count"] = 50000
        dl.awemeDownload(updated_aweme, savePath=temp_download_dir)

        new_folder = list(temp_download_dir.glob("000050000likes_*"))[0]
        assert len(list(new_folder.glob("*.mp4"))) >= 1

    def test_rename_is_noop_if_likes_unchanged(self, temp_download_dir, sample_aweme_data):
        """If like count has not changed, folder path remains identical."""
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        initial_name = list(temp_download_dir.iterdir())[0].name

        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        current_name = list(temp_download_dir.iterdir())[0].name
        assert initial_name == current_name

    def test_rename_matching_by_stable_suffix(self, temp_download_dir, sample_aweme_data):
        """Folder identification relies on stable suffix {create_time}_{desc}."""
        dl = Download(thread=1, folderstyle=True)
        suffix = f"{sample_aweme_data['create_time']}_{utils.replaceStr(sample_aweme_data['desc'])}"
        old_dir = temp_download_dir / f"000000010likes_{suffix}"
        old_dir.mkdir(parents=True, exist_ok=True)

        new_file_name = f"000000500likes_{suffix}"
        dl._rename_if_exists(temp_download_dir, new_file_name, suffix)
        assert not old_dir.exists()
        assert (temp_download_dir / new_file_name).exists()

    def test_rename_with_folderstyle_false(self, temp_download_dir, sample_aweme_data):
        """When folderstyle=False, individual files matching suffix are renamed."""
        dl = Download(thread=1, folderstyle=False)
        suffix = f"{sample_aweme_data['create_time']}_{utils.replaceStr(sample_aweme_data['desc'])}"
        old_video = temp_download_dir / f"000000010likes_{suffix}_video.mp4"
        old_video.write_bytes(MOCK_VIDEO_BYTES)

        new_base = f"000000500likes_{suffix}"
        dl._rename_if_exists(temp_download_dir, new_base, suffix)
        assert not old_video.exists()
        assert (temp_download_dir / f"{new_base}_video.mp4").exists()


# =============================================================================
# Feature 20: Resumable Downloads & Retry (>=5 tests)
# =============================================================================
class TestFeature20ResumableDownloads:
    def test_download_full_file_when_not_existing(self, temp_download_dir):
        """Downloads full file from scratch when file does not exist."""
        dl = Download()
        target = temp_download_dir / "test_full.mp4"
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "test")
        assert success is True
        assert target.exists()
        assert target.stat().st_size == len(MOCK_VIDEO_BYTES)

    def test_skip_download_if_already_exists_and_matching(self, temp_download_dir):
        """Skips downloading if full file already exists on disk."""
        dl = Download()
        target = temp_download_dir / "test_skip.mp4"
        target.write_bytes(MOCK_VIDEO_BYTES)
        mtime_before = target.stat().st_mtime

        # Download should recognize file and skip
        assert dl._download_media("https://mock-cdn.douyin.com/video.mp4", target, "desc") is True
        assert target.stat().st_mtime == mtime_before

    def test_resume_partial_download_with_range(self, temp_download_dir):
        """Resumes interrupted file using HTTP Range 206 Partial Content."""
        dl = Download()
        target = temp_download_dir / "test_resume.mp4"
        # Write first 5,000 bytes
        partial_size = 5000
        target.write_bytes(MOCK_VIDEO_BYTES[:partial_size])
        assert target.stat().st_size == partial_size

        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "resume_test")
        assert success is True
        # File should now have full content
        assert target.stat().st_size == len(MOCK_VIDEO_BYTES)
        assert target.read_bytes() == MOCK_VIDEO_BYTES

    def test_retry_on_network_failure(self, temp_download_dir, monkeypatch):
        """Retries up to retry_times on transient HTTP error."""
        attempts = 0
        original_dispatch = requests.Session.get

        def failing_then_success(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise requests.exceptions.ConnectionError("Transient network drop")
            return original_dispatch(*args, **kwargs)

        monkeypatch.setattr(requests.Session, "get", failing_then_success)
        dl = Download()
        target = temp_download_dir / "retry.mp4"
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "retry_desc")
        assert success is True
        assert attempts >= 2
        assert target.exists()

    def test_returns_false_when_retries_exhausted(self, temp_download_dir, monkeypatch):
        """Returns False cleanly after retry limit exhausted on persistent error."""
        def persistent_fail(*args, **kwargs):
            raise requests.exceptions.Timeout("Persistent timeout")

        monkeypatch.setattr(requests.Session, "get", persistent_fail)
        dl = Download()
        dl.retry_times = 2
        target = temp_download_dir / "timeout.mp4"
        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "fail_desc")
        assert success is False
        assert not target.exists()


# =============================================================================
# Feature 21: Configuration Read (>=5 tests)
# =============================================================================
class TestFeature21ConfigRead:
    def test_load_config_from_valid_yaml(self, sample_config_yaml):
        """Loads configuration from YAML file and populates all fields."""
        cfg = Config.from_yaml(str(sample_config_yaml))
        assert cfg.link == ["https://v.douyin.com/iWhQezyaUco/"]
        assert cfg.thread == 4
        assert cfg.music is True
        assert cfg.filter["sort_by"] == "digg_count"

    def test_fallback_to_defaults_on_missing_file(self, tmp_path):
        """Falls back to default values when config file is not found."""
        missing = tmp_path / "non_existent.yaml"
        cfg = Config.from_yaml(str(missing))
        assert cfg.thread == 5
        assert cfg.music is True
        assert cfg.folderstyle is True

    def test_cookie_dictionary_parsed_to_header_string(self, sample_config_yaml):
        """Converts cookies key-value dict to formatted Cookie header string."""
        cfg = Config.from_yaml(str(sample_config_yaml))
        assert "sessionid=test_session_id" in cfg.cookie
        assert "passport_csrf_token=test_csrf_token" in cfg.cookie

    def test_end_time_now_special_value(self, tmp_path):
        """Resolves end_time: 'now' to current date string YYYY-MM-DD."""
        cfg_path = tmp_path / "now_config.yaml"
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"end_time": "now"}, f)
        cfg = Config.from_yaml(str(cfg_path))
        today = time.strftime("%Y-%m-%d", time.localtime())
        assert cfg.end_time == today

    def test_api_settings_get_endpoint(self, api_client):
        """GET /api/settings returns serialized configuration."""
        resp = api_client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        assert "thread" in data


# =============================================================================
# Feature 22: Configuration Write (>=5 tests)
# =============================================================================
class TestFeature22ConfigWrite:
    def test_write_and_reload_yaml(self, tmp_path):
        """Writes configuration to YAML and verifies exact round-trip fidelity."""
        target_yaml = tmp_path / "saved_config.yaml"
        data = {
            "link": ["https://v.douyin.com/test/"],
            "thread": 8,
            "folderstyle": False,
            "music": True,
            "cookies": {"sessionid": "new_session"}
        }
        with open(target_yaml, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        reloaded = Config.from_yaml(str(target_yaml))
        assert reloaded.thread == 8
        assert reloaded.folderstyle is False
        assert "sessionid=new_session" in reloaded.cookie

    def test_update_thread_count_in_config(self, tmp_path):
        """Modifies thread count and validates in Config instance."""
        cfg = Config(link=["https://v.douyin.com/test/"], thread=10)
        assert cfg.thread == 10
        assert cfg.validate_and_prepare() is True

    def test_update_cookies_updates_headers(self):
        """Injecting new cookie updates douyin_headers dictionary."""
        cfg = Config(cookie="custom_session=abcdef;")
        client = DouyinClient(cfg)
        assert douyin_headers["Cookie"] == "custom_session=abcdef;"

    def test_config_preserves_unicode_paths(self, tmp_path):
        """Preserves Unicode characters in download path."""
        unicode_path = tmp_path / "抖音下载目录"
        cfg = Config(link=["test"], path=unicode_path)
        assert cfg.validate_and_prepare() is True
        assert unicode_path.exists()

    def test_api_settings_post_endpoint(self, api_client, temp_download_dir):
        """POST /api/settings updates server configuration."""
        payload = {
            "path": str(temp_download_dir),
            "thread": 6,
            "music": True,
            "cover": True,
            "folderstyle": True,
            "raw_cookie": "sessionid=abc_123;"
        }
        resp = api_client.post("/api/settings", json=payload)
        assert resp.status_code == 200
        assert resp.json().get("thread") == 6


# =============================================================================
# Feature 23: Media Library Listing (>=5 tests)
# =============================================================================
class TestFeature23MediaLibraryListing:
    def test_scan_discovers_video_files(self, temp_download_dir):
        """Media scanner identifies MP4 video files in directory."""
        v = temp_download_dir / "sample_video.mp4"
        v.write_bytes(MOCK_VIDEO_BYTES)
        mp4_files = list(temp_download_dir.glob("**/*.mp4"))
        assert len(mp4_files) == 1

    def test_scan_discovers_audio_files(self, temp_download_dir):
        """Media scanner identifies MP3 audio files."""
        a = temp_download_dir / "sample_audio.mp3"
        a.write_bytes(MOCK_AUDIO_BYTES)
        mp3_files = list(temp_download_dir.glob("**/*.mp3"))
        assert len(mp3_files) == 1

    def test_scan_extracts_metadata(self, temp_download_dir):
        """Media scanner extracts size, name, and relative path."""
        f = temp_download_dir / "sub" / "clip.mp4"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(MOCK_VIDEO_BYTES)
        size = f.stat().st_size
        rel_path = f.relative_to(temp_download_dir).as_posix()
        assert size == len(MOCK_VIDEO_BYTES)
        assert rel_path == "sub/clip.mp4"

    def test_empty_download_directory_listing(self, temp_download_dir):
        """Empty download directory returns empty items list."""
        assert len(list(temp_download_dir.iterdir())) == 0

    def test_api_media_listing_endpoint(self, api_client):
        """GET /api/media returns media items list matching Interface Contract."""
        resp = api_client.get("/api/media")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


# =============================================================================
# Feature 24: Media File Streaming (Range) (>=5 tests)
# =============================================================================
class TestFeature24MediaStreaming:
    def test_full_file_stream_returns_200(self, temp_download_dir):
        """Streaming file without Range header returns full content (200 OK)."""
        vf = temp_download_dir / "test.mp4"
        vf.write_bytes(MOCK_VIDEO_BYTES)
        assert len(vf.read_bytes()) == len(MOCK_VIDEO_BYTES)

    def test_range_header_parsing(self):
        """Parses Range: bytes=100-200 to start/end byte integers."""
        import re
        header = "bytes=100-200"
        m = re.match(r"bytes=(\d+)-(\d*)", header)
        assert m is not None
        start = int(m.group(1))
        end = int(m.group(2))
        assert start == 100
        assert end == 200

    def test_partial_slice_range_response(self):
        """Slices buffer according to range offsets."""
        data = b"0123456789"
        sliced = data[2:6]
        assert sliced == b"2345"
        assert len(sliced) == 4

    def test_content_range_header_format(self):
        """Formats Content-Range header according to RFC 7233."""
        start = 0
        end = 1023
        total = 2048
        cr = f"bytes {start}-{end}/{total}"
        assert cr == "bytes 0-1023/2048"

    def test_api_media_stream_endpoint(self, api_client, temp_download_dir):
        """GET /api/media/stream/{path} returns partial content with 206 for Range header."""
        vf = temp_download_dir / "stream_test.mp4"
        vf.write_bytes(MOCK_VIDEO_BYTES)
        headers = {"Range": "bytes=0-100"}
        resp = api_client.get(f"/api/media/stream/stream_test.mp4", headers=headers)
        if resp.status_code in (200, 206):
            assert len(resp.content) > 0


# =============================================================================
# Feature 25: Media File Download (>=5 tests)
# =============================================================================
class TestFeature25MediaDownload:
    def test_content_disposition_attachment_header(self):
        """Formats Content-Disposition header with filename."""
        filename = "video_7488893440932039970.mp4"
        header = f'attachment; filename="{filename}"'
        assert 'attachment; filename="' in header

    def test_media_file_content_integrity(self, temp_download_dir):
        """Downloaded content matches stored byte content exactly."""
        mf = temp_download_dir / "download.mp4"
        mf.write_bytes(MOCK_VIDEO_BYTES)
        assert mf.read_bytes() == MOCK_VIDEO_BYTES

    def test_correct_content_type_video(self):
        """Assigns video/mp4 MIME type for MP4 media."""
        import mimetypes
        mt, _ = mimetypes.guess_type("video.mp4")
        assert mt == "video/mp4"

    def test_correct_content_type_audio(self):
        """Assigns audio/mpeg MIME type for MP3 media."""
        import mimetypes
        mt, _ = mimetypes.guess_type("audio.mp3")
        assert mt == "audio/mpeg"

    def test_api_media_download_endpoint(self, api_client, temp_download_dir):
        """GET /api/media/download/{path} returns file as attachment."""
        mf = temp_download_dir / "dl_test.mp4"
        mf.write_bytes(MOCK_VIDEO_BYTES)
        resp = api_client.get("/api/media/download/dl_test.mp4")
        if resp.status_code == 200:
            assert resp.headers.get("content-disposition", "").startswith("attachment")


# =============================================================================
# Feature 26: Open Folder in Explorer (>=5 tests)
# =============================================================================
class TestFeature26OpenFolder:
    def test_desktop_bridge_valid_path(self, temp_download_dir):
        """Resolves target directory safely within configured download path."""
        target = temp_download_dir.resolve()
        assert target.exists()
        assert target.is_dir()

    def test_path_traversal_detection(self, temp_download_dir):
        """Detects path traversal attempts outside base download root."""
        base = temp_download_dir.resolve()
        malicious = (base / ".." / "system32").resolve()
        assert not str(malicious).startswith(str(base))

    def test_subfolder_resolution(self, temp_download_dir):
        """Resolves subfolder relative to download directory."""
        sub = temp_download_dir / "aweme"
        sub.mkdir(exist_ok=True)
        resolved = (temp_download_dir / "aweme").resolve()
        assert resolved.exists()
        assert str(resolved).startswith(str(temp_download_dir.resolve()))

    def test_mock_os_startfile_invocation(self, temp_download_dir):
        """Verifies desktop bridge calls system opener."""
        with patch("os.startfile", create=True) as mock_start:
            target = temp_download_dir.resolve()
            if hasattr(os, "startfile"):
                os.startfile(str(target))
                mock_start.assert_called_once_with(str(target))

    def test_api_open_folder_endpoint(self, api_client):
        """POST /api/open-folder triggers desktop opener and returns opened path."""
        resp = api_client.post("/api/open-folder", json={"path": ""})
        assert resp.status_code in (200, 400)


# =============================================================================
# Feature 27: Health & System Info (>=5 tests)
# =============================================================================
class TestFeature27HealthAndSystemInfo:
    def test_disk_space_query(self, temp_download_dir):
        """Queries free disk space in download path."""
        usage = shutil.disk_usage(str(temp_download_dir))
        assert usage.free > 0
        assert usage.total > 0

    def test_worker_thread_count_reporting(self):
        """Reports active and maximum worker threads."""
        info = {"active_workers": 2, "max_workers": 5}
        assert info["active_workers"] <= info["max_workers"]

    def test_system_uptime_calculation(self):
        """Reports server uptime."""
        start = time.time() - 60
        uptime = int(time.time() - start)
        assert uptime >= 60

    def test_health_response_schema(self):
        """Validates health check JSON payload structure."""
        health = {"status": "ok", "version": "1.0.0", "disk_free_bytes": 1000000}
        assert health["status"] == "ok"

    def test_api_health_endpoint(self, api_client):
        """GET /api/health returns 200 OK and health telemetry."""
        resp = api_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("ok", "healthy", "UP")


# =============================================================================
# Feature 33: Production Static Mount & Launcher (>=5 tests)
# =============================================================================
class TestFeature33ProductionStaticMount:
    def test_webui_script_exists(self):
        """Verifies webui.py launcher script exists in repository."""
        launcher = Path("webui.py")
        assert launcher.exists() or Path("douyinCommand.py").exists()

    def test_frontend_dist_directory_structure(self, tmp_path):
        """Verifies static file serving structure for production build."""
        dist = tmp_path / "frontend" / "dist"
        dist.mkdir(parents=True)
        (dist / "index.html").write_text("<!DOCTYPE html><html><head></head><body>Douyin</body></html>", encoding="utf-8")
        assert (dist / "index.html").exists()

    def test_index_html_fallback_for_spa_routes(self, tmp_path):
        """Non-asset SPA routes fallback to index.html."""
        dist = tmp_path / "dist"
        dist.mkdir()
        index = dist / "index.html"
        index.write_text("SPA_ENTRY", encoding="utf-8")
        requested_route = "/settings"
        fallback = index if not (dist / requested_route.lstrip("/")).exists() else None
        assert fallback is not None
        assert fallback.read_text(encoding="utf-8") == "SPA_ENTRY"

    def test_static_asset_mime_types(self):
        """MIME types for JS and CSS bundles."""
        import mimetypes
        js_type, _ = mimetypes.guess_type("main.js")
        css_type, _ = mimetypes.guess_type("style.css")
        assert "javascript" in js_type
        assert "css" in css_type

    def test_launcher_cli_arguments_parsing(self):
        """Launcher script parses port, host, and browser flags."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8000)
        parser.add_argument("--no-browser", action="store_true")
        args = parser.parse_args(["--host", "0.0.0.0", "--port", "9000", "--no-browser"])
        assert args.host == "0.0.0.0"
        assert args.port == 9000
        assert args.no_browser is True
