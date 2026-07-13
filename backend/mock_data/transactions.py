"""Mock transaction data for demo runs, one representative month per persona."""

try:
    from backend.mock_data.personas import PERSONAS
except ImportError:  # allows running as `python transactions.py` from within backend/mock_data/
    from personas import PERSONAS

CATEGORIES = [
    "Food & Dining",
    "Rent",
    "Shopping",
    "Entertainment",
    "Travel",
    "Utilities",
]

# --- Persona 1: young_professional (high spender) --------------------------
YOUNG_PROFESSIONAL_TXNS = [
    {"date": "2026-06-01", "merchant": "UPI - Landlord Transfer", "category": "Rent", "amount": 35000},
    {"date": "2026-06-02", "merchant": "Swiggy", "category": "Food & Dining", "amount": 480},
    {"date": "2026-06-03", "merchant": "BigBasket", "category": "Food & Dining", "amount": 2450},
    {"date": "2026-06-04", "merchant": "Amazon", "category": "Shopping", "amount": 4200},
    {"date": "2026-06-05", "merchant": "Zomato", "category": "Food & Dining", "amount": 690},
    {"date": "2026-06-06", "merchant": "Uber", "category": "Travel", "amount": 320},
    {"date": "2026-06-07", "merchant": "BookMyShow", "category": "Entertainment", "amount": 900},
    {"date": "2026-06-08", "merchant": "Swiggy", "category": "Food & Dining", "amount": 560},
    {"date": "2026-06-10", "merchant": "Myntra", "category": "Shopping", "amount": 5600},
    {"date": "2026-06-11", "merchant": "Zomato", "category": "Food & Dining", "amount": 750},
    {"date": "2026-06-12", "merchant": "Airtel Postpaid", "category": "Utilities", "amount": 899},
    {"date": "2026-06-13", "merchant": "Tata Power - Electricity Bill", "category": "Utilities", "amount": 2400},
    {"date": "2026-06-15", "merchant": "Amazon", "category": "Shopping", "amount": 7800},
    {"date": "2026-06-16", "merchant": "Swiggy", "category": "Food & Dining", "amount": 610},
    {"date": "2026-06-17", "merchant": "BigBasket", "category": "Food & Dining", "amount": 2680},
    {"date": "2026-06-18", "merchant": "Netflix", "category": "Entertainment", "amount": 649},
    {"date": "2026-06-19", "merchant": "BookMyShow", "category": "Entertainment", "amount": 1100},
    {"date": "2026-06-20", "merchant": "IndiGo Airlines", "category": "Travel", "amount": 6200},
    {"date": "2026-06-26", "merchant": "H&M", "category": "Shopping", "amount": 3400},
    {"date": "2026-06-28", "merchant": "Uber", "category": "Travel", "amount": 410},
]

# --- Persona 2: conservative_near_retirement (disciplined spender) ---------
CONSERVATIVE_NEAR_RETIREMENT_TXNS = [
    {"date": "2026-06-01", "merchant": "Society Maintenance - UPI", "category": "Rent", "amount": 3500},
    {"date": "2026-06-02", "merchant": "BigBasket", "category": "Food & Dining", "amount": 3200},
    {"date": "2026-06-03", "merchant": "LPG Gas Agency", "category": "Utilities", "amount": 950},
    {"date": "2026-06-04", "merchant": "BSNL Landline & Broadband", "category": "Utilities", "amount": 799},
    {"date": "2026-06-05", "merchant": "Local Kirana Store - UPI", "category": "Food & Dining", "amount": 1450},
    {"date": "2026-06-07", "merchant": "Electricity Board - Bill Pay", "category": "Utilities", "amount": 1800},
    {"date": "2026-06-08", "merchant": "Apollo Pharmacy", "category": "Shopping", "amount": 1200},
    {"date": "2026-06-10", "merchant": "Ola", "category": "Travel", "amount": 280},
    {"date": "2026-06-12", "merchant": "BigBasket", "category": "Food & Dining", "amount": 2900},
    {"date": "2026-06-14", "merchant": "Indian Railways - IRCTC", "category": "Travel", "amount": 1450},
    {"date": "2026-06-16", "merchant": "Local Kirana Store - UPI", "category": "Food & Dining", "amount": 1100},
    {"date": "2026-06-18", "merchant": "Reliance Trends", "category": "Shopping", "amount": 1600},
    {"date": "2026-06-19", "merchant": "Airtel Prepaid", "category": "Utilities", "amount": 399},
    {"date": "2026-06-21", "merchant": "BookMyShow", "category": "Entertainment", "amount": 400},
    {"date": "2026-06-23", "merchant": "BigBasket", "category": "Food & Dining", "amount": 2650},
    {"date": "2026-06-25", "merchant": "Ola", "category": "Travel", "amount": 310},
    {"date": "2026-06-27", "merchant": "Temple Trust - Donation", "category": "Entertainment", "amount": 500},
    {"date": "2026-06-29", "merchant": "Local Kirana Store - UPI", "category": "Food & Dining", "amount": 980},
]

# --- Persona 3: freelancer_irregular_income (moderate, building buffer) ----
FREELANCER_IRREGULAR_INCOME_TXNS = [
    {"date": "2026-06-01", "merchant": "UPI - Shared Flat Rent Split", "category": "Rent", "amount": 15000},
    {"date": "2026-06-02", "merchant": "Swiggy", "category": "Food & Dining", "amount": 380},
    {"date": "2026-06-03", "merchant": "BigBasket", "category": "Food & Dining", "amount": 1800},
    {"date": "2026-06-05", "merchant": "Uber", "category": "Travel", "amount": 260},
    {"date": "2026-06-06", "merchant": "Amazon", "category": "Shopping", "amount": 1900},
    {"date": "2026-06-08", "merchant": "Zomato", "category": "Food & Dining", "amount": 520},
    {"date": "2026-06-09", "merchant": "Jio Prepaid", "category": "Utilities", "amount": 349},
    {"date": "2026-06-10", "merchant": "WeWork - Day Pass", "category": "Travel", "amount": 800},
    {"date": "2026-06-12", "merchant": "Swiggy", "category": "Food & Dining", "amount": 610},
    {"date": "2026-06-13", "merchant": "Spotify", "category": "Entertainment", "amount": 119},
    {"date": "2026-06-15", "merchant": "BigBasket", "category": "Food & Dining", "amount": 2100},
    {"date": "2026-06-16", "merchant": "Electricity Board - Bill Pay", "category": "Utilities", "amount": 1350},
    {"date": "2026-06-18", "merchant": "Uber", "category": "Travel", "amount": 340},
    {"date": "2026-06-19", "merchant": "Myntra", "category": "Shopping", "amount": 2200},
    {"date": "2026-06-21", "merchant": "Zomato", "category": "Food & Dining", "amount": 470},
    {"date": "2026-06-23", "merchant": "BookMyShow", "category": "Entertainment", "amount": 600},
    {"date": "2026-06-25", "merchant": "ACT Fibernet", "category": "Utilities", "amount": 899},
    {"date": "2026-06-27", "merchant": "Swiggy", "category": "Food & Dining", "amount": 440},
    {"date": "2026-06-29", "merchant": "Amazon", "category": "Shopping", "amount": 1500},
]

TRANSACTIONS_BY_PERSONA = {
    "young_professional": YOUNG_PROFESSIONAL_TXNS,
    "conservative_near_retirement": CONSERVATIVE_NEAR_RETIREMENT_TXNS,
    "freelancer_irregular_income": FREELANCER_IRREGULAR_INCOME_TXNS,
}


def get_transactions(persona_id: str) -> list[dict]:
    return TRANSACTIONS_BY_PERSONA[persona_id]


def summarize(transactions: list[dict]) -> dict:
    by_category = {category: 0 for category in CATEGORIES}
    for txn in transactions:
        by_category[txn["category"]] += txn["amount"]
    total = sum(by_category.values())
    return {"total_spend": total, "by_category": by_category}


if __name__ == "__main__":
    for persona in PERSONAS:
        transactions = TRANSACTIONS_BY_PERSONA[persona["id"]]
        summary = summarize(transactions)
        income = persona["monthly_income"]
        income_display = income if isinstance(income, (int, float)) else f"varying {income} (avg {sum(income) / len(income):.0f})"
        reference_income = income if isinstance(income, (int, float)) else income[-1]
        savings_rate = (reference_income - summary["total_spend"]) / reference_income * 100

        print(f"\n=== {persona['name']} ({persona['id']}) ===")
        print(f"Monthly income: {income_display}")
        print(f"Transactions: {len(transactions)}")
        print(f"Total spend: Rs. {summary['total_spend']:,}")
        print(f"Savings rate (vs. reference income Rs. {reference_income:,}): {savings_rate:.1f}%")
        print("By category:")
        for category, amount in summary["by_category"].items():
            pct = (amount / summary["total_spend"] * 100) if summary["total_spend"] else 0
            print(f"  - {category:<15} Rs. {amount:>7,}  ({pct:4.1f}%)")
