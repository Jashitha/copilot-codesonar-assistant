# Architecture

## Components

- `scripts/codesonar_assistant.py`
  - Entry point for query handling
- `scripts/intent.py`
  - Maps natural language to backend intent
- `scripts/dispatcher.py`
  - Routes intent to tool handlers
- `scripts/tools/`
  - Domain-specific handlers (dashboard, issue, owner, analytics)
- `scripts/daily_workflow.py`
  - End-to-end tracker update workflow
- `scripts/sync.py`
  - Preserves assignment/review state while syncing findings
- `scripts/parser.py`
  - Normalizes CodeSonar CSV columns

## Data Flow

1. Input CSV is parsed and normalized
2. Intent detection selects handler
3. Handler computes results from tracker data
4. Optional workflow produces exported Excel artifacts

## Outputs

- `output/Master_Tracker.xlsx`
- `output/Master_Tracker_YYYYMMDD.xlsx`
- `output/Dashboard_Output.xlsx`
- `output/Tracker_History.xlsx`
