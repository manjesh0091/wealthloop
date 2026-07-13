"""LangGraph graph definition wiring the WealthLoop agents together."""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

try:
    from backend.state import FinanceState
    from backend.agents.ingestion_agent import ingestion
    from backend.agents.categorization_agent import categorization
    from backend.agents.health_assessment_agent import health_assessment
    from backend.agents.rag_agent import rag_retrieval
    from backend.agents.recommendation_agent import recommendation
    from backend.agents.compliance_agent import compliance_guardrail
    from backend.agents.approval_gate import approval_gate
    from backend.agents.execution_agent import execution
except ImportError:  # allows running as `python graph.py` from within backend/
    from state import FinanceState
    from agents.ingestion_agent import ingestion
    from agents.categorization_agent import categorization
    from agents.health_assessment_agent import health_assessment
    from agents.rag_agent import rag_retrieval
    from agents.recommendation_agent import recommendation
    from agents.compliance_agent import compliance_guardrail
    from agents.approval_gate import approval_gate
    from agents.execution_agent import execution


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def route_after_compliance(state: FinanceState) -> Literal["recommendation", "approval_gate"]:
    # revision_round was already bumped by compliance_guardrail on this pass,
    # so "<= 2" here is equivalent to "revision_round < 2" pre-increment,
    # i.e. at most two automatic revision loops before forcing human review.
    if state.get("suitability_flags") and state.get("revision_round", 0) <= 2:
        return "recommendation"
    return "approval_gate"


def route_after_approval(state: FinanceState) -> Literal["execution", "recommendation"]:
    if state.get("approval_status") == "approved":
        return "execution"
    # "rejected" (and any other non-approved status) loops back to
    # recommendation, carrying rejection_reason along in state.
    return "recommendation"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

graph_builder = StateGraph(FinanceState)

graph_builder.add_node("ingestion", ingestion)
graph_builder.add_node("categorization", categorization)
graph_builder.add_node("health_assessment", health_assessment)
graph_builder.add_node("rag_retrieval", rag_retrieval)
graph_builder.add_node("recommendation", recommendation)
graph_builder.add_node("compliance_guardrail", compliance_guardrail)
graph_builder.add_node("approval_gate", approval_gate)
graph_builder.add_node("execution", execution)

graph_builder.add_edge(START, "ingestion")
graph_builder.add_edge("ingestion", "categorization")
graph_builder.add_edge("categorization", "health_assessment")
graph_builder.add_edge("health_assessment", "rag_retrieval")
graph_builder.add_edge("rag_retrieval", "recommendation")
graph_builder.add_edge("recommendation", "compliance_guardrail")

graph_builder.add_conditional_edges(
    "compliance_guardrail",
    route_after_compliance,
    {"recommendation": "recommendation", "approval_gate": "approval_gate"},
)

graph_builder.add_conditional_edges(
    "approval_gate",
    route_after_approval,
    {"execution": "execution", "recommendation": "recommendation"},
)

graph_builder.add_edge("execution", END)

checkpointer = MemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer)


def get_config(thread_id: str) -> dict:
    """Per-session config so independent runs don't share checkpoint state."""
    return {"configurable": {"thread_id": thread_id}}


if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
