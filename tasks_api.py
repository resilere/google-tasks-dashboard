"""
tasks_api.py
Thin wrapper around the Google Tasks API: build a service from credentials and
perform CRUD on tasks. Authentication lives in auth.py.
"""
from googleapiclient.discovery import build


def get_service(creds):
    """Build a Google Tasks API service from the given credentials."""
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
                "updated": t.get("updated"),
                # NOTE: the Google Tasks API does not expose a real creation time,
                # so "created" mirrors "updated". Analytics "age" is therefore based
                # on last-modified time, not true creation time (surfaced in the UI).
                "created": t.get("updated"),
                "list_title": tl_title,
                "list": tl_title,  # kept for backwards compatibility
                "list_id": tl_id,
                "parent": t.get("parent"),  # for subtask support in analytics
            })
    return all_tasks


# --------------------------
# Add new task
# --------------------------
def add_task(service, tasklist_id, title, notes=None, due=None, status=None):
    body = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = due
    if status:
        body["status"] = status
    return service.tasks().insert(tasklist=tasklist_id, body=body).execute()


# --------------------------
# Update existing task (only if fields changed)
# --------------------------
def update_task(service, tasklist_id, task_id, title=None, notes=None, due=None, status=None):
    if not task_id:
        return None

    body = {"id": task_id}
    if title:
        body["title"] = title
    if notes is not None:
        body["notes"] = notes
    if due:
        body["due"] = due
    if status is not None:
        body["status"] = status

    if len(body) == 1:  # only 'id' present, nothing to update
        return None

    return service.tasks().update(tasklist=tasklist_id, task=task_id, body=body).execute()


# --------------------------
# Delete a task
# --------------------------
def delete_task(service, tasklist_id, task_id):
    if not task_id:
        return None
    return service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
