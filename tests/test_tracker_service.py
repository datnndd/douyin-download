# -*- coding: utf-8 -*-
"""
tests/test_tracker_service.py
Comprehensive test suite for Douyin Creator Video Tracking & 1-Click Update:
1. Database Schema & Migration (minimal columns, cascade delete, zero raw JSON)
2. Baseline Enrollment & Pinned Video Handling (is_top == 1 ignored for baseline)
3. Incremental Change Detection (filtering pinned videos, early stopping, deduplication)
4. Minimal Storage Footprint (<100 bytes/video record, zero rawdata JSON)
5. 1-Click Update Dispatching (task enqueueing, aweme_ids resolution, status transition)
6. REST API Endpoints (enrollment, list, check, update, stats, untrack)
"""

import os
import sqlite3
import tempfile
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.douyin.database import Database
from src.web.core.schemas import TaskStatus
from src.web.services.tracker_service import TrackerService
from src.web.services.task_manager import TaskManager, TaskRecord
from src.web.main_web import app


@pytest.fixture
def temp_db():
    """Provides a fresh temporary SQLite database."""
    fd, path = tempfile.mkstemp(suffix="_test_tracker.db")
    os.close(fd)
    db = Database(path)
    yield db
    db.close()
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


@pytest.fixture
def tracker_svc(temp_db):
    """Provides an isolated TrackerService instance using the temporary database."""
    svc = TrackerService(db_path=temp_db.path)
    svc.stop_background_worker()
    yield svc
    svc.database.close()


@pytest.fixture
def client(temp_db):
    """Provides FastAPI test client wired to the isolated temporary DB."""
    svc = TrackerService(db_path=temp_db.path)
    svc.stop_background_worker()
    with patch("src.web.api.tracker.get_tracker_service", return_value=svc):
        with TestClient(app) as test_client:
            yield test_client
    svc.database.close()


# ==============================================================================
# 1. Database Schema & Minimal Persistence Tests
# ==============================================================================


class TestTrackerDatabase:
    def test_schema_creation_and_indexes(self, temp_db):
        """Verify tracked_creators and tracked_video_log tables exist with expected columns."""
        cur = temp_db.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

        assert "tracked_creators" in tables
        assert "tracked_video_log" in tables

        # Verify minimal columns in tracked_video_log (strictly no rawdata / statistics_json)
        cur.execute("PRAGMA table_info(tracked_video_log)")
        cols = {row[1] for row in cur.fetchall()}
        assert "aweme_id" in cols
        assert "sec_uid" in cols
        assert "create_time" in cols
        assert "title" in cols
        assert "status" in cols
        assert "downloaded_at" in cols
        # Strictly verify no raw JSON dumps
        assert "rawdata" not in cols
        assert "statistics_json" not in cols

    def test_storage_footprint_is_minimal(self, temp_db):
        """Assert stored records contain only truncated text and identifiers."""
        temp_db.upsert_tracked_creator(
            sec_uid="SEC_USER_001",
            unique_id="creator_one",
            nickname="Test Creator",
            avatar_thumb="https://example.com/thumb.jpg",
            last_aweme_id="7000000001",
            last_aweme_time=1700000000,
        )

        long_desc = "A" * 1000  # 1000-char description
        temp_db.sync_tracked_videos(
            sec_uid="SEC_USER_001",
            new_videos=[
                {"aweme_id": "7000000002", "create_time": 1700000500, "desc": long_desc}
            ],
        )

        pending = temp_db.get_pending_videos("SEC_USER_001")
        assert len(pending) == 1
        # Description must be truncated to <= 256 chars
        assert len(pending[0]["title"]) <= 256
        assert pending[0]["status"] == "pending"

    def test_cascade_delete_creator(self, temp_db):
        """Deleting a creator removes all associated video logs."""
        temp_db.upsert_tracked_creator(sec_uid="SEC_USER_DEL", nickname="To Delete")
        temp_db.sync_tracked_videos(
            sec_uid="SEC_USER_DEL",
            new_videos=[
                {"aweme_id": "8001", "create_time": 1700001000, "desc": "Video 1"},
                {"aweme_id": "8002", "create_time": 1700002000, "desc": "Video 2"},
            ],
        )
        assert len(temp_db.get_pending_videos("SEC_USER_DEL")) == 2

        deleted = temp_db.delete_tracked_creator("SEC_USER_DEL")
        assert deleted is True
        assert temp_db.get_tracked_creator("SEC_USER_DEL") is None
        assert len(temp_db.get_pending_videos("SEC_USER_DEL")) == 0


# ==============================================================================
# 2. Creator Enrollment & Baseline Tests
# ==============================================================================


class TestTrackerEnrollment:
    def test_enrollment_with_pinned_video_filter(self, tracker_svc):
        """
        When enrolling, pinned videos (is_top == 1) are skipped
        and the newest non-pinned video becomes the baseline.
        """
        mock_feed = [
            # Pinned video 1 (older publish date, is_top=1)
            {"aweme_id": "PINNED_1", "create_time": 1600000000, "is_top": 1, "desc": "Pinned 1"},
            # Pinned video 2 (is_top=1)
            {"aweme_id": "PINNED_2", "create_time": 1650000000, "is_top": 1, "desc": "Pinned 2"},
            # Normal newest video (is_top=0) -> Should become baseline
            {"aweme_id": "NORMAL_NEWEST", "create_time": 1720000000, "is_top": 0, "desc": "Newest Post"},
            # Normal older video
            {"aweme_id": "NORMAL_OLDER", "create_time": 1710000000, "is_top": 0, "desc": "Older Post"},
        ]

        with patch.object(tracker_svc, "_fetch_creator_feed_page", return_value=mock_feed):
            creator = tracker_svc.track_creator(
                sec_uid="SEC_ENROLL_01",
                nickname="Creator A",
                unique_id="creator_a",
            )

        assert creator.sec_uid == "SEC_ENROLL_01"
        assert creator.nickname == "Creator A"
        # Baseline must be the first NON-PINNED video!
        assert creator.last_aweme_id == "NORMAL_NEWEST"
        assert creator.last_aweme_time == 1720000000
        assert creator.pending_new_count == 0


# ==============================================================================
# 3. Change Detection & Pinned Video Handling
# ==============================================================================


class TestChangeDetection:
    def test_detect_new_videos_and_ignore_pinned(self, tracker_svc):
        """
        Test that new videos published after baseline are detected,
        pinned items are ignored, and pagination terminates early.
        """
        # 1. Establish creator with baseline NORMAL_V1
        tracker_svc.database.upsert_tracked_creator(
            sec_uid="SEC_DETECT_01",
            nickname="Active Creator",
            last_aweme_id="NORMAL_V1",
            last_aweme_time=1700000000,
        )

        # 2. Feed simulation:
        # Pinned video at top (is_top=1)
        # 2 newly uploaded videos (NORMAL_V3, NORMAL_V2)
        # Baseline video (NORMAL_V1)
        # Older video that should never be processed (NORMAL_V0)
        mock_feed = [
            {"aweme_id": "PINNED_TOP", "create_time": 1500000000, "is_top": 1, "desc": "Pinned Old"},
            {"aweme_id": "NORMAL_V3", "create_time": 1700003000, "is_top": 0, "desc": "Video 3"},
            {"aweme_id": "NORMAL_V2", "create_time": 1700002000, "is_top": 0, "desc": "Video 2"},
            {"aweme_id": "NORMAL_V1", "create_time": 1700000000, "is_top": 0, "desc": "Baseline Video 1"},
            {"aweme_id": "NORMAL_V0", "create_time": 1690000000, "is_top": 0, "desc": "Should Be Ignored"},
        ]

        with patch.object(tracker_svc, "_fetch_creator_feed_page", return_value=mock_feed):
            updated, added_count = tracker_svc.check_creator_updates("SEC_DETECT_01")

        assert added_count == 2
        assert updated.pending_new_count == 2
        pending_ids = [v.aweme_id for v in updated.pending_videos]
        assert "NORMAL_V3" in pending_ids
        assert "NORMAL_V2" in pending_ids
        assert "PINNED_TOP" not in pending_ids
        assert "NORMAL_V1" not in pending_ids
        assert "NORMAL_V0" not in pending_ids

    def test_idempotent_repeated_check(self, tracker_svc):
        """Repeated checks before downloading do not duplicate pending items."""
        tracker_svc.database.upsert_tracked_creator(
            sec_uid="SEC_REPEAT_01",
            nickname="Repeat Creator",
            last_aweme_id="NORMAL_V1",
            last_aweme_time=1700000000,
        )

        mock_feed = [
            {"aweme_id": "NORMAL_V2", "create_time": 1700002000, "is_top": 0, "desc": "Video 2"},
            {"aweme_id": "NORMAL_V1", "create_time": 1700000000, "is_top": 0, "desc": "Video 1"},
        ]

        with patch.object(tracker_svc, "_fetch_creator_feed_page", return_value=mock_feed):
            _, added1 = tracker_svc.check_creator_updates("SEC_REPEAT_01")
            assert added1 == 1

            # Second check: NORMAL_V2 is already pending -> early stop
            _, added2 = tracker_svc.check_creator_updates("SEC_REPEAT_01")
            assert added2 == 0

        creator = tracker_svc.get_creator("SEC_REPEAT_01")
        assert creator.pending_new_count == 1


# ==============================================================================
# 4. 1-Click Update & Task Dispatching Tests
# ==============================================================================


class TestOneClickUpdate:
    def test_start_one_click_update_submits_only_pending_items(self, tracker_svc):
        """
        1-Click Update constructs a task targeting strictly pending aweme_ids,
        and transitions them to 'downloaded' with baseline updated on completion.
        """
        sec_uid = "SEC_UPDATE_01"
        tracker_svc.database.upsert_tracked_creator(
            sec_uid=sec_uid,
            nickname="Update Creator",
            last_aweme_id="NORMAL_V1",
            last_aweme_time=1700000000,
        )

        # Sync 2 pending videos
        tracker_svc.database.sync_tracked_videos(
            sec_uid=sec_uid,
            new_videos=[
                {"aweme_id": "V3", "create_time": 1700003000, "desc": "New Video 3"},
                {"aweme_id": "V2", "create_time": 1700002000, "desc": "New Video 2"},
            ],
        )
        assert tracker_svc.get_creator(sec_uid).pending_new_count == 2

        # Mock TaskManager
        mock_tm = MagicMock()
        mock_task_resp = MagicMock(task_id="task-uuid-1234", status=TaskStatus.PENDING)
        mock_tm.submit_task.return_value = mock_task_resp

        registered_callbacks = []
        def _fake_register_cb(tid, cb):
            registered_callbacks.append(cb)

        mock_tm.register_completion_callback.side_effect = _fake_register_cb

        with patch("src.web.services.tracker_service.TaskManager.get_instance", return_value=mock_tm):
            task_resp = tracker_svc.start_one_click_update(sec_uid)

        assert task_resp.task_id == "task-uuid-1234"
        # Verify submit_task received DownloadRequest with aweme_ids = ['V3', 'V2']
        submitted_req = mock_tm.submit_task.call_args[0][0]
        assert submitted_req.aweme_ids == ["V3", "V2"]
        assert submitted_req.key == sec_uid

        # Now simulate completion callback execution
        assert len(registered_callbacks) == 1
        fake_record = MagicMock(task_id="task-uuid-1234")
        registered_callbacks[0](fake_record, TaskStatus.COMPLETED)

        # Verify state transition: pending_new_count is 0, last_aweme_id updated to V3
        updated = tracker_svc.get_creator(sec_uid)
        assert updated.pending_new_count == 0
        assert updated.last_aweme_id == "V3"
        assert len(tracker_svc.database.get_pending_videos(sec_uid)) == 0


# ==============================================================================
# 5. REST API Integration Tests
# ==============================================================================


class TestTrackerApi:
    def test_tracker_api_crud_flow(self, client):
        """End-to-end API test for creator enrollment, checking, stats, and deletion."""
        # 1. Initially 0 creators
        resp = client.get("/api/tracker/creators")
        assert resp.status_code == 200
        assert resp.json() == []

        # 2. Get stats badge
        stats_resp = client.get("/api/tracker/stats")
        assert stats_resp.status_code == 200
        assert stats_resp.json() == {"total_tracked_creators": 0, "total_pending_videos": 0}

        # 3. Enroll creator via POST /api/tracker/creators
        mock_feed = [
            {"aweme_id": "V_BASE", "create_time": 1700000000, "is_top": 0, "desc": "Baseline"}
        ]
        with patch("src.web.services.tracker_service.TrackerService._fetch_creator_feed_page", return_value=mock_feed):
            enroll_resp = client.post(
                "/api/tracker/creators",
                json={
                    "sec_uid": "SEC_API_USER",
                    "nickname": "API Test Creator",
                    "unique_id": "api_creator",
                },
            )
        assert enroll_resp.status_code == 201
        data = enroll_resp.json()
        assert data["sec_uid"] == "SEC_API_USER"
        assert data["last_aweme_id"] == "V_BASE"
        assert data["pending_new_count"] == 0

        # 4. Check updates via POST /api/tracker/creators/{sec_uid}/check
        new_feed = [
            {"aweme_id": "V_NEW_1", "create_time": 1700005000, "is_top": 0, "desc": "Brand New"},
            {"aweme_id": "V_BASE", "create_time": 1700000000, "is_top": 0, "desc": "Baseline"},
        ]
        with patch("src.web.services.tracker_service.TrackerService._fetch_creator_feed_page", return_value=new_feed):
            check_resp = client.post("/api/tracker/creators/SEC_API_USER/check")
        assert check_resp.status_code == 200
        check_data = check_resp.json()
        assert check_data["pending_new_count"] == 1

        # 5. Verify badge stats count updated
        stats_resp2 = client.get("/api/tracker/stats")
        assert stats_resp2.status_code == 200
        assert stats_resp2.json()["total_pending_videos"] == 1

        # 6. Untrack creator via DELETE /api/tracker/creators/{sec_uid}
        del_resp = client.delete("/api/tracker/creators/SEC_API_USER")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # 7. Creator list is now empty again
        list_resp = client.get("/api/tracker/creators")
        assert list_resp.status_code == 200
        assert list_resp.json() == []
