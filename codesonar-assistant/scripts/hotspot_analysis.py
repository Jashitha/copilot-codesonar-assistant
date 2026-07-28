import pandas as pd

def hotspot_analysis(df, top_n=5):
    files = (
        df.groupby("file")
          .size()
          .reset_index(name="count")
          .sort_values("count", ascending=False)
          .head(top_n)
    )

    total = len(df)
    files["percent"] = (files["count"] / total * 100).round(1)

    top_total = files["count"].sum()

    answer = (
        f"Top {top_n} hotspot files contain "
        f"{top_total} findings "
        f"({top_total/total*100:.1f}% of all findings)."
    )

    return {
        "answer": answer,
        "count": len(files),
        "rows": files.to_dict("records")
    }