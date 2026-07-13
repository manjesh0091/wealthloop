"""Categorizes transactions.

Transactions already carry a rough category from mock data. This node runs
a single LLM validation/cleanup pass over that rough categorization (rather
than categorizing from scratch, to keep token usage low), then aggregates
the (possibly corrected) categories into state["expense_categories"].
"""

import json
import re
import time

from groq import GroqError, RateLimitError
from langchain_groq import ChatGroq

try:
    from backend.config import GROQ_API_KEY, GROQ_MODEL
    from backend.state import FinanceState
except ImportError:  # allows running as `python categorization_agent.py` from within backend/agents/
    from config import GROQ_API_KEY, GROQ_MODEL
    from state import FinanceState

ALLOWED_CATEGORIES = [
    "Food & Dining",
    "Rent",
    "Shopping",
    "Entertainment",
    "Travel",
    "Utilities",
]

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2

SYSTEM_PROMPT = (
    "You are a transaction categorization validator for a personal finance app. "
    "You will be given a JSON array of transactions, each with an index (\"i\"), "
    "a merchant, an amount, and a rough pre-assigned category (\"rough_category\"). "
    "Your job is to confirm or correct the category for each transaction. "
    f"The ONLY valid categories are: {', '.join(ALLOWED_CATEGORIES)}. "
    "If a rough category is already correct, keep it as-is; only change it if it "
    "is clearly wrong. "
    "Respond with ONLY a valid JSON array, no markdown code fences, no preamble, "
    "no explanation, no trailing commentary. Each element must be an object with "
    'exactly two keys: "i" (the transaction index, integer) and "category" (one '
    "of the allowed category strings, exactly as written above)."
)


def _build_user_prompt(transactions: list[dict]) -> str:
    compact = [
        {
            "i": i,
            "merchant": t.get("merchant"),
            "amount": t.get("amount"),
            "rough_category": t.get("category"),
        }
        for i, t in enumerate(transactions)
    ]
    return json.dumps(compact)


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
                f"  [categorization] Groq rate-limited (attempt {attempt}/{MAX_RETRIES}), "
                f"retrying in {RETRY_DELAY_SECONDS}s..."
            )
            time.sleep(RETRY_DELAY_SECONDS)


def _parse_llm_categories(raw_content: str, num_transactions: int) -> tuple[dict[int, str], list[str]]:
    """Returns (index -> confirmed/corrected category, list of warning strings)."""
    cleaned = _strip_json_wrapper(raw_content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return {}, [f"malformed_json: {exc}. Raw output: {raw_content!r}"]

    if not isinstance(parsed, list):
        return {}, [f"malformed_json: expected a JSON array, got {type(parsed).__name__}"]

    warnings = []
    index_to_category: dict[int, str] = {}
    for item in parsed:
        if not isinstance(item, dict) or "i" not in item or "category" not in item:
            warnings.append(f"malformed_item: {item!r}")
            continue
        idx = item["i"]
        category = item["category"]
        if not isinstance(idx, int) or not (0 <= idx < num_transactions):
            warnings.append(f"invalid_index: {item!r}")
            continue
        if category not in ALLOWED_CATEGORIES:
            warnings.append(f"category_outside_allowed_set: index={idx} category={category!r}")
            continue
        index_to_category[idx] = category

    return index_to_category, warnings


def _aggregate(transactions: list[dict]) -> dict:
    totals = {cat: 0 for cat in ALLOWED_CATEGORIES}
    for t in transactions:
        category = t.get("category")
        if category in totals:
            totals[category] += t.get("amount", 0)

    grand_total = sum(totals.values())
    expense_categories = {}
    for category, amount in totals.items():
        percentage = (amount / grand_total * 100) if grand_total else 0.0
        expense_categories[category] = {"total": amount, "percentage": round(percentage, 1)}
    return expense_categories


def categorize_transactions(transactions: list[dict]) -> tuple[list[dict], dict, list[str]]:
    """Core logic: runs the LLM validation pass and aggregates categories.

    Returns (refined_transactions, expense_categories, warnings). Usable
    directly (e.g. for testing) or via the `categorization` node below.
    """
    if not transactions:
        return [], _aggregate([]), []

    llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(transactions)},
    ]

    warnings: list[str] = []
    raw_content = ""
    try:
        raw_content = _call_llm_with_retry(llm, messages)
    except GroqError as exc:
        warnings.append(f"llm_call_failed: {exc}")

    if raw_content:
        index_to_category, parse_warnings = _parse_llm_categories(raw_content, len(transactions))
        warnings.extend(parse_warnings)
    else:
        index_to_category = {}
        if not warnings:
            warnings.append("no_llm_response")

    # Transactions the LLM didn't return a valid entry for keep their
    # original mock-data category as a safe fallback.
    refined_transactions = []
    for i, t in enumerate(transactions):
        refined = dict(t)
        if i in index_to_category:
            refined["category"] = index_to_category[i]
        refined_transactions.append(refined)

    expense_categories = _aggregate(refined_transactions)
    return refined_transactions, expense_categories, warnings


def categorization(state: FinanceState) -> FinanceState:
    print("Node: categorization")
    transactions = state.get("transactions") or []
    refined_transactions, expense_categories, warnings = categorize_transactions(transactions)

    for warning in warnings:
        print(f"  [categorization] WARNING: {warning}")

    state["transactions"] = refined_transactions
    state["expense_categories"] = expense_categories
    return state


if __name__ == "__main__":
    try:
        from backend.mock_data.personas import PERSONAS
        from backend.mock_data.transactions import TRANSACTIONS_BY_PERSONA
    except ImportError:
        from mock_data.personas import PERSONAS
        from mock_data.transactions import TRANSACTIONS_BY_PERSONA

    saw_malformed = False
    saw_invalid_category = False

    for persona in PERSONAS:
        transactions = TRANSACTIONS_BY_PERSONA[persona["id"]]
        print(f"\n=== {persona['name']} ({persona['id']}) ===")

        _, expense_categories, warnings = categorize_transactions(transactions)

        for warning in warnings:
            print(f"  WARNING: {warning}")
            if warning.startswith(("malformed_json", "malformed_item", "no_llm_response", "llm_call_failed")):
                saw_malformed = True
            if warning.startswith("category_outside_allowed_set"):
                saw_invalid_category = True

        for category, stats in expense_categories.items():
            print(f"  {category:<15} total=Rs.{stats['total']:>7,}  pct={stats['percentage']:>5.1f}%")

    print("\n=== Summary across all personas ===")
    print(f"Malformed/unparseable LLM output encountered: {saw_malformed}")
    print(f"LLM returned a category outside the 6 allowed: {saw_invalid_category}")
