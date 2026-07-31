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

## Notes

- Existing issue assignment metadata is preserved during sync
- Newly introduced issues are assigned from configured owner/reviewer pools
- Workflow outputs are timestamped for historical analysis
- Gerrit patchset review can also be triggered by the event listener on `patchset-created`
- Gerrit patchset review downloads reviewable file contents from Gerrit before running the Review Engine
- Auto Fix automatically repairs supported safe mechanical violations before re-running the pre-commit review; unsupported findings flow to Fix Guide
