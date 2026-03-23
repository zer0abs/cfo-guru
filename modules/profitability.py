"""Profitability simulator logic and visualizations."""

from dataclasses import asdict, dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.page_sections import render_metric_row
from utils.formatting import format_currency, format_percent
from utils.state import (
    PROFITABILITY_SECTION,
    get_business_inputs,
    merge_with_default_baseline,
    update_business_inputs,
)


@dataclass(frozen=True)
class ProfitabilityInputs:
    """User-provided assumptions for the profitability simulator."""

    price_per_unit: float
    units_sold: float
    product_cost_per_unit: float
    shipping_cost_per_unit: float
    fulfillment_cost_per_unit: float
    packaging_cost_per_unit: float
    fixed_costs: float
    operating_expenses: float
    marketing_spend: float

    @property
    def variable_cost_per_unit(self) -> float:
        """Backward-compatible accessor for blended variable cost per unit."""
        return (
            self.product_cost_per_unit
            + self.shipping_cost_per_unit
            + self.fulfillment_cost_per_unit
            + self.packaging_cost_per_unit
        )


@dataclass(frozen=True)
class ProfitabilityResults:
    """Calculated profitability metrics derived from simulator inputs."""

    revenue: float
    total_variable_cost_per_unit: float
    total_variable_cost: float
    gross_profit: float
    gross_margin: float | None
    total_cost: float
    net_profit: float
    net_margin: float | None
    break_even_units: float | None
    break_even_revenue: float | None


def get_default_inputs() -> ProfitabilityInputs:
    """Return e-commerce demo defaults so the simulator works immediately."""
    return ProfitabilityInputs(
        price_per_unit=68.0,
        units_sold=1800.0,
        product_cost_per_unit=29.0,
        shipping_cost_per_unit=5.5,
        fulfillment_cost_per_unit=3.5,
        packaging_cost_per_unit=1.0,
        fixed_costs=22000.0,
        operating_expenses=14500.0,
        marketing_spend=18000.0,
    )


def calculate_profitability(inputs: ProfitabilityInputs) -> ProfitabilityResults:
    """Calculate profitability metrics with safe handling for edge cases."""
    _validate_inputs(inputs)

    revenue = inputs.price_per_unit * inputs.units_sold
    total_variable_cost_per_unit = inputs.variable_cost_per_unit
    total_variable_cost = total_variable_cost_per_unit * inputs.units_sold
    gross_profit = revenue - total_variable_cost
    total_cost = (
        total_variable_cost
        + inputs.fixed_costs
        + inputs.operating_expenses
        + inputs.marketing_spend
    )
    net_profit = revenue - total_cost

    gross_margin = gross_profit / revenue if revenue else None
    net_margin = net_profit / revenue if revenue else None

    contribution_margin_per_unit = inputs.price_per_unit - total_variable_cost_per_unit
    fixed_cost_base = (
        inputs.fixed_costs + inputs.operating_expenses + inputs.marketing_spend
    )

    if contribution_margin_per_unit > 0:
        break_even_units = fixed_cost_base / contribution_margin_per_unit
        break_even_revenue = break_even_units * inputs.price_per_unit
    else:
        break_even_units = None
        break_even_revenue = None

    return ProfitabilityResults(
        revenue=revenue,
        total_variable_cost_per_unit=total_variable_cost_per_unit,
        total_variable_cost=total_variable_cost,
        gross_profit=gross_profit,
        gross_margin=gross_margin,
        total_cost=total_cost,
        net_profit=net_profit,
        net_margin=net_margin,
        break_even_units=break_even_units,
        break_even_revenue=break_even_revenue,
    )


def render_sidebar_inputs() -> ProfitabilityInputs:
    """Collect e-commerce profitability assumptions from the sidebar."""
    default_values = asdict(get_default_inputs())
    resolved_defaults, _ = merge_with_default_baseline(
        _normalize_profitability_state(get_business_inputs(PROFITABILITY_SECTION)),
        default_values,
    )

    with st.sidebar:
        st.subheader("Profitability Simulator")
        st.caption(
            "Demo model: a direct-to-consumer brand with paid acquisition, fulfillment, and operating overhead."
        )

        inputs = ProfitabilityInputs(
            price_per_unit=st.number_input(
                "Average selling price",
                min_value=0.0,
                value=float(resolved_defaults["price_per_unit"]),
                step=5.0,
                key="profitability_price_per_unit",
            ),
            units_sold=st.number_input(
                "Units sold",
                min_value=0.0,
                value=float(resolved_defaults["units_sold"]),
                step=10.0,
                key="profitability_units_sold",
            ),
            product_cost_per_unit=0.0,
            shipping_cost_per_unit=0.0,
            fulfillment_cost_per_unit=0.0,
            packaging_cost_per_unit=0.0,
            fixed_costs=st.number_input(
                "Warehouse and platform overhead",
                min_value=0.0,
                value=float(resolved_defaults["fixed_costs"]),
                step=500.0,
                key="profitability_fixed_costs",
            ),
            operating_expenses=st.number_input(
                "Team and operating expenses",
                min_value=0.0,
                value=float(resolved_defaults["operating_expenses"]),
                step=500.0,
                key="profitability_operating_expenses",
            ),
            marketing_spend=st.number_input(
                "Paid acquisition spend",
                min_value=0.0,
                value=float(resolved_defaults["marketing_spend"]),
                step=500.0,
                key="profitability_marketing_spend",
            ),
        )
        st.markdown("**Cost Structure**")
        inputs = ProfitabilityInputs(
            price_per_unit=inputs.price_per_unit,
            units_sold=inputs.units_sold,
            product_cost_per_unit=st.number_input(
                "Product cost per unit",
                min_value=0.0,
                value=float(resolved_defaults["product_cost_per_unit"]),
                step=1.0,
                key="profitability_product_cost_per_unit",
            ),
            shipping_cost_per_unit=st.number_input(
                "Shipping cost per unit",
                min_value=0.0,
                value=float(resolved_defaults["shipping_cost_per_unit"]),
                step=0.5,
                key="profitability_shipping_cost_per_unit",
            ),
            fulfillment_cost_per_unit=st.number_input(
                "Fulfillment cost per unit",
                min_value=0.0,
                value=float(resolved_defaults["fulfillment_cost_per_unit"]),
                step=0.5,
                key="profitability_fulfillment_cost_per_unit",
            ),
            packaging_cost_per_unit=st.number_input(
                "Packaging cost per unit",
                min_value=0.0,
                value=float(resolved_defaults["packaging_cost_per_unit"]),
                step=0.25,
                key="profitability_packaging_cost_per_unit",
            ),
            fixed_costs=inputs.fixed_costs,
            operating_expenses=inputs.operating_expenses,
            marketing_spend=inputs.marketing_spend,
        )
        st.caption(
            f"Total variable cost per unit: {format_currency(inputs.variable_cost_per_unit)}"
        )

    update_business_inputs(PROFITABILITY_SECTION, asdict(inputs))
    return inputs


def render_profitability_metrics(results: ProfitabilityResults) -> None:
    """Render key metric cards at the top of the profitability page."""
    render_metric_row(
        [
            {"label": "Revenue", "value": format_currency(results.revenue)},
            {
                "label": "Variable Cost / Unit",
                "value": format_currency(results.total_variable_cost_per_unit),
            },
            {"label": "Total Cost", "value": format_currency(results.total_cost)},
            {"label": "Gross Profit", "value": format_currency(results.gross_profit)},
            {"label": "Net Profit", "value": format_currency(results.net_profit)},
            {"label": "Gross Margin", "value": format_percent(results.gross_margin)},
            {"label": "Net Margin", "value": format_percent(results.net_margin)},
        ],
        columns_per_row=3,
    )


def create_profit_breakdown_waterfall(
    inputs: ProfitabilityInputs, results: ProfitabilityResults
) -> go.Figure:
    """Create a waterfall chart to explain how order revenue turns into net profit."""
    figure = go.Figure(
        go.Waterfall(
            name="Profitability",
            orientation="v",
            measure=["relative", "relative", "relative", "relative", "total"],
            x=[
                "Revenue",
                "Product + Shipping + Fulfillment + Packaging",
                "Warehouse + Platform",
                "Team + Marketing",
                "Net Profit",
            ],
            y=[
                results.revenue,
                -results.total_variable_cost,
                -inputs.fixed_costs,
                -(inputs.operating_expenses + inputs.marketing_spend),
                0,
            ],
            connector={"line": {"color": "#8c8c8c"}},
            increasing={"marker": {"color": "#1f77b4"}},
            decreasing={"marker": {"color": "#d62728"}},
            totals={"marker": {"color": "#2ca02c" if results.net_profit >= 0 else "#d62728"}},
        )
    )
    figure.update_layout(
        title="Profit Breakdown",
        yaxis_title="Amount ($)",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def create_break_even_chart(
    inputs: ProfitabilityInputs, results: ProfitabilityResults
) -> go.Figure:
    """Create a visualization comparing current volume to break-even volume."""
    max_units = max(
        inputs.units_sold * 1.3,
        (results.break_even_units or 0) * 1.2,
        1.0,
    )
    units_range = [0, max_units]
    revenue_line = [unit * inputs.price_per_unit for unit in units_range]
    cost_line = [
        unit * inputs.variable_cost_per_unit
        + inputs.fixed_costs
        + inputs.operating_expenses
        + inputs.marketing_spend
        for unit in units_range
    ]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=units_range,
            y=revenue_line,
            mode="lines",
            name="Revenue",
            line=dict(color="#1f77b4", width=3),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=units_range,
            y=cost_line,
            mode="lines",
            name="Total Cost",
            line=dict(color="#d62728", width=3),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[inputs.units_sold],
            y=[results.revenue],
            mode="markers",
            name="Current Sales Volume",
            marker=dict(color="#2ca02c", size=12),
        )
    )

    if results.break_even_units is not None and results.break_even_revenue is not None:
        figure.add_vline(
            x=results.break_even_units,
            line_dash="dash",
            line_color="#ff7f0e",
            annotation_text=f"Break-even: {results.break_even_units:,.0f} units",
        )
        figure.add_trace(
            go.Scatter(
                x=[results.break_even_units],
                y=[results.break_even_revenue],
                mode="markers",
                name="Break-even Point",
                marker=dict(color="#ff7f0e", size=12, symbol="diamond"),
            )
        )

    figure.update_layout(
        title="Break-even Visualization",
        xaxis_title="Units",
        yaxis_title="Amount ($)",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def render_profitability_details(results: ProfitabilityResults) -> None:
    """Render the full calculation set in a compact table for quick review."""
    detail_rows = pd.DataFrame(
        [
            ("Revenue", format_currency(results.revenue)),
            ("Variable Cost per Unit", format_currency(results.total_variable_cost_per_unit)),
            ("Total Variable Cost", format_currency(results.total_variable_cost)),
            ("Gross Profit", format_currency(results.gross_profit)),
            ("Gross Margin", format_percent(results.gross_margin)),
            ("Total Cost", format_currency(results.total_cost)),
            ("Net Profit", format_currency(results.net_profit)),
            ("Net Margin", format_percent(results.net_margin)),
            (
                "Break-even Units",
                (
                    f"{results.break_even_units:,.0f}"
                    if results.break_even_units is not None
                    else "N/A"
                ),
            ),
            ("Break-even Revenue", format_currency(results.break_even_revenue)),
        ],
        columns=["Metric", "Value"],
    )
    st.dataframe(
        detail_rows,
        use_container_width=True,
        hide_index=True,
    )


def render_cost_structure_breakdown(inputs: ProfitabilityInputs) -> None:
    """Render the e-commerce cost structure as a compact component table."""
    breakdown_rows = pd.DataFrame(
        [
            ("Product Cost / Unit", format_currency(inputs.product_cost_per_unit)),
            ("Shipping Cost / Unit", format_currency(inputs.shipping_cost_per_unit)),
            ("Fulfillment Cost / Unit", format_currency(inputs.fulfillment_cost_per_unit)),
            ("Packaging Cost / Unit", format_currency(inputs.packaging_cost_per_unit)),
            ("Total Variable Cost / Unit", format_currency(inputs.variable_cost_per_unit)),
        ],
        columns=["Cost Component", "Amount"],
    )
    st.dataframe(breakdown_rows, use_container_width=True, hide_index=True)


def render_break_even_summary(results: ProfitabilityResults) -> None:
    """Render a compact summary of break-even outputs."""
    render_metric_row(
        [
            {
                "label": "Break-even Units",
                "value": (
                    f"{results.break_even_units:,.0f}"
                    if results.break_even_units is not None
                    else "N/A"
                ),
            },
            {
                "label": "Break-even Revenue",
                "value": format_currency(results.break_even_revenue),
            },
        ]
    )


def render_input_warning(error_message: str) -> None:
    """Render a consistent validation warning."""
    st.error(error_message)


def _validate_inputs(inputs: ProfitabilityInputs) -> None:
    """Guard against invalid negative input values."""
    for field_name, value in inputs.__dict__.items():
        if value < 0:
            raise ValueError(f"{field_name.replace('_', ' ').title()} cannot be negative.")


def _normalize_profitability_state(state_values: dict[str, float | int]) -> dict[str, float | int]:
    """Map legacy blended variable-cost state into the new decomposed cost structure."""
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
