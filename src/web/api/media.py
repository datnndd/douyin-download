# -*- coding: utf-8 -*-
"""
src/web/api/media.py
Endpoints for media library listing, HTTP 206 range streaming, and downloading.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, Request, Response

from src.web.core.schemas import MediaListResponse
from src.web.services.media_service import MediaService

logger = logging.getLogger("DouyinWeb.Api.Media")
router = APIRouter(tags=["Media Library"])


def get_media_service() -> MediaService:
    return MediaService.get_instance()


@router.get(
    "/media",
    response_model=MediaListResponse,
    summary="List Downloaded Media Files",
)
async def list_media_endpoint() -> MediaListResponse:
    """Discovers all downloaded media files in the download directory."""
    service = get_media_service()
    items = service.scan_media()
    return MediaListResponse(items=items, total=len(items))


@router.get(
    "/media/stream/{path:path}",
    summary="HTTP 206 Partial Content Stream",
)
async def stream_media_endpoint(path: str, range: Optional[str] = Header(None)) -> Response:
    """Streams a video or audio file with support for HTTP Range requests."""
    service = get_media_service()
    return service.stream_media_range(path, range_header=range)


@router.get(
    "/media/download/{path:path}",
    summary="Download Media File Attachment",
)
async def download_media_endpoint(path: str):
    """Downloads a media file directly as an attachment."""
    service = get_media_service()
    return service.download_media(path)
