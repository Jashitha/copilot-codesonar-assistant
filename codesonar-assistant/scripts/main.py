import pandas as pd

from parser import read_codesonar_report
from filters import filter_high_priority
from report import (
    summarize_by_class,
    save_assignment_report,
    save_owner_reports,
)
from assignment import assign_owners
from tracker import (
    generate_progress_summary,
    generate_owner_summary,
)
from sync import sync_tracker
from assistant import process_query


def create_assignment():

    csv_file = "data/codesonar.csv"

    df = read_codesonar_report(csv_file)

    filtered_df = filter_high_priority(df)

    print(f"\nTotal Findings : {len(df)}")
    print(f"High Priority Findings : {len(filtered_df)}")

    summary_df = summarize_by_class(filtered_df)

    print("\n========== CLASS SUMMARY ==========")
    print(summary_df)

    num_devs = int(input("\nEnter number of developers: "))

    developers = []

    for i in range(num_devs):
        name = input(f"Enter Developer {i+1} Name: ")
        developers.append(name)

    assigned_df = assign_owners(filtered_df, developers)

    save_assignment_report(
        assigned_df,
        "output/Master_Tracker.xlsx"
    )

    save_owner_reports(
        assigned_df,
        "output"
    )

    print("\nAssignment report generated successfully!")


def synchronize():

    print("\nSynchronizing Master Tracker...\n")

    latest_df = read_codesonar_report("data/codesonar.csv")
    latest_df = filter_high_priority(latest_df)

    master_df = pd.read_excel(
        "output/Master_Tracker.xlsx",
        dtype={"id": str}
    )

    latest_df["id"] = latest_df["id"].astype(str).str.strip()
    master_df["id"] = master_df["id"].astype(str).str.strip()

    updated_df, new_df, resolved_df = sync_tracker(
        master_df,
        latest_df
    )

    updated_df.to_excel(
        "output/Master_Tracker.xlsx",
        index=False
    )

    print(f"Existing Issues : {len(updated_df) - len(new_df)}")
    print(f"New Issues      : {len(new_df)}")
    print(f"Resolved Issues : {len(resolved_df)}")


def track_progress():

    df = pd.read_excel("output/Master_Tracker.xlsx")

    generate_progress_summary(df)

    generate_owner_summary(df)

def ask_ai():

    df = pd.read_excel(
        "output/Master_Tracker.xlsx",
        dtype={"id": str}
    )

    while True:

        query = input("\nAsk CodeSonar AI ('back' to return): ")
        normalized_query = query.strip().lower()

        if normalized_query == "back":
            break

        result = process_query(df, query)

        if "how many" in normalized_query and "issue" in normalized_query:
            print(f"\nTotal issues: {len(result)}")
            continue

        if len(result) == 0:
            print("\nNo matching issues found.")

        else:
            print(f"\nFound {len(result)} issue(s)\n")

            print(result[
                ["id",
                 "class",
                 "priority",
                 "Owner",
                 "Status"]
            ])


def main():

    while True:

        print("\n========================================")
        print("      CodeSonar Work Tracker")
        print("========================================")
        print("1. Create New Assignment")
        print("2. Synchronize Latest Report")
        print("3. Track Progress")
        print("4. Ask CodeSonar AI")
        print("5. Exit")

        choice = input("\nEnter your choice: ")

        if choice == "1":
            create_assignment()

        elif choice == "2":
            synchronize()

        elif choice == "3":
            track_progress()

        elif choice == "4":
            ask_ai()

        elif choice == "5":
            print("Goodbye!")
            break

        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()