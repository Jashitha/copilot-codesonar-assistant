"""
codesonar_checker.py

Responsibility: detect patterns that map to known CodeSonar finding classes,
annotated with the correlated MISRA-C:2012 rule.

Contract:
  - Accepts source code as a plain string.
  - Returns a list of finding dicts.
  - Never prints, never reads files, never formats output.

CodeSonar Finding          MISRA Rule
----------------------------------------------
Use of strcpy              Rule 21.18
Use of sprintf             Rule 21.6
Inappropriate Assign Type  Rule 10.3
Unreachable Code           Rule 2.2
Null Test After Deref      Rule 18.2
Use After Free             Rule 18.6
Buffer Overflow            Rule 21.17
Ignored Return Value       Rule 17.7
"""

from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_STRCPY     = re.compile(r"\b(strcpy|strcat)\s*\(")
_SPRINTF    = re.compile(r"\bsprintf\s*\(")
_IGNORED_RV = re.compile(r"^\s*(malloc|calloc|realloc|fopen|freopen|scanf|fscanf|sscanf|fgets|read|write|recv|send)\s*\(")
_UNSIGNED_NEG = re.compile(r"\bunsigned\b[^=]*=\s*-\s*\d")       # unsigned x = -1
_FREE_CALL  = re.compile(r"\bfree\s*\(\s*(\w+)\s*\)")
_DEREF      = re.compile(r"\b(\w+)\s*(?:->|\[)")                   # ptr->  or  arr[
_NULL_CHECK = re.compile(r"if\s*\(\s*(\w+)\s*==\s*NULL|if\s*\(\s*!\s*(\w+)\s*\)")
_RETURN_STMT = re.compile(r"^\s*(?:return\b.*|break|continue)\s*;\s*(?://.*)?$")
_COMMENT    = re.compile(r"^\s*(?://|\*)")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run(code: str) -> list[dict]:
    """
    Scan *code* for patterns correlated with CodeSonar finding classes.
    Returns a list of finding dicts compatible with review_report.generate().
    """
    findings: list[dict] = []
    lines = code.splitlines()

    # State for multi-line checks
    freed_vars: dict[str, int] = {}          # var_name -> free() line number
    deref_vars: dict[str, int] = {}          # var_name -> last dereference line

    for i, line in enumerate(lines):
        lineno = i + 1
        if _COMMENT.match(line):
            continue

        # ------------------------------------------------------------------
        # Use of strcpy / strcat → CodeSonar: Use of strcpy, MISRA Rule 21.18
        # ------------------------------------------------------------------
        m = _STRCPY.search(line)
        if m:
            fn = m.group(1)
            findings.append(_finding(
                codesonar_finding=f"Use of {fn}",
                rule="Rule 21.18",
                severity="HIGH",
                lineno=lineno,
                message=f"{fn}() does not validate that the size argument has an appropriate value, risking buffer overrun.",
                fix=f"Use strnlen()-bounded copy or snprintf(); validate buffer sizes before calling string functions.",
            ))

        # ------------------------------------------------------------------
        # Use of sprintf → CodeSonar: Use of sprintf, MISRA Rule 21.6
        # ------------------------------------------------------------------
        if _SPRINTF.search(line):
            findings.append(_finding(
                codesonar_finding="Use of sprintf",
                rule="Rule 21.6",
                severity="HIGH",
                lineno=lineno,
                message="sprintf() writes formatted output without a length limit, risking buffer overrun.",
                fix="Use snprintf() with explicit buffer size.",
            ))

        # ------------------------------------------------------------------
        # Inappropriate Assignment Type: unsigned = negative → Rule 10.3
        # ------------------------------------------------------------------
        if _UNSIGNED_NEG.search(line):
            findings.append(_finding(
                codesonar_finding="Inappropriate Assignment Type",
                rule="Rule 10.3",
                severity="HIGH",
                lineno=lineno,
                message="Negative value assigned to an unsigned variable; result is implementation-defined.",
                fix="Use the correct signedness type or add an explicit documented cast.",
            ))

        # ------------------------------------------------------------------
        # Ignored Return Value: alloc/IO called without capturing result → Rule 17.7
        # ------------------------------------------------------------------
        if _IGNORED_RV.match(line) and "=" not in line:
            fn_match = _IGNORED_RV.match(line)
            fn = fn_match.group(1) if fn_match else "function"
            findings.append(_finding(
                codesonar_finding="Ignored Return Value",
                rule="Rule 17.7",
                severity="MEDIUM",
                lineno=lineno,
                message=f"Return value of {fn}() is ignored; errors or NULL pointers will go undetected.",
                fix=f"Assign the return value and check it for errors (NULL / negative).",
            ))

        # ------------------------------------------------------------------
        # Use After Free tracking (two-pass: record free, then detect deref)
        # ------------------------------------------------------------------
        free_m = _FREE_CALL.search(line)
        if free_m:
            freed_vars[free_m.group(1)] = lineno

        deref_m = _DEREF.search(line)
        if deref_m:
            var = deref_m.group(1)
            if var in freed_vars and lineno > freed_vars[var]:
                findings.append(_finding(
                    codesonar_finding="Use After Free",
                    rule="Rule 18.6",
                    severity="HIGH",
                    lineno=lineno,
                    message=f"Pointer '{var}' is used after being passed to free() on line {freed_vars[var]}.",
                    fix="Set pointer to NULL after free(); check for NULL before reuse.",
                ))
                del freed_vars[var]   # report once per variable
            else:
                deref_vars[var] = lineno   # record most recent dereference

        # ------------------------------------------------------------------
        # Null Test After Dereference: if (ptr == NULL) after ptr->field → Rule 18.2
        # ------------------------------------------------------------------
        null_m = _NULL_CHECK.search(line)
        if null_m:
            var = null_m.group(1) or null_m.group(2) or ""
            if var and var in deref_vars:
                findings.append(_finding(
                    codesonar_finding="Null Test After Dereference",
                    rule="Rule 18.2",
                    severity="HIGH",
                    lineno=lineno,
                    message=f"Null check for '{var}' appears after '{var}' was dereferenced on line {deref_vars[var]}.",
                    fix="Check pointer for NULL before dereferencing it.",
                ))
                del deref_vars[var]

    # ----------------------------------------------------------------------
    # Unreachable Code: statement on line immediately after return/break/continue
    # (multi-line scan, done separately so line-by-line state is settled)
    # ----------------------------------------------------------------------
    for i, line in enumerate(lines[:-1]):
        if _COMMENT.match(line):
            continue
        if _RETURN_STMT.match(line):
            # Scan forward for the first non-blank, non-comment, non-closing-brace line
            for j in range(i + 1, min(i + 5, len(lines))):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                if _COMMENT.match(lines[j]):
                    continue
                if nxt in ("{", "}"):
                    break   # block boundary — not unreachable
                # Anything else here is potentially unreachable
                findings.append(_finding(
                    codesonar_finding="Unreachable Code",
                    rule="Rule 2.2",
                    severity="MEDIUM",
                    lineno=j + 1,
                    message="Statement appears after an unconditional return/break/continue and will never execute.",
                    fix="Remove dead code or restructure the control flow.",
                ))
                break

    return findings


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _finding(*, codesonar_finding: str, rule: str, severity: str,
             lineno: int, message: str, fix: str) -> dict:
    return {
        "checker": "CodeSonar",
        "codesonar_finding": codesonar_finding,
        "rule": rule,
        "line": lineno,
        "severity": severity,
        "message": message,
        "recommended_fix": fix,
    }
