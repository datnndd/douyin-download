# -*- coding: utf-8 -*-
"""
Tests for Preview-First flow and Creator Profile preview enhancements.
Verifies author aweme_count, following_count, tailored content types, and fallback behavior.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.douyin.douyinapi import DouyinApi
from src.douyin.result import Result
from src.web.core.schemas import AuthorPreview, PreviewMetadata, StatisticsModel
from src.web.services.douyin_service import DouyinService


class TestPreviewFirstSchemas:
    def test_author_preview_following_count_coercion(self):
        """AuthorPreview correctly parses and coerces following_count."""
        author = AuthorPreview(
            nickname="Test Creator",
            avatar_thumb="https://cdn.example.com/thumb.jpg",
            avatar="https://cdn.example.com/hd.jpg",
            sec_uid="MS4wLjABAAAA_test",
            signature="Bio here",
            unique_id="creator123",
            follower_count="12500",
            total_favorited=98000,
            following_count="88",
        )
        assert author.following_count == 88
        assert author.follower_count == 12500
        assert author.total_favorited == 98000
        assert author.avatar == "https://cdn.example.com/hd.jpg"

    def test_author_preview_none_counts_default_to_zero(self):
        """None or empty string counts default to 0."""
        author = AuthorPreview(
            nickname="Test Creator",
            avatar_thumb="https://cdn.example.com/thumb.jpg",
            sec_uid="MS4wLjABAAAA_test",
            follower_count=None,
            total_favorited="",
            following_count=None,
        )
        assert author.following_count == 0
        assert author.follower_count == 0
        assert author.total_favorited == 0

    def test_result_author_dict_contains_aweme_count(self):
        """Result class includes aweme_count in authorDict."""
        res = Result()
        assert "aweme_count" in res.authorDict
        assert res.authorDict["aweme_count"] == 0

    def test_result_data_convert_preserves_aweme_count(self):
        """Result.dataConvert retains aweme_count from Douyin raw payload."""
        res = Result()
        raw_user = {
            "nickname": "Artist",
            "aweme_count": 142,
            "follower_count": 500000,
            "following_count": 12,
            "total_favorited": 8900000,
            "unique_id": "artist_id",
            "signature": "My gallery",
        }
        res.dataConvert(0, res.authorDict, raw_user)
        assert res.authorDict["aweme_count"] == 142
        assert res.authorDict["nickname"] == "Artist"


class TestDouyinServiceUserPreview:
    def test_fetch_user_preview_with_user_detail_api(self):
        """_fetch_user_preview extracts work_count from getUserDetailApi."""
        service = DouyinService()
        mock_api = MagicMock(spec=DouyinApi)
        mock_api.getUserDetailApi.return_value = {
            "nickname": "Top Creator",
            "aweme_count": 85,
            "follower_count": 2500000,
            "following_count": 150,
            "total_favorited": 45000000,
            "unique_id": "top_creator",
            "short_id": "12345",
            "signature": "Welcome to my profile!",
            "avatar_thumb": {"url_list": ["https://cdn.example.com/avatar_thumb.jpg"]},
            "avatar": {"url_list": ["https://cdn.example.com/avatar_hd.jpg"]},
            "cover_url": {"url_list": ["https://cdn.example.com/cover.jpg"]},
        }

        content_type, preview = service._fetch_user_preview(mock_api, "MS4wLjABAAAA_secuid")
        assert content_type == "user"
        assert preview.work_count == 85
        assert preview.author.nickname == "Top Creator"
        assert preview.author.avatar == "https://cdn.example.com/avatar_hd.jpg"
        assert preview.author.following_count == 150
        assert preview.author.follower_count == 2500000
        assert preview.extra["aweme_count"] == 85
        assert preview.extra["unique_id"] == "top_creator"

    def test_fetch_user_preview_fallback_to_user_info_api(self):
        """_fetch_user_preview falls back to getUserInfoApi when getUserDetailApi returns None."""
        service = DouyinService()
        mock_api = MagicMock(spec=DouyinApi)
        mock_api.getUserDetailApi.return_value = None
        mock_api.getUserInfoApi.return_value = [
            {
                "author": {
                    "nickname": "Fallback Creator",
                    "aweme_count": 42,
                    "follower_count": 10000,
                    "following_count": 25,
                    "total_favorited": 50000,
                    "unique_id": "fallback_id",
                    "signature": "Fallback bio",
                    "avatar_thumb": {"url_list": ["https://cdn.example.com/avatar.jpg"]},
                }
            }
        ]

        content_type, preview = service._fetch_user_preview(mock_api, "MS4wLjABAAAA_secuid2")
        assert content_type == "user"
        assert preview.work_count == 42
        assert preview.author.nickname == "Fallback Creator"
        assert preview.author.following_count == 25
        assert preview.author.unique_id == "fallback_id"

    def test_fetch_user_preview_zero_posts_graceful_handling(self):
        """_fetch_user_preview handles users with 0 works or empty post list gracefully."""
        service = DouyinService()
        mock_api = MagicMock(spec=DouyinApi)
        mock_api.getUserDetailApi.return_value = {
            "nickname": "New User",
            "aweme_count": 0,
            "follower_count": 0,
            "following_count": 0,
            "total_favorited": 0,
        }

        content_type, preview = service._fetch_user_preview(mock_api, "MS4wLjABAAAA_empty")
        assert content_type == "user"
        assert preview.work_count == 0
        assert preview.author.nickname == "New User"


class TestDouyinServiceMediaPreviews:
    def test_fetch_aweme_preview_photo_album(self):
        """_fetch_aweme_preview returns image content_type and full images list for photo note."""
        service = DouyinService()
        mock_api = MagicMock(spec=DouyinApi)
        mock_api.getAwemeInfoApi.return_value = {
            "aweme_id": "7488893440932039971",
            "awemeType": 1,
            "desc": "Stunning photo album",
            "images": [
                {"url_list": ["https://cdn.example.com/p1.jpg"]},
                {"url_list": ["https://cdn.example.com/p2.jpg"]},
                {"url_list": ["https://cdn.example.com/p3.jpg"]},
            ],
            "author": {
                "nickname": "Photographer",
                "avatar_thumb": {"url_list": ["https://cdn.example.com/avatar.jpg"]},
            },
            "statistics": {
                "digg_count": 500,
                "comment_count": 20,
            },
        }

        content_type, preview = service._fetch_aweme_preview(mock_api, "7488893440932039971")
        assert content_type == "image"
        assert len(preview.images) == 3
        assert preview.work_count == 3
        assert preview.cover_url == "https://cdn.example.com/p1.jpg"

    def test_fetch_aweme_preview_single_video(self):
        """_fetch_aweme_preview returns video content_type and duration for single video."""
        service = DouyinService()
        mock_api = MagicMock(spec=DouyinApi)
        mock_api.getAwemeInfoApi.return_value = {
            "aweme_id": "7488893440932039970",
            "awemeType": 0,
            "desc": "Exciting video tutorial",
            "video": {
                "cover": {"url_list": ["https://cdn.example.com/cover.jpg"]},
                "duration": 95000,
            },
            "author": {
                "nickname": "VideoMaker",
                "unique_id": "maker",
                "avatar_thumb": {"url_list": ["https://cdn.example.com/avatar.jpg"]},
            },
            "statistics": {
                "digg_count": 12000,
            },
        }

        content_type, preview = service._fetch_aweme_preview(mock_api, "7488893440932039970")
        assert content_type == "video"
        assert preview.duration == 95
        assert preview.work_count == 1
        assert preview.author.unique_id == "maker"
