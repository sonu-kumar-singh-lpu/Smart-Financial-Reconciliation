import pandas as pd
import os

from anomaly import detect_anomalies
from transaction_classifier import classify_transactions
from recommendation_engine import load_recommendations


# ----------------------------------------------------------------------
# ✅ 1. Load DEFAULT dataset (bank + ledger already merged)
# ----------------------------------------------------------------------
def load_default_transactions():
    """
    Loads the default prepared dataset stored in 'data/' folder.
    File: reconciliation_with_anomalies.csv
    """
    default_path = os.path.join("data", "reconciliation_with_anomalies.csv")

    if not os.path.exists(default_path):
        raise FileNotFoundError(f"Default dataset NOT found at {default_path}")

    df = pd.read_csv(default_path)
    return df


# ----------------------------------------------------------------------
# ✅ 2. Reconcile uploaded bank + ledger files
# ----------------------------------------------------------------------
def reconcile_uploaded_files(bank_file, ledger_file):
    """
    Takes uploaded bank & ledger CSV and runs the FULL reconciliation pipeline.
    """

    bank_df = pd.read_csv(bank_file)
    ledger_df = pd.read_csv(ledger_file)

    return run_full_reconciliation_pipeline(bank_df, ledger_df)


# ----------------------------------------------------------------------
# ✅ 3. Merge bank & ledger files
# ----------------------------------------------------------------------
def merge_bank_ledger(bank_df, ledger_df):
    """
    Performs reconciliation by merging bank and ledger data.
    """

    bank_df = bank_df.rename(columns={
        "date": "date_bank",
        "amount": "amount_bank",
        "account": "account_bank"
    })

    ledger_df = ledger_df.rename(columns={
        "date": "date_ledger",
        "amount": "amount_ledger",
        "account": "account_ledger"
    })

    merged = pd.merge(
        bank_df,
        ledger_df,
        on="ref",
        how="outer",
        suffixes=("_bank", "_ledger")
    )

    # Fill missing values
    merged["amount_bank"] = merged["amount_bank"].fillna(0)
    merged["amount_ledger"] = merged["amount_ledger"].fillna(0)

    # Create numeric difference columns
    merged["amount_diff"] = (merged["amount_bank"] - merged["amount_ledger"]).abs()
    merged["days_diff"] = (
        pd.to_datetime(merged["date_bank"]) - pd.to_datetime(merged["date_ledger"])
    ).dt.days.fillna(0).abs()

    # Match column
    merged["match"] = (
        (merged["amount_diff"] == 0) &
        (merged["days_diff"] == 0)
    ).astype(int)

    # Rule-based root cause
    merged["root_cause"] = merged.apply(assign_root_cause, axis=1)

    return merged


# ----------------------------------------------------------------------
# ✅ 4. Root Cause Logic
# ----------------------------------------------------------------------
def assign_root_cause(row):
    if row["amount_bank"] == 0:
        return "Missing in Bank"
    if row["amount_ledger"] == 0:
        return "Missing in Ledger"
    if row["amount_diff"] != 0:
        return "Amount Mismatch"
    if row["days_diff"] != 0:
        return "Date Mismatch"
    return "Matched"


# ----------------------------------------------------------------------
# ✅ 5. Full Pipeline
# ----------------------------------------------------------------------
def run_full_reconciliation_pipeline(bank_df, ledger_df):
    """
    Full pipeline:
    1. Merge data
    2. Detect ML anomalies
    3. NLP classification
    4. Generate recommendations
    """

    # Step 1: merge
    merged = merge_bank_ledger(bank_df, ledger_df)

    # Step 2: ML anomaly detection
    merged = detect_anomalies(merged)

    # Step 3: NLP category classification
    merged = classify_transactions(merged)

    # Step 4: AI recommendations
    merged = load_recommendations(merged)

    return merged
