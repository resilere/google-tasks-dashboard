"""
analytics.py
Chart functions for task analytics using Plotly.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from transform import open_tasks, closed_tasks


COLORS = {
    "teal": "#1D9E75",
    "blue": "#378ADD",
    "purple": "#7F77DD",
    "amber": "#EF9F27",
    "coral": "#D85A30",
    "red": "#E24B4A",
    "gray": "#B4B2A9",
}


# ── MOTIVATION ───────────────────────────────────────────
def chart_weekly_goal_ring(df, weekly_goal: int = 15):
    """Gauge chart showing progress toward weekly goal."""
    today = pd.Timestamp.now().normalize()
    mon = today - timedelta(days=today.weekday())
    n = len(closed_tasks(df)[closed_tasks(df)["completed"] >= mon])
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=n,
        gauge=dict(
            axis=dict(range=[0, weekly_goal]),
            bar=dict(color=COLORS["teal"]),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[dict(range=[0, weekly_goal], color="#E1F5EE")],
        ),
        title=dict(text=f"weekly goal: {weekly_goal}"),
        number=dict(suffix=f" / {weekly_goal}"),
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=40, b=20))
    return fig


def chart_velocity_sparkline(df):
    """Last 7 days completion count."""
    closed = closed_tasks(df)
    last7 = [(pd.Timestamp.now().normalize() - timedelta(days=i)).normalize() for i in range(6, -1, -1)]
    daily = closed.groupby("comp_date").size()
    counts = [daily.get(d, 0) for d in last7]
    labels = [d.strftime("%a") for d in last7]
    
    fig = px.bar(
        x=labels, y=counts,
        color=[COLORS["teal"] if c >= 1 else "#E1F5EE" for c in counts],
        color_discrete_map="identity"
    )
    fig.update_layout(
        height=120, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        xaxis=dict(showgrid=False), yaxis=dict(visible=False)
    )
    return fig


def chart_cumulative(df):
    """Cumulative tasks completed over time."""
    closed = closed_tasks(df).dropna(subset=["completed"]).sort_values("completed")
    if closed.empty:
        return go.Figure().update_layout(title="No completed tasks yet")
    
    closed = closed.copy()
    closed["cumul"] = range(1, len(closed) + 1)
    fig = px.line(
        closed, x="completed", y="cumul",
        labels={"cumul": "Total closed"},
        color_discrete_sequence=[COLORS["teal"]]
    )
    fig.update_traces(fill="tozeroy", fillcolor="rgba(29,158,117,0.08)")
    fig.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0))
    return fig


# ── BACKLOG HEALTH ───────────────────────────────────────
def chart_oldest_open(df, n: int = 10):
    """Bar chart of oldest open tasks."""
    open_df = open_tasks(df).nlargest(n, "age_days")[["title", "age_days"]].copy()
    if open_df.empty:
        return go.Figure().update_layout(title="No open tasks!")
    
    colors = [
        COLORS["red"] if a > 60 else (COLORS["coral"] if a > 30 else COLORS["amber"])
        for a in open_df["age_days"]
    ]
    fig = px.bar(
        open_df, x="age_days", y="title", orientation="h",
        color=open_df["age_days"],
        color_continuous_scale=["#EF9F27", "#D85A30", "#E24B4A"],
        labels={"age_days": "Days open", "title": ""}
    )
    fig.update_layout(
        height=max(300, n * 36), margin=dict(l=10, r=40, t=10, b=0),
        coloraxis_showscale=False, yaxis=dict(autorange="reversed")
    )
    return fig


def chart_age_distribution(df):
    """Distribution of open task ages."""
    open_df = open_tasks(df).copy()
    if open_df.empty:
        return go.Figure().update_layout(title="No open tasks!")
    
    bins = [0, 7, 14, 30, 60, 90, 9999]
    labels = ["0–7d", "8–14d", "15–30d", "31–60d", "61–90d", "90d+"]
    open_df["bucket"] = pd.cut(open_df["age_days"], bins=bins, labels=labels, right=True)
    counts = open_df["bucket"].value_counts()[labels]
    
    fig = px.bar(
        x=labels, y=counts.values,
        color=labels,
        color_discrete_sequence=["#9FE1CB", "#5DCAA5", "#1D9E75", "#EF9F27", "#D85A30", "#E24B4A"],
        labels={"x": "Age bucket", "y": "Open tasks"}
    )
    fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
    return fig


def chart_overdue(df):
    """Tasks overdue by how many days."""
    over = open_tasks(df).dropna(subset=["days_overdue"])
    over = over[over["days_overdue"] > 0].nlargest(10, "days_overdue")
    
    if over.empty:
        return go.Figure().update_layout(title="No overdue tasks!")
    
    fig = px.bar(
        over, x="days_overdue", y="title", orientation="h",
        color="days_overdue", color_continuous_scale=["#FAEEDA", "#E24B4A"],
        labels={"days_overdue": "Days overdue", "title": ""}
    )
    fig.update_layout(
        height=max(200, len(over) * 36), margin=dict(l=10, r=40, t=10, b=0),
        coloraxis_showscale=False, yaxis=dict(autorange="reversed")
    )
    return fig


# ── PATTERNS ─────────────────────────────────────────────
def chart_day_of_week(df):
    """Tasks completed by day of week."""
    closed = closed_tasks(df).dropna(subset=["comp_dow"])
    dow = closed.groupby("comp_dow").size().reindex(range(7), fill_value=0)
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    fig = px.bar(
        x=labels, y=dow.values,
        labels={"x": "", "y": "Tasks closed"},
        color=dow.values,
        color_continuous_scale=["#E1F5EE", "#1D9E75"]
    )
    fig.update_layout(
        height=200, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False, coloraxis_showscale=False
    )
    return fig


def chart_time_of_day(df):
    """Tasks completed by hour of day."""
    closed = closed_tasks(df).dropna(subset=["comp_hour"])
    if closed.empty:
        return go.Figure().update_layout(title="No completion time data")
    
    hourly = closed.groupby("comp_hour").size().reindex(range(24), fill_value=0)
    fig = px.bar(
        x=hourly.index, y=hourly.values,
        labels={"x": "Hour of day", "y": "Tasks completed"},
        color=hourly.values,
        color_continuous_scale=["#E1F5EE", "#1D9E75"]
    )
    fig.update_layout(
        height=220, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False, coloraxis_showscale=False
    )
    return fig


# ── TRENDS ──────────────────────────────────────────────
def chart_month_over_month(df, months_back: int = 6):
    """Tasks completed month-by-month."""
    closed = closed_tasks(df).dropna(subset=["comp_month"])
    if closed.empty:
        return go.Figure().update_layout(title="No completion data")
    
    cutoff = (pd.Timestamp.now() - pd.DateOffset(months=months_back)).to_period("M").strftime("%Y-%m")
    monthly = closed[closed["comp_month"] >= cutoff].groupby("comp_month").size().reset_index(name="closed")
    
    fig = px.bar(
        monthly, x="comp_month", y="closed",
        color_discrete_sequence=[COLORS["teal"]],
        labels={"comp_month": "Month", "closed": "Tasks closed"}
    )
    fig.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=0))
    return fig


def chart_rolling_average(df, window: int = 4):
    """Weekly completion with rolling average."""
    closed = closed_tasks(df).dropna(subset=["comp_week"])
    if closed.empty:
        return go.Figure().update_layout(title="No completion data")
    
    weekly = closed.groupby("comp_week").size().reset_index(name="count").sort_values("comp_week")
    weekly["rolling"] = weekly["count"].rolling(window, min_periods=1).mean().round(1)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["comp_week"], y=weekly["count"],
        marker_color="rgba(29,158,117,0.25)", name="Weekly"
    ))
    fig.add_trace(go.Scatter(
        x=weekly["comp_week"], y=weekly["rolling"],
        line=dict(color=COLORS["teal"], width=2.5),
        mode="lines", name=f"{window}-wk avg"
    ))
    fig.update_layout(
        height=230, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", y=-0.15), barmode="overlay"
    )
    return fig


# ── SUMMARY METRICS ──────────────────────────────────────
def compute_stats(df):
    """Return dict of key stats."""
    closed = closed_tasks(df)
    daily = closed.groupby("comp_date").size()
    weekly = closed.groupby("comp_week").size()
    
    # Streak calculation
    streak = 0
    check = pd.Timestamp.now().normalize()
    while True:
        if daily.get(check, 0) >= 1:
            streak += 1
            check -= timedelta(days=1)
        else:
            break
    
    return {
        "total_tasks": len(df),
        "open_tasks": len(open_tasks(df)),
        "closed_tasks": len(closed),
        "best_day": int(daily.max()) if not daily.empty else 0,
        "best_week": int(weekly.max()) if not weekly.empty else 0,
        "current_streak": streak,
    }