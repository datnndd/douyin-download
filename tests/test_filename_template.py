# -*- coding: utf-8 -*-
"""
tests/test_filename_template.py
Verifies configurable filename templates and file naming sanitization.
"""

import pytest
from src.douyin.download import Download
from src.web.core.schemas import DownloadRequest, SettingsModel


class TestFilenameTemplate:
    @pytest.fixture
    def sample_aweme(self):
        return {
            "aweme_id": "7488893440932039970",
            "desc": "赶海现抓现吃?根本:吃不完<test>|hello",
            "create_time": "2024-10-29 16.01.41",
            "author": {
                "nickname": "Fisherman/Dave*",
                "sec_uid": "MS4wLjABAAAA_test",
            },
            "statistics": {
                "digg_count": 772108,
            },
        }

    def test_default_template_without_param(self, sample_aweme):
        """When filename_template is None, uses legacy {likes}likes_{suffix} pattern."""
        d = Download(filename_template=None)
        name = d._format_file_name(sample_aweme)
        assert name.startswith("000772108likes_")
        assert "2024-10-29 16.01.41" in name

    def test_date_title_id_template(self, sample_aweme):
        """Standard {date}_{title}_{id} template formats cleanly without illegal chars."""
        d = Download(filename_template="{date}_{title}_{id}")
        name = d._format_file_name(sample_aweme)
        assert name.startswith("2024-10-29_")
        assert "7488893440932039970" in name
        # Check no illegal windows characters
        for char in r'\/*?:"<>|':
            assert char not in name

    def test_title_id_template(self, sample_aweme):
        """Template {title}_{id} formats title and ID."""
        d = Download(filename_template="{title}_{id}")
        name = d._format_file_name(sample_aweme)
        assert "7488893440932039970" in name
        assert not name.startswith("2024-")

    def test_author_title_id_template(self, sample_aweme):
        """Template {author}_{title}_{id} includes sanitized author nickname."""
        d = Download(filename_template="{author}_{title}_{id}")
        name = d._format_file_name(sample_aweme)
        assert "Fisherman_Dave" in name
        assert "7488893440932039970" in name

    def test_likes_template(self, sample_aweme):
        """Template with {likes} generates 9-digit padded like count."""
        d = Download(filename_template="{likes}likes_{date}_{title}")
        name = d._format_file_name(sample_aweme)
        assert name.startswith("000772108likes_2024-10-29_")

    def test_schema_supports_filename_template(self):
        """DownloadRequest accepts filename_template field."""
        req = DownloadRequest(
            url="https://v.douyin.com/meBXuCMU5l0/",
            filename_template="{date}_{title}_{id}",
        )
        assert req.filename_template == "{date}_{title}_{id}"

    def test_settings_supports_filename_template(self):
        """SettingsModel accepts and persists filename_template field."""
        settings = SettingsModel(
            path="./Downloaded/",
            filename_template="{author}_{title}_{id}",
        )
        assert settings.filename_template == "{author}_{title}_{id}"
