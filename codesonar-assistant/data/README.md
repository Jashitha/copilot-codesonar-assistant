# data/

This directory stores runtime CodeSonar CSV snapshots downloaded by the daily workflow.

Files here are excluded from Git (see `.gitignore`).

To populate this directory, run the Update Tracker workflow or place your
`codesonar.csv` export here manually.

The CSV in this folder can be project-specific, depending on the
`CODESONAR_REPORT_URL` and credentials configured in `.env`.

In offline mode, this directory can hold exported CSV input for an existing
CodeSonar project or tracker snapshot.

In live mode, the daily workflow uses the `.env` configuration to connect to
the CodeSonar server and refresh this data.
