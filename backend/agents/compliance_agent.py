"""Checks recommended_allocation for compliance/suitability issues.

The pass/fail decision itself is a deterministic, rule-based check against
user_profile["risk_appetite"] — kept auditable, no LLM involved in the
decision. An LLM call is made only when a rule fails, to turn the flag into
a human-readable compliance_explanation.

Also tracks revision attempts (based on the flags computed in this same
call) so the compliance <-> recommendation loop in graph.py can cap itself
instead of looping forever.
"""

import time

from groq import GroqError, RateLimitError
from langchain_groq import ChatGroq

try:
    from backend.config import DEMO_FORCE_FAIL_FOR, GROQ_API_KEY, GROQ_MODEL
    from backend.state import FinanceState
except ImportError:  # allows running as `python compliance_agent.py` from within backend/agents/
    from config import DEMO_FORCE_FAIL_FOR, GROQ_API_KEY, GROQ_MODEL
    from state import FinanceState

CONSERVATIVE_EQUITY_CAP_PCT = 15
MODERATE_EQUITY_CAP_PCT = 40
AGGRESSIVE_MIN_EMERGENCY_FUND_PCT = 10

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2

EXPLANATION_SYSTEM_PROMPT = (
    "You are a compliance explanation assistant for a personal finance app. "
    "Given a triggered suitability flag, the specific numbers involved, and "
    "the user's profile, write a brief (2-3 sentence) human-readable "
    "explanation of why this allocation was flagged. Reference the specific "
    "percentages and thresholds involved. Respond with plain text only — no "
    "markdown, no preamble, no JSON."
)


def _pct(recommended_allocation: dict, scheme: str) -> float:
    return (recommended_allocation.get(scheme) or {}).get("percent", 0) or 0


def check_suitability(recommended_allocation: dict, user_profile: dict) -> tuple[list[str], dict]:
    """Deterministic rule-based suitability check. Returns (flags, rule_context)."""
    risk_appetite = user_profile.get("risk_appetite")
    elss_nps_combined = _pct(recommended_allocation, "ELSS") + _pct(recommended_allocation, "NPS")
    emergency_fund_pct = _pct(recommended_allocation, "Emergency Fund")

    if risk_appetite == "conservative":
        if elss_nps_combined > CONSERVATIVE_EQUITY_CAP_PCT:
            return ["equity_exposure_exceeds_conservative_threshold"], {
                "elss_nps_combined_pct": elss_nps_combined,
                "threshold_pct": CONSERVATIVE_EQUITY_CAP_PCT,
            }
    elif risk_appetite == "aggressive":
        if emergency_fund_pct < AGGRESSIVE_MIN_EMERGENCY_FUND_PCT:
            return ["insufficient_emergency_buffer"], {
                "emergency_fund_pct": emergency_fund_pct,
                "threshold_pct": AGGRESSIVE_MIN_EMERGENCY_FUND_PCT,
            }
    elif risk_appetite == "moderate":
        if elss_nps_combined > MODERATE_EQUITY_CAP_PCT:
            return ["equity_exposure_exceeds_moderate_threshold"], {
                "elss_nps_combined_pct": elss_nps_combined,
                "threshold_pct": MODERATE_EQUITY_CAP_PCT,
            }

    return [], {}


def _equity_exposure_flag_for(risk_appetite: str) -> str | None:
    """The equity-exposure flag family for a risk tier, or None if that tier has no such rule."""
    if risk_appetite == "conservative":
        return "equity_exposure_exceeds_conservative_threshold"
    if risk_appetite == "moderate":
        return "equity_exposure_exceeds_moderate_threshold"
    return None  # aggressive's only rule is the emergency-buffer minimum, not an equity cap


def _matches_demo_force_fail(user_profile: dict) -> bool:
    if not DEMO_FORCE_FAIL_FOR:
        return False
    haystack = f"{user_profile.get('id', '')} {user_profile.get('name', '')}".lower()
    return DEMO_FORCE_FAIL_FOR in haystack


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
                f"  [compliance_guardrail] Groq rate-limited (attempt {attempt}/{MAX_RETRIES}), "
                f"retrying in {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)


def _build_explanation_prompt(
    flags: list[str], rule_context: dict, recommended_allocation: dict, user_profile: dict
) -> str:
    percentages = {scheme: entry.get("percent") for scheme, entry in recommended_allocation.items()}
    return (
        f"User: age {user_profile.get('age')}, risk_appetite={user_profile.get('risk_appetite')!r}\n"
        f"Triggered flag(s): {', '.join(flags)}\n"
        f"Relevant numbers: {rule_context}\n"
        f"Full recommended allocation (% of surplus): {percentages}\n"
        "Explain, in plain language, why this allocation was flagged."
    )


def generate_compliance_explanation(
    flags: list[str], rule_context: dict, recommended_allocation: dict, user_profile: dict
) -> str:
    llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.2)
    messages = [
        {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
        {"role": "user", "content": _build_explanation_prompt(flags, rule_context, recommended_allocation, user_profile)},
    ]
    try:
        return _call_llm_with_retry(llm, messages).strip()
    except GroqError as exc:
        print(f"  [compliance_guardrail] WARNING: explanation LLM call failed: {exc}")
        return f"Flagged for: {', '.join(flags)} (explanation unavailable: {exc})"


def compliance_guardrail(state: FinanceState) -> FinanceState:
    print("Node: compliance_guardrail")
    recommended_allocation = state.get("recommended_allocation") or {}
    user_profile = state.get("user_profile") or {}

    flags, rule_context = check_suitability(recommended_allocation, user_profile)

    # Demo hook only: on this persona's FIRST compliance check, force an
    # equity-exposure failure regardless of the actual computed percentages,
    # so the fail-then-retry loop is guaranteed to fire on demand. Retries
    # (revision_round > 0) are never forced — the real rule always decides
    # whether attempt 2+ passes. No-op unless DEMO_FORCE_FAIL_FOR is set.
    is_first_check = state.get("revision_round", 0) == 0
    if is_first_check and _matches_demo_force_fail(user_profile):
        forced_flag = _equity_exposure_flag_for(user_profile.get("risk_appetite"))
        if forced_flag and forced_flag not in flags:
            print(
                f"  [compliance_guardrail] DEMO_FORCE_FAIL_FOR={DEMO_FORCE_FAIL_FOR!r} matched this "
                f"persona -- forcing '{forced_flag}' on the first attempt."
            )
            flags = [forced_flag]
            rule_context = {
                "elss_nps_combined_pct": _pct(recommended_allocation, "ELSS") + _pct(recommended_allocation, "NPS"),
                "threshold_pct": (
                    CONSERVATIVE_EQUITY_CAP_PCT
                    if user_profile.get("risk_appetite") == "conservative"
                    else MODERATE_EQUITY_CAP_PCT
                ),
                "demo_forced": True,
            }

    state["suitability_flags"] = flags  # explicit [] on pass

    if flags:
        state["revision_round"] = state.get("revision_round", 0) + 1
        state["compliance_explanation"] = generate_compliance_explanation(
            flags, rule_context, recommended_allocation, user_profile
        )
    else:
        state["compliance_explanation"] = None

    return state


if __name__ == "__main__":
    try:
        from backend.mock_data.personas import get_persona
    except ImportError:
        from mock_data.personas import get_persona

    # Current allocations from the recommendation_agent test runs.
    test_cases = [
        ("conservative_near_retirement", {"PPF": 60, "NPS": 10, "FD": 10, "Emergency Fund": 20, "ELSS": 0}),
        ("young_professional", {"ELSS": 45, "NPS": 20, "PPF": 7.5, "FD": 7.5, "Emergency Fund": 20}),
        ("freelancer_irregular_income", {"ELSS": 30, "NPS": 15, "PPF": 25, "FD": 15, "Emergency Fund": 20}),
    ]

    for persona_id, percentages in test_cases:
        persona = get_persona(persona_id)
        recommended_allocation = {
            scheme: {"percent": pct, "amount": 0, "reasoning": ""} for scheme, pct in percentages.items()
        }
        state: FinanceState = {
            "user_profile": persona,
            "transactions": [],
            "expense_categories": {},
            "savings_rate": 0.0,
            "surplus_amount": 0.0,
            "emergency_fund_status": "",
            "relevant_schemes": [],
            "recommended_allocation": recommended_allocation,
            "suitability_flags": [],
            "compliance_explanation": None,
            "revision_round": 0,
            "rejection_reason": None,
            "approval_status": "pending",
            "final_plan": None,
        }

        state = compliance_guardrail(state)

        print(f"\n=== {persona['name']} ({persona_id}) — risk_appetite={persona['risk_appetite']} ===")
        print(f"Allocation: {percentages}")
        print(f"suitability_flags: {state['suitability_flags']}")
        print(f"revision_round: {state['revision_round']}")
        if state.get("compliance_explanation"):
            print(f"compliance_explanation: {state['compliance_explanation']}")
