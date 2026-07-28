"""
dispatcher.py

Routes detected intents to the appropriate tool.
"""

from tools import (
    class_summary,
    dashboard,
    explain_issue,
    extract_entities,
    file_issues,
    file_summary,
    fix_guide_batch,
    fix_guide_class,
    fix_guide_issue,
    fix_recommendation,
    highest_workload,
    issue_details,
    issues_by_class,
    owner_progress,
    owner_priority_summary,
    owner_summary,
    owner_workload,
    priority_summary,
    process_query,
    project_health,
    project_summary,
    recommend_next_issue,
    recommend_owner,
    search_issues,
    similar_issues,
    top_classes,
    top_files,
    top_issue_classes,
    trend_analysis,
)
from entry_extractor import extract_filename, extract_issue_id
from hotspot_analysis import hotspot_analysis
from tracker_workflow_runner import run_tracker_workflow


def dispatch(df, intent, query):
    """
    Dispatch the detected intent to the correct handler.
    """

    if intent == "issue_count":

        return {
            "answer": f"Total issues: {len(df)}",
            "count": len(df),
            "rows": []
        }

    elif intent == "pending_count":

        pending = len(
            df[df["Status"].str.lower() == "pending"]
        )

        return {
            "answer": f"There are {pending} pending issue(s).",
            "count": pending,
            "rows": []
        }

    elif intent == "done_count":

        done = len(
            df[df["Status"].str.lower() == "done"]
        )

        return {
            "answer": f"There are {done} completed issue(s).",
            "count": done,
            "rows": []
        }

    elif intent == "highest_workload":

        return highest_workload(df)

    elif intent == "search":

        entities = extract_entities(df, query)

        if any(entities.values()):
            return search_issues(df, entities)

        return process_query(df, query)
    
    elif intent == "top_classes":
        return top_classes(df)

    elif intent == "class_summary":
        return class_summary(df)

    elif intent == "priority_summary":
        return priority_summary(df)

    elif intent == "top_files":
        return top_files(df)

    elif intent == "top_issue_classes":
        return top_issue_classes(df)

    elif intent == "owner_priority_summary":
        return owner_priority_summary(df)

    elif intent == "recommend_owner":
        return recommend_owner(df)

    elif intent == "recommend_next_issue":
        return recommend_next_issue(df, query)

    elif intent == "fix_recommendation":
        return fix_recommendation(query)

    elif intent == "fix_guide_class":
        return fix_guide_class(df, query)

    elif intent == "fix_guide_issue":
        return fix_guide_issue(df, query)

    elif intent == "fix_guide_batch":
        return fix_guide_batch(df)

    elif intent == "similar_issues":
        return similar_issues(df, query)

    elif intent == "file_summary":

        filename = extract_filename(query)

        if filename:
            return file_summary(df, filename)

        return {
            "answer": "No filename found in the query.",
            "count": 0,
            "rows": []
        }

    elif intent == "issue_details":

        issue_id = extract_issue_id(query)

        if issue_id:
            return issue_details(df, issue_id)

        return {
            "answer": "Please provide a valid issue ID.",
            "count": 0,
            "rows": []
        }

    elif intent == "class_issues":

        q = query.lower()

        result = df.copy()

        # ---------------- Owner ----------------
        if "assigned to" in q:
            owner = q.split("assigned to")[-1].strip().split()[0]
            result = result[
                result["Owner"].astype(str).str.lower() == owner.lower()
            ]

        # ---------------- Status ----------------
        if "pending" in q:
            result = result[
                result["Status"].astype(str).str.lower() == "pending"
            ]

        elif "done" in q:
            result = result[
                result["Status"].astype(str).str.lower() == "done"
            ]

        # ---------------- Priority ----------------
        if "hb_prio_1" in q:
            result = result[result["priority"] == "HB_PRIO_1"]

        elif "hb_prio_2" in q:
            result = result[result["priority"] == "HB_PRIO_2"]

        # ---------------- File ----------------
        import re

        m = re.search(r'([A-Za-z0-9_\-]+\.c)', query)

        if m:
            filename = m.group(1)
            result = result[
                result["file"].astype(str).str.lower() == filename.lower()
            ]

        # ---------------- Issue Class ----------------
        classes = [
            "Buffer Overrun",
            "Buffer Underrun",
            "Use After Free",
            "Use of strcpy",
            "Use of strcmp",
            "Null Test After Dereference",
            "Inappropriate Assignment Type",
            "Cast Alters Value",
            "Cast Removes const Qualifier",
            "Redundant Condition",
            "Unreachable Call",
            "Condition Contains Side Effects",
            "Side Effects in Logical Operand",
            "Malformed switch Statement",
            "Conversion to Function Pointer",
            "Conversion from Function Pointer",
            "Function Pointer Conversion",
            "Implicit Function Declaration",
            "Multiple External Definitions",
            "Global Variable Declared with Different Types",
            "Non-const String Literal",
        ]

        for c in classes:
            if c.lower() in q:
                result = result[
                    result["class"].str.lower() == c.lower()
                ]
                break

        return {
            "answer": f"Found {len(result)} matching issue(s). Showing first 10.",
            "count": len(result),
            "rows": result.head(10)[[
                "id",
                "class",
                "priority",
                "Owner",
                "Status",
                "file",
                "line number",
            ]].to_dict(orient="records"),
        }
    elif intent == "owner_summary":
        return owner_summary(df, query)

    elif intent == "explain_issue":
        return explain_issue(df, query)
    elif intent == "dashboard":
        return dashboard(df)
    elif intent == "project_summary":
        return project_summary(df)
    elif intent == "trend_analysis":
        return trend_analysis(df)
    elif intent == "project_health":
        return project_health(df)
    elif intent == "owner_workload":
        return owner_workload(df, query)
    elif intent == "owner_progress":
        return owner_progress(df, query)
    elif intent == "hotspot_analysis":
        return hotspot_analysis(df)
    elif intent == "tracker_workflow":
        return run_tracker_workflow(query)

    else:

        result = process_query(df, query)

        return result