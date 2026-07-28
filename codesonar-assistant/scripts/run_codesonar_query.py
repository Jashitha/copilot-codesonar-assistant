import sys
import pandas as pd

from tools.analytics import highest_workload
from tools.search import process_query

TRACKER = "output/Master_Tracker.xlsx"

df = pd.read_excel(TRACKER, dtype={"id": str})

query = " ".join(sys.argv[1:]).lower()

if "total" in query or "how many issues" in query:
    print({"answer": f"Total issues: {len(df)}", "count": len(df), "rows": []})

elif "pending" in query:
    pending = len(df[df["Status"].str.lower() == "pending"])
    print({"answer": f"There are {pending} pending issue(s).", "count": pending, "rows": []})

elif "highest workload" in query:
    print(highest_workload(df))

else:
    result = process_query(df, query)
    print(result.head(10))
