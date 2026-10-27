"""Tests for modules/five_s.py: pure functions plus page loads with Streamlit's AppTest."""
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import five_s as f  # noqa: E402


def checklist(rows):
    return pd.DataFrame(rows, columns=f.CHECK_COLS)


# ---------------------------------------------------------------- pure functions
def test_normalise_s_names_and_aliases():
    assert f.normalise_s("Sort") == "Sort" and f.normalise_s("  SET  IN-ORDER ") == "Set in order"
    assert f.normalise_s("Standardise") == "Standardize" and f.normalise_s("seiso") == "Shine"
    for bad in [None, np.nan, "", "Safety", 3]:
        assert f.normalise_s(bad) is None


def test_sample_checklist_scores_hand_calculation():
    clean, issues = f.clean_checklist(f.sample_checklist())
    assert issues == [] and len(clean) == 20
    scores = f.score_by_s(clean)
    assert scores["S"].tolist() == f.S_NAMES
    assert scores["Points"].tolist() == [11, 11, 9, 7, 9]
    assert scores["Items scored"].tolist() == [4] * 5
    assert scores["Score %"].round(2).tolist() == [68.75, 68.75, 56.25, 43.75, 56.25]
    assert math.isclose(f.overall_percent(scores["Score %"]), 58.75)
    assert f.weakest_s(scores) == ["Standardize"]


def test_lowest_items_order():
    clean, _ = f.clean_checklist(f.sample_checklist())
    items = f.lowest_items(clean, "Standardize", 2)
    assert items[0] == ("Cleaning and inspection routines documented", 1.0) and len(items) == 2


def test_weakest_ties_and_empty():
    clean, _ = f.clean_checklist(checklist([["Sort", "a", 1, ""], ["Shine", "b", 1, ""], ["Sustain", "c", 3, ""]]))
    assert f.weakest_s(f.score_by_s(clean)) == ["Sort", "Shine"]
    empty, _ = f.clean_checklist(None)
    scores = f.score_by_s(empty)
    assert scores["Score %"].isna().all() and f.weakest_s(scores) == [] and math.isnan(f.overall_percent(scores["Score %"]))


def test_bad_checklist_input_reported_not_raised():
    df = checklist([
        ["Sort", "ok", 4, ""],
        ["Sort", "text score", "high", ""],
        ["Sort", "too high", 5, ""],
        ["Sort", "negative", -1, ""],
        ["Safety", "unknown S", 3, ""],
        [None, None, None, None],
        ["Shine", "blank score", None, ""],
        ["shine", "lower-case S", "3", ""],
        ["Sustain", "inf", float("inf"), ""],
    ])
    clean, issues = f.clean_checklist(df)
    assert clean["Check item"].tolist() == ["ok", "blank score", "lower-case S"]
    assert len(issues) == 5
    scores = f.score_by_s(clean)
    shine = scores[scores["S"] == "Shine"].iloc[0]
    assert shine["Items scored"] == 1 and shine["Points"] == 3  # blank score not counted
    assert math.isnan(scores[scores["S"] == "Sustain"].iloc[0]["Score %"])


def test_clean_checklist_non_dataframe_and_missing_columns():
    for bad in [None, "x", 3, pd.DataFrame()]:
        clean, issues = f.clean_checklist(bad)
        assert clean.empty and issues == []
    clean, issues = f.clean_checklist(pd.DataFrame({"Check item": ["x"]}))
    assert clean.empty and len(issues) == 1


def test_all_items_zero_and_all_four():
    z, _ = f.clean_checklist(checklist([[s, "i", 0, ""] for s in f.S_NAMES]))
    assert f.score_by_s(z)["Score %"].tolist() == [0.0] * 5
    assert f.weakest_s(f.score_by_s(z)) == f.S_NAMES
    four, _ = f.clean_checklist(checklist([[s, "i", 4, ""] for s in f.S_NAMES]))
    assert f.overall_percent(f.score_by_s(four)["Score %"]) == 100.0


def test_history_cleaning():
    raw = pd.DataFrame({
        "Audit date": ["2026-03-01", "not a date", None, "2026-01-01", "2026-03-01", dt.date(2026, 2, 1)],
        "Sort": [50, 60, 70, "abc", 55, 120],
        "Set in order": [40, 40, 40, 40, 45, 40],
        "Shine": [None] * 6, "Standardize": [None] * 6, "Sustain": [None] * 6,
    })
    hist, issues = f.clean_history(raw)
    assert hist["Audit date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert hist.loc[hist["Audit date"] == "2026-03-01", "Sort"].iloc[0] == 55  # last duplicate wins
    assert math.isnan(hist.loc[0, "Sort"]) and math.isnan(hist.loc[1, "Sort"])  # 'abc' and 120 ignored
    assert len(issues) == 5  # unreadable date x2, abc, 120, duplicate date
    for bad in [None, pd.DataFrame(), "x"]:
        assert f.clean_history(bad)[0].empty


def test_previous_audit_and_trend_frame():
    hist, _ = f.clean_history(f.sample_history())
    assert f.previous_audit(hist, dt.date(2026, 10, 27))["Audit date"] == pd.Timestamp("2026-09-08")
    assert f.previous_audit(hist, dt.date(2026, 5, 12)) is None  # same day is not "previous"
    assert f.previous_audit(f.clean_history(None)[0], dt.date(2026, 1, 1)) is None
    t = f.trend_frame(hist, {s: 60.0 for s in f.S_NAMES}, dt.date(2026, 10, 27))
    assert len(t) == 6 and t["Overall"].iloc[-1] == 60.0
    t2 = f.trend_frame(hist, {s: 60.0 for s in f.S_NAMES}, dt.date(2026, 9, 8))  # same date: current replaces history
    assert len(t2) == 5 and t2["Overall"].iloc[-1] == 60.0
    assert f.trend_frame(hist)["Overall"].notna().all()
    assert f.trend_frame(f.clean_history(None)[0]).empty


def test_overall_ignores_missing_s():
    assert f.overall_percent([50, np.nan, 100]) == 75.0
    assert math.isnan(f.overall_percent([np.nan, np.nan]))


def test_figures_build_including_missing_values():
    cur = {"Sort": 70, "Set in order": np.nan, "Shine": 50, "Standardize": 40, "Sustain": 60}
    fig = f.build_radar_fig(cur, {s: 30 for s in f.S_NAMES}, "Previous", 80)
    assert [t.name for t in fig.data] == ["Target (80%)", "Previous", "Current audit"]
    assert fig.data[-1].r[1] is None and fig.data[-1].r[0] == fig.data[-1].r[-1]  # gap kept, polygon closed
    assert len(f.build_radar_fig(cur).data) == 1
    hist, _ = f.clean_history(f.sample_history())
    t = f.trend_frame(hist)
    assert len(f.build_trend_fig(t, 80).data) == 6
    single = f.trend_frame(hist.head(1))
    assert len(f.build_trend_fig(single, None).data) == 6


# ---------------------------------------------------------------- page loads (AppTest)
def run_script(body: str) -> AppTest:
    header = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport datetime as dt\nimport pandas as pd, numpy as np\n"
    script = header + f"from modules import five_s as f\n{body}"
    return AppTest.from_string(script, default_timeout=60).run()


def test_page_loads_and_shows_weakest_s():
    at = run_script("f.render()")
    assert not at.exception
    assert any("Weakest S: Standardize (43.8%)" in w.value for w in at.warning)
    assert [m.label for m in at.metric] == ["Overall score", "Items scored", "S below target"]
    assert at.metric[0].value == "58.8%"
    assert at.metric[1].value == "20"


def test_page_target_change_updates_below_target_count():
    at = run_script("f.render()")
    at.number_input(key="fives_target").set_value(60).run()
    assert not at.exception
    assert at.metric[2].value == "3"  # 56.25, 56.25 and 43.75 are below 60


def test_page_trend_toggle_and_area_blank():
    at = run_script("f.render()")
    at.checkbox(key="fives_include").uncheck().run()
    at.text_input(key="fives_area").set_value("").run()
    assert not at.exception


@pytest.mark.parametrize("state", [
    {"edited_rows": {0: {"Score": 99}, 1: {"S": None}, 2: {"Check item": None, "Score": None}}, "added_rows": [{}], "deleted_rows": [5]},
    {"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(20))},
    {"edited_rows": {3: {"Score": "bad"}}, "added_rows": [{"Check item": "typing"}], "deleted_rows": []},
])
def test_checklist_edits_do_not_crash(state):
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import five_s as f\nf.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["fives_checklist"] = state
    at.run()
    assert not at.exception


@pytest.mark.parametrize("state", [
    {"edited_rows": {0: {"Audit date": None}, 1: {"Sort": 500}}, "added_rows": [{}], "deleted_rows": []},
    {"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(5))},
])
def test_history_edits_do_not_crash(state):
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import five_s as f\nf.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["fives_history"] = state
    at.run()
    assert not at.exception


def test_show_results_edge_inputs():
    body = """
empty, _ = f.clean_checklist(None)
hist, _ = f.clean_history(None)
f.show_results(empty, hist, '', dt.date(2026, 10, 27), 80.0, True)
clean, _ = f.clean_checklist(f.sample_checklist())
f.show_results(clean, hist, 'Area', dt.date(2026, 10, 27), 0.0, True)
f.show_results(clean, hist, 'Area', dt.date(2026, 10, 27), 100.0, False)
"""
    at = run_script(body)
    assert not at.exception
