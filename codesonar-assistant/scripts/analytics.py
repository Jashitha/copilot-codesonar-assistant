import re

def owner_progress(df, query):

    q = query.lower()

    # Extract owner
    m = re.search(r"\bfor\s+([a-zA-Z0-9_]+)", q)

    if not m:
        m = re.search(r"\bowner\s+([a-zA-Z0-9_]+)", q)

    if not m:
        m = re.search(r"\bof\s+([a-zA-Z0-9_]+)", q)

    if not m:
        return {
            "answer": "Please specify an owner.",
            "count": 0,
            "rows": []
        }

    owner = m.group(1)

    data = df[
        df["Owner"].astype(str).str.lower() == owner.lower()
    ]

    if data.empty:
        return {
            "answer": f"No issues assigned to {owner}.",
            "count": 0,
            "rows": []
        }

    total = len(data)

    pending = len(
        data[data["Status"].astype(str).str.lower() == "pending"]
    )

    done = len(
        data[data["Status"].astype(str).str.lower() == "done"]
    )

    hb1 = len(
        data[data["priority"] == "HB_PRIO_1"]
    )

    hb2 = len(
        data[data["priority"] == "HB_PRIO_2"]
    )

    completion = round(done * 100 / total, 2) if total else 0

    return {
        "answer": f"Owner {owner} progress",
        "count": total,
        "rows": [
            {"Metric": "Assigned", "Value": total},
            {"Metric": "Completed", "Value": done},
            {"Metric": "Pending", "Value": pending},
            {"Metric": "Completion %", "Value": f"{completion}%"},
            {"Metric": "HB_PRIO_1 Pending", "Value": hb1},
            {"Metric": "HB_PRIO_2 Pending", "Value": hb2},
        ]
    }