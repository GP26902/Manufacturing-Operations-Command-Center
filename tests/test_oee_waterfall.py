"""Tests for the OEE loss waterfall."""
import sys
import textwrap
from pathlib import Path

import plotly.graph_objects as go
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.oee import calc_oee, loss_breakdown, loss_waterfall_figure  # noqa: E402

DEFAULT = dict(planned_time=480, planned_stops=30, breakdowns=45, setups=30, ideal_ct_s=6.0, total_pieces=3500, defects=105)


def _total(b):
    return b["planned_stops"] + b["breakdowns"] + b["setups"] + b["speed"] + b["quality"] + b["productive"]


def test_default_numbers_by_hand():
    b = loss_breakdown(**DEFAULT)
    assert b["planned"] == 480
    assert b["planned_stops"] == pytest.approx(30)
    assert b["breakdowns"] == pytest.approx(45)
    assert b["setups"] == pytest.approx(30)
    assert b["speed"] == pytest.approx(25.0)      # 375 min run x (1 - 3500/3750)
    assert b["quality"] == pytest.approx(10.5)    # 350 min net run x 3%
    assert b["productive"] == pytest.approx(339.5)


def test_bars_add_up_to_planned_time():
    assert _total(loss_breakdown(**DEFAULT)) == pytest.approx(480)


def test_productive_time_ties_to_oee():
    b = loss_breakdown(**DEFAULT)
    assert b["productive"] / b["available"] * 100 == pytest.approx(calc_oee(**DEFAULT)["oee"])
    assert b["oee"] == pytest.approx(calc_oee(**DEFAULT)["oee"])


def test_capped_performance_has_zero_speed_loss():
    d = dict(DEFAULT, total_pieces=20000, defects=0)  # more pieces than the cycle time allows
    b = loss_breakdown(**d)
    assert b["speed"] == pytest.approx(0.0)
    assert _total(b) == pytest.approx(480)


def test_downtime_exceeding_available_time_is_clamped():
    # 300 + 300 min of downtime against 450 available: setup is cut back to what is left
    b = loss_breakdown(**dict(DEFAULT, breakdowns=300, setups=300))
    assert b["breakdowns"] == pytest.approx(300)
    assert b["setups"] == pytest.approx(150)
    assert b["productive"] == pytest.approx(0.0)
    assert _total(b) == pytest.approx(480)
    # breakdowns alone exceed available time
    b = loss_breakdown(**dict(DEFAULT, breakdowns=500, setups=30))
    assert b["breakdowns"] == pytest.approx(450)
    assert b["setups"] == pytest.approx(0.0)
    assert _total(b) == pytest.approx(480)


def test_no_losses_means_everything_is_productive():
    d = dict(planned_time=480, planned_stops=0, breakdowns=0, setups=0, ideal_ct_s=6.0, total_pieces=4800, defects=0)
    b = loss_breakdown(**d)
    assert b["productive"] == pytest.approx(480)
    assert b["oee"] == pytest.approx(100.0)


@pytest.mark.parametrize(
    "d",
    [
        DEFAULT,
        dict(DEFAULT, planned_time=60, breakdowns=30),
        dict(DEFAULT, planned_stops=240, planned_time=60),   # stops exceed planned time
        dict(DEFAULT, total_pieces=1, defects=1),
        dict(DEFAULT, ideal_ct_s=0.1),
    ],
)
def test_never_negative_and_always_adds_up(d):
    b = loss_breakdown(**d)
    for key in ("planned_stops", "breakdowns", "setups", "speed", "quality", "productive"):
        assert b[key] >= -1e-9, key
    assert _total(b) == pytest.approx(b["planned"])


def test_figure_is_a_waterfall_with_seven_bars():
    fig = loss_waterfall_figure(loss_breakdown(**DEFAULT))
    assert isinstance(fig, go.Figure)
    wf = fig.data[0]
    assert wf.type == "waterfall" and len(wf.x) == 7
    assert list(wf.measure)[0] == "absolute" and list(wf.measure)[-1] == "total"


def _app():
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from modules import oee
        oee.render()
        """
    )
    return AppTest.from_string(script, default_timeout=30)


def test_page_loads_with_waterfall_caption():
    at = _app().run()
    assert not at.exception
    text = " ".join(c.value for c in at.caption)
    assert "Fully productive time is 339.5 min" in text and "75.4%" in text and "450 min available" in text


def test_page_survives_extreme_inputs():
    at = _app().run()
    next(w for w in at.number_input if w.label == "Planned production time (min)").set_value(60)
    at.run()
    assert not at.exception
