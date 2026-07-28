from pathlib import Path
import sys

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from intent import detect_intent  # noqa: E402
from dispatcher import dispatch  # noqa: E402


def _rows_for_display(df: pd.DataFrame, limit: int = 20):
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


def _normalize_response(response):
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
            "rows": _rows_for_display(response),
        }

    if isinstance(response, dict):
        return {
            "answer": response.get("answer", "No answer available."),
            "count": response.get("count", 0),
            "rows": response.get("rows", []),
        }

    return {
        "answer": str(response),
        "count": 0,
        "rows": [],
    }


def dispatch_query(df: pd.DataFrame, query: str):
    intent = detect_intent(query)
    raw_response = dispatch(df, intent, query)
    return intent, _normalize_response(raw_response)
