# -*- coding: utf-8 -*-
"""
Tier 3 — Cross-Feature Pairwise Combinations Test Suite.
Verifies interactions between coupled features:
- Concurrency + Cancellation
- Incremental database updates + Dynamic like count renaming
- Range resumption + Transient retry on network drop
- Custom cookie injection + Multi-mode user scraping
- Directory folderstyle + Selective asset toggles
- Metric sorting + Work limits
- Config hot-reload + Task runner
- Multi-worker parallel downloads + Range resumption
"""

import os
import shutil
import sqlite3
import tempfile
import threading
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


class TestTier3PairwiseCombinations:
    # -------------------------------------------------------------------------
    # Pairwise 1: Concurrency + Task Cancellation
    # -------------------------------------------------------------------------
    def test_pairwise_concurrency_and_cancellation(self, temp_download_dir, sample_user_aweme_list):
        """Worker thread pool halts when cancellation event is triggered."""
        cancel_token = threading.Event()
        processed_items = []

        def worker_task(aweme):
            if cancel_token.is_set():
                return False
            time.sleep(0.01)
            processed_items.append(aweme["aweme_id"])
            # Trigger cancellation after first item
            cancel_token.set()
            return True

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker_task, item) for item in sample_user_aweme_list]
            for f in futures:
                f.result()

        # Cancellation prevented all items from executing
        assert len(processed_items) < len(sample_user_aweme_list)
        assert cancel_token.is_set()

    # -------------------------------------------------------------------------
    # Pairwise 2: Incremental DB Updates + Dynamic Like-Count Renaming
    # -------------------------------------------------------------------------
    def test_pairwise_incremental_db_and_like_renaming(self, temp_download_dir, sample_aweme_data, tmp_path):
        """Scrapes item, logs to DB; when likes increase, folder is renamed and DB is updated without duplicates."""
        db_path = tmp_path / "sync.db"
        dl = Download(thread=1, folderstyle=True, music=False, cover=False, avatar=False, resjson=False)

        # Initial download with 12,500 likes
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)
        with Database(str(db_path)) as db:
            db.upsert_aweme(sample_aweme_data)

        # Verify initial state
        old_folder = list(temp_download_dir.glob("000012500likes_*"))[0]
        assert old_folder.exists()

        # Item gets 50,000 likes on Douyin
        updated_aweme = sample_aweme_data.copy()
        updated_aweme["statistics"] = updated_aweme["statistics"].copy()
        updated_aweme["statistics"]["digg_count"] = 50000

        # Second download pass
        dl.awemeDownload(updated_aweme, savePath=temp_download_dir)
        with Database(str(db_path)) as db:
            db.upsert_aweme(updated_aweme)
            cur = db.conn.cursor()
            cur.execute("SELECT COUNT(*), statistics_json FROM fact_aweme WHERE aweme_id = ?", (sample_aweme_data["aweme_id"],))
            count, stats_json = cur.fetchone()
            import json
            stats = json.loads(stats_json)

        # Assert folder renamed on disk
        assert not old_folder.exists()
        new_folder = list(temp_download_dir.glob("000050000likes_*"))[0]
        assert new_folder.exists()

        # Assert no duplicate in database and stats updated
        assert count == 1
        assert stats["digg_count"] == 50000

    # -------------------------------------------------------------------------
    # Pairwise 3: HTTP Range Resumption + Transient Network Retry
    # -------------------------------------------------------------------------
    def test_pairwise_range_resumption_and_retry(self, temp_download_dir, monkeypatch):
        """Simulates network drop mid-stream; retry resumes using Range offset to complete file."""
        call_count = 0
        original_dispatch = requests.Session.get

        def dropping_dispatch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First attempt drops
                raise requests.exceptions.ConnectionError("Network connection reset by peer")
            # Subsequent retry succeeds with partial content if Range header passed
            return original_dispatch(*args, **kwargs)

        monkeypatch.setattr(requests.Session, "get", dropping_dispatch)
        dl = Download()
        target = temp_download_dir / "resumed_drop.mp4"

        # Pre-seed partial file of 5,000 bytes
        partial_size = 5000
        target.write_bytes(MOCK_VIDEO_BYTES[:partial_size])
        assert target.stat().st_size == partial_size

        success = dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, "resume_drop_test")
        assert success is True
        assert call_count >= 2
        # File complete and integrity matches
        assert target.stat().st_size == len(MOCK_VIDEO_BYTES)
        assert target.read_bytes() == MOCK_VIDEO_BYTES

    # -------------------------------------------------------------------------
    # Pairwise 4: Custom Cookie Injection + Multi-Mode Scraping
    # -------------------------------------------------------------------------
    def test_pairwise_custom_cookie_and_multi_mode(self, temp_download_dir):
        """Custom cookie from config is applied to multi-mode scraping."""
        custom_cookie = "sessionid=custom_user_session_abc123; passport_csrf_token=tok_456;"
        cfg = Config(
            link=["https://v.douyin.com/user_short/"],
            path=temp_download_dir,
            mode=["post", "like"],
            cookie=custom_cookie,
            thread=1
        )
        client = DouyinClient(cfg)
        assert douyin_headers.get("Cookie") == custom_cookie
        client._process_one("https://v.douyin.com/user_short/")

        user_dir = list(temp_download_dir.glob("user_*"))[0]
        assert (user_dir / "post").exists()
        assert (user_dir / "like").exists()

    # -------------------------------------------------------------------------
    # Pairwise 5: Folderstyle Toggle + Selective Asset Types
    # -------------------------------------------------------------------------
    def test_pairwise_folderstyle_false_and_video_cover_only(self, temp_download_dir, sample_aweme_data):
        """When folderstyle=False and only video+cover selected, flat directory contains only those files."""
        dl = Download(thread=1, folderstyle=False, music=False, cover=True, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=temp_download_dir)

        # No subdirectories created
        assert len([d for d in temp_download_dir.iterdir() if d.is_dir()]) == 0
        all_files = [f.name for f in temp_download_dir.iterdir()]
        assert any(f.endswith("_video.mp4") for f in all_files)
        assert any(f.endswith("_cover.jpeg") for f in all_files)
        assert not any(f.endswith("_music.mp3") for f in all_files)
        assert not any(f.endswith("_result.json") for f in all_files)

    # -------------------------------------------------------------------------
    # Pairwise 6: Metric Sorting + Work Limits
    # -------------------------------------------------------------------------
    def test_pairwise_sorting_and_limits(self, sample_user_aweme_list):
        """Combines play_count sorting with limit=2 to select top 2 most-played works."""
        cfg = Config(filter={"sort_by": "play_count", "reverse": True, "limit": 2})
        client = DouyinClient(cfg)
        result = client._apply_filter_and_sort(sample_user_aweme_list.copy())

        assert len(result) == 2
        # Highest play counts in sample list are 1,200,000 and 500,000
        assert result[0]["statistics"]["play_count"] == 1200000
        assert result[1]["statistics"]["play_count"] == 500000

    # -------------------------------------------------------------------------
    # Pairwise 7: Config YAML Hot-Reload + Downloader Execution
    # -------------------------------------------------------------------------
    def test_pairwise_config_hot_reload_and_execution(self, tmp_path, sample_aweme_data):
        """Config file updated on disk is reloaded and dynamically alters download target."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        cfg_file = tmp_path / "config.yaml"

        # Config with dir1
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump({"path": str(dir1), "thread": 2, "folderstyle": True}, f)
        cfg = Config.from_yaml(str(cfg_file))
        assert cfg.path == dir1

        dl = Download(thread=cfg.thread, folderstyle=cfg.folderstyle, music=False, cover=False, avatar=False, resjson=False)
        dl.awemeDownload(sample_aweme_data, savePath=cfg.path)
        assert len(list(dir1.glob("*likes_*"))) == 1

        # Hot-reload with dir2
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump({"path": str(dir2), "thread": 4, "folderstyle": True}, f)
        cfg_reloaded = Config.from_yaml(str(cfg_file))
        assert cfg_reloaded.path == dir2

        dl2 = Download(thread=cfg_reloaded.thread, folderstyle=cfg_reloaded.folderstyle, music=False, cover=False, avatar=False, resjson=False)
        dl2.awemeDownload(sample_aweme_data, savePath=cfg_reloaded.path)
        assert len(list(dir2.glob("*likes_*"))) == 1

    # -------------------------------------------------------------------------
    # Pairwise 8: Multi-Worker Concurrency + Range Resumption
    # -------------------------------------------------------------------------
    def test_pairwise_multi_worker_range_resumption(self, temp_download_dir):
        """Multiple threads concurrently resume partial files without collisions."""
        dl = Download(thread=4)
        targets = []
        for i in range(4):
            t = temp_download_dir / f"concurrent_part_{i}.mp4"
            # Pre-seed first 2,000 bytes
            t.write_bytes(MOCK_VIDEO_BYTES[:2000])
            targets.append(t)

        from concurrent.futures import ThreadPoolExecutor
        def resume_file(target):
            return dl.download_with_resume("https://mock-cdn.douyin.com/video.mp4", target, f"task_{target.name}")

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(resume_file, targets))

        assert all(results)
        for t in targets:
            assert t.stat().st_size == len(MOCK_VIDEO_BYTES)
            assert t.read_bytes() == MOCK_VIDEO_BYTES
