# anomaly.py
import pandas as pd
from sklearn.ensemble import IsolationForest

NUM_FEATURES = ["amount_bank", "amount_ledger", "amount_diff", "days_diff", "dup_ref"]

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Prepare feature matrix robustly
    X = out.copy()
    for col in NUM_FEATURES:
        if col not in X.columns:
            X[col] = 0
        X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)

    if len(X) == 0:
        out["iso_score"] = 0.0
        out["iso_is_anomaly"] = False
        return out

    # Train IsolationForest
    try:
        iso = IsolationForest(
            n_estimators=200,
            contamination=0.15,  # ~15% anomalies
            random_state=42,
        )
        iso.fit(X[NUM_FEATURES])
        scores = -iso.score_samples(X[NUM_FEATURES])  # higher = more anomalous
        preds = iso.predict(X[NUM_FEATURES])  # -1 anomalous, 1 normal

        out["iso_score"] = pd.Series(scores, index=out.index)
        out["iso_is_anomaly"] = (preds == -1)

    except Exception:
        out["iso_score"] = 0.0
        out["iso_is_anomaly"] = False

    # Anomaly reason: keep root cause for missing; otherwise multivariate
    out["anomaly_reason"] = out.get("anomaly_reason", "Multivariate Outlier")
    mask_missing_bank = out["root_cause"] == "Missing in Bank"
    mask_missing_ledger = out["root_cause"] == "Missing in Ledger"
    out.loc[mask_missing_bank, "anomaly_reason"] = "Missing in Bank"
    out.loc[mask_missing_ledger, "anomaly_reason"] = "Missing in Ledger"
    out.loc[~(mask_missing_bank | mask_missing_ledger), "anomaly_reason"] = \
        out.loc[~(mask_missing_bank | mask_missing_ledger), "anomaly_reason"].fillna("Multivariate Outlier")

    return out
