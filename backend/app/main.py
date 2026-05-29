"""FastAPI application entry point.

For now this wires up the database and a health check. API routes and PWA static
serving are added in later build phases.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.auth import require_auth
from app.api.routes import router as api_router
from app.db import init_db

load_dotenv()

# Built PWA lives at <repo>/frontend/dist after `npm run build`.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Start the email poller only when credentials are configured, so local dev and
    # tests don't attempt an IMAP connection.
    if os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"):
        from app.poller import start_scheduler

        start_scheduler()
    yield


app = FastAPI(title="MoneyMoney", lifespan=lifespan)
app.include_router(api_router, dependencies=[Depends(require_auth)])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the built PWA same-origin (so /api works without CORS). Mounted last so it
# doesn't shadow the API routes. Only mounted if a build exists, keeping tests/dev clean.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
