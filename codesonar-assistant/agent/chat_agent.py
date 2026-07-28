import os
from pathlib import Path

import pandas as pd

from dispatcher import dispatch_query
from llm.factory import get_llm


DEFAULT_TRACKER = "/data/home/jkunhiparamb/codesonar_agent/output/Master_Tracker.xlsx"


def _load_env_file(env_path: Path):
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


def main():
    root_dir = Path(__file__).resolve().parents[1]
    _load_env_file(root_dir / ".env")

    tracker_path = os.getenv("CODESONAR_TRACKER_PATH", DEFAULT_TRACKER)
    df = pd.read_excel(tracker_path, dtype={"id": str})

    llm = get_llm()

    context = {
        "owner": None,
        "issue": None,
        "file": None,
        "last_response": None,
    }

    print("=" * 60)
    print("        CodeSonar AI Assistant")
    print("Type 'exit' to quit")
    print("=" * 60)

    while True:
        query = input("\nYou > ").strip()

        if query.lower() in {"exit", "quit"}:
            print("\nGoodbye!")
            break

        intent, response = dispatch_query(df, query)
        context["last_response"] = response

        print(f"\nIntent: {intent}")
        print("\nAssistant:")

        try:
            llm_response = llm.chat(
                query,
                context={
                    "intent": intent,
                    "analysis": response,
                    "session": context,
                },
            )
            print(llm_response)

        except Exception as exc:
            print(response["answer"])
            print(f"\n[LLM fallback to deterministic answer: {exc}]")

        rows = response.get("rows", [])
        if rows:
            print("\nTop rows:")
            for row in rows[:10]:
                print(row)


if __name__ == "__main__":
    main()
