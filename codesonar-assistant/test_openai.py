from pathlib import Path
import os

from openai import APIStatusError, OpenAI, OpenAIError, RateLimitError


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue

        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(Path(__file__).resolve().parent / ".env")

api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is missing. Set it in shell or in .env, then rerun."
    )

client = OpenAI(api_key=api_key)
model = os.getenv("OPENAI_MODEL", "gpt-4.1").strip() or "gpt-4.1"

try:
    response = client.responses.create(
        model=model,
        input="Say hello."
    )
    print(response.output_text)

except RateLimitError as exc:
    print("OpenAI request failed: insufficient quota or rate limit.")
    print("Next steps:")
    print("1. Check OpenAI billing/quota in your account.")
    print("2. Try a lower-cost model (for example gpt-4.1).")
    print("3. Or switch to local mode with LLM_PROVIDER=ollama.")
    print(f"Details: {exc}")

except APIStatusError as exc:
    print(f"OpenAI API status error ({exc.status_code}): {exc}")

except OpenAIError as exc:
    print(f"OpenAI error: {exc}")