"""FastAPI app entrypoint."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

try:
    from backend.routers import analyze, approve, stream
except ImportError:  # allows running as `python main.py` from within backend/
    from routers import analyze, approve, stream

app = FastAPI(title="WealthLoop")

# API routers must be registered before the static mount below -- Starlette
# matches routes in registration order, and a "/" mount would otherwise
# swallow every request (including /api/*) before the routers get a look.
app.include_router(analyze.router)
app.include_router(stream.router)
app.include_router(approve.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
