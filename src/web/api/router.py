# -*- coding: utf-8 -*-
"""
src/web/api/router.py
Unified APIRouter assembling all Douyin Web Downloader endpoints.
"""

from fastapi import APIRouter

from src.web.api.download import router as download_router
from src.web.api.media import router as media_router
from src.web.api.parse import router as parse_router
from src.web.api.settings import router as settings_router
from src.web.api.stream import router as stream_router
from src.web.api.system import router as system_router

api_router = APIRouter(prefix="/api")

# Mount REST sub-routers under /api
api_router.include_router(parse_router)
api_router.include_router(download_router)
api_router.include_router(stream_router)
api_router.include_router(settings_router)
api_router.include_router(media_router)
api_router.include_router(system_router)
