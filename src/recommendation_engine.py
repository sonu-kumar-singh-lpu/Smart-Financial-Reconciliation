# recommendation_engine.py
import pandas as pd

def generate_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    recos = []
    for _, row in out.iterrows():
        rc = str(row.get("root_cause", "")).strip()
        ar = str(row.get("anomaly_reason", "")).strip()
        anom = bool(row.get("iso_is_anomaly", False))

        if rc == "Missing in Bank":
            recos.append("Bank entry missing. Check if payment is pending or incorrectly mapped.")
            continue
        if rc == "Missing in Ledger":
            recos.append("Ledger entry missing. Verify vendor invoice and post the correct ledger entry.")
            continue
        if rc == "Amount Mismatch":
            recos.append("Amount mismatch detected. Verify GST/rounding/partial settlement/double posting.")
            continue
        if rc == "Date Mismatch":
            recos.append("Posting date mismatch. Validate processing date vs clearing date.")
            continue
        if anom:
            recos.append(f"High-risk anomaly: {ar}. Investigate approvals & supporting documents.")
            continue
        recos.append("Reconciled successfully. No action required.")
    out["recommendation"] = recos
    return out

def load_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return generate_recommendations(df)
