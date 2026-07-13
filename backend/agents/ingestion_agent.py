"""Ingests raw financial data into graph state.

This is the single place where `user_profile["monthly_income"]` (raw input
data — an int for a regular salary, or a list[int] of recent months for
irregular/freelance income) gets normalized into two derived fields that
every downstream agent should read instead of the raw field:

- average_monthly_income: float
- income_volatility: "stable" | "variable"
"""

try:
    from backend.state import FinanceState
except ImportError:  # allows running as `python ingestion_agent.py` from within backend/agents/
    from state import FinanceState

INCOME_VOLATILITY_SWING_THRESHOLD_PCT = 15.0


def _normalize_income(user_profile: dict) -> None:
    """Mutates user_profile in place, adding average_monthly_income and income_volatility."""
    monthly_income = user_profile.get("monthly_income")

    if isinstance(monthly_income, list):
        values = monthly_income
        average = sum(values) / len(values)
        swing_pct = ((max(values) - min(values)) / average * 100) if average else 0.0
        volatility = "variable" if swing_pct > INCOME_VOLATILITY_SWING_THRESHOLD_PCT else "stable"
    else:
        average = float(monthly_income) if monthly_income is not None else 0.0
        volatility = "stable"

    user_profile["average_monthly_income"] = average
    user_profile["income_volatility"] = volatility


def ingestion(state: FinanceState) -> FinanceState:
    print("Node: ingestion")
    user_profile = state.get("user_profile") or {}
    _normalize_income(user_profile)
    state["user_profile"] = user_profile
    return state


if __name__ == "__main__":
    import copy

    try:
        from backend.mock_data.personas import PERSONAS
    except ImportError:
        from mock_data.personas import PERSONAS

    for persona in PERSONAS:
        state: FinanceState = {
            "user_profile": copy.deepcopy(persona),
            "transactions": [],
            "expense_categories": {},
            "savings_rate": 0.0,
            "surplus_amount": 0.0,
            "emergency_fund_status": "",
            "relevant_schemes": [],
            "recommended_allocation": {},
            "suitability_flags": [],
            "revision_round": 0,
            "rejection_reason": None,
            "approval_status": "pending",
            "final_plan": None,
        }
        result = ingestion(state)
        print(f"\n=== {persona['name']} ({persona['id']}) ===")
        print(result["user_profile"])
