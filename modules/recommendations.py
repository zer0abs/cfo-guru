"""Rule-based recommendation engine for CFO AI."""

from collections import Counter
from typing import TypedDict

from utils.formatting import format_currency, format_percent


class Recommendation(TypedDict):
    """Structured recommendation object returned by the engine."""

    id: str
    title: str
    category: str
    issue: str
    action: str
    rationale: str
    priority: str
    estimated_impact: str
    metric_reference: str
    evidence: str
    status: str


# Thresholds are grouped here so future scenario testing can tune them easily.
# The values below are meant to be practical defaults for a growing e-commerce brand,
# not hidden model outputs. Every recommendation below maps directly to one or more
# thresholds defined here.
WEAK_NET_MARGIN_THRESHOLD = 0.05
STRONG_NET_MARGIN_THRESHOLD = 0.12
LOW_RUNWAY_URGENT_MONTHS = 3.0
LOW_RUNWAY_WATCH_MONTHS = 6.0
STRONG_RUNWAY_MONTHS = 9.0
WEAK_LTV_CAC_THRESHOLD = 3.0
CRITICAL_LTV_CAC_THRESHOLD = 2.0
STRONG_LTV_CAC_THRESHOLD = 3.5
WEAK_INVENTORY_TURNOVER_THRESHOLD = 3.0
STRONG_INVENTORY_TURNOVER_THRESHOLD = 5.0
HIGH_FIXED_COST_BURDEN_THRESHOLD = 0.30
CRITICAL_FIXED_COST_BURDEN_THRESHOLD = 0.40
HIGH_RETURN_RATE_THRESHOLD = 0.10
WATCH_RETURN_RATE_THRESHOLD = 0.06
HIGH_VARIABLE_COST_RATIO_THRESHOLD = 0.55
CRITICAL_VARIABLE_COST_RATIO_THRESHOLD = 0.65
STRONG_GROSS_MARGIN_THRESHOLD = 0.55
STRONG_HEALTH_SCORE_THRESHOLD = 80
AT_RISK_HEALTH_SCORE_THRESHOLD = 60
HIGH_INVENTORY_STRESS_THRESHOLD = 70
MODERATE_INVENTORY_STRESS_THRESHOLD = 40
HIGH_OVERSTOCK_SCORE_THRESHOLD = 70
MODERATE_OVERSTOCK_SCORE_THRESHOLD = 40
HIGH_LOST_REVENUE_RATIO_THRESHOLD = 0.08
LOW_COVERAGE_MONTHS_THRESHOLD = 1.0
HIGH_EXCESS_INVENTORY_VALUE_RATIO_THRESHOLD = 0.20
MEANINGFUL_LANDED_COST_SAVINGS_THRESHOLD = 0.30
HIGH_SUPPLIER_CASH_TIE_UP_RATIO_THRESHOLD = 0.25
HIGH_SUPPLIER_STOCKOUT_PRESSURE_THRESHOLD = 50
LOW_SUPPLIER_RELIABILITY_THRESHOLD = 0.85

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}
STATUS_ORDER = {"urgent": 0, "watch": 1, "healthy": 2}
DEFAULT_CONTEXT_KEYS = {
    "revenue": None,
    "price_per_unit": None,
    "gross_margin": None,
    "net_margin": None,
    "net_profit": None,
    "total_variable_cost": None,
    "fixed_costs": None,
    "operating_expenses": None,
    "marketing_spend": None,
    "product_cost_per_unit": None,
    "shipping_cost_per_unit": None,
    "fulfillment_cost_per_unit": None,
    "packaging_cost_per_unit": None,
    "break_even_units": None,
    "break_even_revenue": None,
    "variable_cost_ratio": None,
    "fixed_cost_ratio": None,
    "starting_cash": None,
    "forecast_horizon_months": None,
    "monthly_revenue": None,
    "monthly_collections": None,
    "ending_cash": None,
    "runway_months": None,
    "first_negative_month": None,
    "monthly_variable_cost_outflow": None,
    "monthly_inventory_purchase_outflow": None,
    "monthly_fulfillment_outflow": None,
    "monthly_fixed_cost_outflow": None,
    "monthly_total_outflow": None,
    "inventory_coverage_months": None,
    "stockout_month_count": None,
    "low_coverage_month_count": None,
    "lost_sales_units": None,
    "lost_revenue": None,
    "average_fill_rate": None,
    "inventory_stress_score": None,
    "inventory_risk_level": None,
    "excess_coverage_months": None,
    "excess_coverage_flag": None,
    "overstock_flag": None,
    "overstock_month_count": None,
    "excess_inventory_units": None,
    "excess_inventory_value": None,
    "cash_tied_in_excess_inventory": None,
    "average_excess_coverage_months": None,
    "inventory_overstock_score": None,
    "inventory_balance_label": None,
    "demand_source": None,
    "forecast_method": None,
    "forecast_trend_direction": None,
    "forecast_average_units": None,
    "forecast_uncertainty_proxy": None,
    "forecast_paid_share": None,
    "forecast_retention_share": None,
    "forecast_paid_trend": None,
    "forecast_retention_trend": None,
    "forecast_paid_acquisition_cost_per_unit": None,
    "channel_total_acquisition_cost": None,
    "channel_weighted_margin_quality": None,
    "channel_growth_quality_label": None,
    "channel_paid_margin_quality": None,
    "channel_retention_margin_quality": None,
    "channel_paid_acquisition_cost": None,
    "channel_retention_contribution": None,
    "supplier_current_name": None,
    "supplier_current_landed_cost_per_unit": None,
    "supplier_current_lead_time_months": None,
    "supplier_current_reliability_score": None,
    "supplier_current_moq": None,
    "supplier_current_order_cost_at_moq": None,
    "supplier_best_value_name": None,
    "supplier_best_value_landed_cost_per_unit": None,
    "supplier_best_value_score": None,
    "supplier_best_cash_name": None,
    "supplier_best_cash_order_cost_at_moq": None,
    "supplier_best_cash_tie_up_ratio": None,
    "supplier_best_stockout_name": None,
    "supplier_best_stockout_lead_time_months": None,
    "supplier_best_stockout_reliability_score": None,
    "supplier_selected_objective": None,
    "supplier_selected_name": None,
    "supplier_selected_landed_cost_per_unit": None,
    "supplier_selected_lead_time_months": None,
    "supplier_selected_reliability_score": None,
    "supplier_selected_order_cost_at_moq": None,
    "supplier_selected_cash_tie_up_ratio": None,
    "supplier_selected_stockout_pressure_score": None,
    "supplier_landed_cost_savings_per_unit": None,
    "supplier_lead_time_improvement_months": None,
    "supplier_cash_tie_up_savings": None,
    "revenue_growth": None,
    "burn_rate": None,
    "cac": None,
    "ltv": None,
    "ltv_cac_ratio": None,
    "aov": None,
    "return_rate": None,
    "inventory_turnover": None,
    "health_score": None,
    "health_interpretation": None,
}
MAX_HEALTHY_RECOMMENDATIONS = 2


def build_profitability_context(inputs: object, results: object) -> dict[str, float | None]:
    """Build a plain dict from profitability inputs and results objects."""
    revenue = _as_float(_get_attr(results, "revenue"))
    total_variable_cost = _as_float(_get_attr(results, "total_variable_cost"))
    fixed_costs = _as_float(_get_attr(inputs, "fixed_costs"))
    operating_expenses = _as_float(_get_attr(inputs, "operating_expenses"))
    marketing_spend = _as_float(_get_attr(inputs, "marketing_spend"))
    price_per_unit = _as_float(_get_attr(inputs, "price_per_unit"))
    product_cost_per_unit = _as_float(_get_attr(inputs, "product_cost_per_unit"))
    shipping_cost_per_unit = _as_float(_get_attr(inputs, "shipping_cost_per_unit"))
    fulfillment_cost_per_unit = _as_float(_get_attr(inputs, "fulfillment_cost_per_unit"))
    packaging_cost_per_unit = _as_float(_get_attr(inputs, "packaging_cost_per_unit"))

    variable_cost_ratio = (
        total_variable_cost / revenue
        if revenue not in (None, 0) and total_variable_cost is not None
        else None
    )
    fixed_cost_burden = (
        (fixed_costs + operating_expenses) / revenue
        if revenue not in (None, 0)
        and fixed_costs is not None
        and operating_expenses is not None
        else None
    )

    context = {
        "revenue": revenue,
        "price_per_unit": price_per_unit,
        "gross_margin": _as_float(_get_attr(results, "gross_margin")),
        "net_margin": _as_float(_get_attr(results, "net_margin")),
        "net_profit": _as_float(_get_attr(results, "net_profit")),
        "total_variable_cost": total_variable_cost,
        "fixed_costs": fixed_costs,
        "operating_expenses": operating_expenses,
        "marketing_spend": marketing_spend,
        "product_cost_per_unit": product_cost_per_unit,
        "shipping_cost_per_unit": shipping_cost_per_unit,
        "fulfillment_cost_per_unit": fulfillment_cost_per_unit,
        "packaging_cost_per_unit": packaging_cost_per_unit,
        "break_even_units": _as_float(_get_attr(results, "break_even_units")),
        "break_even_revenue": _as_float(_get_attr(results, "break_even_revenue")),
        "variable_cost_ratio": variable_cost_ratio,
        "fixed_cost_ratio": fixed_cost_burden,
    }
    return _with_default_context(context)


def build_cashflow_context(inputs: object, results: object) -> dict[str, float | str | None]:
    """Build a plain dict from cash flow inputs and results objects."""
    context = {
        "starting_cash": _as_float(_get_attr(inputs, "starting_cash")),
        "forecast_horizon_months": _as_float(_get_attr(inputs, "forecast_horizon_months")),
        "monthly_revenue": _as_float(_get_attr(inputs, "monthly_revenue")),
        "monthly_collections": _as_float(_get_attr(inputs, "monthly_collections")),
        "ending_cash": _as_float(_get_attr(results, "ending_cash")),
        "runway_months": _as_float(_get_attr(results, "runway_months")),
        "first_negative_month": _get_attr(results, "first_negative_month"),
        "monthly_variable_cost_outflow": _as_float(
            _get_attr(results, "monthly_variable_cost_outflow")
        ),
        "monthly_inventory_purchase_outflow": _as_float(
            _get_attr(results, "monthly_inventory_purchase_outflow")
        ),
        "monthly_fulfillment_outflow": _as_float(
            _get_attr(results, "monthly_fulfillment_outflow")
        ),
        "monthly_fixed_cost_outflow": _as_float(
            _get_attr(results, "monthly_fixed_cost_outflow")
        ),
        "monthly_total_outflow": _as_float(
            _get_attr(results, "monthly_total_outflow")
        ),
        "inventory_coverage_months": _as_float(
            _get_attr(results, "average_inventory_coverage_months")
        ),
        "stockout_month_count": _as_float(_get_attr(results, "stockout_month_count")),
        "low_coverage_month_count": _as_float(
            _get_attr(results, "low_coverage_month_count")
        ),
        "lost_sales_units": _as_float(_get_attr(results, "lost_sales_units")),
        "lost_revenue": _as_float(_get_attr(results, "lost_revenue")),
        "average_fill_rate": _as_float(_get_attr(results, "average_fill_rate")),
        "inventory_stress_score": _as_float(
            _get_attr(results, "inventory_stress_score")
        ),
        "inventory_risk_level": _get_attr(results, "inventory_risk_level"),
        "excess_coverage_months": _as_float(_get_attr(results, "excess_coverage_months")),
        "excess_coverage_flag": _get_attr(results, "excess_coverage_flag"),
        "overstock_flag": _get_attr(results, "overstock_flag"),
        "overstock_month_count": _as_float(_get_attr(results, "overstock_month_count")),
        "excess_inventory_units": _as_float(_get_attr(results, "excess_inventory_units")),
        "excess_inventory_value": _as_float(_get_attr(results, "excess_inventory_value")),
        "cash_tied_in_excess_inventory": _as_float(
            _get_attr(results, "cash_tied_in_excess_inventory")
        ),
        "average_excess_coverage_months": _as_float(
            _get_attr(results, "average_excess_coverage_months")
        ),
        "inventory_overstock_score": _as_float(
            _get_attr(results, "inventory_overstock_score")
        ),
        "inventory_balance_label": _get_attr(results, "inventory_balance_label"),
        "demand_source": _get_attr(results, "demand_source"),
        "forecast_method": _get_attr(results, "forecast_method"),
        "forecast_trend_direction": _get_attr(results, "forecast_trend_direction"),
        "forecast_average_units": _as_float(
            _get_attr(results, "effective_units_sold")
        ),
    }
    return _with_default_context(context)


def build_kpi_context(dashboard: object) -> dict[str, float | int | None]:
    """Build a plain KPI dict from the KPI dashboard object."""
    kpis = _get_attr(dashboard, "kpis") or {}
    health_score = _get_attr(_get_attr(dashboard, "health_score"), "score")

    cac = _as_float(kpis.get("cac"))
    ltv = _as_float(kpis.get("ltv"))
    context = {
        "revenue": _as_float(kpis.get("revenue")),
        "revenue_growth": _as_float(kpis.get("revenue_growth")),
        "gross_margin": _as_float(kpis.get("gross_margin")),
        "net_margin": _as_float(kpis.get("net_margin")),
        "burn_rate": _as_float(kpis.get("burn_rate")),
        "runway_months": _as_float(kpis.get("runway")),
        "cac": cac,
        "ltv": ltv,
        "ltv_cac_ratio": (ltv / cac) if cac not in (None, 0) and ltv is not None else None,
        "aov": _as_float(kpis.get("aov")),
        "return_rate": _as_float(kpis.get("return_rate")),
        "inventory_turnover": _as_float(kpis.get("inventory_turnover")),
        "health_score": _as_float(health_score),
    }
    return _with_default_context(context)


def build_health_context(health_result: object) -> dict[str, float | str | None]:
    """Build a plain dict from the health score result."""
    context = {
        "score": _as_float(_get_attr(health_result, "score")),
        "health_score": _as_float(_get_attr(health_result, "score")),
        "health_interpretation": _get_attr(health_result, "interpretation"),
    }
    return _with_default_context(context)


def build_forecast_context(
    forecast_result: object | None,
) -> dict[str, float | str | bool | None]:
    """Build a plain dict from the forecasting result."""
    if forecast_result is None:
        return _with_default_context({})
    context = {
        "forecast_method": _get_attr(forecast_result, "method"),
        "forecast_trend_direction": _get_attr(forecast_result, "trend_direction"),
        "forecast_average_units": _as_float(
            _get_attr(forecast_result, "average_forecast_units")
        ),
        "forecast_uncertainty_proxy": _as_float(
            _get_attr(forecast_result, "uncertainty_proxy")
        ),
        "demand_source": _get_attr(forecast_result, "source_label"),
    }
    return _with_default_context(context)


def generate_recommendations(
    profitability_data: dict[str, float | None] | None = None,
    cashflow_data: dict[str, float | str | None] | None = None,
    kpi_data: dict[str, float | int | None] | None = None,
    health_data: dict[str, float | str | None] | None = None,
    forecast_data: dict[str, float | str | bool | None] | None = None,
    supply_chain_data: dict[str, float | str | None] | None = None,
    categories: set[str] | None = None,
) -> list[Recommendation]:
    """Generate explainable recommendations from current app metrics."""
    recommendations: list[Recommendation] = []
    profitability_data = _with_default_context(profitability_data or {})
    cashflow_data = _with_default_context(cashflow_data or {})
    kpi_data = _with_default_context(kpi_data or {})
    health_data = _with_default_context(health_data or {})
    forecast_data = _with_default_context(forecast_data or {})
    supply_chain_data = _with_default_context(supply_chain_data or {})

    net_margin = _first_numeric(kpi_data.get("net_margin"), profitability_data.get("net_margin"))
    if net_margin is not None:
        if net_margin < 0:
            recommendations.append(
                _make_recommendation(
                    rec_id="profit-negative-margin",
                    title="Repair negative net margin before pushing growth",
                    category="profitability",
                    issue=(
                        f"Net margin is negative at {format_percent(net_margin)}, which means current sales volume is not translating into earnings."
                    ),
                    action=(
                        "Review pricing, tighten discounting, and reduce product, shipping, or fulfillment leakage before increasing paid acquisition."
                    ),
                    rationale=(
                        "When contribution after fulfillment and overhead is negative, scaling orders can deepen losses instead of creating operating leverage."
                    ),
                    priority="High",
                    estimated_impact=(
                        "Improving margin by 3 to 5 percentage points could materially strengthen profitability."
                    ),
                    metric_reference=f"Net margin: {format_percent(net_margin)}",
                    evidence=f"Net margin is {format_percent(net_margin)}",
                    status="urgent",
                )
            )
        elif net_margin < WEAK_NET_MARGIN_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="profit-weak-margin",
                    title="Strengthen thin net margin",
                    category="profitability",
                    issue=(
                        f"Net margin is only {format_percent(net_margin)}, leaving little buffer for refunds, ad volatility, or rising fulfillment costs."
                    ),
                    action=(
                        "Test price increases, reduce shipping and packaging cost leakage, and focus spend on higher-margin products."
                    ),
                    rationale=(
                        "E-commerce brands with very thin net margins usually lose flexibility quickly when CAC rises or return rates tick up."
                    ),
                    priority="Medium",
                    estimated_impact=(
                        "A few points of additional net margin would improve reinvestment capacity and cash durability."
                    ),
                    metric_reference=f"Net margin: {format_percent(net_margin)}",
                    evidence=f"Net margin is {format_percent(net_margin)}",
                    status="watch",
                )
            )
        elif net_margin >= STRONG_NET_MARGIN_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="profit-strong-margin",
                    title="Margin structure looks healthy",
                    category="profitability",
                    issue=(
                        f"Net margin is running at {format_percent(net_margin)}, which is strong for a growth-oriented e-commerce brand."
                    ),
                    action=(
                        "Protect current pricing discipline and use this margin cushion to test selective growth bets instead of broad discounting."
                    ),
                    rationale=(
                        "Healthy net margins give the business more room to absorb CAC volatility, seasonality, and working-capital swings."
                    ),
                    priority="Low",
                    estimated_impact=(
                        "Maintaining this margin profile can preserve both cash generation and strategic flexibility."
                    ),
                    metric_reference=f"Net margin: {format_percent(net_margin)}",
                    evidence=f"Net margin is {format_percent(net_margin)}",
                    status="healthy",
                )
            )

    runway = _first_numeric(cashflow_data.get("runway_months"), kpi_data.get("runway_months"))
    if runway is not None:
        if runway < LOW_RUNWAY_URGENT_MONTHS:
            recommendations.append(
                _make_recommendation(
                    rec_id="cash-runway-urgent",
                    title="Preserve cash immediately",
                    category="cash",
                    issue=(
                        f"Cash runway is only {runway:.1f} months, which creates immediate liquidity risk."
                    ),
                    action=(
                        "Cut discretionary spend, slow non-essential marketing, improve collections, and avoid new fixed commitments until runway improves."
                    ),
                    rationale=(
                        "With less than three months of runway, even a modest dip in conversion or collections can force reactive decisions."
                    ),
                    priority="High",
                    estimated_impact=(
                        "Reducing burn now may extend runway enough to avoid financing pressure or rushed cost cuts."
                    ),
                    metric_reference=f"Runway: {runway:.1f} months",
                    evidence=f"Runway is {runway:.1f} months",
                    status="urgent",
                )
            )
        elif runway < LOW_RUNWAY_WATCH_MONTHS:
            recommendations.append(
                _make_recommendation(
                    rec_id="cash-runway-watch",
                    title="Improve cash runway before scaling spend",
                    category="cash",
                    issue=(
                        f"Cash runway is {runway:.1f} months, which is workable but still tight for an e-commerce operator."
                    ),
                    action=(
                        "Tighten operating spend, moderate marketing on low-payback channels, and improve inventory discipline to preserve liquidity."
                    ),
                    rationale=(
                        "Runway between three and six months reduces room for demand shocks, delayed collections, or inventory mistakes."
                    ),
                    priority="Medium",
                    estimated_impact=(
                        "Extending runway toward six-plus months would materially reduce execution risk."
                    ),
                    metric_reference=f"Runway: {runway:.1f} months",
                    evidence=f"Runway is {runway:.1f} months",
                    status="watch",
                )
            )
        elif runway >= STRONG_RUNWAY_MONTHS:
            recommendations.append(
                _make_recommendation(
                    rec_id="cash-runway-healthy",
                    title="Runway provides strategic flexibility",
                    category="cash",
                    issue=(
                        f"Cash runway is {runway:.1f} months, giving the brand room to manage seasonality and test growth deliberately."
                    ),
                    action=(
                        "Keep cash discipline in place and allocate incremental spend toward the channels and SKUs with the clearest payback."
                    ),
                    rationale=(
                        "Healthy runway lets the team make proactive decisions instead of optimizing only for short-term survival."
                    ),
                    priority="Low",
                    estimated_impact=(
                        "Maintaining strong runway supports better negotiation, inventory planning, and measured growth."
                    ),
                    metric_reference=f"Runway: {runway:.1f} months",
                    evidence=f"Runway is {runway:.1f} months",
                    status="healthy",
                )
            )

    inventory_coverage = _as_float(cashflow_data.get("inventory_coverage_months"))
    stockout_month_count = _as_float(cashflow_data.get("stockout_month_count"))
    low_coverage_month_count = _as_float(cashflow_data.get("low_coverage_month_count"))
    overstock_month_count = _as_float(cashflow_data.get("overstock_month_count"))
    excess_inventory_units = _as_float(cashflow_data.get("excess_inventory_units"))
    excess_inventory_value = _as_float(cashflow_data.get("excess_inventory_value"))
    cash_tied_in_excess_inventory = _as_float(
        cashflow_data.get("cash_tied_in_excess_inventory")
    )
    inventory_overstock_score = _as_float(cashflow_data.get("inventory_overstock_score"))
    lost_sales_units = _as_float(cashflow_data.get("lost_sales_units"))
    lost_revenue = _as_float(cashflow_data.get("lost_revenue"))
    average_fill_rate = _as_float(cashflow_data.get("average_fill_rate"))
    inventory_stress_score = _as_float(cashflow_data.get("inventory_stress_score"))

    lost_revenue_ratio = (
        lost_revenue / _as_float(cashflow_data.get("monthly_revenue"))
        if _as_float(cashflow_data.get("monthly_revenue")) not in (None, 0)
        and lost_revenue is not None
        else None
        )

    excess_inventory_value_ratio = (
        excess_inventory_value / _as_float(cashflow_data.get("monthly_revenue"))
        if _as_float(cashflow_data.get("monthly_revenue")) not in (None, 0)
        and excess_inventory_value is not None
        else None
    )

    if stockout_month_count is not None and stockout_month_count > 0:
        priority = "High" if lost_revenue_ratio is not None and lost_revenue_ratio >= HIGH_LOST_REVENUE_RATIO_THRESHOLD else "Medium"
        status = "urgent" if priority == "High" else "watch"
        recommendations.append(
            _make_recommendation(
                rec_id="ops-inventory-stockout-risk",
                title="Inventory policy is causing stockouts",
                category="operations",
                issue=(
                    f"Forecast inventory runs short in {stockout_month_count:.0f} month(s), with estimated lost sales of {lost_sales_units:,.0f} units."
                ),
                action=(
                    "Raise the reorder point or safety stock, place inventory earlier ahead of peaks, and moderate campaigns that will outstrip available stock."
                ),
                rationale=(
                    "Stockouts reduce realized revenue and waste acquisition effort when traffic arrives but inventory is unavailable."
                ),
                priority=priority,
                estimated_impact=(
                    f"Recovering the lost demand could preserve roughly {format_currency(lost_revenue)} of revenue."
                ),
                metric_reference=(
                    f"Lost revenue: {format_currency(lost_revenue)}"
                    if lost_revenue is not None
                    else f"Lost sales units: {lost_sales_units:,.0f}"
                ),
                evidence=(
                    f"Average fill rate is {average_fill_rate * 100:.1f}%"
                    if average_fill_rate is not None
                    else f"Stockout months: {stockout_month_count:.0f}"
                ),
                status=status,
            )
        )

    if inventory_coverage is not None and inventory_coverage < LOW_COVERAGE_MONTHS_THRESHOLD and (stockout_month_count or 0) == 0:
        recommendations.append(
            _make_recommendation(
                rec_id="ops-inventory-low-coverage",
                title="Inventory coverage is too tight",
                category="operations",
                issue=(
                    f"Average inventory coverage is only {inventory_coverage:.1f} months, leaving little buffer for campaign spikes or supplier delays."
                ),
                action=(
                    "Increase target inventory modestly, review reorder points, and secure earlier purchase orders on core SKUs."
                ),
                rationale=(
                    "Low coverage can look manageable until demand or lead times move against the business, at which point sales are constrained quickly."
                ),
                priority="Medium",
                estimated_impact=(
                    "A small increase in coverage can reduce stockout risk without requiring a full inventory reset."
                ),
                metric_reference=f"Inventory coverage: {inventory_coverage:.1f} months",
                evidence=(
                    f"Low coverage appears in {low_coverage_month_count:.0f} month(s)"
                    if low_coverage_month_count is not None
                    else f"Inventory coverage is {inventory_coverage:.1f} months"
                ),
                status="watch",
            )
        )

    if inventory_stress_score is not None and inventory_stress_score >= HIGH_INVENTORY_STRESS_THRESHOLD:
        recommendations.append(
            _make_recommendation(
                rec_id="strategy-inventory-stress-high",
                title="Inventory policy is too stressed for current demand",
                category="strategy",
                issue=(
                    f"Inventory stress is elevated at {inventory_stress_score:.0f}/100, suggesting current reorder settings and lead time leave the business exposed."
                ),
                action=(
                    "Rework reorder point, safety stock, and campaign timing together instead of treating inventory planning and growth spend separately."
                ),
                rationale=(
                    "Inventory planning that is too tight can damage both revenue capture and cash timing, especially in seasonal or promotion-heavy periods."
                ),
                priority="High",
                estimated_impact=(
                    "Reducing inventory stress can improve fill rate while avoiding reactive emergency buys."
                ),
                metric_reference=f"Inventory stress: {inventory_stress_score:.0f}/100",
                evidence=f"Inventory stress score is {inventory_stress_score:.0f}/100",
                status="urgent",
            )
        )
    elif inventory_stress_score is not None and inventory_stress_score >= MODERATE_INVENTORY_STRESS_THRESHOLD:
        recommendations.append(
            _make_recommendation(
                rec_id="strategy-inventory-stress-watch",
                title="Monitor inventory stress before scaling demand",
                category="strategy",
                issue=(
                    f"Inventory stress is {inventory_stress_score:.0f}/100, which suggests the current policy may be too tight for aggressive campaigns."
                ),
                action=(
                    "Pressure-test lead time assumptions, review safety stock, and align upcoming promotions with inventory availability."
                ),
                rationale=(
                    "A moderately stressed inventory policy can become a hard constraint quickly when demand accelerates."
                ),
                priority="Medium",
                estimated_impact=(
                    "Improving inventory resilience should lower the risk of missed sales during peak demand periods."
                ),
                metric_reference=f"Inventory stress: {inventory_stress_score:.0f}/100",
                evidence=f"Inventory stress score is {inventory_stress_score:.0f}/100",
                status="watch",
            )
        )

    if (
        overstock_month_count is not None
        and overstock_month_count > 0
        and inventory_overstock_score is not None
    ):
        priority = (
            "High"
            if excess_inventory_value_ratio is not None
            and excess_inventory_value_ratio >= HIGH_EXCESS_INVENTORY_VALUE_RATIO_THRESHOLD
            else "Medium"
        )
        recommendations.append(
            _make_recommendation(
                rec_id="ops-inventory-overstock",
                title="Too much cash is tied up in excess inventory",
                category="operations",
                issue=(
                    f"Inventory looks overstocked in {overstock_month_count:.0f} month(s), with about {excess_inventory_units:,.0f} excess units above target coverage."
                ),
                action=(
                    "Lower target inventory or reorder quantity, delay the next PO where possible, and use selective promotions to work down excess stock."
                ),
                rationale=(
                    "Excess inventory can tie up cash, increase storage drag, and hide slower demand until the next reorder cycle."
                ),
                priority=priority,
                estimated_impact=(
                    f"Working down the excess position could free up roughly {format_currency(cash_tied_in_excess_inventory)} of cash."
                ),
                metric_reference=(
                    f"Excess inventory value: {format_currency(excess_inventory_value)}"
                ),
                evidence=(
                    f"Inventory overstock score is {inventory_overstock_score:.0f}/100"
                ),
                status="urgent" if priority == "High" else "watch",
            )
        )

    if (
        inventory_overstock_score is not None
        and inventory_overstock_score >= MODERATE_OVERSTOCK_SCORE_THRESHOLD
        and inventory_stress_score not in (None,)
        and inventory_stress_score < MODERATE_INVENTORY_STRESS_THRESHOLD
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="strategy-inventory-balance-excess",
                title="Rebalance inventory after demand slowdown",
                category="strategy",
                issue=(
                    f"Inventory posture has shifted toward excess, with an overstock score of {inventory_overstock_score:.0f}/100."
                ),
                action=(
                    "Reduce reorder aggressiveness, keep campaign plans aligned to real demand, and avoid adding new inventory until current stock coverage normalizes."
                ),
                rationale=(
                    "When demand softens, the right move is often to preserve cash by selling through current stock before rebuilding inventory."
                ),
                priority="Medium",
                estimated_impact=(
                    "Rebalancing inventory policy can improve cash flexibility without relying only on deeper discounting."
                ),
                metric_reference=f"Overstock score: {inventory_overstock_score:.0f}/100",
                evidence=(
                    f"Cash tied in excess inventory is {format_currency(cash_tied_in_excess_inventory)}"
                ),
                status="watch",
            )
        )

    forecast_trend_direction = (
        str(forecast_data.get("forecast_trend_direction"))
        if forecast_data.get("forecast_trend_direction") is not None
        else None
    )
    ltv_cac_ratio_for_mix = _first_numeric(kpi_data.get("ltv_cac_ratio"))
    forecast_paid_share = _as_float(forecast_data.get("forecast_paid_share"))
    forecast_retention_share = _as_float(forecast_data.get("forecast_retention_share"))
    forecast_paid_trend = (
        str(forecast_data.get("forecast_paid_trend"))
        if forecast_data.get("forecast_paid_trend") is not None
        else None
    )
    forecast_retention_trend = (
        str(forecast_data.get("forecast_retention_trend"))
        if forecast_data.get("forecast_retention_trend") is not None
        else None
    )
    channel_growth_quality_label = (
        str(forecast_data.get("channel_growth_quality_label"))
        if forecast_data.get("channel_growth_quality_label") is not None
        else None
    )
    channel_weighted_margin_quality = _as_float(
        forecast_data.get("channel_weighted_margin_quality")
    )
    channel_paid_margin_quality = _as_float(
        forecast_data.get("channel_paid_margin_quality")
    )
    channel_retention_margin_quality = _as_float(
        forecast_data.get("channel_retention_margin_quality")
    )
    if (
        forecast_trend_direction == "Falling"
        and inventory_overstock_score is not None
        and inventory_overstock_score >= MODERATE_OVERSTOCK_SCORE_THRESHOLD
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="strategy-forecast-demand-falling-overstock",
                title="Forecasted demand is weakening against current inventory",
                category="strategy",
                issue=(
                    "Demand forecast is falling while inventory posture remains heavy, increasing the risk of cash being trapped in slower-moving stock."
                ),
                action=(
                    "Reduce reorder levels, preserve cash, and work down current inventory before committing to more units."
                ),
                rationale=(
                    "A weakening baseline forecast should usually tighten inventory policy before it loosens pricing discipline."
                ),
                priority="Medium",
                estimated_impact=(
                    "Avoiding overbuying during a softer demand period can materially improve working-capital flexibility."
                ),
                metric_reference="Forecast trend: Falling",
                evidence="The baseline demand forecast is falling.",
                status="watch",
            )
        )

    if channel_growth_quality_label == "Weak":
        recommendations.append(
            _make_recommendation(
                rec_id="growth-quality-weak",
                title="Growth quality is deteriorating",
                category="growth",
                issue=(
                    "Channel-level contribution after acquisition is weak, which means recent demand mix is not translating cleanly into profitable growth."
                ),
                action=(
                    "Improve paid efficiency, protect pricing discipline, and lean harder on retention and organic demand before scaling spend."
                ),
                rationale=(
                    "Blended demand can look healthy even when the underlying acquisition mix is compressing contribution quality."
                ),
                priority="High",
                estimated_impact=(
                    "Improving growth quality can widen contribution without needing the same level of incremental spend."
                ),
                metric_reference=(
                    f"Weighted margin quality: {channel_weighted_margin_quality * 100:.1f}%"
                    if channel_weighted_margin_quality is not None
                    else "Growth quality: Weak"
                ),
                evidence="Channel-level margin quality is weak after acquisition cost.",
                status="urgent",
            )
        )
    elif channel_growth_quality_label == "Strong":
        recommendations.append(
            _make_recommendation(
                rec_id="growth-quality-strong",
                title="Channel mix is supporting healthier growth",
                category="growth",
                issue=(
                    "Channel contribution quality looks healthy, suggesting recent demand mix is supporting better economics."
                ),
                action=(
                    "Preserve the current mix discipline and keep scaling the channels with the cleanest contribution after acquisition cost."
                ),
                rationale=(
                    "Healthy growth quality usually means the business is not relying too heavily on expensive acquisition to hold volume."
                ),
                priority="Low",
                estimated_impact=(
                    "Maintaining strong growth quality can protect margin while still supporting topline expansion."
                ),
                metric_reference=(
                    f"Weighted margin quality: {channel_weighted_margin_quality * 100:.1f}%"
                    if channel_weighted_margin_quality is not None
                    else "Growth quality: Strong"
                ),
                evidence="Channel-level margin quality is healthy after acquisition cost.",
                status="healthy",
            )
        )

    if (
        forecast_trend_direction == "Rising"
        and inventory_stress_score is not None
        and inventory_stress_score >= MODERATE_INVENTORY_STRESS_THRESHOLD
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="ops-forecast-demand-rising-tight",
                title="Rising demand forecast may outpace inventory policy",
                category="operations",
                issue=(
                    "Demand forecast is rising, but the current inventory policy already looks tight."
                ),
                action=(
                    "Increase reorder timing discipline, pressure-test safety stock, and secure inventory earlier before demand ramps further."
                ),
                rationale=(
                    "When demand is trending up, a tight inventory policy can turn into missed revenue faster than historical averages suggest."
                ),
                priority="Medium",
                estimated_impact=(
                    "Preparing inventory earlier can improve fill rate and reduce emergency purchase pressure."
                ),
                metric_reference="Forecast trend: Rising",
                evidence="The baseline demand forecast is rising.",
                status="watch",
            )
        )

    if (
        channel_paid_margin_quality is not None
        and channel_paid_margin_quality < 0.10
        and forecast_paid_share is not None
        and forecast_paid_share >= 0.35
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="growth-channel-paid-margin-thin",
                title="Paid demand is growing at weak contribution quality",
                category="growth",
                issue=(
                    f"Paid demand is a large share of volume, but paid contribution quality is only {channel_paid_margin_quality * 100:.1f}%."
                ),
                action=(
                    "Tighten paid targeting, improve conversion efficiency, and avoid scaling spend until contribution after acquisition cost improves."
                ),
                rationale=(
                    "High-cost paid growth can dilute blended margin quality even when total units continue to rise."
                ),
                priority="High",
                estimated_impact=(
                    "Improving paid contribution quality can reduce cash burn and raise blended profitability."
                ),
                metric_reference=f"Paid margin quality: {channel_paid_margin_quality * 100:.1f}%",
                evidence="Paid demand is carrying too much of the growth mix at weak contribution quality.",
                status="urgent",
            )
        )

    if (
        channel_retention_margin_quality is not None
        and channel_retention_margin_quality >= 0.20
        and forecast_retention_share is not None
        and forecast_retention_share >= 0.25
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="growth-channel-retention-quality-strong",
                title="Retention demand is improving blended economics",
                category="growth",
                issue=(
                    f"Retention is contributing meaningfully to demand and retention contribution quality is {channel_retention_margin_quality * 100:.1f}%."
                ),
                action=(
                    "Keep investing in repeat purchase flows, bundles, and loyalty mechanics before leaning harder on costlier acquisition."
                ),
                rationale=(
                    "Retention demand usually carries stronger contribution quality because it depends less on paid acquisition cost."
                ),
                priority="Low",
                estimated_impact=(
                    "A stronger retention mix can improve growth quality and reduce pressure on paid spend."
                ),
                metric_reference=f"Retention margin quality: {channel_retention_margin_quality * 100:.1f}%",
                evidence="Retention contribution quality is supporting healthier blended economics.",
                status="healthy",
            )
        )

    if (
        forecast_paid_share is not None
        and forecast_paid_share >= 0.40
        and ltv_cac_ratio_for_mix is not None
        and ltv_cac_ratio_for_mix < WEAK_LTV_CAC_THRESHOLD
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="growth-channel-paid-quality-weak",
                title="Too much demand is leaning on expensive paid acquisition",
                category="growth",
                issue=(
                    f"Paid demand is contributing about {forecast_paid_share * 100:.0f}% of forecasted units while LTV:CAC remains weak."
                ),
                action=(
                    "Improve paid efficiency before scaling, and shift more emphasis toward retention and organic conversion."
                ),
                rationale=(
                    "When channel mix leans too heavily on paid demand during weak acquisition economics, growth quality usually deteriorates."
                ),
                priority="Medium",
                estimated_impact=(
                    "Improving paid mix quality can reduce cash burn and make growth more durable."
                ),
                metric_reference=f"Paid share: {forecast_paid_share * 100:.0f}%",
                evidence=f"LTV:CAC is {ltv_cac_ratio_for_mix:.1f}x with a high paid-demand mix.",
                status="watch",
            )
        )

    if (
        forecast_retention_share is not None
        and forecast_retention_share >= 0.30
        and forecast_retention_trend == "Rising"
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="growth-channel-retention-healthy",
                title="Retention demand is supporting healthier growth",
                category="growth",
                issue=(
                    f"Retention is contributing about {forecast_retention_share * 100:.0f}% of forecasted demand and trending upward."
                ),
                action=(
                    "Lean into lifecycle marketing, repeat purchase programs, and cross-sell offers before leaning harder on paid acquisition."
                ),
                rationale=(
                    "A stronger retention stream usually improves growth efficiency because those units rely less on new acquisition spend."
                ),
                priority="Low",
                estimated_impact=(
                    "Sustaining retention demand can improve margin quality and reduce pressure on CAC-driven growth."
                ),
                metric_reference=f"Retention share: {forecast_retention_share * 100:.0f}%",
                evidence="Retention forecast is rising.",
                status="healthy",
            )
        )

    if forecast_paid_trend == "Falling" and forecast_trend_direction == "Stable":
        recommendations.append(
            _make_recommendation(
                rec_id="growth-channel-paid-softening",
                title="Paid demand is softening beneath the surface",
                category="growth",
                issue=(
                    "Blended demand looks stable, but the paid channel forecast is weakening."
                ),
                action=(
                    "Audit channel efficiency, creative fatigue, and landing-page performance before increasing ad budgets."
                ),
                rationale=(
                    "A blended forecast can hide deteriorating acquisition quality when lower-cost channels offset a softening paid stream."
                ),
                priority="Medium",
                estimated_impact=(
                    "Catching paid softness early can protect CAC and avoid overcommitting inventory to weaker demand quality."
                ),
                metric_reference="Paid trend: Falling",
                evidence="The paid-demand forecast is falling while blended demand remains stable.",
                status="watch",
            )
        )

    supplier_current_name = (
        str(supply_chain_data.get("supplier_current_name"))
        if supply_chain_data.get("supplier_current_name") is not None
        else None
    )
    supplier_best_value_name = (
        str(supply_chain_data.get("supplier_best_value_name"))
        if supply_chain_data.get("supplier_best_value_name") is not None
        else None
    )
    supplier_best_cash_name = (
        str(supply_chain_data.get("supplier_best_cash_name"))
        if supply_chain_data.get("supplier_best_cash_name") is not None
        else None
    )
    supplier_best_stockout_name = (
        str(supply_chain_data.get("supplier_best_stockout_name"))
        if supply_chain_data.get("supplier_best_stockout_name") is not None
        else None
    )
    supplier_selected_objective = (
        str(supply_chain_data.get("supplier_selected_objective"))
        if supply_chain_data.get("supplier_selected_objective") is not None
        else None
    )
    supplier_selected_name = (
        str(supply_chain_data.get("supplier_selected_name"))
        if supply_chain_data.get("supplier_selected_name") is not None
        else None
    )
    supplier_selected_cash_tie_up_ratio = _as_float(
        supply_chain_data.get("supplier_selected_cash_tie_up_ratio")
    )
    supplier_selected_stockout_pressure_score = _as_float(
        supply_chain_data.get("supplier_selected_stockout_pressure_score")
    )
    supplier_selected_lead_time_months = _as_float(
        supply_chain_data.get("supplier_selected_lead_time_months")
    )
    supplier_selected_reliability_score = _as_float(
        supply_chain_data.get("supplier_selected_reliability_score")
    )
    supplier_landed_cost_savings_per_unit = _as_float(
        supply_chain_data.get("supplier_landed_cost_savings_per_unit")
    )
    supplier_cash_tie_up_savings = _as_float(
        supply_chain_data.get("supplier_cash_tie_up_savings")
    )
    supplier_lead_time_improvement_months = _as_float(
        supply_chain_data.get("supplier_lead_time_improvement_months")
    )

    if (
        supplier_current_name is not None
        and supplier_best_value_name is not None
        and supplier_best_value_name != supplier_current_name
        and supplier_landed_cost_savings_per_unit is not None
        and supplier_landed_cost_savings_per_unit >= MEANINGFUL_LANDED_COST_SAVINGS_THRESHOLD
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="ops-supplier-lower-landed-cost",
                title="A lower-landed-cost supplier could improve unit economics",
                category="operations",
                issue=(
                    f"{supplier_current_name} is not the best-value sourcing option, and landed-cost savings of about {format_currency(supplier_landed_cost_savings_per_unit)} per unit appear available."
                ),
                action=(
                    f"Review whether switching part of the volume to {supplier_best_value_name} can reduce landed cost without adding unacceptable lead-time or service risk."
                ),
                rationale=(
                    "Even modest landed-cost improvements can scale materially across recurring purchase orders for an e-commerce brand."
                ),
                priority="Medium",
                estimated_impact=(
                    "Lower landed cost should improve gross profit and reduce inventory-buy cash outflow at the next reorder."
                ),
                metric_reference=(
                    f"Landed-cost savings: {format_currency(supplier_landed_cost_savings_per_unit)} per unit"
                ),
                evidence=(
                    f"{supplier_best_value_name} ranks best on value while current sourcing remains with {supplier_current_name}."
                ),
                status="watch",
            )
        )

    if (
        runway is not None
        and runway < LOW_RUNWAY_WATCH_MONTHS
        and supplier_best_cash_name is not None
        and supplier_best_cash_name != supplier_current_name
        and supplier_selected_cash_tie_up_ratio is not None
        and supplier_selected_cash_tie_up_ratio >= HIGH_SUPPLIER_CASH_TIE_UP_RATIO_THRESHOLD
        and supplier_cash_tie_up_savings is not None
        and supplier_cash_tie_up_savings > 0
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="cash-supplier-moq-pressure",
                title="Current supplier terms create too much cash tie-up",
                category="cash",
                issue=(
                    "MOQ-driven purchase size is heavy relative to current liquidity, which increases working-capital strain."
                ),
                action=(
                    f"Consider shifting volume toward {supplier_best_cash_name} or renegotiating MOQ terms before placing the next large inventory order."
                ),
                rationale=(
                    "When runway is already tight, large MOQ commitments can shorten cash durability before the related inventory converts to sales."
                ),
                priority="High" if runway < LOW_RUNWAY_URGENT_MONTHS else "Medium",
                estimated_impact=(
                    f"Reducing MOQ cash tie-up could preserve roughly {format_currency(supplier_cash_tie_up_savings)} of near-term liquidity."
                ),
                metric_reference=(
                    f"MOQ cash burden: {supplier_selected_cash_tie_up_ratio * 100:.0f}% of cash"
                ),
                evidence=(
                    f"{supplier_selected_objective or 'Selected supplier'} ties up about {supplier_selected_cash_tie_up_ratio * 100:.0f}% of current cash at MOQ."
                ),
                status="urgent" if runway < LOW_RUNWAY_URGENT_MONTHS else "watch",
            )
        )

    if (
        (
            inventory_coverage is not None
            and supplier_selected_lead_time_months is not None
            and supplier_selected_lead_time_months > inventory_coverage
        )
        or (
            supplier_selected_stockout_pressure_score is not None
            and supplier_selected_stockout_pressure_score >= HIGH_SUPPLIER_STOCKOUT_PRESSURE_THRESHOLD
        )
    ):
        target_supplier = supplier_best_stockout_name or supplier_selected_name
        recommendations.append(
            _make_recommendation(
                rec_id="ops-supplier-lead-time-risk",
                title="Supplier lead time looks risky for current inventory posture",
                category="operations",
                issue=(
                    "Current sourcing lead time is long relative to inventory coverage, which increases stockout pressure if demand stays firm or accelerates."
                ),
                action=(
                    f"Use a faster or more reliable supplier such as {target_supplier}, or raise reorder timing and safety stock before the next demand spike."
                ),
                rationale=(
                    "Long lead times matter much more when inventory policy is already tight, because the business has less time to correct errors."
                ),
                priority="High" if (stockout_month_count or 0) > 0 else "Medium",
                estimated_impact=(
                    "Improving supplier responsiveness can reduce lost-sales risk and lower emergency replenishment pressure."
                ),
                metric_reference=(
                    f"Lead time: {supplier_selected_lead_time_months:.1f} months"
                    if supplier_selected_lead_time_months is not None
                    else "Lead-time risk elevated"
                ),
                evidence=(
                    f"Inventory coverage is {_format_optional_months(inventory_coverage)} and supplier stockout pressure is {supplier_selected_stockout_pressure_score:.0f}/100."
                    if supplier_selected_stockout_pressure_score is not None
                    else f"Inventory coverage is {_format_optional_months(inventory_coverage)}."
                ),
                status="urgent" if (stockout_month_count or 0) > 0 else "watch",
            )
        )

    if (
        forecast_trend_direction == "Rising"
        and supplier_selected_reliability_score is not None
        and supplier_selected_reliability_score < LOW_SUPPLIER_RELIABILITY_THRESHOLD
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="ops-supplier-reliability-rising-demand",
                title="Supplier reliability may be too weak for rising demand",
                category="operations",
                issue=(
                    "Demand is trending up, but supplier reliability is not especially strong."
                ),
                action=(
                    "Review service-level performance, defect trends, and backup sourcing before leaning harder into campaigns or larger purchase orders."
                ),
                rationale=(
                    "Reliability matters more when demand rises because replenishment mistakes translate into missed revenue faster."
                ),
                priority="Medium",
                estimated_impact=(
                    "Improving supplier reliability should reduce service risk without relying only on larger safety stock."
                ),
                metric_reference=(
                    f"Supplier reliability: {supplier_selected_reliability_score * 100:.0f}%"
                ),
                evidence="Demand forecast is rising while supplier reliability remains below the preferred threshold.",
                status="watch",
            )
        )

    if (
        supplier_current_name is not None
        and supplier_best_value_name == supplier_current_name
        and supplier_landed_cost_savings_per_unit is not None
        and supplier_landed_cost_savings_per_unit <= 0.05
    ):
        recommendations.append(
            _make_recommendation(
                rec_id="ops-supplier-position-healthy",
                title="Current sourcing looks competitive",
                category="operations",
                issue=(
                    "Current supplier positioning appears reasonably competitive on landed cost and overall tradeoff quality."
                ),
                action=(
                    "Maintain sourcing discipline and focus negotiations on incremental improvements in lead time, MOQ, and reliability."
                ),
                rationale=(
                    "Not every sourcing decision requires a switch; sometimes the best move is preserving continuity while tightening terms."
                ),
                priority="Low",
                estimated_impact=(
                    "Incremental supplier improvements can strengthen cash and inventory resilience without a disruptive vendor change."
                ),
                metric_reference="Supplier position: Competitive",
                evidence="The current supplier remains close to the best-value option.",
                status="healthy",
            )
        )

    cac = _as_float(kpi_data.get("cac"))
    ltv = _as_float(kpi_data.get("ltv"))
    ltv_cac_ratio = _first_numeric(kpi_data.get("ltv_cac_ratio"))
    if ltv_cac_ratio is not None:
        if ltv_cac_ratio < CRITICAL_LTV_CAC_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="growth-cac-critical",
                    title="Pause inefficient acquisition scaling",
                    category="growth",
                    issue=(
                        f"LTV to CAC is only {ltv_cac_ratio:.1f}x, which suggests acquisition payback is too weak for sustainable scaling."
                    ),
                    action=(
                        "Reduce spend on low-efficiency paid channels and improve retention, repeat purchase, and AOV before pushing more budget into acquisition."
                    ),
                    rationale=(
                        "If customer value is not comfortably above acquisition cost, growth can consume cash faster than it creates durable economics."
                    ),
                    priority="High",
                    estimated_impact=(
                        "Improving LTV:CAC toward 3.0x could make growth spend materially more sustainable."
                    ),
                    metric_reference=f"LTV:CAC: {ltv_cac_ratio:.1f}x",
                    evidence=f"LTV:CAC is {ltv_cac_ratio:.1f}x",
                    status="urgent",
                )
            )
        elif ltv_cac_ratio < WEAK_LTV_CAC_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="growth-cac-watch",
                    title="Improve growth efficiency before increasing ad spend",
                    category="growth",
                    issue=(
                        f"LTV to CAC is {ltv_cac_ratio:.1f}x, which is below the typical comfort zone for efficient e-commerce growth."
                    ),
                    action=(
                        "Refine creative, tighten channel mix, and lift repeat purchase rate or AOV before materially increasing paid acquisition."
                    ),
                    rationale=(
                        "A healthier LTV:CAC ratio creates more room to scale while still protecting cash runway and margin."
                    ),
                    priority="Medium",
                    estimated_impact=(
                        "A stronger payback profile can improve both growth confidence and cash efficiency."
                    ),
                    metric_reference=f"LTV:CAC: {ltv_cac_ratio:.1f}x",
                    evidence=f"LTV:CAC is {ltv_cac_ratio:.1f}x",
                    status="watch",
                )
            )
        elif ltv_cac_ratio >= STRONG_LTV_CAC_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="growth-cac-healthy",
                    title="Acquisition efficiency is supportive of growth",
                    category="growth",
                    issue=(
                        f"LTV to CAC is {ltv_cac_ratio:.1f}x, indicating efficient customer acquisition relative to lifetime value."
                    ),
                    action=(
                        "Scale cautiously in the best-performing channels while protecting retention and contribution margin."
                    ),
                    rationale=(
                        "Efficient LTV:CAC gives the business room to grow without relying solely on discounting or margin sacrifice."
                    ),
                    priority="Low",
                    estimated_impact=(
                        "Maintaining efficient acquisition can support growth without sharply increasing burn."
                    ),
                    metric_reference=f"LTV:CAC: {ltv_cac_ratio:.1f}x",
                    evidence=f"LTV:CAC is {ltv_cac_ratio:.1f}x",
                    status="healthy",
                )
            )

    inventory_turnover = _as_float(kpi_data.get("inventory_turnover"))
    if inventory_turnover is not None:
        if inventory_turnover < WEAK_INVENTORY_TURNOVER_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-inventory-watch",
                    title="Reduce capital tied up in slow-moving inventory",
                    category="operations",
                    issue=(
                        f"Inventory turnover is only {inventory_turnover:.1f}x, suggesting stock is moving slowly relative to sales."
                    ),
                    action=(
                        "Tighten reorder volume, move aging SKUs selectively, and prioritize high-velocity products in planning and merchandising."
                    ),
                    rationale=(
                        "Slow-moving inventory locks up cash, increases markdown risk, and raises storage pressure."
                    ),
                    priority="Medium",
                    estimated_impact=(
                        "Reducing excess inventory may improve near-term cash flexibility and lower markdown risk."
                    ),
                    metric_reference=f"Inventory turnover: {inventory_turnover:.1f}x",
                    evidence=f"Inventory turnover is {inventory_turnover:.1f}x",
                    status="watch",
                )
            )
        elif inventory_turnover >= STRONG_INVENTORY_TURNOVER_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-inventory-healthy",
                    title="Inventory velocity looks healthy",
                    category="operations",
                    issue=(
                        f"Inventory turnover is {inventory_turnover:.1f}x, which indicates stock is converting to sales efficiently."
                    ),
                    action=(
                        "Keep replenishment discipline in place and protect best-selling SKUs from stockouts during demand spikes."
                    ),
                    rationale=(
                        "Healthy inventory turnover improves cash conversion and reduces capital trapped in underperforming stock."
                    ),
                    priority="Low",
                    estimated_impact=(
                        "Sustaining strong turnover can preserve working capital and support smoother growth."
                    ),
                    metric_reference=f"Inventory turnover: {inventory_turnover:.1f}x",
                    evidence=f"Inventory turnover is {inventory_turnover:.1f}x",
                    status="healthy",
                )
            )

    fixed_cost_burden = _as_float(profitability_data.get("fixed_cost_ratio"))
    if fixed_cost_burden is not None:
        if fixed_cost_burden >= CRITICAL_FIXED_COST_BURDEN_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="strategy-fixed-cost-critical",
                    title="Reduce fixed cost burden before adding complexity",
                    category="strategy",
                    issue=(
                        f"Fixed costs and core operating expenses are consuming {format_percent(fixed_cost_burden)} of revenue."
                    ),
                    action=(
                        "Delay hiring, rationalize software and overhead, and improve revenue quality before taking on more fixed expense."
                    ),
                    rationale=(
                        "High fixed-cost burden reduces flexibility and makes the brand more exposed to seasonality or channel volatility."
                    ),
                    priority="High",
                    estimated_impact=(
                        "Lowering fixed-cost burden could materially improve breakeven and reduce downside risk."
                    ),
                    metric_reference=f"Fixed-cost burden: {format_percent(fixed_cost_burden)}",
                    evidence=f"Fixed-cost ratio is {format_percent(fixed_cost_burden)}",
                    status="urgent",
                )
            )
        elif fixed_cost_burden >= HIGH_FIXED_COST_BURDEN_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="strategy-fixed-cost-watch",
                    title="Watch overhead growth carefully",
                    category="strategy",
                    issue=(
                        f"Fixed costs and operating expenses are at {format_percent(fixed_cost_burden)} of revenue, which can compress operating leverage."
                    ),
                    action=(
                        "Review subscriptions, headcount plans, and fixed overhead before committing to additional recurring costs."
                    ),
                    rationale=(
                        "Growing fixed costs too early can make short-term revenue dips much harder to absorb."
                    ),
                    priority="Medium",
                    estimated_impact=(
                        "Improving revenue before adding overhead should strengthen operating leverage."
                    ),
                    metric_reference=f"Fixed-cost burden: {format_percent(fixed_cost_burden)}",
                    evidence=f"Fixed-cost ratio is {format_percent(fixed_cost_burden)}",
                    status="watch",
                )
            )

    return_rate = _as_float(kpi_data.get("return_rate"))
    if return_rate is not None:
        if return_rate >= HIGH_RETURN_RATE_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-returns-high",
                    title="Address margin erosion from returns",
                    category="operations",
                    issue=(
                        f"Return and refund rate is {format_percent(return_rate)}, which is high enough to materially erode gross margin."
                    ),
                    action=(
                        "Audit product quality, improve PDP copy and sizing guidance, and identify the SKUs or channels driving most returns."
                    ),
                    rationale=(
                        "High returns create a double hit through lost revenue, reverse logistics, and lower confidence in channel quality."
                    ),
                    priority="High",
                    estimated_impact=(
                        "Reducing return rate can improve margin, inventory availability, and cash recovery."
                    ),
                    metric_reference=f"Return rate: {format_percent(return_rate)}",
                    evidence=f"Return rate is {format_percent(return_rate)}",
                    status="urgent",
                )
            )
        elif return_rate >= WATCH_RETURN_RATE_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-returns-watch",
                    title="Monitor refund pressure closely",
                    category="operations",
                    issue=(
                        f"Return and refund rate is {format_percent(return_rate)}, which may be putting avoidable pressure on margin."
                    ),
                    action=(
                        "Review return reasons, tighten merchandising on high-return products, and refine product education before the rate worsens."
                    ),
                    rationale=(
                        "Even moderate return rates can erode e-commerce contribution margin if left unchecked."
                    ),
                    priority="Medium",
                    estimated_impact=(
                        "Reducing avoidable returns would improve contribution margin and free up inventory."
                    ),
                    metric_reference=f"Return rate: {format_percent(return_rate)}",
                    evidence=f"Return rate is {format_percent(return_rate)}",
                    status="watch",
                )
            )

    variable_cost_ratio = _as_float(profitability_data.get("variable_cost_ratio"))
    if variable_cost_ratio is not None:
        if variable_cost_ratio >= CRITICAL_VARIABLE_COST_RATIO_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-fulfillment-critical",
                    title="Unit-level costs are too heavy",
                    category="operations",
                    issue=(
                        f"Product, shipping, fulfillment, and packaging costs are consuming {format_percent(variable_cost_ratio)} of revenue."
                    ),
                    action=(
                        "Renegotiate shipping, review packaging and pick-pack costs, and shift mix toward products with stronger contribution margin."
                    ),
                    rationale=(
                        "When unit-level costs absorb too much revenue, it becomes difficult for marketing and overhead to scale efficiently."
                    ),
                    priority="High",
                    estimated_impact=(
                        "Reducing fulfillment and unit-cost pressure could materially widen gross margin."
                    ),
                    metric_reference=f"Variable cost ratio: {format_percent(variable_cost_ratio)}",
                    evidence=f"Variable cost ratio is {format_percent(variable_cost_ratio)}",
                    status="urgent",
                )
            )
        elif variable_cost_ratio >= HIGH_VARIABLE_COST_RATIO_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-fulfillment-watch",
                    title="Watch shipping and fulfillment cost pressure",
                    category="operations",
                    issue=(
                        f"Product, shipping, fulfillment, and packaging costs are at {format_percent(variable_cost_ratio)} of revenue, compressing contribution margin."
                    ),
                    action=(
                        "Review carrier rates, free-shipping threshold, packaging choices, and SKU-level fulfillment economics."
                    ),
                    rationale=(
                        "Small improvements in unit-level fulfillment cost can have an outsized effect on e-commerce gross margin."
                    ),
                    priority="Medium",
                    estimated_impact=(
                        "Lower shipping and fulfillment leakage could improve margin quality without requiring more sales volume."
                    ),
                    metric_reference=f"Variable cost ratio: {format_percent(variable_cost_ratio)}",
                    evidence=f"Variable cost ratio is {format_percent(variable_cost_ratio)}",
                    status="watch",
                )
            )

    price_per_unit = _as_float(profitability_data.get("price_per_unit"))
    product_cost_per_unit = _as_float(profitability_data.get("product_cost_per_unit"))
    shipping_cost_per_unit = _as_float(profitability_data.get("shipping_cost_per_unit"))
    fulfillment_cost_per_unit = _as_float(profitability_data.get("fulfillment_cost_per_unit"))

    if price_per_unit not in (None, 0):
        product_cost_ratio = (
            product_cost_per_unit / price_per_unit
            if product_cost_per_unit is not None
            else None
        )
        shipping_cost_ratio = (
            shipping_cost_per_unit / price_per_unit
            if shipping_cost_per_unit is not None
            else None
        )
        fulfillment_cost_ratio = (
            fulfillment_cost_per_unit / price_per_unit
            if fulfillment_cost_per_unit is not None
            else None
        )

        if product_cost_ratio is not None and product_cost_ratio >= 0.50:
            recommendations.append(
                _make_recommendation(
                    rec_id="profit-product-cost-pressure",
                    title="Supplier cost structure is too heavy",
                    category="profitability",
                    issue=f"Product cost per unit is {format_percent(product_cost_ratio)} of selling price.",
                    action="Review supplier terms, sourcing alternatives, and product mix to improve product-level gross margin.",
                    rationale="If product cost absorbs too much of selling price, the business has limited room to recover margin elsewhere.",
                    priority="Medium",
                    estimated_impact="Reducing product cost can directly improve gross profit on every order.",
                    metric_reference=f"Product cost / price: {format_percent(product_cost_ratio)}",
                    evidence=f"Product cost per unit is {format_currency(product_cost_per_unit)} against a price of {format_currency(price_per_unit)}",
                    status="watch",
                )
            )

        if shipping_cost_ratio is not None and shipping_cost_ratio >= 0.12:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-shipping-pressure",
                    title="Shipping costs are compressing unit economics",
                    category="operations",
                    issue=f"Shipping cost per unit is {format_percent(shipping_cost_ratio)} of selling price.",
                    action="Renegotiate carrier pricing, raise the free-shipping threshold, or recover part of the shipping cost through pricing.",
                    rationale="High shipping intensity can erode contribution margin even if demand remains stable.",
                    priority="Medium",
                    estimated_impact="Improving shipping economics could materially strengthen gross margin.",
                    metric_reference=f"Shipping cost / price: {format_percent(shipping_cost_ratio)}",
                    evidence=f"Shipping cost per unit is {format_currency(shipping_cost_per_unit)} against a price of {format_currency(price_per_unit)}",
                    status="watch",
                )
            )

        if fulfillment_cost_ratio is not None and fulfillment_cost_ratio >= 0.08:
            recommendations.append(
                _make_recommendation(
                    rec_id="ops-fulfillment-pressure",
                    title="Fulfillment efficiency needs improvement",
                    category="operations",
                    issue=f"Fulfillment cost per unit is {format_percent(fulfillment_cost_ratio)} of selling price.",
                    action="Review pick-pack workflow, 3PL pricing, and warehouse efficiency to reduce fulfillment drag.",
                    rationale="Fulfillment costs that drift too high weaken margin quality as order volume scales.",
                    priority="Medium",
                    estimated_impact="Improving logistics efficiency can protect margin without requiring more top-line growth.",
                    metric_reference=f"Fulfillment cost / price: {format_percent(fulfillment_cost_ratio)}",
                    evidence=f"Fulfillment cost per unit is {format_currency(fulfillment_cost_per_unit)} against a price of {format_currency(price_per_unit)}",
                    status="watch",
                )
            )

    gross_margin = _first_numeric(kpi_data.get("gross_margin"), profitability_data.get("gross_margin"))
    if gross_margin is not None and gross_margin >= STRONG_GROSS_MARGIN_THRESHOLD:
        recommendations.append(
            _make_recommendation(
                rec_id="profit-gross-margin-healthy",
                title="Gross margin supports reinvestment",
                category="profitability",
                issue=(
                    f"Gross margin is {format_percent(gross_margin)}, which gives the brand room to absorb acquisition and operating costs."
                ),
                action=(
                    "Protect this margin advantage by avoiding broad discounting and doubling down on high-contribution products."
                ),
                rationale=(
                    "Healthy gross margin is the starting point for durable reinvestment in customer acquisition and inventory."
                ),
                priority="Low",
                estimated_impact=(
                    "Sustaining strong gross margin can make both growth and cash planning more resilient."
                ),
                metric_reference=f"Gross margin: {format_percent(gross_margin)}",
                evidence=f"Gross margin is {format_percent(gross_margin)}",
                status="healthy",
            )
        )

    health_score = _first_numeric(health_data.get("health_score"), kpi_data.get("health_score"))
    if health_score is not None:
        if health_score < AT_RISK_HEALTH_SCORE_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="strategy-health-risk",
                    title="Overall business health needs focused intervention",
                    category="strategy",
                    issue=(
                        f"Business Health Score is {health_score:.0f}/100, signaling multiple weak operating dimensions."
                    ),
                    action=(
                        "Prioritize cash preservation, margin repair, and acquisition efficiency before taking on new growth experiments."
                    ),
                    rationale=(
                        "When several dimensions are under pressure at once, a narrower operating plan usually improves results faster than trying to optimize everything simultaneously."
                    ),
                    priority="High",
                    estimated_impact=(
                        "Concentrating on the few biggest constraints can improve execution speed and reduce downside risk."
                    ),
                    metric_reference=f"Health score: {health_score:.0f}/100",
                    evidence=f"Business Health Score is {health_score:.0f}/100",
                    status="urgent",
                )
            )
        elif health_score >= STRONG_HEALTH_SCORE_THRESHOLD:
            recommendations.append(
                _make_recommendation(
                    rec_id="strategy-health-strong",
                    title="Business health is supportive of selective expansion",
                    category="strategy",
                    issue=(
                        f"Business Health Score is {health_score:.0f}/100, indicating strong overall operating balance."
                    ),
                    action=(
                        "Use the current position to test focused growth initiatives while protecting margin and runway guardrails."
                    ),
                    rationale=(
                        "Strong cross-functional performance usually means the team can take measured risks without destabilizing the business."
                    ),
                    priority="Low",
                    estimated_impact=(
                        "Selective expansion from a strong base can produce better growth quality than scaling from a weak one."
                    ),
                    metric_reference=f"Health score: {health_score:.0f}/100",
                    evidence=f"Business Health Score is {health_score:.0f}/100",
                    status="healthy",
                )
            )

    recommendations = _deduplicate_recommendations(recommendations)
    if categories:
        recommendations = [
            recommendation
            for recommendation in recommendations
            if recommendation["category"] in categories
        ]
    recommendations = _limit_healthy_recommendations(recommendations)

    return sorted(
        recommendations,
        key=lambda item: (
            PRIORITY_ORDER.get(item["priority"], 99),
            STATUS_ORDER.get(item["status"], 99),
            item["title"],
        ),
    )


def summarize_recommendations(recommendations: list[Recommendation]) -> dict[str, object]:
    """Build a compact summary for executive UI sections."""
    category_counts = Counter(recommendation["category"] for recommendation in recommendations)
    return {
        "high_priority_count": sum(1 for recommendation in recommendations if recommendation["priority"] == "High"),
        "medium_priority_count": sum(1 for recommendation in recommendations if recommendation["priority"] == "Medium"),
        "low_priority_count": sum(1 for recommendation in recommendations if recommendation["priority"] == "Low"),
        "top_categories": [category for category, _ in category_counts.most_common(3)],
    }


def _make_recommendation(
    rec_id: str,
    title: str,
    category: str,
    issue: str,
    action: str,
    rationale: str,
    priority: str,
    estimated_impact: str,
    metric_reference: str,
    evidence: str,
    status: str,
) -> Recommendation:
    """Create a recommendation dict with a consistent schema."""
    return {
        "id": rec_id,
        "title": title,
        "category": category,
        "issue": issue,
        "action": action,
        "rationale": rationale,
        "priority": priority,
        "estimated_impact": estimated_impact,
        "metric_reference": metric_reference,
        "evidence": evidence,
        "status": status,
    }


def _with_default_context(
    context: dict[str, float | int | str | None],
) -> dict[str, float | int | str | None]:
    """Return a context dict with all stable recommendation keys present."""
    merged_context = DEFAULT_CONTEXT_KEYS.copy()
    merged_context.update(context)
    return merged_context


def _deduplicate_recommendations(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """Remove duplicate recommendations by deterministic id while preserving order."""
    seen_ids: set[str] = set()
    unique_recommendations: list[Recommendation] = []
    for recommendation in recommendations:
        if recommendation["id"] in seen_ids:
            continue
        seen_ids.add(recommendation["id"])
        unique_recommendations.append(recommendation)
    return unique_recommendations


def _limit_healthy_recommendations(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """Keep healthy insights useful but subordinate to warnings."""
    healthy_count = 0
    filtered_recommendations: list[Recommendation] = []
    for recommendation in recommendations:
        if recommendation["status"] == "healthy":
            healthy_count += 1
            if healthy_count > MAX_HEALTHY_RECOMMENDATIONS:
                continue
        filtered_recommendations.append(recommendation)
    return filtered_recommendations


def _first_numeric(*values: object) -> float | None:
    """Return the first available numeric value from a list of candidates."""
    for value in values:
        numeric_value = _as_float(value)
        if numeric_value is not None:
            return numeric_value
    return None


def _format_optional_months(value: float | None) -> str:
    """Format month values safely for evidence strings."""
    if value is None:
        return "N/A"
    return f"{value:.1f} months"


def _get_attr(target: object, attribute_name: str) -> object | None:
    """Read an attribute safely from an object."""
    if target is None:
        return None
    return getattr(target, attribute_name, None)


def _as_float(value: object) -> float | None:
    """Convert simple numeric inputs to float while preserving missing values."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
