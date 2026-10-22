"""Regression tests for the code-review fixes (OEE, maintenance, line balancing, Pareto, DMAIC)."""
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.line_balancing import line_metrics  # noqa: E402
from modules.pareto import pareto_table  # noqa: E402


def _app(module: str, setup: str = "") -> AppTest:
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        {setup}
        from modules import {module}
        {module}.render()
        """
    )
    return AppTest.from_string(script, default_timeout=30)


def _num(at: AppTest, label: str):
    return next(w for w in at.number_input if w.label == label)


def _metric(at: AppTest, label: str):
    return next(m for m in at.metric if m.label == label)


# ---------------- OEE: defaults must never exceed a dynamic max ----------------
def test_oee_default_page_loads():
    at = _app("oee").run()
    assert not at.exception


def test_oee_short_shift_does_not_crash():
    at = _app("oee").run()
    _num(at, "Planned production time (min)").set_value(60)  # available = 30 < default breakdowns (45)
    at.run()
    assert not at.exception
    assert _num(at, "Unplanned breakdowns (min)").value <= 30


def test_oee_few_pieces_does_not_crash():
    at = _app("oee").run()
    _num(at, "Total pieces produced").set_value(100)  # default defects (105) > pieces
    at.run()
    assert not at.exception
    assert _num(at, "Defective / scrapped pieces").value <= 100


# ---------------- Maintenance: MTBF of 0 is a number, not "N/A" ----------------
def test_maintenance_default_page_loads():
    at = _app("maintenance").run()
    assert not at.exception
    assert _metric(at, "MTBF").value == "117.0 h"


def test_maintenance_zero_uptime_shows_zero_mtbf():
    at = _app("maintenance").run()
    _num(at, "Scheduled period (hours)").set_value(100)
    at.run()
    _num(at, "Total repair downtime (hours)").set_value(100.0)  # uptime = 0 with 6 failures
    at.run()
    assert not at.exception
    assert _metric(at, "MTBF").value == "0.0 h"


def test_maintenance_no_failures_shows_na():
    at = _app("maintenance").run()
    _num(at, "Failures (breakdowns)").set_value(0)
    at.run()
    assert not at.exception
    assert _metric(at, "MTBF").value == "N/A"


# ---------------- Line balancing: float noise must not add a station ----------------
def test_min_stations_ignores_float_noise():
    # 0.1 + 0.2 = 0.30000000000000004; at takt 0.1 the true minimum is exactly 3.
    m = line_metrics([0.1, 0.2], net_time_s=10.0, demand=100)
    assert m["min_stations"] == 3


def test_min_stations_rounds_up_real_fractions():
    m = line_metrics([52.0, 74.0, 68.0, 45.0, 48.0], net_time_s=28800, demand=400)  # 287 / 72 = 3.99
    assert m["min_stations"] == 4
    m2 = line_metrics([40.0, 40.0, 40.0], net_time_s=28800, demand=400)  # 120 / 72 = 1.67
    assert m2["min_stations"] == 2


def test_line_default_numbers():
    m = line_metrics([52.0, 74.0, 68.0, 45.0, 48.0], net_time_s=28800, demand=400)
    assert m["takt"] == pytest.approx(72.0)
    assert m["efficiency"] == pytest.approx(287 / (5 * 74) * 100)
    assert m["max_output"] == pytest.approx(28800 / 74)


# ---------------- Pareto: duplicate / padded labels are merged ----------------
def test_pareto_merges_duplicate_labels():
    df = pd.DataFrame({"Defect": ["Scratch", "Burr", "Scratch ", "Void"], "Count": [30, 50, 30, 10]})
    d = pareto_table(df, "Defect", "Count")
    assert d["Defect"].tolist() == ["Scratch", "Burr", "Void"]
    assert d["Count"].tolist() == [60, 50, 10]
    assert d["Cumulative %"].iloc[-1] == pytest.approx(100.0)


def test_pareto_default_vital_few():
    df = pd.DataFrame(
        {"Defect": ["Surface Scratch", "Dimensional Variance", "Porosity / Void",
                    "Assembly Misalignment", "Flash / Burr", "Electrical Short"],
         "Count": [145, 82, 38, 25, 12, 8]}
    )
    d = pareto_table(df, "Defect", "Count")
    assert d.loc[d["Vital Few"], "Defect"].tolist() == ["Surface Scratch", "Dimensional Variance", "Porosity / Void"]


def test_pareto_single_dominant_defect():
    d = pareto_table(pd.DataFrame({"Defect": ["A", "B"], "Count": [90, 10]}), "Defect", "Count")
    assert d.loc[d["Vital Few"], "Defect"].tolist() == ["A"]


# ---------------- DMAIC: blanks and "$" in free text ----------------
def test_dmaic_default_page_loads():
    at = _app("dmaic").run()
    assert not at.exception


def test_dmaic_blank_owner_status_and_dollar_sign():
    setup = textwrap.dedent(
        """
        import numpy as np, pandas as pd, streamlit as st
        st.session_state["dmaic_default"] = pd.DataFrame({
            "Project ID": ["P1", "P2"],
            "Project Title": ["Save $5 on $10 parts", "Blank fields"],
            "Phase": ["Improve", "Define"],
            "Owner": ["Owner $A", np.nan],
            "Priority": ["High", "Low"],
            "Status": ["In Progress", np.nan],
            "Target Savings ($k)": [10.0, 5.0],
        })
        """
    ).replace("\n", "\n        ")
    at = _app("dmaic", setup).run()
    assert not at.exception
    text = " ".join(c.value for c in at.caption) + " ".join(m.value for m in at.markdown)
    assert "nan" not in text.lower()
    assert "None" not in text
    assert "Unassigned" in text
    # every "$" in card text is escaped, so Streamlit cannot treat pairs as LaTeX
    cards = [c.value for c in at.caption if "·" in c.value] + [m.value for m in at.markdown if "**" in m.value and "Save" in m.value]
    for t in cards:
        assert t.count("$") == t.count("\\$")


def test_dmaic_sample_data_consistent():
    at = _app("dmaic").run()
    assert not at.exception
    df = at.session_state["dmaic_default"]
    done = df[df["Status"] == "Completed"]
    # DMAIC ends at Control, so a completed project must sit there
    assert (done["Phase"] == "Control").all()


def test_line_balancing_default_page_loads():
    at = _app("line_balancing").run()
    assert not at.exception
    assert "Takt time = 72.0" in at.info[0].value


def test_pareto_default_page_loads():
    at = _app("pareto").run()
    assert not at.exception
    assert "3 of 6 categories, 85%" in at.success[0].value
