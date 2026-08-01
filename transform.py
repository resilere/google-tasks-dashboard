"""
transform.py
Transform raw task data into analytics-ready format with derived columns.
"""
import pandas as pd
from datetime import timedelta


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns for analytics.
    Expected input: DataFrame with columns from tasks_api.fetch_tasks()
    Gracefully handles missing optional fields.
    Converts all datetimes to tz-naive UTC for consistency.
    Returns a frame that always carries the derived columns (even when empty), so
    downstream analytics never KeyError on an empty task list.
    """
    # (column name -> dtype) for every column analytics expects to exist.
    derived_dtypes = {
        "age_days": "float64", "days_overdue": "float64", "completion_lag": "float64",
        "comp_hour": "float64", "comp_dow": "float64",
        "is_subtask": "bool", "has_due": "bool",
        "category": "object", "comp_week": "object", "comp_month": "object",
        "comp_date": "datetime64[ns]",
    }
    if df.empty:
        out = df.copy()
        for col in ["updated", "due", "completed"]:
            if col not in out.columns:
                out[col] = pd.Series(dtype="datetime64[ns]")
        if "status" not in out.columns:
            out["status"] = pd.Series(dtype="object")
        for col, dtype in derived_dtypes.items():
            if col not in out.columns:
                out[col] = pd.Series(dtype=dtype)
        return out

    df = df.copy()
    
    # Helper to convert any datetime to tz-naive
    def to_tz_naive(s):
        if pd.isna(s) or s is None:
            return pd.NaT
        try:
            # Convert to datetime, then to UTC, then strip timezone
            ts = pd.to_datetime(s, utc=True)
            return ts.tz_localize(None)
        except Exception:
            return pd.NaT
    
    today = pd.Timestamp.now().normalize()

    # ── Ensure required datetime columns exist ─────────
    if "updated" not in df.columns:
        df["updated"] = pd.NaT
    if "due" not in df.columns:
        df["due"] = pd.NaT
    if "completed" not in df.columns:
        df["completed"] = pd.NaT
    if "status" not in df.columns:
        df["status"] = "needsAction"

    # Convert to datetime and strip timezone info
    df["updated"] = df["updated"].apply(to_tz_naive)
    df["due"] = df["due"].apply(to_tz_naive)
    df["completed"] = df["completed"].apply(to_tz_naive)

    # ── Basic derived metrics ──────────────────────────
    df["age_days"] = (today - df["updated"]).dt.days.clip(lower=0)
    df["days_overdue"] = (today - df["due"]).dt.days.where(
        (df["status"] == "needsAction") & df["due"].notna(), other=None
    )
    df["completion_lag"] = (df["completed"] - df["due"]).dt.days.where(
        df["completed"].notna() & df["due"].notna()
    )
    df["is_subtask"] = df["parent"].notna() if "parent" in df.columns else False
    df["has_due"] = df["due"].notna()
    df["category"] = df["list_title"] if "list_title" in df.columns else "Untitled"

    # ── Time decomposition ─────────────────────────────
    df["comp_date"] = df["completed"].dt.normalize()
    df["comp_week"] = df["completed"].dt.to_period("W").astype(str)
    df["comp_month"] = df["completed"].dt.to_period("M").astype(str)
    df["comp_hour"] = df["completed"].dt.hour
    df["comp_dow"] = df["completed"].dt.dayofweek  # 0=Mon

    return df


def open_tasks(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to open tasks."""
    return df[df["status"] == "needsAction"]


def closed_tasks(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to completed tasks."""
    return df[df["status"] == "completed"]