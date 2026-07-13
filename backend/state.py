from typing import TypedDict, Literal, Optional


class FinanceState(TypedDict):
    # user_profile is intentionally untyped (raw persona input, e.g.
    # monthly_income: int | list[int]). After ingestion_agent runs, it is
    # guaranteed to also contain two derived fields that every downstream
    # agent should read instead of the raw monthly_income:
    #   - average_monthly_income: float
    #   - income_volatility: "stable" | "variable"
    user_profile: dict
    transactions: list[dict]
    expense_categories: dict
    savings_rate: float
    surplus_amount: float
    emergency_fund_status: str
    relevant_schemes: list[dict]
    recommended_allocation: dict
    suitability_flags: list[str]
    # Set by compliance_agent only when suitability_flags is non-empty: a
    # human-readable, LLM-generated explanation referencing the specific
    # numbers that triggered the flag(s). None when suitability_flags is [].
    compliance_explanation: Optional[str]
    revision_round: int
    rejection_reason: Optional[str]
    approval_status: Literal["pending", "approved", "rejected", "revise"]
    final_plan: Optional[dict]
