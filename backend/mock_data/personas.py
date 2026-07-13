"""Mock user personas for demo runs, matching the FinanceState `user_profile` shape."""

PERSONAS = [
    {
        "id": "young_professional",
        "name": "Aditya Rao",
        "age": 28,
        "monthly_income": 120000,
        "risk_appetite": "aggressive",
        "financial_goal": "wealth_growth",
        "notes": "High discretionary spender; low current savings rate.",
    },
    {
        "id": "conservative_near_retirement",
        "name": "Sunita Iyer",
        "age": 58,
        "monthly_income": 90000,
        "risk_appetite": "conservative",
        "financial_goal": "retirement",
        "notes": "Compliance-fail trigger persona: near-retirement + conservative "
        "risk appetite should reject any aggressive/equity-heavy recommendation.",
    },
    {
        "id": "freelancer_irregular_income",
        "name": "Kabir Mehta",
        "age": 34,
        "monthly_income": [45000, 78000, 52000],  # last 3 sample months, most recent last
        "risk_appetite": "moderate",
        "financial_goal": "emergency_fund",
        "notes": "Irregular gig income; needs a larger emergency buffer before "
        "committing to long lock-in instruments.",
    },
]


def get_persona(persona_id: str) -> dict:
    for persona in PERSONAS:
        if persona["id"] == persona_id:
            return persona
    raise KeyError(f"Unknown persona_id: {persona_id}")


if __name__ == "__main__":
    for persona in PERSONAS:
        print(persona)
