"""5S audit: checklist scoring, radar chart, score trend and weakest-S callout.

Pure calculation and figure functions come first (no Streamlit calls) so they can be unit-tested.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, PURPLE, RED, editor, plot, sample_data_note, table

S_NAMES = ["Sort", "Set in order", "Shine", "Standardize", "Sustain"]
S_COLORS = [BLUE, ORANGE, GREEN, RED, PURPLE]
SCORE_MIN, SCORE_MAX = 0.0, 4.0
CHECK_COLS = ["S", "Check item", "Score", "Notes"]
HIST_COLS = ["Audit date", *S_NAMES]

_ALIASES = {
    "sort": "Sort", "seiri": "Sort",
    "set in order": "Set in order", "set": "Set in order", "straighten": "Set in order", "seiton": "Set in order",
    "shine": "Shine", "seiso": "Shine", "sweep": "Shine",
    "standardize": "Standardize", "standardise": "Standardize", "seiketsu": "Standardize",
    "sustain": "Sustain", "shitsuke": "Sustain",
}

SCALE_NOTE = (
    "Score each item from 0 to 4 (decimals allowed): 0 = not in place, 1 = started with major gaps, 2 = partly in place, "
    "3 = mostly in place with minor gaps, 4 = fully in place and maintained. Generic orientation only; use your own criteria. "
    "Score % for an S = points / (4 x items scored). Overall = average of the five S percentages, so each S counts equally. "
    "Items with a blank score are not counted."
)


# ---------------------------------------------------------------------------
# Sample data (simulated, generic)
# ---------------------------------------------------------------------------
def sample_checklist() -> pd.DataFrame:
    rows = [
        ("Sort", "Unneeded tools and materials removed from the work area", 3),
        ("Sort", "Red-tag area in use and cleared on schedule", 3),
        ("Sort", "Only current-job materials at the workstation", 3),
        ("Sort", "Obsolete documents and fixtures removed", 2),
        ("Set in order", "Tools have marked locations (outlines or shadow board)", 3),
        ("Set in order", "Material and WIP locations labelled with min/max", 2),
        ("Set in order", "Walkways and floor markings visible", 3),
        ("Set in order", "Frequently used items within reach", 3),
        ("Shine", "Equipment free of oil, chips and dust", 2),
        ("Shine", "Floor clean and free of spills", 2),
        ("Shine", "Cleaning schedule posted and followed", 3),
        ("Shine", "Leak and dirt sources recorded for fixing", 2),
        ("Standardize", "Photos of the correct state posted", 2),
        ("Standardize", "Cleaning and inspection routines documented", 1),
        ("Standardize", "Labels and colour codes consistent across cells", 2),
        ("Standardize", "Responsibilities assigned and visible", 2),
        ("Sustain", "Audits done on schedule", 2),
        ("Sustain", "Findings from the last audit closed", 2),
        ("Sustain", "Team members can explain the 5S rules", 3),
        ("Sustain", "5S results posted and reviewed", 2),
    ]
    return pd.DataFrame([(s, i, float(v), "") for s, i, v in rows], columns=CHECK_COLS)


def sample_history() -> pd.DataFrame:
    dates = ["2026-05-12", "2026-06-09", "2026-07-14", "2026-08-11", "2026-09-08"]
    values = [
        (50, 45, 40, 30, 35),
        (55, 50, 45, 32, 38),
        (60, 58, 50, 35, 42),
        (65, 62, 52, 40, 48),
        (68, 66, 55, 42, 52),
    ]
    df = pd.DataFrame(values, columns=S_NAMES, dtype=float)
    df.insert(0, "Audit date", [dt.date.fromisoformat(d) for d in dates])
    return df


# ---------------------------------------------------------------------------
# Cleaning and scoring
# ---------------------------------------------------------------------------
def _is_blank(value) -> bool:
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        return False
    return isinstance(value, str) and not value.strip()


def _text(value) -> str:
    return "" if _is_blank(value) else str(value).strip()


def normalise_s(name) -> str | None:
    """Map a typed S name (or a Japanese alias) to one of S_NAMES, else None."""
    key = " ".join(_text(name).lower().replace("-", " ").replace("_", " ").split())
    return _ALIASES.get(key)


def _to_number(value) -> float:
    if _is_blank(value):
        return np.nan
    try:
        x = float(value.strip().rstrip("%")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if math.isfinite(x) else np.nan


def clean_checklist(raw) -> tuple[pd.DataFrame, list[str]]:
    """Validate checklist rows. Returns (valid rows with Score, issues). Blank scores are kept with NaN score.

    Excluded and reported: unknown S name, score that is text or outside 0 to 4.
    """
    issues: list[str] = []
    empty = pd.DataFrame({"S": pd.Series(dtype="object"), "Check item": pd.Series(dtype="object"),
                          "Score": pd.Series(dtype="float")})
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return empty, issues
    rows = []
    for pos, rec in enumerate(raw.to_dict("records"), start=1):
        s_raw, item, score_raw = rec.get("S"), _text(rec.get("Check item")), rec.get("Score")
        if _is_blank(s_raw) and not item and _is_blank(score_raw):
            continue
        s = normalise_s(s_raw)
        label = item or "no description"
        if s is None:
            issues.append(f"Row {pos} ({label}): S must be one of {', '.join(S_NAMES)}. Row excluded.")
            continue
        score = _to_number(score_raw)
        if _is_blank(score_raw):
            score = np.nan
        elif np.isnan(score) or score < SCORE_MIN or score > SCORE_MAX:
            issues.append(f"Row {pos} ({label}): score must be a number from 0 to 4. Row excluded.")
            continue
        rows.append({"S": s, "Check item": item, "Score": score})
    if not rows:
        return empty, issues
    return pd.DataFrame(rows), issues


def score_by_s(clean: pd.DataFrame) -> pd.DataFrame:
    """One row per S in canonical order. Score % is NaN when no item of that S has a score."""
    out = []
    for s in S_NAMES:
        scored = clean.loc[(clean["S"] == s) & clean["Score"].notna(), "Score"] if len(clean) else pd.Series(dtype=float)
        n = int(len(scored))
        points = float(scored.sum()) if n else 0.0
        out.append({"S": s, "Items scored": n, "Points": points, "Max points": n * SCORE_MAX,
                    "Score %": points / (n * SCORE_MAX) * 100 if n else np.nan})
    return pd.DataFrame(out)


def overall_percent(values) -> float:
    arr = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    return float(arr.mean()) if len(arr) else np.nan


def weakest_s(scores: pd.DataFrame) -> list[str]:
    """Name(s) of the lowest-scoring S (all of them when tied). Empty when nothing is scored."""
    valid = scores.dropna(subset=["Score %"])
    if valid.empty:
        return []
    low = valid["Score %"].min()
    return [r["S"] for _, r in valid.iterrows() if math.isclose(r["Score %"], low, abs_tol=1e-9)]


def lowest_items(clean: pd.DataFrame, s: str, n: int = 3) -> list[tuple[str, float]]:
    sub = clean[(clean["S"] == s) & clean["Score"].notna()].sort_values("Score", kind="stable").head(n)
    return [(r["Check item"] or "(no description)", float(r["Score"])) for _, r in sub.iterrows()]


def clean_history(raw) -> tuple[pd.DataFrame, list[str]]:
    """Validate the audit-history table: dates must parse, S percentages must be 0 to 100.

    Invalid percentages become blank (the row is kept); rows with unreadable dates are dropped.
    A repeated date keeps the last row.
    """
    issues: list[str] = []
    empty = pd.DataFrame({"Audit date": pd.Series(dtype="datetime64[ns]"), **{s: pd.Series(dtype=float) for s in S_NAMES}})
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return empty, issues
    rows = []
    for pos, rec in enumerate(raw.to_dict("records"), start=1):
        vals = [rec.get(c) for c in HIST_COLS]
        if all(_is_blank(v) for v in vals):
            continue
        date = pd.to_datetime(rec.get("Audit date"), errors="coerce") if not _is_blank(rec.get("Audit date")) else pd.NaT
        if pd.isna(date):
            issues.append(f"History row {pos}: audit date missing or not readable. Row excluded.")
            continue
        row = {"Audit date": pd.Timestamp(date).normalize()}
        for s in S_NAMES:
            v = _to_number(rec.get(s))
            if not _is_blank(rec.get(s)) and (np.isnan(v) or v < 0 or v > 100):
                issues.append(f"History row {pos} ({row['Audit date'].date()}): {s} must be a number from 0 to 100. Value ignored.")
                v = np.nan
            row[s] = v
        rows.append(row)
    if not rows:
        return empty, issues
    df = pd.DataFrame(rows)
    dup = int(df.duplicated(subset=["Audit date"], keep="last").sum())
    if dup:
        issues.append(f"{dup} history row(s) share an audit date with a later row. Only the last row for each date is used.")
        df = df.drop_duplicates(subset=["Audit date"], keep="last")
    return df.sort_values("Audit date").reset_index(drop=True), issues


def previous_audit(history: pd.DataFrame, current_date) -> pd.Series | None:
    """Latest history row dated before current_date, or None."""
    if history.empty:
        return None
    before = history[history["Audit date"] < pd.Timestamp(current_date)]
    return None if before.empty else before.iloc[-1]


def trend_frame(history: pd.DataFrame, current_pcts: dict | None = None, current_date=None) -> pd.DataFrame:
    """History plus (optionally) the current audit, with an Overall column. If the current date repeats a history date, current wins."""
    df = history.copy()
    if current_pcts is not None and current_date is not None:
        row = {"Audit date": pd.Timestamp(current_date).normalize(), **{s: current_pcts.get(s, np.nan) for s in S_NAMES}}
        df = df[df["Audit date"] != row["Audit date"]]
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    if df.empty:
        df["Overall"] = pd.Series(dtype=float)
        return df
    df = df.sort_values("Audit date").reset_index(drop=True)
    df["Overall"] = [overall_percent(r) for r in df[S_NAMES].itertuples(index=False, name=None)]
    return df


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _closed(values) -> list:
    vals = [None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v) for v in values]
    return vals + vals[:1]


def build_radar_fig(current: dict, previous: dict | None = None, previous_label: str = "Previous audit",
                    target: float | None = None, title: str = "5S score by S (%)") -> go.Figure:
    theta = S_NAMES + S_NAMES[:1]
    fig = go.Figure()
    if target is not None:
        fig.add_trace(go.Scatterpolar(r=[target] * len(theta), theta=theta, mode="lines", name=f"Target ({target:g}%)",
                                      line=dict(color=GREEN, dash="dash")))
    if previous is not None:
        fig.add_trace(go.Scatterpolar(r=_closed([previous.get(s) for s in S_NAMES]), theta=theta, mode="lines+markers",
                                      name=previous_label, line=dict(color="#7f7f7f", dash="dot")))
    fig.add_trace(go.Scatterpolar(r=_closed([current.get(s) for s in S_NAMES]), theta=theta, mode="lines+markers",
                                  name="Current audit", fill="toself", line=dict(color=BLUE), fillcolor="rgba(31,119,180,0.25)"))
    fig.update_layout(title=title, height=440, polar=dict(radialaxis=dict(range=[0, 100], ticksuffix="%")),
                      legend=dict(orientation="h", y=-0.15))
    return fig


def build_trend_fig(trend: pd.DataFrame, target: float | None = None) -> go.Figure:
    fig = go.Figure()
    for s, color in zip(S_NAMES, S_COLORS):
        fig.add_trace(go.Scatter(x=trend["Audit date"], y=trend[s], mode="lines+markers", name=s,
                                 line=dict(color=color, width=1.5), marker=dict(size=6)))
    fig.add_trace(go.Scatter(x=trend["Audit date"], y=trend["Overall"], mode="lines+markers", name="Overall",
                             line=dict(color="#333333", width=4), marker=dict(size=9)))
    if target is not None:
        fig.add_hline(y=target, line_dash="dot", line_color=GREEN, annotation_text=f"Target {target:g}%")
    fig.update_layout(title="5S score across audits (%)", height=420, yaxis=dict(range=[0, 100], title="Score %"),
                      xaxis_title="Audit date", legend=dict(orientation="h", y=-0.25))
    return fig


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def _report_issues(issues: list[str]) -> None:
    if not issues:
        return
    with st.expander(f"⚠️ {len(issues)} data note(s): some entries were excluded or ignored", expanded=True):
        for msg in issues[:10]:
            st.markdown(f"- {msg}")
        if len(issues) > 10:
            st.markdown(f"- …and {len(issues) - 10} more.")


def show_results(clean: pd.DataFrame, history: pd.DataFrame, area: str, audit_date, target: float,
                 include_current_in_trend: bool = True) -> None:
    """Metrics, weakest-S callout, radar and trend for already-cleaned inputs."""
    scores = score_by_s(clean)
    current = dict(zip(scores["S"], scores["Score %"]))
    overall = overall_percent(scores["Score %"])
    prev_row = previous_audit(history, audit_date)
    prev_pcts = None if prev_row is None else {s: prev_row[s] for s in S_NAMES}
    prev_overall = None if prev_pcts is None else overall_percent(prev_pcts.values())

    n_scored = int(scores["Items scored"].sum())
    if n_scored == 0:
        st.info("Score at least one checklist item to see the audit results.")
    else:
        weak = weakest_s(scores)
        c1, c2, c3 = st.columns(3)
        delta = None
        if prev_overall is not None and not np.isnan(overall) and not np.isnan(prev_overall):
            delta = f"{overall - prev_overall:+.1f} pts vs previous audit"
        c1.metric("Overall score", f"{overall:.1f}%", delta=delta)
        c2.metric("Items scored", n_scored)
        c3.metric("S below target", int((scores["Score %"] < target).sum()))

        for s in weak:
            pct = float(scores.loc[scores["S"] == s, "Score %"].iloc[0])
            items = "; ".join(f"{name} ({score:g}/4)" for name, score in lowest_items(clean, s))
            st.warning(f"⚠️ **Weakest S: {s} ({pct:.1f}%).** Lowest-scoring items: {items}.")

        left, right = st.columns([3, 2])
        with left:
            plot(build_radar_fig(
                current, prev_pcts,
                previous_label=f"Previous audit ({pd.Timestamp(prev_row['Audit date']).date()})" if prev_row is not None else "",
                target=target, title=f"5S score by S: {area}" if area else "5S score by S (%)",
            ))
        with right:
            shown = scores.copy()
            shown["Gap to target (pts)"] = shown["Score %"] - target
            shown["Score %"] = shown["Score %"].round(1)
            shown["Gap to target (pts)"] = shown["Gap to target (pts)"].round(1)
            shown["Points"] = shown["Points"].round(1)
            shown["Max points"] = shown["Max points"].round(1)
            table(shown)
            st.caption("Score % is blank for an S with no scored items.")

    trend = trend_frame(history, current if (include_current_in_trend and n_scored) else None, audit_date)
    if trend.empty:
        st.info("Add rows to the audit history table, or score the checklist, to see the trend.")
    else:
        plot(build_trend_fig(trend, target))


def render() -> None:
    st.header("🧹 5S Audit")
    st.caption(SCALE_NOTE)
    sample_data_note("Simulated sample audit of a generic workcell. Edit the checklist and history to use your own audit.")

    c1, c2 = st.columns(2)
    area = c1.text_input("Area audited", value="Workcell A (simulated)", key="fives_area")
    audit_date = c2.date_input("Audit date", value=dt.date.today(), key="fives_date")

    st.subheader("1. Checklist")
    raw = editor(
        sample_checklist(), key="fives_checklist", hide_index=True,
        column_config={
            "S": st.column_config.SelectboxColumn("S", options=S_NAMES, width="small"),
            "Check item": st.column_config.TextColumn("Check item", width="large"),
            "Score": st.column_config.NumberColumn("Score (0-4)", min_value=0, max_value=4, step=1, width="small"),
        },
    )
    clean, issues_a = clean_checklist(raw)

    st.subheader("2. Earlier audits (score % per S)")
    raw_hist = editor(
        sample_history(), key="fives_history", hide_index=True,
        column_config={
            "Audit date": st.column_config.DateColumn("Audit date", format="YYYY-MM-DD"),
            **{s: st.column_config.NumberColumn(s, min_value=0, max_value=100, step=1, format="%.0f") for s in S_NAMES},
        },
    )
    history, issues_b = clean_history(raw_hist)
    _report_issues(issues_a + issues_b)

    i1, i2 = st.columns(2)
    target = i1.number_input("Target score (%)", min_value=0, max_value=100, value=80, step=5, key="fives_target")
    include = i2.checkbox("Add the current audit to the trend chart", value=True, key="fives_include")

    st.subheader("3. Results")
    show_results(clean, history, area.strip(), audit_date, float(target), include)
