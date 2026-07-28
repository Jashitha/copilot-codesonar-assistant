import re

from issue_explanations import FIX_GUIDE, ISSUE_EXPLANATIONS


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


def explain_issue(df, query):

    match = re.search(r"(\d+(?:\.\d+)?)", query)

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


def similar_issues(df, query):
    """
    Show issues having the same class as the given issue ID.
    """

    m = re.search(r"(\d+(?:\.\d+)?)", query)

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


# ---------------------------------------------------------------------------
# Fix Guide — Level 1: Class-level guide
# ---------------------------------------------------------------------------

def _match_class_name(query: str, df) -> str | None:
    """Return the best-matching class name from FIX_GUIDE or the tracker."""
    q = query.lower()

    # Exact or partial match against FIX_GUIDE keys
    for class_name in FIX_GUIDE:
        if class_name.lower() in q:
            return class_name

    # Fallback: match against unique class values present in the tracker
    if "class" in df.columns:
        for class_name in df["class"].dropna().unique():
            if str(class_name).lower() in q:
                return str(class_name)

    return None


def fix_guide_class(df, query: str) -> dict:
    """Level-1 Fix Guide: class-level explanation + hotspots from the tracker."""

    class_name = _match_class_name(query, df)

    if class_name is None:
        known = ", ".join(sorted(FIX_GUIDE.keys()))
        return {
            "answer": (
                f"No Fix Guide found for that class. "
                f"Known classes: {known}"
            ),
            "count": 0,
            "rows": [],
        }

    guide = FIX_GUIDE.get(class_name, {})

    # Hotspot data from the current tracker
    class_df = df[df["class"].astype(str) == class_name] if "class" in df.columns else df.iloc[0:0]
    total = len(class_df)

    priority_label = ""
    if "priority" in class_df.columns and not class_df.empty:
        top_prio = class_df["priority"].mode()
        if not top_prio.empty:
            priority_label = f" ({top_prio.iloc[0]})"

    top_files = (
        class_df.groupby("file").size().reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(5)
        if "file" in class_df.columns
        else None
    )

    # Build human-readable answer text
    lines = [
        f"{class_name} — Fix Guide",
        "",
        f"Occurrences: {total}{priority_label}",
        "",
    ]

    if top_files is not None and not top_files.empty:
        lines += ["Top Hotspot Files", "File\tCount"]
        for _, r in top_files.iterrows():
            lines.append(f"{r['file']}\t{r['Count']}")
        lines.append("")

    if guide.get("description"):
        lines += ["Why CodeSonar Reports This", guide["description"], ""]

    if guide.get("causes"):
        lines += ["Typical Causes"] + [f"  • {c}" for c in guide["causes"]] + [""]

    if guide.get("bad_code"):
        lines += ["Typical Bad Code", guide["bad_code"], ""]

    if guide.get("good_code"):
        lines += ["Better Fix", guide["good_code"], ""]

    if guide.get("checklist"):
        lines += ["Things to Check"] + [f"  ✓ {item}" for item in guide["checklist"]] + [""]

    if guide.get("standards"):
        lines += ["Relevant Standards"] + [f"  • {s}" for s in guide["standards"]] + [""]

    rows: list[dict] = []

    # Summary row
    rows.append({"Section": "Summary", "Detail": f"{total} occurrences{priority_label}"})

    if top_files is not None:
        for _, r in top_files.iterrows():
            rows.append({"Section": "Hotspot File", "Detail": f"{r['file']} ({r['Count']})"})

    for cause in guide.get("causes", []):
        rows.append({"Section": "Cause", "Detail": cause})

    for item in guide.get("checklist", []):
        rows.append({"Section": "Check", "Detail": item})

    for std in guide.get("standards", []):
        rows.append({"Section": "Standard", "Detail": std})

    if guide.get("bad_code"):
        rows.append({"Section": "Bad Code", "Detail": guide["bad_code"]})

    if guide.get("good_code"):
        rows.append({"Section": "Good Code", "Detail": guide["good_code"]})

    return {
        "answer": "\n".join(lines),
        "count": total,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Fix Guide — Level 2: Issue-level guide
# ---------------------------------------------------------------------------

def fix_guide_issue(df, query: str) -> dict:
    """Level-2 Fix Guide: per-issue detail — file, line, procedure, likely cause, checklist."""

    m = re.search(r"(\d{5,})", query)   # CodeSonar IDs tend to be long numbers
    if not m:
        m = re.search(r"(\d+)", query)

    if not m:
        return {
            "answer": "Please provide a valid issue ID.",
            "count": 0,
            "rows": [],
        }

    issue_id = m.group(1)
    row_df = df[df["id"].astype(str) == issue_id]

    if row_df.empty:
        return {
            "answer": f"Issue {issue_id} not found in the tracker.",
            "count": 0,
            "rows": [],
        }

    issue = row_df.iloc[0]
    class_name = str(issue.get("class", ""))
    guide = FIX_GUIDE.get(class_name, {})
    fallback = ISSUE_EXPLANATIONS.get(class_name, {})

    description = guide.get("description") or fallback.get("why", "No description available.")
    checklist = guide.get("checklist") or []
    good_code = guide.get("good_code") or fallback.get("fix", "")
    standards = guide.get("standards") or []

    lines = [
        f"Fix Guide — Issue {issue_id}",
        "",
        f"Class      : {class_name}",
        f"File       : {issue.get('file', 'N/A')}",
        f"Line       : {issue.get('line number', 'N/A')}",
        f"Procedure  : {issue.get('procedure', 'N/A')}",
        f"Priority   : {issue.get('priority', 'N/A')}",
        f"Owner      : {issue.get('Owner', 'Unassigned')}",
        f"Status     : {issue.get('Status', 'Pending')}",
        "",
        "What CodeSonar Found",
        description,
        "",
    ]

    if checklist:
        lines += ["Validation Checklist"] + [f"  ✓ {item}" for item in checklist] + [""]

    if good_code:
        lines += ["Suggested Fix Pattern", good_code, ""]

    if standards:
        lines += ["Relevant Standards"] + [f"  • {s}" for s in standards]

    rows = [
        {"Field": "id",        "Value": issue_id},
        {"Field": "class",     "Value": class_name},
        {"Field": "file",      "Value": str(issue.get("file", ""))},
        {"Field": "line",      "Value": str(issue.get("line number", ""))},
        {"Field": "procedure", "Value": str(issue.get("procedure", ""))},
        {"Field": "priority",  "Value": str(issue.get("priority", ""))},
        {"Field": "owner",     "Value": str(issue.get("Owner", "Unassigned"))},
        {"Field": "status",    "Value": str(issue.get("Status", "Pending"))},
        {"Field": "description", "Value": description},
    ]
    for item in checklist:
        rows.append({"Field": "checklist", "Value": item})
    if good_code:
        rows.append({"Field": "fix_pattern", "Value": good_code})

    return {
        "answer": "\n".join(lines),
        "count": 1,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Fix Guide — Level 3: Batch fix guide
# ---------------------------------------------------------------------------

def fix_guide_batch(df) -> dict:
    """Level-3 Fix Guide: rank hotspot (class × file) pairs by impact to prioritise effort."""

    if "class" not in df.columns or "file" not in df.columns:
        return {
            "answer": "Tracker is missing 'class' or 'file' columns.",
            "count": 0,
            "rows": [],
        }

    # Group by class first to get class-level totals
    class_totals = (
        df.groupby("class")
        .size()
        .reset_index(name="ClassTotal")
        .sort_values("ClassTotal", ascending=False)
    )

    # Group by (class, file) to find the densest hotspots
    hotspots = (
        df.groupby(["class", "file"])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(20)
    )

    # Annotate with fix-guide availability
    hotspots["HasGuide"] = hotspots["class"].apply(
        lambda c: "✓" if c in FIX_GUIDE else "—"
    )

    # Class-level impact table (top 10 classes)
    class_impact = class_totals.head(10).copy()
    class_impact["HasGuide"] = class_impact["class"].apply(
        lambda c: "✓" if c in FIX_GUIDE else "—"
    )

    lines = [
        "Batch Fix Guide — Prioritised Hotspots",
        "",
        "Strategy: Fix the class with the most issues in the fewest files first.",
        "",
        "Top Issue Classes by Volume",
        "Class\tTotal\tHasGuide",
    ]
    for _, r in class_impact.iterrows():
        lines.append(f"{r['class']}\t{r['ClassTotal']}\t{r['HasGuide']}")

    lines += [
        "",
        "Top (Class × File) Hotspots — Single-File Fix Impact",
        "Class\tFile\tCount\tHasGuide",
    ]
    for _, r in hotspots.iterrows():
        lines.append(f"{r['class']}\t{r['file']}\t{r['Count']}\t{r['HasGuide']}")

    lines += [
        "",
        "Recommendation",
        "1. Start with classes that have a ✓ Fix Guide — guidance is ready.",
        "2. Within each class, fix the hotspot file first (highest Count).",
        "3. One focused review of a hotspot file often removes dozens of findings.",
        "4. Re-run CodeSonar after each batch to confirm reduction.",
    ]

    rows: list[dict] = []
    for _, r in class_impact.iterrows():
        rows.append({
            "Section":  "ClassImpact",
            "class":    r["class"],
            "file":     "",
            "Count":    int(r["ClassTotal"]),
            "HasGuide": r["HasGuide"],
        })
    for _, r in hotspots.iterrows():
        rows.append({
            "Section":  "Hotspot",
            "class":    r["class"],
            "file":     r["file"],
            "Count":    int(r["Count"]),
            "HasGuide": r["HasGuide"],
        })

    return {
        "answer": "\n".join(lines),
        "count": len(df),
        "rows": rows,
    }
