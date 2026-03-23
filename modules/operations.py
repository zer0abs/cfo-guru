"""Operations page for supply-chain optimization and sourcing tradeoffs."""

import streamlit as st

from components.page_sections import render_info_chips, render_page_header, render_section_header
from components.recommendation_cards import (
    render_recommendation_panel,
    render_recommendation_summary,
    render_top_priorities,
)
from modules.cashflow import calculate_cash_flow_forecast
from modules.kpi import build_kpi_dashboard_data
from modules.profitability import calculate_profitability
from modules.recommendations import (
    build_cashflow_context,
    build_kpi_context,
    build_profitability_context,
    generate_recommendations,
    summarize_recommendations,
)
from modules.scenarios import get_strategy_baseline_from_state
from modules.supply_chain import (
    build_supply_chain_business_context,
    build_supply_chain_context,
    create_supplier_tradeoff_chart,
    analyze_supplier_options,
    load_sample_suppliers,
    render_supplier_comparison_table,
    render_supplier_objective_matrix,
    render_supplier_summary,
    render_supply_chain_controls,
)


def render_operations_page() -> None:
    """Render the Operations workspace."""
    baseline = get_strategy_baseline_from_state()
    demand_plan = (
        list(baseline.demand_forecast.forecast_units)
        if baseline.demand_forecast is not None and baseline.demand_forecast.use_forecast
        else None
    )
    profitability = calculate_profitability(baseline.profitability_inputs)
    cashflow = calculate_cash_flow_forecast(
        baseline.cashflow_inputs,
        demand_plan_units=demand_plan,
        demand_forecast=baseline.demand_forecast,
    )
    kpi_dashboard = build_kpi_dashboard_data(
        baseline.profitability_inputs,
        profitability,
    )
    suppliers = load_sample_suppliers()

    render_page_header(
        "Operations",
        "Compare supplier options across landed cost, lead time, MOQ, reliability, and working-capital pressure.",
    )
    render_info_chips(
        [
            {"label": "Baseline Source", "value": baseline.source, "tone": "brand"},
            {"label": "Runway", "value": f"{cashflow.runway_months:.1f} mo" if cashflow.runway_months is not None else "N/A", "tone": "warning" if (cashflow.runway_months or 99) < 6 else "success"},
            {"label": "Inventory Coverage", "value": f"{cashflow.average_inventory_coverage_months:.1f} mo" if cashflow.average_inventory_coverage_months is not None else "N/A"},
        ]
    )

    control_left, control_right = st.columns((1, 1.2))
    with control_left:
        current_supplier_name, selected_objective = render_supply_chain_controls(suppliers)
    with control_right:
        average_selling_price = (
            baseline.profitability_inputs.price_per_unit
            if baseline.profitability_inputs.price_per_unit > 0
            else (
                baseline.cashflow_inputs.monthly_revenue
                / max(baseline.cashflow_inputs.monthly_units_sold, 1.0)
            )
        )
        monthly_demand_units = (
            baseline.demand_forecast.average_forecast_units
            if baseline.demand_forecast is not None and baseline.demand_forecast.use_forecast
            else baseline.cashflow_inputs.monthly_units_sold
        )
        business_context = build_supply_chain_business_context(
            average_selling_price=average_selling_price,
            monthly_demand_units=monthly_demand_units,
            starting_cash=baseline.cashflow_inputs.starting_cash,
            runway_months=cashflow.runway_months,
            inventory_coverage_months=cashflow.average_inventory_coverage_months,
            safety_stock_units=baseline.cashflow_inputs.safety_stock_units,
        )
        analysis = analyze_supplier_options(suppliers, business_context)
        st.caption(
            "The optimizer uses current demand, inventory coverage, and cash position to rank supplier tradeoffs under different sourcing objectives."
        )

    recommendation_context = build_supply_chain_context(
        analysis,
        current_supplier_name=current_supplier_name,
        selected_objective=selected_objective,
    )
    recommendations = generate_recommendations(
        profitability_data=build_profitability_context(
            baseline.profitability_inputs,
            profitability,
        ),
        cashflow_data=build_cashflow_context(baseline.cashflow_inputs, cashflow),
        kpi_data=build_kpi_context(kpi_dashboard),
        supply_chain_data=recommendation_context,
        categories={"operations", "cash", "profitability", "strategy"},
    )
    recommendation_summary = summarize_recommendations(recommendations)

    render_section_header(
        "Action Center",
        "Supplier guidance is prioritized against the current cash and inventory posture.",
        label="Recommendations",
    )
    render_recommendation_summary(recommendation_summary)
    render_top_priorities(recommendations)

    render_section_header(
        "Supplier Tradeoffs",
        "Compare the current supplier against the best option for the selected business objective.",
        label="Supply Chain",
    )
    render_supplier_summary(
        analysis,
        current_supplier_name=current_supplier_name,
        selected_objective=selected_objective,
    )

    chart_left, chart_right = st.columns((1.15, 1))
    with chart_left:
        st.plotly_chart(
            create_supplier_tradeoff_chart(
                analysis,
                current_supplier_name=current_supplier_name,
                selected_objective=selected_objective,
            ),
            use_container_width=True,
            key="operations_supplier_tradeoff_chart",
        )
    with chart_right:
        render_section_header(
            "Objective Winners",
            "Best supplier under each sourcing priority.",
        )
        render_supplier_objective_matrix(analysis)

    render_section_header(
        "Supplier Comparison",
        "Decision-ready detail across landed cost, lead time, MOQ, reliability, and cash tie-up.",
        label="Comparison",
    )
    render_supplier_comparison_table(analysis)

    render_section_header(
        "Operational Actions",
        "Recommended next steps based on the supplier comparison and current operating conditions.",
        label="Actions",
    )
    render_recommendation_panel(recommendations)
