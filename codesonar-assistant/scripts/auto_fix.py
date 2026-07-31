"""
auto_fix.py

Auto Fix automatically repairs supported safe mechanical violations.

Applies safe, mechanical source fixes for a subset of common findings.

Scope (intentionally conservative):
  - strcpy(dst, src)  -> snprintf(dst, sizeof(dst), "%s", src)
  - sprintf(dst, ...) -> snprintf(dst, sizeof(dst), ...)
  - null-check-after-deref pattern where immediate if (ptr == NULL) return;
    is moved before the dereference line.

Non-goals:
  - No semantic-heavy refactors (ownership/lifetime, signedness redesign, etc.)
  - No claim to fix every finding automatically.
"""

from __future__ import annotations

from pathlib import Path
import re

from precommit_review import review as precommit_review


def _resolve_source_path(input_path: str) -> Path:
    """Resolve file paths similarly to precommit_review.run_precommit_review()."""
    file_path = Path(input_path)

    if file_path.exists():
        return file_path

    script_dir = Path(__file__).parent        # scripts/
    repo_root = script_dir.parent.parent      # ~/.copilot
    cs_root = script_dir.parent               # codesonar-assistant/

    for base in (Path.cwd(), script_dir, cs_root, repo_root):
        candidate = base / file_path
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"File not found: {input_path}")


def _replace_dangerous_calls(line: str) -> tuple[str, int]:
    """
    Apply per-line call replacements.

    Returns (new_line, fix_count_delta).
    """
    changed = 0

    # strcpy(dst, src) -> snprintf(dst, sizeof(dst), "%s", src)
    def _repl_strcpy(match: re.Match) -> str:
        nonlocal changed
        dst = match.group(1)
        src = match.group(2)
        changed += 1
        return f'snprintf({dst}, sizeof({dst}), "%s", {src})'

    new_line = re.sub(
        r"\bstrcpy\s*\(\s*([A-Za-z_]\w*)\s*,\s*([^\)]+?)\s*\)",
        _repl_strcpy,
        line,
    )

    # sprintf(dst, <rest>) -> snprintf(dst, sizeof(dst), <rest>)
    def _repl_sprintf(match: re.Match) -> str:
        nonlocal changed
        dst = match.group(1)
        rest = match.group(2)
        changed += 1
        return f"snprintf({dst}, sizeof({dst}), {rest})"

    new_line = re.sub(
        r"\bsprintf\s*\(\s*([A-Za-z_]\w*)\s*,\s*(.+?)\)",
        _repl_sprintf,
        new_line,
    )

    return new_line, changed


def _move_null_check_before_deref(lines: list[str]) -> tuple[list[str], int]:
    """
    Move immediate null-check blocks before dereference when pattern is obvious.

    Pattern handled:
        <deref-line with var->...>
        if (var == NULL) {
            return;
        }
    """
    i = 0
    moved = 0

    while i < len(lines) - 2:
        deref_line = lines[i]
        deref_match = re.search(r"\b([A-Za-z_]\w*)\s*->", deref_line)
        if not deref_match:
            i += 1
            continue

        var = deref_match.group(1)

        # Support both if (var == NULL) and if (!var)
        check_pattern = (
            rf"^\s*if\s*\(\s*({var}\s*==\s*NULL|!\s*{var})\s*\)\s*\{{"
        )
        if not re.search(check_pattern, lines[i + 1]):
            i += 1
            continue

        # Find matching closing brace for the if-block.
        j = i + 1
        depth = 0
        found = False
        while j < len(lines):
            depth += lines[j].count("{")
            depth -= lines[j].count("}")
            if depth == 0 and j > i + 1:
                found = True
                break
            j += 1

        if not found:
            i += 1
            continue

        if_block = lines[i + 1 : j + 1]
        # Reorder: if-block first, then deref-line.
        lines = lines[:i] + if_block + [deref_line] + lines[j + 1 :]
        moved += 1
        i += len(if_block) + 1

    return lines, moved


def _extract_file_from_query(query: str) -> str | None:
    match = re.search(r"([^\s]+\.[a-zA-Z]+(?:/[^\s]*)?|/[^\s]+)", query)
    if not match:
        return None
    return match.group(1)


def _count_severity(report: str, severity: str) -> int:
    return len(re.findall(rf"Severity\s*:\s*{re.escape(severity)}", report, flags=re.IGNORECASE))


def run_auto_fix(query: str) -> dict:
    """
    Extract a source file path from *query*, apply safe automatic fixes,
    and return a structured assistant response.
    """
    target = _extract_file_from_query(query)
    if not target:
        return {
            "answer": (
                "Please provide a source file path for auto-fix.\n"
                "Example: auto fix <source file>"
            ),
            "count": 0,
            "rows": [],
        }

    try:
        src_path = _resolve_source_path(target)
    except FileNotFoundError as exc:
        return {
            "answer": str(exc),
            "count": 0,
            "rows": [],
        }

    original = src_path.read_text(encoding="utf-8", errors="replace")
    before_report = precommit_review(src_path)

    changed_calls = 0
    updated_lines: list[str] = []
    for line in original.splitlines():
        new_line, delta = _replace_dangerous_calls(line)
        updated_lines.append(new_line)
        changed_calls += delta

    reordered_lines, moved_null_checks = _move_null_check_before_deref(updated_lines)
    updated = "\n".join(reordered_lines)
    if original.endswith("\n"):
        updated += "\n"

    if updated == original:
        return {
            "answer": (
                f"No safe automatic fix pattern matched in {src_path}.\n"
                "Try pre-commit review for manual fix guidance."
            ),
            "count": 0,
            "rows": [],
        }

    src_path.write_text(updated, encoding="utf-8")
    after_report = precommit_review(src_path)

    before_high = _count_severity(before_report, "HIGH")
    after_high = _count_severity(after_report, "HIGH")
    before_medium = _count_severity(before_report, "MEDIUM")
    after_medium = _count_severity(after_report, "MEDIUM")

    answer = (
        "Auto Fix automatically repairs supported safe mechanical violations.\n\n"
        "Auto-fix completed.\n\n"
        f"File: {src_path}\n"
        f"Applied fixes:\n"
        f"  - Dangerous call replacements: {changed_calls}\n"
        f"  - Null-check reorderings: {moved_null_checks}\n\n"
        "Pre-commit findings (before -> after):\n"
        f"  - HIGH: {before_high} -> {after_high}\n"
        f"  - MEDIUM: {before_medium} -> {after_medium}\n"
    )

    rows = [
        {"Metric": "file", "Value": str(src_path)},
        {"Metric": "dangerous_call_replacements", "Value": changed_calls},
        {"Metric": "null_check_reorderings", "Value": moved_null_checks},
        {"Metric": "high_before", "Value": before_high},
        {"Metric": "high_after", "Value": after_high},
        {"Metric": "medium_before", "Value": before_medium},
        {"Metric": "medium_after", "Value": after_medium},
    ]

    return {
        "answer": answer,
        "count": changed_calls + moved_null_checks,
        "rows": rows,
    }
