# CodeSonar Assistant

CodeSonar Assistant is an AI-powered GitHub Copilot agent that simplifies daily CodeSonar analysis and tracker management. It automates repetitive tasks such as downloading reports, updating trackers, generating dashboards, preserving assignments, and answering natural language queries about CodeSonar findings.

## Key Features

### Tracker Management
- Download the latest CodeSonar report
- Filter findings to **HB_PRIO_1** and **HB_PRIO_2**
- Synchronize with the existing Master Tracker
- Preserve Owner, Reviewer, Status, ETA, and Review information
- Automatically assign new findings when owner/reviewer pools are configured
- Generate updated Master Tracker, timestamped snapshots, and tracker history

### Dashboard & Analytics
- Dashboard summary
- Project Health analysis
- Trend Analysis (compare tracker snapshots)
- Hotspot Analysis
- Top Files
- Top Issue Classes
- Owner Workload
- Owner Progress

### Issue Analysis
- Recommend Next Issue
- Issue Details
- Explain Issue
- Similar Issues
- Search by file, class, owner, or priority

### Fix Guidance
Provides fix guidance for CodeSonar findings, including:

- Class-level Fix Guide
- Issue-level Fix Guide
- Batch Fix Guide
- Common causes
- Risk explanation
- Recommended remediation
- High-impact procedures/files to prioritize

### Pre-Commit Code Review
Review source files before commit using built-in checkers:

- Dangerous API checker
- MISRA-C:2012 checker
- CodeSonar-mapped pattern checker
- Memory checker (placeholder when no rules are returned)

Returns grouped findings with line, severity, message, recommendation, summary counts, and commit readiness.

## Folder Structure

```text
codesonar-assistant/
├── scripts/         # Backend implementation
├── docs/            # User guide & architecture
├── data/            # Runtime CSV snapshots
├── input/           # Sample input files
├── output/          # Generated trackers & dashboards
├── examples/        # Example queries and outputs
├── README.md
├── INSTALL.md
├── requirements.txt
└── .env.example
```

Workspace-level agent definition is stored in the top-level repo at `agents/codesonar-assistant.md`.

## Quick Start

1. Clone the repository.

```bash
git clone <repository-url>
cd codesonar-assistant
```

2. Create a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Configure environment variables.

```bash
cp .env.example .env
```

Update the CodeSonar URL and credentials in `.env`.

5. Run the assistant.

```bash
python3 scripts/codesonar_assistant.py \
    --input data/codesonar.csv \
    --query "Dashboard"
```

After the tracker workflow has run successfully, you can also query the generated tracker directly:

```bash
python3 scripts/codesonar_assistant.py \
    --input output/Master_Tracker.xlsx \
    --query "Trend Analysis"
```

## Example Queries

### Dashboard & Project

- Dashboard
- Project Health
- Trend Analysis
- Hotspot Analysis
- Project Summary

### Tracker

- Update Tracker
- Owner Workload for a
- Owner Progress for b

### Recommendations

- Recommend Next Issue for a
- Recommend Owner
- Similar Issues 6253372

### Issue Details

- Issue 6253372
- Explain Issue 6253372
- Show Issues in bsmd.c
- Show HB_PRIO_1 Issues

### Fix Guidance

- How to fix Inappropriate Assignment Type
- How to fix Use After Free
- How to fix Use of strcpy
- Fix Guide 1201340.7557926828
- Batch Fix Guide
- Where should I focus for biggest impact?

### Pre-Commit Review

- review tests/sample_code/dangerous_api.c
- pre-commit review /absolute/path/to/file.c
- check my code bsmd.c
- commit readiness bsmd.c

## Output Files

The assistant automatically generates:

- Master_Tracker.xlsx (two sheets: Summary + Details)
- Tracker_History.xlsx
- Timestamped tracker snapshots (same two-sheet structure)

## Benefits

- Eliminates repetitive manual tracker updates
- Preserves assignment history across daily reports
- Provides instant project health and dashboard metrics
- Helps prioritize high-risk findings
- Explains CodeSonar findings with recommended fixes
- Enables natural language interaction with CodeSonar data through GitHub Copilot

## License

Internal project intended for CodeSonar automation and analysis.