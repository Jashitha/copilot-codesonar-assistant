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

## Notes

- Existing issue assignment metadata is preserved during sync
- Newly introduced issues are assigned from configured owner/reviewer pools
- Workflow outputs are timestamped for historical analysis
