"""Generates financial recommendations.

Core reasoning agent. Calls ChatGroq to propose an allocation of the user's
monthly surplus across ELSS, PPF, NPS, FD, and Emergency Fund, based on
user_profile["average_monthly_income"] / ["income_volatility"] (never raw
monthly_income, per ingestion_agent's contract), the health-assessment
numbers, and the RAG-retrieved reference chunks.

Note: incrementing revision_round is compliance_guardrail's job, not this
agent's — this node just produces a fresh allocation each time it runs,
whether it's the first pass or a retry after rejection/compliance failure.
"""

import json
import re
import time

from groq import GroqError, RateLimitError
from langchain_groq import ChatGroq

try:
    from backend.config import GROQ_API_KEY, GROQ_MODEL
    from backend.state import FinanceState
except ImportError:  # allows running as `python recommendation_agent.py` from within backend/agents/
    from config import GROQ_API_KEY, GROQ_MODEL
    from state import FinanceState

ALLOCATION_SCHEMES = ["ELSS", "PPF", "NPS", "FD", "Emergency Fund"]

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2

SYSTEM_PROMPT = (
    "You are a financial recommendation engine for an Indian personal finance app. "
    "Given a user's profile, financial health numbers, and retrieved reference "
    "chunks about investment schemes, propose an allocation of their monthly "
    f"surplus across exactly these categories: {', '.join(ALLOCATION_SCHEMES)}.\n\n"
    "These are retrieved reference chunks, not pre-vetted recommendations. Some "
    "chunks may describe why a scheme is UNSUITABLE for this user's profile — "
    "read each chunk's actual content and suitability notes carefully. Do not "
    "assume a chunk is being retrieved because it's a good match; judge "
    "suitability yourself based on what the text says, especially any "
    "'Suitability Notes' or 'not suitable for' language.\n\n"
    "This is a recurring monthly SIP-style plan, not a one-time lump sum "
    "meant to close the entire emergency-fund gap in a single shot. Even if "
    "the user's emergency fund is significantly below its target (the number "
    "before the '/' in emergency_fund_status is much lower than the number "
    "after it), the emergency fund should be built up gradually over several "
    "months alongside other goals, not dumped into in one shot. Emergency "
    "fund allocation must be between 15-25% of surplus. Distribute the "
    "remaining 75-85% across ELSS/PPF/NPS/FD based on the user's risk "
    "profile and goals.\n\n"
    "If the user's financial_goal itself falls into a category capped by "
    "the 15-25% rule (e.g. goal is 'emergency_fund' but emergency fund "
    "allocation is capped), explicitly acknowledge this tension in that "
    "line item's reasoning. Explain how the plan still serves the stated "
    "goal despite the cap — for example, by noting the expected number of "
    "months to reach the target at this monthly rate, or by explaining "
    "that another allocation (like FD) provides supplementary liquidity "
    "toward the same goal.\n\n"
    "Respond with ONLY a valid JSON object, no markdown code fences, no "
    "preamble, no explanation, no trailing commentary. The object's keys must "
    "be exactly the five category names above, and each value must be an "
    'object with exactly two keys: "percent" (number; the percentages across '
    'all five categories must sum to 100) and "reasoning" (a brief one-to-two '
    "sentence string explaining that specific allocation)."
)


def _format_relevant_schemes(relevant_schemes: list[dict]) -> str:
    if not relevant_schemes:
        return "(no reference chunks retrieved)"
    blocks = []
    for i, chunk in enumerate(relevant_schemes, start=1):
        blocks.append(
            f"[{i}] Scheme: {chunk.get('scheme_name')} | Section: {chunk.get('section')} "
            f"| Source: {chunk.get('source')}\n{chunk.get('chunk_text')}"
        )
    return "\n\n".join(blocks)


def _build_user_prompt(state: FinanceState) -> str:
    user_profile = state.get("user_profile") or {}

    profile_summary = {
        "age": user_profile.get("age"),
        "average_monthly_income": user_profile.get("average_monthly_income"),
        "risk_appetite": user_profile.get("risk_appetite"),
        "financial_goal": user_profile.get("financial_goal"),
        "income_volatility": user_profile.get("income_volatility"),
    }
    surplus_amount = state.get("surplus_amount", 0) or 0
    health_summary = {
        "savings_rate_pct": state.get("savings_rate"),
        "surplus_amount": surplus_amount,
        "emergency_fund_status": state.get("emergency_fund_status"),
    }

    parts = [
        "USER PROFILE:",
        json.dumps(profile_summary, indent=2),
        "\nFINANCIAL HEALTH:",
        json.dumps(health_summary, indent=2),
        "\nRETRIEVED REFERENCE CHUNKS (read carefully, do not assume relevance = suitability):",
        _format_relevant_schemes(state.get("relevant_schemes") or []),
    ]

    rejection_reason = state.get("rejection_reason")
    suitability_flags = state.get("suitability_flags")
    compliance_explanation = state.get("compliance_explanation")
    if rejection_reason or suitability_flags or compliance_explanation:
        context_lines = ["\nYour previous allocation was rejected/flagged. Revise accordingly."]
        # The compliance explanation is the primary context — it's the
        # human-readable, number-referencing account of what went wrong.
        if compliance_explanation:
            context_lines.append(f"Compliance explanation: {compliance_explanation}")
        if rejection_reason:
            context_lines.append(f"Human rejection reason: {rejection_reason}")
        # The raw flag slug(s) are secondary/technical — useful as an exact
        # machine-readable reference alongside the explanation above.
        if suitability_flags:
            context_lines.append(f"(technical flag reference: {', '.join(suitability_flags)})")
        parts.append("\n".join(context_lines))

    parts.append(
        f"\nPropose an allocation of the monthly surplus (Rs. {surplus_amount:,.2f}) "
        f"across exactly these categories: {', '.join(ALLOCATION_SCHEMES)}."
    )

    return "\n".join(parts)


def _strip_json_wrapper(raw: str) -> str:
    """Strips ```json ... ``` / ``` ... ``` fences some open-weight models add despite instructions."""
    text = raw.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return text


def _call_llm_with_retry(llm: ChatGroq, messages: list[dict]) -> str:
    attempt = 0
    while True:
        try:
            response = llm.invoke(messages)
            return response.content
        except RateLimitError:
            if attempt >= MAX_RETRIES:
                raise
            attempt += 1
            print(
                f"  [recommendation] Groq rate-limited (attempt {attempt}/{MAX_RETRIES}), "
                f"retrying in {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)


def _parse_allocation(raw_content: str) -> tuple[dict, list[str]]:
    """Returns (scheme -> {percent, reasoning}, list of warning strings)."""
    cleaned = _strip_json_wrapper(raw_content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return {}, [f"malformed_json: {exc}. Raw output: {raw_content!r}"]

    if not isinstance(parsed, dict):
        return {}, [f"malformed_json: expected a JSON object, got {type(parsed).__name__}"]

    warnings = []
    allocation: dict[str, dict] = {}
    for scheme in ALLOCATION_SCHEMES:
        entry = parsed.get(scheme)
        if not isinstance(entry, dict) or "percent" not in entry:
            warnings.append(f"missing_or_malformed_scheme: {scheme!r} -> {entry!r}")
            continue
        percent = entry.get("percent")
        if not isinstance(percent, (int, float)):
            warnings.append(f"invalid_percent: {scheme!r} -> {percent!r}")
            continue
        allocation[scheme] = {"percent": float(percent), "reasoning": str(entry.get("reasoning", ""))}

    extra_keys = set(parsed.keys()) - set(ALLOCATION_SCHEMES)
    if extra_keys:
        warnings.append(f"unexpected_keys_ignored: {sorted(extra_keys)}")

    percent_sum = sum(v["percent"] for v in allocation.values())
    if allocation and abs(percent_sum - 100.0) > 1.0:
        warnings.append(f"percentages_do_not_sum_to_100: sum={percent_sum}")

    return allocation, warnings


def generate_recommendation(state: FinanceState) -> tuple[dict, list[str]]:
    """Core logic: calls the LLM and returns (recommended_allocation, warnings).

    Usable directly (e.g. for testing) or via the `recommendation` node below.
    """
    llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.15)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(state)},
    ]

    warnings: list[str] = []
    raw_content = ""
    try:
        raw_content = _call_llm_with_retry(llm, messages)
    except GroqError as exc:
        warnings.append(f"llm_call_failed: {exc}")

    if raw_content:
        allocation, parse_warnings = _parse_allocation(raw_content)
        warnings.extend(parse_warnings)
    else:
        allocation = {}
        if not warnings:
            warnings.append("no_llm_response")

    surplus_amount = state.get("surplus_amount", 0) or 0
    recommended_allocation = {}
    for scheme, entry in allocation.items():
        percent = entry["percent"]
        recommended_allocation[scheme] = {
            "percent": percent,
            "amount": round(percent / 100 * surplus_amount, 2),
            "reasoning": entry["reasoning"],
        }

    return recommended_allocation, warnings


def recommendation(state: FinanceState) -> FinanceState:
    print("Node: recommendation")
    recommended_allocation, warnings = generate_recommendation(state)

    for warning in warnings:
        print(f"  [recommendation] WARNING: {warning}")

    state["recommended_allocation"] = recommended_allocation
    return state


if __name__ == "__main__":
    import copy

    try:
        from backend.mock_data.personas import get_persona
        from backend.mock_data.transactions import TRANSACTIONS_BY_PERSONA
        from backend.agents.ingestion_agent import ingestion
        from backend.agents.categorization_agent import categorize_transactions
        from backend.agents.health_assessment_agent import assess_health
        from backend.agents.rag_agent import rag_retrieval
    except ImportError:
        from mock_data.personas import get_persona
        from mock_data.transactions import TRANSACTIONS_BY_PERSONA
        from ingestion_agent import ingestion
        from categorization_agent import categorize_transactions
        from health_assessment_agent import assess_health
        from rag_agent import rag_retrieval

    test_persona_ids = [
        "young_professional",
        "conservative_near_retirement",
        "freelancer_irregular_income",
    ]

    for persona_id in test_persona_ids:
        persona = get_persona(persona_id)
        state: FinanceState = {
            "user_profile": copy.deepcopy(persona),
            "transactions": TRANSACTIONS_BY_PERSONA[persona_id],
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
        refined_transactions, expense_categories, _ = categorize_transactions(state["transactions"])
        state["transactions"] = refined_transactions
        state["expense_categories"] = expense_categories

        health = assess_health(state["user_profile"], state["expense_categories"])
        state["savings_rate"] = health["savings_rate"]
        state["surplus_amount"] = health["surplus_amount"]
        state["emergency_fund_status"] = health["emergency_fund_status"]

        state = rag_retrieval(state)
        state = recommendation(state)

        print(f"\n=== {persona['name']} ({persona_id}) ===")
        print(f"risk_appetite={persona['risk_appetite']}  financial_goal={persona['financial_goal']}")
        print(
            f"surplus_amount=Rs.{state['surplus_amount']:,.2f}  "
            f"emergency_fund_status={state['emergency_fund_status']}"
        )
        print("Retrieved schemes:", [s["scheme_name"] for s in state["relevant_schemes"]])
        print("Recommended allocation:")
        total_percent = 0.0
        for scheme, alloc in state["recommended_allocation"].items():
            print(f"  {scheme:<15} {alloc['percent']:>5.1f}%  Rs.{alloc['amount']:>9,.2f}  -- {alloc['reasoning']}")
            total_percent += alloc["percent"]
        print(f"  {'TOTAL':<15} {total_percent:>5.1f}%")
