def filter_high_priority(df):
    """
    Return only HB_PRIO_1 and HB_PRIO_2 findings.
    """
    return df[df["priority"].isin(["HB_PRIO_1", "HB_PRIO_2"])]
