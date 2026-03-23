"""Shared Streamlit session-state helpers for cross-page business inputs."""

from collections.abc import Mapping

import streamlit as st


APP_INPUTS_STATE_KEY = "business_inputs"
PROFITABILITY_SECTION = "profitability"
CASHFLOW_SECTION = "cashflow"
FORECASTING_SECTION = "forecasting"


def initialize_default_state() -> None:
    """Initialize the shared app input store if it does not exist yet."""
    st.session_state.setdefault(
        APP_INPUTS_STATE_KEY,
        {
            PROFITABILITY_SECTION: {},
            CASHFLOW_SECTION: {},
            FORECASTING_SECTION: {},
        },
    )


def update_business_inputs(section: str, values: Mapping[str, object]) -> None:
    """Persist the latest input values for a section into shared state."""
    initialize_default_state()
    stored_inputs = st.session_state[APP_INPUTS_STATE_KEY]
    stored_inputs[section] = dict(values)


def get_business_inputs(section: str) -> dict[str, object]:
    """Return the stored input values for a single app section."""
    initialize_default_state()
    stored_inputs = st.session_state.get(APP_INPUTS_STATE_KEY, {})
    return dict(stored_inputs.get(section, {}))


def get_current_business_inputs() -> dict[str, dict[str, object]]:
    """Return all currently stored business inputs."""
    initialize_default_state()
    stored_inputs = st.session_state.get(APP_INPUTS_STATE_KEY, {})
    return {
        PROFITABILITY_SECTION: dict(stored_inputs.get(PROFITABILITY_SECTION, {})),
        CASHFLOW_SECTION: dict(stored_inputs.get(CASHFLOW_SECTION, {})),
        FORECASTING_SECTION: dict(stored_inputs.get(FORECASTING_SECTION, {})),
    }


def merge_with_default_baseline(
    live_values: Mapping[str, object],
    default_values: Mapping[str, object],
) -> tuple[dict[str, object], bool]:
    """Merge live inputs onto defaults and indicate whether live state was used."""
    merged_values = dict(default_values)
    merged_values.update({key: value for key, value in live_values.items() if value is not None})
    using_live_inputs = bool(live_values)
    return merged_values, using_live_inputs
