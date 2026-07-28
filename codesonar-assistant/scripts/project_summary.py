import pandas as pd


def project_summary(df):
    total = len(df)

    pending = len(
        df[df["Status"].astype(str).str.lower() == "pending"]
    )

    done = len(
        df[df["Status"].astype(str).str.lower() == "done"]
    )

    hb1 = len(
        df[df["priority"] == "HB_PRIO_1"]
    )

    hb2 = len(
        df[df["priority"] == "HB_PRIO_2"]
    )

    top_file = (
        df["file"]
        .value_counts()
        .head(1)
    )

    top_class = (
        df["class"]
        .value_counts()
        .head(1)
    )

    owners = (
        df["Owner"]
        .value_counts()
    )

    summary = (
        f"Project currently has {total} issues. "
        f"{pending} are pending and {done} are completed. "
        f"There are {hb1} HB_PRIO_1 issues and {hb2} HB_PRIO_2 issues. "
        f"The most affected file is {top_file.index[0]} ({top_file.iloc[0]} issues). "
        f"The most common issue class is '{top_class.index[0]}' ({top_class.iloc[0]} issues). "
        f"Owner distribution: "
        + ", ".join(
            [
                f"{owner}: {count}"
                for owner, count in owners.items()
            ]
        )
        + "."
    )

    return {
        "answer": summary,
        "count": total,
        "rows": []
    }