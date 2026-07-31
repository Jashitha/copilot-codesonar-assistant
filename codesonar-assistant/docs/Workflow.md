# Workflow

Daily workflow sequence:

Update Tracker
        |
        v
Download latest CodeSonar CSV
        |
        v
Filter HB_PRIO_1 / HB_PRIO_2
        |
        v
Sync Master Tracker
        |
        v
Preserve Owners & Status
        |
        v
Assign New Issues
        |
        v
Generate Dashboard
        |
        v
Ready for Queries

Gerrit Patchset Review flow:

```mermaid
flowchart TD
    A[Paste Gerrit link] --> B[Resolve change and patchset]
    B --> C[Language Detection (.c / .cpp)]
    C --> D[MISRA C / MISRA C++ Analysis]
    C --> E[CodeSonar Pattern Analysis]
    C --> F[Dangerous API Analysis]
    C --> G[Memory Safety Analysis]
    C --> H[Custom Project Rules]
        D --> I[Commit Readiness Report]
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J[Post Gerrit comments and Verified vote]
    J --> K[READY / NOT READY]
```

## Command Cheat Sheet

Start with one of these prompts when you are not sure what to ask:

- `Update Tracker` to refresh live or offline data
- `Dashboard` to see overall project metrics
- `Project Health` to inspect risk concentration
- `Fix Guide <class or issue>` to understand a specific finding
- `Batch Fix Guide` to prioritize high-impact files
- `Auto Fix <source file>` to apply safe edits and rerun review
- `review <source file>` to run local pre-commit review
- `Gerrit patchset review <gerrit link>` to review a patchset

## Live and Offline Modes

Live mode:
1. Set `CODESONAR_REPORT_URL` to the report or CSV export endpoint.
2. Add credentials or token/cookie values in `.env`.
3. Run `Update Tracker` or `Dashboard` to download fresh data.

Offline mode:
1. Use an exported CSV or an existing tracker workbook.
2. Point the assistant at the local file path.
3. Run `Update Tracker`, `Dashboard`, or any issue query against the local data.

## Notes

- Existing issue assignment metadata is preserved during sync
- Newly introduced issues are assigned from configured owner/reviewer pools
- Workflow outputs are timestamped for historical analysis
- Gerrit patchset review can also be triggered by the event listener on `patchset-created`
- Gerrit patchset review downloads reviewable file contents from Gerrit before running the Review Engine
- Auto Fix automatically repairs supported safe mechanical violations before re-running the pre-commit review; unsupported findings flow to Fix Guide
- `CODESONAR_REPORT_URL` should be a report or CSV-download endpoint, not a sign-in page
