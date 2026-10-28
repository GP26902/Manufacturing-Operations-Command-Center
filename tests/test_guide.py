"""Tests for modules/guide.py: consistency of the data and page loads."""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import guide  # noqa: E402


def test_every_tool_has_a_stage_and_stages_are_valid():
    for key, (_title, _section, _path, stages, question, needs, gives) in guide.TOOLS.items():
        assert stages and all(s in guide.STAGES for s in stages), key
        assert question and needs and gives, key
    for stage in guide.STAGES:
        assert guide.tools_in_stage(stage), stage


def test_paths_and_titles_unique():
    paths, titles = guide.all_paths(), [v[0] for v in guide.TOOLS.values()]
    assert len(paths) == len(set(paths)) and len(titles) == len(set(titles))


def test_scenarios_reference_real_tools_and_have_reasons():
    for key, (label, steps) in guide.SCENARIOS.items():
        assert label and len(steps) >= 3, key
        for tool_key, why in steps:
            assert tool_key in guide.TOOLS and len(why) > 20, (key, tool_key)


def test_recommend():
    steps = guide.recommend("unstable_quality")
    assert [s["step"] for s in steps] == list(range(1, len(steps) + 1))
    assert steps[0]["title"] == "Gage R&R" and steps[0]["path"] == "gage-rr"
    assert guide.recommend("nonsense") == [] and guide.recommend(None) == []


def test_cheat_sheet_has_a_row_per_tool():
    sheet = guide.cheat_sheet()
    assert len(sheet) == len(guide.TOOLS) and list(sheet.columns)[:3] == ["Tool", "Section", "Stage"]


def test_stage_figure_has_four_boxes_and_explicit_colours():
    fig = guide.build_stage_fig()
    boxes = [s for s in fig.layout.shapes if s.line.width == 2]
    assert len(boxes) == 4 and fig.layout.paper_bgcolor == "white"
    for ann in fig.layout.annotations:
        if ann.text:
            assert ann.font.color, ann.text
    all_text = " ".join(a.text for a in fig.layout.annotations)
    assert all(guide.TOOLS[k][0] in all_text for k in guide.TOOLS)


def test_page_loads_and_changes_with_scenario():
    script = f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nfrom modules import guide\nguide.render()"
    at = AppTest.from_string(script, default_timeout=60).run()
    assert not at.exception
    first = [m.value for m in at.markdown if m.value.startswith("**1.")]
    assert first and "8D Tracker" in first[0] and "(/eight-d)" in first[0]
    at.selectbox(key="guide_scenario").set_value("slow_line").run()
    assert not at.exception
    assert any("OEE Dashboard" in m.value for m in at.markdown if m.value.startswith("**1."))
