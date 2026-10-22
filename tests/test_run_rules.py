"""Tests for the SPC run rule (one side of the centerline) and trend rule."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import spc_utils as su  # noqa: E402
from modules.common import add_rule_markers, control_chart  # noqa: E402


# ---------------- run rule ----------------
def test_run_of_seven_is_flagged():
    flags = su.run_flags([1, 1, 1, 1, 1, 1, 1, -1], center=0, length=7)
    assert flags.tolist() == [True] * 7 + [False]


def test_run_of_six_is_not_flagged():
    assert not su.run_flags([1] * 6 + [-1] * 2, center=0, length=7).any()


def test_run_below_centerline_is_flagged():
    flags = su.run_flags([-2, -1, -3, -1, -2, -1, -1, 5], center=0, length=7)
    assert flags.tolist() == [True] * 7 + [False]


def test_point_on_centerline_breaks_a_run():
    # six above, one exactly on the centerline, six above: neither side reaches 7
    assert not su.run_flags([1] * 6 + [0] + [1] * 6, center=0, length=7).any()


def test_runs_on_opposite_sides_are_not_merged():
    flags = su.run_flags([1] * 4 + [-1] * 4, center=0, length=7)
    assert not flags.any()


def test_run_length_is_adjustable():
    vals = [1] * 8 + [-1]
    assert su.run_flags(vals, 0, length=8).sum() == 8
    assert su.run_flags(vals, 0, length=9).sum() == 0


def test_missing_values_break_runs():
    vals = [1, 1, 1, np.nan, 1, 1, 1, 1]
    assert not su.run_flags(vals, 0, length=7).any()


def test_constant_values_are_not_a_run():
    vals = [0.05] * 20
    center = float(np.mean(vals))  # may differ from 0.05 by floating-point noise
    assert not su.run_flags(vals, center, 7).any()
    assert not su.trend_flags(vals, 6).any()


def test_floating_point_noise_does_not_create_a_trend():
    vals = [0.1 + 1e-17 * i for i in range(10)]
    assert not su.trend_flags(vals, 6).any()


# ---------------- trend rule ----------------
def test_rising_trend_of_six_is_flagged():
    flags = su.trend_flags([1, 2, 3, 4, 5, 6, 2], length=6)
    assert flags.tolist() == [True] * 6 + [False]


def test_falling_trend_is_flagged():
    flags = su.trend_flags([9, 8, 7, 6, 5, 4, 10], length=6)
    assert flags.tolist() == [True] * 6 + [False]


def test_five_point_trend_is_not_flagged():
    assert not su.trend_flags([1, 2, 3, 4, 5, 1], length=6).any()


def test_equal_neighbours_break_a_trend():
    assert not su.trend_flags([1, 2, 3, 3, 4, 5, 6], length=6).any()


def test_trend_changing_direction_is_not_one_trend():
    assert not su.trend_flags([1, 2, 3, 4, 3, 2, 1], length=6).any()


def test_short_input_is_safe():
    assert su.trend_flags([], 6).tolist() == []
    assert su.trend_flags([1.0], 6).tolist() == [False]
    assert su.run_flags([], 0, 7).tolist() == []


# ---------------- combined output and helpers ----------------
def test_violations_dict_positions():
    v = su.run_rule_violations([1, 1, 1, 1, 1, 1, 1, -1, -1, 0, 1], center=0)
    assert v["run"] == [0, 1, 2, 3, 4, 5, 6] and v["trend"] == []
    assert v["run_segments"] == [(0, 6)] and v["trend_segments"] == []


def test_adjacent_runs_on_opposite_sides_are_separate_segments():
    segs = su.run_segments([1] * 8 + [-1] * 12, center=0, length=7)
    assert segs == [(0, 7), (8, 19)]


def test_rising_then_falling_are_separate_trends():
    segs = su.trend_segments([1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1], length=6)
    assert segs == [(0, 5), (5, 10)]


def test_flags_agree_with_hand_checked_sequence():
    vals = [1, 2, 3, 4, 5, 6, 5, 5, 4, 3, 2, 1, 0]
    v = su.run_rule_violations(vals, center=5.5)
    assert v["run"] == [6, 7, 8, 9, 10, 11, 12]
    assert v["trend"] == [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
    assert v["run_segments"] == [(6, 12)]
    assert v["trend_segments"] == [(0, 5), (7, 12)]


# ---------------- chart helpers ----------------
def test_control_chart_return_value_unchanged():
    out = control_chart([1, 2, 3], [1.0, 2.0, 3.0], 2.0, 4.0, 0.0, "t", "y")
    assert len(out) == 2 and isinstance(out[0], go.Figure)


def test_markers_added_only_when_flagged():
    fig = go.Figure()
    add_rule_markers(fig, [1, 2, 3], [1, 2, 3], {"run": [], "trend": []})
    assert len(fig.data) == 0
    add_rule_markers(fig, [1, 2, 3], [1, 2, 3], {"run": [0, 1], "trend": [1, 2]})
    assert [t.name for t in fig.data] == ["Run on one side of CL", "Trend"]
    assert list(fig.data[0].x) == [1, 2]


# ---------------- page behaviour ----------------
def _spc_app(df: pd.DataFrame | None = None) -> AppTest:
    lines = ["import sys", f"sys.path.insert(0, {str(ROOT)!r})"]
    if df is not None:
        lines += ["import pandas as pd, streamlit as st", f"st.session_state['spc_input_df'] = pd.DataFrame({df.to_dict('list')!r})"]
    lines += ["from modules import spc", "spc.render()"]
    return AppTest.from_string("\n".join(lines), default_timeout=60)


def _frame(means, rng_val=0.05, sd=0.02):
    k = len(means)
    return pd.DataFrame(
        {"Subgroup": np.arange(1, k + 1), "Mean": means, "Range": [rng_val] * k, "StdDev": [sd] * k}
    )


def test_default_page_loads_without_rule_warnings():
    at = _spc_app().run()
    assert not at.exception
    assert not [w for w in at.warning if "in a row" in w.value]


def test_all_charts_render_with_rules():
    at = _spc_app().run()
    at.multiselect[0].set_value(["X-bar (Process Mean)", "R (Range)", "S (Standard Deviation)"])
    at.multiselect[1].set_value(
        ["c (total nonconformities)", "u (nonconformities per unit)", "p (proportion defective)", "np (number defective)"]
    )
    at.run()
    assert not at.exception


def test_process_shift_is_reported():
    # 8 subgroups sit above the centerline, 12 below: inside the limits, but a run
    means = [10.02] * 8 + [9.99] * 12
    at = _spc_app(_frame(means)).run()
    assert not at.exception
    msgs = [w.value for w in at.warning if "on one side of the centerline" in w.value]
    assert any("X-bar chart" in m and "1–8" in m for m in msgs)
    assert any("X-bar chart" in m and "9–20" in m for m in msgs)


def test_drift_is_reported_as_trend():
    means = [10.0, 10.001, 10.002, 10.003, 10.004, 10.005, 10.006, 10.007] + [10.0, 9.999] * 6
    at = _spc_app(_frame(means, rng_val=0.05)).run()
    assert not at.exception
    msgs = [w.value for w in at.warning if "rising or falling" in w.value]
    assert any("X-bar chart" in m and "1–8" in m for m in msgs)


def test_run_length_setting_changes_result():
    means = [10.02] * 8 + [9.99] * 12
    at = _spc_app(_frame(means)).run()
    assert any("on one side" in w.value for w in at.warning)
    at.number_input(key="spc_run_len").set_value(10)
    at.run()
    assert not [w for w in at.warning if "X-bar chart" in w.value and "on one side" in w.value and "1–8" in w.value]
    assert any("X-bar chart" in w.value and "10+ points" in w.value and "9–20" in w.value for w in at.warning)
