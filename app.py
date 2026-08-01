"""
app.py
Google Tasks Manager with an integrated analytics dashboard.

Auth is per-user (see auth.py): every visitor signs in with their own Google
account and their credentials + task data stay in their own session.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from auth import get_credentials, logout
from tasks_api import get_service, fetch_tasks, add_task, update_task, delete_task
from transform import transform
from analytics import (
    chart_weekly_goal_ring,
    chart_velocity_sparkline,
    chart_cumulative,
    chart_oldest_open,
    chart_age_distribution,
    chart_overdue,
    chart_day_of_week,
    chart_time_of_day,
    chart_month_over_month,
    chart_rolling_average,
    compute_stats,
)

st.set_page_config(page_title="Tasks Manager", layout="wide")

# --------------------------
# Authentication (gates the whole app)
# --------------------------
creds = get_credentials()
service = get_service(creds)

st.title("📋 Google Tasks Manager")

tasklists = service.tasklists().list().execute().get("items", [])
if not tasklists:
    st.error("No task lists found in your Google account.")
    st.stop()

tasklist_id = st.selectbox(
    "Select Task List",
    [tl["id"] for tl in tasklists],
    format_func=lambda x: next(tl["title"] for tl in tasklists if tl["id"] == x)
)

# --------------------------
# Helpers
# --------------------------
def to_due_iso(due_date):
    if pd.isna(due_date):
        return None
    return pd.Timestamp(due_date, tz="UTC").strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _to_tz_naive(s):
    """Convert any datetime-like value to a tz-naive UTC Timestamp (or NaT)."""
    if pd.isna(s) or s is None:
        return pd.NaT
    try:
        return pd.to_datetime(s, utc=True).tz_localize(None)
    except Exception:
        return pd.NaT


def load_tasks(force: bool = False):
    """
    Load tasks for the selected list, cached per-session in st.session_state.

    NOTE: we deliberately cache in session_state (per browser session) rather than
    st.cache_data (shared across ALL users) so one visitor's tasks never leak into
    another visitor's view when the app is public.
    """
    cache = st.session_state.setdefault("_tasks_cache", {})
    if not force and tasklist_id in cache:
        return cache[tasklist_id]

    tasks = [t for t in fetch_tasks(service) if t["list_id"] == tasklist_id]

    if not tasks:
        df = pd.DataFrame(
            columns=["id", "title", "notes", "due", "status", "completed", "updated", "list_title"]
        )
    else:
        df = pd.DataFrame(tasks)
        required_cols = ["id", "title", "notes", "due", "status", "completed", "updated", "list_title", "parent"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = pd.NaT if col in ("due", "completed", "updated") else None
        df["due"] = df["due"].apply(_to_tz_naive)
        df["completed"] = df["completed"].apply(_to_tz_naive)
        df["updated"] = df["updated"].apply(_to_tz_naive)

    cache[tasklist_id] = df
    return df


def clear_tasks_cache():
    st.session_state.pop("_tasks_cache", None)


# Load data
raw_df = load_tasks()
df = transform(raw_df)

# --------------------------
# Sidebar: account
# --------------------------
st.sidebar.subheader("Account")
if st.sidebar.button("Sign out"):
    logout()
    clear_tasks_cache()
    st.rerun()

# --------------------------
# TABS: Manage vs Analytics
# --------------------------
tab_manage, tab_analytics = st.tabs(["📝 Manage Tasks", "📊 Analytics"])

# ═══════════════════════════════════════════════════════════
# TAB 1: MANAGE (CRUD workflow)
# ═══════════════════════════════════════════════════════════
with tab_manage:

    # Sidebar: Refresh button
    if st.sidebar.button("Refresh Tasks"):
        clear_tasks_cache()
        st.rerun()

    # Sidebar: Filter by Status
    st.sidebar.subheader("Filter by Status")
    status_options = ["completed", "needsAction"]
    selected_status = st.sidebar.multiselect("Status", status_options, default=status_options)
    df_filtered = df[df["status"].isin(selected_status)].copy()

    # ----- Editable table -----
    st.subheader("Tasks")
    df_display = df_filtered[["id", "title", "notes", "due", "status"]].copy()

    edited_df = st.data_editor(
        df_display,
        num_rows="dynamic",
        use_container_width=True,
    )

    # ----- Sidebar: select a task to edit -----
    st.sidebar.subheader("Edit Specific Task")
    if not df_display.empty:
        task_options = list(df_display["id"])
        selected_task_id = st.sidebar.selectbox(
            "Select task to edit",
            options=task_options,
            format_func=lambda x: df_display[df_display["id"] == x]["title"].values[0]
        )

        # Show editable fields for this specific task
        task_row = df_display[df_display["id"] == selected_task_id].iloc[0]

        new_title = st.sidebar.text_input("Title", value=task_row["title"])
        new_notes = st.sidebar.text_area("Notes", value=task_row.get("notes") or "")
        new_due = st.sidebar.date_input(
            "Due Date (optional)",
            value=task_row["due"].date() if pd.notna(task_row["due"]) else None
        )
        new_status = st.sidebar.selectbox(
            "Status",
            options=["needsAction", "completed"],
            index=0 if task_row["status"] == "needsAction" else 1
        )

        if st.sidebar.button("Update Selected Task"):
            due_iso = to_due_iso(new_due) if new_due else None
            try:
                update_task(
                    service,
                    tasklist_id,
                    selected_task_id,
                    title=new_title,
                    notes=new_notes,
                    due=due_iso,
                    status=new_status
                )
                st.success("Task updated!")
                clear_tasks_cache()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update task: {e}")

    # ----- Add new task -----
    st.subheader("Add New Task")
    with st.form("add_task_form"):
        new_title = st.text_input("Title")
        new_notes = st.text_area("Notes")
        new_due = st.date_input("Due Date (optional)")
        submitted = st.form_submit_button("Add Task")

        if submitted:
            due_iso = to_due_iso(new_due) if new_due else None
            if new_title:
                try:
                    add_task(service, tasklist_id, title=new_title, notes=new_notes, due=due_iso)
                    st.success("Task added!")
                    clear_tasks_cache()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add task: {e}")
            else:
                st.warning("Title is required to add a task.")

    # ----- Multi-select delete -----
    st.subheader("Delete Tasks")
    if not df_display.empty:
        delete_tasks = st.multiselect(
            "Select tasks to delete",
            options=list(df_display["id"]),
            format_func=lambda x: df_display[df_display["id"] == x]["title"].values[0]
        )

        if st.button("Delete Selected Tasks"):
            deleted_count = 0
            for task_id in delete_tasks:
                try:
                    delete_task(service, tasklist_id, task_id)
                    deleted_count += 1
                except Exception as e:
                    st.error(f"Failed to delete task ID {task_id}: {e}")

            st.success(f"Deleted {deleted_count} task(s).")
            clear_tasks_cache()
            st.rerun()

# ═══════════════════════════════════════════════════════════
# TAB 2: ANALYTICS
# ═══════════════════════════════════════════════════════════
with tab_analytics:

    # KPI row
    stats = compute_stats(df)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total tasks", stats["total_tasks"])
    k2.metric("Open", stats["open_tasks"])
    k3.metric("Closed", stats["closed_tasks"])
    k4.metric("Current streak", f"{stats['current_streak']}d")
    k5.metric("Best day", stats["best_day"])

    st.divider()

    # Settings in expander
    with st.expander("⚙️ Analytics settings"):
        col1, col2 = st.columns(2)
        with col1:
            weekly_goal = st.number_input("Weekly goal", 1, 50, 15)
            months_back = st.number_input("Months of history", 1, 24, 6)
        with col2:
            shame_n = st.number_input("Oldest tasks to show", 5, 20, 10)
            rolling_window = st.number_input("Rolling avg window", 2, 12, 4)

    st.subheader("📈 Motivation")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Weekly goal progress")
        st.plotly_chart(chart_weekly_goal_ring(df, weekly_goal), use_container_width=True)
    with c2:
        st.caption("Last 7 days velocity")
        st.plotly_chart(chart_velocity_sparkline(df), use_container_width=True)
    with c3:
        st.caption("Time of day (power hours)")
        st.plotly_chart(chart_time_of_day(df), use_container_width=True)

    st.caption("Cumulative tasks closed")
    st.plotly_chart(chart_cumulative(df), use_container_width=True)

    st.divider()
    st.subheader("🗑️ Backlog Health")
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"Oldest {shame_n} open tasks")
        st.plotly_chart(chart_oldest_open(df, shame_n), use_container_width=True)
    with c2:
        st.caption("Age distribution of open tasks")
        st.plotly_chart(chart_age_distribution(df), use_container_width=True)

    st.caption("Overdue tasks")
    st.plotly_chart(chart_overdue(df), use_container_width=True)

    st.divider()
    st.subheader("📅 Patterns & Trends")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Day of week pattern")
        st.plotly_chart(chart_day_of_week(df), use_container_width=True)
    with c2:
        st.caption("Month-over-month completions")
        st.plotly_chart(chart_month_over_month(df, months_back), use_container_width=True)

    st.caption(f"{rolling_window}-week rolling average")
    st.plotly_chart(chart_rolling_average(df, rolling_window), use_container_width=True)

    st.divider()
    st.caption(
        f"Last refresh: {datetime.now().strftime('%H:%M')} · "
        f"{len(df)} tasks in selected list · "
        "“age” is based on last-modified time (Google Tasks has no creation timestamp)"
    )
