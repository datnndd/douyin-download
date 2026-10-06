# -*- coding: utf-8 -*-
"""
tests/test_m1_core.py
Comprehensive unit tests for Milestone 1: Backend Engine & Task Concurrency.
Tests verify:
1. Config loading, cookie parsing, YAML preservation, ConfigManager singleton.
2. Pydantic v2 schemas validation, coercions, and defaults.
3. DouyinService link extraction, canonical formatting, preview fetching, domain errors, and concurrency.
4. TaskManager lifecycle state machine, worker thread visualizer, SSE pub/sub queues, throttling, and cancellation.
5. Download engine progress callbacks and cancellation tokens in src/douyin/download.py.
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.douyin.download import Download
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
    ContentType,
    DownloadProgressEvent,
    DownloadRequest,
    FilterOptions,
    HealthResponse,
    KeyType,
    MediaItem,
    MediaListResponse,
    OpenFolderRequest,
    OpenFolderResponse,
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
# 1. Config & Cookie Utilities Tests
# ==============================================================================


class TestConfigAndCookies:
    """Tests for cookie parsing, formatting, YAML loading/saving, and ConfigManager."""

    def test_parse_raw_cookie_basic(self):
        raw = "msToken=abc123; ttwid=xyz789; sid_guard=guard_val"
        cookies = parse_raw_cookie(raw)
        assert cookies["msToken"] == "abc123"
        assert cookies["ttwid"] == "xyz789"
        assert cookies["sid_guard"] == "guard_val"

    def test_parse_raw_cookie_edge_cases(self):
        # Base64 padding '==', extra whitespace, trailing semicolon
        raw = " msToken=M2z9tlZ== ;  ttwid=1%7Ctoken ; empty_val= ; "
        cookies = parse_raw_cookie(raw)
        assert cookies["msToken"] == "M2z9tlZ=="
        assert cookies["ttwid"] == "1%7Ctoken"
        assert cookies["empty_val"] == ""

        # None or empty string
        assert parse_raw_cookie("") == {}
        assert parse_raw_cookie(None) == {}

    def test_format_cookie_dict(self):
        cookies = {"msToken": "abc==", "ttwid": "123"}
        formatted = format_cookie_dict(cookies)
        assert "msToken=abc==" in formatted
        assert "ttwid=123" in formatted
        assert format_cookie_dict({}) == ""
        assert format_cookie_dict(None) == ""

    def test_load_config_file_defaults_when_missing(self, tmp_path):
        missing = tmp_path / "non_existent.yaml"
        settings = load_config_file(missing)
        assert isinstance(settings, SettingsModel)
        assert settings.path == "./Downloaded/"
        assert settings.thread == 5
        assert settings.music is True

    def test_load_config_file_with_valid_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        sample_yaml = {
            "path": "./CustomDownloads/",
            "thread": 8,
            "music": False,
            "cover": True,
            "cookies": {
                "msToken": "test_token_123",
                "sid_guard": "guard_456",
            },
            "filter": {
                "sort_by": "digg_count",
                "reverse": False,
                "limit": 10,
            },
        }
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(sample_yaml, f)

        settings = load_config_file(cfg_file)
        assert settings.path == "./CustomDownloads/"
        assert settings.thread == 8
        assert settings.music is False
        assert settings.cover is True
        assert settings.cookies["msToken"] == "test_token_123"
        assert settings.filter.sort_by == "digg_count"
        assert settings.filter.limit == 10

    def test_save_config_file_preserves_comments(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        original_content = (
            "# Main Download Settings\n"
            "path: ./Downloaded/  # Root directory\n"
            "thread: 5  # Concurrency count\n"
            "music: True  # Download audio\n"
            "cookies:\n"
            "  msToken: test_old_token\n"
            "# End of config\n"
        )
        cfg_file.write_text(original_content, encoding="utf-8")

        settings = load_config_file(cfg_file)
        settings.thread = 12
        settings.music = False
        settings.cookies["msToken"] = "new_token_xyz=="

        saved = save_config_file(settings, cfg_file)
        assert saved is True

        content = cfg_file.read_text(encoding="utf-8")
        # Check comments are preserved
        assert "# Main Download Settings" in content
        assert "# Concurrency count" in content
        assert "# End of config" in content
        # Check values were updated
        assert "thread: 12" in content
        assert "music: False" in content

    def test_config_manager_singleton_and_header_update(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        sample_yaml = {
            "path": "./TestDownloads/",
            "thread": 4,
            "cookies": {"msToken": "singleton_test_token"},
        }
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(sample_yaml, f)

        # Reset singleton for testing
        ConfigManager._instance = None
        manager = ConfigManager.get_instance(cfg_file)
        assert manager.get_settings().thread == 4
        assert manager.get_settings().cookies["msToken"] == "singleton_test_token"
        assert "msToken=singleton_test_token" in manager.get_cookie_header()

        # Update settings
        new_settings = manager.get_settings()
        new_settings.thread = 16
        new_settings.raw_cookie = "msToken=updated_token; ttwid=ttwid_val"
        manager.update_settings(new_settings)

        assert manager.get_settings().thread == 16
        assert manager.get_settings().cookies["msToken"] == "updated_token"
        assert manager.get_settings().cookies["ttwid"] == "ttwid_val"

        # Resolve path
        download_dir = manager.resolve_download_path()
        assert download_dir.exists()


# ==============================================================================
# 2. Pydantic Schemas & Data Coercion Tests
# ==============================================================================


class TestPydanticSchemas:
    """Tests for Pydantic v2 model validation, coercions, and defaults."""

    def test_statistics_model_coercions(self):
        # Coerce empty strings and None to 0
        stats = StatisticsModel(
            digg_count="",
            comment_count=None,
            share_count="125",
            play_count="50000",
            collect_count="",
        )
        assert stats.digg_count == 0
        assert stats.comment_count == 0
        assert stats.share_count == 125
        assert stats.play_count == 50000
        assert stats.collect_count == 0

    def test_author_preview_nested_dict_extraction(self):
        # Douyin API returns avatar as dict with url_list
        author = AuthorPreview(
            nickname="Test Creator",
            avatar_thumb={"url_list": ["https://cdn.douyin.com/avatar_thumb.jpg"]},
            avatar={"url_list": ["https://cdn.douyin.com/avatar_hd.jpg"]},
            sec_uid="MS4wLjABAAAA_test",
            follower_count="",
            total_favorited=None,
        )
        assert author.avatar_thumb == "https://cdn.douyin.com/avatar_thumb.jpg"
        assert author.avatar == "https://cdn.douyin.com/avatar_hd.jpg"
        assert author.follower_count == 0
        assert author.total_favorited == 0

    def test_preview_metadata_cover_extraction(self):
        preview = PreviewMetadata(
            title="Video Title",
            desc="Description",
            cover_url={"url_list": ["https://cdn.douyin.com/cover.jpg"]},
            statistics=StatisticsModel(digg_count=500),
            duration=30,
        )
        assert preview.cover_url == "https://cdn.douyin.com/cover.jpg"
        assert preview.duration == 30
        assert preview.statistics.digg_count == 500

    def test_download_request_defaults(self):
        req = DownloadRequest(url="https://v.douyin.com/abc/", key="12345")
        assert req.key_type == "aweme"
        assert req.thread_count == 5
        assert req.asset_types.video is True
        assert req.asset_types.avatar is False
        assert req.folderstyle is True
        assert req.filter.sort_by == "create_time"
        assert req.filter.reverse is True

    def test_task_status_enum_values(self):
        assert TaskStatus.PENDING == "PENDING"
        assert TaskStatus.PARSING == "PARSING"
        assert TaskStatus.DOWNLOADING == "DOWNLOADING"
        assert TaskStatus.COMPLETED == "COMPLETED"
        assert TaskStatus.CANCELLED == "CANCELLED"
        assert TaskStatus.FAILED == "FAILED"
        assert TaskStatus.PAUSED == "PAUSED"

    def test_task_response_and_detail_response(self):
        task_resp = TaskResponse(task_id="test-uuid-123")
        assert task_resp.status == TaskStatus.PENDING
        assert task_resp.task_id == "test-uuid-123"

        now = datetime.now(timezone.utc)
        detail = TaskDetailResponse(
            task_id="test-uuid-123",
            status=TaskStatus.DOWNLOADING,
            progress_pct=50.5,
            downloaded_bytes=1000,
            total_bytes=2000,
            speed_bps=500.0,
            created_at=now,
        )
        assert detail.progress_pct == 50.5
        assert detail.total_bytes == 2000

    def test_download_progress_event(self):
        event = DownloadProgressEvent(
            task_id="task-1",
            status=TaskStatus.DOWNLOADING,
            progress_pct=25.0,
            speed_bps=1024.0,
            downloaded_bytes=512,
            total_bytes=2048,
        )
        assert event.event_type == "task_progress"
        assert event.progress_pct == 25.0


# ==============================================================================
# 3. DouyinService Link Resolution & Preview Tests
# ==============================================================================


class TestDouyinService:
    """Tests for URL extraction, redirection resolution, 5 key types, and error handling."""

    def test_extract_share_url(self):
        service = DouyinService()
        raw_clipboard = "7.35 复制打开抖音，看看【小明同学的作品】 https://v.douyin.com/iWhQezyaUco/ 11/12 l@w.pm :0pm"
        extracted = service.extract_share_url(raw_clipboard)
        assert extracted == "https://v.douyin.com/iWhQezyaUco/"

        plain_url = "https://www.douyin.com/video/7488893440932039970"
        assert service.extract_share_url(plain_url) == plain_url

        no_url = "Just plain text with no link"
        assert service.extract_share_url(no_url) is None

    def test_extract_key_and_type_aweme(self):
        service = DouyinService()
        session = MagicMock()

        # Video
        kt, k = service.extract_key_and_type(
            "https://www.douyin.com/video/7488893440932039970", session
        )
        assert kt == "aweme"
        assert k == "7488893440932039970"

        # Note
        kt, k = service.extract_key_and_type(
            "https://www.douyin.com/note/7488893440932039971", session
        )
        assert kt == "aweme"
        assert k == "7488893440932039971"

    def test_extract_key_and_type_user(self):
        service = DouyinService()
        session = MagicMock()

        kt, k = service.extract_key_and_type(
            "https://www.douyin.com/user/MS4wLjABAAAA_test_author", session
        )
        assert kt == "user"
        assert k == "MS4wLjABAAAA_test_author"

    def test_extract_key_and_type_mix(self):
        service = DouyinService()
        session = MagicMock()

        kt, k = service.extract_key_and_type(
            "https://www.douyin.com/collection/7488893440932039972", session
        )
        assert kt == "mix"
        assert k == "7488893440932039972"

        kt, k = service.extract_key_and_type(
            "https://www.douyin.com/mix/detail/7488893440932039972", session
        )
        assert kt == "mix"
        assert k == "7488893440932039972"

    def test_extract_key_and_type_music(self):
        service = DouyinService()
        session = MagicMock()

        kt, k = service.extract_key_and_type(
            "https://www.douyin.com/music/7488893440932039973", session
        )
        assert kt == "music"
        assert k == "7488893440932039973"

    def test_extract_key_and_type_live(self):
        service = DouyinService()
        session = MagicMock()

        kt, k = service.extract_key_and_type(
            "https://live.douyin.com/7488893440932039974", session
        )
        assert kt == "live"
        assert k == "7488893440932039974"

    def test_build_canonical_url(self):
        assert (
            DouyinService.build_canonical_url("aweme", "123")
            == "https://www.douyin.com/video/123"
        )
        assert (
            DouyinService.build_canonical_url("user", "sec123")
            == "https://www.douyin.com/user/sec123"
        )
        assert (
            DouyinService.build_canonical_url("mix", "mix123")
            == "https://www.douyin.com/collection/mix123"
        )
        assert (
            DouyinService.build_canonical_url("music", "m123")
            == "https://www.douyin.com/music/m123"
        )
        assert (
            DouyinService.build_canonical_url("live", "live123")
            == "https://live.douyin.com/live123"
        )

    def test_invalid_url_raises_error(self):
        service = DouyinService()
        with pytest.raises(DouyinInvalidUrlError) as exc_info:
            service.sync_parse_url("no url here")
        assert exc_info.value.status_code == 400

        with pytest.raises(DouyinInvalidUrlError):
            service.sync_parse_url("")

    def test_async_parse_url_aweme(self):
        async def _run():
            service = DouyinService()
            mock_aweme = {
                "aweme_id": "7488893440932039970",
                "desc": "Test Aweme Description",
                "awemeType": 0,
                "author": {
                    "nickname": "Author Nickname",
                    "sec_uid": "MS4wLjABAAAA_sec",
                    "avatar_thumb": {"url_list": ["https://cdn.douyin.com/thumb.jpg"]},
                },
                "video": {
                    "origin_cover": {"url_list": ["https://cdn.douyin.com/cover.jpg"]},
                    "duration": 45000,
                },
                "statistics": {
                    "digg_count": 12000,
                    "comment_count": 800,
                    "play_count": 100000,
                },
            }

            # Mock the underlying DouyinApi inside thread-local
            with patch.object(service, "_get_api") as mock_get_api:
                mock_api = MagicMock()
                mock_api.getAwemeInfoApi.return_value = mock_aweme
                mock_get_api.return_value = mock_api

                resp = await service.parse_url(
                    "https://www.douyin.com/video/7488893440932039970"
                )
                assert resp.success is True
                assert resp.key_type == "aweme"
                assert resp.key == "7488893440932039970"
                assert resp.content_type == "video"
                assert resp.preview.title == "Test Aweme Description"
                assert resp.preview.author.nickname == "Author Nickname"
                assert resp.preview.cover_url == "https://cdn.douyin.com/cover.jpg"
                assert resp.preview.statistics.digg_count == 12000
                assert resp.preview.duration == 45

        asyncio.run(_run())

    def test_concurrent_parsing_thread_safety(self):
        async def _run():
            service = DouyinService()
            mock_aweme = {
                "aweme_id": "7488893440932039970",
                "desc": "Concurrent Aweme",
                "awemeType": 0,
                "author": {"nickname": "Creator", "sec_uid": "sec_1"},
                "video": {"cover": {"url_list": ["https://cdn.douyin.com/c.jpg"]}},
                "statistics": {"digg_count": 10},
            }

            with patch.object(service, "_get_api") as mock_get_api:
                mock_api = MagicMock()
                mock_api.getAwemeInfoApi.return_value = mock_aweme
                mock_get_api.return_value = mock_api

                # Run 5 concurrent requests
                urls = [
                    f"https://www.douyin.com/video/748889344093203997{i}"
                    for i in range(5)
                ]
                tasks = [service.parse_url(u) for u in urls]
                results = await asyncio.gather(*tasks)

                assert len(results) == 5
                for r in results:
                    assert r.success is True
                    assert r.key_type == "aweme"

        asyncio.run(_run())


# ==============================================================================
# 4. TaskManager Concurrency, Lifecycle & Telemetry Tests
# ==============================================================================


class TestTaskManager:
    """Tests for TaskManager state machine, visualizer slots, SSE queues, throttling, and cancellation."""

    def test_submit_and_get_task(self):
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
            thread_count=3,
        )

        with patch.object(manager, "_run_task_pipeline"):
            resp = manager.submit_task(req)
            assert resp.status == TaskStatus.PENDING
            assert resp.task_id is not None

            # Check task inspection
            detail = manager.get_task(resp.task_id)
            assert detail is not None
            assert detail.task_id == resp.task_id
            assert len(detail.threads) == 3

    def test_cancel_task(self):
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
        )

        with patch.object(manager, "_run_task_pipeline"):
            resp = manager.submit_task(req)
            cancelled = manager.cancel_task(resp.task_id)
            assert cancelled is True

            detail = manager.get_task(resp.task_id)
            assert detail.status == TaskStatus.CANCELLED

            # Cancelling an already cancelled task returns False
            assert manager.cancel_task(resp.task_id) is False

    def test_pause_and_resume_task(self):
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
        )

        with patch.object(manager, "_run_task_pipeline"):
            resp = manager.submit_task(req)
            record = manager._tasks[resp.task_id]
            record.status = TaskStatus.DOWNLOADING

            # Pause
            assert manager.pause_task(resp.task_id) is True
            assert manager.get_task(resp.task_id).status == TaskStatus.PAUSED
            assert not record.pause_event.is_set()

            # Resume
            assert manager.resume_task(resp.task_id) is True
            assert manager.get_task(resp.task_id).status == TaskStatus.DOWNLOADING
            assert record.pause_event.is_set()

    def test_sse_subscription_and_broadcast(self):
        async def _run():
            manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
            loop = asyncio.get_running_loop()
            manager.set_event_loop(loop)

            req = DownloadRequest(url="https://www.douyin.com/video/123", key="123")
            with patch.object(manager, "_run_task_pipeline"):
                resp = manager.submit_task(req)
                task_id = resp.task_id

                # Subscribe to this task
                queue = manager.subscribe(task_id=task_id)

                # Broadcast a test event
                record = manager._tasks[task_id]
                record.downloaded_bytes = 1024
                record.total_bytes = 2048
                record.status = TaskStatus.DOWNLOADING

                manager._broadcast_event(
                    record.to_progress_event(), task_id=task_id, force=True
                )

                # Wait briefly for call_soon_threadsafe
                await asyncio.sleep(0.05)

                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                assert isinstance(event, DownloadProgressEvent)
                assert event.task_id == task_id
                assert event.downloaded_bytes == 1024

                # Unsubscribe
                manager.unsubscribe(queue, task_id=task_id)

        asyncio.run(_run())

    def test_progress_hook_throttling_and_force_emit(self):
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/123", key="123", thread_count=2
        )
        record = TaskRecord("task-throttle", req)
        record.total_bytes = 10000

        emitted_events = []
        with patch.object(
            manager,
            "_broadcast_event",
            side_effect=lambda evt, task_id, force=False: emitted_events.append(evt),
        ):
            hook = manager.create_progress_hook(record)

            # 1. Fire 30 rapid chunk events in < 5ms
            for _ in range(30):
                hook(
                    {
                        "event": "chunk",
                        "worker_id": 1,
                        "filename": "chunk_file.mp4",
                        "chunk_bytes": 100,
                        "downloaded_bytes": 100,
                        "total_bytes": 1000,
                    }
                )

            # Due to 250ms throttle, only 1 or 2 chunk events should have been emitted
            assert len(emitted_events) <= 2
            assert record.downloaded_bytes == 3000

            # 2. Fire file_complete event -> must bypass throttle and force-emit
            hook(
                {
                    "event": "file_complete",
                    "worker_id": 1,
                    "filename": "chunk_file.mp4",
                    "chunk_bytes": 0,
                    "downloaded_bytes": 1000,
                    "total_bytes": 1000,
                }
            )
            assert emitted_events[-1].threads[0].status == "COMPLETED"
            assert emitted_events[-1].threads[0].pct == 100.0


# ==============================================================================
# 5. Download Engine Hooks & Cancellation Tests
# ==============================================================================


class TestDownloadEngineHooks:
    """Tests for Download class backward-compatibility, callbacks, and cancel tokens."""

    def test_download_init_backward_compatibility(self):
        # Default initialization without new arguments works seamlessly
        d = Download(thread=3, music=True, cover=False)
        assert d.thread == 3
        assert d.music is True
        assert d.cover is False
        assert d.progress_callback is None
        assert d.cancel_event is None

    def test_download_media_already_exists_triggers_callback(self, tmp_path):
        existing_file = tmp_path / "test_video.mp4"
        existing_file.write_bytes(b"EXISTING_VIDEO_BYTES")

        events = []

        def callback(evt):
            events.append(evt)

        d = Download(progress_callback=callback)
        result = d._download_media(
            "https://mock-url.com/v.mp4", existing_file, "Existing File", worker_id=2
        )

        assert result is True
        assert len(events) == 1
        assert events[0]["event"] == "file_complete"
        assert events[0]["worker_id"] == 2
        assert events[0]["downloaded_bytes"] == len(b"EXISTING_VIDEO_BYTES")

    def test_cancellation_token_aborts_download(self, tmp_path):
        cancel_token = threading.Event()
        cancel_token.set()  # Signal cancellation immediately

        d = Download(cancel_event=cancel_token)
        target_file = tmp_path / "cancelled_video.mp4"

        result = d._download_media(
            "https://mock-url.com/v.mp4", target_file, "Cancelled File"
        )
        assert result is False
        assert not target_file.exists()

    def test_cancellation_during_aweme_download(self, tmp_path):
        cancel_token = threading.Event()
        cancel_token.set()

        d = Download(cancel_event=cancel_token)
        sample_aweme = {
            "aweme_id": "7488893440932039970",
            "desc": "Test Aweme",
            "create_time": 1728100000,
            "statistics": {"digg_count": 50},
        }
        res = d.awemeDownload(sample_aweme, tmp_path)
        assert res is False

    def test_resume_headers_generated_correctly(self, tmp_path):
        target_file = tmp_path / "partial_video.mp4"
        target_file.write_bytes(b"EXISTING_100_BYTES_" * 5)
        expected_size = target_file.stat().st_size

        d = Download()
        # Verify download_with_resume logic with mocked session
        with patch.object(d, "_get_session") as mock_get_sess:
            mock_sess = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 206
            mock_resp.headers = {"content-length": "500"}
            mock_resp.iter_content.return_value = [b"NEW_CHUNK_DATA"]
            mock_sess.get.return_value = mock_resp
            mock_get_sess.return_value = mock_sess

            res = d.download_with_resume(
                "https://mock-url.com/v.mp4", target_file, "Partial File"
            )
            assert res is True
            # Verify Range header was passed
            call_kwargs = mock_sess.get.call_args[1]
            assert "Range" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Range"] == f"bytes={expected_size}-"


# ==============================================================================
# 6. Additional Previews, Schemas & Task Pipeline End-to-End Tests
# ==============================================================================


class TestPreviewsAndEndToEnd:
    """Additional coverage for user/mix/music/live previews and task execution pipeline."""

    def test_user_preview_extraction(self):
        service = DouyinService()
        mock_posts = [
            {
                "aweme_id": "1",
                "author": {
                    "nickname": "StarCreator",
                    "avatar_thumb": {
                        "url_list": ["https://cdn.douyin.com/u_avatar.jpg"]
                    },
                    "sec_uid": "MS4wLjABAAAA_star",
                    "signature": "Welcome to my profile",
                    "follower_count": 500000,
                    "total_favorited": 2000000,
                    "following_count": 100,
                    "aweme_count": 88,
                },
            }
        ]
        with patch.object(service, "_get_api") as mock_get_api:
            mock_api = MagicMock()
            mock_api.getUserInfoApi.return_value = mock_posts
            mock_get_api.return_value = mock_api

            content_type, preview = service.fetch_preview_metadata(
                mock_api, "user", "MS4wLjABAAAA_star"
            )
            assert content_type == "user"
            assert preview.title == "StarCreator 的个人主页"
            assert preview.author.nickname == "StarCreator"
            assert preview.statistics.follower_count == 500000
            assert preview.work_count == 88

    def test_mix_preview_extraction(self):
        service = DouyinService()
        mock_mix = [
            {
                "aweme_id": "ep1",
                "mix_info": {
                    "mix_name": "Tutorial Series",
                    "cover_url": {"url_list": ["https://cdn.douyin.com/mix_cover.jpg"]},
                    "statis": {"updated_to_episode": 10},
                },
                "author": {
                    "nickname": "Teacher",
                    "avatar_thumb": {
                        "url_list": ["https://cdn.douyin.com/teacher.jpg"]
                    },
                    "sec_uid": "teacher_uid",
                },
            }
        ]
        with patch.object(service, "_get_api") as mock_get_api:
            mock_api = MagicMock()
            mock_api.getMixInfoApi.return_value = mock_mix
            mock_get_api.return_value = mock_api

            content_type, preview = service.fetch_preview_metadata(
                mock_api, "mix", "mix_123"
            )
            assert content_type == "mix"
            assert preview.title == "Tutorial Series"
            assert preview.author.nickname == "Teacher"
            assert preview.work_count == 10

    def test_music_preview_extraction(self):
        service = DouyinService()
        mock_music = [
            {
                "aweme_id": "use1",
                "music": {
                    "title": "Viral Sound 2026",
                    "owner_nickname": "SoundArtist",
                    "owner_id": "sound_owner_id",
                    "cover_hd": {"url_list": ["https://cdn.douyin.com/music_hd.jpg"]},
                },
            }
        ]
        with patch.object(service, "_get_api") as mock_get_api:
            mock_api = MagicMock()
            mock_api.getMusicInfo.return_value = mock_music
            mock_get_api.return_value = mock_api

            content_type, preview = service.fetch_preview_metadata(
                mock_api, "music", "music_123"
            )
            assert content_type == "music"
            assert preview.title == "Viral Sound 2026"
            assert preview.author.nickname == "SoundArtist"

    def test_live_preview_extraction(self):
        service = DouyinService()
        mock_live_dict = {
            "title": "Night Stream",
            "nickname": "StreamerNick",
            "avatar": "https://cdn.douyin.com/streamer.jpg",
            "cover": "https://cdn.douyin.com/streamer_cover.jpg",
            "sec_uid": "streamer_sec",
            "status": "2",  # Live now
            "user_count": "15000",
            "partition": "Gaming",
        }
        with patch.object(service, "_get_api") as mock_get_api:
            mock_api = MagicMock()
            mock_api.getLiveInfoApi.return_value = (mock_live_dict, {})
            mock_get_api.return_value = mock_api

            content_type, preview = service.fetch_preview_metadata(
                mock_api, "live", "live_room_1"
            )
            assert content_type == "live"
            assert preview.title == "Night Stream"
            assert "正在直播" in preview.desc
            assert preview.statistics.play_count == 15000

    def test_not_found_raises_douyin_not_found_error(self):
        service = DouyinService()
        with patch.object(service, "_get_api") as mock_get_api:
            mock_api = MagicMock()
            mock_api.getAwemeInfoApi.return_value = None
            mock_get_api.return_value = mock_api

            with pytest.raises(DouyinNotFoundError) as exc_info:
                service.fetch_preview_metadata(mock_api, "aweme", "non_existent_id")
            assert exc_info.value.status_code == 404

    def test_get_download_items_resolution_for_user(self):
        service = DouyinService()
        req = DownloadRequest(
            url="https://www.douyin.com/user/test_user",
            key_type="user",
            key="test_user",
            modes=["post", "like"],
            number={"post": 2, "like": 1},
        )
        with patch.object(service, "_get_api") as mock_get_api:
            mock_api = MagicMock()
            mock_api.getUserInfoApi.side_effect = [
                [{"aweme_id": "p1"}, {"aweme_id": "p2"}],
                [{"aweme_id": "l1"}],
            ]
            mock_get_api.return_value = mock_api

            items = service.get_download_items(req)
            assert len(items) == 3
            assert items[0]["aweme_id"] == "p1"
            assert items[2]["aweme_id"] == "l1"

    def test_task_manager_list_tasks_filtering(self):
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        manager._tasks.clear()

        req1 = DownloadRequest(url="https://v.douyin.com/1", key="1")
        req2 = DownloadRequest(url="https://v.douyin.com/2", key="2")

        with patch.object(manager, "_run_task_pipeline"):
            t1 = manager.submit_task(req1)
            t2 = manager.submit_task(req2)

            manager._tasks[t1.task_id].status = TaskStatus.COMPLETED
            manager._tasks[t2.task_id].status = TaskStatus.DOWNLOADING

            all_tasks = manager.list_tasks()
            assert len(all_tasks) == 2

            completed = manager.list_tasks(status=TaskStatus.COMPLETED)
            assert len(completed) == 1
            assert completed[0].task_id == t1.task_id

            downloading = manager.list_tasks(status=TaskStatus.DOWNLOADING)
            assert len(downloading) == 1
            assert downloading[0].task_id == t2.task_id

    def test_task_manager_pipeline_execution_completion(self, tmp_path):
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
            download_path=str(tmp_path),
        )

        mock_item = {
            "aweme_id": "7488893440932039970",
            "desc": "Pipeline Test Video",
            "awemeType": 0,
            "create_time": 1728100000,
            "statistics": {"digg_count": 100},
        }

        mock_service = MagicMock()
        mock_service.get_download_items.return_value = [mock_item]

        with patch("src.douyin.download.Download.awemeDownload", return_value=True):
            resp = manager.submit_task(req, douyin_service=mock_service)
            # Allow worker thread to execute (polling wait because time.sleep is monkeypatched)
            deadline = time.monotonic() + 2.0
            detail = manager.get_task(resp.task_id)
            while time.monotonic() < deadline and detail.status not in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            ):
                detail = manager.get_task(resp.task_id)

            assert detail.status == TaskStatus.COMPLETED
            assert detail.completed_items == 1
            assert detail.progress_pct == 100.0

    def test_media_and_system_schemas(self):
        now = datetime.now(timezone.utc)
        media_item = MediaItem(
            id="aweme_123",
            filename="video.mp4",
            relative_path="aweme/video.mp4",
            media_type="video",
            file_size=1048576,
            created_at=now,
            preview_url="/api/media/stream/video.mp4",
            download_url="/api/media/download/video.mp4",
        )
        media_list = MediaListResponse(items=[media_item], total=1)
        assert len(media_list.items) == 1
        assert media_list.total == 1

        folder_req = OpenFolderRequest(path="aweme")
        folder_resp = OpenFolderResponse(
            success=True, opened_path="C:\\Downloads\\aweme"
        )
        assert folder_req.path == "aweme"
        assert folder_resp.success is True

        health = HealthResponse(status="ok", version="1.0.0", active_tasks=2)
        assert health.status == "ok"
        assert health.active_tasks == 2
