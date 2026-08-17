# CodeSonar Assistant

CodeSonar Assistant analyzes CodeSonar findings, maintains the tracker, and generates daily dashboards and reports.

## Quick Start

1. Clone the repo into a Windows-accessible folder.
2. Run `setup.bat` once.
3. Run `run.bat` for the guided menu.

## Windows Entry Points

- `setup.bat` installs Python dependencies and creates `.env` from `.env.example` if needed.
- `run.bat` opens a menu for tracker refresh, dashboard, preview, send, and ad-hoc queries.

## Daily Email Reports

The daily report uses SMTP with the configured mail server and sends one consolidated message to all owners in `EMAIL_OWNERS`, with the team group in `EMAIL_CC`.

- Preview the report without sending mail:

```bash
python3 scripts/run_daily_code_sonar_report.py --preview
```

- Send the consolidated daily report:

```bash
python3 scripts/run_daily_code_sonar_report.py
```

Natural-language aliases:

- `Preview Daily CodeSonar Report`
- `Send Daily CodeSonar Report`
- `Daily Email Report` sends the report.

The generated `output/email/Daily_CodeSonar_Report.html` file is used as the HTML email body.

## More Details

For manual setup and Windows scheduler guidance, see [INSTALL.md](INSTALL.md).
