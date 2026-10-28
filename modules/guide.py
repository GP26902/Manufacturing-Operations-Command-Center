"""Which tool when? A guide to the tools in this app, organised as detect, analyze, fix, prevent.

Pure data and functions (no Streamlit calls) come first so they can be unit-tested; the page is at the bottom.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, PURPLE, plot, table, white_card

INK, MUTED = "#1a1a1a", "#4a4a4a"

STAGES = {
    "Detect": "Is something wrong, and where?",
    "Analyze": "Why is it happening?",
    "Fix": "What do we change?",
    "Prevent": "How do we keep it from coming back?",
}
STAGE_STYLE = {"Detect": ("#e3eef9", BLUE), "Analyze": ("#fff3e0", ORANGE), "Fix": ("#e2f4e2", GREEN),
               "Prevent": ("#f1e6f7", PURPLE)}

# key: (title, section, url path, stages, question it answers, input it needs, what it produces)
TOOLS = {
    "spc": ("SPC Control Charts", "Operations Analytics", "spc", ["Detect", "Prevent"],
            "Is the process stable and capable?", "Measurements in subgroups", "Control charts, run-rule flags, Pp/Ppk"),
    "oee": ("OEE Dashboard", "Operations Analytics", "oee", ["Detect"],
            "Where is production time being lost?", "Availability, performance and quality figures", "OEE and a loss waterfall"),
    "pareto": ("Pareto Defects", "Operations Analytics", "pareto", ["Detect", "Analyze"],
               "Which few categories cause most of the problem?", "Counts per defect or loss category", "Ranked bars and cumulative %"),
    "maintenance": ("Maintenance & MTBF", "Operations Analytics", "maintenance", ["Detect", "Prevent"],
                    "Which equipment fails most, and how often?", "Failure and repair records", "MTBF and downtime summaries"),
    "line_balancing": ("Line Balancing & Takt", "Operations Analytics", "line-balancing", ["Detect", "Fix"],
                       "Is work balanced against customer demand?", "Task times and demand", "Takt time and station balance"),
    "gage_rr": ("Gage R&R", "Operations Analytics", "gage-rr", ["Detect"],
                "Can the measurement system be trusted?", "Repeat readings by several operators on the same parts",
                "Repeatability, reproducibility, % of variation"),
    "dmaic": ("Six Sigma: DMAIC Board", "CI Toolkit", "dmaic", ["Fix"],
              "How do we run a larger improvement project?", "Project scope and tasks", "A Define-Measure-Analyze-Improve-Control board"),
    "fmea": ("FMEA (DFMEA / PFMEA)", "CI Toolkit", "fmea", ["Analyze", "Prevent"],
             "What could fail, and which risks come first?", "Failure modes with severity, occurrence, detection",
             "RPN ranking, heat map, before/after"),
    "five_s": ("5S Audit", "CI Toolkit", "five-s", ["Fix", "Prevent"],
               "How well is the workplace organised and sustained?", "Scored checklist", "Score per S, trend, weakest S"),
    "five_why": ("5 Why Analysis", "CI Toolkit", "five-why", ["Analyze"],
                 "What is the root cause of this one problem?", "A problem and a chain of causes with evidence",
                 "A causal chain ending in a root cause"),
    "fishbone": ("Fishbone (Ishikawa)", "CI Toolkit", "fishbone", ["Analyze"],
                 "What are the possible causes, by category?", "Brainstormed causes by 6M category", "A cause diagram"),
    "eight_d": ("8D Tracker", "CI Toolkit", "eight-d", ["Fix", "Prevent"],
                "Where is this problem report in its steps, and is it on time?", "Step status and dates",
                "Progress stepper and planned-vs-actual timeline"),
    "kaizen": ("Kaizen Log", "CI Toolkit", "kaizen", ["Fix", "Prevent"],
               "Which improvement ideas should we do first?", "Ideas scored for impact and effort",
               "Matrix, funnel, cumulative savings, PDCA"),
}

# Scenario: (label, [(tool key, why it comes at this point), ...])
SCENARIOS = {
    "customer_complaint": ("A customer complaint arrived", [
        ("eight_d", "Open the report and record containment first (D0 to D3), so suspect parts stop reaching the customer."),
        ("fishbone", "List possible causes by category so the team does not jump to one explanation."),
        ("five_why", "Take the suspected causes and test each chain against evidence until you reach a cause you can act on."),
        ("fmea", "Add or update the failure mode so the same risk is rated and watched in future designs or processes."),
        ("kaizen", "Log the permanent fixes as improvement ideas and track them to standardization."),
    ]),
    "unstable_quality": ("A quality chart looks unstable or capability is low", [
        ("gage_rr", "Check the measurement system first. If the gauge adds most of the variation, the chart is showing the gauge."),
        ("spc", "Confirm instability with control limits and run rules, and read Pp/Ppk."),
        ("pareto", "Rank defect types to find the biggest contributor."),
        ("fishbone", "Brainstorm causes for the largest category."),
        ("five_why", "Verify the most likely cause with evidence."),
        ("spc", "After the change, keep charting to confirm the process stays stable."),
    ]),
    "slow_line": ("A line or cell is slower than planned", [
        ("oee", "Find which loss category (availability, performance, quality) is largest."),
        ("line_balancing", "Compare station times with takt to see whether work is balanced."),
        ("pareto", "Rank downtime or defect reasons to choose where to look."),
        ("kaizen", "Log ideas and score them so quick wins start first."),
        ("five_s", "Audit the workplace; poor layout and missing tools often show up as lost time."),
    ]),
    "repeat_failure": ("A machine keeps failing", [
        ("maintenance", "Look at failure history and MTBF to see which machine and failure type repeat."),
        ("pareto", "Rank failure causes by count or downtime to choose which one to investigate first."),
        ("five_why", "Work back from the main failure to a cause in the maintenance or operating method."),
        ("fmea", "Rate the failure modes (process FMEA) and plan controls for the highest risks."),
        ("kaizen", "Track the corrective actions as improvements."),
    ]),
    "new_design_or_process": ("Planning a new design or process", [
        ("fmea", "Use DFMEA for the design or PFMEA for the process to find risks before launch."),
        ("gage_rr", "Validate that the gauges you plan to use are good enough for the tolerances."),
        ("spc", "Plan how the key characteristics will be charted."),
        ("five_s", "Set up the workplace standards from the start."),
    ]),
    "improvement_project": ("Running a larger improvement project", [
        ("dmaic", "Use the board to structure the project and its stages."),
        ("spc", "Establish the baseline performance in the Measure stage."),
        ("fishbone", "Generate possible causes in the Analyze stage."),
        ("five_why", "Verify the likely causes."),
        ("kaizen", "Manage the Improve-stage ideas by impact and effort."),
        ("spc", "Chart the result in the Control stage."),
    ]),
}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------
def tool_title(key: str) -> str:
    return TOOLS[key][0]


def tools_in_stage(stage: str) -> list[str]:
    return [k for k, v in TOOLS.items() if stage in v[3]]


def cheat_sheet() -> pd.DataFrame:
    return pd.DataFrame([
        {"Tool": v[0], "Section": v[1], "Stage": ", ".join(v[3]), "Answers the question": v[4], "Needs": v[5], "Produces": v[6]}
        for v in TOOLS.values()
    ])


def recommend(scenario_key: str) -> list[dict]:
    """Ordered steps for a scenario: [{'step', 'key', 'title', 'path', 'why'}]. Unknown scenario gives an empty list."""
    if scenario_key not in SCENARIOS:
        return []
    out = []
    for i, (key, why) in enumerate(SCENARIOS[scenario_key][1], start=1):
        out.append({"step": i, "key": key, "title": TOOLS[key][0], "path": TOOLS[key][2], "why": why})
    return out


def all_paths() -> list[str]:
    return [v[2] for v in TOOLS.values()]


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
def build_stage_fig() -> go.Figure:
    """Four stage boxes (Detect, Analyze, Fix, Prevent) with the tools that belong to each, joined by arrows."""
    fig = go.Figure()
    w, gap = 2.3, 0.35
    max_tools = max(len(tools_in_stage(s)) for s in STAGES)
    height = 1.6 + 0.5 * max_tools
    for i, (stage, question) in enumerate(STAGES.items()):
        x0 = i * (w + gap)
        fill, border = STAGE_STYLE[stage]
        fig.add_shape(type="rect", x0=x0, x1=x0 + w, y0=0, y1=height, fillcolor=fill, line={"color": border, "width": 2})
        fig.add_shape(type="rect", x0=x0, x1=x0 + w, y0=height - 0.12, y1=height, fillcolor=border, line={"width": 0})
        fig.add_annotation(x=x0 + w / 2, y=height - 0.3, yanchor="top", showarrow=False, text=f"<b>{stage.upper()}</b>",
                           font={"size": 16, "color": INK})
        fig.add_annotation(x=x0 + w / 2, y=height - 0.75, yanchor="top", showarrow=False, text=question,
                           font={"size": 11, "color": MUTED})
        names = [TOOLS[k][0] for k in tools_in_stage(stage)]
        fig.add_annotation(x=x0 + 0.12, y=height - 1.3, xanchor="left", yanchor="top", showarrow=False, align="left",
                           text="<br>".join(f"• {n}" for n in names), font={"size": 12, "color": INK})
        if i < len(STAGES) - 1:
            fig.add_annotation(x=x0 + w + gap, y=height / 2, ax=x0 + w, ay=height / 2, xref="x", yref="y", axref="x",
                               ayref="y", showarrow=True, arrowhead=2, arrowwidth=3, arrowcolor="#555555", text="")
    total_w = len(STAGES) * w + (len(STAGES) - 1) * gap
    fig.update_xaxes(visible=False, range=[-0.1, total_w + 0.1])
    fig.update_yaxes(visible=False, range=[-0.1, height + 0.1])
    fig.update_layout(height=int(height * 52 + 30), margin={"l": 5, "r": 5, "t": 5, "b": 5}, showlegend=False)
    return white_card(fig)


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def render() -> None:
    st.header("🧭 Which Tool When?")
    st.markdown(
        "The tools in this app fit four questions: **detect** a problem, **analyze** its cause, **fix** it, and **prevent** it "
        "from returning. Some tools serve more than one stage. Pick the situation that is closest to yours to see a suggested "
        "order; it is a starting point, not a fixed procedure."
    )
    plot(build_stage_fig())
    st.subheader("Start from a situation")
    keys = list(SCENARIOS)
    choice = st.selectbox("Situation", keys, format_func=lambda k: SCENARIOS[k][0], key="guide_scenario")
    for step in recommend(choice):
        st.markdown(f"**{step['step']}. {step['title']}** &nbsp;[open](/{step['path']})  \n{step['why']}")
    st.caption("Links open the tool in a new tab. Data you edited in the current tab is not carried over.")
    st.subheader("All tools")
    table(cheat_sheet())
