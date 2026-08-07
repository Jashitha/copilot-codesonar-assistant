#!/usr/bin/env python3
"""
gerrit_event_listener.py

Gerrit SSH event-stream listener daemon.

Connects to Gerrit via SSH (`gerrit stream-events`) and automatically
triggers gerrit_hook.run_hook() on every patchset-created event —
no server-side file deployment needed.

Setup
-----
1. Add the required environment variables to .env (see .env.example):
       GERRIT_URL             https://gerrit.example.com
       GERRIT_SSH_HOST        gerrit.example.com   (hostname only, no scheme)
       GERRIT_SSH_PORT        29418                (default Gerrit SSH port)
       GERRIT_USER            your-username
       GERRIT_HTTP_PASSWORD   HTTP password from Gerrit account settings
       GERRIT_SSH_KEY         (optional) path to SSH private key
                              defaults to ~/.ssh/id_rsa

2. Run the listener:
       python3 gerrit_event_listener.py

   Or as a background service:
       nohup python3 gerrit_event_listener.py >> ../logs/gerrit_listener.log 2>&1 &

   Or with systemd — see docs/gerrit_listener.service.example

The listener reconnects automatically on SSH disconnection with
exponential back-off (max 60 s).

Gerrit stream-events requires the caller to have the
"Stream Events" capability in Gerrit (granted to registered users by default
on most installations).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load .env
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_TASK_DIR = _SCRIPT_DIR.parent
_LOG_DIR = _TASK_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

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

sys.path.insert(0, str(_SCRIPT_DIR))
from gerrit_hook import run_hook  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_RECONNECT_BASE = 5    # seconds before first reconnect attempt
_RECONNECT_MAX  = 60   # cap back-off at 60 seconds


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def _build_ssh_command() -> list[str]:
    """
    Build the SSH command that opens the Gerrit event stream.

    ssh [-i <key>] -p <port> <user>@<host> gerrit stream-events
    """
    host = os.environ.get("GERRIT_SSH_HOST", "").strip()
    port = os.environ.get("GERRIT_SSH_PORT", "29418").strip()
    user = os.environ.get("GERRIT_USER", "").strip()
    key  = os.environ.get("GERRIT_SSH_KEY", "").strip()

    if not host:
        # Try to extract hostname from GERRIT_URL
        url = os.environ.get("GERRIT_URL", "").strip()
        if url:
            host = url.split("//")[-1].split("/")[0].split(":")[0]

    if not host or not user:
        missing = []
        if not host:
            missing.append("GERRIT_SSH_HOST (or GERRIT_URL)")
        if not user:
            missing.append("GERRIT_USER")
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    cmd = ["ssh"]
    if key:
        cmd += ["-i", key]
    cmd += [
        "-p", port,
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        f"{user}@{host}",
        "gerrit", "stream-events",
    ]
    return cmd


def _handle_event(event: dict) -> None:
    """Process a single Gerrit event dict."""
    if event.get("type") != "patchset-created":
        return

    change    = event.get("change", {})
    patchset  = event.get("patchSet", {})
    project   = change.get("project", "")
    branch    = change.get("branch", "")
    change_id = change.get("id", "")
    number    = str(change.get("number", ""))
    commit    = patchset.get("revision", "")
    ps_number = str(patchset.get("number", "1"))
    owner     = change.get("owner", {}).get("name", "unknown")

    _log(
        f"patchset-created  project={project}  branch={branch}  "
        f"change={number}  patchset={ps_number}  owner={owner}"
    )

    if not change_id or not commit:
        _log("WARNING: event missing change id or commit SHA — skipping.")
        return

    try:
        rc = run_hook(
            change_id=number or change_id,
            commit=commit,
            patchset=ps_number,
            project=project,
            branch=branch,
        )
        if rc == 0:
            _log(f"Hook completed successfully for change {number}.")
        else:
            _log(f"Hook returned non-zero exit code {rc} for change {number}.")
    except Exception as exc:  # pylint: disable=broad-except
        _log(f"ERROR running hook for change {number}: {exc}")


def _stream_events(cmd: list[str]) -> None:
    """
    Open the SSH stream-events subprocess and process lines until it exits.
    Raises subprocess.CalledProcessError / OSError on failure.
    """
    _log(f"Connecting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        for raw_line in proc.stdout:  # type: ignore[union-attr]
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                _log(f"Non-JSON line from Gerrit: {raw_line[:120]}")
                continue
            _handle_event(event)
    finally:
        proc.stdout.close()   # type: ignore[union-attr]
        proc.wait()
        if proc.returncode not in (0, -15):  # -15 = SIGTERM (clean stop)
            stderr_out = proc.stderr.read() if proc.stderr else ""
            _log(
                f"SSH process exited with code {proc.returncode}. "
                f"stderr: {stderr_out.strip()[:200]}"
            )


def run_listener() -> None:
    """
    Main loop — connects and reconnects on failure with exponential back-off.
    Runs until interrupted with Ctrl-C / SIGTERM.
    """
    try:
        cmd = _build_ssh_command()
    except EnvironmentError as exc:
        _log(f"Configuration error: {exc}")
        sys.exit(1)

    backoff = _RECONNECT_BASE
    _log("Gerrit event listener starting.")

    while True:
        try:
            _stream_events(cmd)
        except KeyboardInterrupt:
            _log("Listener stopped by user.")
            break
        except Exception as exc:  # pylint: disable=broad-except
            _log(f"Stream error: {exc}")

        _log(f"Reconnecting in {backoff}s …")
        time.sleep(backoff)
        backoff = min(backoff * 2, _RECONNECT_MAX)


if __name__ == "__main__":
    run_listener()
