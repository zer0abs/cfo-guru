"""Scenario simulator logic for the CFO AI Strategy Lab."""

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.cashflow import (
    CashFlowInputs,
    CashFlowResults,
    calculate_cash_flow_forecast,
    get_default_inputs as get_default_cashflow_inputs,
)
from modules.forecasting import (
    ChannelEconomicsSummary,
    DemandForecastResult,
    apply_channel_scenario_adjustments,
    build_channel_economics_context,
    build_forecast_context,
    calculate_channel_economics,
    resolve_demand_forecast,
)
from modules.health_score import HealthScoreResult, calculate_business_health_score
from modules.kpi import KPIDashboardData, build_kpi_dashboard_data
from modules.profitability import (
    ProfitabilityInputs,
    ProfitabilityResults,
    calculate_profitability,
    get_default_inputs as get_default_profitability_inputs,
)
from modules.recommendations import (
    build_cashflow_context,
    build_health_context,
    build_kpi_context,
    build_profitability_context,
    generate_recommendations,
)
from utils.formatting import format_currency, format_percent
from utils.state import (
    CASHFLOW_SECTION,
    PROFITABILITY_SECTION,
    get_current_business_inputs,
    merge_with_default_baseline,
)


SEVERITY_FACTORS = {
    "mild": 0.5,
    "moderate": 1.0,
    "severe": 1.5,
}


@dataclass(frozen=True)
class ScenarioDefinition:
    """Metadata and default adjustments for an available scenario."""

    key: str
    name: str
    description: str
    category: str
    base_adjustments: dict[str, float]


@dataclass(frozen=True)
class StrategyBaseline:
    """Baseline inputs needed for scenario analysis."""

    profitability_inputs: ProfitabilityInputs
    cashflow_inputs: CashFlowInputs
    demand_forecast: DemandForecastResult | None
    source: str


@dataclass(frozen=True)
class ScenarioMetrics:
    """Structured metrics bundle used for comparisons."""

    revenue: float | None
    gross_profit: float | None
    gross_margin: float | None
    net_profit: float | None
    net_margin: float | None
    ending_cash: float | None
    runway: float | None
    monthly_inventory_purchase_outflow: float | None
    monthly_fulfillment_outflow: float | None
    monthly_variable_outflow: float | None
    monthly_total_outflow: float | None
    inventory_coverage_months: float | None
    stockout_month_count: int | None
    lost_revenue: float | None
    average_fill_rate: float | None
    inventory_stress_score: int | None
    inventory_risk_level: str | None
    excess_inventory_value: float | None
    overstock_month_count: int | None
    inventory_overstock_score: int | None
    inventory_balance_label: str | None
    total_acquisition_cost: float | None
    weighted_margin_quality: float | None
    growth_quality_label: str | None
    revenue_growth: float | None
    ltv_cac_ratio: float | None
    inventory_turnover: float | None
    return_rate: float | None
    health_score: int | None


@dataclass(frozen=True)
class ScenarioAnalysis:
    """Full scenario analysis output for the Strategy Lab."""

    scenario_key: str
    scenario_name: str
    scenario_description: str
    severity: str
    adjusted_inputs: dict[str, float | str]
    baseline_metrics: ScenarioMetrics
    scenario_metrics: ScenarioMetrics
    deltas: dict[str, float | None]
    baseline_profitability: ProfitabilityResults
    scenario_profitability: ProfitabilityResults
    baseline_cashflow: CashFlowResults
    scenario_cashflow: CashFlowResults
    baseline_kpi: KPIDashboardData
    scenario_kpi: KPIDashboardData
    baseline_channel_economics: ChannelEconomicsSummary | None
    scenario_channel_economics: ChannelEconomicsSummary | None
    baseline_recommendations: list[dict]
    scenario_recommendations: list[dict]
    summary_interpretation: str


SCENARIO_DEFINITIONS = [
    ScenarioDefinition(
        key="ad_cost_shock",
        name="Ad Cost Shock",
        description="Paid acquisition becomes less efficient, raising marketing cost and weakening CAC performance.",
        category="growth",
        base_adjustments={
            "marketing_spend_pct": 0.18,
            "monthly_collections_pct": -0.04,
            "cac_pct": 0.22,
            "ltv_pct": -0.06,
            "revenue_growth_pct": -0.05,
        },
    ),
    ScenarioDefinition(
        key="demand_drop",
        name="Demand Drop",
        description="Order volume softens, reducing revenue and cash generation while leaving much of the cost base intact.",
        category="strategy",
        base_adjustments={
            "units_sold_pct": -0.18,
            "monthly_revenue_pct": -0.18,
            "monthly_collections_pct": -0.18,
            "inventory_turnover_pct": -0.16,
            "revenue_growth_pct": -0.14,
        },
    ),
    ScenarioDefinition(
        key="supplier_cost_increase",
        name="Supplier Cost Increase",
        description="Input costs rise, pushing up product costs and compressing gross margin.",
        category="profitability",
        base_adjustments={
            "product_cost_pct": 0.12,
            "monthly_collections_pct": -0.03,
            "ltv_pct": -0.03,
        },
    ),
    ScenarioDefinition(
        key="shipping_cost_increase",
        name="Shipping Cost Increase",
        description="Fulfillment and carrier expense rise, putting pressure on unit economics and margin quality.",
        category="operations",
        base_adjustments={
            "shipping_cost_pct": 0.12,
            "fulfillment_cost_pct": 0.05,
            "misc_expenses_pct": 0.12,
            "return_rate_pct": 0.04,
        },
    ),
    ScenarioDefinition(
        key="holiday_demand_spike",
        name="Holiday Demand Spike",
        description="Seasonal demand increases order volume and revenue, while adding some operational strain.",
        category="growth",
        base_adjustments={
            "units_sold_pct": 0.22,
            "monthly_revenue_pct": 0.20,
            "monthly_collections_pct": 0.18,
            "fulfillment_cost_pct": 0.08,
            "inventory_turnover_pct": 0.14,
            "return_rate_pct": 0.02,
            "revenue_growth_pct": 0.10,
        },
    ),
    ScenarioDefinition(
        key="discount_campaign",
        name="Discount Campaign",
        description="Promotional pricing lifts volume but reduces average selling price and margin.",
        category="strategy",
        base_adjustments={
            "price_pct": -0.12,
            "units_sold_pct": 0.14,
            "monthly_revenue_pct": 0.03,
            "monthly_collections_pct": 0.02,
            "gross_margin_pct": -0.06,
            "aov_pct": -0.12,
            "revenue_growth_pct": 0.04,
        },
    ),
]


def get_available_scenarios() -> list[dict[str, str]]:
    """Return the scenario catalog for UI selectors."""
    return [
        {
            "key": definition.key,
            "name": definition.name,
            "description": definition.description,
            "category": definition.category,
        }
        for definition in SCENARIO_DEFINITIONS
    ]


def get_default_strategy_baseline() -> StrategyBaseline:
    """Build the default e-commerce baseline used in Strategy Lab."""
    default_cashflow = get_default_cashflow_inputs()
    return StrategyBaseline(
        profitability_inputs=get_default_profitability_inputs(),
        cashflow_inputs=default_cashflow,
        demand_forecast=resolve_demand_forecast(
            default_cashflow.forecast_horizon_months,
            default_cashflow.monthly_units_sold,
        ),
        source="Default e-commerce demo",
    )


def get_strategy_baseline_from_state() -> StrategyBaseline:
    """Resolve Strategy Lab baseline from live app state with default fallback."""
    default_profitability = get_default_profitability_inputs()
    default_cashflow = get_default_cashflow_inputs()
    current_inputs = get_current_business_inputs()
    profitability_state = _normalize_profitability_state_for_scenarios(
        current_inputs.get(PROFITABILITY_SECTION, {})
    )

    profitability_values, using_live_profitability = merge_with_default_baseline(
        profitability_state,
        {
            "price_per_unit": default_profitability.price_per_unit,
            "units_sold": default_profitability.units_sold,
            "product_cost_per_unit": default_profitability.product_cost_per_unit,
            "shipping_cost_per_unit": default_profitability.shipping_cost_per_unit,
            "fulfillment_cost_per_unit": default_profitability.fulfillment_cost_per_unit,
            "packaging_cost_per_unit": default_profitability.packaging_cost_per_unit,
            "fixed_costs": default_profitability.fixed_costs,
            "operating_expenses": default_profitability.operating_expenses,
            "marketing_spend": default_profitability.marketing_spend,
        },
    )
    cashflow_values, using_live_cashflow = merge_with_default_baseline(
        current_inputs.get(CASHFLOW_SECTION, {}),
        {
            "starting_cash": default_cashflow.starting_cash,
            "forecast_horizon_months": default_cashflow.forecast_horizon_months,
            "monthly_revenue": default_cashflow.monthly_revenue,
            "monthly_collections": default_cashflow.monthly_collections,
            "payroll": default_cashflow.payroll,
            "rent": default_cashflow.rent,
            "loan_payments": default_cashflow.loan_payments,
            "operating_expenses": default_cashflow.operating_expenses,
            "miscellaneous_expenses": default_cashflow.miscellaneous_expenses,
            "marketing_spend": default_cashflow.marketing_spend,
            "monthly_units_sold": default_cashflow.monthly_units_sold,
            "product_cost_per_unit": default_cashflow.product_cost_per_unit,
            "shipping_cost_per_unit": default_cashflow.shipping_cost_per_unit,
            "fulfillment_cost_per_unit": default_cashflow.fulfillment_cost_per_unit,
            "packaging_cost_per_unit": default_cashflow.packaging_cost_per_unit,
            "beginning_inventory_units": default_cashflow.beginning_inventory_units,
            "reorder_point_units": default_cashflow.reorder_point_units,
            "target_inventory_units": default_cashflow.target_inventory_units,
            "supplier_lead_time_months": default_cashflow.supplier_lead_time_months,
            "reorder_quantity_units": default_cashflow.reorder_quantity_units,
            "safety_stock_units": default_cashflow.safety_stock_units,
            "seasonality_multiplier": default_cashflow.seasonality_multiplier,
        },
    )

    cashflow_inputs = CashFlowInputs(
        starting_cash=float(cashflow_values["starting_cash"]),
        forecast_horizon_months=int(cashflow_values["forecast_horizon_months"]),
        monthly_revenue=float(cashflow_values["monthly_revenue"]),
        monthly_collections=float(cashflow_values["monthly_collections"]),
        payroll=float(cashflow_values["payroll"]),
        rent=float(cashflow_values["rent"]),
        loan_payments=float(cashflow_values["loan_payments"]),
        operating_expenses=float(cashflow_values["operating_expenses"]),
        miscellaneous_expenses=float(cashflow_values["miscellaneous_expenses"]),
        marketing_spend=float(
            cashflow_values.get(
                "marketing_spend", profitability_values["marketing_spend"]
            )
        ),
        monthly_units_sold=float(
            cashflow_values.get("monthly_units_sold", profitability_values["units_sold"])
        ),
        product_cost_per_unit=float(
            cashflow_values.get(
                "product_cost_per_unit",
                profitability_values["product_cost_per_unit"],
            )
        ),
        shipping_cost_per_unit=float(
            cashflow_values.get(
                "shipping_cost_per_unit",
                profitability_values["shipping_cost_per_unit"],
            )
        ),
        fulfillment_cost_per_unit=float(
            cashflow_values.get(
                "fulfillment_cost_per_unit",
                profitability_values["fulfillment_cost_per_unit"],
            )
        ),
        packaging_cost_per_unit=float(
            cashflow_values.get(
                "packaging_cost_per_unit",
                profitability_values["packaging_cost_per_unit"],
            )
        ),
        beginning_inventory_units=float(cashflow_values["beginning_inventory_units"]),
        reorder_point_units=float(cashflow_values["reorder_point_units"]),
        target_inventory_units=float(cashflow_values["target_inventory_units"]),
        supplier_lead_time_months=int(cashflow_values["supplier_lead_time_months"]),
        reorder_quantity_units=float(cashflow_values["reorder_quantity_units"]),
        safety_stock_units=float(cashflow_values["safety_stock_units"]),
        seasonality_multiplier=float(cashflow_values["seasonality_multiplier"]),
    )
    demand_forecast = resolve_demand_forecast(
        cashflow_inputs.forecast_horizon_months,
        cashflow_inputs.monthly_units_sold,
    )

    return StrategyBaseline(
        profitability_inputs=ProfitabilityInputs(
            price_per_unit=float(profitability_values["price_per_unit"]),
            units_sold=float(profitability_values["units_sold"]),
            product_cost_per_unit=float(profitability_values["product_cost_per_unit"]),
            shipping_cost_per_unit=float(profitability_values["shipping_cost_per_unit"]),
            fulfillment_cost_per_unit=float(profitability_values["fulfillment_cost_per_unit"]),
            packaging_cost_per_unit=float(profitability_values["packaging_cost_per_unit"]),
            fixed_costs=float(profitability_values["fixed_costs"]),
            operating_expenses=float(profitability_values["operating_expenses"]),
            marketing_spend=float(profitability_values["marketing_spend"]),
        ),
        cashflow_inputs=cashflow_inputs,
        demand_forecast=demand_forecast,
        source=(
            "Live app inputs"
            if using_live_profitability or using_live_cashflow
            else "Default e-commerce demo"
        ),
    )


def render_strategy_lab_controls() -> tuple[str, str]:
    """Collect scenario selection controls from the sidebar."""
    scenario_options = get_available_scenarios()
    scenario_lookup = {option["name"]: option["key"] for option in scenario_options}

    with st.sidebar:
        st.subheader("Scenario Simulator")
        st.caption("Stress test the demo brand against common e-commerce operating shocks.")
        selected_name = st.selectbox(
            "Scenario",
            list(scenario_lookup.keys()),
            index=0,
        )
        severity = st.select_slider(
            "Severity",
            options=["mild", "moderate", "severe"],
            value="moderate",
        )

    return scenario_lookup[selected_name], severity


def run_scenario_analysis(
    baseline: StrategyBaseline,
    scenario_key: str,
    severity: str = "moderate",
) -> ScenarioAnalysis:
    """Apply a scenario, rerun metrics, and build a structured comparison."""
    scenario_definition = _get_scenario_definition(scenario_key)
    severity_factor = SEVERITY_FACTORS.get(severity, 1.0)
    baseline_demand_forecast = (
        baseline.demand_forecast
        if baseline.demand_forecast is not None and baseline.demand_forecast.use_forecast
        else None
    )
    baseline_demand_plan = (
        list(baseline_demand_forecast.forecast_units)
        if baseline_demand_forecast is not None
        else None
    )

    baseline_profitability = calculate_profitability(baseline.profitability_inputs)
    baseline_cashflow = calculate_cash_flow_forecast(
        baseline.cashflow_inputs,
        demand_plan_units=baseline_demand_plan,
        demand_forecast=baseline.demand_forecast,
    )
    baseline_average_selling_price = (
        baseline.cashflow_inputs.monthly_revenue
        / max(baseline.cashflow_inputs.monthly_units_sold, 1.0)
    )
    baseline_channel_economics = (
        calculate_channel_economics(
            baseline.demand_forecast,
            average_selling_price=baseline_average_selling_price,
            shared_variable_cost_per_unit=baseline.profitability_inputs.variable_cost_per_unit,
        )
        if baseline.demand_forecast is not None
        else None
    )
    baseline_kpi = build_kpi_dashboard_data(
        baseline.profitability_inputs,
        baseline_profitability,
    )

    adjusted_inputs = apply_scenario(
        baseline_inputs=baseline,
        scenario_key=scenario_key,
        severity=severity,
    )
    scenario_profitability = calculate_profitability(adjusted_inputs["profitability_inputs"])
    scenario_demand_forecast = (
        apply_channel_scenario_adjustments(
            baseline_demand_forecast,
            scenario_key,
            severity_factor,
        )
        if baseline_demand_forecast is not None
        else None
    )
    scenario_demand_plan = (
        list(scenario_demand_forecast.forecast_units)
        if scenario_demand_forecast is not None
        else None
    )
    scenario_cashflow = calculate_cash_flow_forecast(
        adjusted_inputs["cashflow_inputs"],
        demand_plan_units=scenario_demand_plan,
        demand_forecast=scenario_demand_forecast,
    )
    scenario_average_selling_price = (
        adjusted_inputs["cashflow_inputs"].monthly_revenue
        / max(adjusted_inputs["cashflow_inputs"].monthly_units_sold, 1.0)
    )
    scenario_channel_economics = (
        calculate_channel_economics(
            scenario_demand_forecast or baseline.demand_forecast,
            average_selling_price=scenario_average_selling_price,
            shared_variable_cost_per_unit=adjusted_inputs["profitability_inputs"].variable_cost_per_unit,
        )
        if (scenario_demand_forecast or baseline.demand_forecast) is not None
        else None
    )
    scenario_kpi = build_scenario_kpi_dashboard_data(
        adjusted_inputs["profitability_inputs"],
        scenario_profitability,
        baseline_kpi,
        scenario_definition,
        severity_factor,
    )

    baseline_recommendations = generate_recommendations(
        profitability_data=build_profitability_context(
            baseline.profitability_inputs, baseline_profitability
        ),
        cashflow_data=build_cashflow_context(
            baseline.cashflow_inputs, baseline_cashflow
        ),
        kpi_data=build_kpi_context(baseline_kpi),
        health_data=build_health_context(baseline_kpi.health_score),
        forecast_data=(
            build_forecast_context(baseline.demand_forecast)
            | (
                build_channel_economics_context(baseline_channel_economics)
                if baseline_channel_economics is not None
                else {}
            )
        ),
        categories={"profitability", "cash", "growth", "operations", "strategy"},
    )
    scenario_recommendations = generate_recommendations(
        profitability_data=build_profitability_context(
            adjusted_inputs["profitability_inputs"], scenario_profitability
        ),
        cashflow_data=build_cashflow_context(
            adjusted_inputs["cashflow_inputs"], scenario_cashflow
        ),
        kpi_data=build_kpi_context(scenario_kpi),
        health_data=build_health_context(scenario_kpi.health_score),
        forecast_data=(
            build_forecast_context(scenario_demand_forecast or baseline.demand_forecast)
            | (
                build_channel_economics_context(scenario_channel_economics)
                if scenario_channel_economics is not None
                else {}
            )
        ),
        categories={"profitability", "cash", "growth", "operations", "strategy"},
    )

    baseline_metrics = _build_scenario_metrics(
        baseline_profitability,
        baseline_cashflow,
        baseline_kpi,
        baseline_channel_economics,
    )
    scenario_metrics = _build_scenario_metrics(
        scenario_profitability,
        scenario_cashflow,
        scenario_kpi,
        scenario_channel_economics,
    )
    deltas = _build_metric_deltas(baseline_metrics, scenario_metrics)

    return ScenarioAnalysis(
        scenario_key=scenario_definition.key,
        scenario_name=scenario_definition.name,
        scenario_description=scenario_definition.description,
        severity=severity,
        adjusted_inputs=_serialize_adjusted_inputs(adjusted_inputs),
        baseline_metrics=baseline_metrics,
        scenario_metrics=scenario_metrics,
        deltas=deltas,
        baseline_profitability=baseline_profitability,
        scenario_profitability=scenario_profitability,
        baseline_cashflow=baseline_cashflow,
        scenario_cashflow=scenario_cashflow,
        baseline_kpi=baseline_kpi,
        scenario_kpi=scenario_kpi,
        baseline_channel_economics=baseline_channel_economics,
        scenario_channel_economics=scenario_channel_economics,
        baseline_recommendations=baseline_recommendations,
        scenario_recommendations=scenario_recommendations,
        summary_interpretation=_build_interpretation(
            scenario_definition.name,
            deltas,
            scenario_metrics,
        ),
    )


def apply_scenario(
    baseline_inputs: StrategyBaseline,
    scenario_key: str,
    severity: str,
) -> dict[str, ProfitabilityInputs | CashFlowInputs]:
    """Apply a scenario to the baseline inputs and return adjusted input objects."""
    scenario_definition = _get_scenario_definition(scenario_key)
    severity_factor = SEVERITY_FACTORS.get(severity, 1.0)
    adjustments = {
        adjustment_key: adjustment_value * severity_factor
        for adjustment_key, adjustment_value in scenario_definition.base_adjustments.items()
    }

    baseline_profitability = baseline_inputs.profitability_inputs
    baseline_cashflow = baseline_inputs.cashflow_inputs

    adjusted_price = _apply_pct(baseline_profitability.price_per_unit, adjustments.get("price_pct", 0.0))
    adjusted_units = _apply_pct(baseline_profitability.units_sold, adjustments.get("units_sold_pct", 0.0))
    adjusted_marketing = _apply_pct(
        baseline_profitability.marketing_spend,
        adjustments.get("marketing_spend_pct", 0.0),
    )

    profitability_inputs = ProfitabilityInputs(
        price_per_unit=adjusted_price,
        units_sold=adjusted_units,
        product_cost_per_unit=_apply_pct(
            baseline_profitability.product_cost_per_unit,
            adjustments.get("product_cost_pct", adjustments.get("variable_cost_pct", 0.0)),
        ),
        shipping_cost_per_unit=_apply_pct(
            baseline_profitability.shipping_cost_per_unit,
            adjustments.get("shipping_cost_pct", adjustments.get("variable_cost_pct", 0.0)),
        ),
        fulfillment_cost_per_unit=_apply_pct(
            baseline_profitability.fulfillment_cost_per_unit,
            adjustments.get("fulfillment_cost_pct", adjustments.get("variable_cost_pct", 0.0)),
        ),
        packaging_cost_per_unit=_apply_pct(
            baseline_profitability.packaging_cost_per_unit,
            adjustments.get("packaging_cost_pct", adjustments.get("variable_cost_pct", 0.0)),
        ),
        fixed_costs=baseline_profitability.fixed_costs,
        operating_expenses=baseline_profitability.operating_expenses,
        marketing_spend=adjusted_marketing,
    )

    cashflow_inputs = CashFlowInputs(
        starting_cash=baseline_cashflow.starting_cash,
        forecast_horizon_months=baseline_cashflow.forecast_horizon_months,
        monthly_revenue=_apply_pct(
            baseline_cashflow.monthly_revenue,
            adjustments.get("monthly_revenue_pct", adjustments.get("units_sold_pct", 0.0)),
        ),
        monthly_collections=_apply_pct(
            baseline_cashflow.monthly_collections,
            adjustments.get("monthly_collections_pct", adjustments.get("units_sold_pct", 0.0)),
        ),
        payroll=baseline_cashflow.payroll,
        rent=baseline_cashflow.rent,
        loan_payments=baseline_cashflow.loan_payments,
        operating_expenses=_apply_pct(
            baseline_cashflow.operating_expenses,
            adjustments.get("operating_expenses_pct", 0.0),
        ),
        miscellaneous_expenses=_apply_pct(
            baseline_cashflow.miscellaneous_expenses,
            adjustments.get("misc_expenses_pct", 0.0),
        ),
        marketing_spend=adjusted_marketing,
        monthly_units_sold=adjusted_units,
        product_cost_per_unit=profitability_inputs.product_cost_per_unit,
        shipping_cost_per_unit=profitability_inputs.shipping_cost_per_unit,
        fulfillment_cost_per_unit=profitability_inputs.fulfillment_cost_per_unit,
        packaging_cost_per_unit=profitability_inputs.packaging_cost_per_unit,
        beginning_inventory_units=baseline_cashflow.beginning_inventory_units,
        reorder_point_units=baseline_cashflow.reorder_point_units,
        target_inventory_units=_apply_pct(
            baseline_cashflow.target_inventory_units,
            adjustments.get("target_inventory_pct", 0.0),
        ),
        supplier_lead_time_months=max(
            0,
            int(
                round(
                    baseline_cashflow.supplier_lead_time_months
                    + adjustments.get("lead_time_months_delta", 0.0)
                )
            ),
        ),
        reorder_quantity_units=baseline_cashflow.reorder_quantity_units,
        safety_stock_units=baseline_cashflow.safety_stock_units,
        seasonality_multiplier=baseline_cashflow.seasonality_multiplier,
    )

    return {
        "profitability_inputs": profitability_inputs,
        "cashflow_inputs": cashflow_inputs,
    }



def build_scenario_kpi_dashboard_data(
    inputs: ProfitabilityInputs,
    results: ProfitabilityResults,
    baseline_kpi: KPIDashboardData,
    scenario_definition: ScenarioDefinition,
    severity_factor: float,
) -> KPIDashboardData:
    """Build scenario KPI data by adapting baseline KPI trends with scenario shocks."""
    trends = baseline_kpi.trends.copy()
    revenue_adjustment = scenario_definition.base_adjustments.get(
        "monthly_revenue_pct",
        scenario_definition.base_adjustments.get("units_sold_pct", 0.0),
    )
    revenue_multiplier = 1 + (revenue_adjustment * severity_factor)
    trends["revenue"] = trends["revenue"] * max(revenue_multiplier, 0.05)

    if results.gross_margin is not None:
        trends["gross_margin"] = _generate_margin_series(results.gross_margin)
    if results.net_margin is not None:
        trends["net_margin"] = _generate_margin_series(results.net_margin)

    trends["net_profit"] = trends["revenue"] * trends["net_margin"]
    trends["burn_rate"] = trends["net_profit"].apply(lambda value: max(0.0, -float(value)))
    trends["cash_reserve"] = _build_cash_reserve_series(
        baseline_start=float(baseline_kpi.trends["cash_reserve"].iloc[0]),
        ending_target=max(15000.0, float(baseline_kpi.trends["cash_reserve"].iloc[0]) + float(results.net_profit)),
        periods=len(trends),
    )
    trends["runway"] = [
        _calculate_runway_from_cash(cash_reserve, burn_rate)
        for cash_reserve, burn_rate in zip(trends["cash_reserve"], trends["burn_rate"])
    ]

    trends["cac"] = _apply_pct_series(
        trends["cac"],
        scenario_definition.base_adjustments.get("cac_pct", 0.0) * severity_factor,
    )
    trends["ltv"] = _apply_pct_series(
        trends["ltv"],
        scenario_definition.base_adjustments.get("ltv_pct", 0.0) * severity_factor,
    )
    trends["aov"] = _apply_pct_series(
        trends["aov"],
        scenario_definition.base_adjustments.get("aov_pct", scenario_definition.base_adjustments.get("price_pct", 0.0)) * severity_factor,
    )
    trends["return_rate"] = _apply_pct_series(
        trends["return_rate"],
        scenario_definition.base_adjustments.get("return_rate_pct", 0.0) * severity_factor,
        additive=True,
    ).clip(lower=0.0, upper=0.4)
    trends["inventory_turnover"] = _apply_pct_series(
        trends["inventory_turnover"],
        scenario_definition.base_adjustments.get("inventory_turnover_pct", 0.0) * severity_factor,
    ).clip(lower=0.5)
    trends["units_sold"] = _apply_pct_series(
        trends["units_sold"],
        scenario_definition.base_adjustments.get("units_sold_pct", 0.0) * severity_factor,
    ).clip(lower=1.0)
    trends["price_per_unit"] = [inputs.price_per_unit] * len(trends)

    current = trends.iloc[-1]
    previous = trends.iloc[-2]
    kpis = {
        "revenue": float(current["revenue"]),
        "revenue_growth": _safe_growth(float(current["revenue"]), float(previous["revenue"])),
        "gross_margin": results.gross_margin,
        "net_margin": results.net_margin,
        "burn_rate": max(0.0, -float(current["net_profit"])),
        "runway": _calculate_runway_from_cash(
            float(current["cash_reserve"]),
            max(0.0, -float(current["net_profit"])),
        ),
        "cac": float(current["cac"]),
        "ltv": float(current["ltv"]),
        "aov": float(current["aov"]),
        "return_rate": float(current["return_rate"]),
        "inventory_turnover": float(current["inventory_turnover"]),
    }

    health_score = calculate_business_health_score(kpis)
    return KPIDashboardData(kpis=kpis, trends=trends, health_score=health_score)


def create_scenario_comparison_chart(analysis: ScenarioAnalysis) -> go.Figure:
    """Create a grouped bar chart comparing baseline vs scenario metrics."""
    labels = ["Revenue", "Gross Profit", "Net Profit", "Ending Cash"]
    baseline_values = [
        analysis.baseline_metrics.revenue or 0.0,
        analysis.baseline_metrics.gross_profit or 0.0,
        analysis.baseline_metrics.net_profit or 0.0,
        analysis.baseline_metrics.ending_cash or 0.0,
    ]
    scenario_values = [
        analysis.scenario_metrics.revenue or 0.0,
        analysis.scenario_metrics.gross_profit or 0.0,
        analysis.scenario_metrics.net_profit or 0.0,
        analysis.scenario_metrics.ending_cash or 0.0,
    ]

    figure = go.Figure()
    figure.add_trace(go.Bar(name="Baseline", x=labels, y=baseline_values, marker_color="#94a3b8"))
    figure.add_trace(go.Bar(name=analysis.scenario_name, x=labels, y=scenario_values, marker_color="#1f77b4"))
    figure.update_layout(
        title="Baseline vs Scenario",
        barmode="group",
        yaxis_title="Amount ($)",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def create_scenario_cash_chart(analysis: ScenarioAnalysis) -> go.Figure:
    """Create a line chart comparing monthly ending cash paths."""
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=analysis.baseline_cashflow.forecast_table["Month"],
            y=analysis.baseline_cashflow.forecast_table["Ending Cash"],
            mode="lines+markers",
            name="Baseline",
            line=dict(color="#94a3b8", width=3),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=analysis.scenario_cashflow.forecast_table["Month"],
            y=analysis.scenario_cashflow.forecast_table["Ending Cash"],
            mode="lines+markers",
            name=analysis.scenario_name,
            line=dict(color="#1f77b4", width=3),
        )
    )
    figure.add_hline(y=0, line_dash="dash", line_color="#d62728")
    figure.update_layout(
        title="Cash Path Comparison",
        xaxis_title="Month",
        yaxis_title="Ending Cash ($)",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def render_scenario_overview(analysis: ScenarioAnalysis) -> None:
    """Render the key baseline vs scenario comparison cards."""
    columns = st.columns(6)
    comparison_rows = [
        (
            "Revenue",
            format_currency(analysis.scenario_metrics.revenue),
            _format_currency_delta(analysis.deltas.get("revenue_change")),
        ),
        (
            "Net Profit",
            format_currency(analysis.scenario_metrics.net_profit),
            _format_currency_delta(analysis.deltas.get("net_profit_change")),
        ),
        (
            "Ending Cash",
            format_currency(analysis.scenario_metrics.ending_cash),
            _format_currency_delta(analysis.deltas.get("ending_cash_change")),
        ),
        (
            "Runway",
            _format_months(analysis.scenario_metrics.runway),
            _format_month_delta(analysis.deltas.get("runway_change")),
        ),
        (
            "Growth Quality",
            analysis.scenario_metrics.growth_quality_label or "N/A",
            _format_point_delta(analysis.deltas.get("weighted_margin_quality_change")),
        ),
        (
            "Inventory Posture",
            analysis.scenario_metrics.inventory_balance_label or "N/A",
            _format_score_delta(analysis.deltas.get("inventory_balance_score_change")),
        ),
    ]

    for column, (label, value, delta) in zip(columns, comparison_rows):
        column.metric(label, value, delta=delta)


def render_scenario_delta_cards(analysis: ScenarioAnalysis) -> None:
    """Render compact cards showing the directional change for major metrics."""
    columns = st.columns(6)
    delta_rows = [
        ("Gross Margin", _format_point_delta(analysis.deltas.get("gross_margin_change"))),
        (
            "Margin Quality",
            _format_point_delta(analysis.deltas.get("weighted_margin_quality_change")),
        ),
        (
            "Inventory Buy",
            _format_currency_delta(
                analysis.deltas.get("monthly_inventory_purchase_outflow_change")
            ),
        ),
        (
            "Fulfillment Cash",
            _format_currency_delta(
                analysis.deltas.get("monthly_fulfillment_outflow_change")
            ),
        ),
        (
            "Lost Revenue",
            _format_currency_delta(analysis.deltas.get("lost_revenue_change")),
        ),
        (
            "Acquisition Cost",
            _format_currency_delta(analysis.deltas.get("total_acquisition_cost_change")),
        ),
        (
            "Overstock",
            _format_score_delta(analysis.deltas.get("inventory_overstock_score_change")),
        ),
    ]
    for column, (label, delta) in zip(columns, delta_rows):
        column.metric(label, delta or "N/A")


def render_scenario_comparison_table(analysis: ScenarioAnalysis) -> None:
    """Render a clean baseline vs scenario comparison table."""
    comparison_frame = pd.DataFrame(
        [
            {
                "Metric": "Revenue",
                "Baseline": format_currency(analysis.baseline_metrics.revenue),
                "Scenario": format_currency(analysis.scenario_metrics.revenue),
                "Delta": _format_currency_delta(analysis.deltas.get("revenue_change")),
            },
            {
                "Metric": "Gross Margin",
                "Baseline": format_percent(analysis.baseline_metrics.gross_margin),
                "Scenario": format_percent(analysis.scenario_metrics.gross_margin),
                "Delta": _format_point_delta(analysis.deltas.get("gross_margin_change")),
            },
            {
                "Metric": "Net Profit",
                "Baseline": format_currency(analysis.baseline_metrics.net_profit),
                "Scenario": format_currency(analysis.scenario_metrics.net_profit),
                "Delta": _format_currency_delta(analysis.deltas.get("net_profit_change")),
            },
            {
                "Metric": "Ending Cash",
                "Baseline": format_currency(analysis.baseline_metrics.ending_cash),
                "Scenario": format_currency(analysis.scenario_metrics.ending_cash),
                "Delta": _format_currency_delta(analysis.deltas.get("ending_cash_change")),
            },
            {
                "Metric": "Inventory Coverage",
                "Baseline": _format_months(analysis.baseline_metrics.inventory_coverage_months),
                "Scenario": _format_months(analysis.scenario_metrics.inventory_coverage_months),
                "Delta": _format_month_delta(
                    analysis.deltas.get("inventory_coverage_months_change")
                ),
            },
            {
                "Metric": "Stockout Months",
                "Baseline": _format_count(analysis.baseline_metrics.stockout_month_count),
                "Scenario": _format_count(analysis.scenario_metrics.stockout_month_count),
                "Delta": _format_count_delta(
                    analysis.deltas.get("stockout_month_count_change")
                ),
            },
            {
                "Metric": "Lost Revenue",
                "Baseline": format_currency(analysis.baseline_metrics.lost_revenue),
                "Scenario": format_currency(analysis.scenario_metrics.lost_revenue),
                "Delta": _format_currency_delta(analysis.deltas.get("lost_revenue_change")),
            },
            {
                "Metric": "Excess Inventory Value",
                "Baseline": format_currency(analysis.baseline_metrics.excess_inventory_value),
                "Scenario": format_currency(analysis.scenario_metrics.excess_inventory_value),
                "Delta": _format_currency_delta(
                    analysis.deltas.get("excess_inventory_value_change")
                ),
            },
            {
                "Metric": "Overstock Months",
                "Baseline": _format_count(analysis.baseline_metrics.overstock_month_count),
                "Scenario": _format_count(analysis.scenario_metrics.overstock_month_count),
                "Delta": _format_count_delta(
                    analysis.deltas.get("overstock_month_count_change")
                ),
            },
            {
                "Metric": "Inventory Purchase Outflow",
                "Baseline": format_currency(
                    analysis.baseline_metrics.monthly_inventory_purchase_outflow
                ),
                "Scenario": format_currency(
                    analysis.scenario_metrics.monthly_inventory_purchase_outflow
                ),
                "Delta": _format_currency_delta(
                    analysis.deltas.get("monthly_inventory_purchase_outflow_change")
                ),
            },
            {
                "Metric": "Fulfillment-at-Sale Outflow",
                "Baseline": format_currency(
                    analysis.baseline_metrics.monthly_fulfillment_outflow
                ),
                "Scenario": format_currency(
                    analysis.scenario_metrics.monthly_fulfillment_outflow
                ),
                "Delta": _format_currency_delta(
                    analysis.deltas.get("monthly_fulfillment_outflow_change")
                ),
            },
            {
                "Metric": "Monthly Variable Outflow",
                "Baseline": format_currency(analysis.baseline_metrics.monthly_variable_outflow),
                "Scenario": format_currency(analysis.scenario_metrics.monthly_variable_outflow),
                "Delta": _format_currency_delta(
                    analysis.deltas.get("monthly_variable_outflow_change")
                ),
            },
            {
                "Metric": "Monthly Total Outflow",
                "Baseline": format_currency(analysis.baseline_metrics.monthly_total_outflow),
                "Scenario": format_currency(analysis.scenario_metrics.monthly_total_outflow),
                "Delta": _format_currency_delta(
                    analysis.deltas.get("monthly_total_outflow_change")
                ),
            },
            {
                "Metric": "Runway",
                "Baseline": _format_months(analysis.baseline_metrics.runway),
                "Scenario": _format_months(analysis.scenario_metrics.runway),
                "Delta": _format_month_delta(analysis.deltas.get("runway_change")),
            },
            {
                "Metric": "Acquisition Cost Burden",
                "Baseline": format_currency(analysis.baseline_metrics.total_acquisition_cost),
                "Scenario": format_currency(analysis.scenario_metrics.total_acquisition_cost),
                "Delta": _format_currency_delta(
                    analysis.deltas.get("total_acquisition_cost_change")
                ),
            },
            {
                "Metric": "Weighted Margin Quality",
                "Baseline": format_percent(analysis.baseline_metrics.weighted_margin_quality),
                "Scenario": format_percent(analysis.scenario_metrics.weighted_margin_quality),
                "Delta": _format_point_delta(
                    analysis.deltas.get("weighted_margin_quality_change")
                ),
            },
            {
                "Metric": "Growth Quality Label",
                "Baseline": analysis.baseline_metrics.growth_quality_label or "N/A",
                "Scenario": analysis.scenario_metrics.growth_quality_label or "N/A",
                "Delta": (
                    "Changed"
                    if analysis.baseline_metrics.growth_quality_label
                    != analysis.scenario_metrics.growth_quality_label
                    else "No change"
                ),
            },
            {
                "Metric": "Health Score",
                "Baseline": _format_score(analysis.baseline_metrics.health_score),
                "Scenario": _format_score(analysis.scenario_metrics.health_score),
                "Delta": _format_score_delta(analysis.deltas.get("health_score_change")),
            },
            {
                "Metric": "Inventory Stress",
                "Baseline": _format_score(analysis.baseline_metrics.inventory_stress_score),
                "Scenario": _format_score(analysis.scenario_metrics.inventory_stress_score),
                "Delta": _format_score_delta(
                    analysis.deltas.get("inventory_stress_score_change")
                ),
            },
            {
                "Metric": "Inventory Overstock",
                "Baseline": _format_score(analysis.baseline_metrics.inventory_overstock_score),
                "Scenario": _format_score(analysis.scenario_metrics.inventory_overstock_score),
                "Delta": _format_score_delta(
                    analysis.deltas.get("inventory_overstock_score_change")
                ),
            },
        ]
    )
    st.dataframe(comparison_frame, use_container_width=True, hide_index=True)


def summarize_recommendation_changes(analysis: ScenarioAnalysis) -> dict[str, list[str]]:
    """Summarize which recommendations are new, cleared, or persistent."""
    baseline_ids = {recommendation["id"] for recommendation in analysis.baseline_recommendations}
    scenario_ids = {recommendation["id"] for recommendation in analysis.scenario_recommendations}

    new_titles = [
        recommendation["title"]
        for recommendation in analysis.scenario_recommendations
        if recommendation["id"] not in baseline_ids
    ]
    cleared_titles = [
        recommendation["title"]
        for recommendation in analysis.baseline_recommendations
        if recommendation["id"] not in scenario_ids
    ]
    persistent_titles = [
        recommendation["title"]
        for recommendation in analysis.scenario_recommendations
        if recommendation["id"] in baseline_ids
    ]

    return {
        "new": new_titles,
        "cleared": cleared_titles,
        "persistent": persistent_titles,
    }


def _get_scenario_definition(scenario_key: str) -> ScenarioDefinition:
    """Resolve a scenario definition by key."""
    for definition in SCENARIO_DEFINITIONS:
        if definition.key == scenario_key:
            return definition
    raise ValueError(f"Unknown scenario: {scenario_key}")


def _build_scenario_metrics(
    profitability_results: ProfitabilityResults,
    cashflow_results: CashFlowResults,
    kpi_dashboard: KPIDashboardData,
    channel_economics: ChannelEconomicsSummary | None = None,
) -> ScenarioMetrics:
    """Collect comparison metrics from existing module outputs."""
    ltv = kpi_dashboard.kpis.get("ltv")
    cac = kpi_dashboard.kpis.get("cac")
    ratio = (ltv / cac) if cac not in (None, 0) and ltv is not None else None
    return ScenarioMetrics(
        revenue=profitability_results.revenue,
        gross_profit=profitability_results.gross_profit,
        gross_margin=profitability_results.gross_margin,
        net_profit=profitability_results.net_profit,
        net_margin=profitability_results.net_margin,
        ending_cash=cashflow_results.ending_cash,
        runway=cashflow_results.runway_months,
        monthly_inventory_purchase_outflow=cashflow_results.monthly_inventory_purchase_outflow,
        monthly_fulfillment_outflow=cashflow_results.monthly_fulfillment_outflow,
        monthly_variable_outflow=cashflow_results.monthly_variable_cost_outflow,
        monthly_total_outflow=cashflow_results.monthly_total_outflow,
        inventory_coverage_months=cashflow_results.average_inventory_coverage_months,
        stockout_month_count=cashflow_results.stockout_month_count,
        lost_revenue=cashflow_results.lost_revenue,
        average_fill_rate=cashflow_results.average_fill_rate,
        inventory_stress_score=cashflow_results.inventory_stress_score,
        inventory_risk_level=cashflow_results.inventory_risk_level,
        excess_inventory_value=cashflow_results.excess_inventory_value,
        overstock_month_count=cashflow_results.overstock_month_count,
        inventory_overstock_score=cashflow_results.inventory_overstock_score,
        inventory_balance_label=cashflow_results.inventory_balance_label,
        total_acquisition_cost=(
            channel_economics.total_acquisition_cost
            if channel_economics is not None
            else None
        ),
        weighted_margin_quality=(
            channel_economics.weighted_margin_quality
            if channel_economics is not None
            else None
        ),
        growth_quality_label=(
            channel_economics.growth_quality_label
            if channel_economics is not None
            else None
        ),
        revenue_growth=kpi_dashboard.kpis.get("revenue_growth"),
        ltv_cac_ratio=ratio,
        inventory_turnover=kpi_dashboard.kpis.get("inventory_turnover"),
        return_rate=kpi_dashboard.kpis.get("return_rate"),
        health_score=kpi_dashboard.health_score.score,
    )


def _build_metric_deltas(
    baseline_metrics: ScenarioMetrics,
    scenario_metrics: ScenarioMetrics,
) -> dict[str, float | None]:
    """Build the metric delta dictionary for the comparison layer."""
    return {
        "revenue_change": _delta(scenario_metrics.revenue, baseline_metrics.revenue),
        "gross_profit_change": _delta(scenario_metrics.gross_profit, baseline_metrics.gross_profit),
        "gross_margin_change": _delta(scenario_metrics.gross_margin, baseline_metrics.gross_margin),
        "net_profit_change": _delta(scenario_metrics.net_profit, baseline_metrics.net_profit),
        "net_margin_change": _delta(scenario_metrics.net_margin, baseline_metrics.net_margin),
        "ending_cash_change": _delta(scenario_metrics.ending_cash, baseline_metrics.ending_cash),
        "inventory_coverage_months_change": _delta(
            scenario_metrics.inventory_coverage_months,
            baseline_metrics.inventory_coverage_months,
        ),
        "stockout_month_count_change": _delta(
            float(scenario_metrics.stockout_month_count)
            if scenario_metrics.stockout_month_count is not None
            else None,
            float(baseline_metrics.stockout_month_count)
            if baseline_metrics.stockout_month_count is not None
            else None,
        ),
        "lost_revenue_change": _delta(
            scenario_metrics.lost_revenue,
            baseline_metrics.lost_revenue,
        ),
        "excess_inventory_value_change": _delta(
            scenario_metrics.excess_inventory_value,
            baseline_metrics.excess_inventory_value,
        ),
        "overstock_month_count_change": _delta(
            float(scenario_metrics.overstock_month_count)
            if scenario_metrics.overstock_month_count is not None
            else None,
            float(baseline_metrics.overstock_month_count)
            if baseline_metrics.overstock_month_count is not None
            else None,
        ),
        "monthly_inventory_purchase_outflow_change": _delta(
            scenario_metrics.monthly_inventory_purchase_outflow,
            baseline_metrics.monthly_inventory_purchase_outflow,
        ),
        "monthly_fulfillment_outflow_change": _delta(
            scenario_metrics.monthly_fulfillment_outflow,
            baseline_metrics.monthly_fulfillment_outflow,
        ),
        "monthly_variable_outflow_change": _delta(
            scenario_metrics.monthly_variable_outflow,
            baseline_metrics.monthly_variable_outflow,
        ),
        "monthly_total_outflow_change": _delta(
            scenario_metrics.monthly_total_outflow,
            baseline_metrics.monthly_total_outflow,
        ),
        "runway_change": _delta(scenario_metrics.runway, baseline_metrics.runway),
        "total_acquisition_cost_change": _delta(
            scenario_metrics.total_acquisition_cost,
            baseline_metrics.total_acquisition_cost,
        ),
        "weighted_margin_quality_change": _delta(
            scenario_metrics.weighted_margin_quality,
            baseline_metrics.weighted_margin_quality,
        ),
        "ltv_cac_ratio_change": _delta(scenario_metrics.ltv_cac_ratio, baseline_metrics.ltv_cac_ratio),
        "health_score_change": _delta(
            float(scenario_metrics.health_score) if scenario_metrics.health_score is not None else None,
            float(baseline_metrics.health_score) if baseline_metrics.health_score is not None else None,
        ),
        "inventory_stress_score_change": _delta(
            float(scenario_metrics.inventory_stress_score)
            if scenario_metrics.inventory_stress_score is not None
            else None,
            float(baseline_metrics.inventory_stress_score)
            if baseline_metrics.inventory_stress_score is not None
            else None,
        ),
        "inventory_overstock_score_change": _delta(
            float(scenario_metrics.inventory_overstock_score)
            if scenario_metrics.inventory_overstock_score is not None
            else None,
            float(baseline_metrics.inventory_overstock_score)
            if baseline_metrics.inventory_overstock_score is not None
            else None,
        ),
        "inventory_balance_score_change": _delta(
            _inventory_balance_rank(scenario_metrics.inventory_balance_label),
            _inventory_balance_rank(baseline_metrics.inventory_balance_label),
        ),
    }


def _serialize_adjusted_inputs(
    adjusted_inputs: dict[str, ProfitabilityInputs | CashFlowInputs],
) -> dict[str, float | str]:
    """Serialize adjusted dataclass inputs into a small plain dict."""
    profitability_inputs = adjusted_inputs["profitability_inputs"]
    cashflow_inputs = adjusted_inputs["cashflow_inputs"]
    return {
        "price_per_unit": profitability_inputs.price_per_unit,
        "units_sold": profitability_inputs.units_sold,
        "product_cost_per_unit": profitability_inputs.product_cost_per_unit,
        "shipping_cost_per_unit": profitability_inputs.shipping_cost_per_unit,
        "fulfillment_cost_per_unit": profitability_inputs.fulfillment_cost_per_unit,
        "packaging_cost_per_unit": profitability_inputs.packaging_cost_per_unit,
        "total_variable_cost_per_unit": profitability_inputs.variable_cost_per_unit,
        "marketing_spend": profitability_inputs.marketing_spend,
        "monthly_revenue": cashflow_inputs.monthly_revenue,
        "monthly_collections": cashflow_inputs.monthly_collections,
        "monthly_units_sold": cashflow_inputs.monthly_units_sold,
        "beginning_inventory_units": cashflow_inputs.beginning_inventory_units,
        "reorder_point_units": cashflow_inputs.reorder_point_units,
        "target_inventory_units": cashflow_inputs.target_inventory_units,
        "supplier_lead_time_months": cashflow_inputs.supplier_lead_time_months,
        "reorder_quantity_units": cashflow_inputs.reorder_quantity_units,
        "safety_stock_units": cashflow_inputs.safety_stock_units,
        "monthly_total_variable_outflow": (
            cashflow_inputs.monthly_units_sold * cashflow_inputs.total_variable_cost_per_unit
        ),
        "miscellaneous_expenses": cashflow_inputs.miscellaneous_expenses,
    }


def _build_interpretation(
    scenario_name: str,
    deltas: dict[str, float | None],
    scenario_metrics: ScenarioMetrics,
) -> str:
    """Build a concise deterministic scenario summary."""
    net_margin_change = deltas.get("net_margin_change")
    runway_change = deltas.get("runway_change")
    revenue_change = deltas.get("revenue_change")
    inventory_purchase_change = deltas.get("monthly_inventory_purchase_outflow_change")
    lost_revenue_change = deltas.get("lost_revenue_change")
    inventory_stress_change = deltas.get("inventory_stress_score_change")
    overstock_change = deltas.get("inventory_overstock_score_change")
    excess_inventory_value_change = deltas.get("excess_inventory_value_change")
    variable_outflow_change = deltas.get("monthly_variable_outflow_change")
    margin_quality_change = deltas.get("weighted_margin_quality_change")
    acquisition_burden_change = deltas.get("total_acquisition_cost_change")

    if _is_negative(net_margin_change) and _is_negative(runway_change):
        return (
            f"{scenario_name} reduces net margin and shortens runway, suggesting a need to preserve cash and review pricing, acquisition, or cost structure."
        )
    if _is_negative(margin_quality_change) and _is_positive(acquisition_burden_change):
        return (
            f"{scenario_name} shifts demand toward lower-quality growth by increasing acquisition burden faster than contribution, so paid efficiency and channel mix should be reviewed before scaling."
        )
    if _is_positive(inventory_purchase_change) and _is_negative(runway_change):
        return (
            f"{scenario_name} triggers heavier inventory-buy cash requirements before the related sales are fully realized, which tightens liquidity and working-capital flexibility."
        )
    if _is_positive(lost_revenue_change) and _is_positive(inventory_stress_change):
        return (
            f"{scenario_name} increases inventory stress and leaves more revenue at risk from stockouts, so inventory policy should be tightened before demand is scaled."
        )
    if _is_positive(overstock_change) and _is_positive(excess_inventory_value_change):
        return (
            f"{scenario_name} reduces immediate stockout pressure but leaves more cash trapped in inventory, so reorder policy should be tightened before more stock is committed."
        )
    if _is_positive(variable_outflow_change) and _is_negative(runway_change):
        return (
            f"{scenario_name} increases order-driven cash outflows and shortens runway, so pricing, sourcing, or fulfillment efficiency should be reviewed before scaling."
        )
    if _is_positive(revenue_change) and _is_negative(net_margin_change):
        return (
            f"{scenario_name} lifts revenue, but the added volume does not fully protect profitability, so the tradeoff should be evaluated carefully."
        )
    if _is_positive(revenue_change) and _is_positive(runway_change):
        return (
            f"{scenario_name} improves revenue and liquidity, but the business should still monitor operational strain and margin quality."
        )
    if scenario_metrics.runway is not None and scenario_metrics.runway < 3:
        return (
            f"{scenario_name} puts cash durability under pressure and may require immediate action on spend, pricing, or working capital."
        )
    return (
        f"{scenario_name} changes the operating profile meaningfully, so leadership should compare margin, cash, and efficiency tradeoffs before acting."
    )


def _generate_margin_series(target_margin: float) -> pd.Series:
    """Create a short trend series ending at the provided margin."""
    return pd.Series(
        [
            max(-1.0, target_margin - 0.05),
            max(-1.0, target_margin - 0.03),
            max(-1.0, target_margin - 0.02),
            max(-1.0, target_margin - 0.01),
            max(-1.0, target_margin - 0.005),
            target_margin,
        ]
    )


def _build_cash_reserve_series(
    baseline_start: float,
    ending_target: float,
    periods: int,
) -> pd.Series:
    """Build a simple linear cash reserve series for scenario KPI trends."""
    return pd.Series(
        [
            baseline_start + ((ending_target - baseline_start) * index / max(periods - 1, 1))
            for index in range(periods)
        ]
    )


def _apply_pct(value: float, pct_change: float) -> float:
    """Apply a percentage change with a floor at zero."""
    return max(0.0, value * (1 + pct_change))


def _apply_pct_series(
    series: pd.Series,
    pct_change: float,
    additive: bool = False,
) -> pd.Series:
    """Apply a scenario change across a KPI trend series."""
    if additive:
        return series + pct_change
    return series * (1 + pct_change)


def _safe_growth(current_value: float, previous_value: float) -> float | None:
    """Calculate growth safely for scenario KPI output."""
    if previous_value == 0:
        return None
    return (current_value - previous_value) / previous_value


def _calculate_runway_from_cash(cash_reserve: float, burn_rate: float) -> float | None:
    """Convert current cash and burn into runway months."""
    if burn_rate <= 0:
        return None
    return cash_reserve / burn_rate


def _delta(current_value: float | None, baseline_value: float | None) -> float | None:
    """Return the change between a scenario metric and a baseline metric."""
    if current_value is None or baseline_value is None:
        return None
    return current_value - baseline_value


def _format_currency_delta(value: float | None) -> str | None:
    """Format currency deltas."""
    if value is None:
        return None
    sign = "+" if value >= 0 else "-"
    return f"{sign}{format_currency(abs(value))}"


def _format_point_delta(value: float | None) -> str | None:
    """Format margin changes in percentage points."""
    if value is None:
        return None
    return f"{value * 100:+.1f} pts"


def _format_month_delta(value: float | None) -> str | None:
    """Format runway delta."""
    if value is None:
        return None
    return f"{value:+.1f} mo"


def _format_ratio_delta(value: float | None) -> str | None:
    """Format LTV:CAC ratio delta."""
    if value is None:
        return None
    return f"{value:+.1f}x"


def _format_score_delta(value: float | None) -> str | None:
    """Format health score delta."""
    if value is None:
        return None
    return f"{value:+.0f}"


def _format_months(value: float | None) -> str:
    """Format runway values."""
    if value is None:
        return "Stable / N/A"
    return f"{value:.1f} mo"


def _format_score(value: int | None) -> str:
    """Format health score."""
    if value is None:
        return "N/A"
    return f"{value}/100"


def _format_count(value: int | None) -> str:
    """Format count values for comparison tables."""
    if value is None:
        return "N/A"
    return f"{value}"


def _format_count_delta(value: float | None) -> str | None:
    """Format count deltas."""
    if value is None:
        return None
    return f"{value:+.0f}"


def _inventory_balance_rank(label: str | None) -> float | None:
    """Map inventory posture labels into an ordinal scale for deltas."""
    mapping = {"Tight": -1.0, "Balanced": 0.0, "Excess": 1.0}
    if label is None:
        return None
    return mapping.get(label)


def _is_negative(value: float | None) -> bool:
    """Return true when the value exists and is negative."""
    return value is not None and value < 0


def _is_positive(value: float | None) -> bool:
    """Return true when the value exists and is positive."""
    return value is not None and value > 0


def _normalize_profitability_state_for_scenarios(
    state_values: dict[str, float | int],
) -> dict[str, float | int]:
    """Map any legacy blended variable-cost state into component costs."""
    normalized_values = dict(state_values)
    if (
        "variable_cost_per_unit" in normalized_values
        and "product_cost_per_unit" not in normalized_values
    ):
        legacy_value = float(normalized_values["variable_cost_per_unit"])
        normalized_values["product_cost_per_unit"] = round(legacy_value * 0.70, 2)
        normalized_values["shipping_cost_per_unit"] = round(legacy_value * 0.15, 2)
        normalized_values["fulfillment_cost_per_unit"] = round(legacy_value * 0.10, 2)
        normalized_values["packaging_cost_per_unit"] = round(legacy_value * 0.05, 2)
    return normalized_values
