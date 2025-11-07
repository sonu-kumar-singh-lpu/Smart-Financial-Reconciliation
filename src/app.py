# src/app.py
from __future__ import annotations

import os
import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

# Uses your existing PDF builder (already saved by you)
from report_pdf import generate_executive_report


# -----------------------------
# Streamlit page setup
# -----------------------------
st.set_page_config(
    page_title="Smart Financial Reconciliation — Analytics Console",
    page_icon="💼",
    layout="wide",
)

# -----------------------------
# Utility helpers (local, no external deps)
# -----------------------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _to_datetime_safe(s, fmt=None):
    try:
        return pd.to_datetime(s, format=fmt, errors="coerce")
    except Exception:
        return pd.to_datetime(s, errors="coerce")


def _read_csv_safe(path_or_buffer) -> pd.DataFrame:
    try:
        df = pd.read_csv(path_or_buffer)
        return df
    except Exception:
        # some CSVs may be semicolon separated
        try:
            return pd.read_csv(path_or_buffer, sep=";")
        except Exception:
            return pd.DataFrame()


def load_default_bank_ledger() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load default bank & ledger CSVs from ./data/"""
    bank_path = os.path.normpath(os.path.join(DATA_DIR, "bank_statement.csv"))
    ledger_path = os.path.normpath(os.path.join(DATA_DIR, "ledger_entries.csv"))
    bank = _read_csv_safe(bank_path)
    ledger = _read_csv_safe(ledger_path)
    return bank, ledger


def load_default_transactions() -> pd.DataFrame:
    """Optional lookup for NLP Categories."""
    tx_path = os.path.normpath(os.path.join(DATA_DIR, "transactions.csv"))
    if os.path.exists(tx_path):
        return _read_csv_safe(tx_path)
    return pd.DataFrame(columns=["ref", "remark", "category"])


def _normalize_bank(bank: pd.DataFrame) -> pd.DataFrame:
    """Rename/ensure bank columns exist as: date_bank, ref, amount_bank, account_bank, narration"""
    if bank is None or bank.empty:
        return pd.DataFrame(columns=["date_bank", "ref", "amount_bank", "account_bank", "narration"])

    b = bank.copy()
    cols = {c.lower().strip(): c for c in bank.columns}
    # Flexible mappings
    mapping = {}
    mapping[cols.get("date_bank", cols.get("date", cols.get("value_date", None)))] = "date_bank"
    mapping[cols.get("ref", cols.get("reference", cols.get("txn_id", None)))] = "ref"
    mapping[cols.get("amount_bank", cols.get("amount", None))] = "amount_bank"
    mapping[cols.get("account_bank", cols.get("account", cols.get("account_no", None)))] = "account_bank"
    mapping[cols.get("narration", cols.get("description", cols.get("remark", None)))] = "narration"
    mapping = {k: v for k, v in mapping.items() if k is not None}

    b = b.rename(columns=mapping)
    # Ensure required columns exist
    for col in ["date_bank", "ref", "amount_bank", "account_bank", "narration"]:
        if col not in b.columns:
            b[col] = np.nan

    b["date_bank"] = _to_datetime_safe(b["date_bank"])
    # coerce numeric
    b["amount_bank"] = pd.to_numeric(b["amount_bank"], errors="coerce")
    return b[["date_bank", "ref", "amount_bank", "account_bank", "narration"]]


def _normalize_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    """Rename/ensure ledger columns exist as: date_ledger, ref, amount_ledger, account_ledger, category, remark"""
    if ledger is None or ledger.empty:
        return pd.DataFrame(
            columns=["date_ledger", "ref", "amount_ledger", "account_ledger", "category", "remark"]
        )

    l = ledger.copy()
    cols = {c.lower().strip(): c for c in ledger.columns}
    mapping = {}
    mapping[cols.get("date_ledger", cols.get("date", None))] = "date_ledger"
    mapping[cols.get("ref", cols.get("reference", cols.get("txn_id", None)))] = "ref"
    mapping[cols.get("amount_ledger", cols.get("amount", None))] = "amount_ledger"
    mapping[cols.get("account_ledger", cols.get("account", cols.get("gl", None)))] = "account_ledger"
    mapping[cols.get("category", None)] = "category"
    mapping[cols.get("remark", cols.get("narration", cols.get("description", None)))] = "remark"
    mapping = {k: v for k, v in mapping.items() if k is not None}

    l = l.rename(columns=mapping)
    for col in ["date_ledger", "ref", "amount_ledger", "account_ledger", "category", "remark"]:
        if col not in l.columns:
            l[col] = np.nan

    l["date_ledger"] = _to_datetime_safe(l["date_ledger"])
    l["amount_ledger"] = pd.to_numeric(l["amount_ledger"], errors="coerce")
    return l[["date_ledger", "ref", "amount_ledger", "account_ledger", "category", "remark"]]


def reconcile(bank: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    """Outer-merge on ref and derive match/root_cause/iso_score flags (robust & simple)."""
    b = _normalize_bank(bank)
    l = _normalize_ledger(ledger)

    merged = pd.merge(b, l, on="ref", how="outer", suffixes=("_bank", "_ledger"))

    # Differences & flags
    merged["amount_diff"] = (merged["amount_ledger"] - merged["amount_bank"]).fillna(0)
    merged["days_diff"] = (
        (merged["date_ledger"] - merged["date_bank"]).dt.days
        if "date_ledger" in merged and "date_bank" in merged
        else np.nan
    )

    # Match rule: both sides present & amounts match within tolerance (₹1) & account matches if present
    tol = 1.0
    both_present = merged["amount_bank"].notna() & merged["amount_ledger"].notna()
    amt_close = both_present & (merged["amount_diff"].abs() <= tol)
    acct_match = (
        merged["account_bank"].fillna("").astype(str).str.strip()
        == merged["account_ledger"].fillna("").astype(str).str.strip()
    )
    merged["match"] = (amt_close & acct_match).astype(bool)

    # Root cause
    def _rc(row):
        if row["match"]:
            return "Matched"
        if pd.isna(row["amount_bank"]) and pd.notna(row["amount_ledger"]):
            return "Missing in Bank"
        if pd.notna(row["amount_bank"]) and pd.isna(row["amount_ledger"]):
            return "Missing in Ledger"
        if pd.notna(row["amount_bank"]) and pd.notna(row["amount_ledger"]):
            if abs(row["amount_diff"]) > tol:
                return "Amount Mismatch"
            # amount ok but date spread
            if pd.notna(row.get("days_diff", np.nan)) and abs(row.get("days_diff", 0)) > 3:
                return "Date Mismatch"
        return "Matched" if row["match"] else "Uncategorized"

    merged["root_cause"] = merged.apply(_rc, axis=1)

    # Simple anomaly score (0..1): normalize abs amount diff + date difference
    amt_norm = (merged["amount_diff"].abs() / (merged["amount_ledger"].abs() + 1e-9)).clip(0, 1)
    day_norm = (merged["days_diff"].fillna(0).abs() / 30.0).clip(0, 1)
    merged["iso_score"] = (0.7 * amt_norm + 0.3 * day_norm).fillna(0)

    # Flag top 15% as anomaly
    threshold = np.nanpercentile(merged["iso_score"], 85) if len(merged) else 1.0
    merged["iso_is_anomaly"] = merged["iso_score"] >= threshold

    # Lightweight anomaly_reason
    def _ar(row):
        if row["root_cause"] in ["Missing in Bank", "Missing in Ledger"]:
            return row["root_cause"]
        if abs(row["amount_diff"]) > tol:
            return "Unusual Amount Difference"
        if pd.notna(row.get("days_diff", np.nan)) and abs(row.get("days_diff", 0)) > 3:
            return "Unusual Date Gap"
        return "Multivariate Outlier" if row["iso_is_anomaly"] else "OK"

    merged["anomaly_reason"] = merged.apply(_ar, axis=1)

    # Ensure helpful defaults
    for c in ["category", "remark"]:
        if c not in merged.columns:
            merged[c] = np.nan

    # NLP predicted_category (optional). If transactions.csv exists, map remark→category
    tx = load_default_transactions()
    if not tx.empty and "remark" in tx.columns and "category" in tx.columns:
        # simple keyword join: left on ref OR exact remark match
        map_by_ref = dict(zip(tx["ref"].astype(str), tx["category"]))
        merged["predicted_category"] = merged["ref"].astype(str).map(map_by_ref)
        # fill by remark exact match if still missing
        if "remark" in merged.columns and "remark" in tx.columns:
            map_by_remark = dict(zip(tx["remark"].astype(str), tx["category"]))
            merged["predicted_category"] = merged["predicted_category"].fillna(
                merged["remark"].astype(str).map(map_by_remark)
            )
    else:
        merged["predicted_category"] = np.nan

    return merged


def kpis(df: pd.DataFrame) -> tuple[int, int, int, int]:
    total = len(df)
    matched = int(df.get("match", pd.Series([False] * total)).astype(bool).sum())
    mismatched = total - matched
    anomalies = int(df.get("iso_is_anomaly", pd.Series([False] * total)).astype(bool).sum())
    return total, matched, mismatched, anomalies


# -----------------------------
# Sidebar – Upload & Reconcile
# -----------------------------
with st.sidebar:
    st.header("Filters")
    st.caption("Upload bank & ledger CSVs to reconcile your own data.")

    bank_file = st.file_uploader(
        "Upload Bank Statement CSV",
        type=["csv"],
        key="bank_csv",
    )
    ledger_file = st.file_uploader(
        "Upload Ledger CSV",
        type=["csv"],
        key="ledger_csv",
    )
    reconcile_btn = st.button("🔁 Reconcile Uploaded Data", use_container_width=True)


# -----------------------------
# Data loading (defaults or uploaded)
# -----------------------------
if "reco_df" not in st.session_state:
    # First load: try defaults
    default_bank, default_ledger = load_default_bank_ledger()
    if default_bank.empty or default_ledger.empty:
        st.error("Failed to load default dataset from ./data/. Please check CSV files.")
        st.stop()
    st.session_state.reco_df = reconcile(default_bank, default_ledger)
    st.success("Default dataset loaded successfully.")

# If user clicked reconcile with uploaded files
if reconcile_btn:
    if bank_file is None or ledger_file is None:
        st.warning("Please upload both Bank and Ledger CSVs, then click Reconcile.")
    else:
        bdf = _read_csv_safe(bank_file)
        ldf = _read_csv_safe(ledger_file)
        st.session_state.reco_df = reconcile(bdf, ldf)
        st.success("Reconciliation complete for uploaded files.")

df = st.session_state.reco_df

# -----------------------------
# Title & KPI cards
# -----------------------------
st.markdown(
    "<h1 style='margin-top:0'>💼 Smart Financial Reconciliation — Analytics Console</h1>",
    unsafe_allow_html=True,
)

total, matched, mismatched, anomalies = kpis(df)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Transactions", f"{total}")
col2.metric("Matched", f"{matched} ({(matched/total*100):.1f}%)" if total else "0 (0.0%)")
col3.metric("Mismatched", f"{mismatched} ({(mismatched/total*100):.1f}%)" if total else "0 (0.0%)")
col4.metric("Anomalies (ML)", f"{anomalies} ({(anomalies/total*100):.1f}%)" if total else "0 (0.0%)")

st.markdown("---")

# -----------------------------
# TABS
# -----------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Reconciliation", "🚩 Anomalies", "🏷️ Categories (NLP)", "📄 Executive PDF Report"]
)

# ---------------------------------------------------
# TAB 1 — RECONCILIATION
# ---------------------------------------------------
with tab1:
    st.subheader("Reconciliation Overview")

    # Root Cause bar
    rc_counts = df["root_cause"].value_counts(dropna=False).rename_axis("root_cause").reset_index(name="count")
    fig_rc = px.bar(rc_counts, x="root_cause", y="count", title="Root Cause Breakdown")
    fig_rc.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_rc, use_container_width=True)

    # Match pie
    match_counts = df["match"].fillna(False).map({True: "Matched", False: "Not Matched"}).value_counts()
    fig_match = px.pie(
        names=match_counts.index,
        values=match_counts.values,
        title="Match Status",
        hole=0.4,
    )
    fig_match.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_match, use_container_width=True)

    st.markdown("### Drill-down Table")
    st.dataframe(df, use_container_width=True, height=420)
    st.download_button(
        "⬇️ Download Reconciliation View (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="reconciliation_view.csv",
        mime="text/csv",
    )

# ---------------------------------------------------
# TAB 2 — ANOMALIES
# ---------------------------------------------------
with tab2:
    st.subheader("ML Anomaly Insights")
    topk = df.sort_values("iso_score", ascending=False).head(100) if "iso_score" in df else df.head(100)

    # Reason bar
    ar_counts = df["anomaly_reason"].value_counts(dropna=False).rename_axis("anomaly_reason").reset_index(name="count")
    fig_ar = px.bar(ar_counts, x="anomaly_reason", y="count", title="Anomaly Reasons")
    fig_ar.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_ar, use_container_width=True)

    # Score histogram
    if "iso_score" in df:
        fig_hist = px.histogram(df, x="iso_score", nbins=30, title="Anomaly Score Distribution")
        fig_hist.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("### Top Suspicious Records")
    cols = [
        "date_bank",
        "ref",
        "amount_bank",
        "date_ledger",
        "amount_ledger",
        "category",
        "remark",
        "match",
        "root_cause",
        "iso_score",
        "iso_is_anomaly",
        "anomaly_reason",
        "amount_diff",
        "days_diff",
    ]
    cols = [c for c in cols if c in df.columns]
    st.dataframe(topk[cols], use_container_width=True, height=420)

# ---------------------------------------------------
# TAB 3 — NLP CATEGORIES
# ---------------------------------------------------
with tab3:
    st.subheader("Transaction NLP Categorization")

    # Category bar (predicted if present else actual)
    cat_col = "predicted_category" if "predicted_category" in df.columns else "category"
    cat_counts = df[cat_col].fillna("Uncategorized").value_counts().reset_index()
    cat_counts.columns = ["category", "count"]
    fig_cat = px.bar(cat_counts, x="category", y="count", title="Predicted Categories")
    fig_cat.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10))
    st.plotly_chart(fig_cat, use_container_width=True)

    # Drill table
    show_cols = ["ref", "narration", "category"]
    if "predicted_category" in df.columns:
        show_cols.append("predicted_category")
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols].head(1000), use_container_width=True, height=420)

    # Download categorized data
    st.download_button(
        "⬇️ Download NLP Categorized Data",
        data=df[show_cols].to_csv(index=False).encode("utf-8"),
        file_name="nlp_categorized_data.csv",
        mime="text/csv",
    )

# ---------------------------------------------------
# TAB 4 — EXECUTIVE PDF
# ---------------------------------------------------
with tab4:
    st.subheader("Export Executive PDF Report")
    st.write("Generate a one-click **Executive Summary** PDF with KPIs, charts and top recommendations.")
    if st.button("Generate & Download PDF Report"):
        with st.spinner("Generating PDF..."):
            # Your report_pdf.py can accept just the dataframe; it will handle missing charts safely.
            pdf_bytes = generate_executive_report(df)  # if your function accepts figs, you can pass fig_rc/fig_cat too
        st.success("✅ Report generated!")
        st.download_button(
            "📄 Download PDF",
            data=pdf_bytes,
            file_name="executive_reconciliation_report.pdf",
            mime="application/pdf",
        )
