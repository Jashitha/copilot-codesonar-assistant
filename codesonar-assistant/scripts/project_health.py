import pandas as pd


def project_health(df):

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

    if hb1 > 20:
        risk = "HIGH"
    elif hb1 > 10:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "answer": f"Project Health: {risk}",
        "count": total,
        "rows": [
            {
                "Metric": "Total Issues",
                "Value": total
            },
            {
                "Metric": "Pending",
                "Value": pending
            },
            {
                "Metric": "Done",
                "Value": done
            },
            {
                "Metric": "HB_PRIO_1",
                "Value": hb1
            },
            {
                "Metric": "HB_PRIO_2",
                "Value": hb2
            },
            {
                "Metric": "Risk",
                "Value": risk
            },
            {
                "Metric": "Recommendation",
                "Value": "Resolve HB_PRIO_1 issues first."
            }
        ]
    }