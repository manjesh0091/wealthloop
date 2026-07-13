"""POST /api/analyze -- kicks off a graph run for a persona in the background."""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException

try:
    from backend.graph_runner import run_graph_leg
    from backend.mock_data.personas import get_persona
    from backend.mock_data.transactions import TRANSACTIONS_BY_PERSONA
    from backend.models import AnalyzeRequest, AnalyzeResponse
    from backend.session_store import create_session
except ImportError:  # allows running as `python analyze.py` from within backend/routers/
    from graph_runner import run_graph_leg
    from mock_data.personas import get_persona
    from mock_data.transactions import TRANSACTIONS_BY_PERSONA
    from models import AnalyzeRequest, AnalyzeResponse
    from session_store import create_session

router = APIRouter()


def _build_initial_state(request: AnalyzeRequest) -> dict:
    if request.persona_id:
        try:
            user_profile = dict(get_persona(request.persona_id))
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown persona_id: {request.persona_id!r}")
        transactions = request.transactions or TRANSACTIONS_BY_PERSONA.get(request.persona_id, [])
    elif request.user_profile:
        user_profile = dict(request.user_profile)
        transactions = request.transactions or []
    else:
        raise HTTPException(status_code=400, detail="Provide either persona_id or user_profile.")

    return {
        "user_profile": user_profile,
        "transactions": transactions,
        "expense_categories": {},
        "savings_rate": 0.0,
        "surplus_amount": 0.0,
        "emergency_fund_status": "",
        "relevant_schemes": [],
        "recommended_allocation": {},
        "suitability_flags": [],
        "compliance_explanation": None,
        "revision_round": 0,
        "rejection_reason": None,
        "approval_status": "pending",
        "final_plan": None,
    }


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    initial_state = _build_initial_state(request)

    session_id = str(uuid.uuid4())
    create_session(session_id)

    # Fire-and-forget: the graph runs in the background, pushing events onto
    # this session's queue. The response returns immediately, before the
    # graph has done any work.
    asyncio.create_task(run_graph_leg(session_id, initial_state))

    return AnalyzeResponse(session_id=session_id)
