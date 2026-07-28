from query import (
    search_by_class,
    search_by_owner,
    search_by_priority,
    search_by_status,
    search_by_file,
)
from query_parser import extract_filters
from issue_explanations import ISSUE_EXPLANATIONS


def process_query(df, query):
    """
    Generic natural language search supporting multiple filters.
    """

    filters = extract_filters(query)

    result = df.copy()

    # Owner
    if "Owner" in filters:
        result = search_by_owner(result, filters["Owner"])

    # Status
    if "Status" in filters:
        result = search_by_status(result, filters["Status"])

    # Priority
    if "priority" in filters:
        result = search_by_priority(result, filters["priority"])

    # Class
    if "class" in filters:
        result = search_by_class(result, filters["class"])

    return result


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
import re

def recommend_next_issue(df, query):
    # Extract owner (a, b, c...)
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
def explain_issue(df, query):

    import re

    match = re.search(r'(\d+(?:\.\d+)?)', query)

    if not match:
        return {
            "answer": "Please provide a valid issue ID.",
            "count": 0,
            "rows": []
        }

    issue_id = match.group(1)

    row = df[df["id"].astype(str) == issue_id]

    if row.empty:
        return {
            "answer": "Issue not found.",
            "count": 0,
            "rows": []
        }

    issue = row.iloc[0]

    explanation = ISSUE_EXPLANATIONS.get(
        issue["class"],
        {
            "why": "No explanation available.",
            "risk": "",
            "fix": ""
        }
    )

    return {
        "answer": f"Explanation for issue {issue_id}.",
        "count": 1,
        "rows": [{
            "id": issue["id"],
            "class": issue["class"],
            "file": issue["file"],
            "procedure": issue["procedure"],
            "priority": issue["priority"],
            "why": explanation["why"],
            "risk": explanation["risk"],
            "recommended_fix": explanation["fix"]
        }]
    }
def fix_recommendation(query):

    q = query.lower()

    fixes = {

        "buffer overrun": {
            "Issue": "Buffer Overrun",
            "Root Cause": "Writing past the allocated buffer.",
            "Risk": "Memory corruption, crashes, security vulnerabilities.",
            "Recommended Fix": "Validate buffer sizes, use snprintf(), memcpy_s(), strncpy(), and perform bounds checking."
        },

        "buffer underrun": {
            "Issue": "Buffer Underrun",
            "Root Cause": "Reading or writing before the beginning of a buffer.",
            "Risk": "Undefined behavior and memory corruption.",
            "Recommended Fix": "Validate indexes and pointer arithmetic before access."
        },

        "use after free": {
            "Issue": "Use After Free",
            "Root Cause": "Accessing memory after it has been freed.",
            "Risk": "Crashes, memory corruption, exploitable vulnerabilities.",
            "Recommended Fix": "Set pointers to NULL after free() and avoid accessing freed memory."
        },

        "strcpy": {
            "Issue": "Use of strcpy",
            "Root Cause": "strcpy() performs no bounds checking.",
            "Risk": "Buffer overflow.",
            "Recommended Fix": "Replace strcpy() with strncpy() or snprintf()."
        },

        "strcmp": {
            "Issue": "Use of strcmp",
            "Root Cause": "Possible NULL pointer or unsafe comparison.",
            "Risk": "Unexpected behavior.",
            "Recommended Fix": "Validate pointers before calling strcmp()."
        },

        "null": {
            "Issue": "Null Dereference",
            "Root Cause": "Pointer may be NULL before dereference.",
            "Risk": "Program crash.",
            "Recommended Fix": "Check pointer != NULL before use."
        }
    }

    for key, value in fixes.items():
        if key in q:
            return {
                "answer": f"Recommended fix for {value['Issue']}.",
                "count": 1,
                "rows": [value]
            }

    return {
        "answer": "No recommendation available.",
        "count": 0,
        "rows": []
    }