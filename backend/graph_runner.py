"""Runs one leg of the graph (start-to-interrupt, or resume-to-interrupt/end)
and streams node completions into the session's queue.

A "leg" is one call to graph.astream(): it runs until either the graph
reaches an interrupt (approval_gate) or reaches END. /api/analyze kicks off
the first leg; /api/approve kicks off each subsequent leg after a resume.
Both push onto the same per-session queue, which /api/stream/{session_id}
just drains and forwards as SSE -- the streaming endpoint never runs the
graph itself.
"""

try:
    from backend.graph import get_config, graph
    from backend.session_store import get_session
except ImportError:  # allows running as `python graph_runner.py` from within backend/
    from graph import get_config, graph
    from session_store import get_session

# Keep each SSE event focused on what that node actually produced, instead
# of dumping the entire (large) state on every event.
NODE_OUTPUT_KEYS = {
    "ingestion": ["user_profile"],
    "categorization": ["expense_categories", "transactions"],
    "health_assessment": ["savings_rate", "surplus_amount", "emergency_fund_status"],
    "rag_retrieval": ["relevant_schemes"],
    "recommendation": ["recommended_allocation"],
    "compliance_guardrail": ["suitability_flags", "compliance_explanation", "revision_round"],
    "approval_gate": ["approval_status", "rejection_reason"],
    "execution": ["final_plan"],
}


def _relevant_slice(node_name: str, output: dict) -> dict:
    keys = NODE_OUTPUT_KEYS.get(node_name)
    if keys is None:
        return output
    return {key: output[key] for key in keys if key in output}


async def run_graph_leg(session_id: str, input_or_command) -> None:
    session = get_session(session_id)
    if session is None:
        return

    config = get_config(session_id)

    async for chunk in graph.astream(input_or_command, config=config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            interrupt_obj = chunk["__interrupt__"][0]
            session.awaiting_approval = True
            await session.queue.put(
                {
                    "node": "approval_gate",
                    "status": "awaiting_approval",
                    "payload": interrupt_obj.value,
                }
            )
            return  # this leg ends here; /api/approve starts the next one

        for node_name, output in chunk.items():
            await session.queue.put({"node": node_name, "output": _relevant_slice(node_name, output)})

    # Generator exhausted without hitting an interrupt -> graph reached END.
    session.done = True
    await session.queue.put({"node": "done"})
