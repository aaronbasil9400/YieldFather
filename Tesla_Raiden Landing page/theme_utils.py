import streamlit as st
import plotly.graph_objects as go


def apply_global_theme():
    """Inject CSS rules using Streamlit native CSS variables to seamlessly respect Streamlit's native Dark/Light theme."""
    css = """
    <style>
    /* Native CSS Variables Integration */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Headings respect Streamlit native text color */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-color) !important;
        font-weight: 700 !important;
    }

    /* Top container padding */
    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 96%;
    }

    /* KPI Cards using native secondary background variable */
    .kpi-card {
        background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.08));
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .kpi-label {
        font-size: 0.82rem;
        font-weight: 600;
        opacity: 0.8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: var(--text-color);
        line-height: 1.15;
    }
    .kpi-help {
        font-size: 0.78rem;
        opacity: 0.65;
        margin-top: 6px;
    }
    .kpi-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-left: 8px;
        vertical-align: middle;
    }
    .badge-success { background: rgba(34, 197, 94, 0.2); color: #22C55E; border: 1px solid rgba(34, 197, 94, 0.4); }
    .badge-warning { background: rgba(245, 158, 11, 0.2); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-danger { background: rgba(239, 68, 68, 0.2); color: #EF4444; border: 1px solid rgba(239, 68, 68, 0.4); }

    /* Section titles */
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text-color);
        margin: 14px 0 10px 0;
        padding-bottom: 6px;
        border-bottom: 2px solid rgba(128, 128, 128, 0.25);
    }

    /* Subtext and footnotes */
    .small-note {
        font-size: 0.82rem;
        opacity: 0.75;
        line-height: 1.5;
    }

    /* Tabs styling */
    div[data-baseweb="tab-list"] button {
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        padding: 8px 16px !important;
    }

    /* Expanders styling */
    .stExpander {
        background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.05)) !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        border-radius: 10px !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def update_plotly_theme(fig):
    """Formats Plotly figure layouts with transparent background and high-contrast labels that work seamlessly in both light and dark Streamlit native themes."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0
        )
    )

    axis_config = dict(
        gridcolor="rgba(128,128,128,0.2)",
        zerolinecolor="rgba(128,128,128,0.3)"
    )

    fig.update_xaxes(**axis_config)
    fig.update_yaxes(**axis_config)
    return fig


def render_kpi_card(label, value, help_text=None, badge=None, badge_type="success"):
    badge_html = f'<span class="kpi-badge badge-{badge_type}">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}{badge_html}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-help">{help_text or ''}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
