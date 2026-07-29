#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from intent import detect_intent
from dispatcher import dispatch
from filters import filter_high_priority


SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parent
ENV_FILE = TASK_DIR / ".env"


def resolve_input_path(input_file: str) -> Path:
    """
    Resolve input paths relative to the current working directory and the
    task's standard data locations.
    """

    raw_path = Path(input_file).expanduser()

    candidates = []

    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend(
            [
                Path.cwd() / raw_path,
                SCRIPT_DIR / raw_path,
                TASK_DIR / raw_path,
            ]
        )

        if raw_path.name == "Master_Tracker.xlsx":
            candidates.append(TASK_DIR / "output" / raw_path.name)

        if raw_path.name == "codesonar.csv":
            candidates.append(TASK_DIR / "data" / raw_path.name)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved

    searched = "\n".join(f"- {path.resolve()}" for path in candidates)
    raise FileNotFoundError(
        f"Could not find input file '{input_file}'. Searched:\n{searched}\n"
        "Provide an existing .xlsx/.csv path, or place the tracker at "
        f"'{(TASK_DIR / 'output' / 'Master_Tracker.xlsx').resolve()}' "
        "or the raw report at "
        f"'{(TASK_DIR / 'data' / 'codesonar.csv').resolve()}'."
    )


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize CodeSonar CSV/Tracker columns.
    """

    renamed = df.copy()

    if "owner" in renamed.columns and "Owner" not in renamed.columns:
        renamed["Owner"] = renamed["owner"].fillna("")

    if "state" in renamed.columns and "Status" not in renamed.columns:
        renamed["Status"] = renamed["state"].fillna("")

    if "reviewer" in renamed.columns and "Reviewer" not in renamed.columns:
        renamed["Reviewer"] = renamed["reviewer"].fillna("")

    if "Owner" not in renamed.columns:
        renamed["Owner"] = ""

    if "Status" not in renamed.columns:
        renamed["Status"] = ""

    if "Reviewer" not in renamed.columns:
        renamed["Reviewer"] = ""

    renamed["Owner"] = renamed["Owner"].astype(str)
    renamed["Status"] = renamed["Status"].astype(str)
    renamed["Reviewer"] = renamed["Reviewer"].astype(str)

    return renamed


def load_input(input_file: str):
    """
    Load either Master Tracker (.xlsx) or raw CodeSonar CSV.
    """

    path = resolve_input_path(input_file)

    if path.suffix.lower() == ".xlsx":

        try:
            df = pd.read_excel(path, sheet_name="Details", dtype={"id": str})
        except ValueError:
            # Legacy workbook without a Details sheet name.
            df = pd.read_excel(path, dtype={"id": str})

        return normalize_columns(df), str(path)

    if path.suffix.lower() == ".csv":

        df = pd.read_csv(path, dtype={"id": str})

        df = filter_high_priority(normalize_columns(df))

        return df, str(path)

    raise ValueError("Input must be .xlsx or .csv")


def rows_for_display(df: pd.DataFrame, limit: int = 20):
    """
    Convert dataframe rows into JSON-friendly output.
    """

    preferred = [
        "id",
        "class",
        "priority",
        "Owner",
        "Status",
        "file",
        "line number",
    ]

    cols = [c for c in preferred if c in df.columns]

    if not cols:
        cols = list(df.columns)

    return df[cols].head(limit).to_dict(orient="records")


def _tail_lines(text: str, limit: int = 8) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def _load_dotenv_values(path: Path) -> dict[str, str]:
    """Minimal .env parser with KEY=VALUE lines and # comments."""

    values: dict[str, str] = {}

    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            values[key] = value

    return values


def _get_setting(name: str, dotenv_values: dict[str, str]) -> str | None:
    env_value = os.getenv(name)
    if env_value:
        return env_value
    return dotenv_values.get(name)


def _query_hint(query: str, field: str) -> str | None:
    pattern = rf"\b{field}\b\s*[:=]?\s*([^\s,]+)"
    match = re.search(pattern, query, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _query_list_hint(query: str, field: str) -> str | None:
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


def refresh_latest_codesonar_data_for_dashboard(query: str) -> list[str]:
    """
    Run daily workflow before dashboard so metrics come from freshly downloaded
    CodeSonar CSV data.

    Auth/options can be provided via environment variables or .env:
    - CODESONAR_REPORT_URL
    - CODESONAR_USERNAME
    - CODESONAR_PASSWORD
    - CODESONAR_COOKIE
    - CODESONAR_TOKEN
    - CODESONAR_OWNERS
    - CODESONAR_REVIEWERS
    - CODESONAR_INSECURE=true|1
    """

    cmd = [sys.executable, str(SCRIPT_DIR / "daily_workflow.py")]

    dotenv_values = _load_dotenv_values(ENV_FILE)

    report_url = _get_setting("CODESONAR_REPORT_URL", dotenv_values)
    username = _get_setting("CODESONAR_USERNAME", dotenv_values)
    password = _get_setting("CODESONAR_PASSWORD", dotenv_values)
    cookie = _get_setting("CODESONAR_COOKIE", dotenv_values)
    token = _get_setting("CODESONAR_TOKEN", dotenv_values)
    owners = _get_setting("CODESONAR_OWNERS", dotenv_values)
    reviewers = _get_setting("CODESONAR_REVIEWERS", dotenv_values)
    insecure_raw = _get_setting("CODESONAR_INSECURE", dotenv_values) or ""

    # Optional per-query hints for multi-user usage.
    query_username = _query_hint(query, "username")
    query_owners = _query_list_hint(query, "owners")
    query_reviewers = _query_list_hint(query, "reviewers")

    if query_username and not username:
        username = query_username
    if query_owners and not owners:
        owners = query_owners
    if query_reviewers and not reviewers:
        reviewers = query_reviewers

    insecure = insecure_raw.lower() in {"1", "true", "yes"}

    if report_url:
        cmd.extend(["--report-url", report_url])
    if username:
        cmd.extend(["--username", username])
    if password:
        cmd.extend(["--password", password])
    if cookie:
        cmd.extend(["--cookie", cookie])
    if token:
        cmd.extend(["--token", token])
    if owners:
        cmd.extend(["--owners", owners])
    if reviewers:
        cmd.extend(["--reviewers", reviewers])
    if insecure:
        cmd.append("--insecure")

    completed = subprocess.run(
        cmd,
        cwd=str(TASK_DIR),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    stdout_lines = _tail_lines(completed.stdout)
    stderr_lines = _tail_lines(completed.stderr)

    if completed.returncode != 0:
        details = "\n".join(stdout_lines + stderr_lines)
        raise RuntimeError(
            "Dashboard refresh failed while downloading latest CodeSonar CSV. "
            "Set user-specific CODESONAR auth env vars (or .env) and a report URL.\n"
            f"Expected env file: {ENV_FILE}\n"
            f"Workflow output:\n{details}"
        )

    return stdout_lines


def answer(df: pd.DataFrame, query: str, intent: str | None = None):
    """
    Main AI entry point.
    """

    effective_intent = intent or detect_intent(query)
    print("Intent:", effective_intent)

    response = dispatch(df, effective_intent, query)

    # If dispatcher returned a dataframe, convert it
    if isinstance(response, pd.DataFrame):

        if len(response) == 0:
            return {
                "answer": "No matching issues found.",
                "count": 0,
                "rows": [],
            }

        return {
            "answer": f"Found {len(response)} issue(s).",
            "count": len(response),
            "rows": rows_for_display(response),
        }

    # Otherwise dispatcher returned a dictionary
    return response


def main():

    parser = argparse.ArgumentParser(
        description="CodeSonar AI Assistant"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to Master_Tracker.xlsx or CodeSonar CSV",
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Natural language question",
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format",
    )

    args = parser.parse_args()

    intent = detect_intent(args.query)

    source = None
    if intent == "dashboard":
        dashboard_tracker = TASK_DIR / "output" / "Master_Tracker.xlsx"
        try:
            refresh_latest_codesonar_data_for_dashboard(args.query)
        except RuntimeError as exc:
            payload = {
                "source": str(dashboard_tracker),
                "answer": str(exc),
                "count": 0,
                "rows": [],
            }
            if args.format == "json":
                print(json.dumps(payload, indent=2))
            else:
                print(f"Source : {payload['source']}")
                print(payload["answer"])
            return
        # Read the tracker (not the raw CSV) so Owner/Reviewer assignments are included.
        df, source = load_input(str(dashboard_tracker))
    else:
        df, source = load_input(args.input)

    response = answer(df, args.query, intent=intent)

    payload = {
        "source": source,
        "answer": response["answer"],
        "count": response["count"],
        "rows": response["rows"],
    }

    if args.format == "json":

        print(json.dumps(payload, indent=2))

    else:

        print(f"Source : {source}")
        print(payload["answer"])

        if payload["rows"]:
            print(json.dumps(payload["rows"], indent=2))


if __name__ == "__main__":
    main()
