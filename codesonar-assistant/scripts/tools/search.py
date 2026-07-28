"""
Search and entity-extraction handlers.
"""

import re

from query import (
    search_by_class,
    search_by_owner,
    search_by_priority,
    search_by_status,
)
from query_parser import extract_filters


def normalize(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def extract_entities(df, query):
    """
    Extract all entities mentioned in the query.

    Returns:
    {
        "owner": "...",
        "priority": "...",
        "class": "...",
        "status": "..."
    }
    """

    query = normalize(query)

    entities = {
        "owner": None,
        "priority": None,
        "class": None,
        "status": None
    }

    if "Owner" in df.columns:

        owners = (
            df["Owner"]
            .dropna()
            .astype(str)
            .unique()
        )

        for owner in owners:

            if normalize(owner) in query:
                entities["owner"] = owner
                break

    if "priority" in df.columns:

        priorities = (
            df["priority"]
            .dropna()
            .astype(str)
            .unique()
        )

        for priority in priorities:

            if normalize(priority) in query:
                entities["priority"] = priority
                break

    if "class" in df.columns:

        classes = (
            df["class"]
            .dropna()
            .astype(str)
            .unique()
        )

        classes = sorted(classes, key=len, reverse=True)

        for cls in classes:

            if normalize(cls) in query:
                entities["class"] = cls
                break

    if "pending" in query:
        entities["status"] = "Pending"

    elif "done" in query:
        entities["status"] = "Done"

    elif "closed" in query:
        entities["status"] = "Done"

    return entities


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


def process_query(df, query):
    """
    Generic natural language search supporting multiple filters.
    """

    filters = extract_filters(query)

    result = df.copy()

    if "Owner" in filters:
        result = search_by_owner(result, filters["Owner"])

    if "Status" in filters:
        result = search_by_status(result, filters["Status"])

    if "priority" in filters:
        result = search_by_priority(result, filters["priority"])

    if "class" in filters:
        result = search_by_class(result, filters["class"])

    return result
