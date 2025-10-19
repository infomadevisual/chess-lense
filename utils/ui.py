from typing import Literal, Tuple

import pandas as pd
import streamlit as st
from duckdb import DuckDBPyConnection

from services.duckdb_dao import count_rows, create_user_view
from services.services import get_data_manager
from utils.session import (
    CurrentFilters,
    TimeClass,
    TimeClassGamesCount,
    ensure_session_initialized,
    get_available_filters,
    get_session_username,
    get_session_username_normalized,
)


def setup_global_page(page_name: str, layout: Literal["wide", "centered"] = "wide"):
    ensure_session_initialized()

    st.set_page_config(
        page_title=f"ChessLense - {page_name}", page_icon="♟️", layout=layout
    )
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2.5rem !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
            }
            .stApp {
                padding: 0 !important;
                margin: 0 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    ap_key = "__active_page"
    v_key = f"__visit::{page_name}"
    if st.session_state.get(ap_key) != page_name:
        st.session_state[ap_key] = page_name
        st.session_state[v_key] = st.session_state.get(v_key, 0) + 1


def toast_once_page(page_id: str, key: str, text: str, icon: str = "ℹ️"):
    """Show once per page visit regardless of identical text."""
    v_key = f"__visit::{page_id}"
    reg_key = f"__toast_shown::{page_id}"
    visit = st.session_state.get(v_key, 0)
    reg = st.session_state.setdefault(reg_key, {})
    if reg.get(key) != visit:
        st.toast(text, icon=icon)
        reg[key] = visit


def load_validate_games() -> str:
    username = get_session_username()
    if username is None:
        st.warning(
            "No user provided. Go to 📥Load Games and load games of a user first."
        )
        st.stop()

    username_n = get_session_username_normalized()
    tz = st.context.timezone or "UTC"  # TODO: changes this from selection box
    path_to_games = get_data_manager().get_games_path(username_n)
    view = create_user_view(username_n, path_to_games, tz)
    if not view:
        st.warning("No games loaded. Go to 📥Load Games and load your games first.")
        st.stop()

    n = count_rows(view)
    if n == 0:
        st.warning("No games loaded. Go to 📥Load Games and load your games first.")
        st.stop()

    return view


def time_filter_controls(df_scope: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    # counts sorted desc by default
    s = df_scope["time_label"].astype("string")
    counts = s.value_counts()
    labels: list[str] = [str(x) for x in counts.index.tolist()]
    counts_map: dict[str, int] = {str(k): int(v) for k, v in counts.items()}

    options = [f"{lbl} ({counts_map[lbl]})" for lbl in labels]
    default = options  # select all
    selected_opts = st.pills(
        label="Time controls",
        options=options,
        selection_mode="multi",
        default=default,
        key=f"{key_prefix}_pills",
        label_visibility="collapsed",
    )

    selected_labels = [s.split(" (", 1)[0] for s in selected_opts]

    if not selected_labels:
        return df_scope.iloc[0:0]

    mask = df_scope["time_label"].astype(str).isin(selected_labels)
    return df_scope[mask]


# def add_header_with_slider(df_scope: pd.DataFrame, header_title: str) -> pd.DataFrame:
#     hdr_left, hdr_right = st.columns([1, 1])
#     with hdr_left:
#         st.header(header_title)
#     with hdr_right:
#         df_scope = _apply_rated_filter(df_scope, key_prefix="hdr")
#         return _add_year_slider(df_scope)


def _build_month_slider(available_months: list[str]) -> tuple[str, str]:
    st.markdown(
        """
        <style>
        div[data-testid="column"]:has(div[data-testid="stSelectSlider"]) { padding-top: 3rem; }
        </style>
    """,
        unsafe_allow_html=True,
    )
    start_lbl, end_lbl = st.select_slider(
        "Range",
        options=available_months,
        value=(available_months[0], available_months[-1]),
        key="month_slider",
        label_visibility="collapsed",
    )
    return start_lbl, end_lbl


def _build_time_class_filter_multi(
    available_time_classes: list[TimeClassGamesCount],
) -> tuple[list[TimeClass] | None, bool]:

    selected = []
    cols = st.columns(len(available_time_classes) + 1)

    for i, tc in enumerate(available_time_classes):
        with cols[i]:
            checked = st.checkbox(
                f"{tc[0].capitalize()} ({tc[1]})", value=True, key=f"time_class_{tc[0]}"
            )
        if checked:
            selected.append(tc[0])

    with cols[-1]:
        rated_only_checked = st.checkbox(
            f"Rated Only", value=True, key=f"rated_only_checkbox"
        )

    if not selected:
        return (None, rated_only_checked)
    return (selected, rated_only_checked)


def build_filters() -> CurrentFilters:
    available_filters = get_available_filters()
    time_class, rated_only = _build_time_class_filter_multi(
        available_filters.time_classes
    )
    start_lbl, end_lbl = _build_month_slider(available_filters.months)

    return CurrentFilters(
        month_start=start_lbl,
        month_end=end_lbl,
        time_classes=time_class,
        rated_only=rated_only,
    )
