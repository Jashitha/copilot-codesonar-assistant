from datetime import datetime, timedelta
from pathlib import Path
import re
import shutil

import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TOOLS_DIR.parent
TASK_DIR = SCRIPTS_DIR.parent
OUTPUT_DIR = TASK_DIR / "output"


def _build_details_sheet(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = [
        "score",
        "id",
        "class",
        "significance",
        "file",
        "line number",
        "procedure",
        "priority",
        "state",
        "finding",
        "owner",
        "url",
    ]

    fallback_map = {
        "owner": "Owner",
        "state": "Status",
    }

    details = pd.DataFrame()

    for column in required_columns:
        if column in df.columns:
            details[column] = df[column]
        elif column in fallback_map and fallback_map[column] in df.columns:
            details[column] = df[fallback_map[column]]
        else:
            details[column] = ""

    return details


def _save_dashboard_excel(
    df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    top_files_df: pd.DataFrame,
    top_classes_df: pd.DataFrame,
    class_distribution_df: pd.DataFrame,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = OUTPUT_DIR / "Dashboard_Output.xlsx"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dated_path = OUTPUT_DIR / f"Dashboard_Output_{timestamp}.xlsx"

    details_df = _build_details_sheet(df)

    top_files_out = top_files_df.rename(columns={"file": "Top Files"})
    top_classes_out = top_classes_df.rename(columns={"class": "Top Class"})

    with pd.ExcelWriter(latest_path, engine="openpyxl") as writer:
        summary_row = 0

        metrics_df.to_excel(writer, sheet_name="Summary", index=False, startrow=summary_row)
        summary_row += len(metrics_df) + 2
        top_files_out.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
            startrow=summary_row,
        )
        summary_row += len(top_files_out) + 2

        top_classes_out.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
            startrow=summary_row,
        )
        summary_row += len(top_classes_out) + 2
        class_distribution_df.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
            startrow=summary_row,
        )

        details_df.to_excel(
            writer,
            sheet_name="Details",
            index=False,
        )

    shutil.copy2(latest_path, dated_path)

    return latest_path, dated_path


def dashboard(df):

    total = len(df)

    pending = len(
        df[df["Status"].astype(str).str.lower() == "pending"]
    )

    done = len(
        df[df["Status"].astype(str).str.lower() == "done"]
    )

    prio1 = len(
        df[df["priority"] == "HB_PRIO_1"]
    )

    prio2 = len(
        df[df["priority"] == "HB_PRIO_2"]
    )

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

    classes = (
        df.groupby("class")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
        .head(5)
    )

    class_distribution = (
        df.groupby("class")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
    )

    metrics_df = pd.DataFrame(
        [
            {"Metric": "Total Issues", "Value": total},
            {"Metric": "Pending", "Value": pending},
            {"Metric": "Done", "Value": done},
            {"Metric": "HB_PRIO_1", "Value": prio1},
            {"Metric": "HB_PRIO_2", "Value": prio2},
            {"Metric": "Owners", "Value": len(owners)},
        ]
    )

    latest_excel, dated_excel = _save_dashboard_excel(
        df=df,
        metrics_df=metrics_df,
        top_files_df=files,
        top_classes_df=classes,
        class_distribution_df=class_distribution,
    )

    rows = [
        *metrics_df.to_dict("records"),
        {},
        {"Top Owners": ""},
        *owners.to_dict("records"),
        {},
        {"Top Files": ""},
        *files.to_dict("records"),
        {},
        {"Top Classes": ""},
        *classes.to_dict("records"),
        {},
        {"Dashboard Excel": str(latest_excel)},
        {"Dashboard Excel Snapshot": str(dated_excel)},
    ]

    return {
        "answer": "CodeSonar Dashboard",
        "count": total,
        "rows": rows,
    }


def project_summary(df):
    total = len(df)

    pending = len(
        df[df["Status"].astype(str).str.lower() == "pending"]
    )

    done = len(
        df[df["Status"].astype(str).str.lower() == "done"]
    )

    hb1 = len(
        df[df["priority"] == "HB_PRIO_1"]
    )

    hb2 = len(
        df[df["priority"] == "HB_PRIO_2"]
    )

    top_file = (
        df["file"]
        .value_counts()
        .head(1)
    )

    top_class = (
        df["class"]
        .value_counts()
        .head(1)
    )

    owners = (
        df["Owner"]
        .value_counts()
    )

    summary = (
        f"Project currently has {total} issues. "
        f"{pending} are pending and {done} are completed. "
        f"There are {hb1} HB_PRIO_1 issues and {hb2} HB_PRIO_2 issues. "
        f"The most affected file is {top_file.index[0]} ({top_file.iloc[0]} issues). "
        f"The most common issue class is '{top_class.index[0]}' ({top_class.iloc[0]} issues). "
        f"Owner distribution: "
        + ", ".join(
            [
                f"{owner}: {count}"
                for owner, count in owners.items()
            ]
        )
        + "."
    )

    return {
        "answer": summary,
        "count": total,
        "rows": []
    }


def project_health(df):

    total = len(df)

    pending = len(
        df[df["Status"].astype(str).str.lower() == "pending"]
    )

    done = len(
        df[df["Status"].astype(str).str.lower() == "done"]
    )

    hb1 = len(
        df[df["priority"] == "HB_PRIO_1"]
    )

    hb2 = len(
        df[df["priority"] == "HB_PRIO_2"]
    )

    if hb1 > 20:
        risk = "HIGH"
    elif hb1 > 10:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "answer": f"Project Health: {risk}",
        "count": total,
        "rows": [
            {
                "Metric": "Total Issues",
                "Value": total
            },
            {
                "Metric": "Pending",
                "Value": pending
            },
            {
                "Metric": "Done",
                "Value": done
            },
            {
                "Metric": "HB_PRIO_1",
                "Value": hb1
            },
            {
                "Metric": "HB_PRIO_2",
                "Value": hb2
            },
            {
                "Metric": "Risk",
                "Value": risk
            },
            {
                "Metric": "Recommendation",
                "Value": "Resolve HB_PRIO_1 issues first."
            }
        ]
    }


def _extract_metrics(df: pd.DataFrame) -> dict:
    """Return a dict of key metrics for a tracker DataFrame."""
    return {
        "Total":   len(df),
        "Pending": int((df["Status"].astype(str).str.lower() == "pending").sum()),
        "Done":    int((df["Status"].astype(str).str.lower() == "done").sum()),
        "HB1":     int((df["priority"] == "HB_PRIO_1").sum()) if "priority" in df.columns else 0,
        "HB2":     int((df["priority"] == "HB_PRIO_2").sum()) if "priority" in df.columns else 0,
    }


def _change_indicator(today_val: int, yesterday_val: int, lower_is_better: bool = True) -> str:
    """Return an emoji + delta string for a metric change."""
    delta = today_val - yesterday_val
    if delta == 0:
        return "➖ 0"
    if lower_is_better:
        icon = "🟢" if delta < 0 else "🔴"
    else:
        icon = "🟢" if delta > 0 else "🔴"
    sign = "+" if delta > 0 else ""
    return f"{icon} {sign}{delta}"


def _find_dated_tracker(date: datetime) -> Path | None:
    """Locate Master_Tracker_YYYYMMDD.xlsx for the given date in OUTPUT_DIR."""
    name = f"Master_Tracker_{date.strftime('%Y%m%d')}.xlsx"
    path = OUTPUT_DIR / name
    return path if path.exists() else None


def trend_analysis(df: pd.DataFrame) -> dict:
    """Compare today's tracker against the most recent previous daily snapshot."""
    today = datetime.now()
    today_label = today.strftime("%b-%d")

    today_metrics = _extract_metrics(df)

    # Find the most recent previous snapshot (search back up to 30 days)
    prev_path: Path | None = None
    prev_label: str = ""
    for days_back in range(1, 31):
        candidate_date = today - timedelta(days=days_back)
        candidate_path = _find_dated_tracker(candidate_date)
        if candidate_path:
            prev_path = candidate_path
            prev_label = candidate_date.strftime("%b-%d")
            break

    if prev_path is None:
        # No previous snapshot — return current metrics only
        rows = [
            {"Metric": "Total Issues",  "Today": today_metrics["Total"],   "Note": "No previous snapshot found"},
            {"Metric": "Pending",       "Today": today_metrics["Pending"]},
            {"Metric": "Done",          "Today": today_metrics["Done"]},
            {"Metric": "HB_PRIO_1",     "Today": today_metrics["HB1"]},
            {"Metric": "HB_PRIO_2",     "Today": today_metrics["HB2"]},
        ]
        return {
            "answer": f"Trend Analysis — {today_label} (no previous snapshot to compare)",
            "count": today_metrics["Total"],
            "rows": rows,
        }

    prev_df = pd.read_excel(prev_path)
    prev_df = prev_df.rename(columns={"state": "Status", "Owner": "Owner"})
    if "Status" not in prev_df.columns and "state" in prev_df.columns:
        prev_df["Status"] = prev_df["state"]

    prev_metrics = _extract_metrics(prev_df)

    today_file  = f"Master_Tracker_{today.strftime('%Y%m%d')}.xlsx"
    prev_file   = prev_path.name

    metric_rows = [
        ("Total Issues", "Total",   True),
        ("Pending",      "Pending", True),
        ("Done",         "Done",    False),
        ("HB_PRIO_1",    "HB1",     True),
        ("HB_PRIO_2",    "HB2",     True),
    ]

    rows = []
    improving = 0
    regressing = 0
    for label, key, lower_is_better in metric_rows:
        t = today_metrics[key]
        p = prev_metrics[key]
        change = _change_indicator(t, p, lower_is_better)
        rows.append({"Metric": label, prev_label: p, today_label: t, "Change": change})
        delta = t - p
        if delta == 0:
            pass
        elif (lower_is_better and delta < 0) or (not lower_is_better and delta > 0):
            improving += 1
        else:
            regressing += 1

    if regressing == 0 and improving > 0:
        overall = "🟢 Improving"
    elif improving == 0 and regressing > 0:
        overall = "🔴 Regressing"
    elif improving > regressing:
        overall = "🟡 Mostly Improving"
    elif regressing > improving:
        overall = "🟡 Mostly Regressing"
    else:
        overall = "➖ Stable"

    rows.append({"Metric": "Overall Status", prev_label: "", today_label: "", "Change": overall})

    answer = (
        f"Trend Analysis\n\n"
        f"Comparing: {prev_file} ↔ {today_file}\n\n"
        f"Overall Project Trend\n"
        + "\t".join(["Metric", prev_label, today_label, "Change"]) + "\n"
        + "\n".join(
            f"{r['Metric']}\t{r.get(prev_label, '')}\t{r.get(today_label, '')}\t{r.get('Change', '')}"
            for r in rows
        )
    )

    return {
        "answer": answer,
        "count": today_metrics["Total"],
        "rows": rows,
    }
