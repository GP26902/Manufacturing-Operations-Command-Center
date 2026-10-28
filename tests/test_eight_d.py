"""Tests for modules/eight_d.py: pure functions plus page loads with Streamlit's AppTest."""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import eight_d as e  # noqa: E402

D = dt.date
OPENED, AS_OF = D(2026, 9, 1), D(2026, 10, 28)


def steps(rows):
    return pd.DataFrame(rows, columns=e.STEP_COLS)


def clean(rows):
    return e.clean_steps(steps(rows))[0]


# ---------------------------------------------------------------- pure functions
@pytest.mark.parametrize("raw, expected", [("D3", "D3"), ("d3", "D3"), ("3", "D3"), (" D 4 ", "D4"), ("D3 - Containment", "D3"),
                                           (8, "D8"), ("D9", None), ("D10", None), ("", None), (None, None), ("x", None)])
def test_normalise_step(raw, expected):
    assert e.normalise_step(raw) == expected


def test_status_aliases():
    for raw, expected in [("done", "Done"), ("WIP", "In progress"), ("On hold", "Blocked"), ("todo", "Not started")]:
        assert e.normalise_status(raw) == expected
    assert e.normalise_status("maybe") is None and e.normalise_status(None) is None


def test_sample_clean_and_schedule_values():
    df, issues = e.clean_steps(e.sample_steps())
    assert issues == [] and df["Step"].tolist() == e.STEP_IDS
    sched = e.with_schedule(df, AS_OF)
    days = dict(zip(sched["Step"], sched["Days late"]))
    assert days["D3"] == 1 and days["D4"] == 4 and days["D5"] == -1 and days["D6"] == 8  # D6 is overdue as of AS_OF
    assert sched["Overdue"].tolist() == [False] * 6 + [True, False, False]
    assert e.current_step(df) == "D6" and e.days_open(df, OPENED, AS_OF) == 57
    assert e.sequence_notes(df, OPENED, AS_OF) == []


def test_missing_steps_filled_and_empty_inputs():
    df = clean([["D2", "Done", D(2026, 9, 4), D(2026, 9, 4), ""]])
    assert len(df) == 9 and df.loc[2, "Status"] == "Done" and (df.drop(index=2)["Status"] == "Not started").all()
    for bad in [None, "x", 5, pd.DataFrame(), pd.DataFrame({"Other": [1]}), steps([])]:
        out, issues = e.clean_steps(bad)
        assert len(out) == 9 and (out["Status"] == "Not started").all() and list(out.columns) == e.CLEAN_COLS


def test_bad_rows_reported_not_raised():
    df, issues = e.clean_steps(steps([
        ["D1", "Done", "not a date", D(2026, 9, 2), "ok"],
        ["D9", "Done", None, None, "unknown step"],
        ["D2", "maybe", D(2026, 9, 4), None, ""],
        ["D3", "In progress", D(2026, 9, 4), D(2026, 9, 5), "completed date on a not-done step"],
        ["D4", "Done", None, "garbage", ""],
        [None, None, None, None, None],
        ["", "", "", "", ""],
        ["D5", "Done", D(2026, 9, 30), D(2026, 9, 29), 12345],
    ]))
    assert df.loc[1, "Planned"] is pd.NaT or pd.isna(df.loc[1, "Planned"])
    assert df.loc[2, "Status"] == "Not started"
    assert df.loc[3, "Status"] == "In progress" and pd.isna(df.loc[3, "Completed"])
    assert df.loc[5, "Notes"] == "12345"
    assert len(issues) == 5  # bad planned date, unknown step D9, bad status, completed date on not-done step, bad completed date
    joined = " ".join(issues)
    assert "D9" in joined and "not recognised" in joined and "ignored because the status is not Done" in joined


def test_duplicate_step_uses_last_row():
    df, issues = e.clean_steps(steps([["D1", "Not started", None, None, "first"], ["d1", "Done", D(2026, 9, 2), D(2026, 9, 2), "last"]]))
    assert df.loc[1, "Notes"] == "last" and df.loc[1, "Status"] == "Done"
    assert any("more than once" in m for m in issues)


def test_with_schedule_overdue_only_for_not_done():
    df = clean([["D0", "Done", D(2026, 9, 1), D(2026, 9, 10), ""], ["D1", "Blocked", D(2026, 9, 2), None, ""],
                ["D2", "Not started", D(2026, 12, 1), None, ""], ["D3", "In progress", None, None, ""]])
    s = e.with_schedule(df, AS_OF)
    assert s["Overdue"].tolist()[:4] == [False, True, False, False]
    assert s.loc[0, "Days late"] == 9 and s.loc[1, "Days late"] == 56
    assert pd.isna(s.loc[2, "Days late"]) and pd.isna(s.loc[3, "Days late"])


def test_current_step_and_days_open_closed_and_clamped():
    all_done = clean([[s, "Done", D(2026, 9, 1), D(2026, 9, 1 + i), ""] for i, s in enumerate(e.STEP_IDS)])
    assert e.current_step(all_done) is None
    assert e.days_open(all_done, OPENED, D(2027, 1, 1)) == 8  # to the D8 completion date, not as_of
    nothing = clean([])
    assert e.current_step(nothing) == "D0"
    assert e.days_open(nothing, D(2026, 10, 28), D(2026, 9, 1)) == 0  # never negative


def test_sequence_notes_cases():
    base = [["D0", "Done", None, D(2026, 9, 1), ""], ["D1", "Not started", None, None, ""], ["D2", "Done", None, D(2026, 9, 3), ""]]
    notes = e.sequence_notes(clean(base), OPENED, AS_OF)
    assert any("D2 is Done but D1 is not" in n for n in notes)
    notes = e.sequence_notes(clean([["D0", "Done", None, None, ""]]), OPENED, AS_OF)
    assert any("no completed date" in n for n in notes)
    notes = e.sequence_notes(clean([["D0", "Done", None, D(2026, 8, 1), ""]]), OPENED, AS_OF)
    assert any("before the opened date" in n for n in notes)
    notes = e.sequence_notes(clean([]), OPENED, D(2026, 8, 1))
    assert any("'status as of' date is before" in n for n in notes)
    notes = e.sequence_notes(clean([["D0", "Done", None, D(2026, 9, 10), ""], ["D1", "Done", None, D(2026, 9, 5), ""]]), OPENED, AS_OF)
    assert any("D1 was completed before D0" in n for n in notes)


def test_stepper_figure():
    df, _ = e.clean_steps(e.sample_steps())
    fig = e.build_stepper_fig(df, AS_OF)
    names = [t.name for t in fig.data if t.name]
    assert sorted(names) == ["Done", "In progress", "Not started", "Overdue"]
    assert len(fig.layout.annotations) == 9
    assert sum(len(t.x) for t in fig.data if t.name in e.STATUSES) == 9
    no_over = e.build_stepper_fig(df, D(2026, 9, 10))
    assert "Overdue" not in [t.name for t in no_over.data]
    blocked = e.build_stepper_fig(clean([["D2", "Blocked", None, None, ""]]), AS_OF)
    assert "Blocked" in [t.name for t in blocked.data]


def test_timeline_figure():
    df, _ = e.clean_steps(e.sample_steps())
    fig = e.build_timeline_fig(df, AS_OF)
    names = [t.name for t in fig.data if t.name]
    assert names == ["Planned", "Planned (overdue)", "Completed"]
    texts = [t.replace(e.PAD, "") for tr in fig.data if tr.mode == "text" for t in tr.text]
    assert "<b>1 d late</b>" in texts and "<b>1 d early</b>" in texts and "<b>overdue 8 d</b>" in texts and "<b>on time</b>" in texts
    assert e.build_timeline_fig(clean([]), AS_OF) is None
    only_planned = e.build_timeline_fig(clean([["D0", "Not started", D(2027, 1, 1), None, ""]]), AS_OF)
    assert only_planned is not None
    before_all = e.build_timeline_fig(df, D(2020, 1, 1))
    assert before_all is not None


def test_custom_diagrams_have_explicit_text_colours_and_white_card():
    """Regression: unset text colours follow the theme and become unreadable on pale fills in dark mode."""
    df, _ = e.clean_steps(e.sample_steps())
    for fig in (e.build_stepper_fig(df, AS_OF), e.build_timeline_fig(df, AS_OF)):
        assert fig.layout.paper_bgcolor == "white" and fig.layout.plot_bgcolor == "white"
        for axis in (fig.layout.xaxis, fig.layout.yaxis):
            assert axis.tickfont.color == e.INK and axis.title.font.color == e.INK  # theme sets these per axis
        for ann in fig.layout.annotations:
            if ann.text:
                assert ann.font.color, ann.text
        for tr in fig.data:
            if tr.mode and "text" in tr.mode:
                assert tr.textfont.color


# ---------------------------------------------------------------- page loads (AppTest)
def run_script(body: str) -> AppTest:
    script = (f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport datetime as dt\nimport pandas as pd\n"
              f"from modules import eight_d as e\n{body}")
    return AppTest.from_string(script, default_timeout=60).run()


def test_page_loads_with_expected_metrics():
    at = run_script("e.render()")
    assert not at.exception
    assert [m.label for m in at.metric] == ["Steps done", "Current step", "Days open", "Overdue steps"]
    assert [m.value for m in at.metric] == ["6 of 9", "D6", "57", "1"]
    assert any("Overdue: D6 (8 d)" in w.value for w in at.warning)


def test_page_changing_as_of_and_reset_and_blank_title():
    at = run_script("e.render()")
    at.date_input[1].set_value(dt.date(2026, 12, 1)).run()
    assert not at.exception and at.metric[3].value == "3"  # D6, D7 and D8 are now past their planned dates
    at.text_input[0].set_value("").run()
    assert not at.exception
    at.button(key="eight_d_reset").click().run()
    assert not at.exception and at.metric[3].value == "1"


@pytest.mark.parametrize("state", [
    {"edited_rows": {0: {"Step": "D9", "Status": "maybe"}, 1: {"Planned date": "garbage"}}, "added_rows": [{}], "deleted_rows": []},
    {"edited_rows": {}, "added_rows": [], "deleted_rows": list(range(9))},
    {"edited_rows": {6: {"Status": "Blocked"}}, "added_rows": [{"Step": "D2", "Status": "Done"}], "deleted_rows": []},
    {"edited_rows": {7: {"Status": "Done"}, 8: {"Status": "Done", "Completed date": None}}, "added_rows": [], "deleted_rows": []},
])
def test_editor_edits_do_not_crash(state):
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import eight_d as e\ne.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["eight_d_editor_0"] = state
    at.run()
    assert not at.exception


def test_blocked_step_shows_error_and_out_of_order_note():
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import eight_d as e\ne.render()"
    at = AppTest.from_string(script, default_timeout=60)
    at.session_state["eight_d_editor_0"] = {"edited_rows": {6: {"Status": "Blocked"}, 8: {"Status": "Done"}},
                                            "added_rows": [], "deleted_rows": []}
    at.run()
    assert not at.exception
    assert any("Blocked: D6" in x.value for x in at.error)
    assert any("D8 is Done but D6 is not" in i.value for i in at.info)


def test_show_results_empty_table():
    at = run_script("e.show_results(e.clean_steps(None)[0], '', dt.date(2026, 9, 1), dt.date(2026, 9, 1))")
    assert not at.exception
    assert any("planned or completed dates" in i.value for i in at.info)


def test_timeline_labels_sit_clear_of_markers():
    """Labels are placed at the later of the planned and completed dates, with padding, so they do not cover a marker."""
    df, _ = e.clean_steps(e.sample_steps())
    fig = e.build_timeline_fig(df, AS_OF)
    label_tr = [tr for tr in fig.data if tr.mode == "text"][0]
    by_y = dict(zip(label_tr.y, label_tr.x))
    assert by_y["D5 Corrective action"] == "2026-09-30"  # planned later than completed (early finish)
    assert by_y["D4 Root cause"] == "2026-09-22" and by_y["D3 Contain"] == "2026-09-05"
    assert all(t.startswith("<b>" + e.PAD) for t in label_tr.text)
