import streamlit as st
import theme_utils

st.set_page_config(
    page_title="Factory Analytics Hub",
    page_icon="🏭",
    layout="wide"
)

# Apply global CSS variables for native Streamlit light/dark theme support
theme_utils.apply_global_theme()

st.markdown("""
<style>
.hero-container {
    text-align: center;
    padding: 2.5rem 1rem 2rem 1rem;
    margin-bottom: 2rem;
    background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.08));
    border: 1px solid rgba(128, 128, 128, 0.2);
    border-radius: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.hero-title {
    font-size: 3.2rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
    color: var(--text-color);
    letter-spacing: -0.5px;
}

.hero-subtitle {
    font-size: 1.2rem;
    opacity: 0.75;
    margin-bottom: 0;
    font-weight: 500;
}

div.stButton > button {
    width: 100%;
    height: 400px;
    border-radius: 24px;
    border: 1px solid rgba(128, 128, 128, 0.2);
    color: white;
    font-size: 1.25rem;
    font-weight: 700;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    white-space: normal;
    padding: 28px;
    text-align: left;
}

#b-yield_btn button {
    background: linear-gradient(135deg, #1E40AF, #3B82F6);
}

#b-spc_btn button {
    background: linear-gradient(135deg, #0F766E, #06B6D4);
}

div.stButton > button:hover {
    transform: translateY(-6px);
    box-shadow: 0 18px 45px rgba(0,0,0,0.35);
}

div.stButton > button:focus {
    outline: none;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero-container">
        <div class="hero-title">🏭 Factory Analytics Hub</div>
        <div class="hero-subtitle">Teradyne UltraFlex & Factory Production Yield Intelligence</div>
    </div>
    """,
    unsafe_allow_html=True
)

col1, col2 = st.columns(2, gap="large")

yield_label = """
📊

Yield Report and Defect Analysis

• Production yield analysis
• Defect Pareto (Past 28 Days)
• Daily and weekly trends
• WIP tracking & serial status

Click to open ➔
"""

spc_label = """
📈

SPC Dashboard

• Statistical Process Control (SPC)
• Automated Cpk & Cp calculation
• Test result & channel filtering
• Parameter limit analysis

Click to open ➔
"""

with col1:
    if st.button(yield_label, use_container_width=True, key="yield_btn"):
        st.switch_page("pages/1_Yield_Report.py")

with col2:
    if st.button(spc_label, use_container_width=True, key="spc_btn"):
        st.switch_page("pages/2_SPC_Dashboard.py")