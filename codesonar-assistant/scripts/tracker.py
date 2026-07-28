def generate_progress_summary(df):
    total = len(df)

    done = len(df[df["Status"] == "Done"])

    pending = len(df[df["Status"] == "Pending"])

    completion = (done / total) * 100 if total else 0

    print("\n========== Progress Summary ==========")
    print(f"Total Issues : {total}")
    print(f"Done         : {done}")
    print(f"Pending      : {pending}")
    print(f"Completion   : {completion:.2f}%")

def generate_owner_summary(df):

    assigned = df.groupby("Owner").size()

    done = (
        df[df["Status"] == "Done"]
        .groupby("Owner")
        .size()
    )

    pending = (
        df[df["Status"] == "Pending"]
        .groupby("Owner")
        .size()
    )

    owner_df = assigned.reset_index(name="Assigned")

    owner_df["Done"] = owner_df["Owner"].map(done).fillna(0).astype(int)

    owner_df["Pending"] = owner_df["Owner"].map(pending).fillna(0).astype(int)

    print("\n========== OWNER SUMMARY ==========")
    print(owner_df)
