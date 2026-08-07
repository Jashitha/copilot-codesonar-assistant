#!/usr/bin/env python3
"""
gerrit_hook.py

Gerrit patchset-created hook — runs CodeSonar pre-commit review on every
changed C source file in the patch set and posts a Verified vote back to
Gerrit via its REST API.

Behaviour
---------
  * Verified -1 (block)  : any HIGH severity finding is present.
  * Verified +1 (pass)   : no HIGH severity findings in any changed .c file.

Installation (Gerrit server-side hook)
--------------------------------------
1. Copy this script to <gerrit-site>/hooks/patchset-created
2. Make it executable:  chmod +x <gerrit-site>/hooks/patchset-created
3. Set the environment variables below in the Gerrit service environment or in
   the project's .env file at TASK_DIR/.env (loaded automatically).

Required environment variables (see .env.example):
    GERRIT_URL            Base URL of your Gerrit instance
                          e.g. https://gerrit.example.com
    GERRIT_USER           Service-account username
    GERRIT_HTTP_PASSWORD  HTTP password from Gerrit account → Settings → HTTP

Optional:
    CODESONAR_TRACKER     Absolute path to Master_Tracker.xlsx
                          (defaults to <this-script-dir>/../output/Master_Tracker.xlsx)

Gerrit hook arguments (passed by Gerrit automatically):
    --change <change-id>
    --change-url <url>
    --change-owner <owner>
    --project <project>
    --branch <branch>
    --topic <topic>
    --uploader <uploader>
    --commit <sha1>
    --patchset <number>

Usage (manual / CI trigger):
    python3 gerrit_hook.py --change Iabc123 --commit <sha> --patchset 1 \\
        [--project myproject] [--branch main]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load .env from the project root if present
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_TASK_DIR = _SCRIPT_DIR.parent

sys.path.insert(0, str(_SCRIPT_DIR))
from env_bootstrap import ensure_env_file  # noqa: E402

_ENV_FILE = ensure_env_file(_TASK_DIR)

if _ENV_FILE.exists():
    with open(_ENV_FILE) as _fh:
        for _line in _fh:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())

# ---------------------------------------------------------------------------
# Local imports (must come after path bootstrap)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(_SCRIPT_DIR))

from gerrit_client import GerritClient, GerritAuthError, GerritAPIError
from precommit_review import review_with_findings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_REVIEWABLE_EXTENSIONS = {".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}
_HIGH_SEVERITY_RE = re.compile(r"Severity\s*:\s*HIGH", re.IGNORECASE)
_READY_RE = re.compile(r"^READY TO COMMIT$", re.MULTILINE)
_NOT_READY_RE = re.compile(r"^NOT READY$", re.MULTILINE)


def _has_high_severity(report: str) -> bool:
    """Return True if *report* contains at least one HIGH severity finding."""
    return bool(_HIGH_SEVERITY_RE.search(report))


def _extract_inline_comments(report: str, filename: str) -> list[dict]:
    """
    Parse the pre-commit report text and return a list of Gerrit inline
    comment dicts:  [{"line": N, "message": "..."}]

    Only HIGH severity findings are extracted for inline posting.
    """
    comments: list[dict] = []

    # Split on separator lines to get individual finding blocks
    blocks = re.split(r"\n\s*-{20,}\s*\n", report)

    for block in blocks:
        if not _HIGH_SEVERITY_RE.search(block):
            continue
        line_match = re.search(r"Line\s+(\d+)", block)
        if not line_match:
            continue
        line_no = int(line_match.group(1))
        # Clean up the block for the comment message
        msg = block.strip()
        comments.append({"line": line_no, "message": msg})

    return comments


def _fetch_changed_c_files(
    client: GerritClient, change_id: str, revision_id: str
) -> list[str]:
    """
    Return only reviewable C/C++ files changed in this revision.
    Falls back to an empty list with a warning on API error.
    """
    try:
        all_files = client.get_changed_files(change_id, revision_id)
    except GerritAPIError as exc:
        print(f"[gerrit_hook] WARNING: could not list changed files: {exc}",
              file=sys.stderr)
        return []

    return [f for f in all_files if Path(f).suffix.lower() in _REVIEWABLE_EXTENSIONS]


def _fetch_file_from_gerrit(
    client: GerritClient,
    change_id: str,
    revision_id: str,
    gerrit_path: str,
) -> Path | None:
    """
    Download the patchset file content from Gerrit and write it to a temp file.
    Returns the temp Path, or None if Gerrit cannot return the file content.
    """
    try:
        content = client.get_file_content(change_id, revision_id, gerrit_path)
    except GerritAPIError as exc:
        print(
            f"[gerrit_hook] WARNING: could not retrieve {gerrit_path} from Gerrit: {exc}",
            file=sys.stderr,
        )
        return None

    suffix = Path(gerrit_path).suffix or ".c"
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, mode="wb"
    )
    tmp.write(content)
    tmp.flush()
    return Path(tmp.name)


def _report_is_ready(report: str) -> bool:
    """Return True when the pre-commit report says the file is ready."""
    if _NOT_READY_RE.search(report):
        return False
    return bool(_READY_RE.search(report))


def _is_blocking_finding(finding: dict) -> bool:
    """Return True when a finding should block commit readiness."""
    return finding.get("severity") in ("HIGH", "MEDIUM")


def _blocking_reason(finding: dict) -> str:
    """Build a concise, human-readable blocking reason for summary output."""
    checker = finding.get("checker", "")

    if checker == "Dangerous API":
        api = finding.get("api", "")
        return f"Dangerous API: {api}" if api else "Dangerous API"

    if checker.startswith("MISRA"):
        rule = finding.get("rule", "")
        message = finding.get("message", "")
        token_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\(\)", message)
        token = token_match.group(1) if token_match else ""
        if rule and token:
            return f"MISRA {rule} ({token})"
        if rule:
            return f"MISRA {rule}"
        return "MISRA violation"

    if checker.startswith("CodeSonar"):
        name = finding.get("codesonar_finding") or finding.get("message") or "CodeSonar finding"
        return f"CodeSonar: {name}"

    if checker.startswith("Memory"):
        message = finding.get("message", "Memory issue")
        return f"Memory: {message}"

    return finding.get("message") or finding.get("description") or "Blocking finding"


def run_hook(
    change_id: str,
    commit: str,
    patchset: str,
    project: str = "",
    branch: str = "",
) -> int:
    """
    Core logic.  Returns 0 on success, non-zero on error.

    This function is separated from main() so it can be tested or called
    from a CI wrapper without subprocess overhead.
    """

    print(f"[gerrit_hook] change={change_id}  commit={commit}  patchset={patchset}")

    # --- Connect to Gerrit ----------------------------------------------------
    try:
        client = GerritClient.from_env()
    except GerritAuthError as exc:
        print(f"[gerrit_hook] ERROR: {exc}", file=sys.stderr)
        return 1

    # --- List changed C files -------------------------------------------------
    revision_id = commit or "current"
    c_files = _fetch_changed_c_files(client, change_id, revision_id)

    if not c_files:
        print("[gerrit_hook] No C/H files changed — nothing to review.")
        return 0

    print(f"[gerrit_hook] Reviewing {len(c_files)} file(s): {c_files}")

    # --- Run pre-commit review on each file -----------------------------------
    any_blocking = False
    any_fetch_failure = False
    all_inline_comments: dict[str, list[dict]] = {}
    blocking_files: list[tuple[str, list[str]]] = []
    summary_lines: list[str] = [
        "CodeSonar Pre-Commit Review",
        "=" * 40,
    ]

    for gerrit_path in c_files:
        tmp_path = _fetch_file_from_gerrit(client, change_id, revision_id, gerrit_path)
        if tmp_path is None:
            summary_lines.append(
                f"\n[ERROR] {gerrit_path}: could not retrieve file content from Gerrit."
            )
            any_fetch_failure = True
            any_blocking = True
            blocking_files.append((
                gerrit_path,
                ["Could not retrieve file content from Gerrit"],
            ))
            continue

        try:
            review_result = review_with_findings(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        report = review_result.get("report", "")
        findings = review_result.get("findings", [])

        file_ready = _report_is_ready(report)
        if not file_ready:
            any_blocking = True
            reasons: list[str] = []
            for finding in findings:
                if _is_blocking_finding(finding):
                    reason = _blocking_reason(finding)
                    if reason not in reasons:
                        reasons.append(reason)
            blocking_files.append((gerrit_path, reasons))

        inline = _extract_inline_comments(report, Path(gerrit_path).name)
        if inline:
            all_inline_comments[gerrit_path] = inline

        status = "READY" if file_ready else "NOT READY"
        summary_lines.append(f"\n{gerrit_path}  →  {status}")

    # --- Determine vote -------------------------------------------------------
    verified = -1 if any_blocking else 1
    if any_fetch_failure:
        vote_label = "Verified -1 (file content fetch failed or blocking findings present)"
    else:
        vote_label = "Verified -1 (blocking findings present)" if any_blocking else "Verified +1"

    if blocking_files:
        summary_lines += [
            "",
            "Blocking Files",
            "-" * 14,
        ]
        for index, (file_path, reasons) in enumerate(blocking_files, start=1):
            summary_lines.append(f"{index}. {file_path}")
            if reasons:
                for reason in reasons:
                    summary_lines.append(f"   - {reason}")
            else:
                summary_lines.append("   - Blocking findings present")
            summary_lines.append("")

    summary_lines += [
        "",
        "=" * 40,
        f"Commit Readiness : {'NOT READY' if any_blocking else 'READY'}",
        f"Gerrit Vote       : {vote_label}",
    ]

    top_message = "\n".join(summary_lines)
    print(top_message)

    # --- Post review to Gerrit ------------------------------------------------
    try:
        client.post_review(
            change_id=change_id,
            revision_id=revision_id,
            message=top_message,
            verified=verified,
            comments=all_inline_comments if all_inline_comments else None,
        )
        print(f"[gerrit_hook] Review posted successfully ({vote_label}).")
    except GerritAPIError as exc:
        print(f"[gerrit_hook] ERROR posting review: {exc}", file=sys.stderr)
        return 1

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CodeSonar pre-commit review hook for Gerrit."
    )
    # Gerrit passes these automatically when used as a server-side hook
    parser.add_argument("--change", required=True,
                        help="Gerrit change-id (e.g. Iabc123)")
    parser.add_argument("--commit", required=True,
                        help="Git commit SHA of this patchset")
    parser.add_argument("--patchset", default="1",
                        help="Patchset number (default: 1)")
    parser.add_argument("--project", default="",
                        help="Gerrit project name (informational)")
    parser.add_argument("--branch", default="",
                        help="Target branch (informational)")
    # Gerrit passes many more args; accept and ignore them
    parser.add_argument("--change-url", default="")
    parser.add_argument("--change-owner", default="")
    parser.add_argument("--topic", default="")
    parser.add_argument("--uploader", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return run_hook(
        change_id=args.change,
        commit=args.commit,
        patchset=args.patchset,
        project=args.project,
        branch=args.branch,
    )


if __name__ == "__main__":
    sys.exit(main())
