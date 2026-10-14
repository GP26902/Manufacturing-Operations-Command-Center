"""Shared UI helpers: chart rendering, editors, and a reusable control-chart builder."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BLUE, ORANGE, GREEN, RED, PURPLE = "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"


def plot(fig: go.Figure) -> None:
    """Render a Plotly figure full-width (works on old and new Streamlit)."""
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)


def editor(df: pd.DataFrame, key: str, **kwargs) -> pd.DataFrame:
    """Editable table, full width. Returns the user's edited DataFrame."""
    try:
        return st.data_editor(df, key=key, width="stretch", num_rows="dynamic", **kwargs)
    except TypeError:
        return st.data_editor(df, key=key, use_container_width=True, num_rows="dynamic", **kwargs)


def sample_data_note(text: str = "Sample data shown for illustration. Edit the table to use your own numbers.") -> None:
    st.caption(f"ℹ️ {text}")


def control_chart(
    x,
    y,
    center: float,
    ucl,
    lcl,
    title: str,
    y_title: str,
    x_title: str = "Subgroup",
    color: str = BLUE,
    center_label: str = "CL",
    spec_lines: dict | None = None,
) -> tuple[go.Figure, list]:
    """Build a control chart; points beyond limits are drawn in red.

    ``ucl``/``lcl`` may be scalars or per-point sequences (variable-n charts).
    Returns the figure and the list of out-of-control x values.
    """
    y = pd.Series(list(y), index=range(len(y)), dtype=float)
    x = list(x)
    ucl_s = pd.Series([ucl] * len(y)) if pd.api.types.is_scalar(ucl) else pd.Series(list(ucl))
    lcl_s = pd.Series([lcl] * len(y)) if pd.api.types.is_scalar(lcl) else pd.Series(list(lcl))
    ooc = (y > ucl_s) | (y < lcl_s)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Data", line=dict(color=color)))
    if ooc.any():
        fig.add_trace(
            go.Scatter(
                x=[x[i] for i in ooc[ooc].index],
                y=y[ooc],
                mode="markers",
                name="Out of control",
                marker=dict(color=RED, size=12, symbol="x"),
            )
        )
    fig.add_trace(go.Scatter(x=x, y=[center] * len(x), mode="lines", name=center_label, line=dict(color=GREEN)))
    fig.add_trace(go.Scatter(x=x, y=ucl_s, mode="lines", name="UCL", line=dict(color=RED, dash="dash"), line_shape="hv"))
    if (lcl_s != 0).any():
        fig.add_trace(go.Scatter(x=x, y=lcl_s, mode="lines", name="LCL", line=dict(color=RED, dash="dash"), line_shape="hv"))
    for label, val in (spec_lines or {}).items():
        fig.add_hline(y=val, line_dash="dot", line_color=PURPLE, annotation_text=f"{label}: {val:.3f}")
    fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title, height=380, legend=dict(orientation="h", y=-0.25))
    return fig, [x[i] for i in ooc[ooc].index]


def report_ooc(chart_label: str, ooc_points: list, what: str = "Subgroup") -> None:
    """Standard success/error banner for a control chart."""
    if ooc_points:
        st.error(f"⚠️ **{chart_label}: out of control.** {what}(s) {ooc_points} fall outside the control limits. Investigate for special causes.")
    else:
        st.success(f"✅ **{chart_label}:** no points beyond the control limits.")
