"""
gerrit_review.py

Dispatcher entrypoint for Gerrit link / patchset review requests.

Parses a Gerrit link or reference from the user's query, resolves the target
revision, and runs the existing Gerrit hook so the same CodeSonar review logic
and Verified vote behavior are reused.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stderr, redirect_stdout
from urllib.parse import unquote, urlparse

from gerrit_client import GerritAPIError, GerritAuthError, GerritClient
from gerrit_hook import run_hook

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_CHANGE_ID_RE = re.compile(r"\bI[a-fA-F0-9]{8,}\b")
_PATCHSET_RE = re.compile(r"(?:patchset|ps|revision)\s*[:=]?\s*(\d+)", re.IGNORECASE)
_GERRIT_CHANGE_RE = re.compile(r"/\+/([0-9]+)(?:/([0-9]+))?")
_NUMERIC_TAIL_RE = re.compile(r"/([0-9]+)(?:/([0-9]+))?(?:[/?#].*)?$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _clean_url(url: str) -> str:
    return url.rstrip("),.>\'\"")


def _extract_reference(query: str) -> dict[str, str | None]:
    url_match = _URL_RE.search(query)
    url = _clean_url(url_match.group(0)) if url_match else ""
    change_id: str | None = None
    patchset: str | None = None

    if url:
        path = unquote(urlparse(url).path)

        match = _GERRIT_CHANGE_RE.search(path)
        if match:
            change_id = match.group(1)
            patchset = match.group(2)
        else:
            match = _NUMERIC_TAIL_RE.search(path)
            if match and "/c/" in path:
                change_id = match.group(1)
                patchset = match.group(2)

    if not change_id:
        match = _CHANGE_ID_RE.search(query)
        if match:
            change_id = match.group(0)

    if not patchset:
        match = _PATCHSET_RE.search(query)
        if match:
            patchset = match.group(1)

    return {
        "url": url or None,
        "change_id": change_id,
        "patchset": patchset,
    }


def _extract_revision_sha(change_detail: dict, patchset: str | None) -> str | None:
    if patchset:
        try:
            patchset_number = int(patchset)
        except ValueError:
            patchset_number = None

        revisions = change_detail.get("revisions", {})
        if isinstance(revisions, dict) and patchset_number is not None:
            for revision_sha, revision_data in revisions.items():
                if not isinstance(revision_data, dict):
                    continue

                if revision_data.get("_number") == patchset_number and _SHA_RE.match(
                    revision_sha
                ):
                    return revision_sha

    current_revision = change_detail.get("current_revision")
    if isinstance(current_revision, str) and _SHA_RE.match(current_revision):
        return current_revision

    revisions = change_detail.get("revisions", {})
    if isinstance(revisions, dict):
        for revision_sha, revision_data in revisions.items():
            if not isinstance(revision_data, dict):
                continue
            if _SHA_RE.match(revision_sha):
                return revision_sha

    return None


def run_gerrit_review(query: str) -> dict:
    """
    Resolve a Gerrit link or change reference from *query* and run the
    existing Gerrit hook on that patchset.
    """

    reference = _extract_reference(query)
    change_id = reference["change_id"]
    patchset = reference["patchset"]

    if not change_id:
        return {
            "answer": (
                "No Gerrit change reference found. Paste a Gerrit link or include "
                "a change number / Change-Id / patchset hint."
            ),
            "count": 0,
            "rows": [],
        }

    try:
        client = GerritClient.from_env()
        change_detail = client.get_change_detail(change_id)
    except GerritAuthError as exc:
        return {
            "answer": str(exc),
            "count": 0,
            "rows": [],
        }
    except GerritAPIError as exc:
        return {
            "answer": f"Failed to load Gerrit change {change_id}: {exc}",
            "count": 0,
            "rows": [],
        }

    revision_sha = _extract_revision_sha(change_detail, patchset)
    if not revision_sha:
        return {
            "answer": (
                f"Could not resolve a revision SHA for Gerrit change {change_id}."
            ),
            "count": 0,
            "rows": [],
        }

    resolved_patchset = patchset
    if not resolved_patchset:
        revisions = change_detail.get("revisions", {})
        if isinstance(revisions, dict):
            revision_data = revisions.get(revision_sha, {})
            if isinstance(revision_data, dict) and revision_data.get("_number") is not None:
                resolved_patchset = str(revision_data.get("_number"))

    project = change_detail.get("project", "")
    branch = change_detail.get("branch", "")

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        rc = run_hook(
            change_id=change_id,
            commit=revision_sha,
            patchset=resolved_patchset or "current",
            project=project,
            branch=branch,
        )

    stdout_text = stdout_buffer.getvalue().strip()
    stderr_text = stderr_buffer.getvalue().strip()

    answer_lines = [
        f"Gerrit review completed for change {change_id}.",
        f"Revision: {revision_sha}",
    ]

    if resolved_patchset:
        answer_lines.append(f"Patchset: {resolved_patchset}")

    if rc == 0:
        answer_lines.append("Result: review posted successfully.")
    else:
        answer_lines.append(f"Result: review failed with exit code {rc}.")

    if stdout_text:
        answer_lines.append("")
        answer_lines.append(stdout_text)

    if stderr_text:
        answer_lines.append("")
        answer_lines.append("Errors:")
        answer_lines.append(stderr_text)

    return {
        "answer": "\n".join(answer_lines),
        "count": 1 if rc == 0 else 0,
        "rows": [],
    }