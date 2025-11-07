# src/generate_large_dataset.py
import os, random
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

# ---------- Where to save ----------
OUT_DIR = "../data"
os.makedirs(OUT_DIR, exist_ok=True)

N = 1500  # rows for bank + ledger
START = datetime(2025, 1, 1)
END = datetime(2025, 6, 30)

# ---------- Helpers ----------
def random_date(start: datetime, end: datetime) -> datetime:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def choose_weighted(items, probs):
    return np.random.choice(items, p=probs)

def clamp_amount(x, lo, hi):
    return int(max(lo, min(hi, x)))

# Transaction “types” to drive realistic amounts & narration
TX_TYPES = [
    ("Salary",            (40000, 120000),  "Salary Credit",         ["Company Payroll", "HRMS Salary", "Payroll System"]),
    ("ATM",               (-5000, -500),    "ATM Withdrawal",         ["SBI ATM", "HDFC ATM", "ICICI ATM", "Axis ATM"]),
    ("Shopping",          (-8000, -500),    "Online Shopping",        ["Amazon", "Flipkart", "Myntra", "Ajio"]),
    ("Utility",           (-6000, -300),    "Utility Bill",           ["Electricity Board", "Water Dept", "Gas Agency"]),
    ("Project Income",    (2000, 50000),    "Project Income",         ["Client A", "Client B", "ProjectCorp", "InnovaTech"]),
    ("Bank Charge",       (-500, -50),      "Bank Fee",               ["Monthly fee", "Service charge", "SMS charge"]),
    ("Interest",          (50, 2000),       "Interest Credit",        ["Quarterly interest", "Savings interest"]),
    ("UPI Transfer",      (-7000, -100),    "UPI Transfer",           ["to Rahul", "to Neha", "to Vendor", "to Landlord"]),
    ("Refund",            (100, 10000),     "Refund",                 ["Amazon refund", "Payment reversal", "Chargeback"]),
    ("EMI",               (-15000, -2000),  "Loan EMI",               ["HDFC Loan", "ICICI Loan", "Bajaj Finance"]),
    ("Fuel",              (-3000, -300),    "Fuel Purchase",          ["HP Petrol", "Indian Oil", "BPCL"]),
    ("Food",              (-4000, -200),    "Food / Dining",          ["Zomato", "Swiggy", "Restaurant"]),
    ("Wallet",            (-5000, -200),    "Wallet Top-up",          ["Paytm", "PhonePe", "GPay"]),
    ("Medical",           (-15000, -500),   "Medical / Pharmacy",     ["Apollo", "MedPlus", "Practo"]),
    ("Travel",            (-60000, -1000),  "Travel Booking",         ["MakeMyTrip", "IRCTC", "Uber", "Ola"]),
]

TX_NAMES = [t[0] for t in TX_TYPES]
TX_PROBS = np.array([0.12, 0.07, 0.10, 0.08, 0.08, 0.05, 0.04, 0.10, 0.04, 0.05, 0.05, 0.06, 0.06, 0.04, 0.06], dtype=float)
TX_PROBS = TX_PROBS / TX_PROBS.sum()  # normalize

ACCOUNTS = [202001234567, 202001234568, 202001234569]

# ---------- Generate Bank Statement (N rows) ----------
bank_rows = []
for i in range(N):
    ref = f"TXN{200000 + i}"
    tname = choose_weighted(TX_NAMES, TX_PROBS)
    ttype = next(t for t in TX_TYPES if t[0] == tname)
    lo, hi = ttype[1]
    amt = random.randint(lo, hi)
    # Add slight cyclic patterns (salary once a month more likely)
    date = random_date(START, END)
    if tname == "Salary" and date.day < 4:  # early month bias
        date = date.replace(day=random.randint(1, 5))
        amt = clamp_amount(int(np.random.normal(65000, 8000)), lo, hi)

    # Narration string
    narr = f"{ttype[2]} - {random.choice(ttype[3])}"

    bank_rows.append({
        "date_bank": date.date().isoformat(),
        "ref": ref,
        "amount_bank": amt,
        "account_bank": random.choice(ACCOUNTS),
        "narration": narr
    })

bank_df = pd.DataFrame(bank_rows)

# ---------- Generate Ledger from Bank with anomalies ----------
# Probabilities (summing to <= 1.0, rest are perfect matches)
P_MISSING_LEDGER = 0.05     # bank-only
P_AMOUNT_MISMATCH = 0.12
P_DATE_MISMATCH   = 0.08
P_DUP_LEDGER      = 0.03    # duplicate ledger rows for same ref
# extra ghost ledger rows (ledger-only, refs that don’t exist in bank)
N_GHOST_LEDGER = int(0.02 * N)

ledger_rows = []

for i, row in bank_df.iterrows():
    r = random.random()
    ref = row["ref"]

    # Missing in ledger (skip)
    if r < P_MISSING_LEDGER:
        continue

    r2 = random.random()
    # Start from a perfect match
    led_amount = row["amount_bank"]
    led_date = datetime.fromisoformat(row["date_bank"])
    category = choose_weighted(
        ["Salary", "ATM", "Expense", "Utility Bills", "Project Income", "Charge", "Misc"],
        [0.12, 0.08, 0.25, 0.15, 0.15, 0.15, 0.10]
    )
    # remark text richer for ledger
    remark = random.choice([
        "Cleared", "Posted", "Auto-matched", "Manual entry",
        "Vendor invoice", "Reconciled", "Pending approval"
    ])

    # Amount mismatch
    if r2 < P_AMOUNT_MISMATCH:
        led_amount = row["amount_bank"] + random.randint(-1500, 1500)
        if led_amount == row["amount_bank"]:
            led_amount += random.choice([-250, 250])

    # Date mismatch
    elif r2 < P_AMOUNT_MISMATCH + P_DATE_MISMATCH:
        led_date = led_date + timedelta(days=random.randint(-7, 7))

    # (Else: matched)

    ledger_rows.append({
        "date_ledger": led_date.date().isoformat(),
        "ref": ref,
        "amount_ledger": int(led_amount),
        "account_ledger": random.choice(ACCOUNTS),
        "category": category,
        "remark": remark
    })

    # Duplicate ledger row (same ref) 3% chance
    if random.random() < P_DUP_LEDGER:
        dup_amt = led_amount + random.choice([0, 100, -100, 250, -250])
        dup_date = led_date + timedelta(days=random.choice([0, 1, -1]))
        ledger_rows.append({
            "date_ledger": dup_date.date().isoformat(),
            "ref": ref,
            "amount_ledger": int(dup_amt),
            "account_ledger": random.choice(ACCOUNTS),
            "category": category,
            "remark": "Duplicate/adjustment"
        })

# Add ghost ledger rows (no bank)
for j in range(N_GHOST_LEDGER):
    ref = f"LGH{300000 + j}"
    date = random_date(START, END)
    amt = random.randint(-10000, 25000)
    ledger_rows.append({
        "date_ledger": date.date().isoformat(),
        "ref": ref,
        "amount_ledger": int(amt),
        "account_ledger": random.choice(ACCOUNTS),
        "category": choose_weighted(
            ["Expense", "Utility Bills", "Project Income", "Charge", "Misc"], 
            [0.3, 0.2, 0.15, 0.2, 0.15]
        ),
        "remark": random.choice(["Manual journal", "Vendor accrual", "Pending doc", "Unmapped entry"])
    })

ledger_df = pd.DataFrame(ledger_rows)

# ---------- Transactions (for NLP classifier) ----------
TX_REMARKS = [
    "Salary credited", "UPI to grocery", "Electricity bill payment",
    "Amazon order", "Loan EMI debit", "Restaurant dinner",
    "Fuel refill HP petrol", "Refund from Amazon", "Wallet top-up",
    "Mobile recharge", "Insurance premium debit",
    "Flight booking MakeMyTrip", "Zomato lunch", "Swiggy dinner",
    "GST tax payment", "Office stationery", "Vendor payment",
    "Consulting fee", "Internet broadband bill", "Netflix subscription",
    "Prime Video subscription", "Gym membership", "Parking fee"
]
TX_CATS = [
    "Salary", "Grocery", "Utility", "Shopping", "EMI", "Food",
    "Fuel", "Refund", "Wallet", "Recharge", "Insurance", "Travel",
    "Tax", "Business Expense", "Service Expense", "Subscription", "Parking"
]
TX_CAT_PROBS = np.array(
    [0.10, 0.06, 0.08, 0.10, 0.08, 0.10, 0.06, 0.04, 0.05, 0.05, 0.05, 0.08, 0.04, 0.05, 0.04, 0.08, 0.04],
    dtype=float
)
TX_CAT_PROBS = TX_CAT_PROBS / TX_CAT_PROBS.sum()

tx_rows = []
for i in range(N):
    ref = f"TXNP{500000 + i}"
    cat = np.random.choice(TX_CATS, p=TX_CAT_PROBS)
    remark = random.choice(TX_REMARKS)
    tx_rows.append({
        "ref": ref,
        "remark": remark,
        "category": cat
    })

tx_df = pd.DataFrame(tx_rows)

# ---------- Save ----------
bank_path = os.path.join(OUT_DIR, "bank_statement.csv")
ledger_path = os.path.join(OUT_DIR, "ledger_entries.csv")
tx_path = os.path.join(OUT_DIR, "transactions.csv")

bank_df.to_csv(bank_path, index=False)
ledger_df.to_csv(ledger_path, index=False)
tx_df.to_csv(tx_path, index=False)

print("\n✅ Enterprise dataset generated successfully!")
print(f"  • {bank_path} -> {len(bank_df)} rows")
print(f"  • {ledger_path} -> {len(ledger_df)} rows")
print(f"  • {tx_path} -> {len(tx_df)} rows")
print("\nBreakdown:")
print(f"  • Perfect matches  ≈ {int(N*(1 - (0.05+0.12+0.08+0.03)))} rows")
print(f"  • Amount mismatch  ≈ {int(N*0.12)} rows")
print(f"  • Date mismatch    ≈ {int(N*0.08)} rows")
print(f"  • Missing ledger   ≈ {int(N*0.05)} rows")
print(f"  • Duplicate ledger ≈ {int(N*0.03)} rows")
print(f"  • Ghost ledger     = {int(0.02*N)} rows")
