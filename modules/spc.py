"""SPC module: variable charts, process capability, attribute charts, hypothesis testing."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from modules import spc_utils as su
from modules.common import (
    BLUE, GREEN, ORANGE, RED, add_rule_markers, control_chart, editor, plot, report_ooc, report_rules, sample_data_note,
)


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


UPLOAD_WIDE = "One row per subgroup (columns are the measurements)"
UPLOAD_LONG = "One row per measurement (with a subgroup column)"
UPLOAD_SEQ = "Single column of readings in time order"
_LAYOUTS = {"wide": UPLOAD_WIDE, "long": UPLOAD_LONG, "seq": UPLOAD_SEQ}


@dataclass
class Uploaded:
    summary: pd.DataFrame   # Subgroup, Mean, Range, StdDev
    raw: np.ndarray         # every reading, flattened (for Pp/Ppk)
    n: int                  # subgroup size found in the file
    key: str                # identifies the file, so widget defaults reset when it changes


def _lab(base: str, unit: str) -> str:
    return f"{base} ({unit})" if unit else base


def _upload_section() -> Uploaded | None:
    """Optional CSV of raw measurements. Returns None when no (valid) file is loaded."""
    with st.expander("Upload your own measurements (CSV)"):
        st.caption(
            "Upload raw readings and the app computes the subgroup mean, range and standard deviation, "
            "draws the charts, and adds Pp and Ppk. The app does not save your file."
        )
        st.download_button("Download an example CSV (simulated data)", su.example_csv(), file_name="spc_example_subgroups.csv",
                           mime="text/csv", key="spc_example_dl")
        st.caption("The example is simulated around a target of 10.000 with a ±0.035 tolerance, and includes a small shift after subgroup 12.")
        file = st.file_uploader("CSV file", type=["csv", "txt"], key="spc_upload")
        if file is None:
            return None
        data = file.getvalue()
        fid = hashlib.md5(data).hexdigest()[:8]
        try:
            raw_df = su.read_csv_bytes(data)
            cols = list(raw_df.columns)
            guess = su.guess_layout(raw_df)
            layout = st.radio("File layout", list(_LAYOUTS.values()), index=list(_LAYOUTS).index(guess), key=f"spc_layout_{fid}")
            if layout == UPLOAD_WIDE:
                id_guess = su.guess_id_column(raw_df)
                opts = ["(none)"] + cols
                id_col = st.selectbox("Subgroup ID column", opts, index=opts.index(id_guess) if id_guess in opts else 0, key=f"spc_id_{fid}")
                labels, matrix, notes = su.matrix_from_wide(raw_df, None if id_col == "(none)" else id_col)
            elif layout == UPLOAD_LONG:
                g_guess, v_guess = su.guess_long_columns(raw_df)
                g_col = st.selectbox("Subgroup column", cols, index=cols.index(g_guess), key=f"spc_group_{fid}")
                v_col = st.selectbox("Measurement column", cols, index=cols.index(v_guess) if v_guess in cols else 0, key=f"spc_value_{fid}")
                labels, matrix, notes = su.matrix_from_long(raw_df, g_col, v_col)
            else:
                nums = su.numeric_columns(raw_df) or cols
                v_col = st.selectbox("Measurement column", nums, key=f"spc_seqcol_{fid}")
                seq_n = st.number_input("Subgroup size (n)", su.MIN_N, su.MAX_N, 5, 1, key=f"spc_seqn_{fid}")
                labels, matrix, notes = su.matrix_from_sequence(raw_df, v_col, int(seq_n))
        except su.UploadError as exc:
            st.error(f"{exc} Showing the sample data instead.")
            return None
        k, n = matrix.shape
        st.success(f"Loaded {k} subgroups of {n} readings ({k * n:,} measurements).")
        for note in notes:
            st.caption(f"ℹ️ {note}")
        return Uploaded(su.summarize_matrix(labels, matrix), matrix.ravel(), n, fid)


def _show_chart(fig, ooc, x, y, center, label: str, rules: tuple[int, int], what: str = "Subgroup") -> None:
    """Draw a control chart and report Rule 1 (limits), the run rule and the trend rule."""
    run_len, trend_len = rules
    viol = su.run_rule_violations(y, center, run_len, trend_len)
    add_rule_markers(fig, x, y, viol)
    plot(fig)
    report_ooc(label, ooc, what=what)
    report_rules(label, viol, x, run_len, trend_len, what=what)


def _variable_tab(df: pd.DataFrame, n: int, usl: float, lsl: float, rules: tuple[int, int], unit: str = "mm") -> None:
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
            "X-bar Chart (Subgroup Means)", _lab("Dimension", unit), center_label="X̄̄", color=BLUE,
            spec_lines={"USL": usl, "LSL": lsl},
        )
        _show_chart(fig, ooc, x, df["Mean"], lim["xbarbar"], "X-bar chart", rules)
        st.caption(f"UCL = {lim['x_ucl']:.4f}, CL = {lim['xbarbar']:.4f}, LCL = {lim['x_lcl']:.4f}")
    if "R (Range)" in charts:
        fig, ooc = control_chart(
            x, df["Range"], lim["rbar"], lim["r_ucl"], lim["r_lcl"],
            "R Chart (Within-Subgroup Range)", _lab("Range", unit), center_label="R̄", color=ORANGE,
        )
        _show_chart(fig, ooc, x, df["Range"], lim["rbar"], "R chart", rules)
    if "S (Standard Deviation)" in charts:
        fig, ooc = control_chart(
            x, df["StdDev"], lim["sbar"], lim["s_ucl"], lim["s_lcl"],
            "S Chart (Within-Subgroup Std Dev)", _lab("Std Dev", unit), center_label="S̄", color=GREEN,
        )
        _show_chart(fig, ooc, x, df["StdDev"], lim["sbar"], "S chart", rules)
    if not charts:
        st.warning("Select at least one chart.")


def _capability_tab(df: pd.DataFrame, n: int, usl: float, lsl: float, raw: np.ndarray | None = None, unit: str = "mm") -> None:
    st.markdown("#### Process Capability (from the subgroup data above)")
    lim = su.variable_limits(df, n)
    sigma = su.sigma_within(lim["rbar"], n)
    mean = lim["xbarbar"]
    cap = su.capability(usl, lsl, mean, sigma)

    u = f" {unit}" if unit else ""
    st.caption(
        f"Process mean = {mean:.4f}{u} (grand mean). Within-subgroup σ = R̄/d2 = {sigma:.4f}{u}. "
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
    fig.update_layout(title="Process Distribution vs Specification Limits", xaxis_title=_lab("Dimension", unit), yaxis_title="Density", height=380)
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
    if raw is None:
        st.caption("Cp/Cpk use short-term (within-subgroup) sigma. Pp/Ppk require the raw measurements: upload a CSV of raw readings to get them.")
        return
    pp = su.overall_capability(raw, usl, lsl)
    p1, p2, p3 = st.columns(3)
    p1.metric("Pp (overall)", f"{pp['pp']:.2f}")
    p2.metric("Ppk (overall)", f"{pp['ppk']:.2f}")
    p3.metric("Overall σ", f"{pp['sigma']:.4f}{u}", help="Sample standard deviation of all readings together")
    st.caption(
        "Cp/Cpk use short-term (within-subgroup) sigma. Pp/Ppk use the overall sigma of all readings, so they also "
        "include shifts and drift between subgroups. Both assume roughly normal data."
    )
    if not (np.isnan(cap["cpk"]) or np.isnan(pp["ppk"])) and cap["cpk"] - pp["ppk"] > 0.2:
        st.info("Ppk is noticeably below Cpk: variation between subgroups (shifts or drift) is adding to the spread. "
                "Check the control charts for runs and trends.")


def _attribute_tab(rules: tuple[int, int]) -> None:
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
        _show_chart(fig, ooc, lots, res["series"], res["cl"], title, rules, what="Lot")


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

    up = _upload_section()
    unit = "" if up else "mm"

    # Shared process inputs: every tab uses the same data and specs.
    c1, c2, c3 = st.columns(3)
    if up:
        n = up.n
        mean_all, sd_all = float(up.raw.mean()), float(up.raw.std(ddof=1)) if len(up.raw) > 1 else 0.0
        c1.metric("Subgroup size (n), from your file", n)
        target = c2.number_input("Target mean", value=round(mean_all, 4), format="%.4f", key=f"spc_target_{up.key}")
        tol = c3.number_input("Tolerance (±)", value=max(1e-4, round(4 * sd_all, 4)), format="%.4f", min_value=1e-4, key=f"spc_tol_{up.key}")
        st.info(
            "Target and tolerance start as placeholders computed from your data (mean ± 4 standard deviations). "
            "Enter your real specification limits before reading Cp, Cpk, Pp and Ppk."
        )
    else:
        n = c1.slider("Subgroup size (n) for chart constants", 2, 10, 5, key="spc_n")
        target = c2.number_input("Target mean (mm)", value=10.00, format="%.3f", key="spc_target")
        tol = c3.number_input("Tolerance (± mm)", value=0.035, format="%.3f", min_value=0.001, key="spc_tol")
        if n != 5:
            st.caption("The sample data below was generated with subgroups of 5. If you replace it, set n to match your own subgroup size.")
    usl, lsl = target + tol, target - tol

    with st.expander("Run-rule settings (control charts)"):
        st.caption(
            "Besides points beyond the control limits, the charts flag a run of points on one side of the "
            "centerline and a steady trend. Conventions differ (runs are commonly 7, 8 or 9 points; trends 6 or 7), "
            "so the lengths are adjustable."
        )
        r1, r2 = st.columns(2)
        run_len = r1.number_input("Run length (points on one side of CL)", 5, 10, su.DEFAULT_RUN_LENGTH, 1, key="spc_run_len")
        trend_len = r2.number_input("Trend length (points rising or falling)", 5, 8, su.DEFAULT_TREND_LENGTH, 1, key="spc_trend_len")
    rules = (int(run_len), int(trend_len))

    if up:
        st.markdown("##### Subgroup summary from your file")
        st.caption("Mean, range and sample standard deviation of each subgroup, computed from your raw readings.")
        st.dataframe(up.summary, hide_index=True, height=250)
        df = up.summary
    else:
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
        _variable_tab(df, n, usl, lsl, rules, unit)
    with tab2:
        _capability_tab(df, n, usl, lsl, up.raw if up else None, unit)
    with tab3:
        _attribute_tab(rules)
    with tab4:
        _hypothesis_tab()
