"""Pareto defect analysis."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, RED, editor, plot


def pareto_table(df: pd.DataFrame, label_col: str, count_col: str) -> pd.DataFrame:
    """Clean, sort descending and add cumulative % and a vital-few flag.

    A category is 'vital few' if the cumulative share *before* it is below 80%,
    so the category that carries the total past 80% is included.
    """
    d = df.dropna(subset=[label_col]).copy()
    d = d[d[label_col].astype(str).str.strip() != ""]
    d[count_col] = pd.to_numeric(d[count_col], errors="coerce").fillna(0)
    d = d[d[count_col] > 0].sort_values(count_col, ascending=False).reset_index(drop=True)
    total = d[count_col].sum()
    d["Share %"] = d[count_col] / total * 100 if total > 0 else 0.0
    d["Cumulative %"] = d["Share %"].cumsum()
    d["Vital Few"] = (d["Cumulative %"] - d["Share %"]) < 80
    return d


def render() -> None:
    st.subheader("80/20 Pareto Analysis: Defect & Failure Mode Tracking")
    st.markdown("Edit the table; the Pareto chart and the vital-few list update automatically.")
    st.caption("ℹ️ Sample defect data shown for illustration.")

    if "pareto_default" not in st.session_state:
        st.session_state.pareto_default = pd.DataFrame(
            {
                "Defect Category": ["Surface Scratch", "Dimensional Variance", "Porosity / Void",
                                    "Assembly Misalignment", "Flash / Burr", "Electrical Short"],
                "Frequency (Count)": [145, 82, 38, 25, 12, 8],
            }
        )
    edited = editor(st.session_state.pareto_default, key="pareto_editor")
    d = pareto_table(edited, "Defect Category", "Frequency (Count)")
    if d.empty:
        st.warning("⚠️ Add at least one category with a positive count.")
        return

        fig = go.Figure()
    fig.add_trace(go.Bar(x=d["Defect Category"], y=d["Frequency (Count)"], name="Count",
                         marker_color=[RED if v else BLUE for v in d["Vital Few"]]))
    fig.add_trace(go.Scatter(x=d["Defect Category"], y=d["Cumulative %"], name="Cumulative %",
                             mode="lines+markers", line=dict(color="#f5c518", width=3), marker=dict(size=8), yaxis="y2"))
    fig.add_hline(y=80, line_dash="dash", line_color="#9e9e9e", yref="y2", annotation_text="80%")
    fig.update_layout(
        title="Pareto Chart (red = vital few)",
        yaxis=dict(title="Count"),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105], ticksuffix="%"),
        height=430, legend=dict(orientation="h", y=-0.25),
    )
    plot(fig)

    vital = d.loc[d["Vital Few"], "Defect Category"].tolist()
    share = d.loc[d["Vital Few"], "Share %"].sum()
    st.success(f"💡 **Vital few ({len(vital)} of {len(d)} categories, {share:.0f}% of all defects):** {', '.join(vital)}")
