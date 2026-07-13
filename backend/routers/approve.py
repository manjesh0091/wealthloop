"""POST /api/approve/{session_id} -- resumes an interrupted graph run."""

import asyncio

from fastapi import APIRouter, HTTPException
from langgraph.types import Command

try:
    from backend.graph_runner import run_graph_leg
    from backend.models import ApproveRequest, ApproveResponse
    from backend.session_store import get_session
except ImportError:  # allows running as `python approve.py` from within backend/routers/
    from graph_runner import run_graph_leg
    from models import ApproveRequest, ApproveResponse
    from session_store import get_session

router = APIRouter()


@router.post("/api/approve/{session_id}", response_model=ApproveResponse)
async def approve(session_id: str, request: ApproveRequest) -> ApproveResponse:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id!r}")
    if not session.awaiting_approval:
        raise HTTPException(status_code=409, detail="Session is not currently awaiting approval.")

    session.awaiting_approval = False

    resume_payload = {"approval_status": request.approval_status}
    if request.rejection_reason is not None:
        resume_payload["rejection_reason"] = request.rejection_reason

    # Fire-and-forget, same as /api/analyze: this leg continues pushing
    # events onto the SAME session queue that /api/stream/{session_id} is
    # already draining, so the ongoing SSE connection just picks it up.
    asyncio.create_task(run_graph_leg(session_id, Command(resume=resume_payload)))

    return ApproveResponse(status="resumed")
