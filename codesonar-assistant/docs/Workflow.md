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

Gerrit review flow:

Paste Gerrit link
        |
        v
Resolve change and patchset
        |
        v
Run CodeSonar pre-commit review
        |
        v
Post Gerrit comments and Verified vote
        |
        v
READY / NOT READY

## Notes

- Existing issue assignment metadata is preserved during sync
- Newly introduced issues are assigned from configured owner/reviewer pools
- Workflow outputs are timestamped for historical analysis
- Gerrit patchset review can also be triggered by the event listener on `patchset-created`
- Auto Fix runs safe mechanical edits before re-running the pre-commit review
