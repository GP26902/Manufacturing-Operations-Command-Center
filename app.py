import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Manufacturing Operations Command Center",
    page_icon="🏭",
    layout="wide",
)

# Custom CSS to improve sidebar radio button spacing and readability
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
        padding: 10px 0px;
        font-size: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏭 Operations Hub")
st.sidebar.markdown(
    "An integrated engineering suite built for industrial process control and quality tracking."
)
st.sidebar.markdown("---")

app_mode = st.sidebar.radio(
    "Select Analytical Module",
    [
        "📈 SPC Control Charts",
        "⚙️ OEE Dashboard",
        "📊 Pareto Defects",
        "🔧 Maintenance & MTBF",
        "⚖️ Line Balancing & Studies",
        "📐 Six Sigma: DMAIC Kanban Studio",
    ],
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**Tip:** Use the modular controls inside each tab to toggle custom multi-charts and parameters."
)

# App Header
st.title("🏭 Manufacturing Operations Command Center")
st.markdown(f"Currently viewing: **{app_mode}**")
st.markdown("---")

# ==========================================
# MODULE 1: ADVANCED SPC QUALITY CONTROL
# ==========================================
if app_mode == "📈 SPC Control Charts":
    st.subheader("Statistical Process Control & Quality Engineering Suite")

    spc_mode = st.selectbox(
        "Select SPC Analysis Module:",
        [
            "1. Variable Charts (X-bar, R, & S Charts)",
            "2. Process Capability (Cp, Cpk, Cpm)",
            "3. Attribute Charts (c, u, p, np Charts)",
            "4. Hypothesis Testing & Type I/II Errors",
        ],
    )
    st.markdown("---")

    if spc_mode.startswith("1"):
        st.markdown(
            "#### Variable Control Charts: Manual Data Entry & Automated Insights"
        )

        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
        subgroup_size = col_ctrl1.slider(
            "Subgroup Size (n)", 3, 10, 5, key="spc_n"
        )
        target_mean = col_ctrl2.number_input(
            "Target Mean (mm)", value=10.00, key="spc_target"
        )
        tolerance = col_ctrl3.number_input(
            "Tolerance (± mm)", value=0.10, key="spc_tol"
        )

        usl = target_mean + tolerance
        lsl = target_mean - tolerance

        selected_charts = st.multiselect(
            "Select Variable Charts to Display:",
            [
                "X-bar Chart (Process Mean)",
                "R Chart (Range)",
                "S Chart (Standard Deviation)",
            ],
            default=["X-bar Chart (Process Mean)", "R Chart (Range)"],
        )
        st.markdown("---")

        if "spc_input_df" not in st.session_state:
            np.random.seed(42)
            default_means = np.random.normal(target_mean, 0.012, 20)
            default_ranges = np.random.uniform(0.02, 0.05, 20)
            default_sds = np.random.uniform(0.008, 0.02, 20)
            st.session_state.spc_input_df = pd.DataFrame(
                {
                    "Subgroup": np.arange(1, 21),
                    "Mean": default_means,
                    "Range": default_ranges,
                    "StdDev": default_sds,
                }
            )

        st.markdown(
            "**Subgroup Data Table:** Edit the values below to update the control charts and summary boxes in real-time."
        )
        edited_df = st.data_editor(
            st.session_state.spc_input_df,
            num_rows="dynamic",
            use_container_width=True,
            key="subgroup_data_editor",
        )

        df_spc = edited_df
        grand_mean = df_spc["Mean"].mean()
        mean_range = df_spc["Range"].mean()
        mean_s = df_spc["StdDev"].mean()

        a2_table = {
            2: 1.880,
            3: 1.023,
            4: 0.729,
            5: 0.577,
            6: 0.483,
            7: 0.419,
            8: 0.373,
            9: 0.337,
            10: 0.308,
        }
        d3_table = {
            2: 0,
            3: 0,
            4: 0,
            5: 0,
            6: 0,
            7: 0.076,
            8: 0.136,
            9: 0.184,
            10: 0.223,
        }
        d4_table = {
            2: 3.267,
            3: 2.574,
            4: 2.282,
            5: 2.114,
            6: 2.004,
            7: 1.924,
            8: 1.864,
            9: 1.816,
            10: 1.716,
        }
        b3_table = {
            2: 0,
            3: 0,
            4: 0,
            5: 0,
            6: 0.030,
            7: 0.118,
            8: 0.185,
            9: 0.239,
            10: 0.284,
        }
        b4_table = {
            2: 3.267,
            3: 2.568,
            4: 2.266,
            5: 2.089,
            6: 1.970,
            7: 1.882,
            8: 1.815,
            9: 1.761,
            10: 1.716,
        }

        a2 = a2_table.get(subgroup_size, 0.577)
        d3 = d3_table.get(subgroup_size, 0)
        d4 = d4_table.get(subgroup_size, 2.114)
        b3 = b3_table.get(subgroup_size, 0)
        b4 = b4_table.get(subgroup_size, 2.089)

        ucl_x = grand_mean + a2 * mean_range
        lcl_x = grand_mean - a2 * mean_range
        ucl_r = d4 * mean_range
        lcl_r = d3 * mean_range
        ucl_s = b4 * mean_s
        lcl_s = b3 * mean_s

        st.markdown("---")
        if not selected_charts:
            st.warning("Please select at least one chart from the options above.")
        else:
            for chart_name in selected_charts:
                fig = go.Figure()
                if chart_name == "X-bar Chart (Process Mean)":
                    fig.add_trace(
                        go.Scatter(
                            x=df_spc["Subgroup"],
                            y=df_spc["Mean"],
                            mode="lines+markers",
                            name="Subgroup Mean",
                            line=dict(color="#1f77b4"),
                        )
                    )
                    fig.add_hline(
                        y=grand_mean,
                        line_color="green",
                        annotation_text=f"Centerline: {grand_mean:.3f}",
                    )
                    fig.add_hline(
                        y=ucl_x,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"UCL: {ucl_x:.3f}",
                    )
                    fig.add_hline(
                        y=lcl_x,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"LCL: {lcl_x:.3f}",
                    )
                    fig.add_hline(
                        y=usl,
                        line_dash="dot",
                        line_color="purple",
                        annotation_text=f"USL: {usl:.3f}",
                    )
                    fig.add_hline(
                        y=lsl,
                        line_dash="dot",
                        line_color="purple",
                        annotation_text=f"LSL: {lsl:.3f}",
                    )
                    fig.update_layout(
                        title="X-bar Control Chart (Subgroup Averages vs. Specs)",
                        xaxis_title="Subgroup Index",
                        yaxis_title="Dimension (mm)",
                        height=380,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    above_ucl = df_spc[df_spc["Mean"] > ucl_x][
                        "Subgroup"
                    ].tolist()
                    below_lcl = df_spc[df_spc["Mean"] < lcl_x][
                        "Subgroup"
                    ].tolist()
                    if above_ucl or below_lcl:
                        msg = "⚠️ **Out-of-Control Warning (X-bar):** "
                        if above_ucl:
                            msg += f"Subgroup(s) {above_ucl} exceeded UCL. "
                        if below_lcl:
                            msg += f"Subgroup(s) {below_lcl} dropped below LCL."
                        st.error(msg)
                    else:
                        st.success(
                            "✅ **X-bar Process Summary:** All subgroup means are operating safely within statistical control limits ($\text{UCL}$ and $\text{LCL}$)."
                        )

                elif chart_name == "R Chart (Range)":
                    fig.add_trace(
                        go.Scatter(
                            x=df_spc["Subgroup"],
                            y=df_spc["Range"],
                            mode="lines+markers",
                            name="Range",
                            line=dict(color="#ff7f0e"),
                        )
                    )
                    fig.add_hline(
                        y=mean_range,
                        line_color="green",
                        annotation_text=f"Mean Range: {mean_range:.3f}",
                    )
                    fig.add_hline(
                        y=ucl_r,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"UCL: {ucl_r:.3f}",
                    )
                    if lcl_r > 0:
                        fig.add_hline(
                            y=lcl_r,
                            line_dash="dash",
                            line_color="red",
                            annotation_text=f"LCL: {lcl_r:.3f}",
                        )
                    fig.update_layout(
                        title="R Control Chart (Process Dispersion)",
                        xaxis_title="Subgroup Index",
                        yaxis_title="Range (mm)",
                        height=380,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    r_above_ucl = df_spc[df_spc["Range"] > ucl_r][
                        "Subgroup"
                    ].tolist()
                    if r_above_ucl:
                        st.error(
                            f"⚠️ **Out-of-Control Warning (R Chart):** Subgroup(s) {r_above_ucl} exceeded the range control limit ($\text{UCL}_R$)."
                        )
                    else:
                        st.success(
                            "✅ **R Chart Process Summary:** Within-batch dispersion variation is stable."
                        )

                elif chart_name == "S Chart (Standard Deviation)":
                    fig.add_trace(
                        go.Scatter(
                            x=df_spc["Subgroup"],
                            y=df_spc["StdDev"],
                            mode="lines+markers",
                            name="StdDev",
                            line=dict(color="#2ca02c"),
                        )
                    )
                    fig.add_hline(
                        y=mean_s,
                        line_color="green",
                        annotation_text=f"Mean S: {mean_s:.3f}",
                    )
                    fig.add_hline(
                        y=ucl_s,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"UCL: {ucl_s:.3f}",
                    )
                    if lcl_s > 0:
                        fig.add_hline(
                            y=lcl_s,
                            line_dash="dash",
                            line_color="red",
                            annotation_text=f"LCL: {lcl_s:.3f}",
                        )
                    fig.update_layout(
                        title="S Control Chart (Standard Deviation)",
                        xaxis_title="Subgroup Index",
                        yaxis_title="StdDev (mm)",
                        height=380,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    s_above_ucl = df_spc[df_spc["StdDev"] > ucl_s][
                        "Subgroup"
                    ].tolist()
                    if s_above_ucl:
                        st.error(
                            f"⚠️ **Out-of-Control Warning (S Chart):** Subgroup(s) {s_above_ucl} exceeded standard deviation limits."
                        )
                    else:
                        st.success(
                            "✅ **S Chart Process Summary:** Subgroup standard deviations are consistent."
                        )

                st.markdown("---")

    elif spc_mode.startswith("2"):
        st.markdown("#### Multi-Generation Process Capability Analysis")
        c1, c2, c3 = st.columns(3)
        usl_cap = c1.number_input("Upper Spec Limit (USL)", value=10.05)
        lsl_cap = c2.number_input("Lower Spec Limit (LSL)", value=9.95)
        process_mean = c3.number_input("Process Mean (mu)", value=10.01)

        std_dev = 0.012
        cp = (usl_cap - lsl_cap) / (6 * std_dev)
        cpk = min(
            (usl_cap - process_mean) / (3 * std_dev),
            (process_mean - lsl_cap) / (3 * std_dev),
        )
        target = (usl_cap + lsl_cap) / 2
        cpm = (usl_cap - lsl_cap) / (
            6 * np.sqrt(std_dev**2 + (process_mean - target) ** 2)
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Potential Capability (Cp)", f"{cp:.2f}")
        m2.metric("Actual Capability (Cpk)", f"{cpk:.2f}")
        m3.metric("Taguchi Capability (Cpm)", f"{cpm:.2f}")

        x_vals = np.linspace(lsl_cap - 0.03, usl_cap + 0.03, 200)
        y_vals = stats.norm.pdf(x_vals, process_mean, std_dev)
        fig_cap = go.Figure()
        fig_cap.add_trace(
            go.Scatter(x=x_vals, y=y_vals, mode="lines", name="Distribution")
        )
        fig_cap.add_vline(x=usl_cap, line_dash="dash", line_color="red")
        fig_cap.add_vline(x=lsl_cap, line_dash="dash", line_color="red")
        fig_cap.update_layout(
            title="Process Distribution vs Tolerances", height=380
        )
        st.plotly_chart(fig_cap, use_container_width=True)

        if cpk >= 1.33:
            st.success(
                "✅ **Capability Summary:** Process is highly capable ($C_{pk} \ge 1.33$)."
            )
        else:
            st.warning(
                "⚠️ **Capability Warning:** Process capability is low ($C_{pk} < 1.33$)."
            )

    elif spc_mode.startswith("3"):
        st.markdown(
            "#### Attribute Control Charts (c, u, p, np Charts) & Summaries"
        )

        col_att1, col_att2 = st.columns(2)
        sample_size_attr = col_att1.number_input(
            "Sample Size per Lot (n)", value=50, key="att_n"
        )
        num_lots = col_att2.slider(
            "Number of Inspection Lots", 10, 30, 20, key="att_lots"
        )

        selected_attr = st.multiselect(
            "Select Attribute Charts to Display:",
            [
                "c-Chart (Total Nonconformities)",
                "u-Chart (Nonconformities per Unit)",
                "p-Chart (Proportion Defective)",
                "np-Chart (Number of Defectives)",
            ],
            default=[
                "c-Chart (Total Nonconformities)",
                "u-Chart (Nonconformities per Unit)",
            ],
        )
        st.markdown("---")

        np.random.seed(42)
        samples = np.arange(1, num_lots + 1)
        defects_c = np.random.poisson(lam=4.5, size=num_lots)
        defects_p = np.random.binomial(n=sample_size_attr, p=0.08, size=num_lots)

        if not selected_attr:
            st.warning("Please select at least one attribute chart to display.")
        else:
            for attr in selected_attr:
                fig_attr = go.Figure()

                if attr == "c-Chart (Total Nonconformities)":
                    c_bar = defects_c.mean()
                    ucl_c = c_bar + 3 * np.sqrt(c_bar)
                    lcl_c = max(0, c_bar - 3 * np.sqrt(c_bar))

                    fig_attr.add_trace(
                        go.Scatter(
                            x=samples,
                            y=defects_c,
                            mode="lines+markers",
                            name="Defects Count",
                            line=dict(color="#1f77b4"),
                        )
                    )
                    fig_attr.add_hline(
                        y=c_bar,
                        line_color="green",
                        annotation_text=f"Centerline (c̄): {c_bar:.2f}",
                    )
                    fig_attr.add_hline(
                        y=ucl_c,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"UCL: {ucl_c:.2f}",
                    )
                    fig_attr.add_hline(
                        y=lcl_c,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"LCL: {lcl_c:.2f}",
                    )
                    fig_attr.update_layout(
                        title="c-Chart (Total Nonconformities per Lot)",
                        xaxis_title="Inspection Lot",
                        yaxis_title="Defect Count",
                        height=380,
                    )
                    st.plotly_chart(fig_attr, use_container_width=True)

                    above_ucl = samples[defects_c > ucl_c].tolist()
                    if above_ucl:
                        st.error(
                            f"⚠️ **Out-of-Control Warning (c-Chart):** Lot(s) {above_ucl} exceeded the UCL for nonconformities."
                        )
                    else:
                        st.success(
                            "✅ **c-Chart Summary:** Total nonconformity counts across inspection lots are within statistical control limits."
                        )

                elif attr == "u-Chart (Nonconformities per Unit)":
                    u_vals = defects_c / sample_size_attr
                    u_bar = u_vals.mean()
                    ucl_u = u_bar + 3 * np.sqrt(u_bar / sample_size_attr)
                    lcl_u = max(
                        0, u_bar - 3 * np.sqrt(u_bar / sample_size_attr)
                    )

                    fig_attr.add_trace(
                        go.Scatter(
                            x=samples,
                            y=u_vals,
                            mode="lines+markers",
                            name="Defects per Unit",
                            line=dict(color="#ff7f0e"),
                        )
                    )
                    fig_attr.add_hline(
                        y=u_bar,
                        line_color="green",
                        annotation_text=f"Centerline (ū): {u_bar:.3f}",
                    )
                    fig_attr.add_hline(
                        y=ucl_u,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"UCL: {ucl_u:.3f}",
                    )
                    fig_attr.add_hline(
                        y=lcl_u,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"LCL: {lcl_u:.3f}",
                    )
                    fig_attr.update_layout(
                        title="u-Chart (Nonconformities per Unit)",
                        xaxis_title="Inspection Lot",
                        yaxis_title="Defects / Unit",
                        height=380,
                    )
                    st.plotly_chart(fig_attr, use_container_width=True)

                    u_above = samples[u_vals > ucl_u].tolist()
                    if u_above:
                        st.error(
                            f"⚠️ **Out-of-Control Warning (u-Chart):** Lot(s) {u_above} exceeded the UCL for defects per unit."
                        )
                    else:
                        st.success(
                            "✅ **u-Chart Summary:** Nonconformities per unit are stable and under statistical control."
                        )

                elif attr == "p-Chart (Proportion Defective)":
                    p_vals = defects_p / sample_size_attr
                    p_bar = p_vals.mean()
                    ucl_p = p_bar + 3 * np.sqrt(
                        (p_bar * (1 - p_bar)) / sample_size_attr
                    )
                    lcl_p = max(
                        0,
                        p_bar
                        - 3 * np.sqrt((p_bar * (1 - p_bar)) / sample_size_attr),
                    )

                    fig_attr.add_trace(
                        go.Scatter(
                            x=samples,
                            y=p_vals,
                            mode="lines+markers",
                            name="Proportion Defective",
                            line=dict(color="#2ca02c"),
                        )
                    )
                    fig_attr.add_hline(
                        y=p_bar,
                        line_color="green",
                        annotation_text=f"Centerline (p̄): {p_bar:.3f}",
                    )
                    fig_attr.add_hline(
                        y=ucl_p,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"UCL: {ucl_p:.3f}",
                    )
                    fig_attr.add_hline(
                        y=lcl_p,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"LCL: {lcl_p:.3f}",
                    )
                    fig_attr.update_layout(
                        title="p-Chart (Proportion Defective)",
                        xaxis_title="Inspection Lot",
                        yaxis_title="Fraction Defective",
                        height=380,
                    )
                    st.plotly_chart(fig_attr, use_container_width=True)

                    p_above = samples[p_vals > ucl_p].tolist()
                    if p_above:
                        st.error(
                            f"⚠️ **Out-of-Control Warning (p-Chart):** Lot(s) {p_above} exceeded the proportion defective UCL."
                        )
                    else:
                        st.success(
                            "✅ **p-Chart Summary:** Defective proportions are within acceptable statistical control limits."
                        )

                elif attr == "np-Chart (Number of Defectives)":
                    p_bar_np = (defects_p / sample_size_attr).mean()
                    center_np = sample_size_attr * p_bar_np
                    ucl_np = center_np + 3 * np.sqrt(
                        sample_size_attr * p_bar_np * (1 - p_bar_np)
                    )
                    lcl_np = max(
                        0,
                        center_np
                        - 3
                        * np.sqrt(
                            sample_size_attr * p_bar_np * (1 - p_bar_np)
                        ),
                    )

                    fig_attr.add_trace(
                        go.Scatter(
                            x=samples,
                            y=defects_p,
                            mode="lines+markers",
                            name="Defective Count",
                            line=dict(color="#d62728"),
                        )
                    )
                    fig_attr.add_hline(
                        y=center_np,
                        line_color="green",
                        annotation_text=f"Centerline: {center_np:.2f}",
                    )
                    fig_attr.add_hline(
                        y=ucl_np,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"UCL: {ucl_np:.2f}",
                    )
                    fig_attr.add_hline(
                        y=lcl_np,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"LCL: {lcl_np:.2f}",
                    )
                    fig_attr.update_layout(
                        title="np-Chart (Number of Defective Units)",
                        xaxis_title="Inspection Lot",
                        yaxis_title="Defective Count",
                        height=380,
                    )
                    st.plotly_chart(fig_attr, use_container_width=True)

                    np_above = samples[defects_p > ucl_np].tolist()
                    if np_above:
                        st.error(
                            f"⚠️ **Out-of-Control Warning (np-Chart):** Lot(s) {np_above} exceeded the defective unit count UCL."
                        )
                    else:
                        st.success(
                            "✅ **np-Chart Summary:** Number of defective units per lot is operating within stable control bounds."
                        )

                st.markdown("---")

    else:
        st.markdown("#### Hypothesis Testing & Type I / Type II Errors")

        # Interactive controls for hypothesis testing
        h_col1, h_col2, h_col3 = st.columns(3)
        shift_size = h_col1.slider(
            "Process Shift Magnitude", 1.0, 4.0, 2.5, 0.1, key="hyp_shift"
        )
        alpha_level = h_col2.slider(
            "Significance Level (Alpha)", 0.01, 0.10, 0.05, 0.01, key="hyp_alpha"
        )
        std_dev_hyp = h_col3.slider(
            "Standard Deviation ($\sigma$)", 0.5, 2.0, 1.0, 0.1, key="hyp_std"
        )

        # Calculate critical value based on alpha slider
        crit_val = stats.norm.ppf(1 - alpha_level, loc=0, scale=std_dev_hyp)

        x = np.linspace(-3, 6 + shift_size, 400)
        y_h0 = stats.norm.pdf(x, loc=0, scale=std_dev_hyp)
        y_h1 = stats.norm.pdf(x, loc=shift_size, scale=std_dev_hyp)

        fig_hyp = go.Figure()
        fig_hyp.add_trace(
            go.Scatter(
                x=x,
                y=y_h0,
                mode="lines",
                name="Null Hypothesis (H0)",
                line=dict(color="#1f77b4"),
            )
        )
        fig_hyp.add_trace(
            go.Scatter(
                x=x,
                y=y_h1,
                mode="lines",
                name="Alternative (H1)",
                line=dict(color="#2ca02c"),
            )
        )
        fig_hyp.add_vline(
            x=crit_val,
            line_dash="dash",
            line_color="crimson",
            annotation_text=f"Threshold (α={alpha_level})",
        )
        fig_hyp.update_layout(
            title="Interactive Hypothesis Testing & Risk Regions",
            xaxis_title="Measurement Value",
            yaxis_title="Probability Density",
            height=400,
        )
        st.plotly_chart(fig_hyp, use_container_width=True)
        st.info(
            f"ℹ️ **Hypothesis Insight:** Moving the threshold reduces Alpha risk ($\alpha = {alpha_level}$), but automatically increases Beta risk (missed defects) due to curve overlap."
        )

# ==========================================
# MODULE 2: OEE DASHBOARD
# ==========================================
elif app_mode == "⚙️ OEE Dashboard":
    st.subheader("Overall Equipment Effectiveness (OEE) & Loss Analysis")

    # Time Configuration
    o_col1, o_col2 = st.columns(2)
    total_shift_time = o_col1.number_input(
        "Total Planned Production Time (Minutes)",
        min_value=60,
        max_value=1440,
        value=480,
        step=30,
    )
    planned_stops = o_col2.number_input(
        "Planned Maintenance / Shutdowns (Minutes)",
        min_value=0,
        max_value=240,
        value=30,
        step=10,
    )

    operating_time_available = max(1, total_shift_time - planned_stops)

    st.markdown("---")
    st.markdown("##### ⏱️ Availability Losses (Downtime)")
    d_col1, d_col2 = st.columns(2)
    breakdown_time = d_col1.number_input(
        "Unplanned Breakdowns (Minutes)",
        min_value=0,
        max_value=operating_time_available,
        value=45,
        step=5,
    )
    setup_time = d_col2.number_input(
        "Setup & Adjustments / Changeovers (Minutes)",
        min_value=0,
        max_value=operating_time_available,
        value=30,
        step=5,
    )

    actual_operating_time = max(
        0, operating_time_available - (breakdown_time + setup_time)
    )
    availability = (actual_operating_time / operating_time_available) * 100

    st.markdown("---")
    st.markdown("##### ⚡ Performance Losses (Speed & Minor Stops)")
    p_col1, p_col2 = st.columns(2)
    ideal_cycle_time = p_col1.number_input(
        "Ideal Cycle Time per Unit (Seconds)",
        min_value=0.1,
        max_value=60.0,
        value=1.5,
        step=0.1,
    )
    total_pieces_produced = p_col2.number_input(
        "Total Pieces Produced (Good + Defective)",
        min_value=1,
        max_value=20000,
        value=3500,
        step=100,
    )

    operating_time_sec = actual_operating_time * 60
    theoretical_max_pieces = (
        operating_time_sec / ideal_cycle_time if ideal_cycle_time > 0 else 1
    )
    performance = min(
        100.0, (total_pieces_produced / theoretical_max_pieces) * 100
    )

    st.markdown("---")
    st.markdown("##### 🎯 Quality Losses (Defects)")
    q_col1 = st.columns(1)[0]
    defective_pieces = q_col1.number_input(
        "Defective Pieces / Scrapped Units",
        min_value=0,
        max_value=total_pieces_produced,
        value=105,
        step=5,
    )

    good_pieces = max(0, total_pieces_produced - defective_pieces)
    quality = (
        (good_pieces / total_pieces_produced) * 100
        if total_pieces_produced > 0
        else 0
    )

    # Final OEE calculation
    oee = (availability / 100) * (performance / 100) * (quality / 100) * 100

    # Metrics display
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Availability", f"{availability:.1f}%")
    m2.metric("Performance", f"{performance:.1f}%")
    m3.metric("Quality", f"{quality:.1f}%")
    m4.metric(
        "Overall OEE",
        f"{oee:.1f}%",
        delta=f"{oee - 85.0:.1f}% vs World Class (85%)",
    )

    # Visualization
    fig_oee = go.Figure(
        data=[
            go.Bar(
                x=["Availability", "Performance", "Quality", "Total OEE"],
                y=[availability, performance, quality, oee],
                marker_color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
                text=[
                    f"{availability:.1f}%",
                    f"{performance:.1f}%",
                    f"{quality:.1f}%",
                    f"{oee:.1f}%",
                ],
                textposition="auto",
            )
        ]
    )
    fig_oee.update_layout(
        title="OEE Components Breakdown",
        yaxis_title="Percentage (%)",
        yaxis=dict(range=[0, 105]),
        height=380,
    )
    st.plotly_chart(fig_oee, use_container_width=True)
    st.success(
        f"✅ **OEE Insight:** Operating time: {actual_operating_time} mins | Good Units: {good_pieces} / {total_pieces_produced}. World-class manufacturing typically aims for an OEE benchmark of 85% or higher."
    )

# ==========================================
# MODULE 3: 80/20 PARETO DEFECT ANALYSIS
# ==========================================
elif app_mode == "📊 Pareto Defects":
    st.subheader("80/20 Pareto Analysis – Defect & Failure Mode Tracking")
    st.markdown("Enter your defect categories and counts in the table below. The Pareto chart and cumulative impact curve will update automatically.")

    import pandas as pd
    import plotly.graph_objects as go

    # Initialize session state for editable Pareto data if it doesn't exist
    if "pareto_data" not in st.session_state:
        st.session_state.pareto_data = pd.DataFrame(
            {
                "Defect Category": [
                    "Surface Scratch",
                    "Dimensional Variance",
                    "Porosity / Void",
                    "Assembly Misalignment",
                    "Flash / Burr",
                    "Electrical Short",
                ],
                "Frequency (Count)": [145, 82, 38, 25, 12, 8],
            }
        )

    # Interactive data editor for user inputs
    edited_pareto_df = st.data_editor(
        st.session_state.pareto_data,
        num_rows="dynamic",
        use_container_width=True,
        key="pareto_editor_mod",
    )

    # Save changes back to session state
    st.session_state.pareto_data = edited_pareto_df

    # Clean the dataframe to ignore blank rows or NaN counts from the dynamic editor
    cleaned_df = edited_pareto_df.dropna(subset=["Defect Category"]).copy()
    cleaned_df = cleaned_df[
        cleaned_df["Defect Category"].astype(str).str.strip() != ""
    ]
    cleaned_df["Frequency (Count)"] = pd.to_numeric(
        cleaned_df["Frequency (Count)"], errors="coerce"
    ).fillna(0)
    cleaned_df = cleaned_df[cleaned_df["Frequency (Count)"] > 0]

    if not cleaned_df.empty:
        # Sort data descending by frequency for Pareto logic
        df_sorted = cleaned_df.sort_values(
            by="Frequency (Count)", ascending=False
        ).reset_index(drop=True)
        
        # (Keep the rest of your chart building code using df_sorted here...)

        # Calculate cumulative metrics
        df_sorted["Cumulative Sum"] = df_sorted["Frequency (Count)"].cumsum()
        total_defects = df_sorted["Frequency (Count)"].sum()
        df_sorted["Cumulative Percentage"] = (
            df_sorted["Cumulative Sum"] / total_defects
        ) * 100 if total_defects > 0 else 0

        # Build Dual-Axis Plotly Pareto Chart
        fig_pareto = go.Figure()

        # Bar chart for individual defect frequencies
        fig_pareto.add_trace(
            go.Bar(
                x=df_sorted["Defect Category"],
                y=df_sorted["Frequency (Count)"],
                name="Defect Count",
                marker_color="#1f77b4",
                yaxis="y",
            )
        )

        # Line chart for cumulative percentage curve
        fig_pareto.add_trace(
            go.Scatter(
                x=df_sorted["Defect Category"],
                y=df_sorted["Cumulative Percentage"],
                name="Cumulative %",
                marker_color="#d62728",
                mode="lines+markers",
                yaxis="y2",
            )
        )

        # Add 80% threshold reference line
        fig_pareto.add_shape(
            type="line",
            x0=-0.5,
            x1=len(df_sorted) - 0.5,
            y0=80,
            y1=80,
            line=dict(color="orange", dash="dash", width=2),
            yref="y2",
        )

        # Layout configuration for dual axes
        fig_pareto.update_layout(
            title="Pareto Chart: Defect Frequency & Cumulative Impact",
            xaxis=dict(title="Defect Category"),
            yaxis=dict(title="Frequency / Count", side="left"),
            yaxis2=dict(
                title="Cumulative Percentage (%)",
                overlaying="y",
                side="right",
                range=[0, 105],
                ticksuffix="%",
            ),
            height=430,
            legend=dict(x=0.55, y=1.12, orientation="h"),
        )

        st.plotly_chart(fig_pareto, use_container_width=True)

        # Automated insight highlight
        vital_few = df_sorted[df_sorted["Cumulative Percentage"] <= 80][
            "Defect Category"
        ].tolist()
        st.success(
            f"💡 **Pareto Insight:** The 'Vital Few' categories driving up to 80% of quality losses are: **{', '.join(vital_few) if vital_few else 'None'}**."
        )
    else:
        st.warning("⚠️ Please add at least one row in the table above to generate the Pareto analysis chart.")

# ==========================================
# MODULE 4: MAINTENANCE & MTBF
# ==========================================
elif app_mode == "🔧 Maintenance & MTBF":
    st.subheader("Equipment Reliability & Maintenance (MTBF / MTTR)")
    st.markdown("Track asset reliability, failure rates, and maintenance downtime metrics to optimize servicing schedules.")

    import pandas as pd
    import plotly.graph_objects as go

    # Input parameters for reliability
    m_col1, m_col2, m_col3 = st.columns(3)
    total_operating_hours = m_col1.number_input(
        "Total Period Operating Hours", min_value=100, max_value=8760, value=720, step=24
    )
    total_failures = m_col2.number_input(
        "Total Number of Failures (Breakdowns)", min_value=0, max_value=100, value=6, step=1
    )
    total_repair_time = m_col3.number_input(
        "Total Downtime / Repair Time (Hours)", min_value=0.0, max_value=500.0, value=18.0, step=1.0
    )

    # Reliability calculations
    mtbf = total_operating_hours / total_failures if total_failures > 0 else total_operating_hours
    mttr = total_repair_time / total_failures if total_failures > 0 else 0.0
    availability_maint = (total_operating_hours / (total_operating_hours + total_repair_time)) * 100 if (total_operating_hours + total_repair_time) > 0 else 100.0
    failure_rate = (total_failures / total_operating_hours) * 1000 if total_operating_hours > 0 else 0.0 # Failures per 1000 hours

    # Metrics display
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("MTBF", f"{mtbf:.1f} hrs", help="Mean Time Between Failures")
    r2.metric("MTTR", f"{mttr:.1f} hrs", help="Mean Time To Repair")
    r3.metric("Asset Availability", f"{availability_maint:.1f}%")
    r4.metric("Failure Rate", f"{failure_rate:.2f}", help="Failures per 1,000 operating hours")

    # Visualizing Reliability / MTBF trend or breakdown
    fig_maint = go.Figure(
        data=[
            go.Bar(
                x=["Operating Time", "Repair Downtime"],
                y=[total_operating_hours, total_repair_time],
                marker_color=["#2ca02c", "#d62728"],
                text=[f"{total_operating_hours} hrs", f"{total_repair_time} hrs"],
                textposition="auto",
            )
        ]
    )
    fig_maint.update_layout(
        title="Time Allocation: Uptime vs Downtime",
        yaxis_title="Hours",
        height=380,
    )
    st.plotly_chart(fig_maint, use_container_width=True)

    st.success(
        f"💡 **Maintenance Insight:** With an MTBF of **{mtbf:.1f} hours** and an MTTR of **{mttr:.1f} hours**, your asset availability stands at **{availability_maint:.1f}%**. Focus on reducing MTTR through standardizing rapid-changeover spare parts."
    )

# ==========================================
# MODULE 5: Line Balancing & Studies
# ==========================================    
elif app_mode == "⚖️ Line Balancing & Studies":
    st.subheader("Line Balancing & Time Study Analysis")
    st.markdown(
        "Input your shift operating parameters and workstation cycle times below. The model automatically calculates Takt time, identifies bottlenecks, and evaluates line efficiency."
    )

    import pandas as pd
    import plotly.graph_objects as go

    # Shift & Customer Demand Configuration
    lc1, lc2 = st.columns(2)
    net_available_time = lc1.number_input(
        "Net Available Operating Time per Shift (Seconds)",
        min_value=1000,
        max_value=86400,
        value=28800,
        step=600,
    )  # e.g., 8 hours = 28,800s
    customer_demand = lc2.number_input(
        "Customer Demand per Shift (Units)",
        min_value=1,
        max_value=5000,
        value=400,
        step=10,
    )

    # Takt Time Calculation: Net Available Time / Customer Demand
    takt_time = (
        net_available_time / customer_demand if customer_demand > 0 else 0
    )

    st.info(
        f"🎯 **Target Takt Time:** **{takt_time:.2f} seconds/unit** — *The maximum allowable time each workstation has to complete its task to satisfy customer demand.*"
    )

    st.markdown("---")
    st.markdown("##### 🏭 Workstation Cycle Times Data Editor")

    # Initialize editable state for workstations
    if "line_balance_data" not in st.session_state:
        st.session_state.line_balance_data = pd.DataFrame(
            {
                "Workstation": [
                    "Station 1: Prep",
                    "Station 2: Sub-Assembly",
                    "Station 3: Main Assembly",
                    "Station 4: Quality Inspection",
                    "Station 5: Packaging",
                ],
                "Cycle Time (sec)": [52.0, 74.0, 68.0, 45.0, 48.0],
            }
        )

    edited_line_df = st.data_editor(
        st.session_state.line_balance_data,
        num_rows="dynamic",
        use_container_width=True,
        key="line_balance_editor",
    )
    st.session_state.line_balance_data = edited_line_df

    # Data cleaning for calculations
    cleaned_line = edited_line_df.dropna(subset=["Workstation"]).copy()
    cleaned_line = cleaned_line[
        cleaned_line["Workstation"].astype(str).str.strip() != ""
    ]
    cleaned_line["Cycle Time (sec)"] = pd.to_numeric(
        cleaned_line["Cycle Time (sec)"], errors="coerce"
    ).fillna(0.0)

    if not cleaned_line.empty:
        total_cycle_time = cleaned_line["Cycle Time (sec)"].sum()
        max_cycle_time = cleaned_line["Cycle Time (sec)"].max()
        num_stations = len(cleaned_line)

        # Line balance efficiency calculation: Total Cycle Time / (Number of Stations * Max Cycle Time) * 100
        line_efficiency = (
            (total_cycle_time / (num_stations * max_cycle_time)) * 100
            if (num_stations * max_cycle_time) > 0
            else 0.0
        )

        # Metrics layout
        bc1, bc2, bc3 = st.columns(3)
        bc1.metric(
            "Bottleneck Cycle Time",
            f"{max_cycle_time:.1f} s",
            help="Slowest workstation determining total line output",
        )
        bc2.metric("Total Labor Content", f"{total_cycle_time:.1f} s")
        bc3.metric(
            "Line Balance Efficiency",
            f"{line_efficiency:.1f}%",
            help="Higher percentage means less idle worker time across stations",
        )

        # Visualization: Workstation Comparison vs Takt Time
        fig_line = go.Figure()

        # Highlight bottleneck workstation in red, others in blue
        bar_colors = [
            "#d62728" if t == max_cycle_time else "#1f77b4"
            for t in cleaned_line["Cycle Time (sec)"]
        ]

        fig_line.add_trace(
            go.Bar(
                x=cleaned_line["Workstation"],
                y=cleaned_line["Cycle Time (sec)"],
                name="Station Cycle Time",
                marker_color=bar_colors,
                text=[f"{t:.1f}s" for t in cleaned_line["Cycle Time (sec)"]],
                textposition="auto",
            )
        )

        # Add Takt Time reference line
        fig_line.add_shape(
            type="line",
            x0=-0.5,
            x1=len(cleaned_line) - 0.5,
            y0=takt_time,
            y1=takt_time,
            line=dict(color="orange", dash="dash", width=2),
        )

        fig_line.update_layout(
            title="Workstation Cycle Times vs. Takt Time Target (Orange Line)",
            xaxis_title="Workstations",
            yaxis_title="Cycle Time (Seconds)",
            height=420,
            showlegend=False,
        )
        st.plotly_chart(fig_line, use_container_width=True)

        # Identify bottleneck name
        bottleneck_row = cleaned_line.loc[
            cleaned_line["Cycle Time (sec)"].idxmax()
        ]
        st.success(
            f"💡 **Line Balancing Insight:** The primary bottleneck is **{bottleneck_row['Workstation']}** taking **{bottleneck_row['Cycle Time (sec)']}s**, which exceeds your target Takt time of **{takt_time:.2f}s**. Consider re-allocating tasks or adding parallel operations to this workstation."
        )
    else:
        st.warning(
            "⚠️ Please enter at least one workstation and cycle time in the table above."
        )
# ==========================================
# MODULE 6: SIX SIGMA DMAIC KANBAN
# ==========================================
elif app_mode == "📐 Six Sigma: DMAIC Kanban Studio":
    st.subheader("Six Sigma: DMAIC Project & Task Kanban Studio")
    st.markdown(
        "Manage active continuous improvement projects, track phase gates, and assign milestone ownership across the DMAIC lifecycle."
    )

    import pandas as pd

    # Initialize professional DMAIC portfolio state if not present
    if "dmaic_portfolio_data" not in st.session_state:
        st.session_state.dmaic_portfolio_data = pd.DataFrame(
            {
                "Project ID": ["PRJ-101", "PRJ-102", "PRJ-103", "PRJ-104", "PRJ-105", "PRJ-106"],
                "Project Title": [
                    "Reduce Line 3 Scrap Rate",
                    "Gage R&R Measurement Systems Analysis",
                    "Cycle Time Reduction - Packaging",
                    "Poka-Yoke Error Proofing Assembly",
                    "Supply Chain Lead Time Optimization",
                    "Establish SPC Control Plans"
                ],
                "Phase": [
                    "Define",
                    "Measure",
                    "Analyze",
                    "Improve",
                    "Improve",
                    "Control"
                ],
                "Owner": ["Alice M.", "Bob R.", "Charlie K.", "Alice M.", "Diana P.", "Dave L."],
                "Priority": ["High", "High", "Medium", "Critical", "Medium", "High"],
                "Status": ["In Progress", "In Progress", "Completed", "To Do", "In Progress", "To Do"],
                "Target Savings ($k)": [45.0, 15.0, 30.0, 60.0, 25.0, 20.0]
            }
        )

    # Top-level portfolio metrics summary
    df_portfolio = st.session_state.dmaic_portfolio_data
    total_projects = len(df_portfolio)
    completed_projects = len(df_portfolio[df_portfolio["Status"] == "Completed"])
    total_savings = df_portfolio["Target Savings ($k)"].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active DMAIC Projects", total_projects)
    m2.metric("Completed Milestones", completed_projects)
    m3.metric("Project Completion Rate", f"{(completed_projects/total_projects)*100:.0f}%" if total_projects > 0 else "0%")
    m4.metric("Pipeline Target Impact", f"${total_savings:,.1f}k")

    st.markdown("---")
    st.markdown("##### 📋 Continuous Improvement Project Database")
    st.markdown("Select phases, priorities, and statuses directly from the dropdown selectors in the table below:")

    # Interactive Data Editor with Dropdown Configurations
    edited_portfolio = st.data_editor(
        df_portfolio,
        num_rows="dynamic",
        use_container_width=True,
        key="dmaic_studio_editor",
        column_config={
            "Phase": st.column_config.SelectboxColumn(
                "Phase",
                help="Select the DMAIC lifecycle phase",
                options=["Define", "Measure", "Analyze", "Improve", "Control"],
                required=True,
            ),
            "Priority": st.column_config.SelectboxColumn(
                "Priority",
                help="Select project priority level",
                options=["Critical", "High", "Medium", "Low"],
                required=True,
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                help="Select current project milestone status",
                options=["To Do", "In Progress", "Completed"],
                required=True,
            ),
            "Target Savings ($k)": st.column_config.NumberColumn(
                "Target Savings ($k)",
                format="$%.1f k",
                min_value=0.0,
                step=5.0
            )
        }
    )
    st.session_state.dmaic_portfolio_data = edited_portfolio

    # Clean data for Kanban visualizer
    cleaned_portfolio = edited_portfolio.dropna(subset=["Project Title"]).copy()
    cleaned_portfolio = cleaned_portfolio[
        cleaned_portfolio["Project Title"].astype(str).str.strip() != ""
    ]

    if not cleaned_portfolio.empty:
        st.markdown("---")
        st.markdown("##### 📌 Visual DMAIC Phase Workflow Board")

        # 5 Columns representing the DMAIC lifecycle
        dmaic_phases = ["Define", "Measure", "Analyze", "Improve", "Control"]
        kanban_cols = st.columns(5)

        for i, phase in enumerate(dmaic_phases):
            with kanban_cols[i]:
                st.markdown(f"**{phase.upper()}**")
                phase_items = cleaned_portfolio[cleaned_portfolio["Phase"] == phase]
                
                if not phase_items.empty:
                    for _, row in phase_items.iterrows():
                        status_icon = "✅" if row["Status"] == "Completed" else "⏳" if row["Status"] == "In Progress" else "📌"
                        priority_color = "🔴" if row["Priority"] == "Critical" else "🟠" if row["Priority"] == "High" else "🔵"
                        
                        st.markdown(
                            f"""
                            > {status_icon} {priority_color} **{row['Project Title']}**  
                            > *Lead:* {row['Owner']}  
                            > *Impact:* ${row.get('Target Savings ($k)', 0):.1f}k  
                            > *Status:* `{row['Status']}`
                            """
                        )
                else:
                    st.caption("No active projects.")
    else:
        st.warning("⚠️ Please add projects in the database editor above to populate the visual Kanban board.")