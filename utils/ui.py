from typing import Literal, Tuple

import pandas as pd
import streamlit as st
from duckdb import DuckDBPyConnection

from services.duckdb_dao import count_rows, create_user_view
from services.services import get_data_manager, get_duckdb
from utils.session import (
    CurrentFilters,
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


def load_validate_games() -> tuple[DuckDBPyConnection, str]:
    username = get_session_username()
    if username is None:
        st.warning(
            "No user provided. Go to 📥Load Games and load games of a user first."
        )
        st.stop()

    username_n = get_session_username_normalized()
    tz = st.context.timezone or "UTC"  # TODO: changes this from selection box
    path_to_games = get_data_manager().get_games_path(username_n)
    con, view = create_user_view(username_n, path_to_games, tz)
    if not view:
        st.warning("No games loaded. Go to 📥Load Games and load your games first.")
        st.stop()

    n = count_rows(con, view)
    if n == 0:
        st.warning("No games loaded. Go to 📥Load Games and load your games first.")
        st.stop()

    return con, view


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


def build_filters() -> CurrentFilters:
    available_filters = get_available_filters()
    if available_filters is None:
        st.warning(
            "No filters available. Something is really off. Please try to load data again."
        )
        st.stop()

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
        options=available_filters.months,
        value=(available_filters.months[0], available_filters.months[-1]),
        key="month_slider",
        label_visibility="collapsed",
    )
    return CurrentFilters(
        month_start=start_lbl,
        month_end=end_lbl,
        time_class="blitz",  # TODO:
        rated_only=True,  # TODO:
    )


def _add_year_slider(df_scope: pd.DataFrame) -> pd.DataFrame:
    st.markdown(
        """
    <style>
    div[data-testid="column"]:has(div[data-testid="stSelectSlider"]) { padding-top: 3rem; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # parse times
    s_local = pd.to_datetime(df_scope["end_time"], errors="coerce").dt.tz_convert(None)
    if s_local.dropna().empty:
        return df_scope.copy()

    min_p, max_p = s_local.min().to_period("M"), s_local.max().to_period("M")
    months: list[pd.Period] = []
    cur = min_p
    while cur <= max_p:
        months.append(cur)
        cur += 1

    labels = [p.strftime("%Y-%m") for p in months]
    end_idx = len(labels) - 1

    # timestamps for filtering
    t = pd.to_datetime(df_scope["end_time"], errors="coerce", utc=True)

    def _count(si: int, ei: int) -> int:
        start_ts = months[si].to_timestamp(how="start").tz_localize("UTC")
        end_ts = (months[ei] + 1).to_timestamp(how="start").tz_localize("UTC")
        mask = (t >= start_ts) & (t < end_ts)
        return int(mask.sum())

    # start with latest 12 months, then widen by 12 until >=1000 games or full range
    start_idx = max(0, end_idx - 11)
    while _count(start_idx, end_idx) < 1000 and start_idx > 0:
        start_idx = max(0, start_idx - 12)

    default_range = (labels[start_idx], labels[end_idx])

    start_lbl, end_lbl = st.select_slider(
        "Range",
        options=labels,
        value=default_range,
        key="month_slider",
        label_visibility="collapsed",
    )

    start_p, end_p = pd.Period(start_lbl, "M"), pd.Period(end_lbl, "M")
    start_ts = start_p.to_timestamp(how="start").tz_localize("UTC")
    end_ts = (end_p + 1).to_timestamp(how="start").tz_localize("UTC")
    return df_scope[(t >= start_ts) & (t < end_ts)].copy()


def _order_classes(classes):
    order = ["bullet", "blitz", "rapid", "daily", "classical"]
    lower = [c.lower() if isinstance(c, str) else "unknown" for c in classes]
    seen = set()
    ordered = [c for c in order if c in lower and not (c in seen or seen.add(c))]
    rest = [c for c in lower if c not in seen]
    return ordered + sorted(rest)


def get_time_control_tabs(df: pd.DataFrame) -> Tuple[list[str], list[str]]:
    total_n = len(df)
    class_counts = df["time_class"].fillna("unknown").str.lower().value_counts()
    classes = _order_classes(class_counts.index.tolist())
    top_labels = [f"All ({total_n})"] + [
        f"{c.title()} ({int(class_counts.get(c, 0))})" for c in classes
    ]
    return (top_labels, classes)


def _apply_rated_filter(df_scope: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    if "rated" not in df_scope.columns:
        return df_scope
    only_rated = st.checkbox(
        "Rated Games only", value=True, key=f"{key_prefix}__rated_only"
    )
    return df_scope[df_scope["rated"] == True] if only_rated else df_scope
