#!/usr/bin/env python3
"""
scripts/dashboard.py

CodeSonar Assistant v2.0 — Interactive HTML Dashboard generator.

This module is independent of the chat-based "dashboard" query handler in
tools/dashboard.py. It reads the already-generated output/Master_Tracker.xlsx
(and, if present, output/Tracker_History.xlsx) and renders a fully static,
project-generic dashboard:

    output/dashboard/
        index.html
        dashboard_data.json
        css/style.css
        js/dashboard.js
        assets/

The dashboard is 100% static HTML + CSS + JavaScript (Chart.js via CDN) and
requires no Flask/Django/Node.js/web server — just open index.html.

Design note: index.html embeds the dashboard data inline (as a JavaScript
global, not via fetch()) because browsers block fetch()/XHR of local files
opened directly from disk (file:// CORS restrictions). dashboard_data.json is
still written out separately so the same data can be consumed by other tools.

This module never re-implements tracker generation/sync logic — it only reads
the finished tracker file and reuses existing helpers (hotspot_analysis,
issue_explanations) for enrichment.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from hotspot_analysis import hotspot_analysis
from issue_explanations import FIX_GUIDE, ISSUE_EXPLANATIONS

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parent


def _env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to default on missing/invalid value."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float env var, falling back to default on missing/invalid value."""
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# ASPICE-style release-readiness thresholds (Quality Gates / Compliance).
# Overridable per project via environment variables (.env), mirroring the
# existing CODESONAR_OWNERS/REVIEWERS convention used by daily_workflow.py,
# so no code changes are needed to tune thresholds for a given project.
# ---------------------------------------------------------------------------
QUALITY_GATE_CONFIG = {
    # Max HB_PRIO_1 findings allowed in the tracker for the "HB_PRIO_1
    # Threshold" gate/compliance indicator to PASS/be green.
    "hb_prio_1_max": _env_int("CODESONAR_GATE_HB1_MAX", 0),
    # Minimum completion % (Done / Total) for "Review Completion" to PASS.
    "review_completion_min_pct": _env_float("CODESONAR_GATE_REVIEW_MIN_PCT", 80.0),
    # Max % of findings allowed to remain Unassigned for "Owner Assignment".
    "unassigned_max_pct": _env_float("CODESONAR_GATE_UNASSIGNED_MAX_PCT", 10.0),
}

# Details-sheet column names exactly as written by report_generator.py.
COL_ID = "id"
COL_CLASS = "class"
COL_FILE = "file"
COL_LINE = "line number"
COL_PROCEDURE = "procedure"
COL_PRIORITY = "priority"
COL_STATE = "state"
COL_FINDING = "finding"
COL_OWNER = "owner"
COL_URL = "url"


# ---------------------------------------------------------------------------
# Tracker loading (read-only — does not touch tracker generation/sync logic)
# ---------------------------------------------------------------------------

def _blank_to_unassigned(series: pd.Series) -> pd.Series:
    """Collapse blank/NaN/'unassigned'/'none' values into a single label."""
    values = series.astype(str).str.strip()
    mask = values.str.lower().isin(["", "nan", "unassigned", "none"])
    return values.mask(mask, "Unassigned")


def load_tracker(tracker_path: Path) -> pd.DataFrame:
    """Read the Details sheet of Master_Tracker.xlsx and normalize columns.

    Mirrors the light column-normalization convention already used elsewhere
    in this project (owner -> Owner, state -> Status) so the dashboard reads
    the exact same data the rest of the assistant uses.
    """
    try:
        df = pd.read_excel(tracker_path, sheet_name="Details", dtype={COL_ID: str})
    except ValueError:
        # Legacy workbook without a named "Details" sheet.
        df = pd.read_excel(tracker_path, dtype={COL_ID: str})

    df = df.rename(columns={COL_OWNER: "Owner", COL_STATE: "Status"})
    if "Owner" not in df.columns:
        df["Owner"] = "Unassigned"
    if "Status" not in df.columns:
        df["Status"] = "Pending"

    df["Owner"] = _blank_to_unassigned(df["Owner"])
    df["Status"] = df["Status"].astype(str).str.strip().replace("", "Pending")

    for col in (COL_CLASS, COL_FILE, COL_PROCEDURE, COL_PRIORITY, COL_FINDING, COL_URL):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    if COL_LINE in df.columns:
        df[COL_LINE] = pd.to_numeric(df[COL_LINE], errors="coerce").fillna(0).astype(int)

    return df


def load_history(history_path: Path) -> pd.DataFrame | None:
    """Read Tracker_History.xlsx if present, else return None (graceful)."""
    if not history_path.exists():
        return None
    try:
        return pd.read_excel(history_path)
    except Exception:
        return None


def _load_dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _env_list(name: str, task_dir: Path) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        raw = _load_dotenv_values(task_dir / ".env").get(name, "")
    if not raw.strip():
        return []
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return list(dict.fromkeys(values))


# ---------------------------------------------------------------------------
# Fix-guidance enrichment (reuses issue_explanations.py — no duplicated logic)
# ---------------------------------------------------------------------------

def _lookup_explanation(issue_class: str) -> dict:
    """Look up root cause / suggested fix / standards mapping for a class.

    Prefers the richer FIX_GUIDE entry and falls back to ISSUE_EXPLANATIONS.
    Standards are grouped into MISRA / CWE / CERT-C buckets by keyword.
    """
    guide = FIX_GUIDE.get(issue_class)
    simple = ISSUE_EXPLANATIONS.get(issue_class)

    root_cause = ""
    suggested_fix = ""
    standards: list[str] = []

    if guide:
        causes = guide.get("causes") or []
        root_cause = causes[0] if causes else guide.get("description", "")
        suggested_fix = guide.get("good_code") or guide.get("description", "")
        standards = guide.get("standards", [])
    elif simple:
        root_cause = simple.get("why", "")
        suggested_fix = simple.get("fix", "")

    misra = [s for s in standards if "MISRA" in s.upper()]
    cwe = [s for s in standards if "CWE" in s.upper()]
    cert = [s for s in standards if "CERT" in s.upper()]

    return {
        "root_cause": root_cause,
        "suggested_fix": suggested_fix,
        "misra": ", ".join(misra),
        "cwe": ", ".join(cwe),
        "cert_c": ", ".join(cert),
    }


# ---------------------------------------------------------------------------
# Metric builders
# ---------------------------------------------------------------------------

def _completion_pct(done: int, total: int) -> float:
    return round((done / total) * 100, 1) if total else 0.0


def _build_summary(df: pd.DataFrame, history_df: pd.DataFrame | None) -> dict:
    total = len(df)
    pending = int((df["Status"].str.lower() == "pending").sum())
    done = int((df["Status"].str.lower() == "done").sum())
    hb1 = int((df[COL_PRIORITY] == "HB_PRIO_1").sum()) if COL_PRIORITY in df.columns else 0
    hb2 = int((df[COL_PRIORITY] == "HB_PRIO_2").sum()) if COL_PRIORITY in df.columns else 0

    # New/Resolved issue counts are only tracked in Tracker_History.xlsx
    # (Master_Tracker.xlsx itself has no notion of "new since last run").
    new_issues = 0
    resolved_issues = 0
    if history_df is not None and len(history_df):
        last_row = history_df.iloc[-1]
        new_issues = int(last_row.get("New", 0) or 0)
        resolved_issues = int(last_row.get("Resolved", 0) or 0)

    return {
        "total_issues": total,
        "pending": pending,
        "done": done,
        "hb_prio_1": hb1,
        "hb_prio_2": hb2,
        "new_issues": new_issues,
        "resolved_issues": resolved_issues,
        "completion_pct": _completion_pct(done, total),
    }


def _build_priority_distribution(df: pd.DataFrame) -> list[dict]:
    if COL_PRIORITY not in df.columns:
        return []
    counts = df[COL_PRIORITY].value_counts()
    return [{"label": k, "value": int(v)} for k, v in counts.items()]


def _build_class_distribution(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Return (top-20 for charting, full list for the Issue Classes page)."""
    if COL_CLASS not in df.columns:
        return [], []
    counts = df[COL_CLASS].value_counts()
    full = [{"label": k, "value": int(v)} for k, v in counts.items()]
    return full[:20], full


def _build_top_files(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    if COL_FILE not in df.columns:
        return []
    counts = df[COL_FILE].value_counts().head(limit)
    return [{"label": k, "value": int(v)} for k, v in counts.items()]


def _owner_row(owner: str, group: pd.DataFrame | None) -> dict:
    """Build one Owner Dashboard row from the (possibly empty) group of
    tracker rows assigned to `owner`. Shared by every configured/derived
    owner so the metrics are computed identically for all of them."""
    if group is None or not len(group):
        return {
            "owner": owner,
            "assigned": 0,
            "pending": 0,
            "done": 0,
            "hb_prio_1": 0,
            "hb_prio_2": 0,
            "completion_pct": 0.0,
        }
    assigned = len(group)
    done = int((group["Status"].str.lower() == "done").sum())
    pending = int((group["Status"].str.lower() == "pending").sum())
    hb1 = int((group[COL_PRIORITY] == "HB_PRIO_1").sum()) if COL_PRIORITY in group.columns else 0
    hb2 = int((group[COL_PRIORITY] == "HB_PRIO_2").sum()) if COL_PRIORITY in group.columns else 0
    return {
        "owner": owner,
        "assigned": assigned,
        "pending": pending,
        "done": done,
        "hb_prio_1": hb1,
        "hb_prio_2": hb2,
        "completion_pct": _completion_pct(done, assigned),
    }


def _build_owners(df: pd.DataFrame, configured_owners: list[str] | None = None) -> list[dict]:
    """Per-owner metrics for the Owner Dashboard table. Every owner value
    actually present in Master_Tracker.xlsx's Owner column is included
    (never hardcoded), plus any configured-but-currently-unused owners so
    they remain visible with a 0 count."""
    rows = []
    grouped = {owner: group for owner, group in df.groupby("Owner")}
    seen = set()

    for owner in configured_owners or []:
        rows.append(_owner_row(owner, grouped.get(owner)))
        seen.add(owner)

    for owner, group in grouped.items():
        if owner in seen:
            continue
        rows.append(_owner_row(owner, group))

    rows.sort(key=lambda r: r["assigned"], reverse=True)
    return rows


def _build_owner_workload(owners: list[dict]) -> list[dict]:
    """Owner Workload chart series, derived directly from _build_owners()'s
    output (rather than recomputed from the raw dataframe) so the chart and
    the Owner Dashboard table are guaranteed to show identical numbers."""
    return [{"label": o["owner"], "value": o["assigned"]} for o in owners]


def _raw_owner_populated_count(tracker_path: Path) -> int:
    """Independent, pre-normalization read of Master_Tracker.xlsx's raw
    owner column, used only for anomaly detection in
    _build_owner_validation() — never used to compute dashboard metrics."""
    try:
        raw = pd.read_excel(tracker_path, sheet_name="Details", usecols=[COL_OWNER])
    except Exception:
        try:
            raw = pd.read_excel(tracker_path, usecols=[COL_OWNER])
        except Exception:
            return 0
    if COL_OWNER not in raw.columns:
        return 0
    values = raw[COL_OWNER].astype(str).str.strip()
    populated = ~values.str.lower().isin(["", "nan", "unassigned", "none"])
    return int(populated.sum())


def _build_owner_validation(df: pd.DataFrame, owners: list[dict], tracker_path: Path) -> dict:
    """Reconciliation totals + safety-net warnings for the Owner Dashboard.

    Confirms assigned + unassigned == total findings, and flags the specific
    anomaly of Master_Tracker.xlsx containing populated Owner values while
    the dashboard computed zero assigned findings (a pipeline bug signal,
    not a valid 'nobody is assigned yet' state).
    """
    total = len(df)
    unassigned = int((df["Owner"] == "Unassigned").sum())
    assigned_total = sum(o["assigned"] for o in owners if o["owner"] != "Unassigned")
    owners_total = sum(o["assigned"] for o in owners)

    warnings: list[str] = []

    if owners_total != total:
        warnings.append(
            f"Owner Dashboard totals do not reconcile: owner rows sum to {owners_total} but "
            f"Master_Tracker.xlsx has {total} finding(s)."
        )
    if assigned_total + unassigned != total:
        warnings.append(
            f"Assigned ({assigned_total}) + Unassigned ({unassigned}) does not equal Total Findings ({total})."
        )

    raw_populated = _raw_owner_populated_count(tracker_path)
    if raw_populated > 0 and assigned_total == 0:
        warnings.append(
            f"Master_Tracker.xlsx has {raw_populated} finding(s) with a populated Owner value, "
            "but the dashboard computed 0 assigned findings — check the Owner column mapping."
        )

    return {
        "total_findings": total,
        "assigned_total": assigned_total,
        "unassigned_total": unassigned,
        "reconciled": (owners_total == total) and (assigned_total + unassigned == total),
        "warnings": warnings,
    }


def _build_hotspots(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    """Top files by finding count, with priority breakdown and fix order.

    Reuses hotspot_analysis() for the base file/count/percent ranking instead
    of recomputing it, then augments each row with HB_PRIO_1/2 counts.
    """
    if COL_FILE not in df.columns:
        return []

    base = hotspot_analysis(df, top_n=limit)
    rows = []
    for record in base["rows"]:
        file_name = record["file"]
        subset = df[df[COL_FILE] == file_name]
        hb1 = int((subset[COL_PRIORITY] == "HB_PRIO_1").sum()) if COL_PRIORITY in df.columns else 0
        hb2 = int((subset[COL_PRIORITY] == "HB_PRIO_2").sum()) if COL_PRIORITY in df.columns else 0
        rows.append(
            {
                "file": file_name,
                "count": int(record["count"]),
                "percent": float(record["percent"]),
                "hb_prio_1": hb1,
                "hb_prio_2": hb2,
            }
        )

    # Recommended fix order: most HB_PRIO_1 first, then HB_PRIO_2, then volume.
    rows.sort(key=lambda r: (-r["hb_prio_1"], -r["hb_prio_2"], -r["count"]))
    for idx, row in enumerate(rows, start=1):
        row["fix_order"] = idx

    return rows


def _build_findings(df: pd.DataFrame) -> list[dict]:
    """Build the full findings dataset used by the table, filters, search and
    the finding-details modal. Enrichment is looked up once per row."""
    findings = []
    for record in df.to_dict("records"):
        issue_class = str(record.get(COL_CLASS, ""))
        enrichment = _lookup_explanation(issue_class)
        findings.append(
            {
                "id": str(record.get(COL_ID, "")),
                "class": issue_class,
                "priority": str(record.get(COL_PRIORITY, "")),
                "owner": str(record.get("Owner", "Unassigned")),
                "file": str(record.get(COL_FILE, "")),
                "procedure": str(record.get(COL_PROCEDURE, "")),
                "status": str(record.get("Status", "Pending")),
                "line_number": int(record.get(COL_LINE, 0) or 0),
                "finding": str(record.get(COL_FINDING, "")),
                "url": str(record.get(COL_URL, "")),
                **enrichment,
            }
        )
    return findings


def _build_trend(history_df: pd.DataFrame | None) -> dict | None:
    """Line-chart series from Tracker_History.xlsx, or None if unavailable.

    Note: history only records Total/HB1/HB2/New/Resolved per snapshot (see
    daily_workflow.update_tracker_history); Pending/Done are not historically
    tracked, so those two series are omitted gracefully instead of guessed.
    """
    if history_df is None or history_df.empty:
        return None

    def _col(name: str) -> list[int]:
        if name not in history_df.columns:
            return [0] * len(history_df)
        return [int(v) for v in pd.to_numeric(history_df[name], errors="coerce").fillna(0)]

    return {
        "labels": [str(v) for v in history_df.get("Date", pd.Series(dtype=str)).tolist()],
        "total": _col("Total"),
        "hb_prio_1": _col("HB1"),
        "hb_prio_2": _col("HB2"),
        "new_issues": _col("New"),
        "resolved_issues": _col("Resolved"),
    }


# ---------------------------------------------------------------------------
# ASPICE-style report sections: project metadata, quality gates, compliance
# (RAG) overview, release readiness verdict and auto-generated recommendations.
# All of these are read-only derivations of the tracker data already loaded
# above — none of this re-implements or touches tracker generation/sync logic.
# ---------------------------------------------------------------------------

def _detect_git_branch(task_dir: Path) -> str | None:
    """Best-effort current git branch name; returns None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=task_dir, capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch or None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _build_project_meta(task_dir: Path, tracker_path: Path) -> dict:
    """Executive-summary identity fields. Project-generic: falls back to the
    task directory name / git branch / "n/a" when no explicit env var is set,
    so this works for any CodeSonar project without project-specific code."""
    project_name = os.environ.get("CODESONAR_PROJECT_NAME") or task_dir.name
    branch = os.environ.get("CODESONAR_BRANCH") or _detect_git_branch(task_dir) or "n/a"
    build = os.environ.get("CODESONAR_BUILD") or "n/a"
    try:
        analysis_date = datetime.fromtimestamp(tracker_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        analysis_date = "n/a"
    return {
        "project_name": project_name,
        "branch": branch,
        "build": build,
        "analysis_date": analysis_date,
    }


def _build_quality_gates(df: pd.DataFrame, summary: dict, history_df: pd.DataFrame | None) -> list[dict]:
    """PASS/FAIL checklist used for the Quality Gates section and as the
    basis for the Release Readiness verdict. Thresholds come from
    QUALITY_GATE_CONFIG so each project can tune them via .env."""
    total = summary["total_issues"]
    hb1_total = summary["hb_prio_1"]

    hb1_pending = 0
    if COL_PRIORITY in df.columns:
        hb1_pending = int(((df[COL_PRIORITY] == "HB_PRIO_1") & (df["Status"].str.lower() == "pending")).sum())

    unassigned = int((df["Owner"] == "Unassigned").sum())
    unassigned_pct = round((unassigned / total) * 100, 1) if total else 0.0

    # Tracker Synchronization: compare current tracker total against the most
    # recent Tracker_History.xlsx snapshot (if any) to detect a stale/out of
    # sync tracker. Gracefully treated as PASS when no history exists yet.
    sync_ok = True
    sync_detail = "No Tracker_History.xlsx snapshot to compare against yet — treated as in sync."
    if history_df is not None and len(history_df):
        last_total = history_df.iloc[-1].get("Total")
        if last_total is not None and not pd.isna(last_total):
            sync_ok = int(last_total) == total
            sync_detail = (
                f"Master_Tracker.xlsx total ({total}) matches the latest history snapshot ({int(last_total)})."
                if sync_ok else
                f"Mismatch: Master_Tracker.xlsx has {total} finding(s) but the last history snapshot recorded {int(last_total)}. Re-run Update Tracker."
            )

    return [
        {
            "name": "Critical Findings",
            "status": "PASS" if hb1_pending == 0 else "FAIL",
            "detail": "No outstanding HB_PRIO_1 findings pending." if hb1_pending == 0
                       else f"{hb1_pending} HB_PRIO_1 finding(s) still pending.",
        },
        {
            "name": "HB_PRIO_1 Threshold",
            "status": "PASS" if hb1_total <= QUALITY_GATE_CONFIG["hb_prio_1_max"] else "FAIL",
            "detail": f"{hb1_total} HB_PRIO_1 finding(s) (threshold: {QUALITY_GATE_CONFIG['hb_prio_1_max']}).",
        },
        {
            "name": "Owner Assignment",
            "status": "PASS" if unassigned_pct <= QUALITY_GATE_CONFIG["unassigned_max_pct"] else "FAIL",
            "detail": f"{unassigned_pct}% unassigned (threshold: {QUALITY_GATE_CONFIG['unassigned_max_pct']}%).",
        },
        {
            "name": "Tracker Synchronization",
            "status": "PASS" if sync_ok else "FAIL",
            "detail": sync_detail,
        },
        {
            "name": "Review Completion",
            "status": "PASS" if summary["completion_pct"] >= QUALITY_GATE_CONFIG["review_completion_min_pct"] else "FAIL",
            "detail": f"{summary['completion_pct']}% complete (threshold: {QUALITY_GATE_CONFIG['review_completion_min_pct']}%).",
        },
        {
            "name": "Static Analysis Status",
            "status": "PASS",
            "detail": f"Master_Tracker.xlsx loaded successfully ({total} finding(s)).",
        },
    ]


def _build_compliance(findings: list[dict], summary: dict, history_df: pd.DataFrame | None) -> list[dict]:
    """Red/Amber/Green compliance overview. "na" (grey) is used when a
    signal has no applicable data yet (e.g. no MISRA-mapped findings, or no
    history snapshots), rather than guessing a color."""
    total = summary["total_issues"]
    hb1_total = summary["hb_prio_1"]
    unassigned = sum(1 for f in findings if f["owner"] == "Unassigned")
    unassigned_pct = round((unassigned / total) * 100, 1) if total else 0.0

    misra_findings = [f for f in findings if f.get("misra")]
    if misra_findings:
        misra_done = sum(1 for f in misra_findings if f["status"].lower() == "done")
        misra_pct = round((misra_done / len(misra_findings)) * 100, 1)
        misra_level = "green" if misra_pct >= 90 else "amber" if misra_pct >= 60 else "red"
        misra_detail = f"{misra_pct}% of {len(misra_findings)} MISRA-mapped finding(s) resolved."
    else:
        misra_level, misra_detail = "na", "No findings with a MISRA mapping detected."

    hb1_max = QUALITY_GATE_CONFIG["hb_prio_1_max"]
    sa_level = "green" if hb1_total == 0 else "amber" if hb1_total <= max(hb1_max, 1) else "red"
    sa_detail = f"{hb1_total} HB_PRIO_1 finding(s) outstanding."

    completion = summary["completion_pct"]
    min_pct = QUALITY_GATE_CONFIG["review_completion_min_pct"]
    cr_level = "green" if completion >= min_pct else "amber" if completion >= min_pct * 0.6 else "red"
    cr_detail = f"{completion}% of findings reviewed/closed."

    max_unassigned = QUALITY_GATE_CONFIG["unassigned_max_pct"]
    oa_level = "green" if unassigned_pct == 0 else "amber" if unassigned_pct <= max_unassigned else "red"
    oa_detail = f"{unassigned_pct}% of findings unassigned."

    if history_df is None or history_df.empty:
        trend_level, trend_detail = "na", "No Tracker_History.xlsx snapshots available yet."
    else:
        last = history_df.iloc[-1]
        new_v = int(pd.to_numeric(pd.Series([last.get("New", 0)]), errors="coerce").fillna(0).iloc[0])
        resolved_v = int(pd.to_numeric(pd.Series([last.get("Resolved", 0)]), errors="coerce").fillna(0).iloc[0])
        delta = new_v - resolved_v
        trend_level = "green" if delta <= 0 else "amber" if delta <= 5 else "red"
        trend_detail = f"Last snapshot: {new_v} new vs {resolved_v} resolved."

    return [
        {"name": "MISRA Compliance", "level": misra_level, "detail": misra_detail},
        {"name": "Static Analysis", "level": sa_level, "detail": sa_detail},
        {"name": "Code Review", "level": cr_level, "detail": cr_detail},
        {"name": "Owner Assignment", "level": oa_level, "detail": oa_detail},
        {"name": "Trend", "level": trend_level, "detail": trend_detail},
    ]


def _build_release_readiness(gates: list[dict]) -> dict:
    """Overall release verdict: NOT READY if a blocking gate fails,
    CONDITIONAL if only non-blocking gates fail, else READY."""
    by_name = {g["name"]: g["status"] for g in gates}
    blocking = ["Critical Findings", "HB_PRIO_1 Threshold"]
    blocking_failed = [n for n in blocking if by_name.get(n) == "FAIL"]
    other_failed = [g["name"] for g in gates if g["status"] == "FAIL" and g["name"] not in blocking]

    if blocking_failed:
        verdict, level = "NOT READY", "red"
    elif other_failed:
        verdict, level = "CONDITIONAL", "amber"
    else:
        verdict, level = "READY", "green"

    return {
        "verdict": verdict,
        "level": level,
        "blocking_gate_failures": blocking_failed,
        "other_gate_failures": other_failed,
    }


def _build_project_health(release_readiness: dict, compliance: list[dict]) -> dict:
    """Composite health/risk badge for the Executive Summary."""
    has_red = any(c["level"] == "red" for c in compliance)
    if release_readiness["verdict"] == "NOT READY":
        health, risk = "Critical", "High"
    elif release_readiness["verdict"] == "CONDITIONAL" or has_red:
        health, risk = "At Risk", "Medium"
    else:
        health, risk = "Healthy", "Low"
    return {"health": health, "risk_level": risk}


def _build_recommendations(gates: list[dict], compliance: list[dict], hotspots: list[dict]) -> list[str]:
    """Top actionable recommendations, derived automatically from gate and
    compliance failures (most critical first) plus the top hotspot file."""
    by_gate = {g["name"]: g for g in gates}
    by_comp = {c["name"]: c for c in compliance}
    recs: list[str] = []

    if by_gate["Critical Findings"]["status"] == "FAIL":
        recs.append(f"Resolve all outstanding HB_PRIO_1 critical findings before release — {by_gate['Critical Findings']['detail']}")
    if by_gate["HB_PRIO_1 Threshold"]["status"] == "FAIL":
        recs.append(f"Reduce the HB_PRIO_1 backlog — {by_gate['HB_PRIO_1 Threshold']['detail']}")
    if by_gate["Owner Assignment"]["status"] == "FAIL":
        recs.append(f"Assign owners to outstanding findings — {by_gate['Owner Assignment']['detail']}")
    if by_gate["Tracker Synchronization"]["status"] == "FAIL":
        recs.append(f"Re-run Update Tracker to resynchronize — {by_gate['Tracker Synchronization']['detail']}")
    if by_gate["Review Completion"]["status"] == "FAIL":
        recs.append(f"Increase the review/closure rate — {by_gate['Review Completion']['detail']}")
    if by_comp["MISRA Compliance"]["level"] == "red":
        recs.append(f"Prioritize outstanding MISRA rule violations — {by_comp['MISRA Compliance']['detail']}")
    if by_comp["Trend"]["level"] in ("amber", "red"):
        recs.append(f"Investigate the rising finding trend — {by_comp['Trend']['detail']}")
    if hotspots and hotspots[0].get("hb_prio_1", 0) > 0:
        top = hotspots[0]
        recs.append(f"Prioritize fixing {top['file']} — highest concentration of HB_PRIO_1 findings ({top['hb_prio_1']}).")

    if not recs:
        recs.append("No blocking issues detected — project currently meets all configured quality gates.")
    return recs


# ---------------------------------------------------------------------------
# Top-level data assembly
# ---------------------------------------------------------------------------

def build_dashboard_data(tracker_path: Path, history_path: Path) -> dict:
    df = load_tracker(tracker_path)
    history_df = load_history(history_path)
    task_dir = tracker_path.parent.parent
    configured_owners = _env_list("CODESONAR_OWNERS", task_dir)
    configured_reviewers = _env_list("CODESONAR_REVIEWERS", task_dir)

    class_chart, class_full = _build_class_distribution(df)
    summary = _build_summary(df, history_df)
    findings = _build_findings(df)
    hotspots = _build_hotspots(df, limit=10)

    gates = _build_quality_gates(df, summary, history_df)
    compliance = _build_compliance(findings, summary, history_df)
    release_readiness = _build_release_readiness(gates)
    project_health = _build_project_health(release_readiness, compliance)
    recommendations = _build_recommendations(gates, compliance, hotspots)

    owners = _build_owners(df, configured_owners)
    owner_workload = _build_owner_workload(owners)
    owner_validation = _build_owner_validation(df, owners, tracker_path)

    meta = _build_project_meta(task_dir, tracker_path)
    meta.update(project_health)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "tracker_path": str(tracker_path),
            "history_path": str(history_path) if history_df is not None else None,
        },
        "meta": meta,
        "summary": summary,
        "quality_gates": gates,
        "compliance": compliance,
        "release_readiness": release_readiness,
        "recommendations": recommendations,
        "charts": {
            "priority_distribution": _build_priority_distribution(df),
            "class_distribution": class_chart,
            "top_files": _build_top_files(df, limit=10),
            "owner_workload": owner_workload,
        },
        "classes": class_full,
        "owners": owners,
        "owner_validation": owner_validation,
        "configuration": {
            "owners": configured_owners,
            "reviewers": configured_reviewers,
        },
        "hotspots": hotspots,
        "findings": findings,
        "trend": _build_trend(history_df),
    }


def _json_default(obj):
    """json.dumps() fallback for numpy/pandas scalar types and stray NaNs."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return str(obj)


# ---------------------------------------------------------------------------
# Static assets: CSS
# ---------------------------------------------------------------------------

_CSS = """
/* CodeSonar Assistant — Interactive Dashboard styles (GitHub-inspired, responsive) */

:root {
  --bg: #ffffff;
  --bg-secondary: #f6f8fa;
  --border: #d0d7de;
  --text: #24292f;
  --text-muted: #57606a;
  --primary: #0969da;
  --danger: #cf222e;
  --warning: #9a6700;
  --success: #1a7f37;
  --shadow: 0 1px 3px rgba(27,31,36,0.08);
}

html[data-theme="dark"] {
  --bg: #0d1117;
  --bg-secondary: #161b22;
  --border: #30363d;
  --text: #c9d1d9;
  --text-muted: #8b949e;
  --primary: #58a6ff;
  --danger: #f85149;
  --warning: #d29922;
  --success: #3fb950;
  --shadow: 0 1px 3px rgba(0,0,0,0.4);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
}

.layout { display: flex; min-height: 100vh; }

/* Sidebar */
.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  padding: 16px 0;
}
.sidebar h1 { font-size: 15px; padding: 0 16px; margin: 0 0 16px; }
.nav-item {
  display: block;
  padding: 8px 16px;
  color: var(--text);
  text-decoration: none;
  cursor: pointer;
  font-size: 14px;
  border-left: 3px solid transparent;
}
.nav-item:hover { background: var(--border); }
.nav-item.active { border-left-color: var(--primary); font-weight: 600; color: var(--primary); }

/* Main content */
.main { flex: 1; padding: 20px 24px; overflow-x: hidden; }
.topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.topbar .actions button { margin-left: 8px; }

button, select, input[type="text"] {
  font-family: inherit;
  font-size: 13px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  background: var(--bg);
  color: var(--text);
}
button { cursor: pointer; }
button:hover { background: var(--bg-secondary); }
button.primary { background: var(--primary); color: #fff; border-color: var(--primary); }

.page { display: none; }
.page.active { display: block; }

/* Summary cards */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  box-shadow: var(--shadow);
}
.card .label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; }
.card .value { font-size: 26px; font-weight: 700; margin-top: 4px; }
.card.hb1 .value { color: var(--danger); }
.card.hb2 .value { color: var(--warning); }
.card.done .value { color: var(--success); }

/* Charts */
.charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 20px; }
.chart-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}
.chart-box h3 { margin: 0 0 8px; font-size: 14px; }
.chart-box canvas { max-height: 280px; }

/* Filters */
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.filters select, .filters input { min-width: 140px; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { background: var(--bg-secondary); position: sticky; top: 0; }
tbody tr { cursor: pointer; }
tbody tr:hover { background: var(--bg-secondary); }
.table-wrap { max-height: 520px; overflow: auto; border: 1px solid var(--border); border-radius: 8px; }

.badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.badge.HB_PRIO_1 { background: rgba(207,34,46,0.15); color: var(--danger); }
.badge.HB_PRIO_2 { background: rgba(154,103,0,0.15); color: var(--warning); }
.badge.Done { background: rgba(26,127,55,0.15); color: var(--success); }
.badge.Pending { background: rgba(154,103,0,0.15); color: var(--warning); }

.pagination { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 13px; }

/* Owner Dashboard drill-down */
.hint-text { font-size: 12px; color: var(--text-muted); margin: 8px 0; }
.owner-validation-banner .validation-warning {
  background: rgba(207,34,46,0.10);
  border: 1px solid var(--danger);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  font-size: 13px;
}
.owner-drilldown { display: none; margin-top: 20px; border-top: 1px solid var(--border); padding-top: 16px; }
.owner-drilldown.open { display: block; }
.owner-drilldown-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.owner-drilldown-header h3 { margin: 0; font-size: 15px; }
.owner-drilldown .exec-summary { margin-bottom: 12px; }

/* Modal */
.modal-overlay {
  display: none;
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  align-items: center; justify-content: center; z-index: 100;
}
.modal-overlay.open { display: flex; }
.modal {
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
  width: min(640px, 92vw); max-height: 86vh; overflow: auto; padding: 20px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.modal h2 { margin-top: 0; font-size: 16px; }
.modal dl { display: grid; grid-template-columns: 140px 1fr; gap: 6px 12px; font-size: 13px; }
.modal dt { color: var(--text-muted); }
.modal dd { margin: 0; white-space: pre-wrap; }
.modal .close-btn { float: right; }

.empty-state { color: var(--text-muted); font-style: italic; padding: 24px; text-align: center; }

/* ---- ASPICE / functional-safety quality report styling ------------------ */

.report-section { margin-bottom: 28px; }
.report-section h2 {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  border-bottom: 2px solid var(--border);
  padding-bottom: 8px;
  margin: 0 0 14px;
}

/* Executive summary banner */
.exec-summary {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 14px;
  box-shadow: var(--shadow);
}
.exec-summary .meta-item .label { font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em; }
.exec-summary .meta-item .value { font-size: 16px; font-weight: 600; margin-top: 2px; }

.pill { display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.pill.green { background: rgba(26,127,55,0.15); color: var(--success); }
.pill.amber { background: rgba(154,103,0,0.15); color: var(--warning); }
.pill.red   { background: rgba(207,34,46,0.15); color: var(--danger); }
.pill.na    { background: rgba(87,96,106,0.15); color: var(--text-muted); }

/* Quality Gates */
.gates-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.gate-card {
  border: 1px solid var(--border);
  border-left: 4px solid var(--border);
  border-radius: 8px;
  background: var(--bg-secondary);
  padding: 12px 14px;
}
.gate-card.pass { border-left-color: var(--success); }
.gate-card.fail { border-left-color: var(--danger); }
.gate-card .gate-name { font-size: 13px; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
.gate-card .gate-detail { font-size: 12px; color: var(--text-muted); margin-top: 6px; }

/* Compliance RAG overview */
.rag-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.rag-card { border: 1px solid var(--border); border-radius: 8px; background: var(--bg-secondary); padding: 12px 14px; }
.rag-card .rag-title { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.rag-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.rag-dot.green { background: var(--success); }
.rag-dot.amber { background: var(--warning); }
.rag-dot.red   { background: var(--danger); }
.rag-dot.na    { background: var(--text-muted); }
.rag-card .rag-detail { font-size: 12px; color: var(--text-muted); margin-top: 6px; }

/* Release readiness banner */
.readiness-banner {
  border-radius: 8px;
  padding: 18px 20px;
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}
.readiness-banner.green { background: rgba(26,127,55,0.10); border-color: var(--success); }
.readiness-banner.amber { background: rgba(154,103,0,0.10); border-color: var(--warning); }
.readiness-banner.red   { background: rgba(207,34,46,0.10); border-color: var(--danger); }
.readiness-banner .verdict { font-size: 20px; font-weight: 800; }
.readiness-banner .verdict-detail { font-size: 13px; color: var(--text-muted); }

/* Recommendations */
.recommendations-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.recommendations-list li {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  display: flex;
  gap: 10px;
}
.recommendations-list li .rec-index {
  flex-shrink: 0;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}

@media print {
  .sidebar, .filters, .actions, .pagination { display: none !important; }
  .main { padding: 0; }
}
"""


# ---------------------------------------------------------------------------
# Static assets: JavaScript
# ---------------------------------------------------------------------------

_JS = """
// CodeSonar Assistant — Interactive Dashboard client logic.
// Reads window.DASHBOARD_DATA (embedded inline in index.html — no fetch(),
// so the dashboard also works when index.html is opened directly from disk).

(function () {
  var DATA = window.DASHBOARD_DATA || {};
  var charts = {};
  var state = {
    filters: { owner: "", priority: "", class: "", status: "" },
    search: "",
    page: 0,
    pageSize: 25,
    ownerDrilldown: { owner: null, filters: { priority: "", class: "", status: "" } },
  };

  function byId(id) { return document.getElementById(id); }

  // Escape untrusted text before inserting into innerHTML. Finding text,
  // suggested fixes, file/procedure names etc. come from source code and can
  // legitimately contain "<", ">", quotes, etc. (e.g. "if (x < y)") — without
  // this, such content is parsed as HTML/tags, corrupting the layout (this is
  // also an XSS hardening measure: never trust tracker content in innerHTML).
  function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  // Sanitize a value used as a CSS class token (badges, gate/RAG status).
  function cssToken(value) {
    return String(value || "").replace(/[^a-zA-Z0-9_-]/g, "_");
  }

  // ---- Theme -----------------------------------------------------------
  function initTheme() {
    var saved = localStorage.getItem("csa-theme") || "light";
    document.documentElement.setAttribute("data-theme", saved);
    byId("theme-toggle").addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme");
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("csa-theme", next);
    });
  }

  // ---- Navigation --------------------------------------------------------
  function initNav() {
    var links = document.querySelectorAll(".nav-item");
    links.forEach(function (link) {
      link.addEventListener("click", function () {
        links.forEach(function (l) { l.classList.remove("active"); });
        link.classList.add("active");
        document.querySelectorAll(".page").forEach(function (p) { p.classList.remove("active"); });
        byId("page-" + link.dataset.page).classList.add("active");
      });
    });
  }

  // ---- Executive summary + KPI cards --------------------------------------
  function renderMeta() {
    var m = DATA.meta || {};
    byId("exec-summary").innerHTML = [
      ["Project Name", m.project_name || "n/a"],
      ["Branch", m.branch || "n/a"],
      ["Build", m.build || "n/a"],
      ["Analysis Date", m.analysis_date || "n/a"],
      ["Overall Project Health", '<span class="pill ' + cssToken(healthPillLevel(m.health)) + '">' + escapeHtml(m.health || "n/a") + "</span>"],
      ["Risk Level", '<span class="pill ' + cssToken(riskPillLevel(m.risk_level)) + '">' + escapeHtml(m.risk_level || "n/a") + "</span>"],
    ].map(function (pair) {
      return '<div class="meta-item"><div class="label">' + escapeHtml(pair[0]) + '</div><div class="value">' + pair[1] + "</div></div>";
    }).join("");
  }

  function healthPillLevel(health) {
    if (health === "Healthy") return "green";
    if (health === "At Risk") return "amber";
    if (health === "Critical") return "red";
    return "na";
  }
  function riskPillLevel(risk) {
    if (risk === "Low") return "green";
    if (risk === "Medium") return "amber";
    if (risk === "High") return "red";
    return "na";
  }

  function renderSummary() {
    var s = DATA.summary || {};
    byId("summary-cards").innerHTML = [
      ["Total Findings", s.total_issues, ""],
      ["HB_PRIO_1", s.hb_prio_1, "hb1"],
      ["HB_PRIO_2", s.hb_prio_2, "hb2"],
      ["Pending", s.pending, ""],
      ["Resolved", s.resolved_issues, "done"],
      ["Completion %", s.completion_pct + "%", ""],
    ].map(function (c) {
      return '<div class="card ' + c[2] + '"><div class="label">' + escapeHtml(c[0]) + '</div><div class="value">' + escapeHtml(c[1]) + "</div></div>";
    }).join("");
  }

  // ---- Quality Gates -------------------------------------------------------
  function renderQualityGates() {
    var gates = DATA.quality_gates || [];
    byId("gates-grid").innerHTML = gates.map(function (g) {
      var cls = g.status === "PASS" ? "pass" : "fail";
      return '<div class="gate-card ' + cls + '">' +
        '<div class="gate-name">' + escapeHtml(g.name) + '<span class="pill ' + (g.status === "PASS" ? "green" : "red") + '">' + escapeHtml(g.status) + "</span></div>" +
        '<div class="gate-detail">' + escapeHtml(g.detail) + "</div></div>";
    }).join("") || '<div class="empty-state">No quality gate data available.</div>';
  }

  // ---- Compliance Overview (RAG) -------------------------------------------
  function renderCompliance() {
    var items = DATA.compliance || [];
    byId("compliance-grid").innerHTML = items.map(function (c) {
      return '<div class="rag-card">' +
        '<div class="rag-title"><span class="rag-dot ' + cssToken(c.level) + '"></span>' + escapeHtml(c.name) + "</div>" +
        '<div class="rag-detail">' + escapeHtml(c.detail) + "</div></div>";
    }).join("") || '<div class="empty-state">No compliance data available.</div>';
  }

  // ---- Release Readiness ----------------------------------------------------
  function renderReleaseReadiness() {
    var r = DATA.release_readiness || {};
    var el = byId("readiness-banner");
    el.className = "readiness-banner " + cssToken(r.level || "na");
    var failing = (r.blocking_gate_failures || []).concat(r.other_gate_failures || []);
    var detail = failing.length
      ? "Failing gate(s): " + failing.map(escapeHtml).join(", ")
      : "All configured quality gates are passing.";
    el.innerHTML = '<div><div class="verdict">' + escapeHtml(r.verdict || "n/a") + '</div><div class="verdict-detail">' + detail + "</div></div>";
  }

  // ---- Recommendations -------------------------------------------------------
  function renderRecommendations() {
    var recs = DATA.recommendations || [];
    byId("recommendations-list").innerHTML = recs.map(function (text, i) {
      return "<li><span class=\\"rec-index\\">" + (i + 1) + "</span><span>" + escapeHtml(text) + "</span></li>";
    }).join("") || '<li class="empty-state">No recommendations.</li>';
  }

  // ---- Charts -------------------------------------------------------------
  function makeChart(canvasId, config) {
    var ctx = byId(canvasId);
    if (!ctx) return;
    charts[canvasId] = new Chart(ctx.getContext("2d"), config);
  }

  var PALETTE = ["#0969da", "#cf222e", "#9a6700", "#1a7f37", "#8250df", "#bf3989", "#57606a", "#1b7c83"];

  function renderCharts() {
    // Finding Summary: Priority Distribution + Issue Class Distribution.
    var pd = DATA.charts.priority_distribution || [];
    makeChart("chart-priority", {
      type: "pie",
      data: {
        labels: pd.map(function (r) { return r.label; }),
        datasets: [{ data: pd.map(function (r) { return r.value; }), backgroundColor: PALETTE }],
      },
    });

    var cd = DATA.charts.class_distribution || [];
    makeChart("chart-class", {
      type: "bar",
      data: {
        labels: cd.map(function (r) { return r.label; }),
        datasets: [{ label: "Issues", data: cd.map(function (r) { return r.value; }), backgroundColor: "#0969da" }],
      },
      options: { indexAxis: "y", plugins: { legend: { display: false } } },
    });

    // Top files chart lives on the Files page; owner workload on the Owners page.
    var tf = DATA.charts.top_files || [];
    makeChart("chart-files", {
      type: "bar",
      data: {
        labels: tf.map(function (r) { return r.label; }),
        datasets: [{ label: "Findings", data: tf.map(function (r) { return r.value; }), backgroundColor: "#8250df" }],
      },
      options: { plugins: { legend: { display: false } } },
    });

    var ow = DATA.charts.owner_workload || [];
    makeChart("chart-owners", {
      type: "bar",
      data: {
        labels: ow.map(function (r) { return r.label; }),
        datasets: [{ label: "Assigned", data: ow.map(function (r) { return r.value; }), backgroundColor: "#1a7f37" }],
      },
      options: { plugins: { legend: { display: false } } },
    });
  }

  function renderTrend() {
    var section = byId("trend-section");
    var trend = DATA.trend;
    if (!trend || !trend.labels || !trend.labels.length) {
      section.innerHTML = '<div class="empty-state">No Tracker_History.xlsx snapshots available yet — trend charts will appear once history accumulates.</div>';
      return;
    }
    section.innerHTML = '<div class="chart-box"><h3>Issues Over Time</h3><canvas id="chart-trend"></canvas></div>';
    makeChart("chart-trend", {
      type: "line",
      data: {
        labels: trend.labels,
        datasets: [
          { label: "Total", data: trend.total, borderColor: "#0969da", fill: false },
          { label: "HB_PRIO_1", data: trend.hb_prio_1, borderColor: "#cf222e", fill: false },
          { label: "HB_PRIO_2", data: trend.hb_prio_2, borderColor: "#9a6700", fill: false },
          { label: "New", data: trend.new_issues, borderColor: "#1a7f37", fill: false },
          { label: "Resolved", data: trend.resolved_issues, borderColor: "#8250df", fill: false },
        ],
      },
    });
  }

  // ---- Filters / search ----------------------------------------------------
  function uniqueValues(key) {
    var set = {};
    (DATA.findings || []).forEach(function (f) { if (f[key]) set[f[key]] = true; });
    return Object.keys(set).sort();
  }

  function configuredOwners() {
    return (DATA.configuration && DATA.configuration.owners) || [];
  }

  function populateFilterOptions() {
    [["filter-owner", "owner"], ["filter-priority", "priority"], ["filter-class", "class"], ["filter-status", "status"]]
      .forEach(function (pair) {
        var select = byId(pair[0]);
        var values = pair[1] === "owner" ? Array.from(new Set(configuredOwners().concat(uniqueValues(pair[1])))).sort() : uniqueValues(pair[1]);
        values.forEach(function (v) {
          var opt = document.createElement("option");
          opt.value = v; opt.textContent = v;
          select.appendChild(opt);
        });
        select.addEventListener("change", function () {
          state.filters[pair[1]] = select.value;
          state.page = 0;
          renderTable();
        });
      });

    byId("search-box").addEventListener("input", function (e) {
      state.search = e.target.value.toLowerCase();
      state.page = 0;
      renderTable();
    });
  }

  function getFilteredFindings() {
    var f = state.filters, q = state.search;
    return (DATA.findings || []).filter(function (row) {
      if (f.owner && row.owner !== f.owner) return false;
      if (f.priority && row.priority !== f.priority) return false;
      if (f.class && row.class !== f.class) return false;
      if (f.status && row.status !== f.status) return false;
      if (q) {
        var hay = (row.id + " " + row.file + " " + row.procedure + " " + row.class + " " + row.owner).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  // ---- Findings table --------------------------------------------------------
  function renderTable() {
    var rows = getFilteredFindings();
    var start = state.page * state.pageSize;
    var pageRows = rows.slice(start, start + state.pageSize);

    var tbody = byId("findings-tbody");
    if (!pageRows.length) {
      tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state">No findings match the current filters.</div></td></tr>';
    } else {
      tbody.innerHTML = pageRows.map(function (r) {
        return "<tr data-id='" + escapeHtml(r.id) + "'>" +
          "<td>" + escapeHtml(r.id) + "</td>" +
          "<td>" + escapeHtml(r.class) + "</td>" +
          '<td><span class="badge ' + cssToken(r.priority) + '">' + escapeHtml(r.priority) + "</span></td>" +
          "<td>" + escapeHtml(r.owner) + "</td>" +
          "<td>" + escapeHtml(r.file) + "</td>" +
          "<td>" + escapeHtml(r.procedure) + "</td>" +
          '<td><span class="badge ' + cssToken(r.status) + '">' + escapeHtml(r.status) + "</span></td>" +
          "<td>" + escapeHtml(r.line_number) + "</td>" +
        "</tr>";
      }).join("");
    }

    Array.prototype.forEach.call(tbody.querySelectorAll("tr[data-id]"), function (tr) {
      tr.addEventListener("click", function () { openModal(tr.dataset.id); });
    });

    var totalPages = Math.max(1, Math.ceil(rows.length / state.pageSize));
    byId("pagination-info").textContent = "Page " + (state.page + 1) + " of " + totalPages + " (" + rows.length + " findings)";
    byId("prev-page").disabled = state.page <= 0;
    byId("next-page").disabled = state.page >= totalPages - 1;
  }

  function initPagination() {
    byId("prev-page").addEventListener("click", function () { if (state.page > 0) { state.page--; renderTable(); } });
    byId("next-page").addEventListener("click", function () {
      var total = Math.ceil(getFilteredFindings().length / state.pageSize);
      if (state.page < total - 1) { state.page++; renderTable(); }
    });
  }

  // ---- Modal --------------------------------------------------------------
  // Renders the Finding Details modal. All values are escaped before being
  // inserted into innerHTML: finding text / suggested fixes / root causes are
  // free text sourced from analyzed code and may legitimately contain "<",
  // ">", quotes etc. (e.g. "if (x < y)"), which previously broke the <dl>
  // layout when inserted raw and is also an XSS risk if left unescaped.
  function openModal(id) {
    var row = (DATA.findings || []).find(function (f) { return f.id === id; });
    if (!row) return;
    byId("modal-body").innerHTML = [
      ["Issue ID", row.id], ["Finding Class", row.class], ["Finding Text", row.finding],
      ["Priority", row.priority], ["File", row.file], ["Procedure", row.procedure],
      ["Line Number", row.line_number], ["Owner", row.owner], ["Status", row.status],
      ["Root Cause", row.root_cause || "n/a"], ["Suggested Fix", row.suggested_fix || "n/a"],
      ["MISRA Mapping", row.misra || "n/a"], ["CWE Mapping", row.cwe || "n/a"], ["CERT-C Mapping", row.cert_c || "n/a"],
    ].map(function (pair) { return "<dt>" + escapeHtml(pair[0]) + "</dt><dd>" + escapeHtml(pair[1]) + "</dd>"; }).join("");
    byId("modal-overlay").classList.add("open");
  }

  function initModal() {
    byId("modal-overlay").addEventListener("click", function (e) {
      if (e.target.id === "modal-overlay") byId("modal-overlay").classList.remove("open");
    });
    byId("modal-close").addEventListener("click", function () { byId("modal-overlay").classList.remove("open"); });
  }

  // ---- Export / print ------------------------------------------------------
  function toCSV(rows) {
    var cols = ["id", "class", "priority", "owner", "file", "procedure", "status", "line_number"];
    var lines = [cols.join(",")];
    rows.forEach(function (r) {
      lines.push(cols.map(function (c) { return '"' + String(r[c]).replace(/"/g, '""') + '"'; }).join(","));
    });
    return lines.join("\\n");
  }

  function initExportPrint() {
    byId("export-csv").addEventListener("click", function () {
      var blob = new Blob([toCSV(getFilteredFindings())], { type: "text/csv" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "codesonar_findings.csv";
      a.click();
    });
    byId("print-dashboard").addEventListener("click", function () { window.print(); });
  }

  // ---- Owners / Files / Classes / Hotspots pages --------------------------
  function renderOwnerValidationBanner() {
    var el = byId("owner-validation-banner");
    if (!el) return;
    var warnings = (DATA.owner_validation && DATA.owner_validation.warnings) || [];
    if (!warnings.length) {
      el.innerHTML = "";
      el.style.display = "none";
      return;
    }
    el.style.display = "block";
    el.innerHTML = warnings.map(function (w) {
      return '<div class="validation-warning">\u26A0 ' + escapeHtml(w) + "</div>";
    }).join("");
  }

  function renderOwnersPage() {
    var owners = DATA.owners || [];
    renderOwnerValidationBanner();
    byId("owners-tbody").innerHTML = owners.map(function (o) {
      return "<tr data-owner='" + escapeHtml(o.owner) + "'>" +
        "<td>" + escapeHtml(o.owner) + "</td>" +
        "<td>" + escapeHtml(o.assigned) + "</td>" +
        "<td>" + escapeHtml(o.hb_prio_1) + "</td>" +
        "<td>" + escapeHtml(o.hb_prio_2) + "</td>" +
        "<td>" + escapeHtml(o.pending) + "</td>" +
        "<td>" + escapeHtml(o.done) + "</td>" +
        "<td>" + escapeHtml(o.completion_pct) + "%</td>" +
      "</tr>";
    }).join("") || '<tr><td colspan="7"><div class="empty-state">No owner data available.</div></td></tr>';

    Array.prototype.forEach.call(byId("owners-tbody").querySelectorAll("tr[data-owner]"), function (tr) {
      tr.addEventListener("click", function () { openOwnerDrilldown(tr.dataset.owner); });
    });
  }

  function getOwnerFindings(owner) {
    return (DATA.findings || []).filter(function (f) { return f.owner === owner; });
  }

  function getFilteredOwnerFindings() {
    var owner = state.ownerDrilldown.owner;
    var f = state.ownerDrilldown.filters;
    return getOwnerFindings(owner).filter(function (row) {
      if (f.priority && row.priority !== f.priority) return false;
      if (f.class && row.class !== f.class) return false;
      if (f.status && row.status !== f.status) return false;
      return true;
    });
  }

  function renderOwnerDrilldownSummary() {
    var owner = state.ownerDrilldown.owner;
    var row = (DATA.owners || []).find(function (o) { return o.owner === owner; }) || {
      owner: owner, assigned: 0, pending: 0, done: 0, hb_prio_1: 0, hb_prio_2: 0, completion_pct: 0,
    };
    byId("owner-drilldown-summary").innerHTML = [
      ["Owner", row.owner],
      ["Total Assigned", row.assigned],
      ["Pending", row.pending],
      ["Done", row.done],
      ["HB_PRIO_1", row.hb_prio_1],
      ["HB_PRIO_2", row.hb_prio_2],
      ["Completion %", row.completion_pct + "%"],
    ].map(function (pair) {
      return '<div class="meta-item"><div class="label">' + escapeHtml(pair[0]) + '</div><div class="value">' + escapeHtml(pair[1]) + "</div></div>";
    }).join("");
  }

  function populateOwnerDrilldownFilters() {
    var rows = getOwnerFindings(state.ownerDrilldown.owner);
    function uniqueValues(key) {
      var vals = {};
      rows.forEach(function (r) { if (r[key]) vals[r[key]] = true; });
      return Object.keys(vals).sort();
    }
    [["owner-drilldown-filter-priority", "priority", "Priority"], ["owner-drilldown-filter-class", "class", "Class"], ["owner-drilldown-filter-status", "status", "Status"]]
      .forEach(function (pair) {
        var select = byId(pair[0]);
        select.innerHTML = '<option value="">All ' + pair[2] + "</option>";
        uniqueValues(pair[1]).forEach(function (v) {
          var opt = document.createElement("option");
          opt.value = v; opt.textContent = v;
          select.appendChild(opt);
        });
        select.value = state.ownerDrilldown.filters[pair[1]] || "";
      });
  }

  function renderOwnerDrilldownTable() {
    var rows = getFilteredOwnerFindings();
    var tbody = byId("owner-drilldown-tbody");
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="9"><div class="empty-state">No findings match the current filters.</div></td></tr>';
    } else {
      tbody.innerHTML = rows.map(function (r) {
        return "<tr data-id='" + escapeHtml(r.id) + "'>" +
          "<td>" + escapeHtml(r.id) + "</td>" +
          '<td><span class="badge ' + cssToken(r.priority) + '">' + escapeHtml(r.priority) + "</span></td>" +
          "<td>" + escapeHtml(r.class) + "</td>" +
          "<td>" + escapeHtml(r.owner) + "</td>" +
          "<td>" + escapeHtml(r.file) + "</td>" +
          "<td>" + escapeHtml(r.procedure) + "</td>" +
          '<td><span class="badge ' + cssToken(r.status) + '">' + escapeHtml(r.status) + "</span></td>" +
          "<td>" + escapeHtml(r.line_number) + "</td>" +
          "<td>" + escapeHtml(r.finding) + "</td>" +
        "</tr>";
      }).join("");
    }
    Array.prototype.forEach.call(tbody.querySelectorAll("tr[data-id]"), function (tr) {
      tr.addEventListener("click", function () { openModal(tr.dataset.id); });
    });
  }

  function openOwnerDrilldown(owner) {
    state.ownerDrilldown.owner = owner;
    state.ownerDrilldown.filters = { priority: "", class: "", status: "" };
    byId("owner-drilldown-title").textContent = "Findings for " + owner;
    populateOwnerDrilldownFilters();
    renderOwnerDrilldownSummary();
    renderOwnerDrilldownTable();
    byId("owner-drilldown").classList.add("open");
    byId("owner-drilldown").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function closeOwnerDrilldown() {
    byId("owner-drilldown").classList.remove("open");
    state.ownerDrilldown.owner = null;
  }

  function initOwnerDrilldown() {
    byId("owner-drilldown-close").addEventListener("click", closeOwnerDrilldown);
    [["owner-drilldown-filter-priority", "priority"], ["owner-drilldown-filter-class", "class"], ["owner-drilldown-filter-status", "status"]]
      .forEach(function (pair) {
        byId(pair[0]).addEventListener("change", function (e) {
          state.ownerDrilldown.filters[pair[1]] = e.target.value;
          renderOwnerDrilldownTable();
        });
      });
  }

  function renderFilesPage() {
    var files = DATA.charts.top_files || [];
    byId("files-tbody").innerHTML = files.map(function (f) {
      return "<tr><td>" + escapeHtml(f.label) + "</td><td>" + escapeHtml(f.value) + "</td></tr>";
    }).join("") || '<tr><td colspan="2"><div class="empty-state">No file data available.</div></td></tr>';
  }

  function renderClassesPage() {
    var classes = DATA.classes || [];
    byId("classes-tbody").innerHTML = classes.map(function (c) {
      return "<tr><td>" + escapeHtml(c.label) + "</td><td>" + escapeHtml(c.value) + "</td></tr>";
    }).join("") || '<tr><td colspan="2"><div class="empty-state">No class data available.</div></td></tr>';
  }

  function renderHotspotsPage() {
    var hotspots = DATA.hotspots || [];
    byId("hotspots-tbody").innerHTML = hotspots.map(function (h) {
      return "<tr><td>" + escapeHtml(h.fix_order) + "</td><td>" + escapeHtml(h.file) + "</td><td>" + escapeHtml(h.count) + "</td><td>" + escapeHtml(h.percent) + "%</td>" +
        "<td>" + escapeHtml(h.hb_prio_1) + "</td><td>" + escapeHtml(h.hb_prio_2) + "</td></tr>";
    }).join("") || '<tr><td colspan="6"><div class="empty-state">No hotspot data available.</div></td></tr>';
  }

  // ---- Init -----------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", function () {
    byId("generated-at").textContent = "Generated: " + (DATA.generated_at || "n/a");
    if (byId("settings-source")) {
      byId("settings-source").textContent = (DATA.source && DATA.source.tracker_path) || "n/a";
    }
    initTheme();
    initNav();
    initModal();
    initPagination();
    initExportPrint();
    initOwnerDrilldown();
    renderMeta();
    renderSummary();
    renderQualityGates();
    renderCompliance();
    renderReleaseReadiness();
    renderRecommendations();
    renderCharts();
    renderTrend();
    populateFilterOptions();
    renderTable();
    renderOwnersPage();
    renderFilesPage();
    renderClassesPage();
    renderHotspotsPage();
  });
})();
"""


# ---------------------------------------------------------------------------
# Static asset: index.html (data is injected at generation time)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>CodeSonar Assistant — Dashboard</title>
<style>
__DASHBOARD_CSS__
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
<div class="layout">
  <nav class="sidebar">
    <h1>CodeSonar Assistant</h1>
    <a class="nav-item active" data-page="dashboard">Dashboard</a>
    <a class="nav-item" data-page="findings">Findings</a>
    <a class="nav-item" data-page="owners">Owners</a>
    <a class="nav-item" data-page="files">Files</a>
    <a class="nav-item" data-page="classes">Issue Classes</a>
    <a class="nav-item" data-page="hotspots">Hotspots</a>
    <a class="nav-item" data-page="trends">Trends</a>
    <a class="nav-item" data-page="settings">Settings</a>
  </nav>
  <main class="main">
    <div class="topbar">
      <div id="generated-at"></div>
      <div class="actions">
        <button id="theme-toggle">Toggle Theme</button>
        <button id="export-csv">Export CSV</button>
        <button id="print-dashboard">Print</button>
      </div>
    </div>

    <section id="page-dashboard" class="page active">

      <!-- 1. Executive Summary -->
      <div class="report-section">
        <h2>Executive Summary</h2>
        <div id="exec-summary" class="exec-summary"></div>
      </div>

      <!-- 2. Project Health KPIs -->
      <div class="report-section">
        <h2>Project Health KPIs</h2>
        <div id="summary-cards" class="cards"></div>
      </div>

      <!-- 3. Quality Gates -->
      <div class="report-section">
        <h2>Quality Gates</h2>
        <div id="gates-grid" class="gates-grid"></div>
      </div>

      <!-- 4. Compliance Overview -->
      <div class="report-section">
        <h2>Compliance Overview</h2>
        <div id="compliance-grid" class="rag-grid"></div>
      </div>

      <!-- 5. Finding Summary -->
      <div class="report-section">
        <h2>Finding Summary</h2>
        <div class="charts-grid">
          <div class="chart-box"><h3>Priority Distribution</h3><canvas id="chart-priority"></canvas></div>
          <div class="chart-box"><h3>Issue Class Distribution</h3><canvas id="chart-class"></canvas></div>
        </div>
      </div>

      <!-- 9. Release Readiness -->
      <div class="report-section">
        <h2>Release Readiness</h2>
        <div id="readiness-banner" class="readiness-banner"></div>
      </div>

      <!-- 10. Recommendations -->
      <div class="report-section">
        <h2>Recommendations</h2>
        <ul id="recommendations-list" class="recommendations-list"></ul>
      </div>
    </section>

    <section id="page-findings" class="page">
      <h2>Recent Findings</h2>
      <div class="filters">
        <input type="text" id="search-box" placeholder="Search Issue ID, File, Procedure, Class, Owner..." />
        <select id="filter-owner"><option value="">All Owners</option></select>
        <select id="filter-priority"><option value="">All Priorities</option></select>
        <select id="filter-class"><option value="">All Classes</option></select>
        <select id="filter-status"><option value="">All Statuses</option></select>
      </div>

      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Issue ID</th><th>Class</th><th>Priority</th><th>Owner</th>
            <th>File</th><th>Procedure</th><th>Status</th><th>Line Number</th>
          </tr></thead>
          <tbody id="findings-tbody"></tbody>
        </table>
      </div>
      <div class="pagination">
        <button id="prev-page">Prev</button>
        <span id="pagination-info"></span>
        <button id="next-page">Next</button>
      </div>
    </section>

    <!-- 7. Owner Dashboard -->
    <section id="page-owners" class="page">
      <h2>Owner Dashboard</h2>
      <div id="owner-validation-banner" class="owner-validation-banner" style="display:none;"></div>
      <div class="chart-box"><h3>Owner Workload</h3><canvas id="chart-owners"></canvas></div>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Owner</th><th>Total Assigned</th><th>HB_PRIO_1</th><th>HB_PRIO_2</th><th>Pending</th><th>Done</th><th>Completion %</th>
          </tr></thead>
          <tbody id="owners-tbody"></tbody>
        </table>
      </div>
      <p class="hint-text">Click an owner row to view their assigned findings.</p>

      <div id="owner-drilldown" class="owner-drilldown">
        <div class="owner-drilldown-header">
          <h3 id="owner-drilldown-title">Findings for Owner</h3>
          <button id="owner-drilldown-close" class="close-btn">Close</button>
        </div>
        <div id="owner-drilldown-summary" class="exec-summary"></div>
        <div class="filters">
          <select id="owner-drilldown-filter-priority"><option value="">All Priority</option></select>
          <select id="owner-drilldown-filter-class"><option value="">All Class</option></select>
          <select id="owner-drilldown-filter-status"><option value="">All Status</option></select>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>Issue ID</th><th>Priority</th><th>Issue Class</th><th>Owner</th>
              <th>File</th><th>Procedure</th><th>Status</th><th>Line Number</th><th>Finding</th>
            </tr></thead>
            <tbody id="owner-drilldown-tbody"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section id="page-files" class="page">
      <h2>Top Files by Findings</h2>
      <div class="chart-box"><h3>Top 10 Files</h3><canvas id="chart-files"></canvas></div>
      <table>
        <thead><tr><th>File</th><th>Findings</th></tr></thead>
        <tbody id="files-tbody"></tbody>
      </table>
    </section>

    <section id="page-classes" class="page">
      <h2>Issue Class Distribution</h2>
      <table>
        <thead><tr><th>Class</th><th>Issues</th></tr></thead>
        <tbody id="classes-tbody"></tbody>
      </table>
    </section>

    <section id="page-hotspots" class="page">
      <h2>Hotspot Analysis</h2>
      <table>
        <thead><tr><th>Fix Order</th><th>File</th><th>Findings</th><th>% of Total</th><th>HB_PRIO_1</th><th>HB_PRIO_2</th></tr></thead>
        <tbody id="hotspots-tbody"></tbody>
      </table>
    </section>

    <section id="page-trends" class="page">
      <h2>Trends</h2>
      <div id="trend-section"></div>
    </section>

    <section id="page-settings" class="page">
      <h2>Settings</h2>
      <p>Use the "Toggle Theme" button in the top bar to switch between light and dark mode. Your preference is saved locally in this browser.</p>
      <p>Data source: <code id="settings-source"></code></p>
    </section>
  </main>
</div>

<div id="modal-overlay" class="modal-overlay">
  <div class="modal">
    <button id="modal-close" class="close-btn">Close</button>
    <h2>Finding Details</h2>
    <dl id="modal-body"></dl>
  </div>
</div>

<script>window.DASHBOARD_DATA = __DASHBOARD_DATA_JSON__;</script>
<script>
__DASHBOARD_JS__
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def _write_static_assets(dashboard_dir: Path) -> None:
    """Create supporting folders and write CSS/JS assets (idempotent)."""
    (dashboard_dir / "css").mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "js").mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "assets").mkdir(parents=True, exist_ok=True)

    (dashboard_dir / "css" / "style.css").write_text(_CSS, encoding="utf-8")
    (dashboard_dir / "js" / "dashboard.js").write_text(_JS, encoding="utf-8")


def _render_index_html(dashboard_dir: Path, data: dict) -> Path:
    data_json = json.dumps(data, default=_json_default)
    html = _HTML_TEMPLATE
    html = html.replace("__DASHBOARD_DATA_JSON__", data_json)
    html = html.replace("__DASHBOARD_CSS__", _CSS)
    html = html.replace("__DASHBOARD_JS__", _JS)
    index_path = dashboard_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def generate_dashboard(task_dir: Path | None = None) -> dict:
    """Generate the interactive dashboard from output/Master_Tracker.xlsx.

    Handles a missing tracker file gracefully by returning a "skipped" status
    instead of raising, so callers (daily_workflow.py, codesonar_assistant.py)
    can treat dashboard regeneration as a best-effort, non-fatal step.
    """
    task_dir = Path(task_dir) if task_dir else TASK_DIR
    output_dir = task_dir / "output"
    tracker_path = output_dir / "Master_Tracker.xlsx"
    history_path = output_dir / "Tracker_History.xlsx"
    dashboard_dir = output_dir / "dashboard"

    if not tracker_path.exists():
        return {
            "status": "skipped",
            "message": f"Master_Tracker.xlsx not found at {tracker_path}; run Update Tracker first.",
        }

    dashboard_dir.mkdir(parents=True, exist_ok=True)

    data = build_dashboard_data(tracker_path, history_path)

    data_json_path = dashboard_dir / "dashboard_data.json"
    data_json_path.write_text(
        json.dumps(data, indent=2, default=_json_default), encoding="utf-8"
    )

    _write_static_assets(dashboard_dir)
    index_path = _render_index_html(dashboard_dir, data)

    return {
        "status": "ok",
        "message": f"Dashboard generated: {index_path}",
        "dashboard_data": str(data_json_path),
        "index_html": str(index_path),
    }


def main() -> int:
    result = generate_dashboard()
    print(result["message"])
    return 0 if result["status"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())