"""Recommendation UI components."""

import streamlit as st

from modules.recommendations import Recommendation


def render_recommendation_summary(summary: dict[str, object]) -> None:
    """Render a compact executive summary for recommendations."""
    top_categories = summary.get("top_categories", [])
    category_text = ", ".join(top_categories) if top_categories else "None"
    high_count = int(summary.get("high_priority_count", 0))
    medium_count = int(summary.get("medium_priority_count", 0))
    low_count = int(summary.get("low_priority_count", 0))

    st.markdown(
        (
            '<div class="cfo-summary-banner">'
            f"<strong>{high_count}</strong> high-priority items, "
            f"<strong>{medium_count}</strong> medium-priority items, and "
            f"<strong>{low_count}</strong> low-priority insights. "
            f"Current focus areas: <strong>{category_text}</strong>."
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    columns = st.columns(4)
    columns[0].metric("High Priority", str(high_count))
    columns[1].metric("Medium Priority", str(medium_count))
    columns[2].metric("Low Priority", str(low_count))
    columns[3].metric("Focus Areas", category_text)


def render_top_priorities(recommendations: list[Recommendation], limit: int = 3) -> None:
    """Render the highest-priority recommendations at the top of the panel."""
    top_items = recommendations[:limit]
    if not top_items:
        return

    st.subheader("Top Priorities")
    for recommendation in top_items:
        priority_class = _priority_class(recommendation["priority"])
        st.markdown(
            (
                '<div class="top-priority-card">'
                f'<div class="recommendation-title">{recommendation["title"]}</div>'
                '<div class="recommendation-meta">'
                f'<span class="recommendation-badge {priority_class}">{recommendation["priority"]}</span>'
                f'<span class="recommendation-badge badge-category">{recommendation["category"]}</span>'
                f'<span class="recommendation-badge badge-category">{recommendation["status"]}</span>'
                "</div>"
                f'<div class="recommendation-line"><strong>Issue:</strong> {recommendation["issue"]}</div>'
                f'<div class="recommendation-line"><strong>Action:</strong> {recommendation["action"]}</div>'
                f'<div class="recommendation-line recommendation-impact"><strong>Impact:</strong> {recommendation["estimated_impact"]}</div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def render_recommendation_panel(recommendations: list[Recommendation]) -> None:
    """Render recommendation cards with modern readable spacing."""
    st.subheader("Recommendations")

    if not recommendations:
        with st.container(border=True):
            st.write("No recommendations available yet.")
        return

    for recommendation in recommendations:
        priority_class = _priority_class(recommendation["priority"])
        priority_card_class = (
            " priority-high" if recommendation["priority"] == "High" else ""
        )
        st.markdown(
            (
                f'<div class="recommendation-card{priority_card_class}">'
                f'<div class="recommendation-title">{recommendation["title"]}</div>'
                '<div class="recommendation-meta">'
                f'<span class="recommendation-badge {priority_class}">{recommendation["priority"]}</span>'
                f'<span class="recommendation-badge badge-category">{recommendation["category"]}</span>'
                f'<span class="recommendation-badge badge-category">{recommendation["status"]}</span>'
                "</div>"
                f'<div class="recommendation-line"><strong>Issue:</strong> {recommendation["issue"]}</div>'
                f'<div class="recommendation-line"><strong>Action:</strong> {recommendation["action"]}</div>'
                f'<div class="recommendation-line"><strong>Metric:</strong> {recommendation["metric_reference"]}</div>'
                f'<div class="recommendation-line"><strong>Evidence:</strong> {recommendation["evidence"]}</div>'
                f'<div class="recommendation-line"><strong>Why it matters:</strong> {recommendation["rationale"]}</div>'
                f'<div class="recommendation-line recommendation-impact"><strong>Estimated impact:</strong> {recommendation["estimated_impact"]}</div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def _priority_class(priority: str) -> str:
    """Map recommendation priority to a CSS badge class."""
    return {
        "High": "badge-high",
        "Medium": "badge-medium",
        "Low": "badge-low",
    }.get(priority, "badge-category")
