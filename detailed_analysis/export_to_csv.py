"""
export_to_csv.py
Export Google Tasks to CSV for Notion import.

Usage:
    python export_to_csv.py
    
This will create a CSV file for each task list in your Google Tasks.
Example output: tasks_export_2024-03-23.csv
"""

import os
import sys
import pickle
import pandas as pd
from datetime import datetime
from pathlib import Path

# This is a LOCAL-ONLY CLI helper (not part of the deployed web app). It imports the
# shared fetch_tasks() from the repo root and does its own local desktop-style OAuth.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tasks_api import fetch_tasks  # noqa: E402
from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/tasks"]


def get_local_service():
    """Local CLI auth via a Desktop OAuth client (client_secret.json + token.pkl)."""
    creds = None
    if os.path.exists("token.pkl"):
        with open("token.pkl", "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.pkl", "wb") as f:
            pickle.dump(creds, f)
    return build("tasks", "v1", credentials=creds)

# ─────────────────────────────────────────────────────────────
# CSV EXPORT CONFIGURATION
# ─────────────────────────────────────────────────────────────

# Choose which columns to export (in order)
EXPORT_COLUMNS = [
    "title",
    "status",
    "notes",
    "due",
    "completed",
    "list_title",
]

# Friendly column names for Notion (optional renaming)
COLUMN_MAPPING = {
    "title": "Title",
    "status": "Status",
    "notes": "Notes",
    "due": "Due Date",
    "completed": "Completed Date",
    "list_title": "List",
}


def normalize_datetime(dt):
    """Convert datetime to readable format for Notion import."""
    if pd.isna(dt):
        return ""
    if isinstance(dt, str):
        return dt
    # Format as YYYY-MM-DD for Notion
    return dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)


def export_tasks_to_csv(list_title=None):
    """
    Export Google Tasks to CSV file.
    
    Args:
        list_title: If provided, export only this list. Otherwise export all.
    
    Returns:
        Path to the created CSV file
    """
    print("🔄 Fetching tasks from Google Tasks...")
    service = get_local_service()
    all_tasks = fetch_tasks(service)
    
    # Filter by list if specified
    if list_title:
        all_tasks = [t for t in all_tasks if t["list_title"] == list_title]
        print(f"📋 Found {len(all_tasks)} tasks in list: {list_title}")
    else:
        print(f"📋 Found {len(all_tasks)} tasks across all lists")
    
    if not all_tasks:
        print("❌ No tasks found!")
        return None
    
    # Create DataFrame
    df = pd.DataFrame(all_tasks)
    
    # Select only columns to export
    export_cols = [col for col in EXPORT_COLUMNS if col in df.columns]
    df = df[export_cols]
    
    # Rename columns for Notion
    df.columns = [COLUMN_MAPPING.get(col, col) for col in df.columns]
    
    # Normalize datetime columns
    for col in ["Due Date", "Completed Date"]:
        if col in df.columns:
            df[col] = df[col].apply(normalize_datetime)
    
    # Convert "Status" to human-readable format
    if "Status" in df.columns:
        df["Status"] = df["Status"].map({
            "completed": "✅ Completed",
            "needsAction": "⏳ Open",
        }).fillna(df["Status"])
    
    # Create filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if list_title:
        filename = f"tasks_export_{list_title}_{timestamp}.csv"
    else:
        filename = f"tasks_export_all_{timestamp}.csv"
    
    filepath = Path(filename)
    
    # Write to CSV
    df.to_csv(filepath, index=False, encoding="utf-8")
    print(f"✅ Exported to: {filepath}")
    print(f"📊 Total rows: {len(df)}")
    print(f"📋 Columns: {', '.join(df.columns)}")
    
    return filepath


def export_all_lists():
    """Export each list to a separate CSV file."""
    print("🔄 Fetching all task lists...")
    service = get_local_service()
    tasklists = service.tasklists().list().execute()
    
    all_tasks = fetch_tasks(service)
    unique_lists = set([t["list_title"] for t in all_tasks])
    
    print(f"📋 Found {len(unique_lists)} lists:")
    
    files = []
    for list_title in sorted(unique_lists):
        print(f"\n  📤 Exporting: {list_title}")
        filepath = export_tasks_to_csv(list_title=list_title)
        if filepath:
            files.append(filepath)
    
    print(f"\n✅ All exports complete! {len(files)} files created.")
    print("\n📂 Files created:")
    for f in files:
        print(f"   • {f}")
    
    return files


def preview_csv(filepath):
    """Preview the CSV file before uploading to Notion."""
    print(f"\n📊 Preview of {filepath}:")
    print("=" * 80)
    df = pd.read_csv(filepath)
    print(df.to_string(index=False))
    print("=" * 80)
    print(f"\n✅ Ready to import to Notion!")
    print(f"📈 Total rows: {len(df)}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("📋 Google Tasks → CSV Exporter")
    print("=" * 80)
    
    if len(sys.argv) > 1:
        # Export specific list: python export_to_csv.py "List Name"
        list_name = " ".join(sys.argv[1:])
        print(f"\n🎯 Exporting list: {list_name}\n")
        filepath = export_tasks_to_csv(list_title=list_name)
        if filepath:
            preview_csv(filepath)
    else:
        # Export all lists
        print("\n📤 Exporting all task lists...\n")
        export_all_lists()
    
    print("\n" + "=" * 80)
    print("🚀 Next: Import CSV to Notion (see NOTION_IMPORT_GUIDE.md)")
    print("=" * 80)