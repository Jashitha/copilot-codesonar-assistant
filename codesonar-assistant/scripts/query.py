def search_by_class(df, class_name):
    return df[df["class"].str.contains(class_name, case=False, na=False)]


def search_by_owner(df, owner):
    return df[df["Owner"].str.lower() == owner.lower()]


def search_by_priority(df, priority):
    return df[df["priority"] == priority]


def search_by_status(df, status):
    return df[df["Status"].str.lower() == status.lower()]


def search_by_file(df, filename):
    return df[df["file"].str.lower() == filename.lower()]


import re


def similar_issues(df, query):
    """
    Show issues having the same class as the given issue ID.
    """

    m = re.search(r'(\d+\.\d+)', query)

    if not m:
        return {
            "answer": "Please provide a valid issue ID.",
            "count": 0,
            "rows": []
        }

    issue_id = m.group(1)

    issue = df[df["id"] == issue_id]

    if issue.empty:
        return {
            "answer": f"Issue {issue_id} not found.",
            "count": 0,
            "rows": []
        }

    issue_class = issue.iloc[0]["class"]

    matches = df[
        (df["class"] == issue_class) &
        (df["id"] != issue_id)
    ].copy()

    cols = [
        "id",
        "class",
        "priority",
        "Owner",
        "Status",
        "file",
        "line number",
    ]

    cols = [c for c in cols if c in matches.columns]

    return {
        "answer": f"Found {len(matches)} similar issue(s) with class '{issue_class}'.",
        "count": len(matches),
        "rows": matches[cols].head(20).to_dict("records")
    }
import re

def similar_issues(df, query):
    """
    Show issues having the same class as the given issue ID.
    """

    m = re.search(r'(\d+\.\d+)', query)

    if not m:
        return {
            "answer": "Please provide a valid issue ID.",
            "count": 0,
            "rows": []
        }

    issue_id = m.group(1)

    issue = df[df["id"] == issue_id]

    if issue.empty:
        return {
            "answer": f"Issue {issue_id} not found.",
            "count": 0,
            "rows": []
        }

    issue_class = issue.iloc[0]["class"]

    matches = df[df["class"] == issue_class].copy()

    cols = [
        "id",
        "class",
        "priority",
        "Owner",
        "Status",
        "file",
        "line number"
    ]

    cols = [c for c in cols if c in matches.columns]

    return {
        "answer": f"Found {len(matches)} similar issue(s) with class '{issue_class}'.",
        "count": len(matches),
        "rows": matches[cols].to_dict("records")
    }
