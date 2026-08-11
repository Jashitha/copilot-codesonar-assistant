# Installation

## 1. Clone Repository

```bash
git clone <your-repo-url>
cd codesonar-assistant
```

If you want the full assistant workspace, clone this repository and open it in VS Code. The workspace agent definition is already included at `agents/codesonar-assistant.md`.

## 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Copy the Agent

The agent definition is maintained in the top-level repo at `agents/codesonar-assistant.md`.

If you are creating a new workspace, copy that file into the target workspace's `agents/` folder. VS Code will use it as the workspace-level agent configuration once the workspace is opened or reloaded.

## 5. Configure Environment

`.env` is created automatically from `.env.example` the first time you run any assistant script (for example `daily_workflow.py`, `codesonar_assistant.py`, `gerrit_hook.py`, or `gerrit_event_listener.py`), so this step is optional. To create it yourself instead:

```bash
cp .env.example .env
```

Set values in `.env`:

- `CODESONAR_REPORT_URL`
- `CODESONAR_USERNAME`
- `CODESONAR_PASSWORD`
- Optional: `CODESONAR_COOKIE`, `CODESONAR_TOKEN`, `CODESONAR_OWNERS`, `CODESONAR_INSECURE`

Also set Gerrit values for review and gate workflows:

- `GERRIT_URL`
- `GERRIT_USER`
- `GERRIT_HTTP_PASSWORD`

Those values let the assistant review pasted Gerrit links, post inline comments, and cast `Verified -1` or `Verified +1` as needed.

The assistant is project-generic and supports both C and C++ CodeSonar projects.

- Offline mode uses an exported CodeSonar CSV or an existing tracker as input.
- Live mode connects to a CodeSonar server through the `.env` settings above.

## 6. Restart VS Code

Restart VS Code so new agent/customization settings are picked up.


## 7. Configure Daily Email Reports

To enable daily email summaries, add the following values to `.env`:

- `EMAIL_ENABLED=true`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`
- Optional: `EMAIL_CC`, `EMAIL_BCC`
- Optional owner-specific routing: `OWNER_EMAILS_JSON`
- Optional dashboard/tracker quick links: `EMAIL_DASHBOARD_URL`, `EMAIL_MASTER_TRACKER_URL`, `EMAIL_HB_PRIO_1_URL`

Generate the report without sending mail:

```bash
python3 scripts/codesonar_assistant.py --query "Daily CodeSonar Report"
```

Preview the report first:

```bash
python3 scripts/codesonar_assistant.py --query "Preview Daily CodeSonar Report"
```

Send the report after validating the output:

```bash
python3 scripts/codesonar_assistant.py --query "Send Daily CodeSonar Report"
```

The generated files are stored under `output/email/`, including the HTML report, a plain-text fallback, and `email_history.log`. If email delivery fails, check SMTP connectivity and the log file, but avoid storing secrets in logs.
