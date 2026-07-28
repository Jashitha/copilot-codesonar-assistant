"""
misra_checker.py

Responsibility: detect MISRA-C:2012 rule violations via static pattern analysis.

Contract:
  - Accepts source code as a plain string.
  - Returns a list of finding dicts.
  - Never prints, never reads files, never formats output.
"""

import re

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------
# Each entry: (rule_id, severity, pattern, description, recommendation)
# Pattern is matched per-line; group(1) optionally captures the matched token.
# ---------------------------------------------------------------------------

_RULES: list[tuple] = [
    (
        "Rule 21.7",
        "HIGH",
        re.compile(r"\b(atoi|atof|atol|atoll)\s*\("),
        "{token}() shall not be used (no error detection for malformed input).",
        "Use strtol() / strtod() with errno checking instead.",
    ),
    (
        "Rule 21.6",
        "MEDIUM",
        re.compile(r"\b(printf|fprintf|scanf|fscanf|sscanf|puts|gets|fgets|fputs)\s*\("),
        "Standard Library I/O function {token}() shall not be used.",
        "Use a project-approved I/O abstraction layer.",
    ),
    (
        "Rule 21.8",
        "HIGH",
        re.compile(r"\b(abort|exit|_Exit|atexit)\s*\("),
        "Standard Library termination function {token}() shall not be used.",
        "Handle error conditions explicitly; avoid abrupt program termination.",
    ),
    (
        "Rule 21.3",
        "HIGH",
        re.compile(r"\b(malloc|calloc|realloc|free)\s*\("),
        "Dynamic memory function {token}() shall not be used.",
        "Use statically allocated buffers or a project-approved allocator.",
    ),
    (
        "Directive 4.6",
        "LOW",
        re.compile(r"\b(double|float)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*[=;,)]"),
        "Plain floating-point type '{token}' used; prefer fixed-width typedef (e.g. float32_t).",
        "Define float32_t / float64_t typedefs and use them consistently.",
    ),
    (
        "Rule 14.5",
        "LOW",
        re.compile(r"\bcontinue\b"),
        "'continue' statement shall not be used.",
        "Restructure the loop to avoid 'continue'.",
    ),
    (
        "Rule 15.1",
        "LOW",
        re.compile(r"\bgoto\b"),
        "'goto' statement shall not be used.",
        "Refactor control flow to eliminate 'goto'.",
    ),
]


def run(code: str) -> list[dict]:
    """
    Scan *code* for MISRA-C:2012 violations.
    Returns a list of finding dicts compatible with review_report.generate().
    """
    findings: list[dict] = []

    for lineno, line in enumerate(code.splitlines(), start=1):
        # Skip pure comment lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        for rule_id, severity, pattern, description, recommendation in _RULES:
            match = pattern.search(line)
            if match:
                token = match.group(1) if match.lastindex and match.lastindex >= 1 else ""
                findings.append(
                    {
                        "checker": "MISRA-C:2012",
                        "rule": rule_id,
                        "line": lineno,
                        "severity": severity,
                        "message": description.format(token=token),
                        "recommended_fix": recommendation,
                    }
                )

    return findings
