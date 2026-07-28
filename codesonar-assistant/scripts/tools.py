"""
tools.py

Reusable helper functions for the CodeSonar AI Assistant.
"""

import pandas as pd


def get_total_issues(df):
    """Return total number of issues."""

    return {
        "answer": f"Total issues: {len(df)}",
        "count": len(df),
        "rows": []
    }


def get_pending_issues(df):
    """Return pending issues."""

    pending = df[
        df["Status"].str.lower() == "pending"
    ]

    return {
        "answer": f"There are {len(pending)} pending issue(s).",
        "count": len(pending),
        "rows": pending.to_dict("records")
    }


def get_done_issues(df):
    """Return completed issues."""

    done = df[
        df["Status"].str.lower() == "done"
    ]

    return {
        "answer": f"There are {len(done)} completed issue(s).",
        "count": len(done),
        "rows": done.to_dict("records")
    }


def owner_summary(df):
    """
    Owner-wise assignment summary.
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

    return {
        "answer": "Owner summary generated.",
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


def search_by_owner(df, owner):
    """
    Search issues assigned to an owner.
    """

    result = df[
        df["Owner"].str.lower() == owner.lower()
    ]

    if result.empty:
        return {
            "answer": f"No issues found for {owner}.",
            "count": 0,
            "rows": []
        }

    class_summary = (
        result.groupby("class")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(5)
    )

    return {
        "answer": (
            f"{owner} has {len(result)} assigned issue(s).\n"
            "Top issue classes shown below."
        ),
        "count": len(result),
        "rows": class_summary.to_dict("records")
    }


def search_by_class(df, issue_class):
    """
    Search issues by CodeSonar class.
    """

    result = df[
        df["class"].str.contains(
            issue_class,
            case=False,
            na=False
        )
    ]

    if result.empty:
        return {
            "answer": f"No issues found for {issue_class}.",
            "count": 0,
            "rows": []
        }

    owners = (
        result.groupby("Owner")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(5)
    )

    return {
        "answer": (
            f"{issue_class}: {len(result)} issue(s) found.\n"
            "Owner distribution:"
        ),
        "count": len(result),
        "rows": owners.to_dict("records")
    }

def search_by_priority(df, priority):
    """
    Search issues by priority.
    """

    result = df[
        df["priority"].str.contains(priority, case=False, na=False)
    ]

    return {
        "answer": f"Found {len(result)} issue(s).",
        "count": len(result),
        "rows": result.to_dict("records")
    }
def pending_by_owner(df, owner):
    """
    Pending issues for a specific owner.
    """

    result = df[
        (df["Owner"].str.lower() == owner.lower()) &
        (df["Status"].str.lower() == "pending")
    ]

    return {
        "answer": f"{owner} has {len(result)} pending issue(s).",
        "count": len(result),
        "rows": result.head(10).to_dict("records")
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

def search_issues(df, entities):
    """
    Generic filtering engine.
    """

    result = df.copy()

    if entities["owner"]:
        result = result[
            result["Owner"].str.lower() == entities["owner"].lower()
        ]

    if entities["priority"]:
        result = result[
            result["priority"].str.lower() == entities["priority"].lower()
        ]

    if entities["status"]:
        result = result[
            result["Status"].str.lower() == entities["status"].lower()
        ]

    if entities["class"]:
        result = result[
            result["class"].str.contains(
                entities["class"],
                case=False,
                na=False
            )
        ]

    if result.empty:
        return {
            "answer": "No matching issues found.",
            "count": 0,
            "rows": []
        }

    preview_cols = [
        "id",
        "class",
        "priority",
        "Owner",
        "Status",
        "file",
        "line number"
    ]

    preview_cols = [c for c in preview_cols if c in result.columns]

    return {
        "answer": f"Found {len(result)} matching issue(s). Showing first 10.",
        "count": len(result),
        "rows": result[preview_cols].head(10).to_dict("records")
    }


def top_risky_files(df, limit=10):
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


def file_summary(df, filename):
    """
    Show all issues for a file along with the top issue classes.
    """

    if "file" not in df.columns:
        return {
            "answer": "File column not found.",
            "count": 0,
            "rows": []
        }

    result = df[
        df["file"].str.lower() == filename.lower()
    ]

    if result.empty:
        return {
            "answer": f"No issues found for {filename}.",
            "count": 0,
            "rows": []
        }

    class_summary = (
        result.groupby("class")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )

    return {
        "answer": (
            f"{filename} has {len(result)} issue(s). "
            "Top issue classes are shown below."
        ),
        "count": len(result),
        "rows": class_summary.to_dict("records")
    }


def file_issues(df, filename):
    """
    Return actual issues for a file.
    """

    result = df[df["file"].str.lower() == filename.lower()]

    if result.empty:
        return {
            "answer": f"No issues found for {filename}.",
            "count": 0,
            "rows": []
        }

    columns = [
        "id",
        "class",
        "procedure",
        "line number",
        "priority",
        "Status"
    ]

    columns = [c for c in columns if c in result.columns]

    return {
        "answer": f"Found {len(result)} issues in {filename}.",
        "count": len(result),
        "rows": result[columns].head(20).to_dict("records")
    }


def issue_details(df, issue_id):
    """
    Return complete information for a specific issue ID.
    """

    result = df[df["id"].astype(str) == str(issue_id)]

    if result.empty:
        return {
            "answer": f"Issue {issue_id} not found.",
            "count": 0,
            "rows": []
        }

    columns = [
        "id",
        "class",
        "file",
        "procedure",
        "line number",
        "priority",
        "Owner",
        "Status",
        "finding",
        "url",
    ]

    columns = [c for c in columns if c in result.columns]

    return {
        "answer": f"Issue {issue_id} details.",
        "count": 1,
        "rows": result[columns].to_dict("records")
    }


def issues_by_class(df, issue_class):
    """
    Return all issues belonging to a specific CodeSonar class.
    """

    result = df[
        df["class"].str.contains(issue_class, case=False, na=False)
    ]

    if result.empty:
        return {
            "answer": f"No '{issue_class}' issues found.",
            "count": 0,
            "rows": []
        }

    columns = [
        "id",
        "class",
        "file",
        "procedure",
        "line number",
        "priority",
        "Owner",
        "Status",
    ]

    columns = [c for c in columns if c in result.columns]

    return {
        "answer": f"Found {len(result)} '{issue_class}' issue(s).",
        "count": len(result),
        "rows": result[columns].head(20).to_dict("records")
    }