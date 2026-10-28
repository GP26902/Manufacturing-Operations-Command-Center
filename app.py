"""Manufacturing Operations Command Center: entry point and navigation."""
import streamlit as st

from modules import (
    dmaic,
    eight_d,
    fishbone,
    five_s,
    five_why,
    fmea,
    kaizen,
    line_balancing,
    maintenance,
    oee,
    pareto,
    spc,
)

# Sidebar sections. Each entry: (page title, icon, URL path, render function).
# URL paths are unique and stable, so a tool can be linked directly: <app-url>/fmea
NAV_SECTIONS = {
    "Operations Analytics": [
        ("SPC Control Charts", "📈", "spc", spc.render),
        ("OEE Dashboard", "⚙️", "oee", oee.render),
        ("Pareto Defects", "📊", "pareto", pareto.render),
        ("Maintenance & MTBF", "🔧", "maintenance", maintenance.render),
        ("Line Balancing & Takt", "⚖️", "line-balancing", line_balancing.render),
    ],
    "CI Toolkit": [
        ("Six Sigma: DMAIC Board", "📐", "dmaic", dmaic.render),
        ("FMEA (DFMEA / PFMEA)", "⚠️", "fmea", fmea.render),
        ("5S Audit", "🧹", "five-s", five_s.render),
        ("5 Why Analysis", "❓", "five-why", five_why.render),
        ("Fishbone (Ishikawa)", "🐟", "fishbone", fishbone.render),
        ("8D Tracker", "📋", "eight-d", eight_d.render),
        ("Kaizen Log", "🔁", "kaizen", kaizen.render),
    ],
}


def build_pages(sections):
    """Create st.Page objects grouped by section (first page of the first section is the default)."""
    pages, first = {}, True
    for section, entries in sections.items():
        pages[section] = []
        for title, icon, path, fn in entries:
            pages[section].append(st.Page(fn, title=title, icon=icon, url_path=path, default=first))
            first = False
    return pages


def fallback_navigation(sections):
    """Two-step sidebar selection for Streamlit versions without st.navigation. Returns the render function."""
    section = st.sidebar.radio("Section", list(sections))
    titles = {f"{icon} {title}": fn for title, icon, _, fn in sections[section]}
    choice = st.sidebar.radio("Select analytical module", list(titles), key=f"nav_{section}")
    return titles[choice]


def main():
    st.set_page_config(page_title="Manufacturing Operations Command Center", page_icon="🏭", layout="wide")
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label { padding: 10px 0px; font-size: 15px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if hasattr(st, "navigation") and hasattr(st, "Page"):
        page = st.navigation(build_pages(NAV_SECTIONS))
        run = page.run
    else:
        run = fallback_navigation(NAV_SECTIONS)

    st.sidebar.markdown("---")
    st.sidebar.title("🏭 Operations Hub")
    st.sidebar.markdown("An integrated engineering suite for process control, reliability and continuous improvement.")
    st.sidebar.info("Every table is editable. Replace the sample data with your own numbers.")

    st.title("🏭 Manufacturing Operations Command Center")
    st.markdown("---")
    run()


if __name__ == "__main__":
    main()
