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
# Fixability classification
# ---------------------------------------------------------------------------

_AUTO_FIXABLE_DANGEROUS_APIS = {"strcpy", "sprintf"}
_AUTO_FIXABLE_CODESONAR_FINDINGS = {"Use of strcpy", "Use of sprintf", "Null Test After Deref"}


def _finding_fixability(finding: dict) -> tuple[str, str]:
    """Return (status, reason) for a single finding dict."""
    checker = finding.get("checker", "")

    if checker == "Dangerous API":
        api = finding.get("api", "")
        if api in _AUTO_FIXABLE_DANGEROUS_APIS:
            return ("Auto Fix Supported", "Safe mechanical API replacement is implemented.")
        return ("Manual Fix Required", "Requires a code change outside the supported auto-fix set.")

    if checker.startswith("CodeSonar"):
        codesonar_finding = finding.get("codesonar_finding", "")
        if codesonar_finding in _AUTO_FIXABLE_CODESONAR_FINDINGS:
            return ("Auto Fix Supported", "Safe mechanical pattern remediation is implemented.")
        return ("Manual Fix Required", "Requires semantic code changes.")

    if checker.startswith("MISRA"):
        return ("Manual Fix Required", "Requires semantic or standards-driven code changes.")

    if checker == "Memory":
        return ("Manual Fix Required", "Requires investigation of ownership or lifetime behavior.")

    return ("Manual Fix Required", "Requires manual review.")


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
    for finding in findings:
        by_checker.setdefault(finding["checker"], []).append(finding)

    if not findings:
        lines += ["No issues found.", ""]
    else:
        for checker_name, checker_findings in by_checker.items():
            lines += [checker_name, "-" * len(checker_name), ""]
            for finding in checker_findings:
                lines += _format_finding(finding)
            lines.append("")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    dangerous_count = len(by_checker.get("Dangerous API", []))
    misra_count = sum(len(values) for key, values in by_checker.items() if key.startswith("MISRA"))
    codesonar_count = sum(len(values) for key, values in by_checker.items() if key.startswith("CodeSonar"))
    memory_count = sum(len(values) for key, values in by_checker.items() if key.startswith("Memory"))

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
    high_count = sum(1 for finding in findings if finding.get("severity") in ("HIGH", "MEDIUM"))
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

def _format_finding(finding: dict) -> list[str]:
    """Return display lines for a single finding dict."""
    label = (
        f"{finding['codesonar_finding']}  ({finding['rule']})"
        if finding.get("codesonar_finding")
        else finding.get("api") or finding.get("rule") or finding.get("description", "Issue")
    )
    status, reason = _finding_fixability(finding)
    out = [
        f"  Line {finding.get('line', '?')}",
        "",
        f"  {label}",
        "",
    ]

    if finding.get("rule"):
        out += [
            f"  MISRA Rule     : {finding.get('rule')}",
            "",
        ]

    out += [
        f"  Severity        : {finding.get('severity', 'UNKNOWN')}",
        f"  Message         : {finding.get('message', '')}",
        f"  Status          : {status}",
        f"  Reason          : {reason}",
        "",
        "  Recommendation",
        "",
        f"    {finding.get('recommended_fix', 'See coding standards.')}",
        "",
        "  " + "-" * 33,
        "",
    ]
    return out
