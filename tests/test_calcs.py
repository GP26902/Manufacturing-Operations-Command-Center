import math

import numpy as np
import pandas as pd
import pytest

from modules import spc_utils as su
from modules.line_balancing import line_metrics
from modules.maintenance import reliability_metrics
from modules.oee import calc_oee
from modules.pareto import pareto_table


def test_d4_n10_is_1_777():
    assert su.D4[10] == 1.777 and su.B4[10] == 1.716


def test_constants_complete():
    for table in (su.A2, su.D3, su.D4, su.B3, su.B4, su.D2):
        assert set(table) == set(range(2, 11))


def test_variable_limits_n5():
    df = pd.DataFrame({"Mean": [10.0, 10.0], "Range": [0.1, 0.1], "StdDev": [0.04, 0.04]})
    lim = su.variable_limits(df, 5)
    assert lim["x_ucl"] == pytest.approx(10.0577)
    assert lim["r_ucl"] == pytest.approx(0.2114)
    assert lim["r_lcl"] == 0


def test_capability_centered_cp_equals_cpk():
    cap = su.capability(10.05, 9.95, 10.0, 0.0125)
    assert cap["cp"] == pytest.approx(1.3333, rel=1e-3)
    assert cap["cpk"] == pytest.approx(cap["cp"])
    assert cap["cpm"] == pytest.approx(cap["cp"])


def test_capability_off_center_cpk_lower():
    cap = su.capability(10.05, 9.95, 10.02, 0.0125)
    assert cap["cpk"] < cap["cp"]


def test_sigma_within():
    assert su.sigma_within(0.2326, 5) == pytest.approx(0.1)


def test_attribute_limits_p_chart():
    res = su.attribute_limits("p", np.array([4, 5, 6]), 50)
    pbar = 15 / 150
    assert res["cl"] == pytest.approx(pbar)
    assert res["ucl"] == pytest.approx(pbar + 3 * math.sqrt(pbar * (1 - pbar) / 50))


def test_pareto_includes_category_crossing_80():
    df = pd.DataFrame({"c": list("ABCDEF"), "n": [145, 82, 38, 25, 12, 8]})
    t = pareto_table(df, "c", "n")
    assert t.loc[t["Vital Few"], "c"].tolist() == ["A", "B", "C"]  # C carries total past 80%


def test_oee_known_values():
    r = calc_oee(480, 30, 45, 30, 1.5, 3500, 105)
    assert r["availability"] == pytest.approx(75 / 450 * 100 * 0 + (450 - 75) / 450 * 100)
    assert r["oee"] == pytest.approx(r["availability"] * r["performance"] * r["quality"] / 10000)
    assert r["good"] == 3395


def test_reliability_uptime_excludes_repair():
    r = reliability_metrics(720, 6, 18)
    assert r["mtbf"] == pytest.approx(117.0)
    assert r["mttr"] == pytest.approx(3.0)
    assert r["availability"] == pytest.approx(97.5)


def test_reliability_zero_failures():
    assert reliability_metrics(720, 0, 0)["mtbf"] is None


def test_line_metrics_defaults():
    m = line_metrics([52, 74, 68, 45, 48], 28800, 400)
    assert m["takt"] == pytest.approx(72.0)
    assert m["max_output"] == pytest.approx(28800 / 74)
    assert m["min_stations"] == 4
    assert m["efficiency"] == pytest.approx(287 / (5 * 74) * 100)
