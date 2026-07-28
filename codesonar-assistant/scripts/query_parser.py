"""
Extract filters from a natural language query.
"""

import re


KNOWN_CLASSES = [
    "Buffer Overrun",
    "Buffer Underrun",
    "Use After Free",
    "Use of strcpy",
    "Use of strcmp",
    "Inappropriate Assignment Type",
    "Redundant Condition",
    "Unreachable Call",
    "Cast Alters Value",
    "Cast Removes const Qualifier",
    "Condition Contains Side Effects",
    "Side Effects in Logical Operand",
]

KNOWN_PRIORITIES = [
    "HB_PRIO_1",
    "HB_PRIO_2",
]

KNOWN_STATUS = [
    "Pending",
    "Done",
]


def extract_filters(query):

    q = query.lower()

    filters = {}

    # ---------------- Owner ----------------

    m = re.search(r"assigned to\s+(\w+)", q)

    if m:
        filters["Owner"] = m.group(1)

    # ---------------- Priority ----------------

    for p in KNOWN_PRIORITIES:

        if p.lower() in q:

            filters["priority"] = p

    # ---------------- Status ----------------

    if "pending" in q:
        filters["Status"] = "Pending"

    elif "done" in q:
        filters["Status"] = "Done"

    # ---------------- File ----------------

    m = re.search(r"(\w+\.c)", q)

    if m:
        filters["file"] = m.group(1)

    # ---------------- Class ----------------

    for cls in KNOWN_CLASSES:

        if cls.lower() in q:

            filters["class"] = cls

    return filters