# -*- coding: utf-8 -*-
"""
Tier 4 — Real-World Application Scenarios Test Suite.
Verifies >=5 complete end-to-end user workflows:
1. Standard Single Video Full Lifecycle (Parse -> Preview -> Config -> Download -> Storage -> Media Library)
2. Batch User Profile Multi-Mode Scraping Lifecycle (Parse -> Preview -> Modes -> Hierarchy -> DB Dedup)
3. Interrupted Media Download & Range Resumption Lifecycle (Abort -> Partial -> Range Resume -> Integrity)
4. User Collection / Mix Series Complete Download Lifecycle (Parse -> Detail -> Episode Batch -> Storage)
5. Full Desktop App Lifecycle (Health -> Settings Sync -> Task Queue -> Telemetry -> Media -> Explorer Bridge)
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


class TestTier4RealWorldScenarios:
    # -------------------------------------------------------------------------
    # Scenario 1: Standard Single Video Full Lifecycle
    # -------------------------------------------------------------------------
    def test_scenario1_single_video_full_lifecycle(self, temp_download_dir, tmp_path):
        """End-to-end single video workflow: link input -> resolve -> preview -> download -> disk verification -> db record."""
        raw_share_text = "看这个神仙视频！https://v.douyin.com/iWhQezyaUco/ 复制此链接打开抖音"
        db_path = tmp_path / "app.db"

        # Step 1: Link Resolution
        api = DouyinApi(database_path=str(db_path))
        extracted_url = api.getShareLink(raw_share_text)
        assert extracted_url.startswith("https://v.douyin.com/")

        key_type, key = api.getKey(extracted_url)
        assert key_type == "aweme"
        assert key == "7488893440932039970"

        # Step 2: Content Preview Extraction
        preview_data = api.getAwemeInfoApi(key)
        assert preview_data is not None
        assert preview_data["desc"] == "Test Douyin Video Description"
        assert preview_data["author"]["nickname"] == "TestAuthor"
        assert preview_data["statistics"]["digg_count"] == 12500

        # Step 3: Configure and Execute Download
        dl = Download(thread=2, folderstyle=True, music=True, cover=True, avatar=True, resjson=True)
        success = dl.awemeDownload(preview_data, savePath=temp_download_dir)
        assert success is True

        # Step 4: Storage Verification
        folders = list(temp_download_dir.glob("000012500likes_*"))
        assert len(folders) == 1
        work_dir = folders[0]
        files = [f.name for f in work_dir.iterdir()]

        assert any(f.endswith("_video.mp4") for f in files)
        assert any("_music_" in f and f.endswith(".mp3") for f in files)
        assert any(f.endswith("_cover.jpeg") for f in files)
        assert any(f.endswith("_avatar.jpeg") for f in files)
        assert any(f.endswith("_result.json") for f in files)

        # Step 5: Database Index Verification
        with Database(str(db_path)) as db:
            cur = db.conn.cursor()
            cur.execute("SELECT aweme_id FROM fact_aweme WHERE aweme_id = ?", (key,))
            assert cur.fetchone()[0] == key

    # -------------------------------------------------------------------------
    # Scenario 2: Batch User Profile Multi-Mode Scraping Lifecycle
    # -------------------------------------------------------------------------
    def test_scenario2_user_profile_scraping_lifecycle(self, temp_download_dir, tmp_path):
        """End-to-end user profile workflow: URL -> parse -> preview -> post & like download -> hierarchy -> db."""
        user_share = "作者主页：https://v.douyin.com/user_short/ 关注作者获取更多更新"
        db_path = tmp_path / "user_app.db"

        # Step 1: Resolve user ID
        api = DouyinApi(database_path=str(db_path))
        url = api.getShareLink(user_share)
        key_type, sec_uid = api.getKey(url)
        assert key_type == "user"
        assert sec_uid == "MS4wLjABAAAA_test_author"

        # Step 2: Preview user information
        peek = api.getUserInfoApi(sec_uid, mode="post", count=1, number=1)
        assert len(peek) > 0
        nickname = peek[0]["author"]["nickname"]
        assert nickname == "TestAuthor"

        # Step 3: Configure Multi-Mode Download Task
        cfg = Config(
            link=[user_share],
            path=temp_download_dir,
            mode=["post", "like"],
            thread=2,
            music=False,
            cover=False,
            avatar=False,
            json=True,
            database=True
        )
        client = DouyinClient(cfg)
        client.process_all()

        # Step 4: Verify Directory Structure
        user_root = list(temp_download_dir.glob("user_*"))[0]
        assert (user_root / "post").is_dir()
        assert (user_root / "like").is_dir()

        # Step 5: Verify Files in Mode Subfolders
        post_items = list((user_root / "post").glob("*likes_*"))
        assert len(post_items) > 0

    # -------------------------------------------------------------------------
    # Scenario 3: Interrupted Media Download & Range Resumption Lifecycle
    # -------------------------------------------------------------------------
    def test_scenario3_interrupted_download_resumption_lifecycle(self, temp_download_dir):
        """Simulates abrupt network drop during download; subsequent resumption restores full file."""
        target_video = temp_download_dir / "interrupted_stream.mp4"
        dl = Download()

        # Phase 1: Download starts, but connection drops after 4,096 bytes
        partial_bytes = MOCK_VIDEO_BYTES[:4096]
        target_video.write_bytes(partial_bytes)
        assert target_video.stat().st_size == 4096

        # Phase 2: User / system triggers resume
        # Client sends Range: bytes=4096- header to mock server
        resumed = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target_video, "resume_lifecycle")
        assert resumed is True

        # Phase 3: Integrity verification
        assert target_video.exists()
        assert target_video.stat().st_size == len(MOCK_VIDEO_BYTES)
        assert target_video.read_bytes() == MOCK_VIDEO_BYTES

    # -------------------------------------------------------------------------
    # Scenario 4: User Collection / Mix Series Complete Download Lifecycle
    # -------------------------------------------------------------------------
    def test_scenario4_collection_mix_download_lifecycle(self, temp_download_dir):
        """End-to-end collection workflow: collection link -> resolve mix -> scrape all episodes -> hierarchy."""
        mix_share = "合集系列：https://v.douyin.com/mix_short/ 连载中"

        # Step 1: URL Resolution
        api = DouyinApi()
        url = api.getShareLink(mix_share)
        key_type, mix_id = api.getKey(url)
        assert key_type == "mix"
        assert mix_id == "7488893440932039972"

        # Step 2: Download Mix Collection via Client
        cfg = Config(
            link=[mix_share],
            path=temp_download_dir,
            thread=2,
            music=False,
            cover=False,
            avatar=False,
            json=True
        )
        client = DouyinClient(cfg)
        client.process_all()

        # Step 3: Verify Mix Directory Hierarchy
        mix_folders = list(temp_download_dir.glob("*7488893440932039972*"))
        assert len(mix_folders) == 1
        mix_dir = mix_folders[0]

        # Verify episodes downloaded inside mix directory
        episodes = list(mix_dir.glob("*likes_*"))
        assert len(episodes) > 0

    # -------------------------------------------------------------------------
    # Scenario 5: Full Desktop App Lifecycle (Health -> Settings -> Task -> Telemetry -> Explorer)
    # -------------------------------------------------------------------------
    def test_scenario5_full_desktop_app_lifecycle(self, api_client, temp_download_dir):
        """End-to-end desktop app flow through Web API endpoints: health -> settings -> download -> tasks -> media -> open folder."""
        # 1. Health check
        health = api_client.get("/api/health")
        assert health.status_code == 200

        # 2. Get and update settings
        settings_get = api_client.get("/api/settings")
        assert settings_get.status_code == 200

        settings_post = api_client.post("/api/settings", json={
            "path": str(temp_download_dir),
            "thread": 4,
            "music": True,
            "cover": True,
            "folderstyle": True,
            "raw_cookie": "sessionid=lifecycle_token_xyz;"
        })
        assert settings_post.status_code == 200

        # 3. Create download task
        download_req = api_client.post("/api/download", json={
            "url": "https://v.douyin.com/iWhQezyaUco/",
            "key_type": "aweme",
            "key": "7488893440932039970",
            "modes": ["post"],
            "asset_types": {"video": True, "music": True, "cover": True, "avatar": False, "json": True},
            "thread_count": 4,
            "download_path": str(temp_download_dir)
        })
        assert download_req.status_code == 202
        task_id = download_req.json()["task_id"]

        # 4. Monitor task status
        task_status = api_client.get(f"/api/tasks/{task_id}")
        assert task_status.status_code == 200
        assert task_status.json()["task_id"] == task_id

        # 5. Query media library
        media_list = api_client.get("/api/media")
        assert media_list.status_code == 200

        # 6. Trigger open folder desktop bridge
        open_folder = api_client.post("/api/open-folder", json={"path": ""})
        assert open_folder.status_code == 200
