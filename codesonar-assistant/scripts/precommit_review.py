"""
precommit_review.py

Orchestrator for the Pre-Commit Code Review feature.

Responsibilities (and ONLY these):
  1. Accept a source file path.
  2. Read the file.
  3. Call every checker's run() function with the source code.
  4. Merge all findings into one list.
  5. Pass the merged list to review_report.generate().
  6. Return the formatted report string.

This module never implements checker logic.
This module never formats report text.
"""

from __future__ import annotations

from pathlib import Path

# Checker imports -- add new checkers here when they are ready
from checkers import dangerous_api_checker
from checkers import misra_checker
from checkers import codesonar_checker
from checkers import memory_checker
from checkers import review_report

# ---------------------------------------------------------------------------
# Registry: list checkers in the order they should run.
# To add a new checker, append its module here -- nothing else needs changing.
# ---------------------------------------------------------------------------
_CHECKERS = [
    dangerous_api_checker,
    misra_checker,
    codesonar_checker,
    memory_checker,
]


def review(file_path: str | Path) -> str:
    """
    Run all checkers against *file_path* and return a formatted report.

    Parameters
    ----------
    file_path : str | Path
        Path to the C source file to review.

    Returns
    -------
    str
        Formatted pre-commit review report.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    """
    result = review_with_findings(file_path)
    return result["report"]


def review_with_findings(file_path: str | Path) -> dict:
    """
    Run all checkers against *file_path* and return report plus raw findings.

    Returns
    -------
    dict
        {
            "report": <formatted report string>,
            "findings": <list of finding dicts>
        }
    """
    path = Path(file_path)
    code = path.read_text(encoding="utf-8", errors="replace")

    findings: list[dict] = []
    for checker in _CHECKERS:
        findings.extend(checker.run(code))

    return {
        "report": review_report.generate(path.name, findings),
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Assistant bridge: called by dispatcher when intent == "precommit_review"
# ---------------------------------------------------------------------------

def run_precommit_review(query: str) -> dict:
    """
    Extract a file path from the natural-language *query* and run the review.

    Expected query forms:
        review bsmd.c
        pre-commit review scripts/foo.c
        check my code /absolute/path/to/file.c
        review tests/sample_code/dangerous_api.c

    Returns an assistant-style dict with 'answer', 'count', and 'rows'.
    """
    import re

    # Match a token that looks like a file path: has a dot or starts with /
    match = re.search(r'([^\s]+\.[a-zA-Z]+(?:/[^\s]*)?|/[^\s]+)', query)
    if not match:
        return {
            "answer": (
                "Please provide a source file path.\n"
                "Example: review bsmd.c\n"
                "Example: pre-commit review /path/to/file.c"
            ),
            "count": 0,
            "rows": [],
        }

    file_path = Path(match.group(1))

    # If the path is relative and not found from cwd, try common roots
    if not file_path.exists():
        _script_dir = Path(__file__).parent          # scripts/
        _repo_root  = _script_dir.parent.parent      # ~/.copilot
        _cs_root    = _script_dir.parent             # codesonar-assistant/

        for base in (_script_dir, _cs_root, _repo_root):
            candidate = base / file_path
            if candidate.exists():
                file_path = candidate
                break

    if not file_path.exists():
        return {
            "answer": f"File not found: {file_path}",
            "count": 0,
            "rows": [],
        }

    report = review(file_path)
    return {
        "answer": report,
        "count": 1,
        "rows": [],
    }


# ---------------------------------------------------------------------------
# CLI convenience: python precommit_review.py <file>
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python precommit_review.py <source_file>")
        sys.exit(1)

    report = review(sys.argv[1])
    print(report)
