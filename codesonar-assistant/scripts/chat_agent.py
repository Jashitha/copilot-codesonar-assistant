import pandas as pd

from intent import detect_intent
from dispatcher import dispatch

EXCEL_FILE = "/data/home/jkunhiparamb/codesonar_agent/output/Master_Tracker.xlsx"


def rows_for_display(df: pd.DataFrame, limit: int = 20):

    preferred = [
        "id",
        "class",
        "priority",
        "Owner",
        "Status",
        "file",
        "line number",
    ]

    cols = [c for c in preferred if c in df.columns]

    if not cols:
        cols = list(df.columns)

    return df[cols].head(limit).to_dict(orient="records")


def normalize_response(response):

    if isinstance(response, pd.DataFrame):

        if len(response) == 0:
            return {
                "answer": "No matching issues found.",
                "count": 0,
                "rows": [],
            }

        return {
            "answer": f"Found {len(response)} issue(s).",
            "count": len(response),
            "rows": rows_for_display(response),
        }

    if isinstance(response, dict):
        return {
            "answer": response.get("answer", "No answer available."),
            "count": response.get("count", 0),
            "rows": response.get("rows", []),
        }

    return {
        "answer": str(response),
        "count": 0,
        "rows": [],
    }


def main():

    print("=" * 60)
    print("        CodeSonar AI Assistant")
    print("Type 'exit' to quit")
    print("=" * 60)

    df = pd.read_excel(EXCEL_FILE)

    while True:

        query = input("\nYou > ").strip()

        if query.lower() in ["exit", "quit"]:
            print("\nGoodbye!")
            break

        intent = detect_intent(query)

        print(f"\nIntent: {intent}")

        raw_response = dispatch(df, intent, query)
        response = normalize_response(raw_response)
        context["last_response"] = response

        print("\nAssistant:")
        print(response["answer"])

        if response.get("rows"):
            print()

            for row in response["rows"]:
                print(row)
context = {
    "owner": None,
    "issue": None,
    "file": None,
    "last_response": None
}


if __name__ == "__main__":
    main()