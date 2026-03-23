"""Main entry point for the CFO AI Streamlit application."""

from modules.cash_risk import render_cash_risk_page
from modules.financial_health import render_financial_health_page
from modules.operations import render_operations_page
from modules.reporting import render_executive_summary_page
from modules.strategy_lab import render_strategy_lab_page
from utils.layout import apply_app_theme, configure_page, render_sidebar
from utils.state import initialize_default_state


PAGE_RENDERERS = {
    "Executive Summary": render_executive_summary_page,
    "Financial Health": render_financial_health_page,
    "Cash & Risk": render_cash_risk_page,
    "Operations": render_operations_page,
    "Strategy Lab": render_strategy_lab_page,
}


def main() -> None:
    """Configure the app and render the currently selected page."""
    configure_page()
    apply_app_theme()
    initialize_default_state()
    selected_page = render_sidebar(list(PAGE_RENDERERS.keys()))
    PAGE_RENDERERS[selected_page]()


if __name__ == "__main__":
    main()
