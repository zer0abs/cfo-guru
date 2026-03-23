"""Supply chain cost optimizer for supplier tradeoff analysis."""

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.page_sections import render_metric_row
from utils.formatting import format_currency

OBJECTIVE_LABELS = {
    "best_value": "Best Value",
    "cheapest": "Cheapest",
    "fastest": "Fastest",
    "cash_pressure": "Best Under Cash Pressure",
    "stockout_pressure": "Best Under Stockout Pressure",
}

# These weights intentionally stay simple and transparent.
# The optimizer is rule-based rather than mathematical optimization:
# lower landed cost helps cost efficiency, shorter lead time lowers stockout pressure,
# higher reliability reduces service risk, and lower MOQ/order cost protects cash.
OBJECTIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "best_value": {
        "cost_score": 0.35,
        "speed_score": 0.20,
        "reliability_score": 0.25,
        "cash_score": 0.20,
    },
    "cheapest": {
        "cost_score": 0.80,
        "speed_score": 0.05,
        "reliability_score": 0.10,
        "cash_score": 0.05,
    },
    "fastest": {
        "cost_score": 0.05,
        "speed_score": 0.70,
        "reliability_score": 0.20,
        "cash_score": 0.05,
    },
    "cash_pressure": {
        "cost_score": 0.20,
        "speed_score": 0.10,
        "reliability_score": 0.15,
        "cash_score": 0.55,
    },
    "stockout_pressure": {
        "cost_score": 0.10,
        "speed_score": 0.40,
        "reliability_score": 0.40,
        "cash_score": 0.10,
    },
}


@dataclass(frozen=True)
class SupplierOption:
    """Supplier option structure used by the optimizer."""

    supplier_name: str
    product_cost_per_unit: float
    inbound_shipping_cost_per_unit: float
    lead_time_months: float
    minimum_order_quantity: int
    reliability_score: float
    quality_risk_score: float
    notes: str = ""
    is_current: bool = False


@dataclass(frozen=True)
class SupplyChainBusinessContext:
    """Current business conditions used to score supplier tradeoffs."""

    average_selling_price: float
    monthly_demand_units: float
    starting_cash: float
    runway_months: float | None
    inventory_coverage_months: float | None
    safety_stock_units: float


@dataclass(frozen=True)
class SupplierMetrics:
    """Derived supplier tradeoff metrics."""

    option: SupplierOption
    total_landed_cost_per_unit: float
    expected_order_cost_at_moq: float
    lead_time_demand_units: float
    lead_time_burden_value: float
    reliability_adjusted_score: float
    working_capital_ratio: float
    stockout_pressure_score: float
    margin_after_landed_cost: float | None
    objective_scores: dict[str, float]


@dataclass(frozen=True)
class SupplyChainAnalysis:
    """Structured supplier comparison output for UI and recommendations."""

    business_context: SupplyChainBusinessContext
    suppliers: list[SupplierMetrics]
    ranked_by_objective: dict[str, list[SupplierMetrics]]


def load_sample_suppliers() -> list[SupplierOption]:
    """Return demo supplier options for the e-commerce brand."""
    return [
        SupplierOption(
            supplier_name="Pacific Source Co.",
            product_cost_per_unit=7.20,
            inbound_shipping_cost_per_unit=0.85,
            lead_time_months=2.0,
            minimum_order_quantity=3000,
            reliability_score=0.84,
            quality_risk_score=0.05,
            notes="Current balanced offshore supplier.",
            is_current=True,
        ),
        SupplierOption(
            supplier_name="FlexBridge Partners",
            product_cost_per_unit=7.75,
            inbound_shipping_cost_per_unit=0.60,
            lead_time_months=1.2,
            minimum_order_quantity=1200,
            reliability_score=0.92,
            quality_risk_score=0.03,
            notes="Nearshore supplier with lower MOQ and stronger service levels.",
        ),
        SupplierOption(
            supplier_name="Value Harbor Imports",
            product_cost_per_unit=6.55,
            inbound_shipping_cost_per_unit=1.05,
            lead_time_months=2.8,
            minimum_order_quantity=5000,
            reliability_score=0.76,
            quality_risk_score=0.08,
            notes="Lowest nominal cost, but long lead time and larger cash commitment.",
        ),
        SupplierOption(
            supplier_name="FastLane Manufacturing",
            product_cost_per_unit=8.10,
            inbound_shipping_cost_per_unit=0.45,
            lead_time_months=0.8,
            minimum_order_quantity=900,
            reliability_score=0.95,
            quality_risk_score=0.02,
            notes="Fastest option with strong reliability and the smallest MOQ.",
        ),
    ]


def build_supply_chain_business_context(
    average_selling_price: float,
    monthly_demand_units: float,
    starting_cash: float,
    runway_months: float | None,
    inventory_coverage_months: float | None,
    safety_stock_units: float,
) -> SupplyChainBusinessContext:
    """Build the business context used by supplier analysis."""
    return SupplyChainBusinessContext(
        average_selling_price=max(0.0, average_selling_price),
        monthly_demand_units=max(0.0, monthly_demand_units),
        starting_cash=max(1.0, starting_cash),
        runway_months=runway_months,
        inventory_coverage_months=inventory_coverage_months,
        safety_stock_units=max(0.0, safety_stock_units),
    )


def calculate_supplier_metrics(
    option: SupplierOption,
    context: SupplyChainBusinessContext,
) -> SupplierMetrics:
    """Calculate landed-cost and working-capital tradeoffs for one supplier."""
    landed_cost = option.product_cost_per_unit + option.inbound_shipping_cost_per_unit
    expected_order_cost_at_moq = landed_cost * option.minimum_order_quantity
    lead_time_demand_units = context.monthly_demand_units * max(option.lead_time_months, 0.0)
    lead_time_burden_value = lead_time_demand_units * landed_cost
    working_capital_ratio = expected_order_cost_at_moq / max(context.starting_cash, 1.0)
    reliability_adjusted_score = max(
        0.0,
        min(
            100.0,
            (option.reliability_score * 100.0 * 0.7)
            + ((1.0 - option.quality_risk_score) * 100.0 * 0.3),
        ),
    )

    # Higher stockout pressure means the supplier is riskier for continuity.
    inventory_gap = max(
        0.0,
        option.lead_time_months - (context.inventory_coverage_months or 0.0),
    )
    stockout_pressure_score = min(
        100.0,
        (inventory_gap * 28.0)
        + ((1.0 - option.reliability_score) * 55.0)
        + (option.quality_risk_score * 45.0),
    )
    margin_after_landed_cost = (
        (context.average_selling_price - landed_cost) / context.average_selling_price
        if context.average_selling_price > 0
        else None
    )

    return SupplierMetrics(
        option=option,
        total_landed_cost_per_unit=landed_cost,
        expected_order_cost_at_moq=expected_order_cost_at_moq,
        lead_time_demand_units=lead_time_demand_units,
        lead_time_burden_value=lead_time_burden_value,
        reliability_adjusted_score=reliability_adjusted_score,
        working_capital_ratio=working_capital_ratio,
        stockout_pressure_score=stockout_pressure_score,
        margin_after_landed_cost=margin_after_landed_cost,
        objective_scores={},
    )


def analyze_supplier_options(
    suppliers: list[SupplierOption],
    context: SupplyChainBusinessContext,
) -> SupplyChainAnalysis:
    """Analyze supplier options and rank them by each sourcing objective."""
    raw_metrics = [calculate_supplier_metrics(option, context) for option in suppliers]
    cost_scores = _inverse_scores(
        [metric.total_landed_cost_per_unit for metric in raw_metrics]
    )
    speed_scores = _inverse_scores(
        [metric.option.lead_time_months for metric in raw_metrics]
    )
    cash_scores = _inverse_scores(
        [metric.expected_order_cost_at_moq for metric in raw_metrics]
    )
    reliability_scores = [metric.reliability_adjusted_score for metric in raw_metrics]

    enriched_metrics: list[SupplierMetrics] = []
    for index, metric in enumerate(raw_metrics):
        component_scores = {
            "cost_score": cost_scores[index],
            "speed_score": speed_scores[index],
            "cash_score": cash_scores[index],
            "reliability_score": reliability_scores[index],
        }
        objective_scores = {
            objective: _weighted_score(component_scores, weights)
            for objective, weights in OBJECTIVE_WEIGHTS.items()
        }
        enriched_metrics.append(
            SupplierMetrics(
                option=metric.option,
                total_landed_cost_per_unit=metric.total_landed_cost_per_unit,
                expected_order_cost_at_moq=metric.expected_order_cost_at_moq,
                lead_time_demand_units=metric.lead_time_demand_units,
                lead_time_burden_value=metric.lead_time_burden_value,
                reliability_adjusted_score=metric.reliability_adjusted_score,
                working_capital_ratio=metric.working_capital_ratio,
                stockout_pressure_score=metric.stockout_pressure_score,
                margin_after_landed_cost=metric.margin_after_landed_cost,
                objective_scores=objective_scores,
            )
        )

    ranked_by_objective = {
        objective: sorted(
            enriched_metrics,
            key=lambda metric: metric.objective_scores[objective],
            reverse=True,
        )
        for objective in OBJECTIVE_WEIGHTS
    }
    return SupplyChainAnalysis(
        business_context=context,
        suppliers=enriched_metrics,
        ranked_by_objective=ranked_by_objective,
    )


def recommend_supplier_for_objective(
    analysis: SupplyChainAnalysis,
    objective: str,
) -> SupplierMetrics:
    """Return the best-ranked supplier for the selected objective."""
    return analysis.ranked_by_objective[objective][0]


def summarize_supplier_tradeoffs(
    analysis: SupplyChainAnalysis,
    current_supplier_name: str,
    selected_objective: str,
) -> dict[str, str | float | None]:
    """Build a concise summary of supplier tradeoffs."""
    current_supplier = _get_supplier_metrics(analysis, current_supplier_name)
    selected_supplier = recommend_supplier_for_objective(analysis, selected_objective)
    best_value_supplier = recommend_supplier_for_objective(analysis, "best_value")

    return {
        "current_supplier": current_supplier.option.supplier_name,
        "selected_supplier": selected_supplier.option.supplier_name,
        "best_value_supplier": best_value_supplier.option.supplier_name,
        "landed_cost_delta": (
            selected_supplier.total_landed_cost_per_unit
            - current_supplier.total_landed_cost_per_unit
        ),
        "lead_time_delta": (
            selected_supplier.option.lead_time_months
            - current_supplier.option.lead_time_months
        ),
        "moq_cash_delta": (
            selected_supplier.expected_order_cost_at_moq
            - current_supplier.expected_order_cost_at_moq
        ),
    }


def build_supply_chain_context(
    analysis: SupplyChainAnalysis,
    current_supplier_name: str,
    selected_objective: str,
) -> dict[str, float | str | None]:
    """Build a recommendation-ready context from supply-chain analysis."""
    current_supplier = _get_supplier_metrics(analysis, current_supplier_name)
    cheapest_supplier = recommend_supplier_for_objective(analysis, "cheapest")
    fastest_supplier = recommend_supplier_for_objective(analysis, "fastest")
    best_value_supplier = recommend_supplier_for_objective(analysis, "best_value")
    best_cash_supplier = recommend_supplier_for_objective(analysis, "cash_pressure")
    best_stockout_supplier = recommend_supplier_for_objective(
        analysis, "stockout_pressure"
    )
    selected_supplier = recommend_supplier_for_objective(analysis, selected_objective)

    return {
        "supplier_current_name": current_supplier.option.supplier_name,
        "supplier_current_landed_cost_per_unit": current_supplier.total_landed_cost_per_unit,
        "supplier_current_lead_time_months": current_supplier.option.lead_time_months,
        "supplier_current_reliability_score": current_supplier.option.reliability_score,
        "supplier_current_moq": float(current_supplier.option.minimum_order_quantity),
        "supplier_current_order_cost_at_moq": current_supplier.expected_order_cost_at_moq,
        "supplier_best_value_name": best_value_supplier.option.supplier_name,
        "supplier_best_value_landed_cost_per_unit": best_value_supplier.total_landed_cost_per_unit,
        "supplier_best_value_score": best_value_supplier.objective_scores["best_value"],
        "supplier_best_cash_name": best_cash_supplier.option.supplier_name,
        "supplier_best_cash_order_cost_at_moq": best_cash_supplier.expected_order_cost_at_moq,
        "supplier_best_cash_tie_up_ratio": best_cash_supplier.working_capital_ratio,
        "supplier_best_stockout_name": best_stockout_supplier.option.supplier_name,
        "supplier_best_stockout_lead_time_months": best_stockout_supplier.option.lead_time_months,
        "supplier_best_stockout_reliability_score": best_stockout_supplier.option.reliability_score,
        "supplier_selected_objective": OBJECTIVE_LABELS[selected_objective],
        "supplier_selected_name": selected_supplier.option.supplier_name,
        "supplier_selected_landed_cost_per_unit": selected_supplier.total_landed_cost_per_unit,
        "supplier_selected_lead_time_months": selected_supplier.option.lead_time_months,
        "supplier_selected_reliability_score": selected_supplier.option.reliability_score,
        "supplier_selected_order_cost_at_moq": selected_supplier.expected_order_cost_at_moq,
        "supplier_selected_cash_tie_up_ratio": selected_supplier.working_capital_ratio,
        "supplier_selected_stockout_pressure_score": selected_supplier.stockout_pressure_score,
        "supplier_landed_cost_savings_per_unit": (
            current_supplier.total_landed_cost_per_unit
            - cheapest_supplier.total_landed_cost_per_unit
        ),
        "supplier_lead_time_improvement_months": (
            current_supplier.option.lead_time_months
            - fastest_supplier.option.lead_time_months
        ),
        "supplier_cash_tie_up_savings": (
            current_supplier.expected_order_cost_at_moq
            - best_cash_supplier.expected_order_cost_at_moq
        ),
    }


def create_supplier_tradeoff_chart(
    analysis: SupplyChainAnalysis,
    current_supplier_name: str,
    selected_objective: str,
) -> go.Figure:
    """Render a supplier tradeoff scatter for cost, lead time, and MOQ cash tie-up."""
    selected_name = recommend_supplier_for_objective(
        analysis, selected_objective
    ).option.supplier_name
    figure = go.Figure()
    for metric in analysis.suppliers:
        is_current = metric.option.supplier_name == current_supplier_name
        is_selected = metric.option.supplier_name == selected_name
        color = "#ef4444" if is_current else "#2563eb"
        if is_selected:
            color = "#10b981"
        figure.add_trace(
            go.Scatter(
                x=[metric.option.lead_time_months],
                y=[metric.total_landed_cost_per_unit],
                mode="markers+text",
                name=metric.option.supplier_name,
                text=[metric.option.supplier_name],
                textposition="top center",
                marker=dict(
                    size=max(18.0, min(42.0, metric.expected_order_cost_at_moq / 2000.0)),
                    color=color,
                    opacity=0.85,
                    line=dict(color="#0f172a", width=1),
                ),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Lead time: %{x:.1f} mo<br>"
                    "Landed cost: $%{y:.2f}/unit<br>"
                    f"MOQ order cost: {format_currency(metric.expected_order_cost_at_moq)}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title="Supplier Tradeoff Map",
        xaxis_title="Lead Time (Months)",
        yaxis_title="Landed Cost per Unit ($)",
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=False,
    )
    return figure


def render_supplier_summary(
    analysis: SupplyChainAnalysis,
    current_supplier_name: str,
    selected_objective: str,
) -> None:
    """Render compact sourcing summary cards."""
    current_supplier = _get_supplier_metrics(analysis, current_supplier_name)
    selected_supplier = recommend_supplier_for_objective(analysis, selected_objective)
    summary = summarize_supplier_tradeoffs(
        analysis,
        current_supplier_name,
        selected_objective,
    )
    render_metric_row(
        [
            {
                "label": "Current Supplier",
                "value": current_supplier.option.supplier_name,
            },
            {
                "label": OBJECTIVE_LABELS[selected_objective],
                "value": selected_supplier.option.supplier_name,
            },
            {
                "label": "Landed Cost Delta",
                "value": format_currency(summary["landed_cost_delta"]),
            },
            {
                "label": "Lead Time Delta",
                "value": f"{summary['lead_time_delta']:+.1f} mo",
            },
            {
                "label": "MOQ Cash Delta",
                "value": format_currency(summary["moq_cash_delta"]),
            },
            {
                "label": "Working-Capital Tie-Up",
                "value": f"{selected_supplier.working_capital_ratio * 100:.0f}% of cash",
            },
        ],
        columns_per_row=3,
    )


def render_supplier_objective_matrix(analysis: SupplyChainAnalysis) -> None:
    """Render the winner for each sourcing objective."""
    rows = []
    for objective, label in OBJECTIVE_LABELS.items():
        winner = recommend_supplier_for_objective(analysis, objective)
        rows.append(
            {
                "Objective": label,
                "Recommended Supplier": winner.option.supplier_name,
                "Landed Cost": format_currency(winner.total_landed_cost_per_unit),
                "Lead Time": f"{winner.option.lead_time_months:.1f} mo",
                "MOQ Order Cost": format_currency(winner.expected_order_cost_at_moq),
                "Reliability": f"{winner.option.reliability_score * 100:.0f}%",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_supplier_comparison_table(analysis: SupplyChainAnalysis) -> None:
    """Render a detailed supplier comparison table."""
    rows = []
    for metric in analysis.suppliers:
        rows.append(
            {
                "Supplier": metric.option.supplier_name,
                "Current": "Yes" if metric.option.is_current else "",
                "Landed Cost / Unit": format_currency(metric.total_landed_cost_per_unit),
                "MOQ": f"{metric.option.minimum_order_quantity:,}",
                "MOQ Order Cost": format_currency(metric.expected_order_cost_at_moq),
                "Lead Time": f"{metric.option.lead_time_months:.1f} mo",
                "Lead-Time Demand": f"{metric.lead_time_demand_units:,.0f} units",
                "Reliability": f"{metric.option.reliability_score * 100:.0f}%",
                "Quality Risk": f"{metric.option.quality_risk_score * 100:.1f}%",
                "Cash Tie-Up": f"{metric.working_capital_ratio * 100:.0f}%",
                "Stockout Pressure": f"{metric.stockout_pressure_score:.0f}/100",
                "Margin After Landed Cost": (
                    f"{metric.margin_after_landed_cost * 100:.1f}%"
                    if metric.margin_after_landed_cost is not None
                    else "N/A"
                ),
                "Notes": metric.option.notes,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_supply_chain_controls(
    suppliers: list[SupplierOption],
) -> tuple[str, str]:
    """Render supply-chain selector controls."""
    current_index = next(
        (index for index, supplier in enumerate(suppliers) if supplier.is_current),
        0,
    )
    current_supplier_name = st.selectbox(
        "Current supplier",
        options=[supplier.supplier_name for supplier in suppliers],
        index=current_index,
    )
    selected_objective = st.selectbox(
        "Optimization view",
        options=list(OBJECTIVE_LABELS.keys()),
        format_func=lambda value: OBJECTIVE_LABELS[value],
        index=0,
    )
    return current_supplier_name, selected_objective


def _get_supplier_metrics(
    analysis: SupplyChainAnalysis,
    supplier_name: str,
) -> SupplierMetrics:
    """Look up a supplier metric bundle by supplier name."""
    for metric in analysis.suppliers:
        if metric.option.supplier_name == supplier_name:
            return metric
    return analysis.suppliers[0]


def _inverse_scores(values: list[float]) -> list[float]:
    """Convert lower-is-better values into 0-100 scores."""
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        return [75.0] * len(values)
    return [
        100.0 * (max_value - value) / (max_value - min_value)
        for value in values
    ]


def _weighted_score(
    component_scores: dict[str, float],
    weights: dict[str, float],
) -> float:
    """Return a weighted supplier score for a sourcing objective."""
    return sum(component_scores[key] * weight for key, weight in weights.items())
