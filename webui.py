# -*- coding: utf-8 -*-
"""
webui.py
Unified single-command launcher for Douyin Web Downloader.
Launches the FastAPI backend server, serves the built React 19 SPA frontend,
and opens the default web browser automatically.
"""

import argparse
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DouyinWeb.Launcher")


def open_browser(url: str, delay_seconds: float = 1.2):
    """Wait briefly for server to bind then launch the browser."""
    def _open():
        time.sleep(delay_seconds)
        try:
            logger.info("Opening web browser at %s ...", url)
            webbrowser.open_new_tab(url)
        except Exception as e:
            logger.warning("Failed to auto-open browser: %s", e)

    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    parser = argparse.ArgumentParser(
        description="Douyin Web Downloader - Modern Editorial Edition Launcher"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn hot reloading for development",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open browser on startup",
    )

    args = parser.parse_args()

    # Verify frontend build exists
    dist_path = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if not dist_path.exists():
        logger.warning(
            "Frontend bundle not detected at '%s'. Run 'npm run build' in 'frontend/' to build UI.",
            dist_path,
        )

    server_url = f"http://{args.host}:{args.port}"

    print("=" * 64)
    print("  抖音视频/音频/图集 Web 下载器 (Douyin Web Downloader)")
    print("  Editorial Warm Theme Edition")
    print(f"  服务启动中: {server_url}")
    print("  按 Ctrl+C 停止服务")
    print("=" * 64)

    if not args.no_browser:
        open_browser(server_url)

    try:
        import uvicorn

        uvicorn.run(
            "src.web.main_web:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C).")
    except Exception as e:
        logger.error("Error starting server: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
