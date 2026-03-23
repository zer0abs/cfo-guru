"""KPI dashboard helpers for Financial Health."""

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.health_score import HealthScoreResult, calculate_business_health_score
from modules.profitability import ProfitabilityInputs, ProfitabilityResults
from utils.formatting import format_currency, format_percent


@dataclass(frozen=True)
class KPIDashboardData:
    """Container for KPI values, trends, and health score output."""

    kpis: dict[str, float | None]
    trends: pd.DataFrame
    health_score: HealthScoreResult


def build_kpi_dashboard_data(
    inputs: ProfitabilityInputs, results: ProfitabilityResults
) -> KPIDashboardData:
    """Build e-commerce KPI series anchored to the current profitability simulation."""
    trends = _build_sample_trend_data(inputs, results)
    current = trends.iloc[-1]

    kpis = {
        "revenue": float(current["revenue"]),
        "revenue_growth": _safe_growth(
            float(current["revenue"]), float(trends.iloc[-2]["revenue"])
        ),
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


def render_kpi_cards(dashboard: KPIDashboardData) -> None:
    """Render the KPI card grid."""
    trends = dashboard.trends
    current = dashboard.kpis

    cards = [
        {
            "label": "Revenue Growth",
            "value": format_percent(current["revenue_growth"]),
            "delta": _delta_percent(trends["revenue"].iloc[-1], trends["revenue"].iloc[-2]),
        },
        {
            "label": "Gross Margin",
            "value": format_percent(current["gross_margin"]),
            "delta": _delta_points(trends["gross_margin"].iloc[-1], trends["gross_margin"].iloc[-2]),
        },
        {
            "label": "Net Margin",
            "value": format_percent(current["net_margin"]),
            "delta": _delta_points(trends["net_margin"].iloc[-1], trends["net_margin"].iloc[-2]),
        },
        {
            "label": "Burn Rate",
            "value": format_currency(current["burn_rate"]),
            "delta": _delta_currency(trends["burn_rate"].iloc[-1], trends["burn_rate"].iloc[-2]),
        },
        {
            "label": "Runway",
            "value": _format_months(current["runway"]),
            "delta": _delta_months(trends["runway"].iloc[-1], trends["runway"].iloc[-2]),
        },
        {
            "label": "CAC",
            "value": format_currency(current["cac"]),
            "delta": _delta_currency(trends["cac"].iloc[-1], trends["cac"].iloc[-2]),
        },
        {
            "label": "LTV",
            "value": format_currency(current["ltv"]),
            "delta": _delta_currency(trends["ltv"].iloc[-1], trends["ltv"].iloc[-2]),
        },
        {
            "label": "Inventory Turnover",
            "value": f"{current['inventory_turnover']:.1f}x",
            "delta": _delta_turns(
                trends["inventory_turnover"].iloc[-1],
                trends["inventory_turnover"].iloc[-2],
            ),
        },
    ]

    for start_index in range(0, len(cards), 4):
        columns = st.columns(4)
        for column, card in zip(columns, cards[start_index : start_index + 4]):
            column.metric(card["label"], card["value"], delta=card["delta"])


def render_kpi_trend_charts(dashboard: KPIDashboardData) -> None:
    """Render small trend charts for the most decision-useful KPIs."""
    trend_specs = [
        ("Revenue Trend", "revenue", format_currency),
        ("Gross Margin Trend", "gross_margin", format_percent),
        ("Net Margin Trend", "net_margin", format_percent),
        ("Burn Rate Trend", "burn_rate", format_currency),
    ]

    columns = st.columns(len(trend_specs))
    for column, (title, metric_name, formatter) in zip(columns, trend_specs):
        with column:
            st.caption(title)
            st.plotly_chart(
                _create_sparkline_chart(
                    dashboard.trends["month"],
                    dashboard.trends[metric_name],
                    title,
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )
            st.caption(f"Latest: {formatter(float(dashboard.trends[metric_name].iloc[-1]))}")


def render_health_score(dashboard: KPIDashboardData) -> None:
    """Render the business health score with interpretation."""
    score = dashboard.health_score

    left_column, right_column = st.columns((1, 1.4))
    with left_column:
        st.plotly_chart(
            _create_health_score_gauge(score.score),
            use_container_width=True,
            config={"displayModeBar": False},
        )
    with right_column:
        st.subheader("Business Health Score")
        st.metric("Overall Score", f"{score.score}/100", delta=score.interpretation)
        st.write(
            "Interpretation bands: 80-100 Strong, 60-79 Moderate, below 60 At Risk."
        )
        st.caption(
            "The score is built from four dimensions: Profitability, Liquidity, Growth Efficiency, and Operational Efficiency."
        )


def render_health_score_breakdown(dashboard: KPIDashboardData) -> None:
    """Render the underlying health-score components."""
    score_frame = pd.DataFrame(
        [
            {"Dimension": "Profitability", "KPI / Driver": "Gross Margin + Net Margin", "Score": dashboard.health_score.dimension_scores["profitability"]},
            {"Dimension": "Liquidity", "KPI / Driver": "Burn Rate + Runway", "Score": dashboard.health_score.dimension_scores["liquidity"]},
            {"Dimension": "Growth Efficiency", "KPI / Driver": "Revenue Growth + LTV/CAC + AOV", "Score": dashboard.health_score.dimension_scores["growth_efficiency"]},
            {
                "Dimension": "Operational Efficiency",
                "KPI / Driver": "Inventory Turnover + Return Rate",
                "Score": dashboard.health_score.dimension_scores["operational_efficiency"],
            },
        ]
    )
    st.dataframe(score_frame, use_container_width=True, hide_index=True)

    component_frame = pd.DataFrame(
        [
            {"KPI": "Revenue Growth", "Component Score": dashboard.health_score.component_scores["revenue_growth"]},
            {"KPI": "Gross Margin", "Component Score": dashboard.health_score.component_scores["gross_margin"]},
            {"KPI": "Net Margin", "Component Score": dashboard.health_score.component_scores["net_margin"]},
            {"KPI": "Burn Rate", "Component Score": dashboard.health_score.component_scores["burn_rate"]},
            {"KPI": "Runway", "Component Score": dashboard.health_score.component_scores["runway"]},
            {"KPI": "LTV/CAC", "Component Score": dashboard.health_score.component_scores["cac_ltv"]},
            {"KPI": "Average Order Value", "Component Score": dashboard.health_score.component_scores["aov"]},
            {"KPI": "Return / Refund Rate", "Component Score": dashboard.health_score.component_scores["return_rate"]},
            {"KPI": "Inventory Turnover", "Component Score": dashboard.health_score.component_scores["inventory_turnover"]},
        ]
    )
    st.caption("Underlying KPI scores")
    st.dataframe(component_frame, use_container_width=True, hide_index=True)


def _build_sample_trend_data(
    inputs: ProfitabilityInputs, results: ProfitabilityResults
) -> pd.DataFrame:
    """Create e-commerce KPI history anchored to the current simulated results."""
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    revenue_values = [
        results.revenue * 0.82,
        results.revenue * 0.88,
        results.revenue * 0.91,
        results.revenue * 0.95,
        results.revenue * 0.98,
        results.revenue,
    ]
    gross_margin_values = [
        _clamp((results.gross_margin or 0.0) - 0.05),
        _clamp((results.gross_margin or 0.0) - 0.03),
        _clamp((results.gross_margin or 0.0) - 0.02),
        _clamp((results.gross_margin or 0.0) - 0.01),
        _clamp((results.gross_margin or 0.0) - 0.005),
        _clamp(results.gross_margin or 0.0),
    ]
    net_margin_values = [
        _clamp((results.net_margin or 0.0) - 0.06),
        _clamp((results.net_margin or 0.0) - 0.04),
        _clamp((results.net_margin or 0.0) - 0.03),
        _clamp((results.net_margin or 0.0) - 0.02),
        _clamp((results.net_margin or 0.0) - 0.01),
        _clamp(results.net_margin or 0.0),
    ]
    cash_reserve_values = [84000.0, 91000.0, 98000.0, 106000.0, 114000.0, 125000.0]

    cac_values = [31.0, 30.0, 29.0, 28.0, 27.0, 26.0]
    ltv_values = [118.0, 121.0, 125.0, 128.0, 132.0, 136.0]
    inventory_turnover_values = [3.8, 4.2, 4.7, 5.1, 5.5, 5.9]
    aov_values = [
        inputs.price_per_unit * 1.01,
        inputs.price_per_unit * 1.00,
        inputs.price_per_unit * 1.02,
        inputs.price_per_unit * 1.01,
        inputs.price_per_unit * 0.99,
        inputs.price_per_unit,
    ]
    return_rate_values = [0.075, 0.072, 0.070, 0.068, 0.066, 0.064]
    units_sold_values = [
        revenue / aov for revenue, aov in zip(revenue_values, aov_values)
    ]

    net_profit_values = [revenue * margin for revenue, margin in zip(revenue_values, net_margin_values)]
    burn_rate_values = [max(0.0, -net_profit) for net_profit in net_profit_values]
    runway_values = [
        _calculate_runway_from_cash(cash_reserve, burn_rate)
        for cash_reserve, burn_rate in zip(cash_reserve_values, burn_rate_values)
    ]

    return pd.DataFrame(
        {
            "month": month_labels,
            "revenue": revenue_values,
            "gross_margin": gross_margin_values,
            "net_margin": net_margin_values,
            "net_profit": net_profit_values,
            "burn_rate": burn_rate_values,
            "cash_reserve": cash_reserve_values,
            "runway": runway_values,
            "cac": cac_values,
            "ltv": ltv_values,
            "aov": aov_values,
            "return_rate": return_rate_values,
            "units_sold": units_sold_values,
            "inventory_turnover": inventory_turnover_values,
            "price_per_unit": [inputs.price_per_unit] * len(month_labels),
        }
    )


def _create_sparkline_chart(
    x_values: pd.Series, y_values: pd.Series, title: str
) -> go.Figure:
    """Create a compact trend chart for KPI tiles."""
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines+markers",
            line=dict(color="#1f77b4", width=2),
            marker=dict(size=6),
            hovertemplate="%{x}: %{y:.2f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=title,
        height=180,
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        showlegend=False,
    )
    return figure


def _create_health_score_gauge(score: int) -> go.Figure:
    """Create a gauge chart for the health score."""
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#1f77b4"},
                "steps": [
                    {"range": [0, 60], "color": "#f4cccc"},
                    {"range": [60, 80], "color": "#ffe599"},
                    {"range": [80, 100], "color": "#d9ead3"},
                ],
            },
        )
    )
    figure.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20))
    return figure


def _safe_growth(current_value: float, previous_value: float) -> float | None:
    """Calculate growth rate with divide-by-zero protection."""
    if previous_value == 0:
        return None
    return (current_value - previous_value) / previous_value


def _calculate_runway_from_cash(cash_reserve: float, burn_rate: float) -> float | None:
    """Convert current cash and burn into runway months."""
    if burn_rate <= 0:
        return None
    return cash_reserve / burn_rate


def _format_months(value: float | None) -> str:
    """Format runway values for KPI cards."""
    if value is None:
        return "Stable / N/A"
    return f"{value:.1f} mo"


def _delta_percent(current_value: float, previous_value: float) -> str | None:
    """Format percent-change deltas for KPI cards."""
    growth = _safe_growth(current_value, previous_value)
    return format_percent(growth) if growth is not None else None


def _delta_points(current_value: float, previous_value: float) -> str:
    """Format margin deltas in percentage points."""
    delta = (current_value - previous_value) * 100
    return f"{delta:+.1f} pts"


def _delta_currency(current_value: float, previous_value: float) -> str:
    """Format currency deltas for KPI cards."""
    delta = current_value - previous_value
    sign = "+" if delta >= 0 else "-"
    return f"{sign}${abs(delta):,.0f}"


def _delta_months(current_value: float | None, previous_value: float | None) -> str | None:
    """Format runway deltas for KPI cards."""
    if current_value is None or previous_value is None:
        return None
    delta = current_value - previous_value
    return f"{delta:+.1f} mo"


def _delta_turns(current_value: float, previous_value: float) -> str:
    """Format inventory-turnover deltas."""
    delta = current_value - previous_value
    return f"{delta:+.1f}x"


def _clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    """Clamp ratios to a sensible range for sample data generation."""
    return max(minimum, min(value, maximum))
