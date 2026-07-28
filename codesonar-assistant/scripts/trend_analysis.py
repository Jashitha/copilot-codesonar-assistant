import pandas as pd

# Delegate to the canonical implementation in tools/dashboard.py
from tools.dashboard import trend_analysis as _trend_analysis


def trend_analysis(df: pd.DataFrame) -> dict:
    return _trend_analysis(df)
