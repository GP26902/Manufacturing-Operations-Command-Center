"""OEE module: Availability x Performance x Quality with loss analysis."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from modules.common import BLUE, GREEN, ORANGE, RED, plot

WORLD_CLASS = 85.0


def calc_oee(planned_time, planned_stops, breakdowns, setups, ideal_ct_s, total_pieces, defects) -> dict:
    """Pure OEE calculation. Times in minutes, cycle time in seconds."""
    available = max(1.0, planned_time - planned_stops)
    run_time = max(0.0, available - breakdowns - setups)
    availability = run_time / available * 100
    theoretical = (run_time * 60) / ideal_ct_s if ideal_ct_s > 0 else 0
    performance = min(100.0, total_pieces / theoretical * 100) if theoretical > 0 else 0.0
    good = max(0, total_pieces - defects)
    quality = good / total_pieces * 100 if total_pieces > 0 else 0.0
    oee = availability * performance * quality / 10000
    return {
        "available": available, "run_time": run_time, "good": good,
        "availability": availability, "performance": performance, "quality": quality, "oee": oee,
    }


def render() -> None:
    st.subheader("Overall Equipment Effectiveness (OEE) & Loss Analysis")
    st.caption("ℹ️ Default inputs are illustrative. Enter your own shift data.")

    c1, c2 = st.columns(2)
    planned_time = c1.number_input("Planned production time (min)", 60, 1440, 480, 30)
    planned_stops = c2.number_input("Planned stops / maintenance (min)", 0, 240, 30, 10)
    available = max(1, planned_time - planned_stops)

    st.markdown("##### ⏱️ Availability losses")
    d1, d2 = st.columns(2)
    breakdowns = d1.number_input("Unplanned breakdowns (min)", 0, int(available), 45, 5)
    setups = d2.number_input("Setup / changeover (min)", 0, int(available), 30, 5)
    if breakdowns + setups > available:
        st.warning("Breakdowns plus setup exceed available time; run time is clamped to zero.")

    st.markdown("##### ⚡ Performance and ⚙️ quality losses")
    p1, p2, p3 = st.columns(3)
    ideal_ct = p1.number_input("Ideal cycle time (s/unit)", 0.1, 60.0, 1.5, 0.1)
    produced = p2.number_input("Total pieces produced", 1, 20000, 3500, 100)
    defects = p3.number_input("Defective / scrapped pieces", 0, int(produced), 105, 5)

    r = calc_oee(planned_time, planned_stops, breakdowns, setups, ideal_ct, produced, defects)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Availability", f"{r['availability']:.1f}%")
    m2.metric("Performance", f"{r['performance']:.1f}%")
    m3.metric("Quality", f"{r['quality']:.1f}%")
    m4.metric("OEE", f"{r['oee']:.1f}%", delta=f"{r['oee'] - WORLD_CLASS:.1f} pts vs {WORLD_CLASS:.0f}% world class")

    fig = go.Figure(
        go.Bar(
            x=["Availability", "Performance", "Quality", "OEE"],
            y=[r["availability"], r["performance"], r["quality"], r["oee"]],
            marker_color=[BLUE, ORANGE, GREEN, RED],
            text=[f"{v:.1f}%" for v in (r["availability"], r["performance"], r["quality"], r["oee"])],
            textposition="auto",
        )
    )
    fig.add_hline(y=WORLD_CLASS, line_dash="dash", line_color="grey", annotation_text="World class (85%)")
    fig.update_layout(title="OEE Components", yaxis_title="%", yaxis=dict(range=[0, 105]), height=380)
    plot(fig)

    # Insight depends on the numbers: name the weakest factor.
    factors = {"Availability": r["availability"], "Performance": r["performance"], "Quality": r["quality"]}
    weakest = min(factors, key=factors.get)
    msg = (
        f"Run time {r['run_time']:.0f} of {r['available']:.0f} available min | "
        f"Good units {r['good']:,} / {produced:,}. Weakest factor: **{weakest}** ({factors[weakest]:.1f}%)."
    )
    if r["oee"] >= WORLD_CLASS:
        st.success(f"✅ OEE meets the world-class benchmark. {msg}")
    else:
        st.warning(f"⚠️ OEE is below the 85% benchmark. {msg}")
    if r["performance"] >= 100.0:
        st.info("Performance is capped at 100%. If you are hitting the cap, check that the ideal cycle time is not set too slow.")
