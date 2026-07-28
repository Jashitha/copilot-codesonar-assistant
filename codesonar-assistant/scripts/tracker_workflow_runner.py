"""
Run tracker workflow commands from assistant intent routing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _extract_url(query: str) -> str | None:
    match = re.search(r"https?://\S+", query)
    if not match:
        return None
    return match.group(0).strip().rstrip(").,;")


def _extract_list(query: str, field: str) -> str | None:
    # Examples supported:
    # - owners a,b
    # - owner a,b
    # - owners: a, b
    # - owner = a,b
    match = re.search(rf"\b{field}\b\s*[:=]?\s*([a-zA-Z0-9_\-,\s]+)", query, flags=re.IGNORECASE)
    if not match:
        return None

    raw = match.group(1).strip()
    if not raw:
        return None

    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        return None

    return ",".join(values)


def _tail_lines(text: str, limit: int = 15) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def run_tracker_workflow(query: str) -> dict:
    """
    Execute scripts/daily_workflow.py and return assistant-friendly response.
    """

    cmd = [sys.executable, str(SCRIPT_DIR / "daily_workflow.py")]

    owners = _extract_list(query, "owners")
    if owners:
        cmd.extend(["--owners", owners])

    reviewers = _extract_list(query, "reviewers")
    if reviewers:
        cmd.extend(["--reviewers", reviewers])

    url = _extract_url(query)
    if url:
        cmd.extend(["--report-url", url])

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR.parent),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        return {
            "answer": f"Tracker workflow failed to start: {exc}",
            "count": 0,
            "rows": [],
        }

    stdout_lines = _tail_lines(completed.stdout)
    stderr_lines = _tail_lines(completed.stderr)

    if completed.returncode == 0:
        return {
            "answer": "Tracker workflow completed successfully.",
            "count": 0,
            "rows": [{"output": line} for line in stdout_lines],
        }

    rows = []
    for line in stdout_lines:
        rows.append({"output": line})
    for line in stderr_lines:
        rows.append({"error": line})

    return {
        "answer": (
            "Tracker workflow failed. Provide direct CodeSonar CSV export URL or "
            "authentication options to daily_workflow.py if required."
        ),
        "count": 0,
        "rows": rows,
    }
