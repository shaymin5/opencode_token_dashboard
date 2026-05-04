"""FastAPI entry point for the OpenCode Token Dashboard.

Initiates the application, registers the API router, validates the
database on startup, and provides a ``__main__`` block for ``uvicorn``.

The server port is determined by (in order of precedence):

1. ``--port`` CLI argument
2. ``PORT`` environment variable
3. Default ``20230``
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import threading
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.db import get_db_path
from app.routes import router

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate DB on startup; log on shutdown."""
    db_path = get_db_path()
    print(f"[startup] DB path: {db_path}")
    if not os.path.isfile(db_path):
        print(f"[startup] WARNING — database file not found: {db_path}")
    else:
        print("[startup] OK — database file exists")
    yield
    print("[shutdown] OpenCode Token Dashboard is shutting down")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="OpenCode Token Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _resolve_port() -> int:
    """Resolve server port: CLI arg > env var > default."""
    parser = argparse.ArgumentParser(description="OpenCode Token Dashboard")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (overrides PORT env var)",
    )
    args, _ = parser.parse_known_args()
    if args.port is not None:
        return args.port
    return int(os.environ.get("PORT", "20230"))


def _is_wsl() -> bool:
    """Detect if running under Windows Subsystem for Linux."""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version") as f:
            content = f.read().lower()
            return "microsoft" in content or "wsl" in content
    except FileNotFoundError:
        return False


def _open_browser(port: int) -> None:
    """Open the dashboard URL in the default browser after a short delay."""
    url = f"http://127.0.0.1:{port}"
    print(f"[startup] Opening browser at {url}")
    if _is_wsl():
        subprocess.run(["cmd.exe", "/c", "start", url], check=False)
    else:
        webbrowser.open(url)


def main() -> None:
    """Entry point for ``uv run dashboard`` and ``python -m app.main``."""
    port = _resolve_port()
    threading.Timer(1.5, _open_browser, args=[port]).start()
    print(f"[startup] Starting server on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
