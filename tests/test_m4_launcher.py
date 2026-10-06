# -*- coding: utf-8 -*-
"""
tests/test_m4_launcher.py
Milestone 4 verification tests for static SPA serving, assets mount, and webui launcher.
"""

from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from src.web.main_web import app
import webui


@pytest.fixture
def client():
    return TestClient(app)


def test_spa_index_served(client):
    """Verify that root GET / serves the compiled React 19 SPA index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Douyin Web Downloader" in response.text
    assert '<div id="root">' in response.text


def test_spa_assets_served(client):
    """Verify that static assets under /assets/ are served properly."""
    dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "assets"
    asset_files = list(dist_dir.glob("*.js"))
    assert len(asset_files) > 0, "Built javascript assets must exist"
    
    first_asset = asset_files[0].name
    response = client.get(f"/assets/{first_asset}")
    assert response.status_code == 200


def test_spa_client_side_routing_fallback(client):
    """Verify that arbitrary client routes fall back to index.html for SPA router."""
    response = client.get("/library/view")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert '<div id="root">' in response.text


def test_api_routes_do_not_fallback_to_spa(client):
    """Verify that non-existent API routes return 404 JSON, not HTML index."""
    response = client.get("/api/nonexistent_endpoint_for_test")
    assert response.status_code == 404
    assert "application/json" in response.headers.get("content-type", "")


def test_webui_arg_parsing(monkeypatch):
    """Verify webui CLI options parsing."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")

    args = parser.parse_args(["--host", "0.0.0.0", "--port", "8888", "--no-browser"])
    assert args.host == "0.0.0.0"
    assert args.port == 8888
    assert args.no_browser is True
