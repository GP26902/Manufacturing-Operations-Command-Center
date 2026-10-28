"""Kaizen log: impact/effort matrix, status funnel, cumulative savings and a PDCA cycle diagram.

Pure functions (no Streamlit calls) come first so they can be unit-tested; the page is at the bottom.
Custom diagrams use a white card background and explicit text colours so they read the same in light and dark themes.
"""
from __future__ import annotations

import datetime as dt
import html
import math
import textwrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, editor, plot, report_issues, sample_data_note, table

STATUSES = ["Idea", "Plan", "Do", "Check", "Standardized", "Rejected"]
FLOW = STATUSES[:5]  # stages an idea moves through; Rejected leaves the flow
IDEA_COLS = ["Idea", "Area", "Impact", "Effort", "Status", "Est. annual savings", "Date standardized"]
CLEAN_COLS = ["ID", "Idea", "Area", "Impact", "Effort", "Status", "Savings", "Date"]
SCALE_MIN, SCALE_MAX = 1, 5
INK, MUTED = "#1a1a1a", "#4a4a4a"
STATUS_COLORS = {"Idea": "#6b6b6b", "Plan": "#1f77b4", "Do": "#c0580a", "Check": "#8e44ad", "Standardized": "#2e7d32",
                 "Rejected": "#b71c1c"}

_STATUS_ALIASES = {
    "idea": "Idea", "new": "Idea", "proposed": "Idea", "submitted": "Idea", "backlog": "Idea",
    "plan": "Plan", "planned": "Plan", "approved": "Plan",
    "do": "Do", "doing": "Do", "in progress": "Do", "trial": "Do",
    "check": "Check", "checking": "Check", "verify": "Check", "verifying": "Check",
    "standardized": "Standardized", "standardised": "Standardized", "act": "Standardized", "done": "Standardized",
    "implemented": "Standardized", "complete": "Standardized", "completed": "Standardized",
    "rejected": "Rejected", "dropped": "Rejected", "cancelled": "Rejected", "canceled": "Rejected",
}

METHOD_NOTE = (
    "Each idea is scored for impact and effort (1 to 5, whole numbers) and moves through the PDCA stages: Idea, Plan, "
    "Do, Check, Standardized. Quick wins are open ideas with high impact and low effort; the thresholds are set below. "
    "Savings are estimates entered by the team. They are annual run-rate figures, not audited results."
)


# ---------------------------------------------------------------------------
# Sample data (simulated, generic)
# ---------------------------------------------------------------------------
def sample_ideas() -> pd.DataFrame:
    d = dt.date
    rows = [
        ("Add shadow board for torque tools", "Assembly", 3, 1, "Standardized", 4000, d(2026, 3, 18)),
        ("Move fasteners to point-of-use bins", "Assembly", 4, 2, "Standardized", 9500, d(2026, 4, 22)),
        ("Pre-set tool offsets off-line", "Machining", 5, 3, "Standardized", 28000, d(2026, 6, 10)),
        ("Colour-code coolant filters by change interval", "Machining", 2, 1, "Standardized", 1500, d(2026, 7, 8)),
        ("Standard work card at the leak-test station", "Quality", 3, 2, "Standardized", 6000, d(2026, 8, 19)),
        ("Kit parts for changeover", "Machining", 4, 2, "Check", 12000, None),
        ("Barcode scan for part-number check", "Assembly", 4, 3, "Do", 15000, None),
        ("Replace manual counting with a weigh scale", "Warehouse", 3, 2, "Plan", 5500, None),
        ("Re-layout the cell to cut walking distance", "Assembly", 5, 5, "Plan", 40000, None),
        ("Auto-feed for the chip conveyor", "Machining", 3, 5, "Idea", 8000, None),
        ("Daily five-minute cleaning rota", "Quality", 2, 1, "Idea", None, None),
        ("Upgrade the ship-out label printer", "Warehouse", 2, 4, "Rejected", 3000, None),
    ]
    out = pd.DataFrame(rows, columns=IDEA_COLS)
    out["Impact"] = out["Impact"].astype(float)
    out["Effort"] = out["Effort"].astype(float)
    out["Est. annual savings"] = out["Est. annual savings"].astype(float)
    return out


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


def to_scale(value) -> float:
    """Whole number from 1 to 5, else NaN."""
    if _is_blank(value):
        return np.nan
    try:
        x = float(value.strip()) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return np.nan
    if not math.isfinite(x) or x != round(x) or x < SCALE_MIN or x > SCALE_MAX:
        return np.nan
    return x


def to_amount(value) -> float:
    """Finite number >= 0, else NaN."""
    if _is_blank(value):
        return np.nan
    try:
        x = float(value.strip().replace(",", "").lstrip("$")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if math.isfinite(x) and x >= 0 else np.nan


def to_date(value) -> pd.Timestamp:
    if _is_blank(value):
        return pd.NaT
    try:
        ts = pd.to_datetime(value, errors="coerce")
    except (TypeError, ValueError, OverflowError):
        return pd.NaT
    return pd.NaT if pd.isna(ts) else pd.Timestamp(ts).normalize()


def normalise_status(value) -> str | None:
    key = " ".join(_text(value).lower().replace("_", " ").replace("-", " ").split())
    return _STATUS_ALIASES.get(key)


def empty_clean() -> pd.DataFrame:
    return pd.DataFrame({"ID": pd.Series(dtype=object), "Idea": pd.Series(dtype=object), "Area": pd.Series(dtype=object),
                         "Impact": pd.Series(dtype=float), "Effort": pd.Series(dtype=float), "Status": pd.Series(dtype=object),
                         "Savings": pd.Series(dtype=float), "Date": pd.Series(dtype="datetime64[ns]")})


def clean_ideas(raw) -> tuple[pd.DataFrame, list[str]]:
    """Validate the idea table. Never raises on bad cell values.

    Excluded and reported: missing idea text, impact or effort not a whole number 1 to 5, unrecognised status.
    Kept with the value ignored and reported: savings that are not a number >= 0, unreadable dates.
    A blank status means Idea.
    """
    issues: list[str] = []
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return empty_clean(), issues
    rows = []
    for pos, rec in enumerate(raw.to_dict("records"), start=1):
        idea, area = _text(rec.get("Idea")), _text(rec.get("Area"))
        others = [rec.get(c) for c in IDEA_COLS[2:]]
        if not idea and not area and all(_is_blank(v) for v in others):
            continue
        if not idea:
            issues.append(f"Row {pos}: idea text missing. Row excluded.")
            continue
        imp, eff = to_scale(rec.get("Impact")), to_scale(rec.get("Effort"))
        bad = [n for n, v in (("Impact", imp), ("Effort", eff)) if np.isnan(v)]
        if bad:
            issues.append(f"Row {pos} ({idea}): {' and '.join(bad)} must be a whole number from 1 to 5. Row excluded.")
            continue
        status = "Idea" if _is_blank(rec.get("Status")) else normalise_status(rec.get("Status"))
        if status is None:
            issues.append(f"Row {pos} ({idea}): status '{_text(rec.get('Status'))}' not recognised "
                          f"(use {', '.join(STATUSES)}). Row excluded.")
            continue
        raw_sav = rec.get("Est. annual savings")
        sav = to_amount(raw_sav)
        if np.isnan(sav) and not _is_blank(raw_sav):
            issues.append(f"Row {pos} ({idea}): savings must be a number of 0 or more. Value ignored.")
        raw_date = rec.get("Date standardized")
        date = to_date(raw_date)
        if pd.isna(date) and not _is_blank(raw_date):
            issues.append(f"Row {pos} ({idea}): date not readable. Value ignored.")
        rows.append({"Idea": idea, "Area": area, "Impact": imp, "Effort": eff, "Status": status, "Savings": sav, "Date": date})
    if not rows:
        return empty_clean(), issues
    df = pd.DataFrame(rows)
    df.insert(0, "ID", [f"K{i}" for i in range(1, len(df) + 1)])
    df["Date"] = pd.to_datetime(df["Date"])
    repeats = int(df["Idea"].str.lower().duplicated().sum())
    if repeats:
        issues.append(f"{repeats} idea(s) repeat an earlier idea text. Kept and counted separately.")
    return df[CLEAN_COLS], issues


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def cap_default(default: float, max_value: float) -> float:
    return min(default, max_value)


def in_quick_win_zone(df: pd.DataFrame, impact_min: float, effort_max: float) -> pd.Series:
    return (df["Impact"] >= impact_min) & (df["Effort"] <= effort_max) & (df["Status"] != "Rejected")


def open_quick_wins(df: pd.DataFrame, impact_min: float, effort_max: float) -> pd.DataFrame:
    """Quick-win ideas that are not yet standardized (and not rejected)."""
    if df.empty:
        return df
    return df[in_quick_win_zone(df, impact_min, effort_max) & (df["Status"] != "Standardized")]


def funnel_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Ideas that reached at least each stage. Rejected ideas count at Idea only."""
    counts = []
    for i, stage in enumerate(FLOW):
        reached = set(FLOW[i:])
        counts.append({"Stage": stage, "Ideas": int(df["Status"].isin(reached).sum()) if len(df) else 0})
    out = pd.DataFrame(counts)
    if len(df):
        out.loc[0, "Ideas"] = int(len(df))  # every submitted idea, including rejected ones
    return out


def stage_counts(df: pd.DataFrame) -> dict[str, int]:
    """Ideas currently in each status."""
    return {s: int((df["Status"] == s).sum()) if len(df) else 0 for s in STATUSES}


def cumulative_savings(df: pd.DataFrame) -> pd.DataFrame:
    """Standardized ideas with both a date and savings, summed per date, with a running total."""
    if df.empty:
        return pd.DataFrame({"Date": pd.Series(dtype="datetime64[ns]"), "Savings": pd.Series(dtype=float),
                             "Cumulative": pd.Series(dtype=float), "Ideas": pd.Series(dtype=object)})
    done = df[(df["Status"] == "Standardized") & df["Date"].notna() & df["Savings"].notna()]
    if done.empty:
        return cumulative_savings(df.iloc[0:0])
    g = done.groupby("Date").agg(Savings=("Savings", "sum"), Ideas=("ID", lambda s: ", ".join(s))).reset_index()
    g = g.sort_values("Date").reset_index(drop=True)
    g["Cumulative"] = g["Savings"].cumsum()
    return g


def summary(df: pd.DataFrame, impact_min: float, effort_max: float) -> dict:
    if df.empty:
        return {"n": 0, "standardized": 0, "rejected": 0, "realized": 0.0, "pipeline": 0.0, "open_quick": 0,
                "open_quick_savings": 0.0, "standardized_missing": 0}
    std = df[df["Status"] == "Standardized"]
    pipe = df[df["Status"].isin(["Plan", "Do", "Check"])]
    oq = open_quick_wins(df, impact_min, effort_max)
    return {
        "n": int(len(df)),
        "standardized": int(len(std)),
        "rejected": int((df["Status"] == "Rejected").sum()),
        "realized": float(std["Savings"].fillna(0).sum()),
        "pipeline": float(pipe["Savings"].fillna(0).sum()),
        "open_quick": int(len(oq)),
        "open_quick_savings": float(oq["Savings"].fillna(0).sum()),
        "standardized_missing": int((std["Date"].isna() | std["Savings"].isna()).sum()),
    }


def spread_positions(pairs: list[tuple[float, float]], radius: float = 0.22) -> list[tuple[float, float]]:
    """Offset points that share the same (effort, impact) cell onto a small circle so they do not overlap."""
    groups: dict[tuple[float, float], list[int]] = {}
    for i, p in enumerate(pairs):
        groups.setdefault(p, []).append(i)
    out: list[tuple[float, float]] = [(0.0, 0.0)] * len(pairs)
    for (x, y), idx in groups.items():
        k = len(idx)
        for j, i in enumerate(idx):
            if k == 1:
                out[i] = (x, y)
            else:
                r = radius if k <= 4 else radius * 1.35
                a = 2 * math.pi * j / k + math.pi / 4
                out[i] = (x + r * math.cos(a), y + r * math.sin(a))
    return out


def _money(x: float) -> str:
    return f"${x:,.0f}"


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _card(fig: go.Figure) -> go.Figure:
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="white", font={"color": INK})
    return fig


def build_matrix_fig(df: pd.DataFrame, impact_min: float, effort_max: float) -> go.Figure:
    xs, ys = effort_max + 0.5, impact_min - 0.5
    lo, hi = SCALE_MIN - 0.5, SCALE_MAX + 0.5
    quads = [
        (lo, xs, ys, hi, "rgba(44,160,44,0.18)", "QUICK WINS", "#1b5e20", "left", "top", lo + 0.05, hi - 0.05),
        (xs, hi, ys, hi, "rgba(31,119,180,0.10)", "MAJOR PROJECTS", "#0d47a1", "right", "top", hi - 0.05, hi - 0.05),
        (lo, xs, lo, ys, "rgba(127,127,127,0.12)", "FILL-INS", "#444444", "left", "bottom", lo + 0.05, lo + 0.05),
        (xs, hi, lo, ys, "rgba(214,39,40,0.10)", "RECONSIDER", "#8b1a1a", "right", "bottom", hi - 0.05, lo + 0.05),
    ]
    fig = go.Figure()
    for x0, x1, y0, y1, fill, label, color, xa, ya, lx, ly in quads:
        if x1 - x0 <= 1e-9 or y1 - y0 <= 1e-9:
            continue
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=fill, line={"width": 0}, layer="below")
        fig.add_annotation(x=lx, y=ly, text=f"<b>{label}</b>", showarrow=False, xanchor=xa, yanchor=ya,
                           font={"size": 12, "color": color})
    if len(df):
        pos = spread_positions(list(zip(df["Effort"], df["Impact"])))
        px = pd.Series([p[0] for p in pos], index=df.index)
        py = pd.Series([p[1] for p in pos], index=df.index)
        for status in STATUSES:
            sub = df[df["Status"] == status]
            if sub.empty:
                continue
            hover = [
                f"<b>{html.escape(r['ID'])}: {html.escape(r['Idea'], quote=False)}</b><br>{html.escape(r['Area'], quote=False)}"
                f"<br>Impact {r['Impact']:.0f}, effort {r['Effort']:.0f}<br>{r['Status']}"
                + (f"<br>Est. {_money(r['Savings'])}/yr" if not np.isnan(r["Savings"]) else "")
                for _, r in sub.iterrows()
            ]
            fig.add_trace(go.Scatter(
                x=px[sub.index], y=py[sub.index], mode="markers+text", name=status, text=list(sub["ID"]),
                textposition="middle center", textfont={"size": 10, "color": "#ffffff"},
                marker={"size": 30, "color": STATUS_COLORS[status], "line": {"width": 1, "color": "#ffffff"}},
                hovertext=hover, hoverinfo="text"))
    fig.update_xaxes(range=[lo, hi], tickvals=list(range(SCALE_MIN, SCALE_MAX + 1)), title="Effort (1 = low, 5 = high)",
                     gridcolor="#e6e6e6", zeroline=False, color=INK)
    fig.update_yaxes(range=[lo, hi], tickvals=list(range(SCALE_MIN, SCALE_MAX + 1)), title="Impact (1 = low, 5 = high)",
                     gridcolor="#e6e6e6", zeroline=False, color=INK)
    fig.update_layout(height=520, legend={"orientation": "h", "y": -0.18, "font": {"color": INK}},
                      margin={"l": 60, "r": 20, "t": 20, "b": 60})
    return _card(fig)


def build_funnel_fig(df: pd.DataFrame) -> go.Figure:
    counts = funnel_counts(df)
    fig = go.Figure(go.Funnel(
        y=list(counts["Stage"]), x=list(counts["Ideas"]), textinfo="value+percent initial",
        marker={"color": [STATUS_COLORS[s] for s in counts["Stage"]]},
        insidetextfont={"color": "#ffffff", "size": 14}))
    fig.update_layout(title="Ideas that reached each stage", height=380, margin={"l": 10, "r": 10, "t": 50, "b": 10})
    return fig


def build_cumulative_fig(cum: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=list(cum["Date"]), y=list(cum["Cumulative"]), mode="lines+markers", line={"shape": "hv", "color": GREEN, "width": 3},
        marker={"size": 9}, customdata=list(cum["Ideas"]),
        hovertemplate="%{x|%Y-%m-%d}<br>Cumulative $%{y:,.0f}<br>Ideas: %{customdata}<extra></extra>"))
    fig.update_layout(title="Cumulative estimated annual savings from standardized ideas", height=380,
                      yaxis={"title": "Estimated annual savings ($)", "rangemode": "tozero"}, xaxis_title="Date standardized")
    return fig


PDCA_BOXES = [
    ("PLAN", "Define the problem, set a target and choose the change.", "Plan", (0.3, 4.3, 3.4, 5.8), "#e3eef9", BLUE),
    ("DO", "Try the change on a small scale.", "Do", (5.7, 9.7, 3.4, 5.8), "#fff3e0", ORANGE),
    ("CHECK", "Compare the result with the target.", "Check", (5.7, 9.7, 0.2, 2.6), "#f1e6f7", "#8e44ad"),
    ("ACT", "Standardize if it worked. If not, adjust and repeat.", "Standardized", (0.3, 4.3, 0.2, 2.6), "#e2f4e2", GREEN),
]


def build_pdca_fig(df: pd.DataFrame) -> go.Figure:
    counts = stage_counts(df)
    fig = go.Figure()
    for title, desc, status, (x0, x1, y0, y1), fill, border in PDCA_BOXES:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=fill, line={"color": border, "width": 2})
        n = counts[status]
        fig.add_annotation(x=(x0 + x1) / 2, y=y1 - 0.25, yanchor="top", showarrow=False, text=f"<b>{title}</b>",
                           font={"size": 16, "color": INK})
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2 + 0.05, showarrow=False, font={"size": 12, "color": MUTED},
                           text="<br>".join(textwrap.wrap(desc, 34)))
        fig.add_annotation(x=(x0 + x1) / 2, y=y0 + 0.3, yanchor="bottom", showarrow=False, font={"size": 13, "color": INK},
                           text=f"<b>{n}</b> idea{'s' if n != 1 else ''} now at {status}")
    arrows = [((4.3, 4.6), (5.7, 4.6)), ((7.7, 3.4), (7.7, 2.6)), ((5.7, 1.4), (4.3, 1.4)), ((2.3, 2.6), (2.3, 3.4))]
    for (x0, y0), (x1, y1) in arrows:
        fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2,
                           arrowwidth=3, arrowcolor="#555555", text="")
    fig.update_xaxes(visible=False, range=[0, 10])
    fig.update_yaxes(visible=False, range=[0, 6])
    fig.update_layout(height=400, margin={"l": 10, "r": 10, "t": 10, "b": 10}, showlegend=False)
    return _card(fig)


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def _reset() -> None:
    st.session_state["kaizen_ver"] = st.session_state.get("kaizen_ver", 0) + 1


def show_results(df: pd.DataFrame, impact_min: float, effort_max: float) -> None:
    if df.empty:
        st.info("Enter at least one idea with impact and effort scores to see the analysis.")
        return
    s = summary(df, impact_min, effort_max)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ideas", s["n"])
    c2.metric("Standardized", s["standardized"])
    c3.metric("Est. annual savings (standardized)", _money(s["realized"]))
    c4.metric("Open quick wins", s["open_quick"])
    oq = open_quick_wins(df, impact_min, effort_max)
    if len(oq):
        items = "; ".join(f"{r['ID']} {r['Idea']} ({r['Status']})" for _, r in oq.iterrows())
        st.warning(f"⚡ **Quick wins not yet standardized:** {items}. Estimated {_money(s['open_quick_savings'])} per year.")
    elif s["n"]:
        st.caption("No open quick wins at the current thresholds.")
    tabs = st.tabs(["Impact / effort matrix", "Status funnel", "Cumulative savings", "PDCA cycle", "Table"])
    with tabs[0]:
        plot(build_matrix_fig(df, impact_min, effort_max))
        st.caption("Position = impact and effort scores; ideas with the same scores are spread slightly. "
                   "Green zone = quick wins at the thresholds above. Rejected ideas are shown but excluded from quick wins.")
    with tabs[1]:
        plot(build_funnel_fig(df))
        st.caption(f"Rejected ideas ({s['rejected']}) count at the first stage only. Pipeline savings (Plan, Do, Check): "
                   f"{_money(s['pipeline'])} per year, estimated.")
    with tabs[2]:
        cum = cumulative_savings(df)
        if cum.empty:
            st.info("Set an idea to Standardized and enter its date and savings to see cumulative savings.")
        else:
            plot(build_cumulative_fig(cum))
        missing = s["standardized_missing"]
        if missing:
            st.caption(f"{missing} standardized idea(s) have no date or no savings and are left out of this chart.")
        st.caption("Sum of the estimated annual savings of standardized ideas, by the date each was standardized. "
                   "Not audited or confirmed by finance.")
    with tabs[3]:
        plot(build_pdca_fig(df))
        st.caption(f"Counts are ideas currently at each status. Backlog (Idea): {stage_counts(df)['Idea']}.")
    with tabs[4]:
        shown = df.copy()
        shown["Date"] = shown["Date"].dt.strftime("%Y-%m-%d").fillna("")
        table(shown.rename(columns={"Savings": "Est. annual savings ($)", "Date": "Date standardized"}))
        st.download_button("Download ideas (CSV)", shown.to_csv(index=False).encode("utf-8"),
                           file_name="kaizen_log.csv", mime="text/csv", key="kaizen_dl")


def render() -> None:
    st.header("🔁 Kaizen Log")
    st.caption(METHOD_NOTE)
    sample_data_note("Simulated improvement ideas for a generic machining and assembly area. Edit or add rows to use your own.")
    ver = st.session_state.get("kaizen_ver", 0)
    raw = editor(
        sample_ideas(), key=f"kaizen_editor_{ver}", hide_index=True,
        column_config={
            "Idea": st.column_config.TextColumn("Idea", width="large"),
            "Area": st.column_config.TextColumn("Area", width="small"),
            "Impact": st.column_config.NumberColumn("Impact (1-5)", min_value=1, max_value=5, step=1, format="%d", width="small"),
            "Effort": st.column_config.NumberColumn("Effort (1-5)", min_value=1, max_value=5, step=1, format="%d", width="small"),
            "Status": st.column_config.SelectboxColumn("Status", options=STATUSES, width="small"),
            "Est. annual savings": st.column_config.NumberColumn("Est. annual savings ($)", min_value=0, step=500, format="%d"),
            "Date standardized": st.column_config.DateColumn("Date standardized", format="YYYY-MM-DD"),
        },
    )
    st.button("Reset to sample data", key="kaizen_reset", on_click=_reset)
    clean, issues = clean_ideas(raw)
    report_issues(issues)
    i1, i2 = st.columns(2)
    impact_min = i1.number_input("Quick win: impact at least", min_value=SCALE_MIN, max_value=SCALE_MAX,
                                 value=int(cap_default(4, SCALE_MAX)), step=1, key="kaizen_impact_min")
    effort_max = i2.number_input("Quick win: effort at most", min_value=SCALE_MIN, max_value=SCALE_MAX,
                                 value=int(cap_default(2, SCALE_MAX)), step=1, key="kaizen_effort_max")
    show_results(clean, float(impact_min), float(effort_max))
