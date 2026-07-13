"""Human-in-the-loop approval gate node.

Pauses execution via LangGraph's interrupt() and waits for a human decision
before the graph is allowed to route to execution. The interrupt payload
gives the human everything needed to decide: the full recommended_allocation
plus a quick summary (savings_rate, surplus_amount, scheme names/percentages).
"""

from langgraph.types import interrupt

try:
    from backend.state import FinanceState
except ImportError:  # allows running as `python approval_gate.py` from within backend/agents/
    from state import FinanceState

REJECTION_REASONS = ["Too aggressive", "Want more liquidity", "Other"]


def _build_summary(state: FinanceState) -> dict:
    recommended_allocation = state.get("recommended_allocation") or {}
    return {
        "savings_rate_pct": state.get("savings_rate"),
        "surplus_amount": state.get("surplus_amount"),
        "emergency_fund_status": state.get("emergency_fund_status"),
        "schemes": [
            {"scheme": scheme, "percent": entry.get("percent"), "amount": entry.get("amount")}
            for scheme, entry in recommended_allocation.items()
        ],
    }


def approval_gate(state: FinanceState) -> FinanceState:
    print("Node: approval_gate")
    decision = interrupt(
        {
            "message": "Human approval required.",
            "recommended_allocation": state.get("recommended_allocation"),
            "summary": _build_summary(state),
            "valid_rejection_reasons": REJECTION_REASONS,
        }
    )

    approval_status = decision.get("approval_status", "pending")
    state["approval_status"] = approval_status

    if approval_status == "rejected":
        rejection_reason = decision.get("rejection_reason")
        if rejection_reason not in REJECTION_REASONS:
            print(
                f"  [approval_gate] WARNING: rejection_reason {rejection_reason!r} not in the "
                f"fixed set {REJECTION_REASONS}; defaulting to 'Other'."
            )
            rejection_reason = "Other"
        state["rejection_reason"] = rejection_reason
    else:
        state["rejection_reason"] = None

    return state
