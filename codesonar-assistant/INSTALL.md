# Installation

## 1. Clone Repository

```bash
git clone <your-repo-url>
cd codesonar-assistant
```

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

If needed by your setup, use that file as the source for your VS Code agent/customization location.

## 5. Configure Environment

```bash
cp .env.example .env
```

Set values in `.env`:

- `CODESONAR_REPORT_URL`
- `CODESONAR_USERNAME`
- `CODESONAR_PASSWORD`
- Optional: `CODESONAR_COOKIE`, `CODESONAR_TOKEN`, `CODESONAR_OWNERS`, `CODESONAR_INSECURE`

If you want Gerrit review and gate workflows, also set:

- `GERRIT_URL`
- `GERRIT_USER`
- `GERRIT_HTTP_PASSWORD`

Those values let the assistant review pasted Gerrit links, post inline comments, and cast `Verified -1` or `Verified +1` as needed.

The assistant is project-generic and supports both C and C++ CodeSonar projects.

- Offline mode uses an exported CodeSonar CSV or an existing tracker as input.
- Live mode connects to a CodeSonar server through the `.env` settings above.

## 6. Restart VS Code

Restart VS Code so new agent/customization settings are picked up.
