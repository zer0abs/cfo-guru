"""Financial Health page with profitability and KPI monitoring."""

import streamlit as st

from components.recommendation_cards import (
    render_recommendation_panel,
    render_recommendation_summary,
    render_top_priorities,
)
from components.page_sections import render_info_chips, render_page_header, render_section_header
from modules.kpi import (
    build_kpi_dashboard_data,
    render_health_score,
    render_health_score_breakdown,
    render_kpi_cards,
    render_kpi_trend_charts,
)
from modules.profitability import (
    calculate_profitability,
    create_break_even_chart,
    create_profit_breakdown_waterfall,
    render_break_even_summary,
    render_cost_structure_breakdown,
    render_input_warning,
    render_profitability_details,
    render_profitability_metrics,
    render_sidebar_inputs,
)
from modules.recommendations import (
    build_health_context,
    build_kpi_context,
    build_profitability_context,
    generate_recommendations,
    summarize_recommendations,
)
from utils.formatting import format_currency, format_percent


def render_financial_health_page() -> None:
    """Render the Financial Health workspace."""
    render_page_header(
        "Financial Health",
        "Executive view for a demo e-commerce brand: monitor margin, unit economics, and cash resilience.",
    )

    try:
        inputs = render_sidebar_inputs()
        results = calculate_profitability(inputs)
    except ValueError as error:
        render_input_warning(str(error))
        return

    dashboard = build_kpi_dashboard_data(inputs, results)
    recommendations = generate_recommendations(
        profitability_data=build_profitability_context(inputs, results),
        kpi_data=build_kpi_context(dashboard),
        health_data=build_health_context(dashboard.health_score),
        categories={"profitability", "growth", "operations", "strategy"},
    )
    recommendation_summary = summarize_recommendations(recommendations)

    render_info_chips(
        [
            {"label": "Gross Margin", "value": format_percent(results.gross_margin), "tone": "success" if (results.gross_margin or 0) > 0.5 else "warning"},
            {"label": "Net Margin", "value": format_percent(results.net_margin), "tone": "danger" if (results.net_margin or 0) < 0 else "brand"},
            {"label": "Health Score", "value": f"{dashboard.health_score.score}/100", "tone": "brand"},
        ]
    )

    render_section_header(
        "Action Center",
        "Priority actions based on profitability, growth efficiency, and health signals.",
        label="Recommendations",
    )
    render_recommendation_summary(recommendation_summary)
    if recommendation_summary["high_priority_count"] > 0:
        st.warning(
            f"{recommendation_summary['high_priority_count']} high-priority recommendation(s) need attention."
        )
    render_top_priorities(recommendations)

    st.divider()
    render_section_header(
        "KPI Dashboard",
        "A compact view of margin, growth, burn, and operating performance.",
        label="KPIs",
    )
    render_kpi_cards(dashboard)
    render_kpi_trend_charts(dashboard)
    render_health_score(dashboard)

    with st.expander("Health Score Breakdown", expanded=False):
        render_health_score_breakdown(dashboard)

    st.divider()
    render_recommendation_panel(recommendations)
    render_section_header(
        "Profitability Simulator",
        "Core revenue, cost, and break-even outputs from the current unit-economics assumptions.",
        label="Financial Model",
    )
    render_profitability_metrics(results)

    left_column, right_column = st.columns((1.3, 1))

    with left_column:
        st.plotly_chart(
            create_profit_breakdown_waterfall(inputs, results),
            use_container_width=True,
            key="financial_health_profit_breakdown_chart",
        )

    with right_column:
        render_break_even_summary(results)
        st.plotly_chart(
            create_break_even_chart(inputs, results),
            use_container_width=True,
            key="financial_health_break_even_chart",
        )

    render_section_header(
        "Calculation Details",
        "Detailed output values for revenue, margin, cost, and break-even.",
        label="Detail",
    )
    render_profitability_details(results)
    render_section_header(
        "Cost Structure",
        "Current per-unit cost stack across product, shipping, fulfillment, and packaging.",
        label="Costs",
    )
    render_cost_structure_breakdown(inputs)

    render_section_header(
        "Profitability Summary",
        "Plain-English interpretation of the current financial model.",
        label="Summary",
    )
    st.write(
        f"At {inputs.units_sold:,.0f} units sold, the demo brand generates "
        f"{format_currency(results.revenue)} in revenue, "
        f"{format_currency(results.gross_profit)} in gross profit, and "
        f"{format_currency(results.net_profit)} in net profit."
    )

    if results.break_even_units is None:
        st.warning(
            "Break-even cannot be calculated because price per unit is not above variable cost per unit."
        )
    else:
        st.caption(
            f"Gross margin is {format_percent(results.gross_margin)} and net margin is "
            f"{format_percent(results.net_margin)}. Break-even occurs at "
            f"{results.break_even_units:,.0f} units or {format_currency(results.break_even_revenue)} in revenue."
        )
