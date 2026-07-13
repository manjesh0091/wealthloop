"""Retrieves relevant context from ChromaDB.

Pure retrieval — no LLM call. Builds a natural-language query from the
user's risk_appetite, financial_goal, and income_volatility, then queries
backend.rag.retriever for the most relevant scheme-document chunks.
"""

try:
    from backend.state import FinanceState
    from backend.rag.retriever import retrieve
except ImportError:  # allows running as `python rag_agent.py` from within backend/agents/
    from state import FinanceState
    from rag.retriever import retrieve

RISK_APPETITE_PHRASES = {
    "aggressive": "an aggressive investor comfortable with market risk",
    "moderate": "an investor with a moderate risk appetite",
    "conservative": "a conservative investor prioritizing safety and capital protection",
}

FINANCIAL_GOAL_PHRASES = {
    "wealth_growth": "focused on long-term wealth growth",
    "retirement": "planning for retirement",
    "emergency_fund": "building an emergency fund",
}

INCOME_VOLATILITY_CLAUSES = {
    "variable": ", with variable/irregular income and a need for liquidity",
    "stable": "",
}

SCHEME_NAME_BY_SOURCE = {
    "nps_scheme.txt": "NPS",
    "ppf_scheme.txt": "PPF",
    "elss_scheme.txt": "ELSS",
    "fd_emergency_fund.txt": "FD / Emergency Fund",
}


def build_query(user_profile: dict) -> str:
    risk_phrase = RISK_APPETITE_PHRASES.get(
        user_profile.get("risk_appetite"), "an investor"
    )
    goal_phrase = FINANCIAL_GOAL_PHRASES.get(
        user_profile.get("financial_goal"), "managing their finances"
    )
    volatility_clause = INCOME_VOLATILITY_CLAUSES.get(user_profile.get("income_volatility"), "")

    return f"Investment options for {risk_phrase}, {goal_phrase}{volatility_clause}."


def derive_scheme_name(source: str) -> str:
    if source in SCHEME_NAME_BY_SOURCE:
        return SCHEME_NAME_BY_SOURCE[source]
    stem = source.rsplit(".", 1)[0].replace("_scheme", "").replace("_", " ")
    return stem.upper() if len(stem) <= 5 else stem.title()


def rag_retrieval(state: FinanceState) -> FinanceState:
    print("Node: rag_retrieval")
    user_profile = state.get("user_profile") or {}
    query = build_query(user_profile)

    hits = retrieve(query, k=4)
    state["relevant_schemes"] = [
        {
            "scheme_name": derive_scheme_name(hit["source"]),
            "section": hit["section"],
            "chunk_text": hit["text"],
            "source": hit["source"],
        }
        for hit in hits
    ]
    return state


if __name__ == "__main__":
    import copy

    try:
        from backend.mock_data.personas import PERSONAS
        from backend.agents.ingestion_agent import ingestion
    except ImportError:
        from mock_data.personas import PERSONAS
        from ingestion_agent import ingestion

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
        state = ingestion(state)
        query = build_query(state["user_profile"])
        state = rag_retrieval(state)

        print(f"\n=== {persona['name']} ({persona['id']}) ===")
        print(f"Query: {query}")
        for rank, scheme in enumerate(state["relevant_schemes"], start=1):
            print(f"  {rank}. {scheme['scheme_name']:<20} / {scheme['section']}")
