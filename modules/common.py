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


def table(df: pd.DataFrame, **kwargs) -> None:
    """Read-only table, full width, no index (works on old and new Streamlit)."""
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kwargs)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)


def report_issues(issues: list[str], limit: int = 10) -> None:
    """Expander listing data-cleaning notes (excluded rows, ignored values). Shows nothing when empty."""
    if not issues:
        return
    with st.expander(f"⚠️ {len(issues)} data note(s): some entries were excluded or ignored", expanded=True):
        for msg in issues[:limit]:
            st.markdown(f"- {msg}")
        if len(issues) > limit:
            st.markdown(f"- …and {len(issues) - limit} more.")


def white_card(fig: go.Figure, ink: str = "#1a1a1a") -> go.Figure:
    """White background with explicit dark text, so a chart reads the same in light and dark Streamlit themes.

    Streamlit's dark theme sets tick, title and legend font colours itself, which override ``axis.color``;
    they have to be set explicitly.
    """
    fig.update_layout(paper_bgcolor="white", plot_bgcolor="white", font={"color": ink}, title_font_color=ink,
                      legend_font_color=ink)
    fig.update_xaxes(color=ink, tickfont={"color": ink}, title_font={"color": ink}, gridcolor="#e6e6e6")
    fig.update_yaxes(color=ink, tickfont={"color": ink}, title_font={"color": ink}, gridcolor="#e6e6e6")
    return fig


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


def add_rule_markers(fig: go.Figure, x, y, violations: dict) -> None:
    """Overlay markers on a control chart for points flagged by the run and trend rules.

    ``violations`` is the output of ``spc_utils.run_rule_violations`` (0-based positions).
    Rule 1 points (beyond the limits) are drawn by ``control_chart`` itself.
    """
    x = list(x)
    y = list(y)
    styles = {
        "run": ("Run on one side of CL", ORANGE, "diamond-open"),
        "trend": ("Trend", PURPLE, "triangle-up-open"),
    }
    for key, (name, color, symbol) in styles.items():
        idx = violations.get(key, [])
        if idx:
            fig.add_trace(
                go.Scatter(
                    x=[x[i] for i in idx],
                    y=[y[i] for i in idx],
                    mode="markers",
                    name=name,
                    marker=dict(color=color, size=13, symbol=symbol, line=dict(width=2)),
                )
            )


def report_rules(chart_label: str, violations: dict, x, run_length: int, trend_length: int, what: str = "Subgroup") -> None:
    """Warning banners for run and trend rule violations, one range per run or trend."""
    x = list(x)

    def span(a: int, b: int) -> str:
        return f"{x[a]}" if a == b else f"{x[a]}–{x[b]}"

    messages = [
        ("run_segments", f"{run_length}+ points in a row on one side of the centerline", "a sustained shift in the process level"),
        ("trend_segments", f"{trend_length}+ points in a row steadily rising or falling", "a drift, such as tool wear or a warming machine"),
    ]
    for key, rule_text, meaning in messages:
        segs = violations.get(key, [])
        if segs:
            where = ", ".join(span(a, b) for a, b in segs)
            st.warning(f"⚠️ **{chart_label}: {rule_text}.** {what}(s) {where}. This can indicate {meaning}.")
