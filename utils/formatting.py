"""Formatting helpers for finance-focused UI output."""


def format_currency(value: float | None) -> str:
    """Format a numeric value as currency with a safe fallback."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def format_percent(value: float | None) -> str:
    """Format a decimal ratio as a percentage with a safe fallback."""
    if value is None:
        return "N/A"
    return f"{value:.1%}"
