# transaction_classifier.py
import pandas as pd

KEYWORD_MAP = [
    ("salary|payroll|credit - hrms", "Salary"),
    ("upi|transfer", "Transfer"),
    ("bill|charge|electricity|utility", "Utility"),
    ("emi|loan", "EMI"),
    ("amazon|shopping", "Shopping"),
    ("swiggy|zomato|food", "Food"),
    ("insurance", "Insurance"),
    ("wallet|top-up|recharge", "Wallet"),
]

def _simple_nlp_category(text: str) -> str:
    if not isinstance(text, str):
        return "Uncategorized"
    t = text.lower()
    for pat, lab in KEYWORD_MAP:
        if any(k in t for k in pat.split("|")):
            return lab
    return "Uncategorized"

def classify_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure a 'predicted_category' column exists (even if we reuse 'category').
    """
    out = df.copy()
    if "predicted_category" in out.columns:
        return out
    if "category" in out.columns and out["category"].notna().any():
        out["predicted_category"] = out["category"]
        return out
    # fall back to narration-based guess
    out["predicted_category"] = out.get("narration", "").astype(str).apply(_simple_nlp_category)
    return out
