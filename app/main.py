"""FastAPI entry point for the OpenCode Token Dashboard.

Initiates the application, registers the API router, validates the
database on startup, and provides a ``__main__`` block for ``uvicorn``.
"""

from __future__ import annotations

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
