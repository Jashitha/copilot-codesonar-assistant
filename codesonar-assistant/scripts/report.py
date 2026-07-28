def summarize_by_class(filtered_df):
    """
    Return a summary of findings grouped by class.
    """
    summary = (
        filtered_df["class"]
        .value_counts()
        .reset_index()
    )

    summary.columns = ["Class", "Count"]

    return summary

def save_assignment_report(assigned_df, filename):
    """
    Save the assigned issues to an Excel file.
    """
    assigned_df.to_excel(filename, index=False)

def save_owner_reports(assigned_df, output_dir):
    """
    Generate one Excel file for each owner.
    """

    owners = assigned_df["Owner"].unique()

    for owner in owners:
        owner_df = assigned_df[assigned_df["Owner"] == owner]

        filename = f"{output_dir}/{owner}.xlsx"

        owner_df.to_excel(filename, index=False)
