# Changelog

## 0.5.0 - 2026-07-29

- Added `scripts/report_generator.py` with `generate_summary_sheet`, `generate_details_sheet`, and `save_tracker_report`
- Master_Tracker.xlsx now contains exactly two sheets: Summary (Overall Metrics, Top Files, Top Issue Classes, Complete Issue Class Distribution) and Details (full issue list with exact column order)
- Removed separate `Dashboard_Output.xlsx` generation; dashboard metrics are now read from Master_Tracker.xlsx
- Updated `daily_workflow.py`, `tools/dashboard.py`, and `codesonar_assistant.py` to read the Details sheet explicitly for backward-compatible sheet ordering
- Updated agent doc, READMEs, and Architecture.md to reflect the consolidated two-sheet tracker output
- Added Gerrit patchset review and Gerrit gate support with pasted Gerrit link parsing and Verified vote posting
- Added safe Auto Fix workflow with pre-commit review before and after mechanical remediation
- Updated docs and prompts to describe the assistant as generic/project-specific via `.env` CodeSonar URL and credentials

## 0.4.0 - 2026-07-28

- Added Pre-Commit Review workflow with query routing (`review`, `pre-commit review`, `check my code`, `commit readiness`)
- Added modular checker pipeline for pre-commit scans (Dangerous API, MISRA-C:2012, CodeSonar-mapped patterns, Memory placeholder)
- Added path resolution fallback for review queries across `scripts/`, `codesonar-assistant/`, and workspace root
- Fixed `fix guide <issue id>` intent routing and decimal issue ID support
- Updated docs and examples for Fix Guide and Pre-Commit Review

## 0.3.0 - 2026-07-27

- Added tracker history output (`output/Tracker_History.xlsx`)
- Added day-over-day trend comparison support
- Added three-level Fix Guide support (class, issue, batch)

## 0.2.0 - 2026-07-26

- Added dashboard export with summary/details sheets
- Added tracker sync with owner/status/reviewer preservation
- Added hotspot and owner analytics

## 0.1.0 - 2026-07-25

- Initial CodeSonar assistant foundation
- Query routing, parser, and baseline issue analytics
