import json
from typing import Any, Dict, Optional


def build_chat_prompt(user_prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a compact, deterministic prompt for issue-tracker responses.
    """

    safe_context = context or {}

    return (
        "You are CodeSonar Assistant.\n"
        "Use only provided context data and do not invent metrics.\n"
        "Reply with a concise answer first, then 1-3 actionable bullets when helpful.\n\n"
        f"User query: {user_prompt}\n"
        f"Context JSON: {json.dumps(safe_context, ensure_ascii=True)}\n"
    )
