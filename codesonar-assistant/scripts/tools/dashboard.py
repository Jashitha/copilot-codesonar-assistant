"""Dashboard-related handlers used by dispatcher."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re

import pandas as pd

from project_health import project_health  # noqa: F401
from project_summary import project_summary  # noqa: F401


def _extract_metrics(df: pd.DataFrame) -> dict[str, int]:
    pending = len(df[df["Status"].astype(str).str.lower() == "pending"])
    done = len(df[df["Status"].astype(str).str.lower() == "done"])
    hb1 = len(df[df["priority"] == "HB_PRIO_1"])
    hb2 = len(df[df["priority"] == "HB_PRIO_2"])
    return {
        "Total Issues": len(df),
        "Pending": pending,
        "Done": done,
        "HB_PRIO_1": hb1,
        "HB_PRIO_2": hb2,
    }


def _build_dashboard_tables(df: pd.DataFrame):
    metrics = _extract_metrics(df)

    owners = (
        df.groupby("Owner")
        .size()
        .reset_index(name="Assigned")
        .sort_values("Assigned", ascending=False)
    )

    files = (
        df.groupby("file")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
        .head(5)
    )

    top_classes = (
        df.groupby("class")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
        .head(5)
    )

    all_classes = (
        df.groupby("class")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
    )

    summary_rows: list[dict] = [
        {"Metric": "Total Issues", "Value": metrics["Total Issues"]},
        {"Metric": "Pending", "Value": metrics["Pending"]},
        {"Metric": "Done", "Value": metrics["Done"]},
        {"Metric": "HB_PRIO_1", "Value": metrics["HB_PRIO_1"]},
        {"Metric": "HB_PRIO_2", "Value": metrics["HB_PRIO_2"]},
        {"Metric": "Owners", "Value": len(owners)},
        {},
        {"Top Files": "", "Issues": ""},
        *files.to_dict("records"),
        {},
        {"Top Class": "", "Issues": ""},
        *top_classes.rename(columns={"class": "Top Class"}).to_dict("records"),
    ]

    # Rows returned to chat output (includes owners + top classes)
    rows_for_chat = [
        {"Metric": "Total Issues", "Value": metrics["Total Issues"]},
        {"Metric": "Pending", "Value": metrics["Pending"]},
        {"Metric": "Done", "Value": metrics["Done"]},
        {"Metric": "HB_PRIO_1", "Value": metrics["HB_PRIO_1"]},
        {"Metric": "HB_PRIO_2", "Value": metrics["HB_PRIO_2"]},
        {"Metric": "Owners", "Value": len(owners)},
        {},
        {"Top Owners": ""},
        *owners.to_dict("records"),
        {},
        {"Top Files": ""},
        *files.to_dict("records"),
        {},
        {"Top Classes": ""},
        *top_classes.to_dict("records"),
    ]

    return metrics, summary_rows, rows_for_chat, all_classes


def dashboard(df: pd.DataFrame) -> dict:
    metrics, _summary_rows, rows_for_chat, _all_classes = _build_dashboard_tables(df)

    return {
        "answer": "CodeSonar Dashboard",
        "count": metrics["Total Issues"],
        "rows": rows_for_chat,
    }


def _find_previous_snapshot(output_dir: Path) -> Path | None:
    # Prefer dated tracker snapshots like Master_Tracker_YYYYMMDD.xlsx
    candidates = sorted(output_dir.glob("Master_Tracker_*.xlsx"), reverse=True)
    date_re = re.compile(r"Master_Tracker_(\d{8})\.xlsx$")

    today = datetime.now().strftime("%Y%m%d")
    for path in candidates:
        m = date_re.search(path.name)
        if not m:
            continue
        if m.group(1) == today:
            continue
        return path

    # Fallback: try yesterday explicitly
    yday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    p = output_dir / f"Master_Tracker_{yday}.xlsx"
    return p if p.exists() else None


def _change_indicator(delta: int) -> str:
    if delta < 0:
        return f"🟢 {delta}"
    if delta > 0:
        return f"🔴 +{delta}"
    return "➖ 0"


def trend_analysis(df: pd.DataFrame) -> dict:
    """Compare current tracker metrics vs previous dated snapshot when available."""
    current = _extract_metrics(df)
    output_dir = Path(__file__).resolve().parents[2] / "output"
    prev_path = _find_previous_snapshot(output_dir)

    if not prev_path:
        return {
            "answer": f"Trend Analysis — {datetime.now().strftime('%b-%d')} (no previous snapshot to compare)",
            "count": current["Total Issues"],
            "rows": [
                {"Metric": "Total Issues", "Today": current["Total Issues"], "Note": "No previous snapshot found"},
                {"Metric": "Pending", "Today": current["Pending"]},
                {"Metric": "Done", "Today": current["Done"]},
                {"Metric": "HB_PRIO_1", "Today": current["HB_PRIO_1"]},
                {"Metric": "HB_PRIO_2", "Today": current["HB_PRIO_2"]},
            ],
        }

    try:
        prev_df = pd.read_excel(prev_path, sheet_name="Details")
    except ValueError:
        # Legacy workbook without a Details sheet name.
        prev_df = pd.read_excel(prev_path)

    prev_df = prev_df.rename(columns={"owner": "Owner", "state": "Status"})
    previous = _extract_metrics(prev_df)

    rows = []
    for metric in ["Total Issues", "Pending", "Done", "HB_PRIO_1", "HB_PRIO_2"]:
        delta = current[metric] - previous[metric]
        rows.append(
            {
                "Metric": metric,
                "Today": current[metric],
                "Previous": previous[metric],
                "Change": _change_indicator(delta),
            }
        )

    total_delta = current["Total Issues"] - previous["Total Issues"]
    direction = "Improving" if total_delta < 0 else "Regressing" if total_delta > 0 else "Stable"

    return {
        "answer": (
            f"Trend Analysis — {datetime.now().strftime('%b-%d')} vs {prev_path.stem.split('_')[-1]}: {direction}"
        ),
        "count": current["Total Issues"],
        "rows": rows,
    }
