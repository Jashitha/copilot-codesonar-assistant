"""
dangerous_api_checker.py

Detects usage of known-dangerous C APIs in source code.

Responsibility: scan only for dangerous API calls.
Contract:
  - Accepts source code as a plain string.
  - Returns a list of finding dicts.
  - Never prints, never reads files, never formats output.
"""

import re

# ---------------------------------------------------------------------------
# Rule table: each entry maps one dangerous API to its guidance.
# Add new entries here to extend coverage without touching any other file.
# ---------------------------------------------------------------------------
_RULES: list[dict] = [
    {
        "api": "strcpy",
        "severity": "HIGH",
        "message": "strcpy() copies bytes without bounds checking.",
        "recommended_fix": "Use strncpy() or snprintf() instead.",
    },
    {
        "api": "strcat",
        "severity": "HIGH",
        "message": "strcat() appends without bounds checking.",
        "recommended_fix": "Use strncat() instead.",
    },
    {
        "api": "sprintf",
        "severity": "HIGH",
        "message": "sprintf() writes without length limit.",
        "recommended_fix": "Use snprintf() instead.",
    },
    {
        "api": "gets",
        "severity": "HIGH",
        "message": "gets() is removed from C11; no bound on input length.",
        "recommended_fix": "Use fgets() instead.",
    },
    {
        "api": "atoi",
        "severity": "MEDIUM",
        "message": "atoi() has no error detection for malformed input.",
        "recommended_fix": "Use strtol() with error checking instead.",
    },
    {
        "api": "atof",
        "severity": "MEDIUM",
        "message": "atof() has no error detection for malformed input.",
        "recommended_fix": "Use strtod() with error checking instead.",
    },
    {
        "api": "strtok",
        "severity": "MEDIUM",
        "message": "strtok() is not re-entrant and modifies the input string.",
        "recommended_fix": "Use strtok_r() (POSIX) or strtok_s() (C11 Annex K) instead.",
    },
]

# Pre-compile one pattern per rule for efficiency.
_COMPILED: list[tuple[dict, re.Pattern]] = [
    (rule, re.compile(rf"\b{re.escape(rule['api'])}\s*\("))
    for rule in _RULES
]


def run(code: str) -> list[dict]:
    """
    Scan *code* for dangerous API calls.

    Parameters
    ----------
    code : str
        Full source code as a single string.

    Returns
    -------
    list[dict]
        One dict per finding with keys:
        checker, api, line, severity, message, recommended_fix.
    """
    findings: list[dict] = []

    for lineno, line in enumerate(code.splitlines(), start=1):
        for rule, pattern in _COMPILED:
            if pattern.search(line):
                findings.append(
                    {
                        "checker": "Dangerous API",
                        "api": rule["api"],
                        "line": lineno,
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "recommended_fix": rule["recommended_fix"],
                    }
                )

    return findings
