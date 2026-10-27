"""Tests for modules/fmea.py: pure functions plus page loads with Streamlit's AppTest."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import fmea  # noqa: E402


def frame(rows, mode="PFMEA"):
    cols = [fmea.ITEM_LABEL[mode], "Failure mode", "Effect", "Severity", "Cause", "Occurrence",
            "Current controls", "Detection", "Recommended action", *fmea.NEW_COLS]
    return pd.DataFrame(rows, columns=cols)


def row(item="Step", fm="Mode", s=5, o=5, d=5, ns=None, no=None, nd=None, cause="c"):
    return [item, fm, "effect", s, cause, o, "ctrl", d, "action", ns, no, nd]


# ---------------------------------------------------------------- pure functions
def test_rpn_and_ratings():
    assert fmea.rpn(9, 8, 7) == 504
    assert fmea.to_rating("7") == 7 and fmea.to_rating(7.0) == 7
    for bad in [0, 11, 5.5, "high", None, np.nan, "", float("inf"), -3, "7,5"]:
        assert np.isnan(fmea.to_rating(bad)), bad


def test_sample_tables_clean_without_issues():
    for mode in fmea.MODES:
        clean, issues = fmea.clean_fmea(fmea.sample_table(mode), mode)
        assert issues == []
        assert len(clean) == len(fmea.sample_table(mode))
        assert (clean["RPN"] == clean["Severity"] * clean["Occurrence"] * clean["Detection"]).all()
        assert clean["High severity"].any()  # sample data demonstrates the flag
        assert list(clean.columns) == fmea.CLEAN_COLS


def test_sample_has_flagged_row_below_threshold():
    clean, _ = fmea.clean_fmea(fmea.sample_table("PFMEA"), "PFMEA")
    low = clean[(clean["High severity"]) & (clean["RPN"] < 100)]
    assert len(low) >= 1
    st = fmea.with_status(clean, 100)
    assert st.loc[low.index[0], "Review"].startswith("Severity >= 9")


def test_bad_input_never_raises_and_is_reported():
    df = frame([
        row("A", "ok", 9, 2, 3),
        row("B", "text rating", "high", 3, 3),
        row("C", "out of range", 11, 3, 3),
        row("D", "decimal", 5.5, 3, 3),
        row("E", "missing", None, 3, 3),
        row("F", "zero", 0, 3, 3),
        [None] * 12,                      # fully blank row
        ["", "", "", np.nan, "", np.nan, "", np.nan, "", np.nan, np.nan, np.nan],
    ])
    clean, issues = fmea.clean_fmea(df)
    assert list(clean["Failure mode"]) == ["ok"]
    assert len(issues) == 5
    assert all("excluded" in m for m in issues)


def test_text_ratings_are_accepted_when_numeric_strings():
    clean, issues = fmea.clean_fmea(frame([row("A", "m", "7", " 4 ", "3")]))
    assert issues == [] and clean.loc[0, "RPN"] == 84


def test_non_dataframe_and_empty_inputs():
    for bad in [None, "text", 5, pd.DataFrame(), frame([])]:
        clean, issues = fmea.clean_fmea(bad)
        assert clean.empty and list(clean.columns) == fmea.CLEAN_COLS and issues == []


def test_missing_columns_do_not_crash():
    clean, issues = fmea.clean_fmea(pd.DataFrame({"Failure mode": ["x"], "Severity": [5]}))
    assert clean.empty and len(issues) == 1


def test_numbers_in_text_columns_are_converted():
    clean, _ = fmea.clean_fmea(frame([row(item=12, fm=3.5, cause=7)]))
    assert clean.loc[0, "Item"] == "12" and clean.loc[0, "Failure mode"] == "3.5"


def test_revised_ratings_partial_invalid_and_valid():
    df = frame([
        row("A", "full", 8, 4, 4, 8, 2, 2),
        row("B", "partial", 8, 4, 4, 8, None, 2),
        row("C", "invalid", 8, 4, 4, 8, "x", 2),
        row("D", "none", 8, 4, 4),
    ])
    clean, issues = fmea.clean_fmea(df)
    assert len(clean) == 4
    assert clean.loc[0, "New RPN"] == 32
    assert clean["New RPN"].isna().tolist() == [False, True, True, True]
    assert len(issues) == 2 and all("Revised ratings ignored" in m for m in issues)


def test_duplicates_kept_with_unique_ids_and_warning():
    clean, issues = fmea.clean_fmea(frame([row("A", "m", cause="x"), row("A", "m", cause="x")]))
    assert clean["ID"].tolist() == ["F1", "F2"]
    assert any("repeat" in m for m in issues)


def test_severity_flag_regardless_of_rpn():
    clean, _ = fmea.clean_fmea(frame([row("A", "low rpn", 9, 1, 1), row("B", "high rpn", 5, 9, 9), row("C", "s8", 8, 1, 1)]))
    assert clean["High severity"].tolist() == [True, False, False]
    st = fmea.with_status(clean, 100)
    assert st["Review"].tolist() == ["Severity >= 9", "RPN >= threshold", "Monitor"]
    assert fmea.review_status(9, 500, 100) == "Severity >= 9 and RPN >= threshold"


def test_pareto_table_sorted_cumulative_and_top_n():
    clean, _ = fmea.clean_fmea(frame([row("A", "a", 5, 2, 2), row("B", "b", 5, 5, 5), row("C", "c", 5, 3, 3)]))
    p = fmea.pareto_table(clean)
    assert p["RPN"].tolist() == [125, 45, 20]
    assert math.isclose(p["Cumulative %"].iloc[-1], 100.0)
    assert len(fmea.pareto_table(clean, 2)) == 2
    assert len(fmea.pareto_table(clean, 0)) == 1  # clamped to at least one
    assert math.isclose(fmea.pareto_table(clean, 1)["Cumulative %"].iloc[0], 125 / 190 * 100)


def test_pareto_tie_break_by_severity():
    clean, _ = fmea.clean_fmea(frame([row("A", "low s", 2, 6, 5), row("B", "high s", 6, 2, 5)]))
    assert fmea.pareto_table(clean)["Failure mode"].tolist() == ["high s", "low s"]


def test_summary_values():
    clean, _ = fmea.clean_fmea(frame([row("A", "a", 9, 5, 5, 9, 2, 5), row("B", "b", 5, 2, 2), row("C", "c", 4, 5, 5, 4, 6, 6)]))
    s = fmea.summary(clean, 100)
    assert s["n"] == 3 and s["max_rpn"] == 225 and s["max_id"] == "F1"
    assert s["n_high_severity"] == 1 and s["n_over_threshold"] == 2  # 225 and 100 (>= threshold)
    assert s["paired_n"] == 2 and s["paired_before"] == 325 and s["paired_after"] == 90 + 144
    assert s["n_increased"] == 1
    assert fmea.summary(fmea.empty_clean(), 100)["n"] == 0


def test_so_cells_groups_ids():
    clean, _ = fmea.clean_fmea(frame([row("A", "a", 9, 2, 2), row("B", "b", 9, 2, 3), row("C", "c", 3, 4, 4)]))
    cells = fmea.so_cells(clean)
    assert cells[(9, 2)] == ["F1", "F2"] and cells[(3, 4)] == ["F3"]


def test_cap_default():
    assert fmea.cap_default(10, 3) == 3
    assert fmea.cap_default(10, 50) == 10
    assert fmea.cap_default(100, 1000) == 100


def test_figures_build_for_edge_cases():
    one, _ = fmea.clean_fmea(frame([row("A", "only", 10, 10, 10)]))
    same, _ = fmea.clean_fmea(frame([row("A", "a", 5, 5, 5), row("B", "b", 5, 5, 5)]))
    many, _ = fmea.clean_fmea(frame([row("A", f"m{i}", 5, 5, 5, cause=str(i)) for i in range(8)]))  # 8 in one cell
    long, _ = fmea.clean_fmea(frame([row("A", "x" * 200, 5, 5, 5)]))
    for df in (one, same, many, long):
        assert len(fmea.build_pareto_fig(df, 100).data) == 3
        assert fmea.build_heatmap_fig(df).data[0].type == "heatmap"
    assert fmea.build_before_after_fig(one) is None
    # heat map text for an over-full cell is shortened
    assert "+5" in fmea.build_heatmap_fig(many).data[0].text[4][4]
    # threshold above max RPN still gives a visible axis
    assert fmea.build_pareto_fig(one, 5000).layout.yaxis.range[1] >= 5000


def test_before_after_figure_has_two_series():
    clean, _ = fmea.clean_fmea(frame([row("A", "a", 8, 5, 5, 8, 2, 2), row("B", "b", 5, 5, 5)]))
    fig = fmea.build_before_after_fig(clean)
    assert [t.name for t in fig.data] == ["Current RPN", "Revised RPN"]
    assert len(fig.data[0].y) == 1


# ---------------------------------------------------------------- page loads (AppTest)
def run_script(body: str) -> AppTest:
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport pandas as pd, numpy as np\nfrom modules import fmea\n{body}"
    return AppTest.from_string(script, default_timeout=60).run()


def test_page_loads_default_dfmea():
    at = run_script("fmea.render()")
    assert not at.exception
    assert any("Design FMEA" in m.value for m in at.markdown)
    assert any("classic RPN" in c.value for c in at.caption)
    assert len(at.tabs) == 4


def test_page_toggle_to_dfmea_and_back():
    at = run_script("fmea.render()")
    at.radio(key="fmea_type").set_value(fmea.MODES["PFMEA"]).run()
    assert not at.exception
    assert any("Process FMEA" in m.value for m in at.markdown)
    assert [w.key for w in at.number_input][0] == "fmea_thr_PFMEA"
    at.radio(key="fmea_type").set_value(fmea.MODES["DFMEA"]).run()
    assert not at.exception
    assert any("Design FMEA" in m.value for m in at.markdown)


def test_page_shows_flag_banner_and_metrics():
    at = run_script("fmea.render()")
    assert any("regardless of RPN" in w.value for w in at.warning)
    assert len(at.metric) == 4


@pytest.mark.parametrize("rows", [
    "[]",
    "[['A','only','e',10,'c',10,'k',10,'x',None,None,None]]",
    "[['A','a','e',5,'c',5,'k',5,'x',None,None,None],['B','b','e',5,'c',5,'k',5,'x',None,None,None]]",
])
def test_show_results_edge_tables(rows):
    body = f"""
cols = [fmea.ITEM_LABEL['PFMEA'], 'Failure mode', 'Effect', 'Severity', 'Cause', 'Occurrence',
        'Current controls', 'Detection', 'Recommended action', *fmea.NEW_COLS]
raw = pd.DataFrame({rows}, columns=cols)
clean, issues = fmea.clean_fmea(raw, 'PFMEA')
fmea.show_results(clean, 'PFMEA', 100.0, None)
"""
    at = run_script(body)
    assert not at.exception


def test_show_results_with_garbage_table():
    body = """
raw = pd.DataFrame({'Process step': ['a', None, 5], 'Failure mode': [None, 'x', 'y'], 'Severity': ['bad', 9, 1e9],
                    'Occurrence': [3, 3, 3], 'Detection': [3, 3, 3]})
clean, issues = fmea.clean_fmea(raw, 'PFMEA')
fmea._report_issues(issues)
fmea.show_results(clean, 'PFMEA', 100.0, 5)
"""
    at = run_script(body)
    assert not at.exception


def test_page_number_inputs_capped_at_row_count():
    at = run_script("fmea.render()")
    n = len(fmea.sample_table("DFMEA"))
    top = [w for w in at.number_input if w.key.startswith("fmea_top_DFMEA")][0]
    assert top.max == n and top.value <= top.max
    thr = at.number_input(key="fmea_thr_DFMEA")
    assert thr.value <= thr.max


@pytest.mark.parametrize("state, expect_info", [
    ({"edited_rows": {0: {"Severity": "abc"}}, "added_rows": [], "deleted_rows": []}, False),
    ({"edited_rows": {0: {"Severity": 99, "Occurrence": None}, 1: {"Failure mode": None}},
      "added_rows": [{}], "deleted_rows": [2]}, False),
    ({"edited_rows": {}, "added_rows": [{"Failure mode": "typing..."}], "deleted_rows": []}, False),
    ({"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(7))}, True),
])
def test_editor_edits_do_not_crash_page(state, expect_info):
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import fmea\nfmea.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["fmea_editor_DFMEA_0"] = state
    at.run()
    assert not at.exception
    assert any("Enter at least one complete row" in i.value for i in at.info) == expect_info
