"""Navigation: sidebar sections, unique URL paths, and a full app load."""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


def test_two_named_sections_with_expected_tools():
    assert list(app.NAV_SECTIONS) == ["Operations Analytics", "CI Toolkit"]
    ops = [t for t, *_ in app.NAV_SECTIONS["Operations Analytics"]]
    ci = [t for t, *_ in app.NAV_SECTIONS["CI Toolkit"]]
    assert ops == ["SPC Control Charts", "OEE Dashboard", "Pareto Defects", "Maintenance & MTBF", "Line Balancing & Takt",
                   "Gage R&R"]
    assert "Six Sigma: DMAIC Board" in ci and "Six Sigma: DMAIC Board" not in ops
    assert any("FMEA" in t for t in ci) and "5S Audit" in ci
    assert "5 Why Analysis" in ci and "Fishbone (Ishikawa)" in ci
    assert "8D Tracker" in ci and "Kaizen Log" in ci and "Which Tool When?" in ci


def test_url_paths_unique_and_functions_callable():
    entries = [e for section in app.NAV_SECTIONS.values() for e in section]
    paths = [e[2] for e in entries]
    assert len(paths) == len(set(paths))
    assert all(callable(e[3]) for e in entries)


def test_app_loads_default_page_without_error():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert "Manufacturing Operations Command Center" in at.title[0].value


def test_fallback_navigation_for_old_streamlit():
    script = (
        f"import sys\nsys.path.insert(0, {str(ROOT)!r})\nimport app\n"
        "fn = app.fallback_navigation(app.NAV_SECTIONS)\nfn()\n"
    )
    at = AppTest.from_string(script, default_timeout=60).run()
    assert not at.exception
    assert at.sidebar.radio[0].options == ["Operations Analytics", "CI Toolkit"]
    at.sidebar.radio[0].set_value("CI Toolkit").run()
    assert not at.exception
    five_s = [o for o in at.sidebar.radio[1].options if "5S" in o][0]
    at.sidebar.radio[1].set_value(five_s).run()
    assert not at.exception
    assert [h.value for h in at.header] == ["🧹 5S Audit"]


def test_guide_tools_match_navigation_exactly():
    """Every page (except the guide itself) is described in the guide, and every guide link points at a real page."""
    from modules import guide

    nav_paths = {e[2] for section in app.NAV_SECTIONS.values() for e in section}
    assert set(guide.all_paths()) == nav_paths - {"guide"}
    nav_titles = {e[2]: e[0] for section in app.NAV_SECTIONS.values() for e in section}
    for key, (title, section, path, *_rest) in guide.TOOLS.items():
        assert nav_titles[path] == title, key
        assert any(path == e[2] for e in app.NAV_SECTIONS[section]), key
