"""Tests for modules/kaizen.py: pure functions plus page loads with Streamlit's AppTest."""
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

from modules import kaizen as k  # noqa: E402


def ideas(rows):
    return pd.DataFrame(rows, columns=k.IDEA_COLS)


def row(idea="i", area="a", imp=3, eff=3, status="Idea", sav=None, date=None):
    return [idea, area, imp, eff, status, sav, date]


def clean(rows):
    return k.clean_ideas(ideas(rows))[0]


# ---------------------------------------------------------------- pure functions
def test_sample_cleans_and_summary_hand_values():
    df, issues = k.clean_ideas(k.sample_ideas())
    assert issues == [] and len(df) == 12 and df["ID"].tolist()[:2] == ["K1", "K2"]
    s = k.summary(df, 4, 2)
    assert s["standardized"] == 5 and s["realized"] == 49000 and s["pipeline"] == 72500
    assert s["rejected"] == 1 and s["open_quick"] == 1 and s["open_quick_savings"] == 12000
    assert s["standardized_missing"] == 0


def test_funnel_counts():
    df, _ = k.clean_ideas(k.sample_ideas())
    assert k.funnel_counts(df)["Ideas"].tolist() == [12, 9, 7, 6, 5]
    assert k.stage_counts(df) == {"Idea": 2, "Plan": 2, "Do": 1, "Check": 1, "Standardized": 5, "Rejected": 1}
    empty = k.funnel_counts(k.empty_clean())
    assert empty["Ideas"].tolist() == [0] * 5
    only_rej = clean([row("r", status="Rejected")])
    assert k.funnel_counts(only_rej)["Ideas"].tolist() == [1, 0, 0, 0, 0]


def test_bad_input_reported_not_raised():
    df, issues = k.clean_ideas(ideas([
        row("ok", "a", 4, 2, "Plan", 1000, dt.date(2026, 1, 1)),
        row("text scale", "a", "high", 2),
        row("out of range", "a", 6, 2),
        row("decimal", "a", 3.5, 2),
        row("zero", "a", 0, 2),
        row("bad status", "a", 3, 2, "someday"),
        row(None, "a", 3, 2),                       # no idea text
        [None] * 7,                                  # blank row
        ["", "", np.nan, np.nan, "", np.nan, ""],     # blank row, other style
        row("neg savings", "a", 3, 2, "Idea", -5),
        row("text savings", "a", 3, 2, "Idea", "lots"),
        row("bad date", "a", 3, 2, "Standardized", 100, "not a date"),
    ]))
    assert df["Idea"].tolist() == ["ok", "neg savings", "text savings", "bad date"]
    assert df["Savings"].isna().tolist() == [False, True, True, False]
    assert df["Date"].isna().tolist() == [False, True, True, True]
    assert len(issues) == 9  # 5 excluded rows + missing idea + 2 savings + 1 date


def test_aliases_and_money_strings():
    df = clean([row("a", "x", 3, 3, "done", "$1,500"), row("b", "x", 3, 3, " In Progress "), row("c", "x", 3, 3, None),
                row("d", "x", "4", "2", "approved", "2500.5")])
    assert df["Status"].tolist() == ["Standardized", "Do", "Idea", "Plan"]
    assert df["Savings"].tolist()[0] == 1500 and df["Savings"].tolist()[3] == 2500.5
    assert df["Impact"].tolist()[3] == 4


@pytest.mark.parametrize("bad", [None, "x", 5, pd.DataFrame(), pd.DataFrame({"Other": [1]}), ideas([])])
def test_non_table_inputs(bad):
    df, issues = k.clean_ideas(bad)
    assert df.empty and list(df.columns) == k.CLEAN_COLS


def test_repeated_idea_warning_keeps_rows():
    df, issues = k.clean_ideas(ideas([row("Same"), row("same")]))
    assert len(df) == 2 and any("repeat" in m for m in issues)


def test_quick_wins_thresholds_and_exclusions():
    df = clean([row("q-open", "a", 5, 1, "Plan"), row("q-done", "a", 5, 1, "Standardized"), row("q-rej", "a", 5, 1, "Rejected"),
                row("not-q", "a", 3, 1, "Plan"), row("edge", "a", 4, 2, "Idea")])
    assert k.open_quick_wins(df, 4, 2)["Idea"].tolist() == ["q-open", "edge"]
    assert k.open_quick_wins(df, 5, 1)["Idea"].tolist() == ["q-open"]
    assert len(k.open_quick_wins(df, 1, 5)) == 3  # all rows except Rejected and Standardized
    assert k.open_quick_wins(k.empty_clean(), 4, 2).empty


def test_cumulative_savings_groups_by_date_and_skips_missing():
    d1, d2 = dt.date(2026, 1, 5), dt.date(2026, 2, 5)
    df = clean([row("a", "x", 3, 3, "Standardized", 100, d1), row("b", "x", 3, 3, "Standardized", 50, d1),
                row("c", "x", 3, 3, "Standardized", 25, d2), row("no date", "x", 3, 3, "Standardized", 999),
                row("no savings", "x", 3, 3, "Standardized", None, d2), row("plan", "x", 3, 3, "Plan", 7, d2)])
    cum = k.cumulative_savings(df)
    assert cum["Savings"].tolist() == [150, 25] and cum["Cumulative"].tolist() == [150, 175]
    assert cum["Ideas"].tolist() == ["K1, K2", "K3"]
    assert k.summary(df, 4, 2)["standardized_missing"] == 2
    assert k.cumulative_savings(k.empty_clean()).empty
    assert k.cumulative_savings(clean([row("x", "x", 3, 3, "Plan", 5)])).empty


def test_zero_savings_still_plotted():
    cum = k.cumulative_savings(clean([row("z", "x", 3, 3, "Standardized", 0, dt.date(2026, 1, 1))]))
    assert cum["Cumulative"].tolist() == [0]


def test_spread_positions():
    pts = [(2.0, 3.0)] * 4 + [(1.0, 1.0)]
    out = k.spread_positions(pts)
    assert out[4] == (1.0, 1.0)
    assert len(set(out[:4])) == 4
    assert all(math.dist(p, (2.0, 3.0)) < 0.5 for p in out[:4])
    many = k.spread_positions([(3.0, 3.0)] * 12)
    assert len(set(many)) == 12
    assert k.spread_positions([]) == []


def test_cap_default():
    assert k.cap_default(4, 3) == 3 and k.cap_default(2, 5) == 2


def test_matrix_quadrants_follow_thresholds():
    df, _ = k.clean_ideas(k.sample_ideas())
    assert len(k.build_matrix_fig(df, 4, 2).layout.shapes) == 4
    assert len(k.build_matrix_fig(df, 4, 5).layout.shapes) == 2   # no right-hand quadrants
    assert len(k.build_matrix_fig(df, 1, 2).layout.shapes) == 2   # no bottom quadrants
    assert len(k.build_matrix_fig(df, 1, 5).layout.shapes) == 1
    qw = k.build_matrix_fig(df, 4, 2).layout.shapes[0]
    assert (qw.x0, qw.x1, qw.y0, qw.y1) == (0.5, 2.5, 3.5, 5.5)


def test_matrix_traces_per_status_and_empty():
    df, _ = k.clean_ideas(k.sample_ideas())
    fig = k.build_matrix_fig(df, 4, 2)
    assert [t.name for t in fig.data] == [s for s in k.STATUSES]
    assert sum(len(t.x) for t in fig.data) == 12
    assert len(k.build_matrix_fig(k.empty_clean(), 4, 2).data) == 0


def test_matrix_stress_same_cell_and_hostile_text():
    df = clean([row("<script>x</script> " + "w" * 300, "<b>area</b>", 3, 3, "Plan", 1) for _ in range(12)])
    fig = k.build_matrix_fig(df, 4, 2)
    hover = fig.data[0].hovertext
    assert len(hover) == 12 and all("<script>" not in h for h in hover) and any("&lt;script&gt;" in h for h in hover)
    assert len({(round(x, 4), round(y, 4)) for x, y in zip(fig.data[0].x, fig.data[0].y)}) == 12


def test_funnel_cumulative_pdca_figures_build_including_empty():
    df, _ = k.clean_ideas(k.sample_ideas())
    assert k.build_funnel_fig(df).data[0].type == "funnel"
    assert k.build_funnel_fig(k.empty_clean()).data[0].x == (0, 0, 0, 0, 0)
    assert k.build_cumulative_fig(k.cumulative_savings(df)).data[0].y[-1] == 49000
    assert len(k.build_pdca_fig(df).layout.shapes) == 4 and len(k.build_pdca_fig(k.empty_clean()).layout.shapes) == 4


def test_pdca_counts_in_labels():
    df, _ = k.clean_ideas(k.sample_ideas())
    texts = " ".join(a.text for a in k.build_pdca_fig(df).layout.annotations)
    assert "<b>5</b> ideas now at Standardized" in texts and "<b>1</b> idea now at Do" in texts


def test_custom_diagrams_have_explicit_text_colours_and_white_card():
    """Regression: unset text colours follow the theme and become unreadable on pale fills in dark mode."""
    df, _ = k.clean_ideas(k.sample_ideas())
    for fig in (k.build_matrix_fig(df, 4, 2), k.build_pdca_fig(df)):
        assert fig.layout.paper_bgcolor == "white" and fig.layout.plot_bgcolor == "white"
        for ann in fig.layout.annotations:
            if ann.text:
                assert ann.font.color, ann.text
        for tr in fig.data:
            assert tr.textfont.color


# ---------------------------------------------------------------- page loads (AppTest)
def run_script(body: str) -> AppTest:
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport pandas as pd, numpy as np\nfrom modules import kaizen as k\n{body}"
    return AppTest.from_string(script, default_timeout=60).run()


def test_page_loads_with_expected_metrics():
    at = run_script("k.render()")
    assert not at.exception
    assert [m.value for m in at.metric] == ["12", "5", "$49,000", "1"]
    assert any("Quick wins not yet standardized" in w.value and "K6" in w.value for w in at.warning)
    assert len(at.tabs) == 5


def test_page_thresholds_change_quick_wins_and_are_capped():
    at = run_script("k.render()")
    for key in ("kaizen_impact_min", "kaizen_effort_max"):
        w = at.number_input(key=key)
        assert w.value <= w.max
    at.number_input(key="kaizen_impact_min").set_value(5).run()
    assert not at.exception and at.metric[3].value == "0"
    at.number_input(key="kaizen_impact_min").set_value(1).run()
    at.number_input(key="kaizen_effort_max").set_value(5).run()
    assert not at.exception and int(at.metric[3].value) > 1


def test_page_reset_button():
    at = run_script("k.render()")
    at.button(key="kaizen_reset").click().run()
    assert not at.exception


@pytest.mark.parametrize("state", [
    {"edited_rows": {0: {"Impact": 99, "Effort": None}, 1: {"Status": None}, 2: {"Idea": None}}, "added_rows": [{}], "deleted_rows": []},
    {"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(12))},
    {"edited_rows": {3: {"Impact": "bad"}}, "added_rows": [{"Idea": "typing"}], "deleted_rows": []},
    {"edited_rows": {0: {"Date standardized": "garbage"}}, "added_rows": [], "deleted_rows": [1, 2, 3, 4]},
    {"edited_rows": {}, "added_rows": [{"Idea": f"n{i}", "Impact": 3, "Effort": 3, "Status": "Do"} for i in range(30)], "deleted_rows": []},
])
def test_editor_edits_do_not_crash(state):
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import kaizen as k\nk.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["kaizen_editor_0"] = state
    at.run()
    assert not at.exception


def test_show_results_empty_and_degenerate():
    at = run_script("k.show_results(k.empty_clean(), 4.0, 2.0)")
    assert not at.exception and any("at least one idea" in i.value for i in at.info)
    body = """
df, _ = k.clean_ideas(pd.DataFrame({'Idea': ['only'], 'Impact': [1], 'Effort': [5], 'Status': ['Standardized']}))
k.show_results(df, 1.0, 5.0)
"""
    at = run_script(body)
    assert not at.exception
