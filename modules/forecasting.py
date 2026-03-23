"""Lightweight channel-based demand forecasting helpers for CFO AI."""

from dataclasses import dataclass
from statistics import mean

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.page_sections import render_metric_row
from utils.state import FORECASTING_SECTION, get_business_inputs, update_business_inputs

CHANNELS = ("paid", "organic", "retention")
CHANNEL_LABELS = {
    "paid": "Paid",
    "organic": "Organic",
    "retention": "Retention",
}
CHANNEL_COLORS = {
    "paid": "#ef4444",
    "organic": "#10b981",
    "retention": "#2563eb",
}
DEFAULT_FORECAST_METHOD = "Weighted Moving Average"
FORECAST_METHODS = (
    "Moving Average",
    "Weighted Moving Average",
    "Exponential Smoothing",
)
WEIGHTED_MOVING_AVERAGE_WEIGHTS = (0.5, 0.3, 0.2)
DEFAULT_SMOOTHING_ALPHA = 0.4
DEFAULT_HISTORY_MONTHS = (
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
    "Jan",
    "Feb",
    "Mar",
)
CHANNEL_SCENARIO_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "ad_cost_shock": {"paid": -0.18, "organic": -0.02, "retention": 0.00},
    "demand_drop": {"paid": -0.20, "organic": -0.14, "retention": -0.10},
    "supplier_cost_increase": {"paid": -0.04, "organic": -0.02, "retention": -0.01},
    "shipping_cost_increase": {"paid": -0.05, "organic": -0.03, "retention": -0.02},
    "holiday_demand_spike": {"paid": 0.18, "organic": 0.24, "retention": 0.20},
    "discount_campaign": {"paid": 0.20, "organic": 0.12, "retention": 0.06},
}
CHANNEL_SCENARIO_CAC_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "ad_cost_shock": {"paid": 0.22, "organic": 0.00, "retention": 0.00},
    "demand_drop": {"paid": 0.06, "organic": 0.00, "retention": 0.00},
    "supplier_cost_increase": {"paid": 0.03, "organic": 0.00, "retention": 0.00},
    "shipping_cost_increase": {"paid": 0.02, "organic": 0.00, "retention": 0.00},
    "holiday_demand_spike": {"paid": 0.05, "organic": 0.00, "retention": 0.00},
    "discount_campaign": {"paid": 0.10, "organic": 0.02, "retention": 0.00},
}
DEFAULT_CHANNEL_ACQUISITION_COSTS = {
    "paid": 16.0,
    "organic": 2.0,
    "retention": 4.0,
}
STRONG_GROWTH_QUALITY_THRESHOLD = 0.25
WATCH_GROWTH_QUALITY_THRESHOLD = 0.12


@dataclass(frozen=True)
class DemandForecastResult:
    """Structured demand forecast output used by cashflow and scenarios."""

    channel_history: dict[str, list[float]]
    channel_forecast: dict[str, list[float]]
    history_units: list[float]
    forecast_units: list[float]
    method: str
    horizon_months: int
    trend_direction: str
    channel_trend_direction: dict[str, str]
    average_forecast_units: float
    uncertainty_proxy: float
    channel_mix: dict[str, float]
    channel_acquisition_cost_per_unit: dict[str, float]
    use_forecast: bool
    source_label: str


@dataclass(frozen=True)
class ChannelEconomicsSummary:
    """Structured channel-level unit economics summary."""

    channel_units: dict[str, float]
    channel_revenue: dict[str, float]
    channel_acquisition_cost: dict[str, float]
    channel_contribution_after_acquisition: dict[str, float]
    channel_margin_quality: dict[str, float | None]
    total_acquisition_cost: float
    blended_contribution_after_acquisition: float
    weighted_margin_quality: float | None
    growth_quality_label: str


def load_sample_channel_demand_history() -> dict[str, list[float]]:
    """Return demo monthly demand history split by channel."""
    return {
        "paid": [420, 445, 460, 485, 510, 535, 570, 595, 640, 615, 650, 680],
        "organic": [430, 445, 455, 470, 490, 500, 520, 540, 565, 555, 575, 590],
        "retention": [330, 345, 355, 370, 390, 420, 450, 475, 520, 510, 540, 570],
    }


def load_sample_demand_history() -> list[float]:
    """Return aggregated demo monthly demand history."""
    channel_history = load_sample_channel_demand_history()
    return combine_channel_series(channel_history)


def generate_demand_forecast(
    history_units: list[float],
    horizon_months: int,
    method: str = DEFAULT_FORECAST_METHOD,
) -> DemandForecastResult:
    """Backward-compatible total-demand forecast builder."""
    channel_history = {"paid": history_units, "organic": [], "retention": []}
    return generate_channel_forecasts(channel_history, horizon_months, method)


def generate_channel_forecasts(
    channel_history: dict[str, list[float]],
    horizon_months: int,
    method: str = DEFAULT_FORECAST_METHOD,
    channel_acquisition_cost_per_unit: dict[str, float] | None = None,
) -> DemandForecastResult:
    """Generate separate monthly demand forecasts for each channel."""
    normalized_history = _normalize_channel_history(channel_history)
    channel_forecast = {
        channel: _forecast_series(history, horizon_months, method)
        for channel, history in normalized_history.items()
    }
    history_units = combine_channel_series(normalized_history)
    forecast_units = combine_channel_series(channel_forecast)
    channel_trend_direction = {
        channel: _classify_trend_direction(normalized_history[channel], channel_forecast[channel])
        for channel in CHANNELS
    }
    channel_mix = _calculate_channel_mix(channel_forecast)
    channel_acquisition_cost_per_unit = (
        _normalize_channel_costs(channel_acquisition_cost_per_unit)
        if channel_acquisition_cost_per_unit is not None
        else DEFAULT_CHANNEL_ACQUISITION_COSTS.copy()
    )

    return DemandForecastResult(
        channel_history=normalized_history,
        channel_forecast=channel_forecast,
        history_units=history_units,
        forecast_units=forecast_units,
        method=method,
        horizon_months=horizon_months,
        trend_direction=_classify_trend_direction(history_units, forecast_units),
        channel_trend_direction=channel_trend_direction,
        average_forecast_units=mean(forecast_units) if forecast_units else 0.0,
        uncertainty_proxy=_calculate_uncertainty_proxy(history_units),
        channel_mix=channel_mix,
        channel_acquisition_cost_per_unit=channel_acquisition_cost_per_unit,
        use_forecast=True,
        source_label="Channel forecast baseline",
    )


def resolve_demand_forecast(
    horizon_months: int,
    manual_monthly_units: float,
) -> DemandForecastResult:
    """Resolve the current forecast configuration from shared state."""
    state_values = get_business_inputs(FORECASTING_SECTION)
    sample_history = load_sample_channel_demand_history()
    method = str(state_values.get("method", DEFAULT_FORECAST_METHOD))
    use_forecast = bool(state_values.get("use_forecast", False))
    channel_costs = _normalize_channel_costs(
        {
            channel: state_values.get(
                f"{channel}_acquisition_cost_per_unit",
                DEFAULT_CHANNEL_ACQUISITION_COSTS[channel],
            )
            for channel in CHANNELS
        }
    )
    channel_history = {
        channel: _parse_history_csv(
            str(
                state_values.get(
                    f"{channel}_history_csv",
                    ",".join(str(int(value)) for value in sample_history[channel]),
                )
            )
        )
        for channel in CHANNELS
    }
    channel_history = _normalize_channel_history(channel_history)

    if use_forecast:
        return generate_channel_forecasts(
            channel_history,
            horizon_months,
            method,
            channel_costs,
        )

    manual_units = max(0.0, float(manual_monthly_units))
    manual_mix = _calculate_channel_mix(channel_history)
    channel_forecast = {
        channel: [manual_units * manual_mix[channel]] * horizon_months for channel in CHANNELS
    }
    history_units = combine_channel_series(channel_history)
    return DemandForecastResult(
        channel_history=channel_history,
        channel_forecast=channel_forecast,
        history_units=history_units,
        forecast_units=[manual_units] * horizon_months,
        method="Manual baseline",
        horizon_months=horizon_months,
        trend_direction="Stable",
        channel_trend_direction={channel: "Stable" for channel in CHANNELS},
        average_forecast_units=manual_units,
        uncertainty_proxy=_calculate_uncertainty_proxy(history_units),
        channel_mix=manual_mix,
        channel_acquisition_cost_per_unit=channel_costs,
        use_forecast=False,
        source_label="Manual demand baseline",
    )


def render_forecast_sidebar_controls(
    default_horizon_months: int,
    manual_monthly_units: float,
) -> DemandForecastResult:
    """Render channel-based forecasting controls in the sidebar."""
    state_values = get_business_inputs(FORECASTING_SECTION)
    sample_history = load_sample_channel_demand_history()
    method = str(state_values.get("method", DEFAULT_FORECAST_METHOD))
    use_forecast = bool(state_values.get("use_forecast", False))
    history_csv_by_channel = {
        channel: str(
            state_values.get(
                f"{channel}_history_csv",
                ",".join(str(int(value)) for value in sample_history[channel]),
            )
        )
        for channel in CHANNELS
    }
    acquisition_cost_by_channel = {
        channel: float(
            state_values.get(
                f"{channel}_acquisition_cost_per_unit",
                DEFAULT_CHANNEL_ACQUISITION_COSTS[channel],
            )
        )
        for channel in CHANNELS
    }

    with st.sidebar:
        st.subheader("Demand Forecasting")
        st.caption(
            "Generate a baseline demand forecast from monthly paid, organic, and retention units."
        )
        use_forecast = st.toggle(
            "Use forecasted demand baseline",
            value=use_forecast,
            key="forecasting_use_forecast",
        )
        method = st.selectbox(
            "Forecast method",
            FORECAST_METHODS,
            index=FORECAST_METHODS.index(method)
            if method in FORECAST_METHODS
            else FORECAST_METHODS.index(DEFAULT_FORECAST_METHOD),
            key="forecasting_method",
        )
        for channel in CHANNELS:
            history_csv_by_channel[channel] = st.text_area(
                f"{CHANNEL_LABELS[channel]} monthly units",
                value=history_csv_by_channel[channel],
                help="Enter comma-separated monthly units for this channel.",
                key=f"forecasting_{channel}_history_csv",
                height=80,
            )
        st.markdown("**Channel Economics**")
        for channel in CHANNELS:
            acquisition_cost_by_channel[channel] = st.number_input(
                f"{CHANNEL_LABELS[channel]} acquisition cost / unit",
                min_value=0.0,
                value=float(acquisition_cost_by_channel[channel]),
                step=1.0,
                key=f"forecasting_{channel}_acquisition_cost_per_unit",
            )

    update_business_inputs(
        FORECASTING_SECTION,
        {
            "use_forecast": use_forecast,
            "method": method,
            **{
                f"{channel}_history_csv": history_csv_by_channel[channel]
                for channel in CHANNELS
            },
            **{
                f"{channel}_acquisition_cost_per_unit": acquisition_cost_by_channel[channel]
                for channel in CHANNELS
            },
        },
    )

    if use_forecast:
        return generate_channel_forecasts(
            {
                channel: _parse_history_csv(history_csv_by_channel[channel])
                for channel in CHANNELS
            },
            default_horizon_months,
            method,
            acquisition_cost_by_channel,
        )
    return resolve_demand_forecast(default_horizon_months, manual_monthly_units)


def build_forecast_context(
    forecast_result: DemandForecastResult,
) -> dict[str, float | str | bool | None]:
    """Build a plain forecast context for recommendation logic."""
    return {
        "forecast_method": forecast_result.method,
        "forecast_horizon_months": forecast_result.horizon_months,
        "forecast_trend_direction": forecast_result.trend_direction,
        "forecast_average_units": forecast_result.average_forecast_units,
        "forecast_uncertainty_proxy": forecast_result.uncertainty_proxy,
        "forecast_source": forecast_result.source_label,
        "forecast_enabled": forecast_result.use_forecast,
        "forecast_paid_share": forecast_result.channel_mix.get("paid"),
        "forecast_retention_share": forecast_result.channel_mix.get("retention"),
        "forecast_paid_trend": forecast_result.channel_trend_direction.get("paid"),
        "forecast_retention_trend": forecast_result.channel_trend_direction.get("retention"),
        "forecast_paid_acquisition_cost_per_unit": forecast_result.channel_acquisition_cost_per_unit.get("paid"),
    }


def calculate_channel_economics(
    forecast_result: DemandForecastResult,
    average_selling_price: float,
    shared_variable_cost_per_unit: float,
) -> ChannelEconomicsSummary:
    """Estimate channel-level contribution quality using shared product and fulfillment economics."""
    channel_units = {
        channel: mean(forecast_result.channel_forecast[channel])
        if forecast_result.channel_forecast[channel]
        else 0.0
        for channel in CHANNELS
    }
    channel_revenue = {
        channel: units * average_selling_price for channel, units in channel_units.items()
    }
    shared_contribution_per_unit = max(
        0.0,
        average_selling_price - shared_variable_cost_per_unit,
    )
    channel_acquisition_cost = {
        channel: units * forecast_result.channel_acquisition_cost_per_unit[channel]
        for channel, units in channel_units.items()
    }
    channel_contribution_after_acquisition = {
        channel: (units * shared_contribution_per_unit) - channel_acquisition_cost[channel]
        for channel, units in channel_units.items()
    }
    channel_margin_quality = {
        channel: (
            channel_contribution_after_acquisition[channel] / channel_revenue[channel]
            if channel_revenue[channel] > 0
            else None
        )
        for channel in CHANNELS
    }
    total_revenue = sum(channel_revenue.values())
    total_acquisition_cost = sum(channel_acquisition_cost.values())
    blended_contribution_after_acquisition = sum(
        channel_contribution_after_acquisition.values()
    )
    weighted_margin_quality = (
        blended_contribution_after_acquisition / total_revenue if total_revenue > 0 else None
    )

    return ChannelEconomicsSummary(
        channel_units=channel_units,
        channel_revenue=channel_revenue,
        channel_acquisition_cost=channel_acquisition_cost,
        channel_contribution_after_acquisition=channel_contribution_after_acquisition,
        channel_margin_quality=channel_margin_quality,
        total_acquisition_cost=total_acquisition_cost,
        blended_contribution_after_acquisition=blended_contribution_after_acquisition,
        weighted_margin_quality=weighted_margin_quality,
        growth_quality_label=_classify_growth_quality(weighted_margin_quality),
    )


def build_channel_economics_context(
    economics_summary: ChannelEconomicsSummary,
) -> dict[str, float | str | None]:
    """Build a plain channel-economics context for recommendation logic."""
    return {
        "channel_total_acquisition_cost": economics_summary.total_acquisition_cost,
        "channel_weighted_margin_quality": economics_summary.weighted_margin_quality,
        "channel_growth_quality_label": economics_summary.growth_quality_label,
        "channel_paid_margin_quality": economics_summary.channel_margin_quality.get("paid"),
        "channel_retention_margin_quality": economics_summary.channel_margin_quality.get("retention"),
        "channel_paid_acquisition_cost": economics_summary.channel_acquisition_cost.get("paid"),
        "channel_retention_contribution": economics_summary.channel_contribution_after_acquisition.get("retention"),
    }


def create_demand_forecast_chart(forecast_result: DemandForecastResult) -> go.Figure:
    """Create a combined history and forecast demand chart with channels."""
    history_labels = list(DEFAULT_HISTORY_MONTHS[-len(forecast_result.history_units) :])
    forecast_labels = [f"F{index}" for index in range(1, forecast_result.horizon_months + 1)]

    figure = go.Figure()
    for channel in CHANNELS:
        figure.add_trace(
            go.Bar(
                x=history_labels,
                y=forecast_result.channel_history[channel],
                name=f"{CHANNEL_LABELS[channel]} History",
                marker_color=CHANNEL_COLORS[channel],
                opacity=0.45,
                legendgroup=channel,
            )
        )
    for channel in CHANNELS:
        figure.add_trace(
            go.Scatter(
                x=forecast_labels,
                y=forecast_result.channel_forecast[channel],
                mode="lines+markers",
                name=f"{CHANNEL_LABELS[channel]} Forecast",
                line=dict(color=CHANNEL_COLORS[channel], width=3),
                legendgroup=channel,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=history_labels + forecast_labels,
            y=forecast_result.history_units + forecast_result.forecast_units,
            mode="lines+markers",
            name="Total Demand",
            line=dict(color="#111827", width=3, dash="dash"),
        )
    )
    figure.update_layout(
        title="Demand Forecast by Channel",
        xaxis_title="Month",
        yaxis_title="Units",
        barmode="stack",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def render_forecast_summary(
    forecast_result: DemandForecastResult,
    manual_monthly_units: float,
) -> None:
    """Render compact demand forecast summary metrics."""
    baseline_value = (
        f"{forecast_result.average_forecast_units:,.0f} units"
        if forecast_result.use_forecast
        else f"{manual_monthly_units:,.0f} units"
    )
    dominant_channel = max(
        forecast_result.channel_mix.items(),
        key=lambda item: item[1],
    )[0]
    render_metric_row(
        [
            {
                "label": "Demand Source",
                "value": "Channel Forecast" if forecast_result.use_forecast else "Manual",
            },
            {
                "label": "Method",
                "value": forecast_result.method,
            },
            {
                "label": "Baseline Demand",
                "value": baseline_value,
            },
            {
                "label": "Trend",
                "value": forecast_result.trend_direction,
            },
            {
                "label": "Dominant Channel",
                "value": CHANNEL_LABELS[dominant_channel],
            },
            {
                "label": "Paid Share",
                "value": f"{forecast_result.channel_mix['paid'] * 100:.0f}%",
            },
            {
                "label": "Uncertainty",
                "value": f"{forecast_result.uncertainty_proxy:.1%}",
            },
        ],
        columns_per_row=3,
    )


def render_channel_economics_summary(
    economics_summary: ChannelEconomicsSummary,
) -> None:
    """Render compact channel-economics summary cards."""
    render_metric_row(
        [
            {
                "label": "Growth Quality",
                "value": economics_summary.growth_quality_label,
            },
            {
                "label": "Acquisition Cost Burden",
                "value": f"${economics_summary.total_acquisition_cost:,.0f}",
            },
            {
                "label": "Weighted Margin Quality",
                "value": (
                    f"{economics_summary.weighted_margin_quality * 100:.1f}%"
                    if economics_summary.weighted_margin_quality is not None
                    else "N/A"
                ),
            },
        ]
    )


def create_channel_economics_chart(
    economics_summary: ChannelEconomicsSummary,
) -> go.Figure:
    """Create a channel contribution chart."""
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=[CHANNEL_LABELS[channel] for channel in CHANNELS],
            y=[economics_summary.channel_revenue[channel] for channel in CHANNELS],
            name="Revenue",
            marker_color="#94a3b8",
        )
    )
    figure.add_trace(
        go.Bar(
            x=[CHANNEL_LABELS[channel] for channel in CHANNELS],
            y=[
                economics_summary.channel_contribution_after_acquisition[channel]
                for channel in CHANNELS
            ],
            name="Contribution After Acquisition",
            marker_color="#1f77b4",
        )
    )
    figure.update_layout(
        title="Channel Contribution Quality",
        barmode="group",
        yaxis_title="Amount ($)",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return figure


def render_channel_economics_table(
    economics_summary: ChannelEconomicsSummary,
) -> None:
    """Render the channel-level economics table."""
    rows = []
    for channel in CHANNELS:
        rows.append(
            {
                "Channel": CHANNEL_LABELS[channel],
                "Units": f"{economics_summary.channel_units[channel]:,.0f}",
                "Revenue": f"${economics_summary.channel_revenue[channel]:,.0f}",
                "Acquisition Cost": f"${economics_summary.channel_acquisition_cost[channel]:,.0f}",
                "Contribution After Acquisition": f"${economics_summary.channel_contribution_after_acquisition[channel]:,.0f}",
                "Margin Quality": (
                    f"{economics_summary.channel_margin_quality[channel] * 100:.1f}%"
                    if economics_summary.channel_margin_quality[channel] is not None
                    else "N/A"
                ),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_forecast_detail_table(forecast_result: DemandForecastResult) -> None:
    """Render a channel-level history and forecast table."""
    rows: list[dict[str, str]] = []
    for index, label in enumerate(DEFAULT_HISTORY_MONTHS[-len(forecast_result.history_units) :]):
        rows.append(
            {
                "Period": label,
                "Type": "History",
                "Paid": f"{forecast_result.channel_history['paid'][index]:,.0f}",
                "Organic": f"{forecast_result.channel_history['organic'][index]:,.0f}",
                "Retention": f"{forecast_result.channel_history['retention'][index]:,.0f}",
                "Total": f"{forecast_result.history_units[index]:,.0f}",
            }
        )
    for index in range(forecast_result.horizon_months):
        rows.append(
            {
                "Period": f"F{index + 1}",
                "Type": "Forecast",
                "Paid": f"{forecast_result.channel_forecast['paid'][index]:,.0f}",
                "Organic": f"{forecast_result.channel_forecast['organic'][index]:,.0f}",
                "Retention": f"{forecast_result.channel_forecast['retention'][index]:,.0f}",
                "Total": f"{forecast_result.forecast_units[index]:,.0f}",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def merge_forecast_with_scenario_adjustments(
    forecast_units: list[float],
    pct_change: float,
) -> list[float]:
    """Backward-compatible aggregate scenario adjustment helper."""
    return [max(0.0, value * (1 + pct_change)) for value in forecast_units]


def apply_channel_scenario_adjustments(
    forecast_result: DemandForecastResult,
    scenario_key: str,
    severity_factor: float,
) -> DemandForecastResult:
    """Apply scenario effects to each channel forecast separately."""
    if not forecast_result.use_forecast:
        return forecast_result

    channel_adjustments = CHANNEL_SCENARIO_ADJUSTMENTS.get(scenario_key, {})
    cac_adjustments = CHANNEL_SCENARIO_CAC_ADJUSTMENTS.get(scenario_key, {})
    adjusted_channel_forecast = {
        channel: [
            max(0.0, value * (1 + (channel_adjustments.get(channel, 0.0) * severity_factor)))
            for value in forecast_result.channel_forecast[channel]
        ]
        for channel in CHANNELS
    }
    total_forecast = combine_channel_series(adjusted_channel_forecast)
    adjusted_mix = _calculate_channel_mix(adjusted_channel_forecast)
    adjusted_channel_acquisition_cost_per_unit = {
        channel: max(
            0.0,
            forecast_result.channel_acquisition_cost_per_unit[channel]
            * (1 + (cac_adjustments.get(channel, 0.0) * severity_factor)),
        )
        for channel in CHANNELS
    }

    return DemandForecastResult(
        channel_history=forecast_result.channel_history,
        channel_forecast=adjusted_channel_forecast,
        history_units=forecast_result.history_units,
        forecast_units=total_forecast,
        method=forecast_result.method,
        horizon_months=forecast_result.horizon_months,
        trend_direction=_classify_trend_direction(
            forecast_result.history_units,
            total_forecast,
        ),
        channel_trend_direction={
            channel: _classify_trend_direction(
                forecast_result.channel_history[channel],
                adjusted_channel_forecast[channel],
            )
            for channel in CHANNELS
        },
        average_forecast_units=mean(total_forecast) if total_forecast else 0.0,
        uncertainty_proxy=forecast_result.uncertainty_proxy,
        channel_mix=adjusted_mix,
        channel_acquisition_cost_per_unit=adjusted_channel_acquisition_cost_per_unit,
        use_forecast=True,
        source_label=f"{forecast_result.source_label} + Scenario",
    )


def combine_channel_series(channel_series: dict[str, list[float]]) -> list[float]:
    """Combine multiple channel series into a total demand series."""
    max_length = max((len(values) for values in channel_series.values()), default=0)
    combined_values: list[float] = []
    for index in range(max_length):
        combined_values.append(
            sum(
                values[index] if index < len(values) else 0.0
                for values in channel_series.values()
            )
        )
    return combined_values


def get_forecasted_monthly_demand(
    forecast_result: DemandForecastResult,
) -> list[float] | None:
    """Return forecast units only when forecasting is enabled."""
    if not forecast_result.use_forecast:
        return None
    return list(forecast_result.forecast_units)


def _normalize_channel_history(
    channel_history: dict[str, list[float]],
) -> dict[str, list[float]]:
    """Normalize channel history into a complete aligned dict."""
    sample_history = load_sample_channel_demand_history()
    normalized = {
        channel: [
            max(0.0, float(value))
            for value in channel_history.get(channel, sample_history[channel])
            if value is not None
        ]
        for channel in CHANNELS
    }
    max_length = max(len(values) for values in normalized.values())
    for channel in CHANNELS:
        if not normalized[channel]:
            normalized[channel] = sample_history[channel]
        if len(normalized[channel]) < max_length:
            normalized[channel] = _left_pad_series(
                normalized[channel],
                max_length,
                normalized[channel][0],
            )
    return normalized


def _left_pad_series(values: list[float], target_length: int, fill_value: float) -> list[float]:
    """Pad a short series at the front to align channel history lengths."""
    if len(values) >= target_length:
        return values
    return [fill_value] * (target_length - len(values)) + values


def _forecast_series(
    history_units: list[float],
    horizon_months: int,
    method: str,
) -> list[float]:
    """Generate the forecast series using the selected method."""
    working_history = list(history_units)
    forecast_values: list[float] = []

    for _ in range(horizon_months):
        if method == "Moving Average":
            next_value = (
                mean(working_history[-3:]) if len(working_history) >= 3 else mean(working_history)
            )
        elif method == "Exponential Smoothing":
            next_value = _simple_exponential_smoothing(
                working_history,
                DEFAULT_SMOOTHING_ALPHA,
            )
        else:
            next_value = _weighted_moving_average(working_history)
        next_value = max(0.0, float(next_value))
        forecast_values.append(next_value)
        working_history.append(next_value)

    return forecast_values


def _weighted_moving_average(history_units: list[float]) -> float:
    """Calculate a weighted moving average over the most recent observations."""
    if len(history_units) < 3:
        return mean(history_units)
    recent_values = history_units[-3:]
    return sum(
        value * weight
        for value, weight in zip(recent_values[::-1], WEIGHTED_MOVING_AVERAGE_WEIGHTS)
    )


def _simple_exponential_smoothing(history_units: list[float], alpha: float) -> float:
    """Calculate the next value using simple exponential smoothing."""
    smoothed_value = history_units[0]
    for value in history_units[1:]:
        smoothed_value = (alpha * value) + ((1 - alpha) * smoothed_value)
    return smoothed_value


def _calculate_uncertainty_proxy(history_units: list[float]) -> float:
    """Use average absolute deviation as a lightweight uncertainty proxy."""
    if len(history_units) < 2:
        return 0.0
    average_value = mean(history_units)
    if average_value == 0:
        return 0.0
    avg_abs_dev = mean(abs(value - average_value) for value in history_units)
    return avg_abs_dev / average_value


def _classify_trend_direction(
    history_units: list[float],
    forecast_units: list[float],
) -> str:
    """Classify forecast direction as rising, stable, or falling."""
    if not history_units or not forecast_units:
        return "Stable"
    recent_average = mean(history_units[-3:]) if len(history_units) >= 3 else mean(history_units)
    forecast_average = mean(forecast_units)
    if recent_average == 0:
        return "Stable"
    pct_change = (forecast_average - recent_average) / recent_average
    if pct_change > 0.05:
        return "Rising"
    if pct_change < -0.05:
        return "Falling"
    return "Stable"


def _calculate_channel_mix(channel_forecast: dict[str, list[float]]) -> dict[str, float]:
    """Calculate forecast mix shares by channel."""
    totals = {channel: mean(values) if values else 0.0 for channel, values in channel_forecast.items()}
    total_units = sum(totals.values())
    if total_units == 0:
        equal_share = 1 / len(CHANNELS)
        return {channel: equal_share for channel in CHANNELS}
    return {channel: totals[channel] / total_units for channel in CHANNELS}


def _normalize_channel_costs(channel_costs: dict[str, float] | None) -> dict[str, float]:
    """Normalize channel acquisition-cost assumptions."""
    if channel_costs is None:
        return DEFAULT_CHANNEL_ACQUISITION_COSTS.copy()
    return {
        channel: max(
            0.0,
            float(channel_costs.get(channel, DEFAULT_CHANNEL_ACQUISITION_COSTS[channel])),
        )
        for channel in CHANNELS
    }


def _classify_growth_quality(weighted_margin_quality: float | None) -> str:
    """Classify blended contribution quality after acquisition."""
    if weighted_margin_quality is None:
        return "N/A"
    if weighted_margin_quality >= STRONG_GROWTH_QUALITY_THRESHOLD:
        return "Strong"
    if weighted_margin_quality >= WATCH_GROWTH_QUALITY_THRESHOLD:
        return "Watch"
    return "Weak"


def _parse_history_csv(history_csv: str) -> list[float]:
    """Parse comma-separated monthly demand history with graceful fallback."""
    parsed_values: list[float] = []
    for part in history_csv.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        try:
            parsed_values.append(max(0.0, float(stripped)))
        except ValueError:
            continue
    return parsed_values
