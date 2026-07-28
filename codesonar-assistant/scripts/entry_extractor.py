"""
entity_extractor.py

Extract Owner, Priority, Class and Status
from natural language.
"""

import re


def normalize(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def extract_filename(query):
    """
    Extract a source filename mentioned in the query.
    """

    match = re.search(r"\b([A-Za-z0-9_./-]+\.(?:c|cc|cpp|cxx|h|hpp))\b", str(query))

    if match:
        return match.group(1)

    return None


def extract_issue_id(query):
    """
    Extract an issue ID mentioned in the query.
    """

    match = re.search(r"\b(\d+\.\d+)\b", str(query))

    if match:
        return match.group(1)

    return None


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

    # -------------------
    # Owner
    # -------------------

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

    # -------------------
    # Priority
    # -------------------

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

    # -------------------
    # Class
    # -------------------

    if "class" in df.columns:

        classes = (
            df["class"]
            .dropna()
            .astype(str)
            .unique()
        )

        classes = sorted(classes,
                         key=len,
                         reverse=True)

        for cls in classes:

            if normalize(cls) in query:
                entities["class"] = cls
                break

    # -------------------
    # Status
    # -------------------

    if "pending" in query:
        entities["status"] = "Pending"

    elif "done" in query:
        entities["status"] = "Done"

    elif "closed" in query:
        entities["status"] = "Done"

    return entities