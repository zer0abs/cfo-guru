"""Layout and navigation helpers for the Streamlit app."""

import streamlit as st


def configure_page() -> None:
    """Set global page-level configuration."""
    st.set_page_config(
        page_title="CFOGuru",
        page_icon=":bar_chart:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def apply_app_theme() -> None:
    """Inject a cleaner, more modern dashboard style across the app."""
    st.markdown(
        """
        <style>
        :root {
            --surface: rgba(248, 255, 251, 0.96);
            --surface-strong: #fdfefd;
            --text-strong: #081514;
            --text-muted: #335850;
            --border-soft: rgba(5, 97, 75, 0.22);
            --shadow-soft: 0 20px 46px rgba(2, 14, 14, 0.10);
            --brand: #05614b;
            --brand-soft: rgba(1, 222, 130, 0.16);
            --brand-strong: #05614b;
            --danger: #b42318;
            --warning: #9a6700;
            --success: #05614b;
            --navy-soft: rgba(2, 14, 14, 0.06);
            --sidebar-bg-top: #020e0e;
            --sidebar-bg-bottom: #05614b;
            --mint: #01de82;
            --mint-soft: rgba(1, 222, 130, 0.14);
            --teal-soft: rgba(5, 97, 75, 0.12);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(1, 222, 130, 0.16), transparent 24%),
                radial-gradient(circle at bottom right, rgba(5, 97, 75, 0.14), transparent 30%),
                linear-gradient(180deg, #f2fbf7 0%, #e4f4ed 100%);
            color: var(--text-strong);
        }

        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 3.2rem;
            max-width: 1440px;
        }

        [data-testid="stHeader"] {
            background: rgba(245, 255, 250, 0.82);
            backdrop-filter: blur(10px);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--sidebar-bg-top) 0%, var(--sidebar-bg-bottom) 100%);
            border-right: 1px solid rgba(1, 222, 130, 0.10);
        }

        [data-testid="stSidebar"] * {
            color: #f8fafc;
        }

        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #f8fafc !important;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(244,255,249,0.96));
            border: 1px solid rgba(5, 97, 75, 0.18);
            border-radius: 20px;
            padding: 1.05rem 1.05rem 0.9rem 1.05rem;
            box-shadow: var(--shadow-soft);
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.77rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--text-muted);
            font-weight: 700;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.48rem;
            font-weight: 700;
            color: var(--text-strong);
            line-height: 1.2;
        }

        [data-testid="stMetricDelta"] {
            font-size: 0.88rem;
        }

        div[data-testid="stPlotlyChart"],
        div[data-testid="stDataFrame"],
        div[data-testid="stExpander"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(244,255,249,0.96));
            border: 1px solid rgba(5, 97, 75, 0.18);
            border-radius: 20px;
            padding: 0.8rem;
            box-shadow: var(--shadow-soft);
        }

        div[data-testid="stDataFrame"] {
            padding-top: 0.4rem;
        }

        div[data-testid="stDataFrame"] [role="grid"] {
            border-radius: 14px;
            overflow: hidden;
        }

        div[data-testid="stDataFrame"] [role="columnheader"] {
            background: rgba(5, 97, 75, 0.06);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            color: var(--text-muted);
        }

        div[data-testid="stDataFrame"] [role="gridcell"] {
            font-size: 0.9rem;
            color: var(--text-strong);
        }

        [data-testid="stSidebar"] [data-testid="stRadio"] label,
        [data-testid="stSidebar"] [data-testid="stSelectbox"] label,
        [data-testid="stSidebar"] [data-testid="stNumberInput"] label,
        [data-testid="stSidebar"] [data-testid="stTextArea"] label {
            font-size: 0.82rem;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            font-weight: 700;
        }

        [data-testid="stSidebar"] [role="radiogroup"] > label {
            padding: 0.32rem 0;
        }

        [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.15rem;
        }

        div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] > div[data-testid="stAlert"] {
            border-radius: 16px;
        }

        h1, h2, h3 {
            color: var(--text-strong) !important;
            letter-spacing: -0.02em;
        }

        h1 {
            font-size: 2.7rem;
            font-weight: 800;
            margin-bottom: 0.35rem;
        }

        h2 {
            font-size: 1.55rem;
            margin-top: 0.2rem;
        }

        h3 {
            font-size: 1.1rem;
        }

        div[data-testid="stMarkdownContainer"],
        div[data-testid="stText"],
        p,
        label,
        span,
        .stCaption,
        .st-emotion-cache-10trblm,
        .st-emotion-cache-16idsys {
            color: var(--text-muted) !important;
        }

        div[data-testid="stMarkdownContainer"] strong,
        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3 {
            color: var(--text-strong) !important;
        }

        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div {
            background: rgba(2, 14, 14, 0.55) !important;
            color: #f8fafc !important;
            border: 1px solid rgba(1, 222, 130, 0.14) !important;
            border-radius: 14px !important;
        }

        .cfo-section-label {
            display: inline-block;
            margin-bottom: 0.65rem;
            padding: 0.33rem 0.68rem;
            border-radius: 999px;
            background: var(--mint-soft);
            color: #020e0e !important;
            font-size: 0.73rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .cfo-sidebar-brand {
            color: var(--mint) !important;
            font-size: 1.9rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            line-height: 1.1;
            margin: 0 0 0.3rem 0;
        }

        .cfo-sidebar-subtitle {
            color: rgba(248, 250, 252, 0.84) !important;
            font-size: 0.95rem;
            line-height: 1.5;
            margin: 0 0 0.9rem 0;
        }

        .cfo-page-intro {
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(232, 251, 242, 0.98));
            border: 1px solid rgba(5, 97, 75, 0.16);
            border-radius: 24px;
            padding: 1.15rem 1.2rem;
            box-shadow: var(--shadow-soft);
            margin-bottom: 1.2rem;
        }

        .cfo-page-title {
            font-size: 2.65rem;
            font-weight: 800;
            color: var(--text-strong);
            letter-spacing: -0.03em;
            margin: 0 0 0.3rem 0;
        }

        .cfo-page-description {
            color: var(--text-muted);
            font-size: 1rem;
            line-height: 1.6;
            margin: 0;
            max-width: 900px;
        }

        .cfo-section-heading {
            margin: 1.2rem 0 0.8rem 0;
        }

        .cfo-section-title {
            color: var(--text-strong);
            font-size: 1.3rem;
            font-weight: 700;
            margin: 0 0 0.15rem 0;
            letter-spacing: -0.02em;
        }

        .cfo-section-description {
            color: var(--text-muted);
            font-size: 0.95rem;
            margin: 0;
        }

        .cfo-info-grid {
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
            margin: 0.15rem 0 0.15rem 0;
        }

        .cfo-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.34rem 0.68rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.68);
            color: var(--text-muted) !important;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            border: 1px solid rgba(5, 97, 75, 0.14);
        }

        .chip-brand {
            background: var(--brand-soft);
            color: var(--brand-strong) !important;
        }

        .chip-warning {
            background: rgba(154, 103, 0, 0.10);
            color: var(--warning) !important;
        }

        .chip-danger {
            background: rgba(180, 35, 24, 0.10);
            color: var(--danger) !important;
        }

        .chip-success {
            background: var(--mint-soft);
            color: var(--success) !important;
        }

        .cfo-panel {
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(244,255,249,0.96));
            border: 1px solid rgba(5, 97, 75, 0.16);
            border-radius: 22px;
            padding: 1rem 1.05rem;
            box-shadow: var(--shadow-soft);
        }

        .cfo-text-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(244,255,249,0.97));
            border: 1px solid rgba(5, 97, 75, 0.16);
            border-radius: 20px;
            padding: 1rem 1.05rem;
            box-shadow: var(--shadow-soft);
            height: 100%;
        }

        .cfo-text-card h3 {
            margin-top: 0;
            margin-bottom: 0.55rem;
        }

        .cfo-text-card ul {
            margin: 0;
            padding-left: 1.1rem;
        }

        .cfo-text-card li {
            margin-bottom: 0.55rem;
            color: var(--text-muted);
            line-height: 1.5;
        }

        .recommendation-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.99), rgba(242,255,248,0.98));
            border: 1px solid rgba(5, 97, 75, 0.16);
            border-radius: 22px;
            padding: 1.2rem 1.25rem;
            box-shadow: var(--shadow-soft);
            margin-bottom: 1rem;
        }

        .recommendation-card.priority-high {
            border-color: rgba(5, 97, 75, 0.22);
            box-shadow: 0 18px 38px rgba(5, 97, 75, 0.08);
        }

        .recommendation-title {
            color: var(--text-strong);
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
        }

        .recommendation-meta {
            display: flex;
            gap: 0.4rem;
            flex-wrap: wrap;
            margin-bottom: 0.75rem;
        }

        .recommendation-badge {
            display: inline-block;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            font-size: 0.73rem;
            font-weight: 700;
            letter-spacing: 0.03em;
        }

        .badge-high {
            background: rgba(5, 97, 75, 0.12);
            color: var(--brand-strong);
        }

        .badge-medium {
            background: rgba(1, 222, 130, 0.16);
            color: var(--brand-strong);
        }

        .badge-low {
            background: rgba(5, 97, 75, 0.08);
            color: var(--text-muted);
        }

        .badge-category {
            background: rgba(5, 97, 75, 0.06);
            color: var(--brand-strong);
        }

        .recommendation-line {
            color: var(--text-muted);
            margin: 0.35rem 0;
            line-height: 1.5;
        }

        .recommendation-impact {
            margin-top: 0.8rem;
            padding-top: 0.8rem;
            border-top: 1px solid rgba(148, 163, 184, 0.16);
        }

        .recommendation-line strong {
            color: var(--text-strong);
        }

        .top-priority-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.99), rgba(230, 252, 241, 0.99));
            border: 1px solid rgba(1, 222, 130, 0.20);
            border-radius: 20px;
            padding: 1rem 1.1rem;
            box-shadow: var(--shadow-soft);
            margin-bottom: 0.8rem;
        }

        .top-priority-card strong {
            color: var(--text-strong);
        }

        .cfo-summary-banner {
            background: linear-gradient(135deg, rgba(5, 97, 75, 0.14), rgba(1, 222, 130, 0.12));
            border: 1px solid rgba(5, 97, 75, 0.18);
            border-radius: 20px;
            padding: 1rem 1.05rem;
            color: var(--text-strong);
            margin: 0.6rem 0 1.1rem 0;
        }

        .cfo-summary-banner strong {
            color: var(--text-strong);
        }

        .cfo-download-row {
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(242,255,248,0.98));
            border: 1px solid rgba(5, 97, 75, 0.16);
            border-radius: 20px;
            padding: 0.85rem 0.95rem;
            box-shadow: var(--shadow-soft);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(page_names: list[str]) -> str:
    """Render the sidebar and return the selected page name."""
    with st.sidebar:
        st.markdown(
            '<div class="cfo-sidebar-brand">CFOGuru</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cfo-sidebar-subtitle">Finance OS for modern e-commerce operators.</div>',
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown('<div class="cfo-section-label">Navigation</div>', unsafe_allow_html=True)
        selected_page = st.radio("Navigate", page_names, index=0)
        st.divider()
        st.markdown('<div class="cfo-section-label">Demo Context</div>', unsafe_allow_html=True)
        st.caption(
            "Default demo: a growing e-commerce brand focused on margin, CAC efficiency, and cash runway."
        )

    return selected_page
