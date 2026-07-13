"""Executes approved actions.

Only does meaningful work when approval_status == "approved" — pure
formatting/calculation, no LLM call. Computes monthly_sip,
annual_deployment, and a rough estimated_tax_saved from the approved
recommended_allocation, then stores it all in state["final_plan"] with an
activated_at timestamp.
"""

from datetime import datetime, timezone

try:
    from backend.state import FinanceState
except ImportError:  # allows running as `python execution_agent.py` from within backend/agents/
    from state import FinanceState

SECTION_80C_ANNUAL_LIMIT = 150000
SECTION_80CCD_1B_ANNUAL_LIMIT = 50000

# Simplifying assumption for a rough estimate only — not personalized to the
# user's actual income tax slab. Real tax-saved figures depend on the
# investor's marginal rate, which this app doesn't model.
ASSUMED_MARGINAL_TAX_RATE = 0.20


def _compute_final_plan(recommended_allocation: dict) -> dict:
    monthly_sip = sum(
        entry.get("amount", 0)
        for scheme, entry in recommended_allocation.items()
        if scheme != "Emergency Fund"
    )
    annual_deployment = monthly_sip * 12

    annual_elss = (recommended_allocation.get("ELSS") or {}).get("amount", 0) * 12
    annual_ppf = (recommended_allocation.get("PPF") or {}).get("amount", 0) * 12
    annual_nps = (recommended_allocation.get("NPS") or {}).get("amount", 0) * 12

    # ELSS + PPF share the combined Section 80C ceiling; NPS gets an
    # additional, separate ceiling under Section 80CCD(1B).
    eligible_80c = min(annual_elss + annual_ppf, SECTION_80C_ANNUAL_LIMIT)
    eligible_80ccd1b = min(annual_nps, SECTION_80CCD_1B_ANNUAL_LIMIT)
    total_deduction = eligible_80c + eligible_80ccd1b
    estimated_tax_saved = round(total_deduction * ASSUMED_MARGINAL_TAX_RATE, 2)

    return {
        "monthly_sip": round(monthly_sip, 2),
        "annual_deployment": round(annual_deployment, 2),
        "estimated_tax_saved": {
            "annual_80c_eligible": round(eligible_80c, 2),
            "annual_80ccd1b_eligible": round(eligible_80ccd1b, 2),
            "total_deduction": round(total_deduction, 2),
            "assumed_marginal_tax_rate_pct": ASSUMED_MARGINAL_TAX_RATE * 100,
            "estimated_annual_tax_saved": estimated_tax_saved,
        },
    }


def execution(state: FinanceState) -> FinanceState:
    print("Node: execution")
    if state.get("approval_status") != "approved":
        print("  [execution] WARNING: called without approval_status == 'approved'; leaving final_plan unset.")
        return state

    recommended_allocation = state.get("recommended_allocation") or {}
    plan = _compute_final_plan(recommended_allocation)

    state["final_plan"] = {
        "recommended_allocation": recommended_allocation,
        **plan,
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    return state
