# User Guide

Use natural-language queries with the assistant backend.

## Dashboard

Query: `Dashboard`

Returns overall counts, HB priorities, owners, top files, and top classes.

## Update Tracker

Query: `Update Tracker`

Runs the daily workflow:
- Downloads latest CodeSonar CSV
- Filters HB_PRIO_1 and HB_PRIO_2
- Syncs with master tracker
- Preserves owner/reviewer/status/ETA fields
- Assigns new issues
- Generates tracker and dashboard outputs

## Project Health

Query: `Project Health`

Provides risk-oriented view using current priority distribution.

## Trend Analysis

Query: `Trend Analysis`

Compares today vs previous tracker snapshot and reports deltas.

## Hotspot Analysis

Query: `Hotspot Analysis`

Highlights files/procedures/classes with highest concentration of findings.

## Recommend Next Issue

Query: `Recommend Next Issue`

Recommends high-priority pending issue based on priority and impact.

## Fix Guide

Class-level query examples:
- `How to fix Use After Free`
- `How to fix Inappropriate Assignment Type`

Issue-level query examples:
- `Fix Guide 1201340.7557926828`
- `Fix Guide for Issue 6253372`

Returns:
- Why the class is reported
- Risks and common patterns
- Safer fix pattern
- Verification checklist
- Relevant standards
- Tracker hotspots

## Batch Fix Guide

Query examples:
- `Batch Fix Guide`
- `Where should I focus for biggest impact?`

Returns top class/file hotspots and a prioritized execution order to maximize finding reduction.

## Review Engine

The Review Engine powers both Pre-Commit Review and Gerrit Patchset Review.

## Pre-Commit Review

Query examples:
- `review tests/sample_code/dangerous_api.c`
- `pre-commit review /absolute/path/to/file.c`
- `check my code bsmd.c`
- `commit readiness bsmd.c`

```mermaid
flowchart TD
    A[Pre-Commit Review] --> B[Language Detection (.c / .cpp)]
    B --> C[MISRA C / MISRA C++ Analysis]
    B --> D[CodeSonar Pattern Analysis]
    B --> E[Dangerous API Analysis]
    B --> F[Memory Safety Analysis]
    B --> G[Custom Project Rules]
    C --> H[Commit Readiness Report]
    D --> H
    E --> H
    F --> H
    G --> H
```

Returns:
- Findings grouped by checker
- Line, severity, message, and recommendation
- MISRA Rule when available
- Status: Auto Fix Supported or Manual Fix Required
- Reason for the status
- Summary counts per checker
- Commit readiness (`READY TO COMMIT` or `NOT READY`)

## Gerrit Patchset Review

Query examples:
- `Gerrit patchset review https://gerrit.example.com/c/project/+/123/4`
- `Gerrit gate patchset-created https://gerrit.example.com/c/project/+/123/4`

Returns a Gerrit review summary for the pasted link, downloads reviewable file contents from Gerrit, runs the Review Engine, and posts a `Verified -1`
vote when blocking findings remain.

## Auto Fix

Query examples:
- `Auto Fix tests/sample_code/dangerous_api.c`

Auto Fix automatically repairs supported safe mechanical violations. It applies safe mechanical fixes where possible, reruns the pre-commit review, and leaves unsupported findings for the Fix Guide workflow.

Supported categories include safe API replacements and simple null-check reorderings; unsupported categories remain manual.
