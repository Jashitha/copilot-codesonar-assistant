# Installation

If you are on Windows, the easiest path is to run `setup.bat` once and then use `run.bat` for normal work.
The steps below are the manual setup path if you want to do everything yourself.

## 1. Clone Repository

```bash
git clone <your-repo-url>
cd codesonar-assistant
```

If you want the full assistant workspace, clone this repository and open it in VS Code.

## 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Environment

`.env` is created automatically from `.env.example` the first time you run any assistant script, so this step is optional. To create it yourself instead:

```bash
cp .env.example .env
```

Required values for the tracker and dashboard workflow:

- `CODESONAR_REPORT_URL`
- `CODESONAR_USERNAME`
- `CODESONAR_PASSWORD`
- Optional: `CODESONAR_COOKIE`, `CODESONAR_TOKEN`, `CODESONAR_OWNERS`, `CODESONAR_REVIEWERS`, `CODESONAR_INSECURE`

Required values for daily email reports:

- `EMAIL_BACKEND=smtp`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `EMAIL_FROM`
- `EMAIL_OWNERS`
- `EMAIL_CC`

`EMAIL_OWNERS` is the consolidated recipient list for owners/reviewers. `EMAIL_CC` is the team/group email.

## 5. SMTP Prerequisites

SMTP is the only supported email-sending mechanism. Outlook Desktop is not required.

Use one of these server modes:

- Port `587` with `SMTP_USE_TLS=true` for STARTTLS
- Port `465` for SMTP over SSL

Install the Python dependencies in the virtual environment:

```bash
pip install -r requirements.txt
```

## 6. Daily Email Commands

Preview the report without sending mail:

```bash
python3 scripts/run_daily_code_sonar_report.py --preview
```

Send the report:

```bash
python3 scripts/run_daily_code_sonar_report.py
```

You can also ask the assistant:

- `Preview Daily CodeSonar Report`
- `Send Daily CodeSonar Report`
- `Daily Email Report`

`Daily Email Report` is an alias for send.

## 7. Task Scheduler

Use Windows Task Scheduler to run the daily workflow on a schedule.

Example action:

- Program: `C:/path/to/codesonar-assistant/run.bat`
- Or directly run: `C:/path/to/codesonar-assistant/.venv/Scripts/python.exe`
- Arguments: `scripts/run_daily_code_sonar_report.py`
- Start in: `C:/path/to/codesonar-assistant`

Recommended schedule:

- Trigger: daily at the desired report time
- Run only when user is logged on if the environment or file access depends on the desktop session
- The scheduled workflow is: CodeSonar daily workflow -> latest CodeSonar analysis -> tracker update -> dashboard generation -> HTML email report -> SMTP send

## 8. Notes

- Linux can still generate the tracker, dashboard, and HTML report preview.
- The generated files are stored under `output/email/`.
