"""Executive summary and report layer for CFO AI."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from components.page_sections import (
    render_info_chips,
    render_metric_row,
    render_page_header,
    render_section_header,
    render_text_card,
)
from components.recommendation_cards import (
    render_recommendation_panel,
    render_recommendation_summary,
    render_top_priorities,
)
from modules.cashflow import calculate_cash_flow_forecast
from modules.forecasting import (
    build_channel_economics_context,
    build_forecast_context,
    calculate_channel_economics,
)
from modules.kpi import build_kpi_dashboard_data
from modules.profitability import calculate_profitability
from modules.recommendations import (
    build_cashflow_context,
    build_health_context,
    build_kpi_context,
    build_profitability_context,
    generate_recommendations,
    summarize_recommendations,
)
from modules.scenarios import (
    ScenarioAnalysis,
    get_available_scenarios,
    get_strategy_baseline_from_state,
    run_scenario_analysis,
)
from modules.supply_chain import (
    OBJECTIVE_LABELS,
    SupplyChainAnalysis,
    SupplyChainBusinessContext,
    analyze_supplier_options,
    build_supply_chain_business_context,
    build_supply_chain_context,
    load_sample_suppliers,
    recommend_supplier_for_objective,
)
from utils.formatting import format_currency, format_percent


@dataclass(frozen=True)
class ExecutiveKeyMetric:
    """Compact metric used in the executive summary cards."""

    label: str
    value: str
    delta: str | None = None


@dataclass(frozen=True)
class ExecutiveSummaryData:
    """Structured executive summary output synthesized from app modules."""

    headline: str
    narrative_summary: str
    key_metrics: list[ExecutiveKeyMetric]
    top_risks: list[str]
    top_opportunities: list[str]
    recommended_actions: list[str]
    scenario_takeaway: str
    sourcing_takeaway: str
    top_supplier_objective: str
    top_supplier_name: str
    top_scenario_name: str
    recommendations: list[dict]
    recommendation_summary: dict[str, object]
    export_metrics: pd.DataFrame
    export_text: str


def render_executive_summary_page() -> None:
    """Render the operator-facing executive summary page."""
    report = generate_executive_summary()

    render_page_header(
        "Executive Summary",
        "Founder-ready summary of profitability, cash, inventory, demand quality, scenario risk, and sourcing priorities.",
    )
    render_info_chips(
        [
            {"label": "Top Scenario", "value": report.top_scenario_name, "tone": "warning"},
            {"label": "Sourcing Priority", "value": report.top_supplier_objective, "tone": "brand"},
            {"label": "Recommended Supplier", "value": report.top_supplier_name, "tone": "success"},
        ]
    )
    st.markdown(
        (
            '<div class="cfo-summary-banner">'
            f"<strong>{report.headline}</strong><br>{report.narrative_summary}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    render_metric_row(
        [
            {"label": metric.label, "value": metric.value, "delta": metric.delta}
            for metric in report.key_metrics
        ],
        columns_per_row=3,
    )

    render_section_header(
        "Executive Priorities",
        "The clearest risks, opportunities, and actions from the current operating baseline.",
        label="Summary",
    )
    section_left, section_right = st.columns((1.05, 1))
    with section_left:
        render_text_card("Top Risks", report.top_risks)
        st.markdown("<div style='height: 0.85rem;'></div>", unsafe_allow_html=True)
        render_text_card("Recommended Actions", report.recommended_actions)
    with section_right:
        render_text_card("Top Opportunities", report.top_opportunities)
        st.markdown("<div style='height: 0.85rem;'></div>", unsafe_allow_html=True)
        render_text_card(
            "Scenario and Sourcing Takeaways",
            [report.scenario_takeaway, report.sourcing_takeaway],
        )

    st.divider()
    render_section_header(
        "Action Center",
        "The recommendation engine prioritizes the actions with the highest current decision value.",
        label="Recommendations",
    )
    render_recommendation_summary(report.recommendation_summary)
    render_top_priorities(report.recommendations)

    render_section_header(
        "Exports",
        "Lightweight summary outputs for sharing or adding to a portfolio walkthrough.",
        label="Reporting",
    )
    st.markdown('<div class="cfo-download-row">', unsafe_allow_html=True)
    export_left, export_right = st.columns((1, 1))
    with export_left:
        st.download_button(
            "Download Summary Text",
            data=report.export_text,
            file_name="cfo_ai_executive_summary.txt",
            mime="text/plain",
        )
    with export_right:
        st.download_button(
            "Download Executive Metrics CSV",
            data=report.export_metrics.to_csv(index=False),
            file_name="cfo_ai_executive_metrics.csv",
            mime="text/csv",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    render_recommendation_panel(report.recommendations)


def generate_executive_summary() -> ExecutiveSummaryData:
    """Build the full structured executive summary from current app outputs."""
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
    channel_economics = (
        calculate_channel_economics(
            baseline.demand_forecast,
            average_selling_price=baseline.profitability_inputs.price_per_unit,
            shared_variable_cost_per_unit=baseline.profitability_inputs.variable_cost_per_unit,
        )
        if baseline.demand_forecast is not None
        else None
    )

    supply_context = _build_supply_chain_analysis(
        baseline_source=baseline.source,
        price_per_unit=baseline.profitability_inputs.price_per_unit,
        cashflow=cashflow,
        monthly_demand_units=(
            baseline.demand_forecast.average_forecast_units
            if baseline.demand_forecast is not None
            else baseline.cashflow_inputs.monthly_units_sold
        ),
        starting_cash=baseline.cashflow_inputs.starting_cash,
        safety_stock_units=baseline.cashflow_inputs.safety_stock_units,
    )
    supplier_objective = _select_supplier_objective(cashflow)
    supplier_context = build_supply_chain_context(
        supply_context,
        current_supplier_name=_current_supplier_name(supply_context),
        selected_objective=supplier_objective,
    )
    recommendations = generate_recommendations(
        profitability_data=build_profitability_context(
            baseline.profitability_inputs,
            profitability,
        ),
        cashflow_data=build_cashflow_context(baseline.cashflow_inputs, cashflow),
        kpi_data=build_kpi_context(kpi_dashboard),
        health_data=build_health_context(kpi_dashboard.health_score),
        forecast_data=(
            build_forecast_context(baseline.demand_forecast)
            | (
                build_channel_economics_context(channel_economics)
                if channel_economics is not None
                else {}
            )
        ),
        supply_chain_data=supplier_context,
        categories={"profitability", "cash", "growth", "operations", "strategy"},
    )
    recommendation_summary = summarize_recommendations(recommendations)

    top_scenario = _select_top_scenario(baseline)
    headline = _build_headline(
        profitability.net_margin,
        cashflow.runway_months,
        cashflow.inventory_balance_label,
        channel_economics.growth_quality_label if channel_economics is not None else None,
    )
    narrative_summary = _build_narrative_summary(
        profitability.net_margin,
        cashflow.runway_months,
        cashflow.inventory_risk_level,
        cashflow.inventory_balance_label,
        baseline.demand_forecast.trend_direction if baseline.demand_forecast is not None else None,
        channel_economics.growth_quality_label if channel_economics is not None else None,
        supplier_objective,
        supplier_context.get("supplier_selected_name"),
    )

    top_risks = _build_top_risks(
        profitability.net_margin,
        cashflow,
        baseline.demand_forecast.trend_direction if baseline.demand_forecast is not None else None,
        channel_economics.growth_quality_label if channel_economics is not None else None,
        top_scenario,
    )
    top_opportunities = _build_top_opportunities(
        profitability.gross_margin,
        cashflow,
        channel_economics.growth_quality_label if channel_economics is not None else None,
        supplier_context,
    )
    recommended_actions = [recommendation["action"] for recommendation in recommendations[:4]]
    scenario_takeaway = _build_scenario_takeaway(top_scenario)
    sourcing_takeaway = _build_sourcing_takeaway(
        supplier_objective,
        supplier_context,
        cashflow,
    )

    key_metrics = [
        ExecutiveKeyMetric(
            label="Business Health",
            value=f"{kpi_dashboard.health_score.score}/100",
            delta=kpi_dashboard.health_score.interpretation,
        ),
        ExecutiveKeyMetric(
            label="Net Margin",
            value=format_percent(profitability.net_margin),
        ),
        ExecutiveKeyMetric(
            label="Runway",
            value=_format_months(cashflow.runway_months),
        ),
        ExecutiveKeyMetric(
            label="Inventory Posture",
            value=cashflow.inventory_balance_label,
        ),
        ExecutiveKeyMetric(
            label="Demand Trend",
            value=(
                baseline.demand_forecast.trend_direction
                if baseline.demand_forecast is not None
                else "Manual"
            ),
        ),
        ExecutiveKeyMetric(
            label="Growth Quality",
            value=(
                channel_economics.growth_quality_label
                if channel_economics is not None
                else "N/A"
            ),
        ),
    ]

    export_metrics = pd.DataFrame(
        [
            {"Metric": "Business Health Score", "Value": kpi_dashboard.health_score.score},
            {"Metric": "Net Margin", "Value": profitability.net_margin},
            {"Metric": "Gross Margin", "Value": profitability.gross_margin},
            {"Metric": "Ending Cash", "Value": cashflow.ending_cash},
            {"Metric": "Runway Months", "Value": cashflow.runway_months},
            {"Metric": "Inventory Posture", "Value": cashflow.inventory_balance_label},
            {"Metric": "Inventory Risk", "Value": cashflow.inventory_risk_level},
            {
                "Metric": "Demand Trend",
                "Value": (
                    baseline.demand_forecast.trend_direction
                    if baseline.demand_forecast is not None
                    else "Manual"
                ),
            },
            {
                "Metric": "Growth Quality",
                "Value": (
                    channel_economics.growth_quality_label
                    if channel_economics is not None
                    else "N/A"
                ),
            },
            {"Metric": "Top Scenario", "Value": top_scenario.scenario_name},
            {"Metric": "Supplier Objective", "Value": OBJECTIVE_LABELS[supplier_objective]},
            {"Metric": "Recommended Supplier", "Value": supplier_context.get("supplier_selected_name")},
        ]
    )
    export_text = _build_export_text(
        headline=headline,
        narrative_summary=narrative_summary,
        key_metrics=key_metrics,
        top_risks=top_risks,
        top_opportunities=top_opportunities,
        recommended_actions=recommended_actions,
        scenario_takeaway=scenario_takeaway,
        sourcing_takeaway=sourcing_takeaway,
    )

    return ExecutiveSummaryData(
        headline=headline,
        narrative_summary=narrative_summary,
        key_metrics=key_metrics,
        top_risks=top_risks,
        top_opportunities=top_opportunities,
        recommended_actions=recommended_actions,
        scenario_takeaway=scenario_takeaway,
        sourcing_takeaway=sourcing_takeaway,
        top_supplier_objective=OBJECTIVE_LABELS[supplier_objective],
        top_supplier_name=str(supplier_context.get("supplier_selected_name")),
        top_scenario_name=top_scenario.scenario_name,
        recommendations=recommendations,
        recommendation_summary=recommendation_summary,
        export_metrics=export_metrics,
        export_text=export_text,
    )


def _build_supply_chain_analysis(
    baseline_source: str,
    price_per_unit: float,
    cashflow: object,
    monthly_demand_units: float,
    starting_cash: float,
    safety_stock_units: float,
) -> SupplyChainAnalysis:
    """Build supplier analysis from current live business context."""
    suppliers = load_sample_suppliers()
    business_context: SupplyChainBusinessContext = build_supply_chain_business_context(
        average_selling_price=price_per_unit,
        monthly_demand_units=monthly_demand_units,
        starting_cash=starting_cash,
        runway_months=getattr(cashflow, "runway_months", None),
        inventory_coverage_months=getattr(cashflow, "average_inventory_coverage_months", None),
        safety_stock_units=safety_stock_units,
    )
    _ = baseline_source
    return analyze_supplier_options(suppliers, business_context)


def _current_supplier_name(analysis: SupplyChainAnalysis) -> str:
    """Return the current supplier from the analysis set."""
    for supplier in analysis.suppliers:
        if supplier.option.is_current:
            return supplier.option.supplier_name
    return analysis.suppliers[0].option.supplier_name


def _select_supplier_objective(cashflow: object) -> str:
    """Choose the most relevant supplier objective from current posture."""
    runway = getattr(cashflow, "runway_months", None)
    stockout_months = getattr(cashflow, "stockout_month_count", 0) or 0
    coverage = getattr(cashflow, "average_inventory_coverage_months", None)
    if runway is not None and runway < 6:
        return "cash_pressure"
    if stockout_months > 0 or (coverage is not None and coverage < 1.5):
        return "stockout_pressure"
    return "best_value"


def _select_top_scenario(baseline: object) -> ScenarioAnalysis:
    """Select the most decision-relevant scenario using a simple downside score."""
    analyses = [
        run_scenario_analysis(baseline, scenario["key"], severity="moderate")
        for scenario in get_available_scenarios()
    ]
    return min(analyses, key=_scenario_risk_score)


def _scenario_risk_score(analysis: ScenarioAnalysis) -> float:
    """Rank scenarios by downside to runway, profit, and inventory stability."""
    runway = analysis.scenario_metrics.runway or 0.0
    net_profit = analysis.scenario_metrics.net_profit or 0.0
    lost_revenue = analysis.scenario_metrics.lost_revenue or 0.0
    inventory_stress = float(analysis.scenario_metrics.inventory_stress_score or 0)
    return (runway * 8.0) + net_profit - lost_revenue - (inventory_stress * 120.0)


def _build_headline(
    net_margin: float | None,
    runway_months: float | None,
    inventory_balance_label: str | None,
    growth_quality_label: str | None,
) -> str:
    """Build a deterministic one-line executive headline."""
    if net_margin is not None and net_margin < 0 and runway_months is not None and runway_months < 6:
        return "The business is losing money and operating with limited cash flexibility."
    if inventory_balance_label == "Excess":
        return "The business is operationally stable, but too much cash is sitting in inventory."
    if growth_quality_label == "Weak":
        return "Revenue quality is under pressure because growth is leaning too hard on weaker contribution channels."
    return "The business is broadly stable, but execution quality still depends on disciplined cash, inventory, and channel decisions."


def _build_narrative_summary(
    net_margin: float | None,
    runway_months: float | None,
    inventory_risk_level: str | None,
    inventory_balance_label: str | None,
    demand_trend: str | None,
    growth_quality_label: str | None,
    supplier_objective: str,
    supplier_name: object,
) -> str:
    """Generate a concise operator-facing narrative with deterministic rules."""
    parts: list[str] = []
    if net_margin is not None:
        if net_margin < 0:
            parts.append("The brand is currently unprofitable at the net level.")
        elif net_margin < 0.05:
            parts.append("The brand is profitable, but margin remains thin.")
        else:
            parts.append("The brand is currently generating positive operating profit.")
    if runway_months is not None:
        if runway_months < 3:
            parts.append("Cash runway is urgent.")
        elif runway_months < 6:
            parts.append("Cash runway is workable but still tight.")
        else:
            parts.append("Cash durability is reasonably healthy.")
    if inventory_risk_level == "High":
        parts.append("Inventory policy is exposing the business to stockout risk.")
    elif inventory_balance_label == "Excess":
        parts.append("Inventory posture is skewing excess and tying up working capital.")
    if demand_trend == "Falling":
        parts.append("Demand baseline is weakening.")
    elif demand_trend == "Rising":
        parts.append("Demand baseline is moving up.")
    if growth_quality_label == "Weak":
        parts.append("Growth quality is deteriorating because acquisition-heavy demand is compressing contribution.")
    elif growth_quality_label == "Strong":
        parts.append("Growth quality is supported by healthier channel mix.")
    parts.append(
        f"Given the current posture, supplier decisions should prioritize {OBJECTIVE_LABELS[supplier_objective].lower()} via {supplier_name}."
    )
    return " ".join(parts)


def _build_top_risks(
    net_margin: float | None,
    cashflow: object,
    demand_trend: str | None,
    growth_quality_label: str | None,
    top_scenario: ScenarioAnalysis,
) -> list[str]:
    """Build the highest-signal executive risk list."""
    risks: list[str] = []
    runway = getattr(cashflow, "runway_months", None)
    if net_margin is not None and net_margin < 0:
        risks.append("Negative net margin means additional volume may still deepen losses.")
    if runway is not None and runway < 6:
        risks.append(f"Runway is only {runway:.1f} months, limiting room for execution mistakes.")
    if getattr(cashflow, "inventory_risk_level", None) == "High":
        risks.append("Inventory stress is high enough to put future revenue at risk from stockouts.")
    if getattr(cashflow, "inventory_balance_label", None) == "Excess":
        risks.append("Excess inventory is trapping cash that could otherwise improve flexibility.")
    if demand_trend == "Falling":
        risks.append("Demand forecast is softening, which raises the risk of overbuying inventory.")
    if growth_quality_label == "Weak":
        risks.append("Channel mix quality is weakening as paid demand contributes less efficiently.")
    risks.append(
        f"{top_scenario.scenario_name} is currently the most important downside scenario to monitor."
    )
    return risks[:5]


def _build_top_opportunities(
    gross_margin: float | None,
    cashflow: object,
    growth_quality_label: str | None,
    supplier_context: dict[str, float | str | None],
) -> list[str]:
    """Build the highest-signal executive opportunity list."""
    opportunities: list[str] = []
    if gross_margin is not None and gross_margin >= 0.55:
        opportunities.append("Gross margin is healthy enough to support selective reinvestment.")
    if growth_quality_label == "Strong":
        opportunities.append("Channel mix is supporting healthier growth quality than a paid-heavy blend.")
    if getattr(cashflow, "inventory_balance_label", None) != "Excess":
        opportunities.append("Inventory posture is not materially overbuilt, leaving room for cleaner working-capital management.")
    supplier_name = supplier_context.get("supplier_selected_name")
    supplier_savings = supplier_context.get("supplier_landed_cost_savings_per_unit")
    if supplier_name is not None and supplier_savings is not None and float(supplier_savings) > 0.10:
        opportunities.append(
            f"{supplier_name} offers a credible sourcing lever to improve landed cost or flexibility."
        )
    if getattr(cashflow, "runway_months", None) is not None and getattr(cashflow, "runway_months") >= 6:
        opportunities.append("Runway is long enough to support more deliberate testing rather than reactive cuts.")
    return opportunities[:5]


def _build_scenario_takeaway(top_scenario: ScenarioAnalysis) -> str:
    """Summarize the top scenario insight in plain English."""
    return (
        f"{top_scenario.scenario_name} is the most important scenario to watch right now. "
        f"{top_scenario.summary_interpretation}"
    )


def _build_sourcing_takeaway(
    supplier_objective: str,
    supplier_context: dict[str, float | str | None],
    cashflow: object,
) -> str:
    """Summarize the top sourcing decision in plain English."""
    supplier_name = str(supplier_context.get("supplier_selected_name"))
    if supplier_objective == "cash_pressure":
        return (
            f"Cash is tight enough that sourcing should prioritize liquidity. {supplier_name} is the strongest fit because it reduces MOQ-related cash tie-up better than the alternatives."
        )
    if supplier_objective == "stockout_pressure":
        return (
            f"Inventory posture is tight enough that sourcing should prioritize service continuity. {supplier_name} is the best fit because it reduces lead-time and reliability risk."
        )
    if getattr(cashflow, "inventory_balance_label", None) == "Excess":
        return (
            f"Inventory is already heavy, so sourcing should stay disciplined. {supplier_name} is the best option when balancing landed cost against avoiding unnecessary working-capital strain."
        )
    return (
        f"Sourcing can prioritize balanced value right now. {supplier_name} offers the best overall landed-cost, lead-time, and reliability tradeoff for the current operating posture."
    )


def _build_export_text(
    headline: str,
    narrative_summary: str,
    key_metrics: list[ExecutiveKeyMetric],
    top_risks: list[str],
    top_opportunities: list[str],
    recommended_actions: list[str],
    scenario_takeaway: str,
    sourcing_takeaway: str,
) -> str:
    """Build a lightweight export-ready text report."""
    lines = [
        "CFO AI Executive Summary",
        "",
        f"Headline: {headline}",
        "",
        "Narrative",
        narrative_summary,
        "",
        "Key Metrics",
    ]
    lines.extend([f"- {metric.label}: {metric.value}" for metric in key_metrics])
    lines.extend(
        [
            "",
            "Top Risks",
            *[f"- {item}" for item in top_risks],
            "",
            "Top Opportunities",
            *[f"- {item}" for item in top_opportunities],
            "",
            "Recommended Actions",
            *[f"- {item}" for item in recommended_actions],
            "",
            "Scenario Takeaway",
            scenario_takeaway,
            "",
            "Sourcing Takeaway",
            sourcing_takeaway,
        ]
    )
    return "\n".join(lines)


def _format_months(value: float | None) -> str:
    """Format runway or coverage months safely."""
    if value is None:
        return "N/A"
    return f"{value:.1f} mo"
