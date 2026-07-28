"""
Compatibility entry points for assistant handlers.
"""

from tools.issue import explain_issue, fix_recommendation
from tools.owner import owner_summary, recommend_next_issue
from tools.search import process_query

__all__ = [
    "process_query",
    "owner_summary",
    "recommend_next_issue",
    "explain_issue",
    "fix_recommendation",
]
