import json
import sys

import pandas as pd

FIELDS = [
    "session_dt", "conversion_dt", "register_date", "campaign_id", "page",
    "auto_city", "auto_country", "auto_state", "device_type", "sub1", "sub2", "sub3",
    "business_type", "credit_score", "industry", "loan_amount", "loan_reason",
    "monthly_revenue", "time_in_business", "fname", "lname", "cellphone",
]
SAMPLE_SIZE = 200
SEED = 42

data_path, out_path = sys.argv[1], sys.argv[2]
df = pd.read_csv(data_path, low_memory=False, usecols=FIELDS)
df = df.dropna(subset=["register_date", "cellphone", "campaign_id", "page", "session_dt"])
df = df.drop_duplicates(subset=["register_date", "cellphone"]).sample(SAMPLE_SIZE, random_state=SEED)

bodies = []
for row in df.to_dict(orient="records"):
    user = {k: (None if pd.isna(v) else v) for k, v in row.items()}
    user["campaign_id"] = int(row["campaign_id"])
    user["cellphone"] = int(row["cellphone"])
    bodies.append(json.dumps(user))

with open(out_path, "w") as f:
    json.dump(bodies, f)
