"""
Builds data/ravenstack.db (SQLite) from the 5 source CSVs published as the
"RavenStack" dataset by River @ Rivalytics on Kaggle:
https://www.kaggle.com/datasets/rivalytics/saas-subscription-and-churn-analytics-dataset

Run this once after placing the 5 CSVs in this same data/ folder:
    ravenstack_accounts.csv
    ravenstack_subscriptions.csv
    ravenstack_feature_usage.csv
    ravenstack_support_tickets.csv
    ravenstack_churn_events.csv
"""

import pandas as pd
import sqlite3
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "ravenstack.db")

FILES = {
    "accounts": "ravenstack_accounts.csv",
    "subscriptions": "ravenstack_subscriptions.csv",
    "feature_usage": "ravenstack_feature_usage.csv",
    "support_tickets": "ravenstack_support_tickets.csv",
    "churn_events": "ravenstack_churn_events.csv",
}

missing = [f for f in FILES.values() if not os.path.exists(os.path.join(HERE, f))]
if missing:
    raise FileNotFoundError(
        f"Missing source CSV(s): {missing}. Download the RavenStack dataset from Kaggle "
        f"and place the CSVs in {HERE}/ before running this script."
    )

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
for table_name, filename in FILES.items():
    df = pd.read_csv(os.path.join(HERE, filename))
    df.to_sql(table_name, conn, index=False)
    print(f"{table_name:18s} -> {len(df):>7,} rows  (from {filename})")

cur = conn.cursor()
for stmt in [
    "CREATE INDEX idx_subs_account ON subscriptions(account_id);",
    "CREATE INDEX idx_feat_sub ON feature_usage(subscription_id);",
    "CREATE INDEX idx_tick_account ON support_tickets(account_id);",
    "CREATE INDEX idx_churn_account ON churn_events(account_id);",
]:
    cur.execute(stmt)
conn.commit()
conn.close()

print(f"\nSQLite DB written to: {DB_PATH}")
