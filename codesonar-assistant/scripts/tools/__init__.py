"""
Logical tool modules for CodeSonar assistant handlers.
"""

from .analytics import (
    class_summary,
    highest_workload,
    owner_priority_summary,
    priority_summary,
    top_classes,
    top_files,
    top_issue_classes,
)
from .dashboard import (
    dashboard,
    project_health,
    project_summary,
    trend_analysis,
)
from .issue import (
    explain_issue,
    file_issues,
    file_summary,
    fix_guide_batch,
    fix_guide_class,
    fix_guide_issue,
    fix_recommendation,
    issue_details,
    issues_by_class,
    similar_issues,
)
from .owner import (
    owner_progress,
    owner_summary,
    owner_workload,
    recommend_next_issue,
    recommend_owner,
)
from .search import (
    extract_entities,
    process_query,
    search_issues,
)
