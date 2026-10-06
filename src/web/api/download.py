# -*- coding: utf-8 -*-
"""
src/web/api/download.py
Endpoints for submitting download jobs and monitoring task state machine.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status

from src.web.core.schemas import DownloadRequest, TaskDetailResponse, TaskResponse
from src.web.services.douyin_service import DouyinService
from src.web.services.task_manager import TaskManager

logger = logging.getLogger("DouyinWeb.Api.Download")
router = APIRouter(tags=["Download & Tasks"])


def get_task_manager() -> TaskManager:
    return TaskManager.get_instance()


def get_douyin_service() -> DouyinService:
    from src.web.api.parse import get_douyin_service as _get_ds
    return _get_ds()


@router.post(
    "/download",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Download Task",
)
async def submit_download_endpoint(payload: DownloadRequest) -> TaskResponse:
    """
    Submits a new download job to the background worker pool.
    Returns 202 Accepted with a unique task_id for tracking.
    """
    if not payload.url or not payload.url.strip():
        raise HTTPException(status_code=422, detail="Download URL cannot be empty.")

    manager = get_task_manager()
    service = get_douyin_service()

    try:
        task_resp = manager.submit_task(payload, douyin_service=service)
        return task_resp
    except Exception as e:
        logger.error(f"Failed to submit download task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task submission failed: {str(e)}")


@router.get(
    "/tasks",
    response_model=List[TaskDetailResponse],
    summary="List All Download Tasks",
)
async def list_tasks_endpoint() -> List[TaskDetailResponse]:
    """Retrieves all tracked download tasks ordered by creation time."""
    manager = get_task_manager()
    return manager.list_tasks()


@router.get(
    "/tasks/{task_id}",
    response_model=TaskDetailResponse,
    summary="Get Task Details & Progress",
)
async def get_task_detail_endpoint(task_id: str) -> TaskDetailResponse:
    """Retrieves current telemetry, worker slots, and execution state for a task."""
    manager = get_task_manager()
    record = manager.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return record


@router.post(
    "/tasks/{task_id}/cancel",
    summary="Cancel Download Task",
)
async def cancel_task_endpoint(task_id: str):
    """Cancels an active or pending task and halts all associated worker threads."""
    manager = get_task_manager()
    record = manager.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    manager.cancel_task(task_id)
    return {"success": True, "message": f"Task {task_id} cancelled successfully."}


@router.post(
    "/tasks/{task_id}/pause",
    summary="Pause Download Task",
)
async def pause_task_endpoint(task_id: str):
    """Pauses worker threads for an active task."""
    manager = get_task_manager()
    record = manager.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    manager.pause_task(task_id)
    return {"success": True, "message": f"Task {task_id} paused."}


@router.post(
    "/tasks/{task_id}/resume",
    summary="Resume Download Task",
)
async def resume_task_endpoint(task_id: str):
    """Resumes paused worker threads for a task."""
    manager = get_task_manager()
    record = manager.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

    manager.resume_task(task_id)
    return {"success": True, "message": f"Task {task_id} resumed."}
