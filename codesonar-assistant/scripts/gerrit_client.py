"""
gerrit_client.py

Thin wrapper around the Gerrit REST API.

Responsibilities (and ONLY these):
  1. Post an inline/top-level review comment on a change revision.
  2. Cast a Verified vote (+1 or -1) on a change revision.
  3. Raise clear exceptions on HTTP errors — never swallow failures silently.

Authentication:
  Gerrit HTTP credentials (username + HTTP password generated in Gerrit UI).
  Configured via environment variables:
      GERRIT_URL           e.g. https://gerrit.example.com
      GERRIT_USER          Gerrit username
      GERRIT_HTTP_PASSWORD HTTP password from Gerrit account settings

Usage:
    client = GerritClient.from_env()
    client.post_review(
        change_id="Iabc123",
        revision_id="current",
        message="CodeSonar pre-commit review passed.",
        verified=1,
    )
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
import base64
from typing import Optional


class GerritAuthError(RuntimeError):
    """Raised when Gerrit credentials are missing or rejected."""


class GerritAPIError(RuntimeError):
    """Raised when the Gerrit REST API returns an unexpected status code."""


class GerritClient:
    """Minimal Gerrit REST API client (no third-party dependencies)."""

    def __init__(self, base_url: str, username: str, http_password: str) -> None:
        self._base_url = base_url.rstrip("/")
        credentials = f"{username}:{http_password}"
        self._auth_header = (
            "Basic " + base64.b64encode(credentials.encode()).decode()
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "GerritClient":
        """
        Build a GerritClient from environment variables.

        Required:
            GERRIT_URL, GERRIT_USER, GERRIT_HTTP_PASSWORD
        """
        url = os.environ.get("GERRIT_URL", "").strip()
        user = os.environ.get("GERRIT_USER", "").strip()
        password = os.environ.get("GERRIT_HTTP_PASSWORD", "").strip()

        missing = [
            name
            for name, val in [
                ("GERRIT_URL", url),
                ("GERRIT_USER", user),
                ("GERRIT_HTTP_PASSWORD", password),
            ]
            if not val
        ]
        if missing:
            raise GerritAuthError(
                f"Missing required Gerrit environment variables: {', '.join(missing)}"
            )

        return cls(url, user, password)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post_review(
        self,
        change_id: str,
        revision_id: str,
        message: str,
        verified: int,
        comments: Optional[dict] = None,
    ) -> None:
        """
        POST /changes/{change_id}/revisions/{revision_id}/review

        Parameters
        ----------
        change_id   : Gerrit change identifier (e.g. "Iabc123" or numeric ID).
        revision_id : Revision (e.g. "current" or a full commit SHA).
        message     : Top-level review message posted as a comment.
        verified    : +1 (pass) or -1 (fail) for the Verified label.
        comments    : Optional dict of per-file inline comments in Gerrit format:
                      { "filename.c": [{"line": N, "message": "..."}] }
        """
        if verified not in (1, -1):
            raise ValueError(f"verified must be +1 or -1, got {verified!r}")

        payload: dict = {
            "message": message,
            "labels": {"Verified": verified},
        }
        if comments:
            payload["comments"] = comments

        endpoint = (
            f"{self._base_url}/a/changes/{change_id}"
            f"/revisions/{revision_id}/review"
        )
        self._post_json(endpoint, payload)

    def get_changed_files(self, change_id: str, revision_id: str = "current") -> list[str]:
        """
        GET /changes/{change_id}/revisions/{revision_id}/files

        Returns a list of file paths modified in this revision.
        Gerrit prefixes a magic COMMIT_MSG entry — that is filtered out.
        """
        endpoint = (
            f"{self._base_url}/a/changes/{change_id}"
            f"/revisions/{revision_id}/files"
        )
        data = self._get_json(endpoint)
        return [f for f in data.keys() if not f.startswith("/COMMIT_MSG")]

    def get_change_detail(self, change_id: str) -> dict:
        """Return Gerrit change detail for resolving revision metadata."""
        endpoint = f"{self._base_url}/a/changes/{change_id}/detail"
        return self._get_json(endpoint)

    def get_revision_info(self, change_id: str, revision_id: str) -> dict:
        """Return Gerrit revision metadata for a specific revision."""
        endpoint = (
            f"{self._base_url}/a/changes/{change_id}"
            f"/revisions/{revision_id}"
        )
        return self._get_json(endpoint)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_json(self, url: str, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": self._auth_header,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        self._send(req, url)

    def _get_json(self, url: str) -> dict:
        req = urllib.request.Request(
            url,
            headers={"Authorization": self._auth_header},
            method="GET",
        )
        raw = self._send(req, url)
        # Gerrit prefixes responses with ")]}'\n" as XSSI protection
        if raw.startswith(b")]}"):
            raw = raw[raw.index(b"\n") + 1 :]
        return json.loads(raw.decode("utf-8"))

    def _send(self, req: urllib.request.Request, url: str) -> bytes:
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GerritAPIError(
                f"Gerrit API error {exc.code} for {url}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GerritAPIError(
                f"Network error reaching Gerrit at {url}: {exc.reason}"
            ) from exc
