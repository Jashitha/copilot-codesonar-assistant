import pandas as pd

def read_codesonar_report(csv_file):

    df = pd.read_csv(csv_file, dtype={"id": str})

    # Normalize columns
    df.columns = [c.strip() for c in df.columns]

    # Standardize names
    rename_map = {
        "owner": "Owner",
        "state": "Status",
        "class": "class",
        "priority": "priority",
    }

    for old, new in rename_map.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # Ensure required columns exist
    if "Owner" not in df.columns:
        df["Owner"] = "Unassigned"

    if "Status" not in df.columns:
        df["Status"] = "Pending"

    df["id"] = df["id"].astype(str).str.strip()

    return df
