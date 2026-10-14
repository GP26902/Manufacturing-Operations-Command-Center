"""Six Sigma DMAIC project board (table-driven Kanban)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.common import editor

PHASES = ["Define", "Measure", "Analyze", "Improve", "Control"]
PRIORITY_ICON = {"Critical": "🔴", "High": "🟠", "Medium": "🔵", "Low": "⚪"}
STATUS_ICON = {"Completed": "✅", "In Progress": "⏳", "To Do": "📌"}


def render() -> None:
    st.subheader("Six Sigma: DMAIC Project Board")
    st.markdown("Track improvement projects through the DMAIC phases. Edit the table; the board below updates from it.")
    st.caption("ℹ️ All projects, names and savings below are made-up sample data, for illustration only.")

    if "dmaic_default" not in st.session_state:
        st.session_state.dmaic_default = pd.DataFrame(
            {
                "Project ID": ["PRJ-101", "PRJ-102", "PRJ-103", "PRJ-104", "PRJ-105", "PRJ-106"],
                "Project Title": ["Reduce Line 3 Scrap Rate", "Gage R&R Measurement Systems Analysis",
                                  "Cycle Time Reduction: Packaging", "Poka-Yoke Error Proofing Assembly",
                                  "Supply Chain Lead Time Optimization", "Establish SPC Control Plans"],
                "Phase": ["Define", "Measure", "Analyze", "Improve", "Improve", "Control"],
                "Owner": ["Owner A", "Owner B", "Owner C", "Owner A", "Owner D", "Owner E"],
                "Priority": ["High", "High", "Medium", "Critical", "Medium", "High"],
                "Status": ["In Progress", "In Progress", "Completed", "To Do", "In Progress", "To Do"],
                "Target Savings ($k)": [45.0, 15.0, 30.0, 60.0, 25.0, 20.0],
            }
        )

    edited = editor(
        st.session_state.dmaic_default,
        key="dmaic_editor",
        column_config={
            "Phase": st.column_config.SelectboxColumn("Phase", options=PHASES, required=True),
            "Priority": st.column_config.SelectboxColumn("Priority", options=list(PRIORITY_ICON), required=True),
            "Status": st.column_config.SelectboxColumn("Status", options=list(STATUS_ICON), required=True),
            "Target Savings ($k)": st.column_config.NumberColumn("Target Savings ($k)", format="$%.1fk", min_value=0.0, step=5.0),
        },
    )

    # Metrics come from the edited table, so they never lag behind the user's edits.
    d = edited.dropna(subset=["Project Title"]).copy()
    d = d[d["Project Title"].astype(str).str.strip() != ""]
    d["Target Savings ($k)"] = pd.to_numeric(d["Target Savings ($k)"], errors="coerce").fillna(0.0)
    total = len(d)
    done = int((d["Status"] == "Completed").sum())
    open_ = total - done

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total projects", total)
    m2.metric("Open projects", open_)
    m3.metric("Completed", f"{done} ({done / total * 100:.0f}%)" if total else "0")
    m4.metric("Target savings (open)", f"${d.loc[d['Status'] != 'Completed', 'Target Savings ($k)'].sum():,.0f}k")

    if d.empty:
        st.warning("⚠️ Add projects in the table to populate the board.")
        return
    no_phase = d[~d["Phase"].isin(PHASES)]
    if len(no_phase):
        st.info(f"{len(no_phase)} project(s) have no Phase selected and are not shown on the board.")

    st.markdown("##### DMAIC Board")
    cols = st.columns(len(PHASES))
    for col, phase in zip(cols, PHASES):
        with col:
            st.markdown(f"**{phase.upper()}**")
            items = d[d["Phase"] == phase]
            if items.empty:
                st.caption("No projects")
            for _, row in items.iterrows():
                with st.container(border=True):
                    st.markdown(f"{STATUS_ICON.get(row['Status'], '📌')} {PRIORITY_ICON.get(row['Priority'], '⚪')} **{row['Project Title']}**")
                    st.caption(f"{row.get('Owner') or 'Unassigned'} · ${row['Target Savings ($k)']:.0f}k · {row['Status']}")
