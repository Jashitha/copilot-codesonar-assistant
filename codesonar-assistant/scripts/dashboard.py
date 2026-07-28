import pandas as pd


def dashboard(df):

    total = len(df)

    pending = len(
        df[df["Status"].astype(str).str.lower() == "pending"]
    )

    done = len(
        df[df["Status"].astype(str).str.lower() == "done"]
    )

    prio1 = len(
        df[df["priority"] == "HB_PRIO_1"]
    )

    prio2 = len(
        df[df["priority"] == "HB_PRIO_2"]
    )

    owners = (
        df.groupby("Owner")
        .size()
        .reset_index(name="Assigned")
        .sort_values("Assigned", ascending=False)
    )

    files = (
        df.groupby("file")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
        .head(5)
    )

    classes = (
        df.groupby("class")
        .size()
        .reset_index(name="Issues")
        .sort_values("Issues", ascending=False)
        .head(5)
    )

    rows = [
        {"Metric": "Total Issues", "Value": total},
        {"Metric": "Pending", "Value": pending},
        {"Metric": "Done", "Value": done},
        {"Metric": "HB_PRIO_1", "Value": prio1},
        {"Metric": "HB_PRIO_2", "Value": prio2},
        {"Metric": "Owners", "Value": len(owners)},
        {},
        {"Top Owners": ""},
        *owners.to_dict("records"),
        {},
        {"Top Files": ""},
        *files.to_dict("records"),
        {},
        {"Top Classes": ""},
        *classes.to_dict("records"),
    ]

    return {
        "answer": "CodeSonar Dashboard",
        "count": total,
        "rows": rows,
    }