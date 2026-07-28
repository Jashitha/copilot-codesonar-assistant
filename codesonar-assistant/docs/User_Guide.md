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

Query examples:
- `How to fix Use After Free`
- `How to fix Inappropriate Assignment Type`

Returns:
- Why the class is reported
- Risks and common patterns
- Safer fix pattern
- Verification checklist
- Relevant standards
- Tracker hotspots

## Batch Fix Plan

Query example:
- `Batch Fix Plan for Use of strcpy`

Returns class/file hotspots and a prioritized plan to maximize finding reduction.
