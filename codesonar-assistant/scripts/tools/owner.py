import re


def extract_owner(query):

    q = query.lower()

    patterns = [
        r"assigned to\s+(\w+)",
        r"owner\s+(\w+)",
        r"assigned\s+(\w+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return m.group(1)

    return None


def owner_summary(df, query):

    owner = extract_owner(query)

    if owner is None:
        return {
            "answer": "Please specify an owner.",
            "count": 0,
            "rows": []
        }

    data = df[df["Owner"].str.lower() == owner.lower()]

    if data.empty:
        return {
            "answer": f"No issues assigned to {owner}.",
            "count": 0,
            "rows": []
        }

    priority = (
        data.groupby("priority")
            .size()
            .reset_index(name="Issues")
    )

    top_class = (
        data.groupby("class")
            .size()
            .reset_index(name="Count")
            .sort_values("Count", ascending=False)
            .head(3)
    )

    top_file = (
        data.groupby("file")
            .size()
            .reset_index(name="Count")
            .sort_values("Count", ascending=False)
            .head(3)
    )

    rows = []

    rows.extend(priority.to_dict("records"))
    rows.extend(top_class.to_dict("records"))
    rows.extend(top_file.to_dict("records"))

    return {
        "answer": f"{owner} has {len(data)} assigned issues.",
        "count": len(data),
        "rows": rows,
    }


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


def owner_progress(df, query):

    q = query.lower()

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


def recommend_owner(df):
    """
    Recommend the owner with the least workload.
    """

    if "Owner" not in df.columns:
        return {
            "answer": "Owner column not found.",
            "count": 0,
            "rows": []
        }

    summary = (
        df.groupby("Owner")
        .size()
        .reset_index(name="Assigned")
        .sort_values("Assigned")
    )

    if summary.empty:
        return {
            "answer": "No owners found.",
            "count": 0,
            "rows": []
        }

    recommended = summary.iloc[0]

    return {
        "answer": (
            f"Recommended owner: {recommended['Owner']} "
            f"(currently has {recommended['Assigned']} assigned issues)."
        ),
        "count": len(summary),
        "rows": summary.to_dict("records")
    }


def recommend_next_issue(df, query):

    match = re.search(r"\b([a-z])\b$", query.lower())
    if not match:
        return {
            "answer": "Please specify an owner.",
            "count": 0,
            "rows": []
        }

    owner = match.group(1)

    issues = df[
        (df["Owner"].str.lower() == owner) &
        (df["Status"].str.lower() == "pending")
    ].copy()

    if issues.empty:
        return {
            "answer": f"No pending issues for {owner}.",
            "count": 0,
            "rows": []
        }

    priority_order = {
        "HB_PRIO_1": 1,
        "HB_PRIO_2": 2
    }

    issues["priority_rank"] = issues["priority"].map(priority_order)

    issues = issues.sort_values(
        by=["priority_rank", "score"],
        ascending=[True, False]
    )

    best = issues.head(1)

    return {
        "answer": f"Recommended next issue for {owner}.",
        "count": 1,
        "rows": best[[
            "id",
            "class",
            "priority",
            "score",
            "file",
            "line number",
            "procedure"
        ]].to_dict("records")
    }
