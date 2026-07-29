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
- `scripts/auto_fix.py`
  - Applies safe mechanical fixes and reruns pre-commit review
- `scripts/gerrit_client.py`
  - Thin Gerrit REST client for reading changes and posting reviews
- `scripts/gerrit_hook.py`
  - Reviews a Gerrit patchset and posts Verified votes/comments
- `scripts/gerrit_review.py`
  - Resolves pasted Gerrit links into change/patchset reviews
- `scripts/gerrit_event_listener.py`
  - Listens to Gerrit `patchset-created` events and triggers the hook
- `scripts/daily_workflow.py`
  - End-to-end tracker update workflow
- `scripts/sync.py`
  - Preserves assignment/review state while syncing findings
- `scripts/parser.py`
  - Normalizes CodeSonar CSV columns
- `scripts/report_generator.py`
  - Builds the Summary and Details sheets and saves the tracker workbook

## Data Flow

1. Input CSV is parsed and normalized
2. Intent detection selects handler
3. Handler computes results from tracker data or routes to Gerrit/auto-fix flows
4. Optional workflow produces exported Excel artifacts or posts Gerrit review votes

## Outputs

- `output/Master_Tracker.xlsx` (Summary + Details sheets)
- `output/Master_Tracker_YYYYMMDD.xlsx` (Summary + Details sheets)
- `output/Tracker_History.xlsx`
