"""
fix_guide.py

Dedicated wrappers for Fix Guide queries:
- class-level fix guide
- issue-level fix guide
- batch fix guide
"""

from tools.issue import fix_guide_batch, fix_guide_class, fix_guide_issue

__all__ = [
    "fix_guide_class",
    "fix_guide_issue",
    "fix_guide_batch",
]
