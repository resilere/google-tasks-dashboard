"""
app.py
Google Tasks Manager with an integrated analytics dashboard.

Auth is per-user (see auth.py): every visitor signs in with their own Google
account and their credentials + task data stay in their own session.
"""
import random

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from auth import get_credentials, logout
from tasks_api import (
    get_service, fetch_tasks, add_task, update_task, delete_task, list_tasklists,
)
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

tasklists = list_tasklists(service)
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


def _build_df(tasks):
    """Turn raw task dicts from fetch_tasks() into a normalized DataFrame."""
    if not tasks:
        return pd.DataFrame(
            columns=["id", "title", "notes", "due", "status", "completed",
                     "updated", "list_title", "list_id", "parent"]
        )
    df = pd.DataFrame(tasks)
    required_cols = ["id", "title", "notes", "due", "status", "completed",
                     "updated", "list_title", "list_id", "parent"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = pd.NaT if col in ("due", "completed", "updated") else None
    df["due"] = df["due"].apply(_to_tz_naive)
    df["completed"] = df["completed"].apply(_to_tz_naive)
    df["updated"] = df["updated"].apply(_to_tz_naive)
    return df


def load_all_tasks(force: bool = False):
    """
    Load tasks across ALL lists, cached per-session in st.session_state.

    NOTE: we deliberately cache in session_state (per browser session) rather than
    st.cache_data (shared across ALL users) so one visitor's tasks never leak into
    another visitor's view when the app is public.
    """
    cache = st.session_state.setdefault("_tasks_cache", {})
    if not force and "__all__" in cache:
        return cache["__all__"]
    df = _build_df(fetch_tasks(service))
    cache["__all__"] = df
    return df


def load_tasks(force: bool = False):
    """Tasks for the currently selected list (derived from the all-lists load)."""
    all_df = load_all_tasks(force)
    if all_df.empty:
        return all_df
    return all_df[all_df["list_id"] == tasklist_id].copy()


def clear_tasks_cache():
    st.session_state.pop("_tasks_cache", None)


def pick_focus_tasks(open_df, n, favor_long_open, seed):
    """
    Weighted-random selection of open tasks. When favor_long_open is True, a task's
    probability is proportional to how long it has been open (age_days), so tasks
    that have lingered the longest surface more often. Returns them sorted by
    days-open (longest first).
    """
    idx = open_df.index.to_numpy()
    n = min(int(n), len(idx))
    if n == 0:
        return open_df.iloc[0:0]
    rng = np.random.default_rng(seed)
    if favor_long_open:
        weights = open_df["age_days"].fillna(0).clip(lower=0).to_numpy(dtype=float) + 1.0
        probs = weights / weights.sum()
        chosen = rng.choice(idx, size=n, replace=False, p=probs)
    else:
        chosen = rng.choice(idx, size=n, replace=False)
    return open_df.loc[chosen].sort_values("age_days", ascending=False)


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
# TABS: Manage vs Focus vs Analytics
# --------------------------
tab_manage, tab_focus, tab_analytics = st.tabs(
    ["📝 Manage Tasks", "🎯 Focus", "📊 Analytics"]
)

# ═══════════════════════════════════════════════════════════
# TAB 1: MANAGE (CRUD workflow)
# ═══════════════════════════════════════════════════════════
with tab_manage:

    # Sidebar: Refresh button
    if st.sidebar.button("Refresh Tasks"):
        clear_tasks_cache()
        st.rerun()

    # Sidebar: which tasks to show (open by default — completed are hidden)
    st.sidebar.subheader("Show")
    view_choice = st.sidebar.radio(
        "Tasks to show", ["Open", "Completed", "All"], index=0, key="status_view"
    )
    if view_choice == "Open":
        df_filtered = df[df["status"] == "needsAction"].copy()
    elif view_choice == "Completed":
        df_filtered = df[df["status"] == "completed"].copy()
    else:
        df_filtered = df.copy()

    # Kept for the sidebar single-task editor and the delete section below.
    df_display = df_filtered[["id", "title", "notes", "due", "status"]].copy()

    # ----- Editable table (checkbox = done; inline edits save via the button) -----
    st.subheader("Tasks")
    if df_filtered.empty:
        st.info("No tasks to show. Try a different filter, or add one below.")
    else:
        editor_view = df_filtered.set_index("id")[["status", "title", "notes", "due"]].copy()
        editor_view.insert(0, "done", editor_view["status"] == "completed")
        editor_view = editor_view.drop(columns=["status"])

        edited = st.data_editor(
            editor_view,
            column_config={
                "done": st.column_config.CheckboxColumn("Done", width="small"),
                "title": st.column_config.TextColumn("Task", width="large", required=True),
                "notes": st.column_config.TextColumn("Notes", width="medium"),
                "due": st.column_config.DateColumn("Due", format="YYYY-MM-DD", width="small"),
            },
            use_container_width=True,
            num_rows="fixed",
            hide_index=True,
            key="task_editor",
        )

        if st.button("💾 Save changes", type="primary"):
            def _as_date(v):
                return None if v is None or pd.isna(v) else pd.Timestamp(v).date()

            changed = 0
            for tid in edited.index:
                new, old = edited.loc[tid], editor_view.loc[tid]
                updates = {}

                new_title = (new["title"] or "").strip()
                if new_title and new_title != (old["title"] or ""):
                    updates["title"] = new_title

                new_notes = "" if new["notes"] is None else str(new["notes"])
                old_notes = "" if old["notes"] is None else str(old["notes"])
                if new_notes != old_notes:
                    updates["notes"] = new_notes

                new_due, old_due = _as_date(new["due"]), _as_date(old["due"])
                if new_due != old_due and new_due is not None:
                    updates["due"] = to_due_iso(new_due)

                new_status = "completed" if bool(new["done"]) else "needsAction"
                if new_status != ("completed" if bool(old["done"]) else "needsAction"):
                    updates["status"] = new_status

                if updates:
                    try:
                        update_task(service, tasklist_id, tid, **updates)
                        changed += 1
                    except Exception as e:
                        st.error(f"Failed to update “{old['title']}”: {e}")

            if changed:
                st.success(f"Saved {changed} change(s).")
                clear_tasks_cache()
                st.rerun()
            else:
                st.info("No changes to save.")

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
# TAB 2: FOCUS (weighted-random picker across ALL lists)
# ═══════════════════════════════════════════════════════════
with tab_focus:
    st.subheader("🎯 Focus — what should I tackle now?")
    st.caption(
        "A weighted-random pick from your open tasks across **all** lists, biased "
        "toward the ones that have stayed open the longest."
    )

    focus_df = transform(load_all_tasks())
    open_all = (
        focus_df[focus_df["status"] == "needsAction"].copy()
        if not focus_df.empty else focus_df
    )

    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 1])
    with ctrl1:
        n_picks = st.number_input("How many tasks", min_value=1, max_value=10, value=3, key="focus_n")
    with ctrl2:
        favor_long = st.toggle("Favor long-open tasks", value=True, key="focus_favor")
    with ctrl3:
        st.write("")  # vertical alignment
        if st.button("🎲 Randomize", key="focus_shuffle", use_container_width=True):
            st.session_state["focus_seed"] = random.randrange(2**32)
            st.rerun()

    seed = st.session_state.setdefault("focus_seed", random.randrange(2**32))

    if open_all.empty:
        st.success("🎉 No open tasks anywhere — you're at inbox zero!")
    else:
        st.caption(f"Choosing from {len(open_all)} open tasks across all lists.")
        picks = pick_focus_tasks(open_all, n_picks, favor_long, seed)

        for _, row in picks.iterrows():
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"### {row['title'] or '(untitled)'}")
                    st.caption(f"📂 {row['list_title'] or 'Unknown list'}")
                    due = row.get("due")
                    overdue = row.get("days_overdue")
                    if pd.notna(due):
                        if pd.notna(overdue) and overdue > 0:
                            st.markdown(f":red[⚠️ {int(overdue)} days overdue] · due {due.date()}")
                        else:
                            st.markdown(f"📅 Due {due.date()}")
                    notes = row.get("notes")
                    if notes:
                        st.caption(str(notes)[:200])
                with right:
                    age = row.get("age_days")
                    st.metric("Days open", int(age) if pd.notna(age) else "—")
                    if st.button("✓ Done", key=f"focus_done_{row['id']}", use_container_width=True):
                        try:
                            update_task(service, row["list_id"], row["id"], status="completed")
                            clear_tasks_cache()
                            st.toast("Marked done ✓")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to complete: {e}")

        st.caption(
            "“Days open” = days since the task was last modified (Google Tasks has no "
            "creation timestamp)."
        )

# ═══════════════════════════════════════════════════════════
# TAB 3: ANALYTICS
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
