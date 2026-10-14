"""Manufacturing Operations Command Center: entry point and navigation."""
import streamlit as st

from modules import dmaic, line_balancing, maintenance, oee, pareto, spc

st.set_page_config(page_title="Manufacturing Operations Command Center", page_icon="🏭", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label { padding: 10px 0px; font-size: 15px; }
    </style>
    """,
    unsafe_allow_html=True,
)

MODULES = {
    "📈 SPC Control Charts": spc.render,
    "⚙️ OEE Dashboard": oee.render,
    "📊 Pareto Defects": pareto.render,
    "🔧 Maintenance & MTBF": maintenance.render,
    "⚖️ Line Balancing & Takt": line_balancing.render,
    "📐 Six Sigma: DMAIC Board": dmaic.render,
}

st.sidebar.title("🏭 Operations Hub")
st.sidebar.markdown("An integrated engineering suite for process control, reliability and continuous improvement.")
st.sidebar.markdown("---")
choice = st.sidebar.radio("Select analytical module", list(MODULES))
st.sidebar.markdown("---")
st.sidebar.info("Every table is editable. Replace the sample data with your own numbers.")

st.title("🏭 Manufacturing Operations Command Center")
st.markdown("---")
MODULES[choice]()
