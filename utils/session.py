from typing import Literal, TypeAlias

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ConfigDict, field_validator

SESSION_KEY_USERNAME = "username"
SESSION_KEY_FILTERS = "available_filters"
SESSION_KEY_FILTERS_CURRENT = "current_filters"

TimeClass: TypeAlias = Literal["bullet", "blitz", "rapid", "classic", "daily"]
TimeClassGamesCount: TypeAlias = tuple[TimeClass, int]

_TIMECLASS_ORDER = ["bullet", "blitz", "rapid", "classic", "daily"]


class FilterOptionsAvailable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    months: list[str]  # ["YYYY-MM", ...]
    rated: list[bool]  # e.g. [True, False]
    time_classes: list[TimeClassGamesCount]

    @field_validator("time_classes")
    def sort_time_classes(
        cls, v: list[TimeClassGamesCount]
    ) -> list[TimeClassGamesCount]:
        order = {tc: i for i, tc in enumerate(_TIMECLASS_ORDER)}
        return sorted(v, key=lambda x: order.get(x[0], len(order)))

    def to_period_index(self) -> pd.PeriodIndex:
        return pd.PeriodIndex(self.months, freq="M")


class CurrentFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")
    month_start: str | None = None  # "YYYY-MM"
    month_end: str | None = None  # "YYYY-MM"
    rated_only: bool = True  # False = both
    time_classes: list[TimeClass] | None = None  # None for all


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


def get_available_filters() -> FilterOptionsAvailable:
    data = st.session_state.get(SESSION_KEY_FILTERS)
    if not data:
        raise ValueError("Available filters not set in session")
    return FilterOptionsAvailable.model_validate(data)


def set_current_filters(cur: CurrentFilters) -> None:
    st.session_state[SESSION_KEY_FILTERS_CURRENT] = cur.model_dump()


def get_current_filters() -> CurrentFilters | None:
    data = st.session_state.get(SESSION_KEY_FILTERS_CURRENT)
    return None if not data else CurrentFilters.model_validate(data)
