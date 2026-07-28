def assign_owners(filtered_df, developers):
    if not developers:
        raise ValueError("developers list cannot be empty")

    assigned_df = filtered_df.copy()

    assigned_df["Owner"] = [
        developers[index % len(developers)]
        for index in range(len(assigned_df))
    ]
    assigned_df["Status"] = "Pending"
    assigned_df["ETA"] = ""

    return assigned_df