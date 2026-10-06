# -*- coding: utf-8 -*-
"""
Pytest configuration and offline test infrastructure for Douyin Web Downloader.
Provides:
- Automatic monkeypatching of upstream Douyin API endpoints and media CDNs (100% offline, deterministic).
- Temporary directory and SQLite database isolation fixtures.
- Config file generation fixtures.
- FastAPI TestClient integration fixture for Web API verification.
"""

import io
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import requests

# -----------------------------------------------------------------------------
# Patch getttwid before any src.douyin module import to avoid network timeout
# -----------------------------------------------------------------------------
from src.common.utils import Utils
Utils.getttwid = lambda self: "mock_ttwid_offline_token_12345"
from src.douyin import douyin_headers
douyin_headers["Cookie"] = "msToken=mock_msToken; ttwid=mock_ttwid_offline_token_12345; odin_tt=mock_odin; passport_csrf_token=mock_csrf;"


# -----------------------------------------------------------------------------
# Synthetic Data Constants
# -----------------------------------------------------------------------------
MOCK_VIDEO_BYTES = b"MOCK_MP4_HEADER_VIDEO_STREAM_" * 500  # 15,000 bytes
MOCK_AUDIO_BYTES = b"MOCK_MP3_AUDIO_STREAM_CHUNK_" * 300    # 8,700 bytes
MOCK_IMAGE_BYTES = b"MOCK_JPEG_IMAGE_DATA_BYTES__" * 100    # 2,800 bytes


def create_mock_aweme_detail(
    aweme_id: str = "7488893440932039970",
    desc: str = "Test Douyin Video Description",
    digg_count: int = 12500,
    play_count: int = 150000,
    comment_count: int = 840,
    share_count: int = 320,
    create_time: int = 1728100000,
    author_uid: str = "12345678",
    author_sec_uid: str = "MS4wLjABAAAA_test_author",
    nickname: str = "TestAuthor",
    is_video: bool = True
) -> Dict[str, Any]:
    """Generates canonical Douyin aweme detail dictionary matching DouyinApi and Result format."""
    item: Dict[str, Any] = {
        "aweme_id": aweme_id,
        "desc": desc,
        "awemeType": 0 if is_video else 1,
        "create_time": create_time,
        "author": {
            "uid": author_uid,
            "sec_uid": author_sec_uid,
            "nickname": nickname,
            "avatar_thumb": {
                "url_list": ["https://mock-cdn.douyin.com/avatar.jpg"]
            },
            "avatar": {
                "url_list": ["https://mock-cdn.douyin.com/avatar.jpg"]
            }
        },
        "statistics": {
            "digg_count": digg_count,
            "play_count": play_count,
            "comment_count": comment_count,
            "share_count": share_count,
            "collect_count": 500
        },
        "music": {
            "title": "Test Music Track",
            "play_url": {
                "url_list": ["https://mock-cdn.douyin.com/audio.mp3"]
            }
        }
    }
    if is_video:
        item["video"] = {
            "play_addr": {
                "url_list": [f"https://mock-cdn.douyin.com/video_{aweme_id}.mp4"]
            },
            "cover": {
                "url_list": ["https://mock-cdn.douyin.com/cover.jpg"]
            },
            "duration": 45000
        }
    else:
        item["images"] = [
            {"url_list": ["https://mock-cdn.douyin.com/img_01.jpg"]},
            {"url_list": ["https://mock-cdn.douyin.com/img_02.jpg"]}
        ]
        item["video"] = {
            "cover": {
                "url_list": ["https://mock-cdn.douyin.com/cover.jpg"]
            }
        }
    return item


# -----------------------------------------------------------------------------
# Mock Response Engine for Upstream Douyin & Media CDNs
# -----------------------------------------------------------------------------
class MockHttpResponse:
    """Simulates requests.Response for offline deterministic execution."""
    def __init__(
        self,
        url: str,
        status_code: int = 200,
        json_data: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        request_path_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.url = url
        self.status_code = status_code
        self._json_data = json_data
        self._content = content or (json.dumps(json_data, ensure_ascii=False).encode("utf-8") if json_data else b"")
        self.text = self._content.decode("utf-8", errors="replace")
        self.headers = headers or {}
        if "content-length" not in [k.lower() for k in self.headers]:
            self.headers["content-length"] = str(len(self._content))
        self.cookies = {}

        # Mock request object needed by getKey
        self.request = MagicMock()
        self.request.path_url = request_path_url or url.replace("https://www.douyin.com", "").replace("https://live.douyin.com", "")

    def json(self) -> Any:
        if self._json_data is not None:
            return self._json_data
        return json.loads(self.text)

    @property
    def content(self) -> bytes:
        return self._content

    def iter_content(self, chunk_size: int = 8192) -> Generator[bytes, None, None]:
        bio = io.BytesIO(self._content)
        while chunk := bio.read(chunk_size):
            yield chunk

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def mock_network_dispatch(url: str, *args, **kwargs) -> MockHttpResponse:
    """Deterministic offline dispatcher for all outgoing HTTP requests."""
    url_str = str(url)
    req_headers = kwargs.get("headers") or {}

    # 1. Short URL redirection resolution (v.douyin.com)
    if "v.douyin.com" in url_str:
        if "user" in url_str:
            target_url = "https://www.douyin.com/user/MS4wLjABAAAA_test_author"
            path_url = "/user/MS4wLjABAAAA_test_author"
        elif "mix" in url_str or "collection" in url_str:
            target_url = "https://www.douyin.com/collection/7488893440932039972"
            path_url = "/collection/7488893440932039972"
        elif "music" in url_str:
            target_url = "https://www.douyin.com/music/7488893440932039973"
            path_url = "/music/7488893440932039973"
        elif "live" in url_str:
            target_url = "https://live.douyin.com/7488893440932039974"
            path_url = "/7488893440932039974"
        elif "note" in url_str:
            target_url = "https://www.douyin.com/note/7488893440932039971"
            path_url = "/note/7488893440932039971"
        else:
            # Default single video
            target_url = "https://www.douyin.com/video/7488893440932039970"
            path_url = "/video/7488893440932039970"

        return MockHttpResponse(target_url, 200, request_path_url=path_url)

    # 2. Live enter endpoints
    if "webcast/room/web/enter" in url_str or "live.douyin.com" in url_str:
        live_data = {
            "status_code": 0,
            "data": {
                "data": [
                    {
                        "status_str": "2",
                        "title": "Test Live Stream",
                        "cover": {"url_list": ["https://mock-cdn.douyin.com/cover.jpg"]},
                        "owner": {
                            "nickname": "TestStreamer",
                            "sec_uid": "MS4wLjABAAAA_test_streamer",
                            "web_rid": "7488893440932039974",
                            "avatar_thumb": {"url_list": ["https://mock-cdn.douyin.com/avatar.jpg"]}
                        },
                        "user_count_str": "1000",
                        "room_view_stats": {"display_long": "1000"},
                        "stream_url": {
                            "flv_pull_url": {
                                "FULL_HD1": "https://mock-cdn.douyin.com/live.flv"
                            }
                        }
                    }
                ]
            }
        }
        return MockHttpResponse(url_str, 200, json_data=live_data, request_path_url="/7488893440932039974")

    if "webcast/room/reflow/info" in url_str:
        reflow_data = {
            "status_code": 0,
            "data": {
                "room": {
                    "owner": {
                        "web_rid": "7488893440932039974",
                        "nickname": "TestStreamer"
                    }
                }
            }
        }
        return MockHttpResponse(url_str, 200, json_data=reflow_data)

    # 3. Aweme Detail API (Single Video/Note)
    if "/aweme/v1/web/aweme/detail/" in url_str:
        aweme_id_match = re.search(r"aweme_id=(\d+)", url_str)
        aweme_id = aweme_id_match.group(1) if aweme_id_match else "7488893440932039970"
        detail = create_mock_aweme_detail(aweme_id=aweme_id)
        return MockHttpResponse(url_str, 200, json_data={"status_code": 0, "aweme_detail": detail})

    # 4. User Posts & Likes
    if "/aweme/v1/web/aweme/post/" in url_str or "/aweme/v1/web/aweme/favorite/" in url_str or "/web/api/v2/aweme/like/" in url_str:
        items = [
            create_mock_aweme_detail(aweme_id="7488893440932039901", desc="User Post 1", digg_count=100, create_time=1728000000),
            create_mock_aweme_detail(aweme_id="7488893440932039902", desc="User Post 2", digg_count=5000, create_time=1728100000),
            create_mock_aweme_detail(aweme_id="7488893440932039903", desc="User Post 3", digg_count=20000, create_time=1728200000),
        ]
        return MockHttpResponse(url_str, 200, json_data={"status_code": 0, "aweme_list": items, "has_more": False, "max_cursor": 0})

    # 5. User Mix List
    if "/aweme/v1/web/mix/list/" in url_str:
        mix_data = {
            "status_code": 0,
            "mix_infos": [
                {"mix_id": "7488893440932039972", "mix_name": "TutorialSeries"}
            ],
            "has_more": False,
            "cursor": 0
        }
        return MockHttpResponse(url_str, 200, json_data=mix_data)

    # 6. Mix Aweme List
    if "/aweme/v1/web/mix/aweme/" in url_str:
        items = [
            create_mock_aweme_detail(aweme_id="7488893440932039951", desc="Mix Episode 1", digg_count=1200),
            create_mock_aweme_detail(aweme_id="7488893440932039952", desc="Mix Episode 2", digg_count=2400),
        ]
        return MockHttpResponse(url_str, 200, json_data={"status_code": 0, "aweme_list": items, "has_more": False, "cursor": 0})

    # 7. Music Aweme List
    if "/aweme/v1/web/music/aweme/" in url_str:
        items = [
            create_mock_aweme_detail(aweme_id="7488893440932039961", desc="Music Video 1"),
        ]
        return MockHttpResponse(url_str, 200, json_data={"status_code": 0, "aweme_list": items, "has_more": False, "cursor": 0})

    # 8. User Profile Info
    if "/aweme/v1/web/user/profile/other/" in url_str or "/aweme/v1/web/im/user/info/" in url_str:
        user_info = {
            "status_code": 0,
            "user": {
                "uid": "12345678",
                "sec_uid": "MS4wLjABAAAA_test_author",
                "nickname": "TestAuthor",
                "avatar_thumb": {"url_list": ["https://mock-cdn.douyin.com/avatar.jpg"]},
                "aweme_count": 42
            }
        }
        return MockHttpResponse(url_str, 200, json_data=user_info)

    # 9. Media CDN Downloads (Video, Audio, Cover, Avatar) with HTTP Range support
    if "mock-cdn.douyin.com" in url_str or url_str.endswith(".mp4") or url_str.endswith(".mp3") or url_str.endswith(".jpg") or url_str.endswith(".jpeg"):
        if ".mp4" in url_str:
            raw_bytes = MOCK_VIDEO_BYTES
        elif ".mp3" in url_str:
            raw_bytes = MOCK_AUDIO_BYTES
        else:
            raw_bytes = MOCK_IMAGE_BYTES

        total_len = len(raw_bytes)
        range_header = req_headers.get("Range") or req_headers.get("range")

        if range_header and range_header.startswith("bytes="):
            # Parse Range: bytes={offset}-
            match = re.search(r"bytes=(\d+)-", range_header)
            if match:
                offset = int(match.group(1))
                if offset < total_len:
                    sliced = raw_bytes[offset:]
                    headers = {
                        "content-length": str(len(sliced)),
                        "content-range": f"bytes {offset}-{total_len - 1}/{total_len}",
                    }
                    return MockHttpResponse(url_str, 206, content=sliced, headers=headers)
                else:
                    return MockHttpResponse(url_str, 416, content=b"")

        headers = {"content-length": str(total_len)}
        return MockHttpResponse(url_str, 200, content=raw_bytes, headers=headers)

    # 10. Fallback standard JSON
    return MockHttpResponse(url_str, 200, json_data={"status_code": 0, "message": "success"})


# -----------------------------------------------------------------------------
# Pytest Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    """Bypasses rate-limiting sleeps in DouyinApi/DouyinClient during offline testing."""
    monkeypatch.setattr(time, "sleep", lambda s: None)


@pytest.fixture(autouse=True)
def offline_douyin_network(monkeypatch):
    """
    Autouse fixture that intercepts requests.Session.get, requests.Session.post,
    requests.get, and requests.post with deterministic mock responses.
    Prevents any network access, captchas, or external dependencies.
    """
    def mock_get(*args, **kwargs):
        if len(args) > 1 and isinstance(args[1], str):
            target_url = args[1]
            extra_args = args[2:]
        elif len(args) > 0 and isinstance(args[0], str):
            target_url = args[0]
            extra_args = args[1:]
        else:
            target_url = kwargs.pop("url", "")
            extra_args = args
        kwargs.pop("url", None)
        return mock_network_dispatch(target_url, *extra_args, **kwargs)

    def mock_post(*args, **kwargs):
        if len(args) > 1 and isinstance(args[1], str):
            target_url = args[1]
            extra_args = args[2:]
        elif len(args) > 0 and isinstance(args[0], str):
            target_url = args[0]
            extra_args = args[1:]
        else:
            target_url = kwargs.pop("url", "")
            extra_args = args
        kwargs.pop("url", None)
        return mock_network_dispatch(target_url, *extra_args, **kwargs)

    monkeypatch.setattr(requests.Session, "get", mock_get)
    monkeypatch.setattr(requests.Session, "post", mock_post)
    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)
    yield


@pytest.fixture
def temp_download_dir(tmp_path: Path) -> Path:
    """Provides an isolated clean temporary download directory."""
    d = tmp_path / "Downloaded"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def sample_aweme_data() -> Dict[str, Any]:
    """Provides a standard single video aweme metadata dictionary."""
    return create_mock_aweme_detail(
        aweme_id="7488893440932039970",
        desc="Opaque Box Test Video Title",
        digg_count=12500,
        play_count=150000,
        comment_count=840,
        share_count=320,
        create_time=1728100000,
        nickname="OpaqueAuthor",
        is_video=True
    )


@pytest.fixture
def sample_image_note_data() -> Dict[str, Any]:
    """Provides a standard image note aweme metadata dictionary."""
    return create_mock_aweme_detail(
        aweme_id="7488893440932039971",
        desc="Opaque Box Test Image Note",
        digg_count=500,
        play_count=3000,
        is_video=False
    )


@pytest.fixture
def sample_user_aweme_list() -> List[Dict[str, Any]]:
    """Provides a list of awemes with varying statistics for sorting and filtering."""
    return [
        create_mock_aweme_detail(aweme_id="7488893440932039901", desc="Video Alpha", digg_count=100, play_count=1000, create_time=1728000000),
        create_mock_aweme_detail(aweme_id="7488893440932039902", desc="Video Beta", digg_count=50000, play_count=500000, create_time=1728200000),
        create_mock_aweme_detail(aweme_id="7488893440932039903", desc="Video Gamma", digg_count=2500, play_count=30000, create_time=1728100000),
        create_mock_aweme_detail(aweme_id="7488893440932039904", desc="Video Delta", digg_count=8000, play_count=90000, create_time=1728300000),
        create_mock_aweme_detail(aweme_id="7488893440932039905", desc="Video Epsilon", digg_count=120000, play_count=1200000, create_time=1728400000),
    ]


@pytest.fixture
def sample_config_yaml(tmp_path: Path) -> Path:
    """Creates a temporary valid config.yaml with test settings."""
    cfg_path = tmp_path / "config.yaml"
    content = {
        "link": ["https://v.douyin.com/iWhQezyaUco/"],
        "path": str(tmp_path / "Downloaded"),
        "music": True,
        "cover": True,
        "avatar": True,
        "json": True,
        "folderstyle": True,
        "database": True,
        "mode": ["post"],
        "thread": 4,
        "cookies": {
            "sessionid": "test_session_id",
            "passport_csrf_token": "test_csrf_token"
        },
        "number": {"post": 5, "like": 0, "allmix": 0, "mix": 0, "music": 0},
        "increase": {"post": False, "like": False},
        "filter": {"sort_by": "digg_count", "reverse": True, "limit": 3}
    }
    import yaml
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(content, f, allow_unicode=True)
    return cfg_path


# -----------------------------------------------------------------------------
# FastAPI Test Client Integration
# -----------------------------------------------------------------------------
try:
    from src.web.main_web import app as fastapi_app
    HAS_WEB_APP = True
except (ImportError, ModuleNotFoundError):
    fastapi_app = None
    HAS_WEB_APP = False


@pytest.fixture
def api_client():
    """
    Test client for FastAPI REST endpoints.
    When src.web.main_web is implemented, provides starlette TestClient.
    If pending implementation, skips gracefully per Progressive Testability.
    """
    if not HAS_WEB_APP or fastapi_app is None:
        pytest.skip("FastAPI app (src.web.main_web) not yet implemented (pending Milestone 2)")
    from fastapi.testclient import TestClient
    return TestClient(fastapi_app)
