"""8D tracker: D0 to D8 progress stepper and planned-versus-actual timeline.

Pure functions (no Streamlit calls) come first so they can be unit-tested; the page is at the bottom.
Custom diagrams use a white card background and explicit text colours so they read the same in light and dark themes.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, RED, editor, plot, report_issues, sample_data_note, table

STEP_IDS = [f"D{i}" for i in range(9)]
STEP_NAMES = {
    "D0": "Prepare / emergency response", "D1": "Establish the team", "D2": "Describe the problem",
    "D3": "Interim containment", "D4": "Root cause and escape point", "D5": "Choose permanent corrective action",
    "D6": "Implement and validate", "D7": "Prevent recurrence", "D8": "Close and recognize the team",
}
STEP_SHORT = {"D0": "Prepare", "D1": "Team", "D2": "Problem", "D3": "Contain", "D4": "Root<br>cause", "D5": "Corrective<br>action",
              "D6": "Implement", "D7": "Prevent", "D8": "Close"}
STATUSES = ["Not started", "In progress", "Done", "Blocked"]
STEP_COLS = ["Step", "Status", "Planned date", "Completed date", "Notes"]
CLEAN_COLS = ["Step", "Name", "Status", "Planned", "Completed", "Notes"]
INK, MUTED = "#1a1a1a", "#4a4a4a"
PAD = "\u00a0\u00a0\u00a0"  # keeps timeline labels clear of the markers
OK_TEXT, WARN_TEXT, BAD_TEXT = "#1b5e20", "#b34700", "#b71c1c"
STATUS_STYLE = {  # fill, text colour on the marker, border
    "Done": (GREEN, "#ffffff", GREEN),
    "In progress": (BLUE, "#ffffff", BLUE),
    "Blocked": (RED, "#ffffff", RED),
    "Not started": ("#ffffff", INK, "#8a8f98"),
}
SAMPLE_TITLE = "Oversize bores reported by a customer (simulated example)"
SAMPLE_OPENED = dt.date(2026, 9, 1)
SAMPLE_AS_OF = dt.date(2026, 10, 28)

METHOD_NOTE = (
    "8D is a structured problem-solving report, usually requested after a customer complaint or a significant internal "
    "failure. Step names vary between organizations; this tool uses D0 Prepare, D1 Team, D2 Problem description, D3 Interim "
    "containment, D4 Root cause, D5 Permanent corrective action, D6 Implementation and validation, D7 Prevent recurrence, "
    "D8 Close. Planned dates are entered by you; the tool compares them with completion dates and the 'status as of' date."
)


# ---------------------------------------------------------------------------
# Sample data (simulated, generic)
# ---------------------------------------------------------------------------
def sample_steps() -> pd.DataFrame:
    d = dt.date
    rows = [
        ("D0", "Done", d(2026, 9, 1), d(2026, 9, 1), "Complaint received; 8D opened."),
        ("D1", "Done", d(2026, 9, 2), d(2026, 9, 2), "Cross-functional team named."),
        ("D2", "Done", d(2026, 9, 4), d(2026, 9, 4), "Bore diameter oversize on 12 of 50 parts in the returned lot."),
        ("D3", "Done", d(2026, 9, 4), d(2026, 9, 5), "100% bore inspection before shipping; suspect lot quarantined."),
        ("D4", "Done", d(2026, 9, 18), d(2026, 9, 22), "Tool-life counter not reset at changeover (see 5 Why)."),
        ("D5", "Done", d(2026, 9, 30), d(2026, 9, 29), "Add counter reset to the changeover checklist."),
        ("D6", "In progress", d(2026, 10, 20), None, "Checklist revision in review."),
        ("D7", "Not started", d(2026, 11, 10), None, ""),
        ("D8", "Not started", d(2026, 11, 20), None, ""),
    ]
    return pd.DataFrame(rows, columns=STEP_COLS)


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------
def _is_blank(value) -> bool:
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        return False
    return isinstance(value, str) and not value.strip()


def _text(value) -> str:
    return "" if _is_blank(value) else " ".join(str(value).split())


def to_date(value) -> pd.Timestamp:
    if _is_blank(value):
        return pd.NaT
    try:
        ts = pd.to_datetime(value, errors="coerce")
    except (TypeError, ValueError, OverflowError):
        return pd.NaT
    return pd.NaT if pd.isna(ts) else pd.Timestamp(ts).normalize()


def normalise_step(value) -> str | None:
    """'D3', 'd3', '3', 'D3 - Containment' -> 'D3'. Anything else -> None."""
    m = re.match(r"^\s*d?\s*([0-8])(?!\d)", _text(value).lower())
    return f"D{m.group(1)}" if m else None


def normalise_status(value) -> str | None:
    key = " ".join(_text(value).lower().replace("_", " ").replace("-", " ").split())
    aliases = {"not started": "Not started", "todo": "Not started", "open": "Not started", "in progress": "In progress",
               "doing": "In progress", "wip": "In progress", "done": "Done", "complete": "Done", "completed": "Done",
               "closed": "Done", "blocked": "Blocked", "on hold": "Blocked", "stuck": "Blocked"}
    return aliases.get(key)


def clean_steps(raw) -> tuple[pd.DataFrame, list[str]]:
    """Return a fixed nine-row D0 to D8 table. Steps missing from the input are Not started.

    Reported: unknown step labels (row excluded), repeated steps (the last row is used), unrecognised status
    (treated as Not started), unreadable dates (ignored), completed dates on steps that are not Done (ignored).
    """
    issues: list[str] = []
    by_step: dict[str, dict] = {}
    if isinstance(raw, pd.DataFrame) and not raw.empty:
        for pos, rec in enumerate(raw.to_dict("records"), start=1):
            step_raw = rec.get("Step")
            vals = [rec.get(c) for c in STEP_COLS]
            if all(_is_blank(v) for v in vals):
                continue
            step = normalise_step(step_raw)
            if step is None:
                issues.append(f"Row {pos}: step '{_text(step_raw)}' is not D0 to D8. Row excluded.")
                continue
            if step in by_step:
                issues.append(f"{step} appears more than once. The last row is used.")
            status = "Not started" if _is_blank(rec.get("Status")) else normalise_status(rec.get("Status"))
            if status is None:
                issues.append(f"{step}: status '{_text(rec.get('Status'))}' not recognised. Treated as Not started.")
                status = "Not started"
            planned, completed = to_date(rec.get("Planned date")), to_date(rec.get("Completed date"))
            if pd.isna(planned) and not _is_blank(rec.get("Planned date")):
                issues.append(f"{step}: planned date not readable. Ignored.")
            if pd.isna(completed) and not _is_blank(rec.get("Completed date")):
                issues.append(f"{step}: completed date not readable. Ignored.")
            if status != "Done" and not pd.isna(completed):
                issues.append(f"{step}: completed date ignored because the status is not Done.")
                completed = pd.NaT
            by_step[step] = {"Status": status, "Planned": planned, "Completed": completed, "Notes": _text(rec.get("Notes"))}
    rows = []
    for step in STEP_IDS:
        info = by_step.get(step, {"Status": "Not started", "Planned": pd.NaT, "Completed": pd.NaT, "Notes": ""})
        rows.append({"Step": step, "Name": STEP_NAMES[step], **info})
    df = pd.DataFrame(rows)
    df["Planned"] = pd.to_datetime(df["Planned"])
    df["Completed"] = pd.to_datetime(df["Completed"])
    return df[CLEAN_COLS], issues


# ---------------------------------------------------------------------------
# Schedule logic
# ---------------------------------------------------------------------------
def with_schedule(df: pd.DataFrame, as_of) -> pd.DataFrame:
    """Add Overdue (not Done, planned date before as_of), Days late (Done: completed - planned; overdue: as_of - planned)."""
    out = df.copy()
    as_of = pd.Timestamp(as_of).normalize()
    done = out["Status"] == "Done"
    overdue = (~done) & out["Planned"].notna() & (out["Planned"] < as_of)
    days = pd.Series([float("nan")] * len(out), index=out.index)
    both = done & out["Planned"].notna() & out["Completed"].notna()
    days[both] = (out.loc[both, "Completed"] - out.loc[both, "Planned"]).dt.days
    days[overdue] = (as_of - out.loc[overdue, "Planned"]).dt.days
    out["Overdue"] = overdue
    out["Days late"] = days
    return out


def current_step(df: pd.DataFrame) -> str | None:
    pending = df[df["Status"] != "Done"]
    return None if pending.empty else str(pending["Step"].iloc[0])


def days_open(df: pd.DataFrame, opened, as_of) -> int:
    """Days from opened to the D8 completion date if closed, otherwise to as_of. Never negative."""
    opened, as_of = pd.Timestamp(opened).normalize(), pd.Timestamp(as_of).normalize()
    closed = df.loc[df["Step"] == "D8"]
    end = as_of
    if len(closed) and closed["Status"].iloc[0] == "Done" and closed["Completed"].notna().iloc[0]:
        end = closed["Completed"].iloc[0]
    return max(int((end - opened).days), 0)


def sequence_notes(df: pd.DataFrame, opened, as_of) -> list[str]:
    """Advisory checks. These do not change the data."""
    notes: list[str] = []
    opened, as_of = pd.Timestamp(opened).normalize(), pd.Timestamp(as_of).normalize()
    if as_of < opened:
        notes.append("The 'status as of' date is before the opened date.")
    first_gap = None
    for _, r in df.iterrows():
        if r["Status"] != "Done" and first_gap is None:
            first_gap = r["Step"]
        elif r["Status"] == "Done" and first_gap is not None:
            notes.append(f"{r['Step']} is Done but {first_gap} is not. Check the order of work.")
            break
    done = df[df["Status"] == "Done"]
    for _, r in done.iterrows():
        if pd.isna(r["Completed"]):
            notes.append(f"{r['Step']} is Done with no completed date; it is left off the timeline.")
        elif r["Completed"] < opened:
            notes.append(f"{r['Step']} completed date is before the opened date.")
    prev = None
    for _, r in done.iterrows():
        if prev is not None and pd.notna(r["Completed"]) and pd.notna(prev["Completed"]) and r["Completed"] < prev["Completed"]:
            notes.append(f"{r['Step']} was completed before {prev['Step']}. Check the dates.")
        if pd.notna(r["Completed"]):
            prev = r
    return notes


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _card(fig: go.Figure) -> go.Figure:
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="white", font={"color": INK})
    # Streamlit's dark theme sets tick and title font colours on each axis, which override axis.color.
    fig.update_xaxes(color=INK, tickfont={"color": INK}, title_font={"color": INK})
    fig.update_yaxes(color=INK, tickfont={"color": INK}, title_font={"color": INK})
    return fig


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def build_stepper_fig(df: pd.DataFrame, as_of) -> go.Figure:
    sched = with_schedule(df, as_of)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 8], y=[0, 0], mode="lines", line={"color": "#c4c8cf", "width": 4}, hoverinfo="skip",
                             showlegend=False))
    over = sched[sched["Overdue"]]
    if len(over):
        fig.add_trace(go.Scatter(x=[STEP_IDS.index(s) for s in over["Step"]], y=[0] * len(over), mode="markers",
                                 name="Overdue", marker={"size": 58, "symbol": "circle-open", "color": ORANGE,
                                                         "line": {"width": 4, "color": ORANGE}}, hoverinfo="skip"))
    for status in STATUSES:
        sub = sched[sched["Status"] == status]
        if sub.empty:
            continue
        fill, txt, border = STATUS_STYLE[status]
        fig.add_trace(go.Scatter(
            x=[STEP_IDS.index(s) for s in sub["Step"]], y=[0] * len(sub), mode="markers+text", name=status,
            text=[f"<b>{s}</b>" for s in sub["Step"]], textposition="middle center", textfont={"size": 13, "color": txt},
            marker={"size": 44, "color": fill, "line": {"width": 3, "color": border}},
            hovertext=[f"{r['Step']} {r['Name']}<br>{r['Status']}" for _, r in sub.iterrows()], hoverinfo="text"))
    status_color = {"Done": OK_TEXT, "In progress": "#0d47a1", "Blocked": BAD_TEXT, "Not started": MUTED}
    for _, r in sched.iterrows():
        due = f"<br>due {pd.Timestamp(r['Planned']).strftime('%b %d')}" if pd.notna(r["Planned"]) else ""
        label = f"<b>{STEP_SHORT[r['Step']]}</b>"
        fig.add_annotation(x=STEP_IDS.index(r["Step"]), y=-0.45, yanchor="top", showarrow=False, align="center",
                           text=f"{label}<br><span style='color:{status_color[r['Status']]}'>{r['Status']}</span>"
                                f"<span style='color:{MUTED}'>{due}</span>", font={"size": 11, "color": INK})
    fig.update_xaxes(visible=False, range=[-0.6, 8.6])
    fig.update_yaxes(visible=False, range=[-2.0, 0.7])
    fig.update_layout(height=270, margin={"l": 10, "r": 10, "t": 10, "b": 10},
                      legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0, "font": {"color": INK}})
    return _card(fig)


def build_timeline_fig(df: pd.DataFrame, as_of) -> go.Figure | None:
    """Planned versus actual dates per step. Returns None when no step has a planned or completed date."""
    sched = with_schedule(df, as_of)
    has = sched[sched["Planned"].notna() | sched["Completed"].notna()]
    if has.empty:
        return None
    labels = {s: f"{s} {STEP_SHORT[s].replace('<br>', ' ')}" for s in STEP_IDS}
    fig = go.Figure()
    as_of_ts = pd.Timestamp(as_of).normalize()
    for _, r in has.iterrows():
        y = labels[r["Step"]]
        if pd.notna(r["Planned"]) and pd.notna(r["Completed"]):
            late = r["Completed"] > r["Planned"]
            fig.add_trace(go.Scatter(x=[_iso(r["Planned"]), _iso(r["Completed"])], y=[y, y], mode="lines",
                                     line={"color": "#c62828" if late else "#2e7d32", "width": 4}, hoverinfo="skip",
                                     showlegend=False))
        elif r["Overdue"]:
            fig.add_trace(go.Scatter(x=[_iso(r["Planned"]), _iso(as_of_ts)], y=[y, y], mode="lines",
                                     line={"color": "#c62828", "width": 3, "dash": "dot"}, hoverinfo="skip", showlegend=False))
    planned = has[has["Planned"].notna() & ~has["Overdue"]]
    fig.add_trace(go.Scatter(x=[_iso(t) for t in planned["Planned"]], y=[labels[s] for s in planned["Step"]], mode="markers",
                             name="Planned", marker={"symbol": "diamond-open", "size": 13, "color": "#555555",
                                                     "line": {"width": 2}},
                             hovertext=[f"{r['Step']} planned {_iso(r['Planned'])}" for _, r in planned.iterrows()],
                             hoverinfo="text"))
    over = has[has["Overdue"]]
    if len(over):
        fig.add_trace(go.Scatter(x=[_iso(t) for t in over["Planned"]], y=[labels[s] for s in over["Step"]], mode="markers",
                                 name="Planned (overdue)", marker={"symbol": "diamond", "size": 13, "color": "#c62828"},
                                 hovertext=[f"{r['Step']} planned {_iso(r['Planned'])}, {int(r['Days late'])} d overdue"
                                            for _, r in over.iterrows()], hoverinfo="text"))
    comp = has[has["Completed"].notna()]
    fig.add_trace(go.Scatter(x=[_iso(t) for t in comp["Completed"]], y=[labels[s] for s in comp["Step"]], mode="markers",
                             name="Completed", marker={"symbol": "circle", "size": 12, "color": "#2e7d32"},
                             hovertext=[f"{r['Step']} completed {_iso(r['Completed'])}" for _, r in comp.iterrows()],
                             hoverinfo="text"))
    notes_x, notes_y, notes_t, notes_c = [], [], [], []
    for _, r in has.iterrows():
        if r["Status"] == "Done" and pd.notna(r["Days late"]):
            d = int(r["Days late"])
            text, color = ("on time", OK_TEXT) if d == 0 else ((f"{d} d late", BAD_TEXT) if d > 0 else (f"{-d} d early", OK_TEXT))
            later = max(r["Completed"], r["Planned"]) if pd.notna(r["Planned"]) else r["Completed"]
            notes_x.append(_iso(later))
        elif r["Overdue"]:
            text, color = f"overdue {int(r['Days late'])} d", BAD_TEXT
            notes_x.append(_iso(as_of_ts))
        else:
            continue
        notes_y.append(labels[r["Step"]])
        notes_t.append(f"<b>{PAD}{text}</b>")
        notes_c.append(color)
    if notes_x:
        fig.add_trace(go.Scatter(x=notes_x, y=notes_y, mode="text", text=notes_t, textposition="middle right",
                                 textfont={"size": 12, "color": notes_c}, hoverinfo="skip", showlegend=False))
    fig.add_shape(type="line", x0=_iso(as_of_ts), x1=_iso(as_of_ts), y0=0, y1=1, xref="x", yref="paper",
                  line={"color": "#555555", "dash": "dash", "width": 2})
    fig.add_annotation(x=_iso(as_of_ts), y=1.0, yref="paper", yanchor="bottom", text=f"as of {_iso(as_of_ts)}", showarrow=False,
                       font={"size": 12, "color": MUTED})
    fig.update_yaxes(categoryorder="array", categoryarray=[labels[s] for s in STEP_IDS][::-1], color=INK, gridcolor="#eeeeee")
    fig.update_xaxes(type="date", gridcolor="#e6e6e6", color=INK, title="Date")
    fig.update_layout(height=430, margin={"l": 10, "r": 90, "t": 40, "b": 50},
                      legend={"orientation": "h", "y": -0.18, "font": {"color": INK}})
    return _card(fig)


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def _reset() -> None:
    st.session_state["eight_d_ver"] = st.session_state.get("eight_d_ver", 0) + 1


def show_results(df: pd.DataFrame, title: str, opened, as_of) -> None:
    sched = with_schedule(df, as_of)
    n_done = int((df["Status"] == "Done").sum())
    cur = current_step(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Steps done", f"{n_done} of {len(df)}")
    c2.metric("Current step", cur or "Closed")
    c3.metric("Days open", days_open(df, opened, as_of))
    c4.metric("Overdue steps", int(sched["Overdue"].sum()))
    if (df["Status"] == "Blocked").any():
        st.error("Blocked: " + ", ".join(df.loc[df["Status"] == "Blocked", "Step"]) + ".")
    over = sched[sched["Overdue"]]
    if len(over):
        st.warning("Overdue: " + "; ".join(f"{r['Step']} ({int(r['Days late'])} d)" for _, r in over.iterrows()) + ".")
    for note in sequence_notes(df, opened, as_of):
        st.info(note)
    st.subheader(f"Progress: {title}" if _text(title) else "Progress")
    plot(build_stepper_fig(df, as_of))
    fig = build_timeline_fig(df, as_of)
    st.subheader("Planned versus actual")
    if fig is None:
        st.info("Enter planned or completed dates to see the timeline.")
    else:
        plot(fig)
        st.caption("Diamond = planned date, green dot = completed date. Red line = completed after the planned date. "
                   "Overdue = not Done and planned date before the 'status as of' date.")
    with st.expander("Step table"):
        shown = sched.copy()
        for c in ("Planned", "Completed"):
            shown[c] = shown[c].dt.strftime("%Y-%m-%d").fillna("")
        table(shown)
        st.download_button("Download steps (CSV)", shown.to_csv(index=False).encode("utf-8"),
                           file_name="eight_d_steps.csv", mime="text/csv", key="eight_d_dl")


def render() -> None:
    st.header("📋 8D Tracker")
    st.caption(METHOD_NOTE)
    sample_data_note("Simulated 8D for a generic machining problem. Replace the title, dates and steps with your own.")
    ver = st.session_state.get("eight_d_ver", 0)
    c1, c2, c3 = st.columns([3, 1, 1])
    title = c1.text_input("8D title", value=SAMPLE_TITLE, key=f"eight_d_title_{ver}")
    opened = c2.date_input("Opened", value=SAMPLE_OPENED, key=f"eight_d_opened_{ver}")
    as_of = c3.date_input("Status as of", value=SAMPLE_AS_OF, key=f"eight_d_asof_{ver}",
                          help="Set this to today's date to track a live 8D. The sample uses a fixed date.")
    raw = editor(
        sample_steps(), key=f"eight_d_editor_{ver}", hide_index=True,
        column_config={
            "Step": st.column_config.SelectboxColumn("Step", options=STEP_IDS, width="small"),
            "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, width="small"),
            "Planned date": st.column_config.DateColumn("Planned date", format="YYYY-MM-DD"),
            "Completed date": st.column_config.DateColumn("Completed date", format="YYYY-MM-DD"),
            "Notes": st.column_config.TextColumn("Notes", width="large"),
        },
    )
    st.button("Reset to sample data", key="eight_d_reset", on_click=_reset)
    clean, issues = clean_steps(raw)
    report_issues(issues)
    show_results(clean, title, opened, as_of)
