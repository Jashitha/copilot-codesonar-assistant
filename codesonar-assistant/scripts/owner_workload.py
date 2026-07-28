import re
import pandas as pd


def owner_workload(df, query):

    q = query.lower()

    m = re.search(r'\bfor\s+([a-zA-Z0-9_]+)', q)

    if not m:
        m = re.search(r'\bowner\s+([a-zA-Z0-9_]+)', q)

    if not m:
        return {
            "answer": "Please specify an owner.",
            "count": 0,
            "rows": []
        }

    owner = m.group(1)

    result = df[
        df["Owner"].astype(str).str.lower() == owner.lower()
    ]

    if result.empty:
        return {
            "answer": f"No issues assigned to {owner}.",
            "count": 0,
            "rows": []
        }

    total = len(result)

    pending = len(
        result[result["Status"].astype(str).str.lower() == "pending"]
    )

    done = len(
        result[result["Status"].astype(str).str.lower() == "done"]
    )

    hb1 = len(
        result[result["priority"] == "HB_PRIO_1"]
    )

    hb2 = len(
        result[result["priority"] == "HB_PRIO_2"]
    )

    top_file = (
        result["file"]
        .value_counts()
        .head(1)
    )

    top_class = (
        result["class"]
        .value_counts()
        .head(1)
    )

    return {
        "answer": f"Owner {owner} workload",
        "count": total,
        "rows": [
            {
                "Metric": "Assigned",
                "Value": total
            },
            {
                "Metric": "Pending",
                "Value": pending
            },
            {
                "Metric": "Done",
                "Value": done
            },
            {
                "Metric": "HB_PRIO_1",
                "Value": hb1
            },
            {
                "Metric": "HB_PRIO_2",
                "Value": hb2
            },
            {
                "Metric": "Top File",
                "Value": f"{top_file.index[0]} ({top_file.iloc[0]})"
            },
            {
                "Metric": "Top Issue Class",
                "Value": f"{top_class.index[0]} ({top_class.iloc[0]})"
            }
        ]
    }