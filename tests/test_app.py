"""Smoke tests: every module renders without exceptions."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"

LABELS = [
    "📈 SPC Control Charts", "⚙️ OEE Dashboard", "📊 Pareto Defects",
    "🔧 Maintenance & MTBF", "⚖️ Line Balancing & Takt", "📐 Six Sigma: DMAIC Board",
]


@pytest.mark.parametrize("label", LABELS)
def test_module_renders(label):
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.sidebar.radio[0].set_value(label).run()
    assert not at.exception, [e.value for e in at.exception]
