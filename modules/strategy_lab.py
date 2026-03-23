"""Strategy Lab scenario simulator page."""

import streamlit as st

from components.recommendation_cards import (
    render_recommendation_panel,
    render_recommendation_summary,
    render_top_priorities,
)
from components.page_sections import render_info_chips, render_page_header, render_section_header, render_text_card
from modules.forecasting import (
    create_channel_economics_chart,
    render_channel_economics_summary,
    render_channel_economics_table,
)
from modules.recommendations import summarize_recommendations
from modules.scenarios import (
    create_scenario_cash_chart,
    create_scenario_comparison_chart,
    get_available_scenarios,
    get_strategy_baseline_from_state,
    render_scenario_comparison_table,
    render_scenario_delta_cards,
    render_scenario_overview,
    render_strategy_lab_controls,
    run_scenario_analysis,
    summarize_recommendation_changes,
)


def render_strategy_lab_page() -> None:
    """Render the Strategy Lab workspace."""
    scenario_lookup = {scenario["key"]: scenario for scenario in get_available_scenarios()}
    scenario_key, severity = render_strategy_lab_controls()
    scenario_metadata = scenario_lookup[scenario_key]
    baseline = get_strategy_baseline_from_state()
    analysis = run_scenario_analysis(
        baseline=baseline,
        scenario_key=scenario_key,
        severity=severity,
    )
    recommendation_summary = summarize_recommendations(analysis.scenario_recommendations)
    recommendation_changes = summarize_recommendation_changes(analysis)

    render_page_header(
        "Strategy Lab",
        "Compare baseline performance against scenario shocks and growth bets for the demo e-commerce brand.",
    )
    render_info_chips(
        [
            {"label": "Scenario", "value": analysis.scenario_name, "tone": "brand"},
            {"label": "Severity", "value": severity.title(), "tone": "warning"},
            {"label": "Baseline Source", "value": baseline.source},
            {
                "label": "Demand Baseline",
                "value": (
                    f"{'Forecast' if baseline.demand_forecast.use_forecast else 'Manual'} via {baseline.demand_forecast.method}"
                    if baseline.demand_forecast is not None
                    else "N/A"
                ),
            },
        ]
    )
    st.markdown(
        (
            '<div class="cfo-summary-banner">'
            f"<strong>{analysis.scenario_name}</strong><br>{analysis.summary_interpretation}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    st.caption(f"{scenario_metadata['description']} Severity: {severity.title()}.")
    if analysis.scenario_metrics.inventory_risk_level == "High":
        st.warning(
            f"Scenario inventory risk is high. Estimated lost revenue rises to {analysis.scenario_metrics.lost_revenue:,.0f} and inventory stress reaches {analysis.scenario_metrics.inventory_stress_score}/100."
        )
    elif analysis.scenario_metrics.inventory_balance_label == "Excess":
        st.warning(
            f"Scenario inventory posture shifts to excess, tying up about {analysis.scenario_metrics.excess_inventory_value:,.0f} above target coverage."
        )
    elif analysis.scenario_metrics.inventory_risk_level == "Watch":
        st.info(
            f"Scenario inventory coverage tightens to {analysis.scenario_metrics.inventory_coverage_months:.1f} months. Review reorder timing before scaling demand."
        )
    if analysis.scenario_metrics.growth_quality_label == "Weak":
        st.warning(
            "Scenario growth quality weakens. Paid acquisition burden is rising faster than contribution, so mix quality and ad efficiency should be reviewed before scaling."
        )
    elif (
        analysis.baseline_metrics.growth_quality_label != analysis.scenario_metrics.growth_quality_label
        and analysis.scenario_metrics.growth_quality_label is not None
    ):
        st.info(
            f"Growth quality shifts from {analysis.baseline_metrics.growth_quality_label or 'N/A'} to {analysis.scenario_metrics.growth_quality_label} under this scenario."
        )

    render_section_header(
        "Scenario Overview",
        "Headline comparison between the current baseline and the selected scenario.",
        label="Scenario",
    )
    render_scenario_overview(analysis)
    render_scenario_delta_cards(analysis)

    chart_left, chart_right = st.columns((1.1, 1))
    with chart_left:
        st.plotly_chart(
            create_scenario_comparison_chart(analysis),
            use_container_width=True,
            key="strategy_lab_scenario_comparison_chart",
        )
    with chart_right:
        st.plotly_chart(
            create_scenario_cash_chart(analysis),
            use_container_width=True,
            key="strategy_lab_scenario_cash_chart",
        )

    render_section_header(
        "Baseline vs Scenario",
        "Detailed comparison across margin, cash, inventory, and growth quality.",
        label="Comparison",
    )
    render_scenario_comparison_table(analysis)

    if (
        analysis.baseline_channel_economics is not None
        and analysis.scenario_channel_economics is not None
    ):
        render_section_header(
            "Channel Economics",
            "How the scenario changes demand quality and channel contribution after acquisition cost.",
            label="Channels",
        )
        baseline_column, scenario_column = st.columns(2)
        with baseline_column:
            st.caption("Baseline Growth Mix")
            render_channel_economics_summary(analysis.baseline_channel_economics)
            st.plotly_chart(
                create_channel_economics_chart(analysis.baseline_channel_economics),
                use_container_width=True,
                key="strategy_lab_channel_economics_baseline_chart",
            )
        with scenario_column:
            st.caption(f"{analysis.scenario_name} Growth Mix")
            render_channel_economics_summary(analysis.scenario_channel_economics)
            st.plotly_chart(
                create_channel_economics_chart(analysis.scenario_channel_economics),
                use_container_width=True,
                key="strategy_lab_channel_economics_scenario_chart",
            )
        with st.expander("Channel Contribution Detail", expanded=False):
            table_left, table_right = st.columns(2)
            with table_left:
                st.caption("Baseline")
                render_channel_economics_table(analysis.baseline_channel_economics)
            with table_right:
                st.caption(analysis.scenario_name)
                render_channel_economics_table(analysis.scenario_channel_economics)

    render_section_header(
        "Recommendation Changes",
        "What becomes more urgent, what clears, and what remains relevant under the scenario.",
        label="Decision Impact",
    )
    change_left, change_right, change_center = st.columns(3)
    with change_left:
        render_text_card("New Under Scenario", recommendation_changes["new"][:4])
    with change_right:
        render_text_card("Cleared vs Baseline", recommendation_changes["cleared"][:4])
    with change_center:
        render_text_card("Still Relevant", recommendation_changes["persistent"][:4])

    st.divider()
    render_section_header(
        "Scenario Actions",
        "Recommended actions if this scenario becomes the working plan.",
        label="Recommendations",
    )
    render_recommendation_summary(recommendation_summary)
    render_top_priorities(analysis.scenario_recommendations)
    render_recommendation_panel(analysis.scenario_recommendations)

    with st.expander("Adjusted Inputs", expanded=False):
        st.json(analysis.adjusted_inputs)
