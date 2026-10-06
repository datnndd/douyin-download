# -*- coding: utf-8 -*-
"""
src/web/services/media_service.py
Service for scanning downloaded media, providing HTTP 206 range streaming,
file downloads, and desktop directory opening bridge.
"""

import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from fastapi import HTTPException, Response
from fastapi.responses import FileResponse

from src.web.core.config import ConfigManager
from src.web.core.schemas import MediaItem, MediaListResponse

logger = logging.getLogger("DouyinWeb.MediaService")


class MediaService:
    """Service managing media library discovery, streaming, and desktop integration."""

    _instance: Optional["MediaService"] = None

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager.get_instance()

    @classmethod
    def get_instance(cls) -> "MediaService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_download_dir(self) -> Path:
        """Returns the current resolved download root directory."""
        settings = self.config_manager.get_settings()
        raw_path = settings.path or "./Downloaded/"
        return Path(raw_path).resolve()

    def resolve_safe_path(self, relative_path: str, download_dir: Optional[Path] = None) -> Path:
        """
        Resolves relative_path within download_dir, strictly preventing directory traversal attacks.
        Raises HTTPException(400) if a traversal attempt is detected.
        """
        root = (download_dir or self.get_download_dir()).resolve()
        decoded = unquote(relative_path).strip()

        # Check for path traversal indicators
        normalized = decoded.replace("\\", "/")
        if ".." in normalized.split("/"):
            raise HTTPException(status_code=400, detail="Invalid path traversal detected.")

        candidate = (root / decoded).resolve()

        try:
            candidate.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Path traversal outside download directory.")

        return candidate

    def scan_media(self, download_dir: Optional[Path] = None) -> List[MediaItem]:
        """Recursively scans download directory for downloaded videos, audio, images, and JSON metadata."""
        root = (download_dir or self.get_download_dir()).resolve()
        if not root.exists() or not root.is_dir():
            return []

        media_items: List[MediaItem] = []
        valid_extensions = {
            ".mp4": "video",
            ".mkv": "video",
            ".webm": "video",
            ".mov": "video",
            ".mp3": "audio",
            ".m4a": "audio",
            ".wav": "audio",
            ".jpg": "image",
            ".jpeg": "image",
            ".png": "image",
            ".webp": "image",
            ".json": "json",
        }

        for p in root.rglob("*"):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext not in valid_extensions:
                continue

            try:
                rel_path = p.relative_to(root).as_posix()
                stat = p.stat()
                media_type = valid_extensions[ext]
                created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                item_id = f"{media_type}_{p.stem}"

                encoded_path = quote(rel_path)
                preview_url = f"/api/media/stream/{encoded_path}"
                download_url = f"/api/media/download/{encoded_path}"

                media_items.append(
                    MediaItem(
                        id=item_id,
                        filename=p.name,
                        relative_path=rel_path,
                        media_type=media_type,
                        file_size=stat.st_size,
                        created_at=created_at,
                        preview_url=preview_url,
                        download_url=download_url,
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping file {p} during media scan: {e}")

        # Sort newest first
        media_items.sort(key=lambda x: x.created_at, reverse=True)
        return media_items

    def stream_media_range(
        self, relative_path: str, range_header: Optional[str] = None, download_dir: Optional[Path] = None
    ) -> Response:
        """
        Handles HTTP 206 Partial Content range requests for video/audio playback.
        Falls back to full 200 OK or 416 Range Not Satisfiable as appropriate.
        """
        safe_path = self.resolve_safe_path(relative_path, download_dir)
        if not safe_path.exists() or not safe_path.is_file():
            raise HTTPException(status_code=404, detail="Requested media file not found.")

        file_size = safe_path.stat().st_size
        content_type, _ = mimetypes.guess_type(str(safe_path))
        if not content_type:
            content_type = "video/mp4" if safe_path.suffix.lower() == ".mp4" else "application/octet-stream"

        if not range_header or not range_header.strip():
            return FileResponse(
                path=str(safe_path),
                media_type=content_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(file_size),
                },
            )

        # Parse Range header: Range: bytes=start-end
        match = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
        if not match:
            # Invalid range syntax: fall back to full file (200 OK)
            return FileResponse(
                path=str(safe_path),
                media_type=content_type,
                headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
            )

        start_str, end_str = match.groups()

        if not start_str and not end_str:
            return FileResponse(
                path=str(safe_path),
                media_type=content_type,
                headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
            )

        if not start_str:
            # Suffix range: bytes=-500
            length = int(end_str)
            start = max(0, file_size - length)
            end = file_size - 1
        elif not end_str:
            # Prefix range: bytes=500-
            start = int(start_str)
            end = file_size - 1
        else:
            start = int(start_str)
            end = int(end_str)

        if start >= file_size or start > end:
            return Response(
                status_code=416,
                headers={
                    "Content-Range": f"bytes */{file_size}",
                    "Accept-Ranges": "bytes",
                },
            )

        end = min(end, file_size - 1)
        chunk_length = end - start + 1

        with open(safe_path, "rb") as f:
            f.seek(start)
            data = f.read(chunk_length)

        return Response(
            content=data,
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_length),
            },
        )

    def download_media(
        self, relative_path: str, download_dir: Optional[Path] = None
    ) -> FileResponse:
        """Returns media file as an attachment download."""
        safe_path = self.resolve_safe_path(relative_path, download_dir)
        if not safe_path.exists() or not safe_path.is_file():
            raise HTTPException(status_code=404, detail="Requested media file not found.")

        content_type, _ = mimetypes.guess_type(str(safe_path))
        if not content_type:
            content_type = "application/octet-stream"

        return FileResponse(
            path=str(safe_path),
            media_type=content_type,
            filename=safe_path.name,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_path.name}"',
                "Content-Length": str(safe_path.stat().st_size),
            },
        )

    def open_folder(
        self, subpath: Optional[str] = "", download_dir: Optional[Path] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Desktop integration bridge: Opens the download directory in Windows File Explorer.
        Safely validates subpath and prevents directory traversal.
        """
        root = (download_dir or self.get_download_dir()).resolve()
        target = root

        if subpath and subpath.strip():
            target = self.resolve_safe_path(subpath, root)

        target.mkdir(parents=True, exist_ok=True)
        target_str = str(target)

        try:
            if hasattr(os, "startfile"):
                os.startfile(target_str)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target_str])
            else:
                subprocess.Popen(["xdg-open", target_str])
            return True, target_str, None
        except Exception as e:
            logger.warning(f"Could not open directory via system opener: {e}")
            return True, target_str, str(e)
