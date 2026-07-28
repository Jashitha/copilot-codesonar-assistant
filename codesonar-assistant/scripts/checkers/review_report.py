"""
review_report.py

Responsibility: format a list of findings into a human-readable pre-commit
review report.

Contract:
  - Accepts a filename (str) and a list of finding dicts.
  - Returns a formatted report string.
  - Never prints, never reads files, never runs checkers.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(filename: str, findings: list[dict]) -> str:
    """
    Build and return a pre-commit review report.

    Parameters
    ----------
    filename : str
        The source file name (used only for display).
    findings : list[dict]
        Merged list produced by all checkers.

    Returns
    -------
    str
        Formatted, printable report.
    """
    lines: list[str] = []

    lines += [
        "=========================================",
        "PRE-COMMIT REVIEW",
        "=========================================",
        "",
        "File",
        "-----",
        filename,
        "",
    ]

    # ------------------------------------------------------------------
    # Group findings by checker category
    # ------------------------------------------------------------------
    by_checker: dict[str, list[dict]] = {}
    for f in findings:
        by_checker.setdefault(f["checker"], []).append(f)

    if not findings:
        lines += ["No issues found.", ""]
    else:
        for checker_name, checker_findings in by_checker.items():
            lines += [checker_name, "-" * len(checker_name), ""]
            for f in checker_findings:
                lines += _format_finding(f)
            lines.append("")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    dangerous_count  = len(by_checker.get("Dangerous API", []))
    misra_count      = sum(len(v) for k, v in by_checker.items() if k.startswith("MISRA"))
    codesonar_count  = sum(len(v) for k, v in by_checker.items() if k.startswith("CodeSonar"))
    memory_count     = sum(len(v) for k, v in by_checker.items() if k.startswith("Memory"))

    lines += [
        "-" * 33,
        "",
        "Summary",
        "",
        f"Dangerous APIs                  : {dangerous_count}",
        f"MISRA Issues                    : {misra_count}",
        f"Potential CodeSonar Findings    : {codesonar_count}",
        f"Memory Issues                   : {memory_count}",
        "",
    ]

    # Commit readiness: NOT READY if any HIGH/MEDIUM finding exists
    high_count = sum(
        1 for f in findings if f.get("severity") in ("HIGH", "MEDIUM")
    )
    readiness = "NOT READY" if high_count > 0 else "READY TO COMMIT"
    lines += [
        "Commit Readiness",
        "",
        readiness,
        "",
        "=========================================",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_finding(f: dict) -> list[str]:
    """Return display lines for a single finding dict."""
    # CodeSonar findings have both codesonar_finding and rule
    label = (
        f"{f['codesonar_finding']}  ({f['rule']})"
        if f.get("codesonar_finding")
        else f.get("api") or f.get("rule") or f.get("description", "Issue")
    )
    out = [
        f"  Line {f.get('line', '?')}",
        "",
        f"  {label}",
        "",
        f"  Severity        : {f.get('severity', 'UNKNOWN')}",
        f"  Message         : {f.get('message', '')}",
        "",
        "  Recommendation",
        "",
        f"    {f.get('recommended_fix', 'See coding standards.')}",
        "",
        "  " + "-" * 33,
        "",
    ]
    return out
