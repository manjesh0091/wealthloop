"""Assesses overall financial health.

Pure calculation node — no LLM call, deterministic. Reads
user_profile["average_monthly_income"] / user_profile["income_volatility"]
(set by ingestion_agent — never the raw user_profile["monthly_income"])
plus state["expense_categories"] to compute savings_rate, surplus_amount,
and emergency_fund_status.
"""

try:
    from backend.state import FinanceState
except ImportError:  # allows running as `python health_assessment_agent.py` from within backend/agents/
    from state import FinanceState

STABLE_EMERGENCY_FUND_TARGET_MONTHS = 3
VARIABLE_EMERGENCY_FUND_TARGET_MONTHS = 6

# Placeholder assumption: mock data doesn't track an actual existing
# emergency fund balance, so we approximate one as 0.5x the current
# monthly surplus (kept under 1x so no persona appears "already fully
# funded" before the recommendation agent runs). This is a stand-in
# until real savings-balance data is available and should be replaced then.
ASSUMED_EXISTING_FUND_AS_MULTIPLE_OF_SURPLUS = 0.5


def _total_expenses(expense_categories: dict) -> float:
    return sum(stats.get("total", 0) for stats in expense_categories.values())


def assess_health(user_profile: dict, expense_categories: dict) -> dict:
    """Core logic: computes savings_rate, surplus_amount, emergency_fund_status."""
    income = user_profile.get("average_monthly_income", 0.0)
    volatility = user_profile.get("income_volatility", "stable")
    total_expenses = _total_expenses(expense_categories)

    surplus_amount = income - total_expenses
    savings_rate = (surplus_amount / income * 100) if income else 0.0

    target_months = (
        VARIABLE_EMERGENCY_FUND_TARGET_MONTHS
        if volatility == "variable"
        else STABLE_EMERGENCY_FUND_TARGET_MONTHS
    )
    assumed_existing_fund = ASSUMED_EXISTING_FUND_AS_MULTIPLE_OF_SURPLUS * surplus_amount
    months_covered = (assumed_existing_fund / total_expenses) if total_expenses else 0.0
    emergency_fund_status = f"{months_covered:.1f} / {target_months} months"

    return {
        "savings_rate": round(savings_rate, 1),
        "surplus_amount": round(surplus_amount, 2),
        "emergency_fund_status": emergency_fund_status,
    }


def health_assessment(state: FinanceState) -> FinanceState:
    print("Node: health_assessment")
    user_profile = state.get("user_profile") or {}
    expense_categories = state.get("expense_categories") or {}

    result = assess_health(user_profile, expense_categories)
    state["savings_rate"] = result["savings_rate"]
    state["surplus_amount"] = result["surplus_amount"]
    state["emergency_fund_status"] = result["emergency_fund_status"]
    return state


if __name__ == "__main__":
    try:
        from backend.mock_data.personas import PERSONAS
        from backend.mock_data.transactions import TRANSACTIONS_BY_PERSONA
        from backend.agents.ingestion_agent import ingestion
        from backend.agents.categorization_agent import categorize_transactions
    except ImportError:
        from mock_data.personas import PERSONAS
        from mock_data.transactions import TRANSACTIONS_BY_PERSONA
        from ingestion_agent import ingestion
        from categorization_agent import categorize_transactions

    import copy

    for persona in PERSONAS:
        state: FinanceState = {
            "user_profile": copy.deepcopy(persona),
            "transactions": TRANSACTIONS_BY_PERSONA[persona["id"]],
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

        state = ingestion(state)
        _, expense_categories, _ = categorize_transactions(state["transactions"])
        state["expense_categories"] = expense_categories

        state = health_assessment(state)

        print(f"\n=== {persona['name']} ({persona['id']}) ===")
        print(f"average_monthly_income: {state['user_profile']['average_monthly_income']:.2f}")
        print(f"income_volatility: {state['user_profile']['income_volatility']}")
        print(f"savings_rate: {state['savings_rate']}%")
        print(f"surplus_amount: Rs. {state['surplus_amount']:,.2f}")
        print(f"emergency_fund_status: {state['emergency_fund_status']}")
