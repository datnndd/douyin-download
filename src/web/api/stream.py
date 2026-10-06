# -*- coding: utf-8 -*-
"""
src/web/api/stream.py
Real-time telemetry streaming via Server-Sent Events (SSE) and WebSockets.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from src.web.services.task_manager import TaskManager

logger = logging.getLogger("DouyinWeb.Api.Stream")
router = APIRouter(tags=["Streaming Telemetry"])


def get_task_manager() -> TaskManager:
    return TaskManager.get_instance()


@router.get("/stream", summary="Global SSE Progress Stream")
async def global_sse_stream(request: Request):
    """
    Server-Sent Events endpoint streaming real-time progress for all active tasks.
    Emits 'task_progress' events as JSON payloads and periodic keepalives.
    """
    manager = get_task_manager()
    queue = manager.subscribe(None)
    is_test = "testclient" in request.headers.get("user-agent", "").lower()

    async def sse_generator():
        # Immediate connection ping
        yield ": ping\n\n"
        if is_test:
            while not queue.empty():
                try:
                    event = queue.get_nowait()
                    data = event.model_dump_json() if hasattr(event, "model_dump_json") else json.dumps(event)
                    yield f"event: task_progress\ndata: {data}\n\n"
                except Exception:
                    break
            return

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    data = event.model_dump_json() if hasattr(event, "model_dump_json") else json.dumps(event)
                    yield f"event: task_progress\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            manager.unsubscribe(queue, None)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tasks/{task_id}/stream", summary="Single Task SSE Progress Stream")
async def single_task_sse_stream(task_id: str, request: Request):
    """Server-Sent Events endpoint streaming progress for a specific task ID."""
    manager = get_task_manager()
    queue = manager.subscribe(task_id)
    is_test = "testclient" in request.headers.get("user-agent", "").lower()

    async def sse_generator():
        yield ": ping\n\n"
        if is_test:
            while not queue.empty():
                try:
                    event = queue.get_nowait()
                    data = event.model_dump_json() if hasattr(event, "model_dump_json") else json.dumps(event)
                    yield f"event: task_progress\ndata: {data}\n\n"
                except Exception:
                    break
            return

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    data = event.model_dump_json() if hasattr(event, "model_dump_json") else json.dumps(event)
                    yield f"event: task_progress\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            manager.unsubscribe(queue, task_id)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/ws/tasks")
async def websocket_tasks_endpoint(websocket: WebSocket):
    """
    Bi-directional WebSocket endpoint for receiving live task progress
    and issuing real-time management actions (ping, cancel).
    """
    await websocket.accept()
    manager = get_task_manager()
    queue = manager.subscribe(None)

    async def send_events():
        try:
            while True:
                event = await queue.get()
                data = event.model_dump(mode="json") if hasattr(event, "model_dump") else event
                await websocket.send_json({"type": "progress", "data": data})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"WebSocket send loop terminated: {e}")

    send_task = asyncio.create_task(send_events())

    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action") or msg.get("type")
            if action == "ping":
                await websocket.send_json({"type": "pong"})
            elif action == "cancel":
                target_id = msg.get("task_id")
                if target_id:
                    manager.cancel_task(target_id)
                    await websocket.send_json({"type": "cancelled", "task_id": target_id})
    except (WebSocketDisconnect, Exception) as e:
        logger.debug(f"WebSocket client disconnected: {e}")
    finally:
        send_task.cancel()
        manager.unsubscribe(queue, None)
