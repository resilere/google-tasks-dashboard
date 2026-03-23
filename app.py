import streamlit as st
import pandas as pd
from datetime import datetime
from tasks_api import get_service, fetch_tasks, add_task, update_task, delete_task

st.title("Google Tasks Manager")

# --------------------------
# Initialize Google Tasks service
# --------------------------
service = get_service()

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

def load_tasks():
    tasks = fetch_tasks(service)
    # Filter tasks by the selected list
    tasks = [t for t in tasks if t["list_id"] == tasklist_id]
    df = pd.DataFrame(tasks)
    if df.empty:
        df = pd.DataFrame(columns=["id", "title", "notes", "due", "status", "completed"])
    else:
        df["due"] = pd.to_datetime(df["due"], errors="coerce")
        df["completed"] = pd.to_datetime(df["completed"], errors="coerce")
    return df

df = load_tasks()

# --------------------------
# Sidebar: Refresh button
# --------------------------
if st.sidebar.button("Refresh Tasks"):
    df = load_tasks()

# --------------------------
# Sidebar: Filter by Status
# --------------------------
st.sidebar.subheader("Filter by Status")
status_options = ["completed", "needsAction"]
selected_status = st.sidebar.multiselect("Status", status_options, default=status_options)
df_filtered = df[df["status"].isin(selected_status)].copy()

# --------------------------
# Editable table
# --------------------------
st.subheader("Tasks")
df_display = df_filtered[["id", "title", "notes", "due", "status"]].copy()

edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
)


# Sidebar: select a task to edit
st.sidebar.subheader("Edit Specific Task")
task_options = list(df_display["id"])
selected_task_id = st.sidebar.selectbox(
    "Select task to edit",
    options=task_options,
    format_func=lambda x: df_display[df_display["id"]==x]["title"].values[0]
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
    index=0 if task_row["status"]=="needsAction" else 1
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
        df = load_tasks()  # refresh table
    except Exception as e:
        st.error(f"Failed to update task: {e}")
# --------------------------
# Add new task
# --------------------------
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
                df = load_tasks()
            except Exception as e:
                st.error(f"Failed to add task: {e}")
        else:
            st.warning("Title is required to add a task.")

# --------------------------
# Multi-select delete
# --------------------------
st.subheader("Delete Tasks")
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
    df = load_tasks()