# -*- coding: utf-8 -*-
"""
src/web/api/parse.py
POST /api/parse endpoint for link resolution and preview extraction.
"""

import logging
from fastapi import APIRouter, HTTPException

from src.web.core.schemas import ParseRequest, ParseResponse
from src.web.services.douyin_service import (
    DouyinInvalidUrlError,
    DouyinNotFoundError,
    DouyinService,
    DouyinServiceError,
    DouyinUpstreamError,
)

logger = logging.getLogger("DouyinWeb.Api.Parse")
router = APIRouter(tags=["Parse"])

_service: DouyinService = DouyinService()


def get_douyin_service() -> DouyinService:
    global _service
    return _service


@router.post("/parse", response_model=ParseResponse, summary="Parse Douyin URL & Extract Preview")
async def parse_url_endpoint(payload: ParseRequest) -> ParseResponse:
    """
    Parses a Douyin share URL or raw string, expands short links,
    resolves the key type, and extracts rich preview metadata.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    service = get_douyin_service()
    from src.web.core.config import ConfigManager
    effective_cookie = payload.cookie or ConfigManager.get_instance().get_cookie_header() or None

    try:
        response = await service.parse_url(payload.url, cookie=effective_cookie)
        return response
    except DouyinInvalidUrlError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DouyinNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DouyinUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error parsing URL {payload.url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error parsing URL: {str(e)}")
