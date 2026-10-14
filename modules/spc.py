"""SPC module: variable charts, process capability, attribute charts, hypothesis testing."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from modules import spc_utils as su
from modules.common import BLUE, GREEN, ORANGE, RED, control_chart, editor, plot, report_ooc, sample_data_note


def _default_subgroups(target: float, n: int = 5, k: int = 20) -> pd.DataFrame:
    """Generate raw measurements, then summarise them, so Mean/Range/StdDev are consistent."""
    rng = np.random.default_rng(42)
    raw = rng.normal(target, 0.012, size=(k, n))
    return pd.DataFrame(
        {
            "Subgroup": np.arange(1, k + 1),
            "Mean": raw.mean(axis=1),
            "Range": raw.max(axis=1) - raw.min(axis=1),
            "StdDev": raw.std(axis=1, ddof=1),
        }
    )


def _variable_tab(df: pd.DataFrame, n: int, usl: float, lsl: float) -> None:
    st.markdown("#### Variable Control Charts (X-bar, R, S)")
    charts = st.multiselect(
        "Charts to display:",
        ["X-bar (Process Mean)", "R (Range)", "S (Standard Deviation)"],
        default=["X-bar (Process Mean)", "R (Range)"],
    )
    lim = su.variable_limits(df, n)
    x = df["Subgroup"].tolist()

    if "X-bar (Process Mean)" in charts:
        fig, ooc = control_chart(
            x, df["Mean"], lim["xbarbar"], lim["x_ucl"], lim["x_lcl"],
            "X-bar Chart (Subgroup Means)", "Dimension (mm)", center_label="X̄̄", color=BLUE,
            spec_lines={"USL": usl, "LSL": lsl},
        )
        plot(fig)
        report_ooc("X-bar chart", ooc)
        st.caption(f"UCL = {lim['x_ucl']:.4f}, CL = {lim['xbarbar']:.4f}, LCL = {lim['x_lcl']:.4f}")
    if "R (Range)" in charts:
        fig, ooc = control_chart(
            x, df["Range"], lim["rbar"], lim["r_ucl"], lim["r_lcl"],
            "R Chart (Within-Subgroup Range)", "Range (mm)", center_label="R̄", color=ORANGE,
        )
        plot(fig)
        report_ooc("R chart", ooc)
    if "S (Standard Deviation)" in charts:
        fig, ooc = control_chart(
            x, df["StdDev"], lim["sbar"], lim["s_ucl"], lim["s_lcl"],
            "S Chart (Within-Subgroup Std Dev)", "Std Dev (mm)", center_label="S̄", color=GREEN,
        )
        plot(fig)
        report_ooc("S chart", ooc)
    if not charts:
        st.warning("Select at least one chart.")


def _capability_tab(df: pd.DataFrame, n: int, usl: float, lsl: float) -> None:
    st.markdown("#### Process Capability (from the subgroup data above)")
    lim = su.variable_limits(df, n)
    sigma = su.sigma_within(lim["rbar"], n)
    mean = lim["xbarbar"]
    cap = su.capability(usl, lsl, mean, sigma)

    st.caption(
        f"Process mean = {mean:.4f} mm (grand mean). Within-subgroup σ = R̄/d2 = {sigma:.4f} mm. "
        f"Specs: LSL {lsl:.3f}, USL {usl:.3f} (set at the top of this module)."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Cp (potential)", f"{cap['cp']:.2f}")
    c2.metric("Cpk (actual)", f"{cap['cpk']:.2f}")
    c3.metric("Cpm (Taguchi)", f"{cap['cpm']:.2f}")

    xs = np.linspace(lsl - 3 * sigma, usl + 3 * sigma, 300)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=stats.norm.pdf(xs, mean, sigma), mode="lines", name="Process distribution", fill="tozeroy"))
    fig.add_vline(x=usl, line_dash="dash", line_color=RED, annotation_text="USL")
    fig.add_vline(x=lsl, line_dash="dash", line_color=RED, annotation_text="LSL")
    fig.update_layout(title="Process Distribution vs Specification Limits", xaxis_title="Dimension (mm)", yaxis_title="Density", height=380)
    plot(fig)

    ppm = (stats.norm.cdf(lsl, mean, sigma) + stats.norm.sf(usl, mean, sigma)) * 1e6
    st.write(f"Estimated out-of-spec fraction (normal assumption): **{ppm:,.0f} ppm**")
    if np.isnan(cap["cpk"]):
        st.warning("Enter valid specs (USL > LSL) and data with non-zero spread.")
    elif cap["cpk"] >= 1.33:
        st.success("✅ Cpk ≥ 1.33: the process is capable.")
    elif cap["cpk"] >= 1.0:
        st.warning("⚠️ 1.00 ≤ Cpk < 1.33: marginal. Centering or variation reduction is needed.")
    else:
        st.error("🚨 Cpk < 1.00: the process is not capable of meeting the specs.")
    if cap["cp"] - cap["cpk"] > 0.3:
        st.info("Cp is well above Cpk: the process spread fits the specs but the mean is off-center. Re-centering is the cheapest fix.")
    st.caption("Cp/Cpk use short-term (within-subgroup) sigma. Pp/Ppk require the raw measurements, which are not in this summary table.")


def _attribute_tab() -> None:
    st.markdown("#### Attribute Control Charts (c, u, p, np)")
    if "spc_attr_df" not in st.session_state:
        rng = np.random.default_rng(7)
        k = 20
        st.session_state.spc_attr_df = pd.DataFrame(
            {
                "Lot": np.arange(1, k + 1),
                "Sample Size (n)": [50] * k,
                "Defects (c, u charts)": rng.poisson(4.5, k),
                "Defectives (p, np charts)": rng.binomial(50, 0.08, k),
            }
        )
    sample_data_note("Sample inspection data shown. Edit or add lots to use your own counts.")
    df = editor(st.session_state.spc_attr_df, key="spc_attr_editor").dropna()
    if len(df) < 5:
        st.warning("Enter at least 5 lots to compute meaningful limits.")
        return
    n = df["Sample Size (n)"].to_numpy(dtype=float)
    lots = df["Lot"].tolist()
    sel = st.multiselect(
        "Charts to display:",
        ["c (total nonconformities)", "u (nonconformities per unit)", "p (proportion defective)", "np (number defective)"],
        default=["c (total nonconformities)", "p (proportion defective)"],
    )
    specs = {
        "c": ("c (total nonconformities)", "Defects (c, u charts)", "c-Chart", "Defect count"),
        "u": ("u (nonconformities per unit)", "Defects (c, u charts)", "u-Chart", "Defects per unit"),
        "p": ("p (proportion defective)", "Defectives (p, np charts)", "p-Chart", "Fraction defective"),
        "np": ("np (number defective)", "Defectives (p, np charts)", "np-Chart", "Defective count"),
    }
    for kind, (label, col, title, ytitle) in specs.items():
        if label not in sel:
            continue
        if kind in ("c", "np") and len(set(n)) > 1:
            st.warning(f"{title} assumes a constant sample size. Use the {'u' if kind == 'c' else 'p'}-chart for varying n.")
        res = su.attribute_limits(kind, df[col].to_numpy(), n)
        fig, ooc = control_chart(lots, res["series"], res["cl"], res["ucl"], res["lcl"], title, ytitle, x_title="Lot")
        plot(fig)
        report_ooc(title, ooc, what="Lot")


def _hypothesis_tab() -> None:
    st.markdown("#### Hypothesis Testing: Type I (α) and Type II (β) Risk")
    c1, c2, c3 = st.columns(3)
    shift = c1.slider("Process shift (mean units)", 1.0, 4.0, 2.5, 0.1)
    alpha = c2.slider("Significance level α", 0.01, 0.10, 0.05, 0.01)
    sd = c3.slider("Standard deviation σ", 0.5, 2.0, 1.0, 0.1)

    crit = stats.norm.ppf(1 - alpha, 0, sd)
    beta = stats.norm.cdf(crit, shift, sd)
    x = np.linspace(-3 * sd, shift + 4 * sd, 500)
    h0, h1 = stats.norm.pdf(x, 0, sd), stats.norm.pdf(x, shift, sd)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=h0, mode="lines", name="H0 (in control)", line=dict(color=BLUE)))
    fig.add_trace(go.Scatter(x=x, y=h1, mode="lines", name="H1 (shifted)", line=dict(color=GREEN)))
    m_a = x >= crit
    fig.add_trace(go.Scatter(x=x[m_a], y=h0[m_a], fill="tozeroy", mode="none", name="α (false alarm)", fillcolor="rgba(214,39,40,0.45)"))
    m_b = x <= crit
    fig.add_trace(go.Scatter(x=x[m_b], y=h1[m_b], fill="tozeroy", mode="none", name="β (missed shift)", fillcolor="rgba(255,127,14,0.45)"))
    fig.add_vline(x=crit, line_dash="dash", line_color="crimson", annotation_text="Decision threshold")
    fig.update_layout(title="Risk Regions", xaxis_title="Measurement", yaxis_title="Density", height=400)
    plot(fig)

    m1, m2, m3 = st.columns(3)
    m1.metric("α (false alarm)", f"{alpha:.3f}")
    m2.metric("β (missed shift)", f"{beta:.3f}")
    m3.metric("Power (1 − β)", f"{1 - beta:.3f}")
    st.info("Raising the threshold lowers α but raises β. The only way to cut both is to reduce variation or increase sample size.")


def render() -> None:
    st.subheader("Statistical Process Control & Quality Engineering Suite")

    # Shared process inputs: every tab uses the same data and specs.
    c1, c2, c3 = st.columns(3)
    n = c1.slider("Subgroup size (n) for chart constants", 2, 10, 5, key="spc_n")
    target = c2.number_input("Target mean (mm)", value=10.00, format="%.3f", key="spc_target")
    tol = c3.number_input("Tolerance (± mm)", value=0.035, format="%.3f", min_value=0.001, key="spc_tol")
    usl, lsl = target + tol, target - tol

    if "spc_input_df" not in st.session_state:
        st.session_state.spc_input_df = _default_subgroups(target)
    sample_data_note("Sample subgroup data shown (simulated). Edit the table, paste rows, or add subgroups.")
    df = editor(st.session_state.spc_input_df, key="spc_editor")
    df = df.dropna(subset=["Mean", "Range", "StdDev"]).reset_index(drop=True)

    if len(df) < 5:
        st.warning("Enter at least 5 subgroups to compute control limits.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["Variable charts", "Process capability", "Attribute charts", "Hypothesis testing"])
    with tab1:
        _variable_tab(df, n, usl, lsl)
    with tab2:
        _capability_tab(df, n, usl, lsl)
    with tab3:
        _attribute_tab()
    with tab4:
        _hypothesis_tab()
