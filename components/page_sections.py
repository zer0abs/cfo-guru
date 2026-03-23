"""Shared page-level UI building blocks."""

from collections.abc import Sequence

import streamlit as st


def render_page_header(title: str, description: str) -> None:
    """Render a consistent page header across modules."""
    st.markdown(
        (
            '<div class="cfo-page-intro">'
            f'<div class="cfo-page-title">{title}</div>'
            f'<p class="cfo-page-description">{description}</p>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_placeholder_card(title: str, body: str) -> None:
    """Render a simple placeholder card for work-in-progress sections."""
    with st.container(border=True):
        st.subheader(title)
        st.write(body)


def render_section_card(title: str, description: str | None = None) -> None:
    """Render a standardized section heading inside a bordered container."""
    with st.container(border=True):
        st.subheader(title)
        if description:
            st.caption(description)


def render_section_header(title: str, description: str | None = None, label: str | None = None) -> None:
    """Render a shared section header with optional small label."""
    label_markup = (
        f'<div class="cfo-section-label">{label}</div>'
        if label
        else ""
    )
    description_markup = (
        f'<p class="cfo-section-description">{description}</p>'
        if description
        else ""
    )
    st.markdown(
        (
            '<div class="cfo-section-heading">'
            f"{label_markup}"
            f'<div class="cfo-section-title">{title}</div>'
            f"{description_markup}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_info_chips(items: Sequence[dict[str, str]]) -> None:
    """Render lightweight status chips for metadata and state indicators."""
    if not items:
        return
    parts: list[str] = []
    for item in items:
        chip_tone = item.get("tone", "default")
        label = item.get("label", "").strip()
        value = item.get("value", "").strip()
        text = f"{label}: {value}" if label and value else label or value
        if not text:
            continue
        class_name = {
            "brand": "chip-brand",
            "warning": "chip-warning",
            "danger": "chip-danger",
            "success": "chip-success",
        }.get(chip_tone, "")
        parts.append(f'<span class="cfo-chip {class_name}">{text}</span>')
    if not parts:
        return
    st.markdown(
        f'<div class="cfo-info-grid">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def render_text_card(title: str, items: Sequence[str]) -> None:
    """Render a clean bordered text card for summary bullets."""
    bullets = "".join(f"<li>{item}</li>" for item in items) if items else "<li>No items yet.</li>"
    st.markdown(
        (
            '<div class="cfo-text-card">'
            f"<h3>{title}</h3>"
            f"<ul>{bullets}</ul>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_metric_row(metrics: Sequence[dict[str, str]], columns_per_row: int | None = None) -> None:
    """Render metric cards with automatic wrapping for readability."""
    if not metrics:
        return

    columns_per_row = columns_per_row or min(4, len(metrics))
    for start_index in range(0, len(metrics), columns_per_row):
        row_metrics = metrics[start_index : start_index + columns_per_row]
        columns = st.columns(len(row_metrics))
        for column, metric_data in zip(columns, row_metrics):
            column.metric(
                metric_data["label"],
                metric_data["value"],
                delta=metric_data.get("delta"),
            )
