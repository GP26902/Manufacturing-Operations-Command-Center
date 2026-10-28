"""Tests for modules/gage_rr.py: maths cross-checks, edge cases and page loads with Streamlit's AppTest."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import gage_rr as g  # noqa: E402


def long(values, parts, opers, reps):
    """Build long-format data from a nested list values[part][operator] = list of readings."""
    rows = []
    for i in range(parts):
        for j in range(opers):
            for y in values[i][j]:
                rows.append((str(i + 1), "ABCDEFGH"[j], y))
    return pd.DataFrame(rows, columns=g.DATA_COLS)


# ---------------------------------------------------------------- F distribution
def test_f_sf_matches_scipy():
    stats = pytest.importorskip("scipy.stats")
    for d1 in (1, 2, 3, 5, 9, 18, 40):
        for d2 in (1, 2, 5, 20, 60, 200, 1000):
            for f in (0.01, 0.3, 1, 2.5, 6, 20, 100, 1e4):
                expected = stats.f.sf(f, d1, d2)
                got = g.f_sf(f, d1, d2)
                assert got == pytest.approx(expected, rel=1e-8, abs=1e-12), (d1, d2, f)


def test_f_sf_edge_cases():
    assert g.f_sf(0.0, 3, 10) == 1.0 and g.f_sf(-1.0, 3, 10) == 1.0
    assert g.f_sf(math.inf, 3, 10) == 0.0
    assert math.isnan(g.f_sf(math.nan, 3, 10)) and math.isnan(g.f_sf(2.0, 0, 10)) and math.isnan(g.f_sf(2.0, 3, 0))
    assert g.betainc_reg(0.0, 2, 3) == 0.0 and g.betainc_reg(1.0, 2, 3) == 1.0


# ---------------------------------------------------------------- ANOVA
def test_sums_of_squares_match_brute_force():
    df = g.sample_data()
    a = g.anova_table(df)
    y = df["Measurement"].to_numpy()
    P, Q = pd.factorize(df["Part"])[0], pd.factorize(df["Operator"])[0]
    p, o = P.max() + 1, Q.max() + 1
    gm = y.mean()
    ssp = sum(((y[P == i].mean() - gm) ** 2) * (P == i).sum() for i in range(p))
    sso = sum(((y[Q == j].mean() - gm) ** 2) * (Q == j).sum() for j in range(o))
    sst = ((y - gm) ** 2).sum()
    sse = sum(((y[(P == i) & (Q == j)] - y[(P == i) & (Q == j)].mean()) ** 2).sum() for i in range(p) for j in range(o))
    assert a["ss"]["part"] == pytest.approx(ssp) and a["ss"]["oper"] == pytest.approx(sso)
    assert a["ss"]["eq"] == pytest.approx(sse) and a["ss"]["inter"] == pytest.approx(sst - ssp - sso - sse)
    assert a["df"] == {"part": 9, "oper": 2, "inter": 18, "eq": 60}


def test_hand_calculable_example():
    """2 parts x 2 operators x 2 readings; every quantity below was worked out by hand."""
    df = long([[[10, 12], [11, 13]], [[20, 22], [19, 21]]], 2, 2, 2)
    a = g.anova_table(df)
    # cell means: P1A 11, P1B 12, P2A 21, P2B 20. grand mean 16. part means 11.5 and 20.5; operator means 16 and 16.
    assert a["grand"] == pytest.approx(16.0)
    assert a["ss"]["part"] == pytest.approx(2 * 2 * ((11.5 - 16) ** 2 + (20.5 - 16) ** 2))  # 324
    assert a["ss"]["oper"] == pytest.approx(0.0)
    assert a["ss"]["inter"] == pytest.approx(2 * (4 * 0.5**2 * 1))  # 4 cells, each residual +-0.5 -> r * 4 * 0.25 = 2
    assert a["ss"]["eq"] == pytest.approx(8.0)  # each cell: two readings 2 apart -> SS 2; four cells
    assert a["df"]["eq"] == 4 and a["ms"]["eq"] == pytest.approx(2.0)


def test_recovers_known_variance_components():
    big = g.simulate(300, 10, 5, 0.02, 0.003, 0.0025, 0.0015, seed=11, decimals=8)
    res = g.analyze(big, alpha=0.25)
    v = res["var"]
    assert res["keep_interaction"]
    assert math.sqrt(v["repeat"]) == pytest.approx(0.003, rel=0.05)
    assert math.sqrt(v["inter"]) == pytest.approx(0.0015, rel=0.10)
    assert math.sqrt(v["part"]) == pytest.approx(0.02, rel=0.10)
    assert math.sqrt(v["oper"]) == pytest.approx(0.0025, rel=0.45)  # only 10 operators drawn, so a noisier estimate


def test_components_add_up_and_percentages():
    res = g.analyze(g.sample_data(), 0.25, g.SAMPLE_TOLERANCE)
    v = res["var"]
    assert v["grr"] == pytest.approx(v["repeat"] + v["oper"] + v["inter"]) and v["total"] == pytest.approx(v["grr"] + v["part"])
    comp = res["components"].set_index("Source")
    assert comp.loc["Total Gage R&R", "% Contribution"] + comp.loc["Part-to-Part", "% Contribution"] == pytest.approx(100.0)
    assert comp.loc["Total variation", "% Study var"] == pytest.approx(100.0)
    assert comp.loc["Total Gage R&R", "% Tolerance"] == pytest.approx(100 * 6 * math.sqrt(v["grr"]) / g.SAMPLE_TOLERANCE)
    assert res["ndc"] == math.floor(1.41 * math.sqrt(v["part"]) / math.sqrt(v["grr"]))


def test_sample_data_pinned_results():
    """Regression pins for the default simulated study (seed 42)."""
    res = g.analyze(g.sample_data(), 0.25, g.SAMPLE_TOLERANCE)
    comp = res["components"].set_index("Source")
    assert res["keep_interaction"] and res["p_interaction"] < 0.01
    assert comp.loc["Total Gage R&R", "% Study var"] == pytest.approx(24.68, abs=0.05)
    assert comp.loc["Total Gage R&R", "% Tolerance"] == pytest.approx(18.62, abs=0.05)
    assert res["ndc"] == 5
    assert g.verdict(24.68, 5)[0] == "marginal"


def test_interaction_removed_when_not_significant():
    df = g.simulate(10, 3, 3, 0.02, 0.003, 0.002, 0.0, seed=5)
    res = g.analyze(df, alpha=0.25)
    assert not res["keep_interaction"] and res["var"]["inter"] == 0.0
    assert "Operator x Part" not in set(res["components"]["Source"])
    assert any("removed from the model" in n for n in res["notes"])
    assert "Repeatability (pooled with interaction)" in set(res["anova"]["Source"])
    forced = g.analyze(df, alpha=1.0)  # p <= 1 always, so the interaction stays in
    assert forced["keep_interaction"] and "Operator x Part" in set(forced["components"]["Source"])


def test_negative_variance_clipped_with_note():
    rng = np.random.RandomState(3)
    rows = [(str(i), op, float(rng.normal(10, 0.01))) for i in range(1, 6) for op in "AB" for _ in range(3)]
    res = g.analyze(pd.DataFrame(rows, columns=g.DATA_COLS), alpha=0.25)  # pure noise: part variance estimate may go negative
    assert all(v >= 0 for v in res["var"].values())


def test_degenerate_data():
    same = pd.DataFrame([(str(i), op, 5.0) for i in (1, 2, 3) for op in "AB" for _ in range(2)], columns=g.DATA_COLS)
    res = g.analyze(same)
    assert math.isnan(res["ndc"]) and g.verdict(float(res["components"].iloc[0]["% Study var"]), res["ndc"])[0] == "undetermined"
    perfect_gauge = pd.DataFrame([(str(i), op, float(i)) for i in (1, 2, 3) for op in "AB" for _ in range(2)], columns=g.DATA_COLS)
    res = g.analyze(perfect_gauge)
    assert math.isinf(res["ndc"]) and res["var"]["grr"] == 0.0
    assert g.verdict(0.0, math.inf)[0] == "acceptable"


def test_verdict_levels_and_ndc_warning():
    assert g.verdict(9.9, 8)[0] == "acceptable" and g.verdict(10.0, 8)[0] == "marginal"
    assert g.verdict(30.0, 8)[0] == "marginal" and g.verdict(30.1, 8)[0] == "unacceptable"
    level, text = g.verdict(5.0, 3)
    assert level == "acceptable" and "3 distinct categories" in text
    assert g.verdict(None, 5)[0] == "undetermined"


def test_dominant_source_statements():
    rep = g.analyze(g.simulate(10, 3, 3, 0.02, 0.008, 0.0005, 0.0, seed=1))
    assert g.dominant_source(rep).startswith("Repeatability")
    rpd = g.analyze(g.simulate(10, 3, 3, 0.02, 0.0005, 0.01, 0.0, seed=1))
    assert g.dominant_source(rpd).startswith("Reproducibility")
    assert "No measurement variation" in g.dominant_source({"var": {"grr": 0.0, "repeat": 0.0, "repro": 0.0}})


# ---------------------------------------------------------------- data handling
def test_simulate_is_deterministic_and_shaped():
    a, b = g.simulate(5, 3, 2, 0.02, 0.003, 0.002, 0.001, seed=7), g.simulate(5, 3, 2, 0.02, 0.003, 0.002, 0.001, seed=7)
    assert a.equals(b) and len(a) == 30 and sorted(a["Operator"].unique()) == ["A", "B", "C"]
    assert not a.equals(g.simulate(5, 3, 2, 0.02, 0.003, 0.002, 0.001, seed=8))
    zero = g.simulate(3, 2, 2, 0.0, 0.0, 0.0, 0.0)
    assert (zero["Measurement"] == 25.0).all()
    assert len(g.sample_data()) == 90


def test_clean_measurements_edge_cases():
    raw = pd.DataFrame({
        "Part": [1.0, 2, "3", None, "", 5, 6, None],
        "Operator": ["A", "A", None, "B", "", "B", "B", None],
        "Measurement": [10.1, "10.2", 10.3, 10.4, None, "abc", float("inf"), None],
    })
    df, issues = g.clean_measurements(raw)
    assert df["Part"].tolist() == ["1", "2"] and df["Measurement"].tolist() == [10.1, 10.2]
    assert len(issues) == 4  # missing operator, missing part, text measurement, infinite measurement
    for bad in (None, "x", 4, pd.DataFrame(), pd.DataFrame({"Other": [1]})):
        assert g.clean_measurements(bad)[0].empty


def test_check_design_problems():
    ok, problems = g.check_design(g.sample_data())
    assert ok and problems == []
    unbalanced = g.sample_data().iloc[:-1]
    ok, problems = g.check_design(unbalanced)
    assert not ok and "not balanced" in problems[0] and "part 10/operator C: 2" in problems[0]
    one_reading = g.simulate(4, 3, 1, 0.02, 0.003, 0.002, 0.001)
    assert not g.check_design(one_reading)[0]
    assert not g.check_design(g.sample_data()[g.sample_data()["Operator"] == "A"])[0]
    assert not g.check_design(g.sample_data()[g.sample_data()["Part"] == "1"])[0]
    assert g.check_design(g.clean_measurements(None)[0]) == (False, ["No valid measurements."])


def test_ordered_labels():
    assert g.ordered(["10", "2", "1", "2"]) == ["1", "2", "10"]
    assert g.ordered(["b", "a", "b"]) == ["b", "a"]


def test_parse_upload():
    good, msg = g.parse_upload(b"part,OPERATOR,Measurement\n1,A,10.1\n1,B,10.2\n")
    assert msg == "" and list(good.columns) == g.DATA_COLS and len(good) == 2
    bad, msg = g.parse_upload(b"a,b\n1,2\n")
    assert bad is None and "Missing column" in msg
    bad, msg = g.parse_upload(b"")
    assert bad is None and msg


# ---------------------------------------------------------------- figures
def test_figures_build_and_use_explicit_colours():
    df = g.sample_data()
    res = g.analyze(df, 0.25, g.SAMPLE_TOLERANCE)
    figs = [g.build_components_fig(res), g.build_by_part_fig(df, "mm"), g.build_by_operator_fig(df, "mm"),
            g.build_interaction_fig(df, "mm")]
    for fig in figs:
        assert fig.layout.paper_bgcolor == "white" and fig.layout.plot_bgcolor == "white"
        for axis in (fig.layout.xaxis, fig.layout.yaxis):
            assert axis.tickfont.color == g.INK and axis.title.font.color == g.INK
        assert fig.layout.legend.font.color == g.INK
    assert [t.name for t in figs[0].data] == ["% Contribution", "% Study var", "% Tolerance"]
    assert [t.name for t in g.build_components_fig(g.analyze(df, 0.25, None)).data] == ["% Contribution", "% Study var"]
    assert len(figs[1].data) == 3 + 1 and len(figs[2].data) == 3 and len(figs[3].data) == 3


def test_figures_with_many_operators_and_text_labels():
    df = g.simulate(6, 10, 2, 0.02, 0.003, 0.002, 0.001, seed=3)
    assert len(g.build_by_part_fig(df).data) == 11 and len(g.build_by_operator_fig(df).data) == 10
    labelled = pd.DataFrame([(p, o, 1.0 + 0.1 * i + 0.01 * k) for i, p in enumerate(["Housing", "Cover", "Base"])
                             for o in ["Ann", "Bo"] for k in range(2)], columns=g.DATA_COLS)
    assert g.build_interaction_fig(labelled).data[0].x == ("Housing", "Cover", "Base")


# ---------------------------------------------------------------- page loads (AppTest)
def run_script(body: str) -> AppTest:
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport pandas as pd\nfrom modules import gage_rr as g\n{body}"
    return AppTest.from_string(script, default_timeout=90).run()


def test_page_loads_with_sample_result():
    at = run_script("g.render()")
    assert not at.exception
    assert any("Marginal." in w.value and "24.7%" in w.value for w in at.warning)
    assert [m.value for m in at.metric] == ["24.7%", "6.1%", "5", "18.6%"]
    assert len(at.tabs) == 5


def test_page_simulation_inputs_change_the_verdict_and_caps_hold():
    at = run_script("g.render()")
    for w in at.number_input:
        assert w.min <= w.value <= w.max, w.key
    at.number_input(key="grr_sr").set_value(0.03).run()  # much noisier gauge
    assert not at.exception and any("Unacceptable." in e.value for e in at.error)
    at.number_input(key="grr_sr").set_value(0.0005).run()
    at.number_input(key="grr_so").set_value(0.0).run()
    at.number_input(key="grr_si").set_value(0.0).run()
    assert not at.exception and any("Acceptable." in s.value for s in at.success)
    at.number_input(key="grr_tol").set_value(0.0).run()
    assert not at.exception and at.metric[3].value == "set tolerance"


@pytest.mark.parametrize("params", [
    {"grr_parts": 3, "grr_opers": 2, "grr_reps": 2},
    {"grr_parts": 30, "grr_opers": 10, "grr_reps": 6},
    {"grr_sp": 0.0, "grr_sr": 0.0, "grr_so": 0.0, "grr_si": 0.0},
    {"grr_sp": 0.0},
])
def test_page_extreme_simulation_settings_do_not_crash(params):
    at = run_script("g.render()")
    for key, val in params.items():
        at.number_input(key=key).set_value(val)
    at.run()
    assert not at.exception


def test_page_edit_mode_and_bad_edits():
    at = run_script("g.render()")
    at.radio(key="grr_mode").set_value("Edit or upload data").run()
    assert not at.exception
    state = {"edited_rows": {0: {"Measurement": None}, 1: {"Operator": None}, 2: {"Part": ""}}, "added_rows": [{}], "deleted_rows": [5]}
    at.session_state["grr_editor_0"] = state
    at.run()
    assert not at.exception
    assert any("not balanced" in w.value for w in at.warning)  # rows excluded or deleted -> cells no longer equal


@pytest.mark.parametrize("state", [
    {"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(90))},
    {"edited_rows": {3: {"Measurement": "abc"}}, "added_rows": [{"Part": "x"}], "deleted_rows": []},
    {"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(45, 90))},
])
def test_page_edit_mode_extreme_edits(state):
    at = run_script("g.render()")
    at.radio(key="grr_mode").set_value("Edit or upload data").run()
    at.session_state["grr_editor_0"] = state
    at.run()
    assert not at.exception


def test_show_results_unbalanced_and_empty():
    at = run_script("g.show_results(g.sample_data().iloc[:-1], 0.12, 0.25, 'mm')")
    assert not at.exception and any("not balanced" in w.value for w in at.warning)
    at = run_script("g.show_results(g.clean_measurements(None)[0], None, 0.25, '')")
    assert not at.exception and any("No valid measurements" in w.value for w in at.warning)
