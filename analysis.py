import pandas as pd

def analyze(tasks):

    df = pd.DataFrame(tasks)

    # --------------------------
    # Timestamp conversion
    # --------------------------
    df["created"] = pd.to_datetime(df.get("created"), errors="coerce", utc=True)
    df["completed"] = pd.to_datetime(df.get("completed"), errors="coerce", utc=True)

    # --------------------------
    # Derived columns
    # --------------------------
    df["time_to_complete"] = df["completed"] - df["created"]

    df["completion_days"] = (
        df["time_to_complete"].dt.total_seconds() / 86400
    )

    today = pd.Timestamp.now(tz="UTC")

    df["age_days"] = (today - df["created"]).dt.days

    # --------------------------
    # Completed tasks
    # --------------------------
    completed = df[df["status"] == "completed"].copy()
    completed = completed[completed["time_to_complete"].notna()]

    # --------------------------
    # Aggregations
    # --------------------------
    per_day = completed.groupby(
        completed["completed"].dt.date
    ).size().reset_index(name="tasks_completed")

    per_week = completed.groupby(
        completed["completed"].dt.to_period("W").astype(str)
    ).size().reset_index(name="tasks_completed")

    # --------------------------
    # Ranking datasets
    # --------------------------
    longest_completion = completed.sort_values(
        "time_to_complete",
        ascending=False
    )

    recent_completed = completed.sort_values(
        "completed",
        ascending=False
    )

    oldest_pending = df[df["status"] != "completed"].sort_values(
        "age_days",
        ascending=False
    )

    return {
        "df": df,
        "completed": completed,
        "per_day": per_day,
        "per_week": per_week,
        "longest_completion": longest_completion,
        "recent_completed": recent_completed,
        "oldest_pending": oldest_pending
    }