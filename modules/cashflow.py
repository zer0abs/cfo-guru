"""Cash flow forecasting logic and UI helpers."""

from dataclasses import asdict, dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.page_sections import render_metric_row
from modules.forecasting import DemandForecastResult
from modules.profitability import get_default_inputs as get_default_profitability_inputs
from utils.formatting import format_currency
from utils.state import (
    CASHFLOW_SECTION,
    PROFITABILITY_SECTION,
    get_business_inputs,
    merge_with_default_baseline,
    update_business_inputs,
)

LOW_COVERAGE_MONTHS_THRESHOLD = 1.0
CRITICAL_COVERAGE_MONTHS_THRESHOLD = 0.5
EXCESS_COVERAGE_MONTHS_THRESHOLD = 3.0
HIGH_EXCESS_COVERAGE_MONTHS_THRESHOLD = 4.5
HIGH_FILL_RATE_THRESHOLD = 0.98
MODERATE_FILL_RATE_THRESHOLD = 0.92
HIGH_INVENTORY_STRESS_SCORE = 70
MODERATE_INVENTORY_STRESS_SCORE = 40
HIGH_OVERSTOCK_SCORE = 70
MODERATE_OVERSTOCK_SCORE = 40


@dataclass(frozen=True)
class CashFlowInputs:
    """User assumptions for the cash forecast model."""

    starting_cash: float
    forecast_horizon_months: int
    monthly_revenue: float
    monthly_collections: float
    payroll: float
    rent: float
    loan_payments: float
    operating_expenses: float
    miscellaneous_expenses: float
    marketing_spend: float
    monthly_units_sold: float
    product_cost_per_unit: float
    shipping_cost_per_unit: float
    fulfillment_cost_per_unit: float
    packaging_cost_per_unit: float
    beginning_inventory_units: float
    reorder_point_units: float
    target_inventory_units: float
    supplier_lead_time_months: int
    reorder_quantity_units: float
    safety_stock_units: float
    seasonality_multiplier: float = 1.0

    @property
    def fulfillment_cost_per_unit_total(self) -> float:
        """Return the cost incurred at the time of sale."""
        return (
            self.shipping_cost_per_unit
            + self.fulfillment_cost_per_unit
            + self.packaging_cost_per_unit
        )

    @property
    def total_variable_cost_per_unit(self) -> float:
        """Return the full unit cost stack across purchase and sale timing."""
        return self.product_cost_per_unit + self.fulfillment_cost_per_unit_total


@dataclass(frozen=True)
class CashFlowResults:
    """Structured results from the monthly cash flow forecast."""

    forecast_table: pd.DataFrame
    ending_cash: float
    first_negative_month: str | None
    runway_months: float | None
    monthly_inventory_purchase_outflow: float
    monthly_fulfillment_outflow: float
    monthly_variable_cost_outflow: float
    monthly_fixed_cost_outflow: float
    monthly_total_outflow: float
    monthly_product_cost_outflow: float
    monthly_shipping_cost_outflow: float
    monthly_fulfillment_cost_outflow: float
    monthly_packaging_cost_outflow: float
    effective_units_sold: float
    average_inventory_purchased_units: float
    ending_inventory_units: float
    average_inventory_coverage_months: float
    stockout_month_count: int
    low_coverage_month_count: int
    lost_sales_units: float
    lost_revenue: float
    lost_gross_profit: float
    average_fill_rate: float
    inventory_stress_score: int
    inventory_risk_level: str
    excess_coverage_months: float
    excess_coverage_flag: bool
    overstock_flag: bool
    overstock_month_count: int
    excess_inventory_units: float
    excess_inventory_value: float
    cash_tied_in_excess_inventory: float
    average_excess_coverage_months: float
    inventory_overstock_score: int
    inventory_balance_label: str
    demand_source: str
    forecast_method: str | None
    forecast_trend_direction: str | None


def get_default_inputs() -> CashFlowInputs:
    """Return e-commerce demo defaults so the forecast is usable immediately."""
    profitability_defaults = get_default_profitability_inputs()
    return CashFlowInputs(
        starting_cash=125000.0,
        forecast_horizon_months=12,
        monthly_revenue=(
            profitability_defaults.price_per_unit * profitability_defaults.units_sold
        ),
        monthly_collections=114000.0,
        payroll=32000.0,
        rent=9000.0,
        loan_payments=4500.0,
        operating_expenses=24000.0,
        miscellaneous_expenses=6000.0,
        marketing_spend=profitability_defaults.marketing_spend,
        monthly_units_sold=profitability_defaults.units_sold,
        product_cost_per_unit=profitability_defaults.product_cost_per_unit,
        shipping_cost_per_unit=profitability_defaults.shipping_cost_per_unit,
        fulfillment_cost_per_unit=profitability_defaults.fulfillment_cost_per_unit,
        packaging_cost_per_unit=profitability_defaults.packaging_cost_per_unit,
        beginning_inventory_units=4200.0,
        reorder_point_units=1800.0,
        target_inventory_units=4200.0,
        supplier_lead_time_months=1,
        reorder_quantity_units=0.0,
        safety_stock_units=600.0,
        seasonality_multiplier=1.0,
    )


def render_sidebar_inputs() -> CashFlowInputs:
    """Collect e-commerce cash forecasting assumptions from the sidebar."""
    default_values = asdict(get_default_inputs())
    resolved_cashflow_defaults, _ = merge_with_default_baseline(
        _normalize_cashflow_state(get_business_inputs(CASHFLOW_SECTION)),
        default_values,
    )
    profitability_defaults, using_live_unit_economics = _resolve_profitability_defaults()

    with st.sidebar:
        st.subheader("Cash Flow Forecast")
        st.caption(
            "Demo model: an e-commerce brand managing collections, inventory buys, and fulfillment cash timing."
        )

        inputs = CashFlowInputs(
            starting_cash=st.number_input(
                "Starting cash",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["starting_cash"]),
                step=1000.0,
                key="cashflow_starting_cash",
            ),
            forecast_horizon_months=st.number_input(
                "Forecast horizon in months",
                min_value=1,
                max_value=36,
                value=int(resolved_cashflow_defaults["forecast_horizon_months"]),
                step=1,
                key="cashflow_forecast_horizon_months",
            ),
            monthly_revenue=st.number_input(
                "Monthly gross sales",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["monthly_revenue"]),
                step=1000.0,
                key="cashflow_monthly_revenue",
            ),
            monthly_collections=st.number_input(
                "Monthly cash collected",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["monthly_collections"]),
                step=1000.0,
                key="cashflow_monthly_collections",
            ),
            payroll=st.number_input(
                "Team payroll",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["payroll"]),
                step=500.0,
                key="cashflow_payroll",
            ),
            rent=st.number_input(
                "Warehouse and office rent",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["rent"]),
                step=500.0,
                key="cashflow_rent",
            ),
            loan_payments=st.number_input(
                "Loan payments",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["loan_payments"]),
                step=250.0,
                key="cashflow_loan_payments",
            ),
            operating_expenses=st.number_input(
                "Software and operating expenses",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["operating_expenses"]),
                step=500.0,
                key="cashflow_operating_expenses",
            ),
            miscellaneous_expenses=st.number_input(
                "Refunds and miscellaneous expenses",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["miscellaneous_expenses"]),
                step=250.0,
                key="cashflow_miscellaneous_expenses",
            ),
            marketing_spend=float(profitability_defaults["marketing_spend"]),
            monthly_units_sold=float(profitability_defaults["monthly_units_sold"]),
            product_cost_per_unit=float(profitability_defaults["product_cost_per_unit"]),
            shipping_cost_per_unit=float(profitability_defaults["shipping_cost_per_unit"]),
            fulfillment_cost_per_unit=float(profitability_defaults["fulfillment_cost_per_unit"]),
            packaging_cost_per_unit=float(profitability_defaults["packaging_cost_per_unit"]),
            beginning_inventory_units=0.0,
            reorder_point_units=0.0,
            target_inventory_units=0.0,
            supplier_lead_time_months=0,
            reorder_quantity_units=0.0,
            safety_stock_units=0.0,
            seasonality_multiplier=st.number_input(
                "Seasonality multiplier",
                min_value=0.1,
                max_value=3.0,
                value=float(resolved_cashflow_defaults["seasonality_multiplier"]),
                step=0.05,
                help="Applies a simple multiplier to demand, gross sales, and collections.",
                key="cashflow_seasonality_multiplier",
            ),
        )

        st.markdown("**Inventory Timing**")
        inputs = CashFlowInputs(
            starting_cash=inputs.starting_cash,
            forecast_horizon_months=inputs.forecast_horizon_months,
            monthly_revenue=inputs.monthly_revenue,
            monthly_collections=inputs.monthly_collections,
            payroll=inputs.payroll,
            rent=inputs.rent,
            loan_payments=inputs.loan_payments,
            operating_expenses=inputs.operating_expenses,
            miscellaneous_expenses=inputs.miscellaneous_expenses,
            marketing_spend=inputs.marketing_spend,
            monthly_units_sold=inputs.monthly_units_sold,
            product_cost_per_unit=inputs.product_cost_per_unit,
            shipping_cost_per_unit=inputs.shipping_cost_per_unit,
            fulfillment_cost_per_unit=inputs.fulfillment_cost_per_unit,
            packaging_cost_per_unit=inputs.packaging_cost_per_unit,
            beginning_inventory_units=st.number_input(
                "Beginning inventory units",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["beginning_inventory_units"]),
                step=100.0,
                key="cashflow_beginning_inventory_units",
            ),
            reorder_point_units=st.number_input(
                "Reorder point units",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["reorder_point_units"]),
                step=100.0,
                key="cashflow_reorder_point_units",
            ),
            target_inventory_units=st.number_input(
                "Target inventory units",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["target_inventory_units"]),
                step=100.0,
                key="cashflow_target_inventory_units",
            ),
            supplier_lead_time_months=st.number_input(
                "Supplier lead time (months)",
                min_value=0,
                max_value=12,
                value=int(resolved_cashflow_defaults["supplier_lead_time_months"]),
                step=1,
                key="cashflow_supplier_lead_time_months",
            ),
            reorder_quantity_units=st.number_input(
                "Fixed reorder quantity",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["reorder_quantity_units"]),
                step=100.0,
                help="Set to 0 to replenish back toward target inventory automatically.",
                key="cashflow_reorder_quantity_units",
            ),
            safety_stock_units=st.number_input(
                "Safety stock units",
                min_value=0.0,
                value=float(resolved_cashflow_defaults["safety_stock_units"]),
                step=100.0,
                key="cashflow_safety_stock_units",
            ),
            seasonality_multiplier=inputs.seasonality_multiplier,
        )
        source_label = (
            "Live Financial Health inputs"
            if using_live_unit_economics
            else "Default demo unit economics"
        )
        st.caption(
            f"Using {source_label}: {inputs.monthly_units_sold:,.0f} monthly units, "
            f"{format_currency(inputs.product_cost_per_unit)} product cost at purchase, "
            f"{format_currency(inputs.fulfillment_cost_per_unit_total)} fulfillment cost at sale."
        )

    update_business_inputs(CASHFLOW_SECTION, asdict(inputs))
    return inputs


def calculate_cash_flow_forecast(
    inputs: CashFlowInputs,
    demand_plan_units: list[float] | None = None,
    demand_forecast: DemandForecastResult | None = None,
) -> CashFlowResults:
    """Build a month-by-month cash balance forecast with simple inventory timing.

    MVP assumption:
    Product-cost cash is recognized when a purchase order is placed.
    Inventory is received after `supplier_lead_time_months`.
    Shipping, fulfillment, and packaging costs are recognized in the month of sale.
    """
    _validate_inputs(inputs)

    manual_revenue = inputs.monthly_revenue * inputs.seasonality_multiplier
    manual_collections = inputs.monthly_collections * inputs.seasonality_multiplier
    manual_units_sold = inputs.monthly_units_sold * inputs.seasonality_multiplier
    fixed_cost_outflow = (
        inputs.payroll
        + inputs.rent
        + inputs.loan_payments
        + inputs.operating_expenses
        + inputs.miscellaneous_expenses
        + inputs.marketing_spend
    )

    inventory_on_hand = inputs.beginning_inventory_units
    receipt_schedule: dict[int, float] = {}
    monthly_rows: list[dict[str, float | str | bool]] = []
    beginning_cash = inputs.starting_cash

    for month_index in range(1, inputs.forecast_horizon_months + 1):
        month_label = f"Month {month_index}"
        planned_units_sold = (
            float(demand_plan_units[month_index - 1])
            if demand_plan_units and month_index - 1 < len(demand_plan_units)
            else manual_units_sold
        )
        demand_scaler = (
            planned_units_sold / manual_units_sold if manual_units_sold > 0 else 1.0
        )
        planned_revenue = manual_revenue * demand_scaler
        planned_collections = manual_collections * demand_scaler
        beginning_inventory = inventory_on_hand
        units_received = receipt_schedule.pop(month_index, 0.0)
        inventory_available = beginning_inventory + units_received

        units_sold = min(planned_units_sold, inventory_available)
        sales_fill_rate = units_sold / planned_units_sold if planned_units_sold > 0 else 1.0
        realized_revenue = planned_revenue * sales_fill_rate
        realized_collections = planned_collections * sales_fill_rate
        lost_sales_units = max(0.0, planned_units_sold - units_sold)
        lost_revenue = planned_revenue - realized_revenue
        lost_gross_profit = lost_sales_units * max(
            0.0,
            inputs.monthly_revenue / max(inputs.monthly_units_sold, 1.0)
            - inputs.total_variable_cost_per_unit,
        )

        ending_inventory_before_replenishment = inventory_available - units_sold
        reorder_triggered = (
            ending_inventory_before_replenishment <= inputs.reorder_point_units
        )
        inventory_units_ordered = (
            _determine_reorder_quantity(
                inputs,
                ending_inventory_before_replenishment,
            )
            if reorder_triggered
            else 0.0
        )
        inventory_purchase_cash_outflow = (
            inventory_units_ordered * inputs.product_cost_per_unit
        )

        immediate_receipt_units = 0.0
        if inventory_units_ordered > 0:
            arrival_month = month_index + max(inputs.supplier_lead_time_months, 0)
            if inputs.supplier_lead_time_months == 0:
                immediate_receipt_units = inventory_units_ordered
            else:
                receipt_schedule[arrival_month] = (
                    receipt_schedule.get(arrival_month, 0.0) + inventory_units_ordered
                )

        ending_inventory_after_receipts = (
            ending_inventory_before_replenishment + immediate_receipt_units
        )
        inventory_on_hand = ending_inventory_after_receipts

        shipping_cost_outflow = units_sold * inputs.shipping_cost_per_unit
        fulfillment_cost_outflow = units_sold * inputs.fulfillment_cost_per_unit
        packaging_cost_outflow = units_sold * inputs.packaging_cost_per_unit
        fulfillment_cash_outflow = (
            shipping_cost_outflow
            + fulfillment_cost_outflow
            + packaging_cost_outflow
        )
        variable_cost_outflow = (
            inventory_purchase_cash_outflow + fulfillment_cash_outflow
        )
        total_cash_outflow = variable_cost_outflow + fixed_cost_outflow
        net_cash_flow = realized_collections - total_cash_outflow
        ending_cash = beginning_cash + net_cash_flow
        inventory_coverage = (
            ending_inventory_after_receipts / planned_units_sold
            if planned_units_sold > 0
            else None
        )
        excess_coverage_months = (
            max(0.0, inventory_coverage - EXCESS_COVERAGE_MONTHS_THRESHOLD)
            if inventory_coverage is not None
            else 0.0
        )
        excess_inventory_units = (
            max(
                0.0,
                ending_inventory_after_receipts
                - (planned_units_sold * EXCESS_COVERAGE_MONTHS_THRESHOLD),
            )
            if planned_units_sold > 0
            else 0.0
        )
        excess_inventory_value = excess_inventory_units * inputs.product_cost_per_unit
        stockout_flag = lost_sales_units > 0
        low_coverage_flag = (
            inventory_coverage is not None
            and inventory_coverage < LOW_COVERAGE_MONTHS_THRESHOLD
        )
        excess_coverage_flag = (
            inventory_coverage is not None
            and inventory_coverage > EXCESS_COVERAGE_MONTHS_THRESHOLD
        )
        overstock_flag = (
            inventory_coverage is not None
            and inventory_coverage > HIGH_EXCESS_COVERAGE_MONTHS_THRESHOLD
        )
        stockout_severity = _classify_stockout_severity(sales_fill_rate, stockout_flag)

        monthly_rows.append(
            {
                "Month": month_label,
                "Beginning Cash": beginning_cash,
                "Planned Units Sold": planned_units_sold,
                "Units Sold": units_sold,
                "Sales Fill Rate": sales_fill_rate,
                "Gross Sales": realized_revenue,
                "Cash Collected": realized_collections,
                "Beginning Inventory": beginning_inventory,
                "Units Received": units_received,
                "Inventory Available": inventory_available,
                "Ending Inventory Before Replenishment": ending_inventory_before_replenishment,
                "Reorder Triggered": reorder_triggered,
                "Inventory Units Ordered": inventory_units_ordered,
                "Inventory Purchase Cash Outflow": inventory_purchase_cash_outflow,
                "Ending Inventory": ending_inventory_after_receipts,
                "Inventory Coverage": inventory_coverage,
                "Stockout Flag": stockout_flag,
                "Stockout Severity": stockout_severity,
                "Low Coverage Flag": low_coverage_flag,
                "Excess Coverage Flag": excess_coverage_flag,
                "Overstock Flag": overstock_flag,
                "Excess Coverage Months": excess_coverage_months,
                "Excess Inventory Units": excess_inventory_units,
                "Excess Inventory Value": excess_inventory_value,
                "Lost Sales Units": lost_sales_units,
                "Lost Revenue": lost_revenue,
                "Lost Gross Profit": lost_gross_profit,
                "Shipping Cost": shipping_cost_outflow,
                "Fulfillment Cost": fulfillment_cost_outflow,
                "Packaging Cost": packaging_cost_outflow,
                "Fulfillment Cash Outflow": fulfillment_cash_outflow,
                "Paid Acquisition": inputs.marketing_spend,
                "Team Payroll": inputs.payroll,
                "Rent": inputs.rent,
                "Loan Payments": inputs.loan_payments,
                "Operating Expenses": inputs.operating_expenses,
                "Refunds + Misc": inputs.miscellaneous_expenses,
                "Fixed Cash Outflow": fixed_cost_outflow,
                "Variable Cost Outflow": variable_cost_outflow,
                "Total Cash Outflow": total_cash_outflow,
                "Net Cash Flow": net_cash_flow,
                "Ending Cash": ending_cash,
            }
        )
        beginning_cash = ending_cash

    forecast_table = pd.DataFrame(monthly_rows)
    negative_cash_rows = forecast_table[forecast_table["Ending Cash"] < 0]
    first_negative_month = (
        str(negative_cash_rows.iloc[0]["Month"]) if not negative_cash_rows.empty else None
    )
    average_collections = float(forecast_table["Cash Collected"].mean())
    average_total_outflow = float(forecast_table["Total Cash Outflow"].mean())
    runway_months = _calculate_runway_months(
        inputs.starting_cash,
        average_collections,
        average_total_outflow,
    )
    average_inventory_coverage_months = float(forecast_table["Inventory Coverage"].mean())
    stockout_month_count = int(forecast_table["Stockout Flag"].sum())
    low_coverage_month_count = int(forecast_table["Low Coverage Flag"].sum())
    overstock_month_count = int(forecast_table["Overstock Flag"].sum())
    lost_sales_units = float(forecast_table["Lost Sales Units"].sum())
    lost_revenue = float(forecast_table["Lost Revenue"].sum())
    lost_gross_profit = float(forecast_table["Lost Gross Profit"].sum())
    average_fill_rate = float(forecast_table["Sales Fill Rate"].mean())
    inventory_stress_score = _calculate_inventory_stress_score(
        average_inventory_coverage_months=average_inventory_coverage_months,
        average_fill_rate=average_fill_rate,
        stockout_month_count=stockout_month_count,
        low_coverage_month_count=low_coverage_month_count,
        inputs=inputs,
    )
    inventory_risk_level = _classify_inventory_risk_level(inventory_stress_score)
    average_excess_coverage_months = float(forecast_table["Excess Coverage Months"].mean())
    excess_inventory_units = float(forecast_table["Excess Inventory Units"].mean())
    excess_inventory_value = float(forecast_table["Excess Inventory Value"].mean())
    inventory_overstock_score = _calculate_inventory_overstock_score(
        average_inventory_coverage_months=average_inventory_coverage_months,
        average_excess_coverage_months=average_excess_coverage_months,
        overstock_month_count=overstock_month_count,
        average_fill_rate=average_fill_rate,
        inputs=inputs,
    )
    inventory_balance_label = _classify_inventory_balance(
        inventory_stress_score=inventory_stress_score,
        inventory_overstock_score=inventory_overstock_score,
    )

    return CashFlowResults(
        forecast_table=forecast_table,
        ending_cash=float(forecast_table.iloc[-1]["Ending Cash"]),
        first_negative_month=first_negative_month,
        runway_months=runway_months,
        monthly_inventory_purchase_outflow=float(
            forecast_table["Inventory Purchase Cash Outflow"].mean()
        ),
        monthly_fulfillment_outflow=float(
            forecast_table["Fulfillment Cash Outflow"].mean()
        ),
        monthly_variable_cost_outflow=float(
            forecast_table["Variable Cost Outflow"].mean()
        ),
        monthly_fixed_cost_outflow=float(forecast_table["Fixed Cash Outflow"].mean()),
        monthly_total_outflow=average_total_outflow,
        monthly_product_cost_outflow=float(
            forecast_table["Inventory Purchase Cash Outflow"].mean()
        ),
        monthly_shipping_cost_outflow=float(forecast_table["Shipping Cost"].mean()),
        monthly_fulfillment_cost_outflow=float(
            forecast_table["Fulfillment Cost"].mean()
        ),
        monthly_packaging_cost_outflow=float(forecast_table["Packaging Cost"].mean()),
        effective_units_sold=float(forecast_table["Units Sold"].mean()),
        average_inventory_purchased_units=float(
            forecast_table["Inventory Units Ordered"].mean()
        ),
        ending_inventory_units=float(forecast_table.iloc[-1]["Ending Inventory"]),
        average_inventory_coverage_months=average_inventory_coverage_months,
        stockout_month_count=stockout_month_count,
        low_coverage_month_count=low_coverage_month_count,
        lost_sales_units=lost_sales_units,
        lost_revenue=lost_revenue,
        lost_gross_profit=lost_gross_profit,
        average_fill_rate=average_fill_rate,
        inventory_stress_score=inventory_stress_score,
        inventory_risk_level=inventory_risk_level,
        excess_coverage_months=float(
            forecast_table.iloc[-1]["Excess Coverage Months"]
        ),
        excess_coverage_flag=bool(forecast_table.iloc[-1]["Excess Coverage Flag"]),
        overstock_flag=bool(forecast_table.iloc[-1]["Overstock Flag"]),
        overstock_month_count=overstock_month_count,
        excess_inventory_units=excess_inventory_units,
        excess_inventory_value=excess_inventory_value,
        cash_tied_in_excess_inventory=excess_inventory_value,
        average_excess_coverage_months=average_excess_coverage_months,
        inventory_overstock_score=inventory_overstock_score,
        inventory_balance_label=inventory_balance_label,
        demand_source=(
            demand_forecast.source_label
            if demand_forecast is not None and demand_forecast.use_forecast
            else "Manual demand baseline"
        ),
        forecast_method=(
            demand_forecast.method if demand_forecast is not None and demand_forecast.use_forecast else None
        ),
        forecast_trend_direction=(
            demand_forecast.trend_direction
            if demand_forecast is not None and demand_forecast.use_forecast
            else None
        ),
    )


def render_cashflow_metrics(results: CashFlowResults) -> None:
    """Render top-level metrics for the cash forecast."""
    render_metric_row(
        [
            {"label": "Ending Cash", "value": format_currency(results.ending_cash)},
            {
                "label": "Inventory Buy / Mo",
                "value": format_currency(results.monthly_inventory_purchase_outflow),
            },
            {
                "label": "Fulfillment / Mo",
                "value": format_currency(results.monthly_fulfillment_outflow),
            },
            {
                "label": "Runway",
                "value": (
                    f"{results.runway_months:.1f} months"
                    if results.runway_months is not None
                    else "Stable / N/A"
                ),
            },
            {
                "label": "First Negative Month",
                "value": results.first_negative_month or "None",
            },
        ],
        columns_per_row=3,
    )


def create_cash_balance_chart(results: CashFlowResults) -> go.Figure:
    """Create a line chart for monthly ending cash balances."""
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=results.forecast_table["Month"],
            y=results.forecast_table["Ending Cash"],
            mode="lines+markers",
            name="Ending Cash",
            line=dict(color="#1f77b4", width=3),
            marker=dict(size=8),
        )
    )
    figure.add_hline(y=0, line_dash="dash", line_color="#d62728")
    figure.update_layout(
        title="Cash Balance Forecast",
        xaxis_title="Month",
        yaxis_title="Cash Balance ($)",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def render_forecast_table(results: CashFlowResults) -> None:
    """Render the monthly forecast as a pandas DataFrame."""
    formatted_table = results.forecast_table.copy()
    currency_columns = [
        "Beginning Cash",
        "Gross Sales",
        "Cash Collected",
        "Inventory Purchase Cash Outflow",
        "Lost Revenue",
        "Lost Gross Profit",
        "Shipping Cost",
        "Fulfillment Cost",
        "Packaging Cost",
        "Fulfillment Cash Outflow",
        "Paid Acquisition",
        "Team Payroll",
        "Rent",
        "Loan Payments",
        "Operating Expenses",
        "Refunds + Misc",
        "Fixed Cash Outflow",
        "Variable Cost Outflow",
        "Total Cash Outflow",
        "Net Cash Flow",
        "Ending Cash",
    ]
    numeric_columns = [
        "Planned Units Sold",
        "Units Sold",
        "Beginning Inventory",
        "Units Received",
        "Inventory Available",
        "Ending Inventory Before Replenishment",
        "Inventory Units Ordered",
        "Ending Inventory",
        "Lost Sales Units",
        "Excess Inventory Units",
    ]

    for column in currency_columns:
        formatted_table[column] = formatted_table[column].map(format_currency)
    for column in numeric_columns:
        formatted_table[column] = formatted_table[column].map(lambda value: f"{float(value):,.0f}")
    formatted_table["Sales Fill Rate"] = formatted_table["Sales Fill Rate"].map(
        lambda value: f"{float(value) * 100:.1f}%"
    )
    formatted_table["Inventory Coverage"] = formatted_table["Inventory Coverage"].map(
        lambda value: f"{float(value):.1f} mo" if value is not None else "N/A"
    )
    formatted_table["Reorder Triggered"] = formatted_table["Reorder Triggered"].map(
        lambda value: "Yes" if value else "No"
    )
    formatted_table["Stockout Flag"] = formatted_table["Stockout Flag"].map(
        lambda value: "Yes" if value else "No"
    )
    formatted_table["Low Coverage Flag"] = formatted_table["Low Coverage Flag"].map(
        lambda value: "Yes" if value else "No"
    )
    formatted_table["Excess Coverage Flag"] = formatted_table["Excess Coverage Flag"].map(
        lambda value: "Yes" if value else "No"
    )
    formatted_table["Overstock Flag"] = formatted_table["Overstock Flag"].map(
        lambda value: "Yes" if value else "No"
    )
    formatted_table["Excess Coverage Months"] = formatted_table[
        "Excess Coverage Months"
    ].map(lambda value: f"{float(value):.1f} mo")

    st.dataframe(formatted_table, use_container_width=True, hide_index=True)


def render_cash_outflow_breakdown(results: CashFlowResults) -> None:
    """Render a compact breakdown of monthly cash drivers."""
    breakdown_rows = pd.DataFrame(
        [
            (
                "Inventory Purchase Outflow",
                format_currency(results.monthly_inventory_purchase_outflow),
            ),
            (
                "Fulfillment-at-Sale Outflow",
                format_currency(results.monthly_fulfillment_outflow),
            ),
            ("Shipping Cost Outflow", format_currency(results.monthly_shipping_cost_outflow)),
            (
                "Fulfillment Labor / 3PL Outflow",
                format_currency(results.monthly_fulfillment_cost_outflow),
            ),
            ("Packaging Outflow", format_currency(results.monthly_packaging_cost_outflow)),
            ("Fixed Cash Outflow", format_currency(results.monthly_fixed_cost_outflow)),
            (
                "Cash Tied in Excess Inventory",
                format_currency(results.cash_tied_in_excess_inventory),
            ),
            ("Total Cash Outflow", format_currency(results.monthly_total_outflow)),
        ],
        columns=["Monthly Cash Driver", "Amount"],
    )
    st.dataframe(breakdown_rows, use_container_width=True, hide_index=True)


def render_inventory_risk_summary(results: CashFlowResults) -> None:
    """Render key inventory risk signals from the current forecast."""
    render_metric_row(
        [
            {
                "label": "Inventory Posture",
                "value": results.inventory_balance_label,
            },
            {
                "label": "Coverage",
                "value": f"{results.average_inventory_coverage_months:.1f} mo",
            },
            {
                "label": "Fill Rate",
                "value": f"{results.average_fill_rate * 100:.1f}%",
            },
            {
                "label": "Lost Sales Units",
                "value": f"{results.lost_sales_units:,.0f}",
            },
            {
                "label": "Lost Revenue",
                "value": format_currency(results.lost_revenue),
            },
            {
                "label": "Stress Score",
                "value": f"{results.inventory_stress_score}/100",
            },
            {
                "label": "Excess Value",
                "value": format_currency(results.excess_inventory_value),
            },
            {
                "label": "Overstock Score",
                "value": f"{results.inventory_overstock_score}/100",
            },
        ],
        columns_per_row=3,
    )


def render_inventory_policy_summary(
    inputs: CashFlowInputs, results: CashFlowResults
) -> None:
    """Render the current inventory policy and average activity."""
    render_metric_row(
        [
            {
                "label": "Beginning Inventory",
                "value": f"{inputs.beginning_inventory_units:,.0f} units",
            },
            {
                "label": "Reorder Point",
                "value": f"{inputs.reorder_point_units:,.0f} units",
            },
            {
                "label": "Target Inventory",
                "value": f"{inputs.target_inventory_units:,.0f} units",
            },
            {
                "label": "Lead Time",
                "value": f"{inputs.supplier_lead_time_months} mo",
            },
            {
                "label": "Avg Units Ordered / Mo",
                "value": f"{results.average_inventory_purchased_units:,.0f}",
            },
            {
                "label": "Ending Inventory",
                "value": f"{results.ending_inventory_units:,.0f} units",
            },
        ],
        columns_per_row=3,
    )


def render_cash_alert(results: CashFlowResults) -> None:
    """Render a warning when the forecast dips below zero."""
    if results.first_negative_month:
        st.error(
            f"Cash turns negative in {results.first_negative_month}. Review inventory buys, ad efficiency, and operating spend."
        )
    else:
        st.success("Cash remains non-negative throughout the forecast horizon.")
    if results.stockout_month_count > 0:
        st.warning(
            f"Inventory constraints create stockouts in {results.stockout_month_count} forecast month(s), with estimated lost revenue of {format_currency(results.lost_revenue)}."
        )
    elif results.low_coverage_month_count > 0:
        st.info(
            f"Inventory coverage is tight in {results.low_coverage_month_count} month(s). Consider reviewing reorder point or safety stock before demand spikes."
        )
    if results.overstock_month_count > 0:
        st.warning(
            f"Inventory coverage is excessive in {results.overstock_month_count} forecast month(s), with about {format_currency(results.cash_tied_in_excess_inventory)} tied up above target coverage."
        )


def _determine_reorder_quantity(
    inputs: CashFlowInputs,
    ending_inventory_before_replenishment: float,
) -> float:
    """Return the reorder quantity for the current month.

    When a fixed reorder quantity is not provided, the model replenishes toward
    target inventory plus safety stock. This keeps the logic explainable and
    avoids introducing a more complex planning engine.
    """
    if inputs.reorder_quantity_units > 0:
        return inputs.reorder_quantity_units

    target_inventory = inputs.target_inventory_units + inputs.safety_stock_units
    return max(0.0, target_inventory - ending_inventory_before_replenishment)


def _calculate_inventory_stress_score(
    average_inventory_coverage_months: float,
    average_fill_rate: float,
    stockout_month_count: int,
    low_coverage_month_count: int,
    inputs: CashFlowInputs,
) -> int:
    """Build a simple deterministic inventory stress score from 0 to 100."""
    score = 0.0

    if average_inventory_coverage_months < CRITICAL_COVERAGE_MONTHS_THRESHOLD:
        score += 35
    elif average_inventory_coverage_months < LOW_COVERAGE_MONTHS_THRESHOLD:
        score += 20

    if average_fill_rate < MODERATE_FILL_RATE_THRESHOLD:
        score += 30
    elif average_fill_rate < HIGH_FILL_RATE_THRESHOLD:
        score += 15

    score += min(stockout_month_count * 12, 24)
    score += min(low_coverage_month_count * 4, 16)

    demand_during_lead_time = inputs.monthly_units_sold * max(inputs.supplier_lead_time_months, 1)
    recommended_reorder_floor = demand_during_lead_time + inputs.safety_stock_units
    if inputs.reorder_point_units < recommended_reorder_floor:
        score += 10

    target_inventory_floor = (
        inputs.monthly_units_sold * (inputs.supplier_lead_time_months + 1)
        + inputs.safety_stock_units
    )
    if inputs.target_inventory_units < target_inventory_floor:
        score += 10

    return int(min(round(score), 100))


def _calculate_inventory_overstock_score(
    average_inventory_coverage_months: float,
    average_excess_coverage_months: float,
    overstock_month_count: int,
    average_fill_rate: float,
    inputs: CashFlowInputs,
) -> int:
    """Build a deterministic overstock score from 0 to 100."""
    score = 0.0

    if average_inventory_coverage_months > HIGH_EXCESS_COVERAGE_MONTHS_THRESHOLD:
        score += 35
    elif average_inventory_coverage_months > EXCESS_COVERAGE_MONTHS_THRESHOLD:
        score += 20

    score += min(average_excess_coverage_months * 10, 20)
    score += min(overstock_month_count * 8, 24)

    if average_fill_rate >= HIGH_FILL_RATE_THRESHOLD:
        score += 8

    if inputs.reorder_quantity_units > 0 and inputs.reorder_quantity_units > inputs.monthly_units_sold:
        score += 8

    if inputs.target_inventory_units > (inputs.monthly_units_sold * HIGH_EXCESS_COVERAGE_MONTHS_THRESHOLD):
        score += 10

    return int(min(round(score), 100))


def _classify_inventory_risk_level(score: int) -> str:
    """Convert inventory stress score into a readable risk label."""
    if score >= HIGH_INVENTORY_STRESS_SCORE:
        return "High"
    if score >= MODERATE_INVENTORY_STRESS_SCORE:
        return "Watch"
    return "Healthy"


def _classify_inventory_balance(
    inventory_stress_score: int,
    inventory_overstock_score: int,
) -> str:
    """Classify overall inventory posture as tight, balanced, or excess."""
    if inventory_stress_score >= MODERATE_INVENTORY_STRESS_SCORE:
        return "Tight"
    if inventory_overstock_score >= MODERATE_OVERSTOCK_SCORE:
        return "Excess"
    return "Balanced"


def _classify_stockout_severity(fill_rate: float, stockout_flag: bool) -> str:
    """Convert the monthly fill rate into a readable severity flag."""
    if not stockout_flag:
        return "None"
    if fill_rate < MODERATE_FILL_RATE_THRESHOLD:
        return "High"
    return "Moderate"


def _calculate_runway_months(
    starting_cash: float,
    monthly_collections: float,
    total_monthly_expenses: float,
) -> float | None:
    """Estimate runway from current burn if average monthly net cash flow is negative."""
    monthly_burn = total_monthly_expenses - monthly_collections
    if monthly_burn <= 0:
        return None
    return starting_cash / monthly_burn


def _validate_inputs(inputs: CashFlowInputs) -> None:
    """Guard against invalid values before forecasting."""
    if inputs.forecast_horizon_months < 1:
        raise ValueError("Forecast horizon must be at least 1 month.")
    if inputs.target_inventory_units < inputs.reorder_point_units:
        raise ValueError("Target inventory units should be at least the reorder point.")

    for field_name, value in inputs.__dict__.items():
        if value < 0:
            raise ValueError(f"{field_name.replace('_', ' ').title()} cannot be negative.")


def _resolve_profitability_defaults() -> tuple[dict[str, float], bool]:
    """Resolve unit-economics defaults from live Financial Health state when available."""
    profitability_defaults = get_default_profitability_inputs()
    profitability_state = _normalize_profitability_cost_state(
        get_business_inputs(PROFITABILITY_SECTION)
    )
    resolved_values, using_live_inputs = merge_with_default_baseline(
        profitability_state,
        {
            "monthly_units_sold": profitability_defaults.units_sold,
            "product_cost_per_unit": profitability_defaults.product_cost_per_unit,
            "shipping_cost_per_unit": profitability_defaults.shipping_cost_per_unit,
            "fulfillment_cost_per_unit": profitability_defaults.fulfillment_cost_per_unit,
            "packaging_cost_per_unit": profitability_defaults.packaging_cost_per_unit,
            "marketing_spend": profitability_defaults.marketing_spend,
        },
    )
    return {
        "monthly_units_sold": float(
            resolved_values.get(
                "monthly_units_sold",
                resolved_values.get("units_sold", profitability_defaults.units_sold),
            )
        ),
        "product_cost_per_unit": float(resolved_values["product_cost_per_unit"]),
        "shipping_cost_per_unit": float(resolved_values["shipping_cost_per_unit"]),
        "fulfillment_cost_per_unit": float(resolved_values["fulfillment_cost_per_unit"]),
        "packaging_cost_per_unit": float(resolved_values["packaging_cost_per_unit"]),
        "marketing_spend": float(resolved_values["marketing_spend"]),
    }, using_live_inputs


def _normalize_cashflow_state(state_values: dict[str, float | int]) -> dict[str, float | int]:
    """Map any legacy cashflow state into the current schema."""
    normalized_values = dict(state_values)
    if "units_sold" in normalized_values and "monthly_units_sold" not in normalized_values:
        normalized_values["monthly_units_sold"] = normalized_values["units_sold"]
    normalized_values.setdefault("beginning_inventory_units", 4200.0)
    normalized_values.setdefault("reorder_point_units", 1800.0)
    normalized_values.setdefault("target_inventory_units", 4200.0)
    normalized_values.setdefault("supplier_lead_time_months", 1)
    normalized_values.setdefault("reorder_quantity_units", 0.0)
    normalized_values.setdefault("safety_stock_units", 600.0)
    return normalized_values


def _normalize_profitability_cost_state(
    state_values: dict[str, float | int],
) -> dict[str, float | int]:
    """Map legacy blended variable cost state into decomposed unit-cost values."""
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
