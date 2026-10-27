"""Tests for modules/five_why.py: pure functions plus page loads with Streamlit's AppTest."""
import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import five_why as w  # noqa: E402


def chain_df(rows):
    return pd.DataFrame(rows, columns=w.CHAIN_COLS)


# ---------------------------------------------------------------- pure functions
def test_sample_chain_cleans_clean():
    chain, issues = w.clean_chain(w.sample_chain())
    assert issues == [] and chain["Level"].tolist() == [1, 2, 3, 4, 5]
    assert chain["Verified"].tolist() == [True, True, True, True, False]


def test_blank_rows_dropped_and_levels_renumbered():
    df = chain_df([["a", "", True], [None, None, None], ["", "  ", False], ["b", "", False]])
    chain, issues = w.clean_chain(df)
    assert chain["Cause"].tolist() == ["a", "b"] and chain["Level"].tolist() == [1, 2] and issues == []


def test_evidence_without_cause_excluded():
    chain, issues = w.clean_chain(chain_df([["a", "", True], [None, "orphan evidence", True], ["b", "", True]]))
    assert chain["Cause"].tolist() == ["a", "b"]
    assert len(issues) == 1 and "Row 2" in issues[0]


def test_bad_values_never_raise():
    df = chain_df([[123, 4.5, "yes"], ["x", float("nan"), "maybe"], ["y", None, object()], ["  spaced   out  ", "", 0]])
    chain, issues = w.clean_chain(df)
    assert chain["Cause"].tolist() == ["123", "x", "y", "spaced out"]
    assert chain["Verified"].tolist() == [True, False, True, False]
    assert issues == []


@pytest.mark.parametrize("bad", [None, "x", 5, pd.DataFrame(), pd.DataFrame({"Other": [1]}), chain_df([])])
def test_non_table_inputs(bad):
    chain, issues = w.clean_chain(bad)
    assert chain.empty and list(chain.columns) == w.CLEAN_COLS


def test_cap_at_max_levels_and_repeat_warning():
    df = chain_df([[f"cause {i}", "", True] for i in range(14)])
    chain, issues = w.clean_chain(df)
    assert len(chain) == w.MAX_LEVELS and len(issues) == 1 and "first 10" in issues[0]
    chain, issues = w.clean_chain(chain_df([["Same", "", True], ["same", "", True]]))
    assert len(chain) == 2 and "repeats" in issues[0]


def test_to_bool():
    assert w.to_bool(True) and w.to_bool("TRUE") and w.to_bool("x") and w.to_bool(1)
    assert not w.to_bool(None) and not w.to_bool(float("nan")) and not w.to_bool("no") and not w.to_bool(0)


def test_chain_checks():
    chain, _ = w.clean_chain(w.sample_chain())
    msgs = w.chain_checks(chain)
    assert any("Why 5" in m for m in msgs) and any("root-cause statement is not marked verified" in m for m in msgs)
    short, _ = w.clean_chain(chain_df([["a", "", True], ["b", "", True]]))
    assert any("Only 2" in m for m in w.chain_checks(short)) and all("not marked" not in m for m in w.chain_checks(short))
    assert w.chain_checks(w._empty()) == []


def test_therefore_reading_order():
    chain, _ = w.clean_chain(chain_df([["cause A.", "", True], ["cause B", "", True]]))
    lines = w.therefore_reading("the problem", chain)
    assert lines == ["cause B  →  therefore  →  cause A", "cause A  →  therefore  →  the problem"]
    assert w.therefore_reading("p", w._empty()) == []
    assert "(problem not stated)" in w.therefore_reading("", chain)[-1]


def test_wrap_label_escapes_and_truncates():
    out = w.wrap_label("<script>alert(1)</script> " + "word " * 80)
    assert "<script>" not in out and "&lt;script&gt;" in out and out.rstrip().endswith("…")
    assert w.wrap_label("") == ""


def test_chain_figure_structure():
    chain, _ = w.clean_chain(w.sample_chain())
    fig = w.build_chain_fig(w.SAMPLE_PROBLEM, chain)
    assert len(fig.layout.shapes) == 6  # problem + 5 whys
    dashed = [s for s in fig.layout.shapes if s.line.dash == "dash"]
    assert len(dashed) == 0  # the only unverified row is the root cause, which is drawn as the root box
    assert fig.layout.shapes[-1].line.color == w.GREEN
    only_problem = w.build_chain_fig("", w._empty())
    assert len(only_problem.layout.shapes) == 1
    long_chain, _ = w.clean_chain(chain_df([["x" * 600, "e" * 600, False]] * 10))
    assert w.build_chain_fig("p" * 500, long_chain).layout.height > 0


def test_unverified_middle_row_is_dashed():
    chain, _ = w.clean_chain(chain_df([["a", "", False], ["b", "", True], ["c", "", True]]))
    fig = w.build_chain_fig("p", chain)
    assert [s.line.dash for s in fig.layout.shapes] == ["solid", "dash", "solid", "solid"]


# ---------------------------------------------------------------- page loads (AppTest)
def run_script(body: str) -> AppTest:
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport pandas as pd\nfrom modules import five_why as w\n{body}"
    return AppTest.from_string(script, default_timeout=60).run()


def test_page_loads():
    at = run_script("w.render()")
    assert not at.exception
    assert [m.label for m in at.metric] == ["Why levels", "Verified", "Root-cause row"]
    assert at.metric[0].value == "5" and at.metric[1].value == "4 of 5"
    assert any("Root cause:" in s.value for s in at.success)
    assert any("root-cause statement is not marked verified" in x.value for x in at.warning)


def test_page_problem_blank_and_reset():
    at = run_script("w.render()")
    at.text_input[0].set_value("").run()
    assert not at.exception
    at.button(key="five_why_reset").click().run()
    assert not at.exception and at.text_input[0].value == w.SAMPLE_PROBLEM


@pytest.mark.parametrize("state", [
    {"edited_rows": {0: {"Cause": None}, 1: {"Verified": "maybe"}}, "added_rows": [{}], "deleted_rows": []},
    {"edited_rows": {}, "added_rows": [], "deleted_rows": [0, 1, 2, 3, 4]},
    {"edited_rows": {2: {"Evidence": "only evidence", "Cause": ""}}, "added_rows": [{"Evidence": "orphan"}], "deleted_rows": []},
    {"edited_rows": {0: {"Cause": "<b>bold</b> & <script>"}}, "added_rows": [], "deleted_rows": []},
])
def test_editor_edits_do_not_crash(state):
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import five_why as w\nw.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["five_why_editor_0"] = state
    at.run()
    assert not at.exception


def test_show_results_empty_chain():
    at = run_script("w.show_results('p', w._empty(), '')")
    assert not at.exception and any("at least one cause" in i.value for i in at.info)
