"""GET /api/stream/{session_id} -- SSE stream of node-completion events.

Pure consumer: this endpoint never runs the graph itself, it just drains the
session's queue (fed by graph_runner.run_graph_leg, kicked off from
/api/analyze and /api/approve) and forwards each item as an SSE event. When
approval_gate interrupts, the queue simply has nothing new to give until
/api/approve starts the next leg -- the `await queue.get()` below just
blocks, keeping the connection open without closing it.
"""

import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

try:
    from backend.session_store import get_session
except ImportError:  # allows running as `python stream.py` from within backend/routers/
    from session_store import get_session

router = APIRouter()


@router.get("/api/stream/{session_id}")
async def stream(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id!r}")

    async def event_generator():
        while True:
            event = await session.queue.get()
            yield {"event": "message", "data": json.dumps(event, default=str)}
            if event.get("node") == "done":
                break

    return EventSourceResponse(event_generator())
