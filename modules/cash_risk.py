"""Cash & Risk page with the Phase 2 cash flow forecast."""

import streamlit as st

from components.recommendation_cards import (
    render_recommendation_panel,
    render_recommendation_summary,
    render_top_priorities,
)
from components.page_sections import render_info_chips, render_page_header, render_section_header
from modules.cashflow import (
    calculate_cash_flow_forecast,
    create_cash_balance_chart,
    render_cash_alert,
    render_cash_outflow_breakdown,
    render_cashflow_metrics,
    render_forecast_table,
    render_inventory_policy_summary,
    render_inventory_risk_summary,
    render_sidebar_inputs,
)
from modules.forecasting import (
    build_channel_economics_context,
    build_forecast_context,
    calculate_channel_economics,
    create_channel_economics_chart,
    create_demand_forecast_chart,
    render_channel_economics_summary,
    render_channel_economics_table,
    render_forecast_detail_table,
    render_forecast_sidebar_controls,
    render_forecast_summary,
)
from modules.recommendations import (
    build_cashflow_context,
    generate_recommendations,
    summarize_recommendations,
)
from utils.formatting import format_currency


def render_cash_risk_page() -> None:
    """Render the Cash & Risk workspace."""
    render_page_header(
        "Cash & Risk",
        "Cash runway monitor for a demo e-commerce brand balancing growth spend and liquidity risk.",
    )

    try:
        inputs = render_sidebar_inputs()
        demand_forecast = render_forecast_sidebar_controls(
            inputs.forecast_horizon_months,
            inputs.monthly_units_sold,
        )
        demand_plan_units = (
            demand_forecast.forecast_units if demand_forecast.use_forecast else None
        )
        results = calculate_cash_flow_forecast(
            inputs,
            demand_plan_units=demand_plan_units,
            demand_forecast=demand_forecast,
        )
        average_selling_price = (
            inputs.monthly_revenue / max(inputs.monthly_units_sold, 1.0)
        )
        channel_economics = calculate_channel_economics(
            demand_forecast,
            average_selling_price=average_selling_price,
            shared_variable_cost_per_unit=(
                inputs.product_cost_per_unit
                + inputs.shipping_cost_per_unit
                + inputs.fulfillment_cost_per_unit
                + inputs.packaging_cost_per_unit
            ),
        )
    except ValueError as error:
        st.error(str(error))
        return

    render_info_chips(
        [
            {"label": "Demand Source", "value": results.demand_source, "tone": "brand"},
            {"label": "Inventory Posture", "value": results.inventory_balance_label, "tone": "warning" if results.inventory_balance_label == "Excess" else "success"},
            {"label": "Inventory Risk", "value": results.inventory_risk_level, "tone": "danger" if results.inventory_risk_level == "High" else "warning"},
        ]
    )
    render_cashflow_metrics(results)
    render_cash_alert(results)
    render_section_header(
        "Inventory Risk & Stress",
        "Stockout exposure, coverage pressure, and overstock signals from the current forecast.",
        label="Inventory",
    )
    render_inventory_risk_summary(results)

    recommendations = generate_recommendations(
        cashflow_data=build_cashflow_context(inputs, results),
        forecast_data=(
            build_forecast_context(demand_forecast)
            | build_channel_economics_context(channel_economics)
        ),
        categories={"cash", "operations", "strategy"},
    )
    recommendation_summary = summarize_recommendations(recommendations)

    render_section_header(
        "Action Center",
        "Priority actions based on runway, inventory posture, and demand quality.",
        label="Recommendations",
    )
    render_recommendation_summary(recommendation_summary)
    if recommendation_summary["high_priority_count"] > 0:
        st.warning(
            f"{recommendation_summary['high_priority_count']} high-priority recommendation(s) need attention."
        )
    render_top_priorities(recommendations)

    left_column, right_column = st.columns((1.3, 1))

    with left_column:
        st.plotly_chart(
            create_cash_balance_chart(results),
            use_container_width=True,
            key="cash_risk_cash_balance_chart",
        )

    with right_column:
        render_section_header(
            "Forecast Summary",
            "A quick read on cash trajectory and inventory-buy timing.",
        )
        st.write(
            f"Starting from {format_currency(inputs.starting_cash)}, the forecast ends at "
            f"{format_currency(results.ending_cash)} after {inputs.forecast_horizon_months} months."
        )
        st.write(
            f"At roughly {results.effective_units_sold:,.0f} fulfilled units per month, the model averages "
            f"{format_currency(results.monthly_inventory_purchase_outflow)} of inventory-buy cash and "
            f"{format_currency(results.monthly_fulfillment_outflow)} of fulfillment-at-sale cash."
        )
        st.caption(
            "Product cost is modeled at purchase timing, while shipping, fulfillment, and packaging are modeled at sale timing."
        )
        st.write(
            f"Inventory posture is currently {results.inventory_balance_label.lower()}, with about "
            f"{format_currency(results.cash_tied_in_excess_inventory)} tied up above target coverage."
        )
        st.caption(f"Demand source: {results.demand_source}")

    render_section_header(
        "Demand Forecasting",
        "Historical demand, forecast method, and forward-looking demand baseline.",
        label="Forecast",
    )
    render_forecast_summary(demand_forecast, inputs.monthly_units_sold)
    st.plotly_chart(
        create_demand_forecast_chart(demand_forecast),
        use_container_width=True,
        key="cash_risk_demand_forecast_chart",
    )
    with st.expander("Demand Forecast Detail", expanded=False):
        render_forecast_detail_table(demand_forecast)

    render_section_header(
        "Channel Economics",
        "How paid, organic, and retention demand contribute to growth quality.",
        label="Channels",
    )
    render_channel_economics_summary(channel_economics)
    st.plotly_chart(
        create_channel_economics_chart(channel_economics),
        use_container_width=True,
        key="cash_risk_channel_economics_chart",
    )
    with st.expander("Channel Contribution Detail", expanded=False):
        render_channel_economics_table(channel_economics)

    render_section_header(
        "Inventory Policy",
        "Current reorder settings and inventory planning posture.",
        label="Policy",
    )
    render_inventory_policy_summary(inputs, results)

    render_section_header(
        "Monthly Cash Cost Structure",
        "Variable and fixed cash outflows separated for easier cash planning.",
        label="Costs",
    )
    render_cash_outflow_breakdown(results)

    render_section_header(
        "Monthly Forecast Table",
        "Detailed monthly forecast with inventory and cash-flow mechanics.",
        label="Table",
    )
    render_forecast_table(results)

    st.divider()
    render_recommendation_panel(recommendations)
