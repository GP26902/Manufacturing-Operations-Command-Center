"""Tests for modules/fishbone.py: pure functions plus page loads with Streamlit's AppTest."""
import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import fishbone as f  # noqa: E402


def causes(rows):
    return pd.DataFrame(rows, columns=f.CAUSE_COLS)


# ---------------------------------------------------------------- pure functions
def test_category_aliases():
    for raw, expected in [("Machine", "Machine"), ("equipment", "Machine"), (" PEOPLE ", "Man (People)"), ("Man", "Man (People)"),
                          ("mother nature", "Environment"), ("Mother Nature (Environment)", "Environment"),
                          ("Inspection", "Measurement"), ("process", "Method"), ("Materials", "Material")]:
        assert f.normalise_category(raw) == expected, raw
    for bad in [None, "", "Money", 3, float("nan")]:
        assert f.normalise_category(bad) is None


def test_sample_cleans_and_structure():
    clean, issues = f.clean_causes(f.sample_causes())
    assert issues == [] and len(clean) == 12
    struct = f.build_structure(clean)
    assert list(struct) == f.CATEGORIES
    summary = f.category_summary(struct)
    assert summary["Causes"].tolist() == [2, 2, 2, 2, 2, 2]
    assert summary["Sub-causes"].sum() == 2 and summary["Suspected"].sum() == 2
    assert f.suspected_causes(struct) == [("Method", "Seal fitted without lubricant"), ("Material", "Seal hardness varies between lots")]


def test_bad_rows_excluded_and_reported():
    df = causes([
        ["Machine", "ok", "", False],
        ["Money", "unknown category", "", True],
        [None, "no category", "", False],
        ["Method", "", "sub without cause", False],
        ["Method", "", "", False],                 # category only: dropped silently
        [None, None, None, None],                   # blank
        ["Money", "", "", False],                   # unknown category, no text
        ["Machine", "OK", "", True],                # repeat of row 1 (case-insensitive): ignored
        ["machine", "second", 12, "yes"],           # number in text column, text bool
    ])
    clean, issues = f.clean_causes(df)
    assert clean["Cause"].tolist() == ["ok", "second"]
    assert clean["Sub-cause"].tolist() == ["", "12"] and clean["Suspected"].tolist() == [False, True]
    assert len(issues) == 5


@pytest.mark.parametrize("bad", [None, "x", 7, pd.DataFrame(), pd.DataFrame({"Other": [1]}), causes([])])
def test_non_table_inputs(bad):
    clean, issues = f.clean_causes(bad)
    assert clean.empty and list(clean.columns) == f.CLEAN_COLS


def test_structure_merges_same_cause_and_ors_suspected():
    clean, _ = f.clean_causes(causes([
        ["Machine", "Wear", "a", False], ["Machine", "wear", "b", True], ["Machine", "Other", "", False]]))
    struct = f.build_structure(clean)
    assert len(struct["Machine"]) == 2
    assert struct["Machine"][0]["subs"] == ["a", "b"] and struct["Machine"][0]["suspected"] is True


def test_empty_structure_has_all_six_bones():
    struct = f.build_structure(f._empty())
    geo = f.layout_fishbone(struct)
    bones = [ln for ln in geo["lines"] if ln[3] == "bone"]
    assert sorted(b[2] for b in bones) == sorted(f.CATEGORIES)
    assert [t["text"] for t in geo["texts"]] == f.CATEGORIES  # only the six labels, no causes
    assert f.build_fishbone_fig("", struct).data


def test_layout_positions_are_distinct_and_in_range():
    rows = [(cat, f"cause {i}", "sub" if i % 2 else "", i == 0) for cat in f.CATEGORIES for i in range(5)]
    clean, _ = f.clean_causes(causes(rows))
    geo = f.layout_fishbone(f.build_structure(clean))
    H = geo["H"]
    items = [t for t in geo["texts"] if t["kind"] != "category"]
    assert len({(round(t["x"], 3), round(t["y"], 3)) for t in items}) == len(items)
    assert all(abs(t["y"]) < H for t in items) and all(t["y"] > 0 for t in items if t["category"] in f.TOP)
    assert all(t["y"] < 0 for t in items if t["category"] in f.BOTTOM)


def test_text_does_not_overlap_estimate():
    """Estimated text extents (about 10 px per x unit and 6.6 px per character) must not overlap or leave the plot."""
    rows = [(cat, "x" * 40 + str(i), "y" * 40, False) for cat in f.CATEGORIES for i in range(6)]
    clean, _ = f.clean_causes(causes(rows))
    geo = f.layout_fishbone(f.build_structure(clean))
    boxes = [(t["x"] - len(t["text"]) * 0.66, t["x"], t["y"]) for t in geo["texts"] if t["kind"] != "category"]
    for i, a in enumerate(boxes):
        assert a[0] >= -6
        for b in boxes[i + 1:]:
            if abs(a[2] - b[2]) < 0.6:
                assert not (a[0] < b[1] and b[0] < a[1]), (a, b)


def test_long_and_hostile_text_is_shortened_and_escaped():
    clean, _ = f.clean_causes(causes([["Machine", "<script>" + "z" * 300, "", True]]))
    fig = f.build_fishbone_fig("<img src=x> " + "e" * 400, f.build_structure(clean))
    text_trace = fig.data[-1]
    assert all("<script>" not in t for t in text_trace.text)
    assert any("&lt;script&gt;" in t for t in text_trace.text)
    assert len(text_trace.text[-1]) < 120
    assert "<img" not in fig.layout.annotations[0].text


def test_suspected_drawn_red_and_hover_has_full_text():
    clean, _ = f.clean_causes(causes([["Method", "m" * 100, "", True], ["Method", "other", "", False]]))
    trace = f.build_fishbone_fig("e", f.build_structure(clean)).data[-1]
    colors = list(trace.textfont.color)
    texts = list(trace.hovertext)
    assert colors[[i for i, h in enumerate(texts) if h.startswith("mmm")][0]] == f.RED
    assert any(h == "m" * 100 + " (suspected)" for h in texts)


def test_figure_height_grows_with_rows():
    few, _ = f.clean_causes(causes([["Machine", "a", "", False]]))
    many, _ = f.clean_causes(causes([["Machine", f"c{i}", "", False] for i in range(15)]))
    tall = f.build_fishbone_fig("e", f.build_structure(many)).layout.height
    short = f.build_fishbone_fig("e", f.build_structure(few)).layout.height
    assert tall > short


# ---------------------------------------------------------------- page loads (AppTest)
def run_script(body: str) -> AppTest:
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport pandas as pd\nfrom modules import fishbone as f\n{body}"
    return AppTest.from_string(script, default_timeout=60).run()


def test_page_loads():
    at = run_script("f.render()")
    assert not at.exception
    assert [m.label for m in at.metric] == ["Causes", "Categories with causes", "Suspected"]
    assert [m.value for m in at.metric] == ["12", "6", "2"]
    assert any("Suspected causes to verify" in i.value for i in at.info)


def test_page_effect_blank_and_reset():
    at = run_script("f.render()")
    at.text_input[0].set_value("").run()
    assert not at.exception
    at.button(key="fishbone_reset").click().run()
    assert not at.exception and at.text_input[0].value == f.SAMPLE_EFFECT


@pytest.mark.parametrize("state", [
    {"edited_rows": {0: {"Category": None}, 1: {"Cause": None, "Sub-cause": "orphan"}}, "added_rows": [{}], "deleted_rows": []},
    {"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(12))},
    {"edited_rows": {2: {"Suspected": "maybe"}}, "added_rows": [{"Category": "Method", "Cause": "<b>x</b> & y"}], "deleted_rows": []},
    {"edited_rows": {}, "added_rows": [{"Category": "Machine", "Cause": f"c{i}"} for i in range(40)], "deleted_rows": []},
])
def test_editor_edits_do_not_crash(state):
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import fishbone as f\nf.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["fishbone_editor_0"] = state
    at.run()
    assert not at.exception


def test_show_results_empty():
    at = run_script("f.show_results('', f._empty())")
    assert not at.exception and any("Add causes" in i.value for i in at.info)


def test_text_colours_explicit_and_white_card_for_dark_theme():
    """Regression: effect box and heat-map style text must not depend on the theme's (light) text colour."""
    clean, _ = f.clean_causes(f.sample_causes())
    fig = f.build_fishbone_fig("effect", f.build_structure(clean))
    assert fig.layout.annotations[0].font.color == "#1a1a1a"
    assert fig.layout.paper_bgcolor == "white" and fig.layout.plot_bgcolor == "white"
    assert all(c for c in fig.data[-1].textfont.color)
