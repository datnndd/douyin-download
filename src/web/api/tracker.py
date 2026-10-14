# -*- coding: utf-8 -*-
"""
src/web/api/tracker.py
FastAPI router for Creator Tracker endpoints:
- Creator enrollment and listing
- Change detection (filtering pinned videos)
- 1-Click Update dispatching
- Summary metrics and badge counter
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException, status

from src.web.core.schemas import (
    CheckAllResponse,
    TaskResponse,
    TrackCreatorRequest,
    TrackedCreatorResponse,
    TrackerStatsResponse,
)
from src.web.services.tracker_service import TrackerService

logger = logging.getLogger("DouyinWeb.Api.Tracker")
router = APIRouter(prefix="/tracker", tags=["Creator Tracker"])


def get_tracker_service() -> TrackerService:
    return TrackerService.get_instance()


@router.get(
    "/creators",
    response_model=List[TrackedCreatorResponse],
    summary="List Tracked Creators",
)
async def list_creators_endpoint() -> List[TrackedCreatorResponse]:
    """List all tracked Douyin creators, sorted by pending updates first."""
    service = get_tracker_service()
    return service.list_creators()


@router.post(
    "/creators",
    response_model=TrackedCreatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Track a Creator",
)
async def track_creator_endpoint(payload: TrackCreatorRequest) -> TrackedCreatorResponse:
    """
    Enroll a new creator into tracking.
    Resolves the creator profile and establishes the baseline latest video ID.
    """
    service = get_tracker_service()
    try:
        creator = service.track_creator(
            url=payload.url,
            sec_uid=payload.sec_uid,
            nickname=payload.nickname,
            avatar_thumb=payload.avatar_thumb,
            unique_id=payload.unique_id,
        )
        return creator
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to track creator: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to track creator: {str(e)}")


@router.get(
    "/creators/{sec_uid}",
    response_model=TrackedCreatorResponse,
    summary="Get Tracked Creator Details",
)
async def get_creator_endpoint(sec_uid: str) -> TrackedCreatorResponse:
    """Get details of a single tracked creator along with pending new videos."""
    service = get_tracker_service()
    creator = service.get_creator(sec_uid, include_pending=True)
    if not creator:
        raise HTTPException(status_code=404, detail=f"Creator {sec_uid} not found.")
    return creator


@router.delete(
    "/creators/{sec_uid}",
    status_code=status.HTTP_200_OK,
    summary="Untrack Creator",
)
async def untrack_creator_endpoint(sec_uid: str):
    """Remove a creator and all associated tracking history."""
    service = get_tracker_service()
    success = service.untrack_creator(sec_uid)
    if not success:
        raise HTTPException(status_code=404, detail=f"Creator {sec_uid} not found.")
    return {"success": True, "message": f"Creator {sec_uid} untracked successfully"}


@router.post(
    "/creators/{sec_uid}/check",
    response_model=TrackedCreatorResponse,
    summary="Check Updates for One Creator",
)
async def check_creator_updates_endpoint(sec_uid: str) -> TrackedCreatorResponse:
    """
    Check for newly uploaded videos for a specific creator.
    Filters pinned videos and stops immediately upon reaching previously seen IDs.
    """
    service = get_tracker_service()
    try:
        updated_creator, _ = service.check_creator_updates(sec_uid)
        return updated_creator
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error checking updates for {sec_uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")


@router.post(
    "/creators/check-all",
    response_model=CheckAllResponse,
    summary="Check Updates for All Creators",
)
async def check_all_creators_endpoint() -> CheckAllResponse:
    """Check for new uploads across all enrolled creators with polite rate-limiting jitter."""
    service = get_tracker_service()
    try:
        res = service.check_all_creators()
        return res
    except Exception as e:
        logger.error(f"Error checking all creators: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Check-all failed: {str(e)}")


@router.post(
    "/creators/{sec_uid}/update",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="1-Click Update for Creator",
)
async def update_creator_endpoint(sec_uid: str) -> TaskResponse:
    """
    1-Click Update:
    Downloads ONLY the newly published videos detected since the last baseline.
    Enqueues a background download task and marks them downloaded upon completion.
    """
    service = get_tracker_service()
    try:
        task = service.start_one_click_update(sec_uid)
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"1-Click update failed for {sec_uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.post(
    "/update-all",
    response_model=List[TaskResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="1-Click Update for All Creators",
)
async def update_all_creators_endpoint() -> List[TaskResponse]:
    """Trigger 1-Click updates for all creators that currently have pending videos."""
    service = get_tracker_service()
    try:
        tasks = service.update_all_creators()
        return tasks
    except Exception as e:
        logger.error(f"Update-all failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update-all failed: {str(e)}")


@router.get(
    "/stats",
    response_model=TrackerStatsResponse,
    summary="Get Tracker Summary Stats",
)
async def get_tracker_stats_endpoint() -> TrackerStatsResponse:
    """Return summary statistics for UI badge counter (total creators & total pending)."""
    service = get_tracker_service()
    return service.get_summary_stats()
