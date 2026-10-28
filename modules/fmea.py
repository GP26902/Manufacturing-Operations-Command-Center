"""FMEA (Design / Process) using the classic RPN method.

Pure calculation and figure functions come first (no Streamlit calls) so they can be unit-tested.
The Streamlit page is at the bottom: ``render()`` builds the inputs, ``show_results()`` draws the output.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, RED, editor, plot, sample_data_note, table

SEVERITY_FLAG = 9
RATING_MIN, RATING_MAX = 1, 10
MAX_RPN = RATING_MAX**3

MODES = {"DFMEA": "Design FMEA (DFMEA)", "PFMEA": "Process FMEA (PFMEA)"}
ITEM_LABEL = {"DFMEA": "Component / function", "PFMEA": "Process step"}

TEXT_COLS = ["Item", "Failure mode", "Effect", "Cause", "Current controls", "Recommended action"]
BASE_COLS = ["Severity", "Occurrence", "Detection"]
NEW_COLS = ["New Severity", "New Occurrence", "New Detection"]
CLEAN_COLS = ["ID", *TEXT_COLS, *BASE_COLS, "RPN", "High severity", *NEW_COLS, "New RPN"]

METHOD_NOTE = (
    "This tool uses the classic RPN method: RPN = Severity x Occurrence x Detection, each rated 1 to 10. "
    "It does not use the AIAG-VDA Action Priority tables. RPN has known limits: different S/O/D combinations "
    f"can give the same RPN, and the product treats ordinal ratings as if they were numbers. Any failure mode "
    f"with Severity >= {SEVERITY_FLAG} is therefore flagged regardless of its RPN."
)

SCALE_NOTE = """
Generic orientation only. Replace with your organisation's own rating scales.

| Rating | Severity | Occurrence | Detection |
|---|---|---|---|
| 1 | No noticeable effect | Failure very unlikely | Current controls almost certain to detect it |
| 5 | Moderate effect: rework, customer dissatisfied | Occasional failures | Controls have a moderate chance of detecting it |
| 9-10 | Safety or regulatory consequence | Failure very likely | Controls unlikely to detect it, or none exist |

Detection is rated so that a higher number is worse (harder to detect).
"""


# ---------------------------------------------------------------------------
# Sample data (simulated, generic)
# ---------------------------------------------------------------------------
def sample_table(mode: str) -> pd.DataFrame:
    """Simulated sample rows for the editor. Column order follows a typical FMEA worksheet."""
    item = ITEM_LABEL[mode]
    if mode == "DFMEA":
        rows = [
            ("Drive shaft", "Fatigue fracture", "Loss of drive, stoppage", 9, "Stress concentration at keyway radius", 3,
             "FEA review, prototype fatigue test", 4, "Increase keyway radius; shot-peen shaft", 9, 2, 4),
            ("Shaft seal", "Seal leakage", "Fluid loss, contamination", 6, "Seal material not compatible with fluid", 4,
             "Material compatibility chart", 5, "Run supplier compatibility test", 6, 2, 3),
            ("Bearing", "Premature wear", "Noise, vibration", 7, "Lubricant not retained in housing", 5,
             "Design review", 6, "Add grease reservoir; accelerated life test", 7, 3, 4),
            ("Housing", "Crack at mounting boss", "Misalignment, leak", 8, "Wall thickness too small", 3,
             "FEA stress review", 5, "Increase wall thickness at boss", 8, 2, 5),
            ("Fastener joint", "Preload loss", "Joint loosens in service", 7, "Embedment, no locking feature", 5,
             "Torque specification", 7, "Add locking feature; preload test", 7, 3, 4),
            ("Temperature sensor", "Reading drifts", "Overheating not detected", 9, "Sensor mounted near heat source", 4,
             "Calibration at assembly", 6, "Relocate sensor; add plausibility check", 9, 2, 3),
            ("Cover", "Surface scratch", "Cosmetic complaint", 2, "Sharp edge on packaging", 5,
             "Visual check", 3, None, None, None, None),
        ]
    else:
        rows = [
            ("Drilling", "Hole oversize", "Fastener loose, rework or scrap", 6, "Worn drill bit", 5,
             "Tool-life counter", 4, "Change tool on hole-count interval", 6, 3, 4),
            ("Drilling", "Hole position off", "Assembly interference", 7, "Fixture clamp not seated", 4,
             "Visual check at setup", 6, "Add locating pin (poka-yoke)", 7, 2, 3),
            ("Fastener torque", "Under-torque", "Joint loosens in service", 8, "Torque tool calibration drift", 4,
             "Monthly calibration", 5, "Torque tool with angle monitoring", 8, 3, 2),
            ("Fastener torque", "Fastener missing", "Parts separate in service", 9, "Step omitted by operator", 2,
             "Final visual inspection", 3, "Add fastener-count sensor", 9, 2, 2),
            ("Seal installation", "Seal damaged", "Leak at test", 7, "Burr on bore edge", 5,
             "End-of-line leak test", 3, "Add deburr check before seal fit", 7, 2, 3),
            ("Seal installation", "Wrong seal fitted", "Leak or field failure", 8, "Similar part numbers in adjacent bins", 3,
             "Part number on tray label", 6, "Separate bins; barcode scan", 8, 2, 2),
            ("Cleaning", "Chips left in cavity", "Contamination, wear", 9, "Wash cycle too short", 4,
             "Cleanliness spot check", 5, "Extend cycle; add cleanliness test", 9, 2, 3),
            ("Final inspection", "Out-of-tolerance part not detected", "Nonconforming part shipped", 6, "Gauge not zeroed", 3,
             "Daily gauge check", 5, None, None, None, None),
        ]
    cols = [item, "Failure mode", "Effect", "Severity", "Cause", "Occurrence", "Current controls", "Detection",
            "Recommended action", *NEW_COLS]
    out = pd.DataFrame(rows, columns=cols)
    for c in BASE_COLS:
        out[c] = out[c].astype(float)
    for c in NEW_COLS:
        out[c] = out[c].astype(float)
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
    return "" if _is_blank(value) else str(value).strip()


def to_rating(value) -> float:
    """Return the value as a float if it is a whole number from 1 to 10, otherwise NaN."""
    if _is_blank(value):
        return np.nan
    try:
        x = float(value.strip()) if isinstance(value, str) else float(value)
    except (TypeError, ValueError):
        return np.nan
    if not math.isfinite(x) or x != round(x) or x < RATING_MIN or x > RATING_MAX:
        return np.nan
    return x


def rpn(severity: float, occurrence: float, detection: float) -> int:
    return int(round(severity * occurrence * detection))


def empty_clean() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in CLEAN_COLS})


def clean_fmea(raw, mode: str = "PFMEA") -> tuple[pd.DataFrame, list[str]]:
    """Turn the editor table into an analysis table. Never raises on bad cell values.

    Rows with a missing or invalid Severity, Occurrence or Detection are excluded and reported.
    Revised ratings are optional; incomplete or invalid ones are ignored and reported.
    Row numbers in messages count from the top of the table as shown (1-based).
    """
    issues: list[str] = []
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return empty_clean(), issues

    item_label = ITEM_LABEL.get(mode, "Item")
    records = []
    for pos, rec in enumerate(raw.to_dict("records"), start=1):
        item = _text(rec.get(item_label, rec.get("Item")))
        texts = {
            "Item": item,
            "Failure mode": _text(rec.get("Failure mode")),
            "Effect": _text(rec.get("Effect")),
            "Cause": _text(rec.get("Cause")),
            "Current controls": _text(rec.get("Current controls")),
            "Recommended action": _text(rec.get("Recommended action")),
        }
        base_raw = [rec.get(c) for c in BASE_COLS]
        new_raw = [rec.get(c) for c in NEW_COLS]
        if all(not v for v in texts.values()) and all(_is_blank(v) for v in base_raw + new_raw):
            continue  # fully blank row

        name = texts["Failure mode"] or item or "no description"
        base = [to_rating(v) for v in base_raw]
        bad = [c for c, v in zip(BASE_COLS, base) if np.isnan(v)]
        if bad:
            issues.append(
                f"Row {pos} ({name}): {', '.join(bad)} missing or not a whole number from {RATING_MIN} to {RATING_MAX}. "
                "Row excluded from the analysis."
            )
            continue

        new = [np.nan, np.nan, np.nan]
        new_rpn = np.nan
        if not all(_is_blank(v) for v in new_raw):
            parsed = [to_rating(v) for v in new_raw]
            if any(np.isnan(v) for v in parsed):
                issues.append(f"Row {pos} ({name}): revised ratings incomplete or invalid. Revised ratings ignored.")
            else:
                new = parsed
                new_rpn = float(rpn(*parsed))

        records.append(
            {
                **texts,
                "Severity": base[0],
                "Occurrence": base[1],
                "Detection": base[2],
                "RPN": float(rpn(*base)),
                "High severity": bool(base[0] >= SEVERITY_FLAG),
                "New Severity": new[0],
                "New Occurrence": new[1],
                "New Detection": new[2],
                "New RPN": new_rpn,
            }
        )

    if not records:
        return empty_clean(), issues

    df = pd.DataFrame(records)
    df.insert(0, "ID", [f"F{i}" for i in range(1, len(df) + 1)])
    for c in ["Severity", "Occurrence", "Detection", "RPN"]:
        df[c] = df[c].astype(int)
    repeats = int(df.duplicated(subset=["Item", "Failure mode", "Cause"]).sum())
    if repeats:
        issues.append(
            f"{repeats} row(s) repeat an earlier item / failure mode / cause combination. "
            "They are kept and counted separately; remove them if they are not intended."
        )
    return df[CLEAN_COLS], issues


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def cap_default(default: float, max_value: float) -> float:
    """Never let a number-input default exceed its (possibly dynamic) maximum."""
    return min(default, max_value)


def review_status(severity: float, rpn_value: float, threshold: float) -> str:
    high_s = severity >= SEVERITY_FLAG
    high_r = rpn_value >= threshold
    if high_s and high_r:
        return f"Severity >= {SEVERITY_FLAG} and RPN >= threshold"
    if high_s:
        return f"Severity >= {SEVERITY_FLAG}"
    if high_r:
        return "RPN >= threshold"
    return "Monitor"


def with_status(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    out = df.copy()
    out["Review"] = [review_status(s, r, threshold) for s, r in zip(out["Severity"], out["RPN"])]
    return out


def label_for(row, width: int = 30) -> str:
    mode_text = row["Failure mode"] or row["Item"] or "(unnamed)"
    mode_text = mode_text if len(mode_text) <= width else mode_text[: width - 1] + "…"
    return f"{row['ID']} {mode_text}"


def pareto_table(df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    """Failure modes sorted by RPN (ties: higher severity first). Cumulative % is of the total over all rows."""
    if df.empty:
        return df.assign(**{"Cumulative %": pd.Series(dtype=float), "Label": pd.Series(dtype=object)})
    out = df.sort_values(["RPN", "Severity"], ascending=[False, False], kind="stable").copy()
    total = out["RPN"].sum()
    out["Cumulative %"] = out["RPN"].cumsum() / total * 100 if total > 0 else 0.0
    out["Label"] = out.apply(label_for, axis=1)
    if top_n is not None:
        out = out.head(max(int(top_n), 1))
    return out


def summary(df: pd.DataFrame, threshold: float) -> dict:
    if df.empty:
        return {"n": 0, "max_rpn": 0, "max_id": "", "n_high_severity": 0, "n_over_threshold": 0,
                "paired_before": 0, "paired_after": 0, "paired_n": 0, "reduction_pct": np.nan, "n_increased": 0}
    top = df.sort_values(["RPN", "Severity"], ascending=False, kind="stable").iloc[0]
    paired = df[df["New RPN"].notna()]
    before = float(paired["RPN"].sum())
    after = float(paired["New RPN"].sum())
    return {
        "n": int(len(df)),
        "max_rpn": int(top["RPN"]),
        "max_id": str(top["ID"]),
        "n_high_severity": int(df["High severity"].sum()),
        "n_over_threshold": int((df["RPN"] >= threshold).sum()),
        "paired_n": int(len(paired)),
        "paired_before": before,
        "paired_after": after,
        "reduction_pct": (before - after) / before * 100 if before > 0 else np.nan,
        "n_increased": int((paired["New RPN"] > paired["RPN"]).sum()),
    }


def so_cells(df: pd.DataFrame) -> dict[tuple[int, int], list[str]]:
    """Map (severity, occurrence) to the list of failure-mode IDs in that cell."""
    cells: dict[tuple[int, int], list[str]] = {}
    for _, r in df.iterrows():
        cells.setdefault((int(r["Severity"]), int(r["Occurrence"])), []).append(str(r["ID"]))
    return cells


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def build_pareto_fig(df: pd.DataFrame, threshold: float, top_n: int | None = None) -> go.Figure:
    p = pareto_table(df, top_n)
    labels = list(p["Label"])
    flagged = list(p["High severity"])
    rpns = list(p["RPN"])
    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=labels, y=[v if not f else None for v, f in zip(rpns, flagged)], name=f"Severity < {SEVERITY_FLAG}",
               marker_color=BLUE, hovertemplate="%{x}<br>RPN %{y}<extra></extra>")
    )
    fig.add_trace(
        go.Bar(x=labels, y=[v if f else None for v, f in zip(rpns, flagged)], name=f"Severity >= {SEVERITY_FLAG} (flagged)",
               marker_color=RED, hovertemplate="%{x}<br>RPN %{y}<extra></extra>")
    )
    fig.add_trace(
        go.Scatter(x=labels, y=list(p["Cumulative %"]), name="Cumulative % of total RPN", yaxis="y2",
                   mode="lines+markers", line=dict(color=ORANGE), hovertemplate="%{y:.0f}%<extra></extra>")
    )
    top = max([*rpns, threshold, 1])
    fig.add_hline(y=threshold, line_dash="dot", line_color=GREEN, annotation_text=f"Review threshold: {threshold:g}")
    fig.update_layout(
        title="RPN Pareto (failure modes ranked by RPN)",
        barmode="overlay",
        height=440,
        yaxis=dict(title="RPN", range=[0, top * 1.15]),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105], showgrid=False),
        xaxis=dict(categoryorder="array", categoryarray=labels, tickangle=-35),
        legend=dict(orientation="h", y=-0.45),
    )
    return fig


def build_heatmap_fig(df: pd.DataFrame) -> go.Figure:
    scale = list(range(RATING_MIN, RATING_MAX + 1))
    cells = so_cells(df)
    z, text, hover = [], [], []
    for s in scale:
        z_row, t_row, h_row = [], [], []
        for o in scale:
            ids = cells.get((s, o), [])
            z_row.append(s * o)
            t_row.append(", ".join(ids[:3]) + (f" +{len(ids) - 3}" if len(ids) > 3 else ""))
            names = [
                f"{i}: {df.loc[df['ID'] == i, 'Failure mode'].iloc[0] or '(unnamed)'}" for i in ids
            ]
            h_row.append("<br>".join(names) if names else "No failure modes")
        z.append(z_row)
        text.append(t_row)
        hover.append(h_row)
    fig = go.Figure(
        go.Heatmap(
            x=scale, y=scale, z=z, text=text, customdata=hover, texttemplate="%{text}", textfont=dict(size=11),
            colorscale=[[0, "#c7e9c0"], [0.35, "#ffe08a"], [1, "#e6550d"]], zmin=1, zmax=MAX_RPN // 10,
            colorbar=dict(title="S x O"),
            hovertemplate="Severity %{y}, Occurrence %{x}<br>S x O = %{z}<br>%{customdata}<extra></extra>",
        )
    )
    fig.add_hrect(y0=SEVERITY_FLAG - 0.5, y1=RATING_MAX + 0.5, line=dict(color=RED, width=2, dash="dot"),
                  fillcolor="rgba(0,0,0,0)", annotation_text=f"Severity >= {SEVERITY_FLAG}", annotation_position="top left",
                  annotation_font_color="#7a1a10")
    fig.update_layout(
        title="Severity x Occurrence heat map (cell shading = S x O; labels = failure-mode IDs)",
        xaxis=dict(title="Occurrence", dtick=1), yaxis=dict(title="Severity", dtick=1), height=520,
    )
    return fig


def build_before_after_fig(df: pd.DataFrame) -> go.Figure | None:
    paired = df[df["New RPN"].notna()]
    if paired.empty:
        return None
    paired = paired.sort_values("RPN", ascending=True, kind="stable")
    labels = [label_for(r) for _, r in paired.iterrows()]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=paired["RPN"], name="Current RPN", orientation="h", marker_color=BLUE,
                         text=paired["RPN"], textposition="outside"))
    fig.add_trace(go.Bar(y=labels, x=paired["New RPN"], name="Revised RPN", orientation="h", marker_color=GREEN,
                         text=paired["New RPN"].astype(int), textposition="outside"))
    fig.update_layout(title="RPN before and after recommended actions", barmode="group",
                      height=max(340, 70 * len(paired) + 140), xaxis_title="RPN",
                      xaxis=dict(range=[0, max(float(paired["RPN"].max()), float(paired["New RPN"].max())) * 1.2]),
                      legend=dict(orientation="h", y=-0.2))
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


def _column_config(mode: str) -> dict:
    rating = dict(min_value=RATING_MIN, max_value=RATING_MAX, step=1, format="%d", width="small")
    cc = st.column_config
    return {
        ITEM_LABEL[mode]: cc.TextColumn(ITEM_LABEL[mode]),
        "Severity": cc.NumberColumn("Severity", help="1 to 10", **rating),
        "Occurrence": cc.NumberColumn("Occurrence", help="1 to 10", **rating),
        "Detection": cc.NumberColumn("Detection", help="1 to 10; higher = harder to detect", **rating),
        "New Severity": cc.NumberColumn("New Severity", help="After the action. Leave blank if none.", **rating),
        "New Occurrence": cc.NumberColumn("New Occurrence", **rating),
        "New Detection": cc.NumberColumn("New Detection", **rating),
    }


def show_results(df: pd.DataFrame, mode: str, threshold: float, top_n: int | None = None) -> None:
    """Metrics, flags and charts for an already-cleaned table."""
    if df.empty:
        st.info("Enter at least one complete row (Severity, Occurrence and Detection) to see the analysis.")
        return
    s = summary(df, threshold)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Failure modes analysed", s["n"])
    c2.metric("Highest RPN", s["max_rpn"], help=f"{s['max_id']}")
    c3.metric(f"Severity >= {SEVERITY_FLAG}", s["n_high_severity"])
    c4.metric("RPN >= threshold", s["n_over_threshold"])

    flagged = df[df["High severity"]]
    if len(flagged):
        items = "; ".join(f"{r['ID']} {r['Failure mode'] or r['Item']} (S={r['Severity']}, RPN={r['RPN']})" for _, r in flagged.iterrows())
        st.warning(f"⚠️ **Severity >= {SEVERITY_FLAG} is flagged regardless of RPN:** {items}.")
    if s["n_increased"]:
        st.warning(f"{s['n_increased']} failure mode(s) have a revised RPN higher than the current RPN. Check the revised ratings.")

    tabs = st.tabs(["RPN Pareto", "S x O heat map", "Before / after", "Analysed table"])
    with tabs[0]:
        plot(build_pareto_fig(df, threshold, top_n))
        st.caption("Red bars: Severity >= 9. The threshold line is a team choice; there is no universal RPN limit.")
    with tabs[1]:
        plot(build_heatmap_fig(df))
        st.caption("Shading shows S x O only; Detection is not on this chart. Hover a cell for the failure modes in it.")
    with tabs[2]:
        fig = build_before_after_fig(df)
        if fig is None:
            st.info("Enter all three revised ratings (New Severity, New Occurrence, New Detection) on at least one row.")
        else:
            plot(fig)
            if s["paired_n"]:
                st.caption(
                    f"Rows with revised ratings: {s['paired_n']}. Total RPN {s['paired_before']:.0f} to {s['paired_after']:.0f}"
                    + (f" ({-s['reduction_pct']:+.0f}%)." if not np.isnan(s["reduction_pct"]) else ".")
                )
    with tabs[3]:
        shown = with_status(df, threshold).rename(columns={"Item": ITEM_LABEL.get(mode, "Item")})
        shown = shown.drop(columns=["High severity"])
        table(shown)
        st.download_button(
            "Download analysed table (CSV)", shown.to_csv(index=False).encode("utf-8"),
            file_name=f"{mode.lower()}_analysis.csv", mime="text/csv", key=f"fmea_dl_{mode}",
        )


def _reset(mode: str) -> None:
    key = f"fmea_ver_{mode}"
    st.session_state[key] = st.session_state.get(key, 0) + 1


def render() -> None:
    st.header("⚠️ FMEA: Failure Mode and Effects Analysis")
    mode_label = st.radio("FMEA type", list(MODES.values()), horizontal=True, key="fmea_type")
    mode = next(k for k, v in MODES.items() if v == mode_label)
    if mode == "DFMEA":
        st.markdown("**Design FMEA:** failure modes of components and functions in a product design.")
    else:
        st.markdown("**Process FMEA:** failure modes of manufacturing or assembly steps.")
    st.caption(METHOD_NOTE)
    with st.expander("Rating scale orientation"):
        st.markdown(SCALE_NOTE)

    what = "mechanical sub-assembly" if mode == "DFMEA" else "machining and assembly cell"
    sample_data_note(f"Simulated sample data for a generic {what}. Edit the table or add rows to use your own analysis.")
    ver = st.session_state.get(f"fmea_ver_{mode}", 0)
    raw = editor(sample_table(mode), key=f"fmea_editor_{mode}_{ver}", column_config=_column_config(mode), hide_index=True)
    st.button("Reset to sample data", key=f"fmea_reset_{mode}", on_click=_reset, args=(mode,))

    clean, issues = clean_fmea(raw, mode)
    _report_issues(issues)

    n = len(clean)
    i1, i2 = st.columns(2)
    with i1:
        threshold = st.number_input("RPN review threshold", min_value=1, max_value=MAX_RPN,
                                    value=int(cap_default(100, MAX_RPN)), step=10, key=f"fmea_thr_{mode}",
                                    help="Team-set value. Failure modes at or above it are marked for review.")
    top_n = None
    if n > 1:
        with i2:
            top_n = st.number_input("Failure modes shown in Pareto", min_value=1, max_value=n,
                                    value=int(cap_default(10, n)), step=1, key=f"fmea_top_{mode}_{n}")
    show_results(clean, mode, float(threshold), None if top_n is None else int(top_n))
