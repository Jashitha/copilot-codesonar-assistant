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

## 6. Restart VS Code

Restart VS Code so new agent/customization settings are picked up.
