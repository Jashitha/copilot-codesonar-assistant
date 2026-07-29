# data/

This directory stores runtime CodeSonar CSV snapshots downloaded by the daily workflow.

Files here are excluded from Git (see `.gitignore`).

To populate this directory, run the Update Tracker workflow or place your
`codesonar.csv` export here manually.

The CSV in this folder can be project-specific, depending on the
`CODESONAR_REPORT_URL` and credentials configured in `.env`.
