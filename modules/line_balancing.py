"""Line balancing & takt-time analysis."""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, RED, editor, plot


def line_metrics(cycle_times: list[float], net_time_s: float, demand: float) -> dict:
    """Takt, bottleneck, capacity vs demand, balance efficiency and idle time."""
    takt = net_time_s / demand if demand > 0 else float("inf")
    total = sum(cycle_times)
    bottleneck = max(cycle_times)
    k = len(cycle_times)
    return {
        "takt": takt,
        "total": total,
        "bottleneck": bottleneck,
        "stations": k,
        "efficiency": total / (k * bottleneck) * 100,
        "balance_delay": 100 - total / (k * bottleneck) * 100,
        "max_output": net_time_s / bottleneck,
        "min_stations": math.ceil(total / takt) if takt not in (0, float("inf")) else None,
    }


def render() -> None:
    st.subheader("Line Balancing & Takt Time Analysis")
    st.markdown("Enter shift parameters and station cycle times. The model computes takt, flags stations that cannot keep up, and checks line capacity against demand.")
    st.caption("ℹ️ Sample stations shown for illustration. Edit the table to model your own line.")

    c1, c2 = st.columns(2)
    hours = c1.number_input("Net available time per shift (hours)", 1.0, 24.0, 8.0, 0.25, help="After breaks and planned stops.")
    demand = c2.number_input("Customer demand per shift (units)", 1, 20000, 400, 10)
    net_time = hours * 3600

    if "line_default" not in st.session_state:
        st.session_state.line_default = pd.DataFrame(
            {
                "Workstation": ["Station 1: Prep", "Station 2: Sub-Assembly", "Station 3: Main Assembly",
                                "Station 4: Quality Inspection", "Station 5: Packaging"],
                "Cycle Time (sec)": [52.0, 74.0, 68.0, 45.0, 48.0],
            }
        )
    edited = editor(st.session_state.line_default, key="line_editor")
    d = edited.dropna(subset=["Workstation"]).copy()
    d = d[d["Workstation"].astype(str).str.strip() != ""]
    d["Cycle Time (sec)"] = pd.to_numeric(d["Cycle Time (sec)"], errors="coerce")
    d = d[d["Cycle Time (sec)"] > 0]
    if d.empty:
        st.warning("⚠️ Enter at least one workstation with a positive cycle time.")
        return

    m = line_metrics(d["Cycle Time (sec)"].tolist(), net_time, demand)
    st.info(f"🎯 **Takt time = {m['takt']:.1f} s/unit** ({hours:g} h × 3600 ÷ {demand:,} units). Each station must finish within this time.")

    a, b, c, e = st.columns(4)
    a.metric("Bottleneck", f"{m['bottleneck']:.1f} s")
    b.metric("Max output / shift", f"{m['max_output']:.0f} units", delta=f"{m['max_output'] - demand:+.0f} vs demand")
    c.metric("Balance efficiency", f"{m['efficiency']:.1f}%", help="Total labor content ÷ (stations × bottleneck time)")
    e.metric("Balance delay", f"{m['balance_delay']:.1f}%")

    over = d["Cycle Time (sec)"] > m["takt"]
    fig = go.Figure(go.Bar(
        x=d["Workstation"], y=d["Cycle Time (sec)"],
        marker_color=[RED if o else BLUE for o in over],
        text=[f"{t:.0f}s" for t in d["Cycle Time (sec)"]], textposition="auto",
    ))
    fig.add_hline(y=m["takt"], line_dash="dash", line_color="orange", annotation_text=f"Takt {m['takt']:.1f}s")
    fig.update_layout(title="Station Cycle Time vs Takt (red = exceeds takt)", yaxis_title="Seconds", height=420, showlegend=False)
    plot(fig)

    d["Idle vs bottleneck (s)"] = m["bottleneck"] - d["Cycle Time (sec)"]
    st.dataframe(d.assign(**{"Exceeds takt": over.map({True: "Yes", False: "No"})}), hide_index=True)

    slow = d.loc[over, "Workstation"].tolist()
    if slow:
        shortfall = demand - m["max_output"]
        st.error(
            f"🚨 {len(slow)} station(s) exceed takt: {', '.join(slow)}. The line can make about {m['max_output']:.0f} units per shift "
            f"against demand of {demand:,} (short by {shortfall:.0f}). Rebalance tasks, add parallel capacity, or reduce work content at the bottleneck."
        )
    else:
        st.success(f"✅ Every station is within takt. Capacity is {m['max_output']:.0f} units/shift against demand of {demand:,}.")
    if m["min_stations"]:
        st.caption(f"Theoretical minimum stations at this takt: {m['min_stations']} (total labor content {m['total']:.0f} s ÷ takt, rounded up). Current: {m['stations']}.")
