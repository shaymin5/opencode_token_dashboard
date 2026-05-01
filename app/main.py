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
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

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


if __name__ == "__main__":
    port = _resolve_port()
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
