import pandas as pd


def sync_tracker(master_df, latest_df):
    """
    Synchronize the Master Tracker with the latest CodeSonar report.

    Existing issues:
        - Preserve Owner
        - Preserve Status
        - Preserve ETA
        - Preserve Reviewer
        - Preserve ReviewStatus
        - Preserve ReviewETA

    New issues:
        - Owner = Unassigned
        - Status = Pending
        - ETA = blank
        - Reviewer = Unassigned
        - ReviewStatus = Pending
        - ReviewETA = blank

    Returns:
        updated_df
        new_issues
        resolved_issues
    """

    keep_columns = [
        "id",
        "Owner",
        "Status",
        "ETA",
        "Reviewer",
        "ReviewStatus",
        "ReviewETA",
    ]

    master_small = master_df.copy()
    for col in keep_columns:
        if col not in master_small.columns:
            master_small[col] = ""

    master_small = master_small[keep_columns]

    updated_df = latest_df.merge(
        master_small,
        on="id",
        how="left"
    )

    updated_df["Owner"] = updated_df["Owner"].fillna("Unassigned")
    updated_df["Status"] = updated_df["Status"].fillna("Pending")
    updated_df["ETA"] = updated_df["ETA"].fillna("")

    updated_df["Reviewer"] = updated_df["Reviewer"].fillna("Unassigned")
    updated_df["ReviewStatus"] = updated_df["ReviewStatus"].fillna("Pending")
    updated_df["ReviewETA"] = updated_df["ReviewETA"].fillna("")

    new_issues = latest_df[
        ~latest_df["id"].isin(master_df["id"])
    ]

    resolved_issues = master_df[
        ~master_df["id"].isin(latest_df["id"])
    ]

    print("Master IDs :", len(master_df["id"].unique()))
    print("Latest IDs :", len(latest_df["id"].unique()))

    common = latest_df["id"].isin(master_df["id"])

    print("Common IDs :", common.sum())
    print("New IDs    :", (~common).sum())

    return updated_df, new_issues, resolved_issues
