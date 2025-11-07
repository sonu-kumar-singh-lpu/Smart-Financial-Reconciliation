from recommendation_engine import RecommendationEngine
import pandas as pd
from anomaly import RecoAnomalyDetector, AnomalyConfig
from transaction_classifier import TransactionClassifier

# ---------------------------------------------------
# 1) LOAD DATA
# ---------------------------------------------------
bank_df = pd.read_csv('../data/bank_statement.csv')
ledger_df = pd.read_csv('../data/ledger_entries.csv')
transactions_df = pd.read_csv('../data/transactions.csv')

# ---------------------------------------------------
# 2) MERGE BANK + LEDGER
# ---------------------------------------------------
merged = bank_df.merge(
    ledger_df,
    on='ref',
    suffixes=('_bank', '_ledger'),
    how='outer'
)

# ---------------------------------------------------
# 3) MATCH FLAG
# ---------------------------------------------------
merged['match'] = (
    (merged['amount_bank'] == merged['amount_ledger']) &
    (merged['date_bank'] == merged['date_ledger'])
)

# ---------------------------------------------------
# 4) ROOT CAUSE TAGGING
# ---------------------------------------------------
def root_cause(row):
    if pd.isnull(row['amount_ledger']):
        return 'Missing in Ledger'
    elif pd.isnull(row['amount_bank']):
        return 'Missing in Bank'
    elif row['amount_bank'] != row['amount_ledger']:
        return 'Amount Mismatch'
    elif row['date_bank'] != row['date_ledger']:
        return 'Date Mismatch'
    else:
        return 'Matched'

merged['root_cause'] = merged.apply(root_cause, axis=1)

print("\nReconciliation Results:")
print(merged)

# ---------------------------------------------------
# 5) ANOMALY DETECTION
# ---------------------------------------------------
print("\nTraining anomaly detection model...")

cfg = AnomalyConfig(
    contamination=0.15,
    random_state=42
)

detector = RecoAnomalyDetector(cfg)

# Step 1: Train the model on MATCHED records only
detector.fit(merged)

# Step 2: Score the entire dataset
scored = detector.score(merged)

print("\nTop Anomalies:")
print(scored.head(10))

# Save anomaly output
scored.to_csv('../data/reconciliation_with_anomalies.csv', index=False)
print("\n✅ Saved: reconciliation_with_anomalies.csv")

# ---------------------------------------------------
# 6) NLP TRANSACTION CATEGORIZATION
# ---------------------------------------------------
print("\nTraining Transaction Category Classifier...")

clf = TransactionClassifier()
clf.train(transactions_df)

transactions_with_predictions = clf.add_predictions(transactions_df)

print("\nPredicted Transaction Categories:")
print(transactions_with_predictions[['ref', 'remark', 'category', 'predicted_category']])

transactions_with_predictions.to_csv('../data/transactions_with_predictions.csv', index=False)
print("\n✅ Saved: transactions_with_predictions.csv")

# ---------------------------------------------------
# 7) SMART RECOMMENDATION ENGINE
# ---------------------------------------------------
print("\nGenerating Smart Recommendations...")

reco_engine = RecommendationEngine()

final_df = reco_engine.add_recommendations(scored)

# Save the final combined report
final_df.to_csv('../data/reconciliation_final_report.csv', index=False)

print("\n✅ Saved: reconciliation_final_report.csv")
print("\nTop rows with recommendations:")
print(final_df[['ref', 'root_cause', 'anomaly_reason', 'recommendation']].head(10))
