"""
intent.py

Detect the user's intent from a natural language question.
"""


def detect_intent(query: str) -> str:

    q = query.lower()

    # ==========================================================
    # Analytics
    # ==========================================================

    if (
        ("file" in q or "files" in q)
        and (
            "most issues" in q
            or "top file" in q
            or "risky file" in q
            or "problematic file" in q
        )
    ):
        return "top_files"

    if (
        "highest workload" in q
        or "who has the highest workload" in q
        or "who has the most workload" in q
    ):
        return "highest_workload"

    if (
        "top issue class" in q
        or "top issue classes" in q
        or "top classes" in q
        or "most common issue" in q
        or "most common findings" in q
    ):
        return "top_issue_classes"

    if (
        "hb_prio_1" in q
        and (
            "owner" in q
            or "who has the most" in q
        )
    ):
        return "owner_priority_summary"

    # ==========================================================
    # Counts
    # ==========================================================

    if "how many" in q and "pending" in q:
        return "pending_count"

    if "how many" in q and "done" in q:
        return "done_count"

    if "how many" in q and "issue" in q:
        return "issue_count"

    # ==========================================================
    # Owner Summary
    # ==========================================================

    if (
        ("summary" in q and "owner" in q)
        or ("summarize" in q and "assigned" in q)
        or ("summarize issues assigned to" in q)
    ):
        return "owner_summary"

    # ==========================================================
    # Recommend Owner (least workload)
    # ==========================================================

    if (
        "recommend owner" in q
        or "recommend an owner" in q
        or "least workload" in q
        or "balance workload" in q
        or "assign issue" in q
    ):
        return "recommend_owner"

    # ==========================================================
    # Recommend Next Issue
    # ==========================================================

    keywords = ["next", "recommend", "fix"]

    if "issue" in q and any(k in q for k in keywords):
        return "recommend_next_issue"

    # "fix <id>" with no "issue" word — route to explain_issue for per-issue detail
    if q.startswith("fix ") and any(ch.isdigit() for ch in q):
        return "explain_issue"

    # ==========================================================
    # Explain Issue
    # ==========================================================

    if (
        "explain issue" in q
        or "why is issue" in q
        or (any(ch.isdigit() for ch in q) and ("explain" in q or "fix" in q or "issue" in q))
    ):
        return "explain_issue"

    # ==========================================================
    # Similar Issues
    # ==========================================================

    if (
        "similar issue" in q
        or "similar issues" in q
    ):
        return "similar_issues"

    # ==========================================================
    # Single Issue Details
    # ==========================================================

    if (
        ("show issue" in q or q.startswith("issue "))
        and any(ch.isdigit() for ch in q)
    ):
        return "issue_details"

    # ==========================================================
    # Fix Guide (three levels — check before fix_recommendation)
    # ==========================================================

    # Level 3: batch / where-to-focus
    if (
        "batch fix" in q
        or "fix guide batch" in q
        or "where should i focus" in q
        or "where to focus" in q
        or "biggest impact" in q
        or "most impactful fix" in q
        or "prioritise fix" in q
        or "prioritize fix" in q
    ):
        return "fix_guide_batch"

    # Level 2: issue-level guide  ("fix guide for issue 12345" / "fix guide 12345")
    if (
        ("fix guide" in q or "how to fix issue" in q)
        and any(ch.isdigit() for ch in q)
    ):
        return "fix_guide_issue"

    # Level 1: class-level guide  ("how to fix <class>" / "fix guide for <class>")
    if (
        "fix guide" in q
        or (
            ("how to fix" in q or "guide for" in q)
            and not any(ch.isdigit() for ch in q)
        )
    ):
        return "fix_guide_class"

    # ==========================================================
    # Fix Recommendation (legacy simple lookup)
    # ==========================================================

    if (
        "how do i fix" in q
        or "how to fix" in q
        or "recommended fix" in q
        or "fix buffer" in q
        or "fix use after free" in q
        or "fix strcpy" in q
        or "fix strcmp" in q
        or "fix null" in q
    ):
        return "fix_recommendation"

    # ==========================================================
    # File Summary
    # ==========================================================

    if (
        "why is" in q
        and ".c" in q
    ):
        return "file_summary"

    # ==========================================================
    # File/Class Issues
    # ==========================================================

    if (
        ".c" in q
        and (
            "show issues" in q
            or "issues in" in q
            or "show hb_prio" in q
            or "pending" in q
            or "assigned" in q
        )
    ):
        return "class_issues"

    if "dashboard" in q:
        return "dashboard"

    if (
        "project summary" in q
        or "summarize project" in q
        or "overall summary" in q
        or "overall project summary" in q
        or "project overview" in q
    ):
        return "project_summary"

    if (
        "progress for" in q
        or "owner progress" in q
        or "progress of" in q
    ):
        return "owner_progress"

    if (
        "trend" in q
        or "since yesterday" in q
        or "since last report" in q
        or "what changed" in q
        or "project trend" in q
    ):
        return "trend_analysis"

    if (
        "project health" in q
        or "health" in q
        or "project status" in q
        or "overall status" in q
    ):
        return "project_health"

    if (
        "owner workload" in q
        or "workload for" in q
        or "show workload" in q
        or "workload of" in q
    ):
        return "owner_workload"

    if (
        "create tracker" in q
        or "update tracker" in q
        or "sync tracker" in q
        or "daily workflow" in q
        or "download the latest codesonar csv" in q
        or "download latest codesonar csv" in q
        or "download codesonar csv" in q
    ):
        return "tracker_workflow"

    # ==========================================================
    # Hotspot Analysis
    # ==========================================================

    if (
        "hotspot" in q
        or "hotspot analysis" in q
        or "top files" in q
        or "most affected files" in q
        or "file hotspots" in q
        or "files with most issues" in q
    ):
        return "hotspot_analysis"

    # ==========================================================
    # Default Search
    # ==========================================================

    return "search"
