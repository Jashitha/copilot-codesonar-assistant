#!/usr/bin/env python3

"""
Daily workflow for CodeSonar tracker maintenance.

Flow:
1. Download latest CodeSonar CSV report.
2. Create or update Master_Tracker.xlsx.
3. Keep only HB_PRIO_1 / HB_PRIO_2 findings.
4. Preserve owner/status/ETA for existing issues.
5. Auto-assign new issues when owner pool is provided.
6. Save today's tracker snapshot.
"""

from __future__ import annotations

import argparse
import os
import io
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
import requests

from filters import filter_high_priority
from parser import read_codesonar_report
from report_generator import save_tracker_report
from sync import sync_tracker

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parent
DATA_DIR = TASK_DIR / "data"
OUTPUT_DIR = TASK_DIR / "output"

from env_bootstrap import ensure_env_file

ENV_FILE = ensure_env_file(TASK_DIR)

DEFAULT_PROJECT_URL = "https://codesonar-idc.harman.com:7340/project/2601.html?theme=light"


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

def _load_dotenv_values(path: Path) -> dict:
    """Parse a KEY=VALUE .env file; ignores comments and blank lines."""
    vals: dict = {}
    if not path.exists():
        return vals
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    return vals


def _apply_env_defaults(args: argparse.Namespace) -> argparse.Namespace:
    """Fill missing CLI args from environment variables or .env file."""
    env = _load_dotenv_values(ENV_FILE)

    def _get(name: str) -> str | None:
        return os.environ.get(name) or env.get(name) or None

    if not args.report_url or args.report_url == DEFAULT_PROJECT_URL:
        v = _get("CODESONAR_REPORT_URL")
        if v:
            args.report_url = v
    if not args.username:
        args.username = _get("CODESONAR_USERNAME")
    if not args.password:
        args.password = _get("CODESONAR_PASSWORD")
    if not args.cookie:
        args.cookie = _get("CODESONAR_COOKIE")
    if not args.token:
        args.token = _get("CODESONAR_TOKEN")
    if not args.owners:
        args.owners = _get("CODESONAR_OWNERS")
    if not args.reviewers:
        args.reviewers = _get("CODESONAR_REVIEWERS")
    insecure_env = _get("CODESONAR_INSECURE")
    if not args.insecure and insecure_env and insecure_env.lower() in ("1", "true", "yes"):
        args.insecure = True
    return args


class WorkflowError(RuntimeError):
    """Raised for recoverable workflow errors with user-facing messages."""


def _candidate_report_urls(url: str) -> list[str]:
    """
    Build candidate URLs for CSV download.

    If a project HTML URL is provided, also try the same path with .csv.
    """

    candidates = [url]

    if ".html" in url:
        parts = urlsplit(url)
        csv_path = parts.path.replace(".html", ".csv")
        csv_url = urlunsplit((parts.scheme, parts.netloc, csv_path, parts.query, parts.fragment))
        if csv_url != url:
            candidates.insert(0, csv_url)

    return candidates


def _looks_like_csv(content: bytes) -> bool:
    head = content[:2048].decode("utf-8", errors="ignore").lower()
    if "<html" in head or "<!doctype html" in head:
        return False
    return "," in head


def _download_csv_bytes(
    url: str,
    username: str | None,
    password: str | None,
    cookie: str | None,
    token: str | None,
    verify_tls: bool,
    timeout_sec: int,
) -> bytes | None:
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    if token:
        headers["Authorization"] = f"Bearer {token}"

    auth = (username, password) if username and password else None

    response = requests.get(
        url,
        headers=headers,
        auth=auth,
        timeout=timeout_sec,
        verify=verify_tls,
        allow_redirects=True,
    )

    if response.status_code >= 400:
        return None

    body = response.content
    if not _looks_like_csv(body):
        return None

    return body


def download_latest_report(
    report_url: str,
    destination: Path,
    username: str | None,
    password: str | None,
    cookie: str | None,
    token: str | None,
    verify_tls: bool,
    timeout_sec: int,
) -> Path:
    """Download the latest CodeSonar CSV report to destination."""

    tried = []

    for url in _candidate_report_urls(report_url):
        tried.append(url)
        body = _download_csv_bytes(
            url=url,
            username=username,
            password=password,
            cookie=cookie,
            token=token,
            verify_tls=verify_tls,
            timeout_sec=timeout_sec,
        )
        if body is None:
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        return destination

    tried_message = "\n".join(f"- {item}" for item in tried)
    raise WorkflowError(
        "Could not download a CSV report from the provided URL(s). "
        "The endpoint may require authentication or may not be a CSV export URL.\n"
        f"Tried:\n{tried_message}\n"
        "Tip: use the direct CodeSonar CSV export URL (not just the project HTML page), "
        "or provide credentials/cookie/token options."
    )


def _csv_has_issue_columns(csv_path: Path) -> bool:
    try:
        columns = pd.read_csv(csv_path, nrows=0).columns.tolist()
    except Exception:
        return False

    lowered = {str(col).strip().lower() for col in columns}
    return "id" in lowered and "priority" in lowered


def _maybe_resolve_analysis_index_to_issue_csv(
    csv_path: Path,
    report_url: str,
    username: str | None,
    password: str | None,
    cookie: str | None,
    token: str | None,
    verify_tls: bool,
    timeout_sec: int,
) -> str | None:
    """If project CSV is an analysis index, follow its URL links to fetch issue CSV."""

    if _csv_has_issue_columns(csv_path):
        return None

    try:
        index_df = pd.read_csv(csv_path, dtype=str)
    except Exception as exc:
        raise WorkflowError(f"Downloaded CSV could not be parsed: {exc}")

    normalized_cols = {str(c).strip().lower(): c for c in index_df.columns}
    url_col = normalized_cols.get("url")
    if not url_col:
        raise WorkflowError(
            "Downloaded CSV does not include issue columns and has no URL field to follow. "
            "Provide a direct issue-level CSV export URL."
        )

    state_col = normalized_cols.get("state")
    candidates = index_df.copy()

    if state_col:
        finished = candidates[candidates[state_col].astype(str).str.lower() == "finished"]
        if not finished.empty:
            candidates = finished

    base = urlsplit(report_url)
    root = f"{base.scheme}://{base.netloc}"

    for _, row in candidates.iterrows():
        rel = str(row.get(url_col, "")).strip()
        if not rel:
            continue

        issue_url = urljoin(root + "/", rel.lstrip("/"))
        body = _download_csv_bytes(
            url=issue_url,
            username=username,
            password=password,
            cookie=cookie,
            token=token,
            verify_tls=verify_tls,
            timeout_sec=timeout_sec,
        )
        if body is None:
            continue

        try:
            test_cols = pd.read_csv(io.BytesIO(body), nrows=0).columns.tolist()
        except Exception:
            continue

        lowered = {str(col).strip().lower() for col in test_cols}
        if "id" not in lowered:
            continue

        csv_path.write_bytes(body)
        return issue_url

    raise WorkflowError(
        "Downloaded the project analysis index, but could not fetch an issue-level CSV from its URLs. "
        "Use a direct issue export URL or verify permissions for analysis CSV endpoints."
    )


def _normalize_pool(raw: str | None) -> list[str]:
    if not raw:
        return []

    values = [item.strip() for item in raw.split(",") if item.strip()]
    return list(dict.fromkeys(values))


def _normalize_owner_pool(raw: str | None) -> list[str]:
    return _normalize_pool(raw)


def _normalize_reviewer_pool(raw: str | None) -> list[str]:
    return _normalize_pool(raw)


def _existing_owner_pool(master_df: pd.DataFrame) -> list[str]:
    if "Owner" not in master_df.columns:
        return []

    owners = (
        master_df["Owner"]
        .astype(str)
        .str.strip()
        .replace({"": "Unassigned"})
        .unique()
        .tolist()
    )

    return [o for o in owners if o.lower() != "unassigned"]


def _existing_reviewer_pool(master_df: pd.DataFrame) -> list[str]:
    if "Reviewer" not in master_df.columns:
        return []

    reviewers = (
        master_df["Reviewer"]
        .astype(str)
        .str.strip()
        .replace({"": "Unassigned"})
        .unique()
        .tolist()
    )

    return [r for r in reviewers if r.lower() != "unassigned"]


def _assign_new_issues(updated_df: pd.DataFrame, new_issue_ids: Iterable[str], owners: list[str]) -> None:
    """Assign owners for newly introduced IDs currently unassigned."""

    if not owners:
        return

    new_ids = {str(item).strip() for item in new_issue_ids}
    if not new_ids:
        return

    if "Owner" not in updated_df.columns:
        updated_df["Owner"] = "Unassigned"

    owner_counts = defaultdict(int)
    normalized_owner = updated_df["Owner"].astype(str).str.strip()

    for owner in owners:
        owner_counts[owner] = int((normalized_owner == owner).sum())

    for idx, row in updated_df.iterrows():
        issue_id = str(row.get("id", "")).strip()
        if issue_id not in new_ids:
            continue

        current_owner = str(row.get("Owner", "")).strip()
        if current_owner and current_owner.lower() != "unassigned":
            continue

        selected_owner = min(owners, key=lambda o: owner_counts[o])
        updated_df.at[idx, "Owner"] = selected_owner
        owner_counts[selected_owner] += 1


def _assign_reviewers(updated_df: pd.DataFrame, new_issue_ids: Iterable[str], reviewers: list[str], fill_unassigned: bool = False) -> None:
    """Assign reviewer for new IDs (and optionally all Unassigned); prefer someone different from owner."""

    if not reviewers:
        return

    new_ids = {str(item).strip() for item in new_issue_ids}

    # When fill_unassigned is True (explicit reviewer pool provided), also fill existing Unassigned reviewers
    if fill_unassigned:
        unassigned_ids = set(
            updated_df.loc[
                updated_df.get("Reviewer", pd.Series(dtype=str)).astype(str).str.strip().str.lower() == "unassigned",
                "id"
            ].astype(str).tolist()
        )
        new_ids = new_ids | unassigned_ids

    if not new_ids:
        return

    if "Reviewer" not in updated_df.columns:
        updated_df["Reviewer"] = "Unassigned"

    reviewer_counts = defaultdict(int)
    normalized_reviewer = updated_df["Reviewer"].astype(str).str.strip()

    for reviewer in reviewers:
        reviewer_counts[reviewer] = int((normalized_reviewer == reviewer).sum())

    for idx, row in updated_df.iterrows():
        issue_id = str(row.get("id", "")).strip()
        if issue_id not in new_ids:
            continue

        current_reviewer = str(row.get("Reviewer", "")).strip()
        if current_reviewer and current_reviewer.lower() != "unassigned":
            continue

        owner = str(row.get("Owner", "")).strip()
        eligible = [r for r in reviewers if r != owner]
        if not eligible:
            eligible = reviewers

        selected_reviewer = min(eligible, key=lambda r: reviewer_counts[r])
        updated_df.at[idx, "Reviewer"] = selected_reviewer
        reviewer_counts[selected_reviewer] += 1


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    if "Owner" not in result.columns:
        result["Owner"] = "Unassigned"

    if "Status" not in result.columns:
        result["Status"] = "Pending"

    if "ETA" not in result.columns:
        result["ETA"] = ""

    if "Reviewer" not in result.columns:
        result["Reviewer"] = "Unassigned"

    if "ReviewStatus" not in result.columns:
        result["ReviewStatus"] = "Pending"

    if "ReviewETA" not in result.columns:
        result["ReviewETA"] = ""

    result["Owner"] = result["Owner"].fillna("Unassigned")
    result["Status"] = result["Status"].fillna("Pending")
    result["ETA"] = result["ETA"].fillna("")

    result["Reviewer"] = result["Reviewer"].fillna("Unassigned")
    result["ReviewStatus"] = result["ReviewStatus"].fillna("Pending")
    result["ReviewETA"] = result["ReviewETA"].fillna("")

    return result


def _read_master_tracker(tracker_path: Path) -> pd.DataFrame:
    """Read back the tracker's Details sheet and normalize columns for sync."""
    try:
        master_df = pd.read_excel(tracker_path, sheet_name="Details", dtype={"id": str})
    except ValueError:
        # Older/legacy workbook without a Details sheet name.
        master_df = pd.read_excel(tracker_path, dtype={"id": str})

    if "owner" in master_df.columns and "Owner" not in master_df.columns:
        master_df = master_df.rename(columns={"owner": "Owner"})
    if "state" in master_df.columns and "Status" not in master_df.columns:
        master_df = master_df.rename(columns={"state": "Status"})

    return master_df


def update_tracker_history(
    df: pd.DataFrame,
    new_count: int,
    resolved_count: int,
) -> Path:
    """Append today's snapshot to output/Tracker_History.xlsx.

    Columns: Date, Total, HB1, HB2, New, Resolved.
    If a row for today already exists it is overwritten.
    """
    history_path = OUTPUT_DIR / "Tracker_History.xlsx"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    today_label = datetime.now().strftime("%b-%d")  # e.g. "Jul-27"

    hb1 = int((df["priority"] == "HB_PRIO_1").sum()) if "priority" in df.columns else 0
    hb2 = int((df["priority"] == "HB_PRIO_2").sum()) if "priority" in df.columns else 0
    total = len(df)

    new_row = pd.DataFrame(
        [{"Date": today_label, "Total": total, "HB1": hb1, "HB2": hb2,
          "New": new_count, "Resolved": resolved_count}]
    )

    if history_path.exists():
        history_df = pd.read_excel(history_path, dtype=str)
        # Drop any existing row for the same date so today's run wins
        history_df = history_df[history_df["Date"].astype(str) != today_label]
        history_df = pd.concat([history_df, new_row], ignore_index=True)
    else:
        history_df = new_row

    # Coerce numeric columns to int for clean display
    for col in ("Total", "HB1", "HB2", "New", "Resolved"):
        if col in history_df.columns:
            history_df[col] = pd.to_numeric(history_df[col], errors="coerce").fillna(0).astype(int)

    history_df.to_excel(history_path, index=False)
    return history_path


def _print_summary(
    df: pd.DataFrame,
    raw_count: int,
    new_count: int,
    resolved_count: int,
    reopened_count: int,
    owners_preserved: int,
    new_owner_assignments: int,
    new_reviewer_assignments: int,
    archive_csv: Path,
    tracker_path: Path,
    daily_tracker: Path,
    history_path: Path | None = None,
) -> None:
    hb1 = int((df["priority"] == "HB_PRIO_1").sum()) if "priority" in df.columns else 0
    hb2 = int((df["priority"] == "HB_PRIO_2").sum()) if "priority" in df.columns else 0
    filtered_total = hb1 + hb2

    W = 42
    SEP = "-" * W

    def _row(label: str, value) -> str:
        return f"  {label:<30}{value:>10}"

    print()
    print("=" * W)
    print("  CodeSonar Update Tracker — Summary")
    print("=" * W)

    print()
    print("  Downloaded:")
    print(f"    {archive_csv.name}")

    print()
    print("  Filter Results")
    print(f"  {SEP}")
    print(_row("Original findings :", f"{raw_count:,}"))
    print(_row("HB_PRIO_1         :", f"{hb1:,}"))
    print(_row("HB_PRIO_2         :", f"{hb2:,}"))
    print(_row("Filtered total    :", f"{filtered_total:,}"))

    print()
    print("  Tracker Sync")
    print(f"  {SEP}")
    existing = len(df) - new_count
    print(_row("Existing issues   :", f"{existing:,}"))
    print(_row("New issues        :", f"{new_count:,}"))
    print(_row("Resolved issues   :", f"{resolved_count:,}"))
    print(_row("Reopened issues   :", f"{reopened_count:,}"))

    print()
    print("  Assignments")
    print(f"  {SEP}")
    print(_row("Owners preserved      :", f"{owners_preserved:,}"))
    print(_row("New owner assignments :", f"{new_owner_assignments:,}"))
    print(_row("Reviewers assigned    :", f"{new_reviewer_assignments:,}"))

    print()
    print("  Generated Files")
    print(f"  {SEP}")
    for path in [tracker_path, daily_tracker, history_path]:
        if path and path.exists():
            print(f"  ✓ {path.relative_to(TASK_DIR)}")
        elif path:
            print(f"  ✗ {path.relative_to(TASK_DIR)}  (not created)")

    print()
    print("=" * W)


def run_daily_workflow(args: argparse.Namespace) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")

    latest_csv    = DATA_DIR   / "codesonar.csv"
    archive_csv   = DATA_DIR   / f"codesonar_{today}.csv"
    tracker_path  = OUTPUT_DIR / "Master_Tracker.xlsx"
    daily_tracker = OUTPUT_DIR / f"Master_Tracker_{today}.xlsx"

    # ── Download ──────────────────────────────────────────────────────────────
    print("Downloading latest CodeSonar report...")
    downloaded_csv = download_latest_report(
        report_url=args.report_url,
        destination=latest_csv,
        username=args.username,
        password=args.password,
        cookie=args.cookie,
        token=args.token,
        verify_tls=not args.insecure,
        timeout_sec=args.timeout,
    )
    resolved_url = _maybe_resolve_analysis_index_to_issue_csv(
        csv_path=downloaded_csv,
        report_url=args.report_url,
        username=args.username,
        password=args.password,
        cookie=args.cookie,
        token=args.token,
        verify_tls=not args.insecure,
        timeout_sec=args.timeout,
    )
    archive_csv.write_bytes(downloaded_csv.read_bytes())

    # ── Filter ────────────────────────────────────────────────────────────────
    raw_df     = read_codesonar_report(str(downloaded_csv))
    raw_count  = len(raw_df)
    latest_df  = filter_high_priority(raw_df)
    latest_df  = _ensure_columns(latest_df)

    # ── Sync / create tracker ─────────────────────────────────────────────────
    reopened_count           = 0
    new_owner_assignments    = 0
    new_reviewer_assignments = 0
    owners_preserved         = 0

    if tracker_path.exists():
        master_df = _read_master_tracker(tracker_path)
        master_df = _ensure_columns(master_df)

        latest_df["id"]  = latest_df["id"].astype(str).str.strip()
        master_df["id"]  = master_df["id"].astype(str).str.strip()

        latest_sync_df = latest_df.drop(
            columns=["Owner", "Status", "ETA", "Reviewer", "ReviewStatus", "ReviewETA"],
            errors="ignore",
        )
        updated_df, new_df, resolved_df = sync_tracker(master_df, latest_sync_df)

        # Reopened = issues that were Done in master but back in latest
        if "Status" in master_df.columns:
            done_ids = set(master_df.loc[master_df["Status"].str.lower() == "done", "id"].astype(str))
            latest_ids = set(latest_df["id"].astype(str))
            reopened_count = len(done_ids & latest_ids)

        # Count preserved (non-Unassigned) owners before assignment
        owners_preserved = int(
            (updated_df["Owner"].astype(str).str.strip().str.lower() != "unassigned").sum()
        )

        owner_pool      = _normalize_owner_pool(args.owners) or _existing_owner_pool(master_df)
        explicit_rev    = _normalize_reviewer_pool(args.reviewers)
        reviewer_pool   = explicit_rev or _existing_reviewer_pool(master_df) or owner_pool

        new_ids_list = new_df["id"].astype(str).tolist()
        _assign_new_issues(updated_df, new_ids_list, owner_pool)
        _assign_reviewers(updated_df, new_ids_list, reviewer_pool, fill_unassigned=bool(explicit_rev))

        # Count what was actually assigned
        new_owner_assignments = int(
            updated_df.loc[updated_df["id"].isin(new_ids_list), "Owner"]
            .astype(str).str.strip().str.lower().ne("unassigned").sum()
        )
        new_reviewer_assignments = int(
            updated_df.loc[updated_df["id"].isin(new_ids_list), "Reviewer"]
            .astype(str).str.strip().str.lower().ne("unassigned").sum()
        )

        final_df       = _ensure_columns(updated_df)
        new_count      = len(new_df)
        resolved_count = len(resolved_df)

    else:
        final_df = latest_df.copy()
        owner_pool    = _normalize_owner_pool(args.owners)
        reviewer_pool = _normalize_reviewer_pool(args.reviewers)

        all_ids = final_df["id"].astype(str).tolist()
        if owner_pool:
            _assign_new_issues(final_df, all_ids, owner_pool)
        if reviewer_pool:
            _assign_reviewers(final_df, all_ids, reviewer_pool, fill_unassigned=True)

        new_owner_assignments    = int(
            final_df["Owner"].astype(str).str.strip().str.lower().ne("unassigned").sum()
        )
        new_reviewer_assignments = int(
            final_df["Reviewer"].astype(str).str.strip().str.lower().ne("unassigned").sum()
        )
        final_df       = _ensure_columns(final_df)
        new_count      = len(final_df)
        resolved_count = 0
        owners_preserved = 0

    # ── Save tracker (Summary + Details sheets) ─────────────────────────────
    save_tracker_report(final_df, tracker_path)
    save_tracker_report(final_df, daily_tracker)

    # ── History ───────────────────────────────────────────────────────────────
    history_path: Path | None = None
    try:
        history_path = update_tracker_history(
            df=final_df,
            new_count=new_count,
            resolved_count=resolved_count,
        )
    except Exception as exc:
        print(f"[warn] Tracker history update skipped: {exc}")

    # ── Rich summary ──────────────────────────────────────────────────────────
    _print_summary(
        df=final_df,
        raw_count=raw_count,
        new_count=new_count,
        resolved_count=resolved_count,
        reopened_count=reopened_count,
        owners_preserved=owners_preserved,
        new_owner_assignments=new_owner_assignments,
        new_reviewer_assignments=new_reviewer_assignments,
        archive_csv=archive_csv,
        tracker_path=tracker_path,
        daily_tracker=daily_tracker,
        history_path=history_path,
    )

    # ── Interactive dashboard (v2.0) ────────────────────────────────────────
    # Regenerate the static HTML dashboard from the tracker we just wrote.
    # Best-effort only: a dashboard rendering issue must never fail the
    # Update Tracker workflow itself.
    try:
        from dashboard import generate_dashboard
        dashboard_result = generate_dashboard(TASK_DIR)
        print(f"  Dashboard          : {dashboard_result['message']}")
    except Exception as exc:
        print(f"[warn] Dashboard generation skipped: {exc}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CodeSonar daily workflow")

    parser.add_argument(
        "--report-url",
        default=DEFAULT_PROJECT_URL,
        help="CodeSonar report URL (prefer direct CSV export URL).",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Username for HTTP auth if required.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password for HTTP auth if required.",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Raw Cookie header value for authenticated downloads.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token for authenticated downloads.",
    )
    parser.add_argument(
        "--owners",
        default=None,
        help="Comma-separated owner list used for auto-assignment of new issues.",
    )
    parser.add_argument(
        "--reviewers",
        default=None,
        help="Comma-separated reviewer list used for assigning reviews of new issues.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Download timeout in seconds.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for report download.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args = _apply_env_defaults(args)

    try:
        return run_daily_workflow(args)
    except WorkflowError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
