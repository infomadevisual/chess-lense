import pandas as pd
import streamlit as st
from pydantic import BaseModel, ConfigDict

SESSION_KEY_USERNAME = "username"
SESSION_KEY_FILTERS = "available_filters"
SESSION_KEY_FILTERS_CURRENT = "current_filters"


class FilterOptionsAvailable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    months: list[str]  # ["YYYY-MM", ...]
    rated: list[bool]  # e.g. [True, False]
    time_class: list[str]  # e.g. ["All","bullet","blitz","rapid","daily"]

    def to_period_index(self) -> pd.PeriodIndex:
        return pd.PeriodIndex(self.months, freq="M")


class CurrentFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")
    month_start: str | None = None  # "YYYY-MM"
    month_end: str | None = None  # "YYYY-MM"
    rated_only: bool | None = None  # None = both
    time_class: str = "All"  # one of available


def init_session():
    st.session_state.setdefault(SESSION_KEY_USERNAME, None)
    st.session_state.initialized = True


def ensure_session_initialized():
    if "initialized" not in st.session_state:
        init_session()


def get_session_username() -> str | None:
    return st.session_state[SESSION_KEY_USERNAME]


def get_session_username_normalized() -> str:
    u = get_session_username()
    if u is None:
        return ""
    return u.strip().lower()


def set_session_username(username: str | None):
    st.session_state[SESSION_KEY_USERNAME] = username


def set_available_filters(filters: FilterOptionsAvailable):
    st.session_state[SESSION_KEY_FILTERS] = filters.model_dump()


def get_available_filters() -> FilterOptionsAvailable | None:
    data = st.session_state.get(SESSION_KEY_FILTERS)
    if not data:
        return None
    return FilterOptionsAvailable.model_validate(data)


def set_current_filters(cur: CurrentFilters) -> None:
    st.session_state[SESSION_KEY_FILTERS_CURRENT] = cur.model_dump()


def get_current_filters() -> CurrentFilters | None:
    data = st.session_state.get(SESSION_KEY_FILTERS_CURRENT)
    return None if not data else CurrentFilters.model_validate(data)
