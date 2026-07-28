"""
Analytics-focused handlers.
"""


def top_files(df, limit=10):
    """
    Return files with the highest number of CodeSonar findings.
    """

    if "file" not in df.columns:
        return {
            "answer": "File column not found.",
            "count": 0,
            "rows": []
        }

    summary = (
        df.groupby("file")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
        .head(limit)
    )

    return {
        "answer": f"Top {len(summary)} files with the most issues.",
        "count": len(summary),
        "rows": summary.to_dict("records")
    }


def top_classes(df, top_n=10):
    """
    Return the top N most common CodeSonar issue classes.
    """

    if "class" not in df.columns:
        return {
            "answer": "Class column not found.",
            "count": 0,
            "rows": []
        }

    summary = (
        df.groupby("class")
          .size()
          .reset_index(name="Count")
          .sort_values("Count", ascending=False)
          .head(top_n)
    )

    return {
        "answer": f"Top {len(summary)} issue classes.",
        "count": len(summary),
        "rows": summary.to_dict("records")
    }


def priority_summary(df):
    """
    Summary by priority.
    """

    summary = (
        df.groupby("priority")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    return {
        "answer": "Priority summary generated.",
        "count": len(summary),
        "rows": summary.to_dict("records")
    }


def highest_workload(df):
    """
    Find owner with highest workload.
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
        .sort_values("Assigned", ascending=False)
    )

    if summary.empty:

        return {
            "answer": "No owners found.",
            "count": 0,
            "rows": []
        }

    top = summary.iloc[0]

    return {
        "answer": f"{top['Owner']} has the highest workload ({top['Assigned']} issues).",
        "count": int(top["Assigned"]),
        "rows": summary.to_dict("records")
    }


def owner_priority_summary(df, priority="HB_PRIO_1"):
    """
    Show owner-wise issue count for a given priority.
    """

    if "Owner" not in df.columns or "priority" not in df.columns:
        return {
            "answer": "Required columns not found.",
            "count": 0,
            "rows": []
        }

    summary = (
        df[df["priority"] == priority]
        .groupby("Owner")
        .size()
        .reset_index(name=priority)
        .sort_values(priority, ascending=False)
    )

    if summary.empty:
        return {
            "answer": f"No {priority} issues found.",
            "count": 0,
            "rows": []
        }

    top = summary.iloc[0]

    return {
        "answer": f"{top['Owner']} has the most {priority} issues ({top[priority]}).",
        "count": len(summary),
        "rows": summary.to_dict("records")
    }


def class_summary(df):
    """
    Summary by issue class.
    """

    summary = (
        df.groupby("class")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    return {
        "answer": "Class summary generated.",
        "count": len(summary),
        "rows": summary.to_dict("records")
    }


def top_issue_classes(df, limit=10):
    """
    Return issue classes with the highest number of findings.
    """

    if "class" not in df.columns:
        return {
            "answer": "Class column not found.",
            "count": 0,
            "rows": []
        }

    summary = (
        df.groupby("class")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
        .head(limit)
    )

    return {
        "answer": f"Top {len(summary)} issue classes.",
        "count": len(summary),
        "rows": summary.to_dict("records")
    }
