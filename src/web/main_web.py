# -*- coding: utf-8 -*-
"""
src/web/main_web.py
Main entrypoint and FastAPI application factory for Douyin Web Downloader.
Integrates REST APIs, streaming telemetry, static asset mounts, and SPA fallback.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.web.api.router import api_router
from src.web.api.stream import router as ws_stream_router
from src.web.core.config import ConfigManager
from src.web.services.task_manager import TaskManager

logger = logging.getLogger("DouyinWeb.App")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: manages background thread pools and config managers."""
    logger.info("Initializing Douyin Web Downloader application...")
    ConfigManager.get_instance()
    task_manager = TaskManager.get_instance()
    # Register current running event loop with TaskManager
    task_manager._loop = asyncio.get_running_loop()
    yield
    logger.info("Shutting down Douyin Web Downloader application...")
    task_manager.shutdown(wait=False)


app = FastAPI(
    title="Douyin Web Downloader",
    description="Modern web application for downloading Douyin videos, audios, covers, and metadata.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local Vite development and cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST APIs under /api
app.include_router(api_router)

# Mount WebSocket endpoint /ws/tasks
app.include_router(ws_stream_router)

# -----------------------------------------------------------------------------
# Static Mount and SPA Fallback (Milestone 3 & 4)
# -----------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Exclude /api and /ws from SPA catch-all
        if full_path.startswith("api") or full_path.startswith("ws"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        file_candidate = FRONTEND_DIST / full_path
        if file_candidate.is_file() and file_candidate.exists():
            return FileResponse(file_candidate)

        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def root_index():
        return {
            "name": "Douyin Web Downloader API",
            "version": "1.0.0",
            "status": "ready",
            "docs": "/docs",
        }
