import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import streamlit as st

SCOPES = ["https://www.googleapis.com/auth/tasks"]

# --------------------------
# Authentication / service
# --------------------------
def get_service():
    creds = None
    try:
        with open("token.pkl", "rb") as token_file:
            creds = pickle.load(token_file)
    except FileNotFoundError:
        pass

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.pkl", "wb") as token_file:
            pickle.dump(creds, token_file)

    return build("tasks", "v1", credentials=creds)

# --------------------------
# Fetch tasks
# --------------------------
def fetch_tasks(service):
    all_tasks = []
    tasklists = service.tasklists().list().execute()
    for tl in tasklists.get("items", []):
        tl_id = tl["id"]
        tl_title = tl.get("title", "")
        tasks = service.tasks().list(tasklist=tl_id, showHidden=True).execute()
        for t in tasks.get("items", []):
            all_tasks.append({
                "id": t.get("id"),
                "title": t.get("title"),
                "status": t.get("status"),
                "notes": t.get("notes"),
                "completed": t.get("completed"),
                "due": t.get("due"),
                "updated": t.get("updated"),  # Standard field name for analytics
                "created": t.get("updated"),  # Kept for backwards compatibility
                "list_title": tl_title,  # Standard name for analytics
                "list": tl_title,  # Kept for backwards compatibility
                "list_id": tl_id,
                "parent": t.get("parent"),  # For subtask support in analytics
            })
    return all_tasks

# --------------------------
# Cached fetch for Streamlit
# --------------------------
@st.cache_data(show_spinner=False)
def fetch_tasks_cached(creds):
    service = build("tasks", "v1", credentials=creds)
    return fetch_tasks(service)

# --------------------------
# Add new task
# --------------------------
def add_task(service, tasklist_id, title, notes=None, due=None, status=None):
    body = {"title": title}
    if notes: body["notes"] = notes
    if due: body["due"] = due
    if status: body["status"] = status
    print(f"Adding task to list {tasklist_id}: {body}")
    result = service.tasks().insert(tasklist=tasklist_id, body=body).execute()
    print(f"Add result: {result}")
    return result

# --------------------------
# Update existing task (only if fields changed)
# --------------------------
def update_task(service, tasklist_id, task_id, title=None, notes=None, due=None, status=None):
    print(f"--- update_task called ---")
    print(f"task_id: {task_id}")
    print(f"title: {title}, notes: {notes}, due: {due}, status: {status}")

    if not task_id:
        print("Skipping update: task_id missing")
        return None

    body = {"id": task_id}
    if title: body["title"] = title
    if notes is not None: body["notes"] = notes
    if due: body["due"] = due
    if status is not None: body["status"] = status

    if len(body) == 1:  # only 'id' present, nothing to update
        print("Skipping update: no fields changed")
        return None

    print(f"Updating task {task_id} with body: {body}")
    result = service.tasks().update(tasklist=tasklist_id, task=task_id, body=body).execute()
    print(f"Update result: {result}")
    return result

# --------------------------
# Delete a task
# --------------------------
def delete_task(service, tasklist_id, task_id):
    if not task_id:
        print("Skipping delete: task_id missing")
        return None
    print(f"Deleting task {task_id} from list {tasklist_id}")
    result = service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
    print(f"Delete result: {result}")
    return result