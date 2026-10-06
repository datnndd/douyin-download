# -*- coding: utf-8 -*-
"""
src/web/api/system.py
Endpoints for system health reporting and desktop Windows Explorer bridge.
"""

import logging
import shutil
from fastapi import APIRouter, HTTPException

from src.web.core.schemas import HealthResponse, OpenFolderRequest, OpenFolderResponse
from src.web.services.media_service import MediaService
from src.web.services.task_manager import TaskManager

logger = logging.getLogger("DouyinWeb.Api.System")
router = APIRouter(tags=["System Bridge"])


def get_media_service() -> MediaService:
    return MediaService.get_instance()


def get_task_manager() -> TaskManager:
    return TaskManager.get_instance()


@router.post(
    "/open-folder",
    response_model=OpenFolderResponse,
    summary="Open Download Directory in Explorer",
)
async def open_folder_endpoint(payload: OpenFolderRequest) -> OpenFolderResponse:
    """
    Desktop integration bridge: Opens the download directory (or valid subfolder)
    in Windows File Explorer, preventing traversal attacks.
    """
    service = get_media_service()
    success, opened_path, error = service.open_folder(payload.path or "")
    return OpenFolderResponse(success=success, opened_path=opened_path, error=error)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application Health & Disk Space",
)
async def health_check_endpoint() -> HealthResponse:
    """Returns application status, version, free disk space, and active task count."""
    service = get_media_service()
    download_dir = service.get_download_dir()
    download_dir.mkdir(parents=True, exist_ok=True)

    disk_info = {}
    try:
        usage = shutil.disk_usage(str(download_dir))
        disk_info = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "path": str(download_dir),
        }
    except Exception as e:
        logger.warning(f"Could not query disk space: {e}")

    manager = get_task_manager()
    active_count = len(manager.list_tasks(status="DOWNLOADING")) + len(manager.list_tasks(status="RUNNING"))

    return HealthResponse(
        status="ok",
        version="1.0.0",
        disk_space=disk_info,
        active_tasks=active_count,
    )
