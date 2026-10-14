"""Maintenance & reliability: MTBF, MTTR, availability."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from modules.common import GREEN, RED, plot


def reliability_metrics(period_hours: float, failures: int, repair_hours: float) -> dict:
    """Uptime = scheduled period minus repair downtime.

    MTBF is None when no failures were observed (it cannot be estimated).
    """
    uptime = max(0.0, period_hours - repair_hours)
    mtbf = uptime / failures if failures > 0 else None
    mttr = repair_hours / failures if failures > 0 else 0.0
    availability = uptime / period_hours * 100 if period_hours > 0 else 0.0
    rate = failures / uptime * 1000 if uptime > 0 else 0.0
    return {"uptime": uptime, "mtbf": mtbf, "mttr": mttr, "availability": availability, "rate_per_1000h": rate}


def render() -> None:
    st.subheader("Equipment Reliability & Maintenance (MTBF / MTTR)")
    st.caption("ℹ️ Default inputs are illustrative. Enter data for one asset or asset group over one period.")

    c1, c2, c3, c4 = st.columns(4)
    period = c1.number_input("Scheduled period (hours)", 100, 8760, 720, 24, help="Total scheduled time, including downtime (720 h = 30 days).")
    failures = c2.number_input("Failures (breakdowns)", 0, 500, 6, 1)
    repair = c3.number_input("Total repair downtime (hours)", 0.0, float(period), 18.0, 1.0)
    target = c4.number_input("Availability target (%)", 50.0, 99.9, 95.0, 0.5)

    r = reliability_metrics(period, failures, repair)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("MTBF", f"{r['mtbf']:.1f} h" if r["mtbf"] else "N/A", help="Uptime / failures. N/A when there are no failures.")
    m2.metric("MTTR", f"{r['mttr']:.1f} h")
    m3.metric("Availability", f"{r['availability']:.1f}%", delta=f"{r['availability'] - target:.1f} pts vs target")
    m4.metric("Failure rate", f"{r['rate_per_1000h']:.2f} /1000 h")

    fig = go.Figure(go.Bar(
        x=["Uptime", "Repair downtime"], y=[r["uptime"], repair], marker_color=[GREEN, RED],
        text=[f"{r['uptime']:.0f} h", f"{repair:.0f} h"], textposition="auto",
    ))
    fig.update_layout(title="Time Allocation", yaxis_title="Hours", height=340)
    plot(fig)

    if r["mtbf"]:
        t = np.linspace(0, r["mtbf"] * 3, 200)
        fig2 = go.Figure(go.Scatter(x=t, y=np.exp(-t / r["mtbf"]) * 100, mode="lines", line=dict(color=GREEN, width=3)))
fig2.add_vline(x=r["mtbf"], line_dash="dash", line_color="#f5c518", annotation_text="MTBF (36.8% survive)")
        fig2.update_layout(title="Reliability R(t) = e^(-t/MTBF), constant failure rate assumption",
                           xaxis_title="Operating hours", yaxis_title="Probability of surviving (%)", height=340)
        plot(fig2)

    if failures == 0:
        st.info("No failures recorded, so MTBF cannot be estimated. Availability is limited only by planned repair time.")
    elif r["availability"] >= target:
        st.success(f"✅ Availability {r['availability']:.1f}% meets the {target:.1f}% target.")
    else:
        # What it would take to hit the target, holding the other metric fixed.
        a = target / 100
        mtbf, mttr = r["mtbf"], r["mttr"]
        need_mttr = mtbf * (1 - a) / a
        need_mtbf = mttr * a / (1 - a)
        st.warning(
            f"⚠️ Availability is {target - r['availability']:.1f} pts below target. To reach {target:.1f}% you need either "
            f"MTTR ≤ {need_mttr:.1f} h (now {mttr:.1f} h, holding MTBF) or MTBF ≥ {need_mtbf:.1f} h (now {mtbf:.1f} h, holding MTTR). "
            "Compare which change is more realistic for this asset."
        )
