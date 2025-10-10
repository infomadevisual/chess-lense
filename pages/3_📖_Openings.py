from typing import Literal

import altair as alt
import pandas as pd
import streamlit as st

from utils.data_processor import counts_by_opening
from utils.ui import (
    add_header_with_slider,
    get_time_control_tabs,
    load_validate_games,
    setup_global_page,
    time_filter_controls,
    toast_once_page,
)

PAGE_ID = "📖 Openings"
setup_global_page(PAGE_ID)


def _chart_top(
    counts: pd.DataFrame,
    column_name: Literal["opening_fullname", "opening_name"],
    title_prefix: str,
    top_n: int = 10,
):
    top = counts.sort_values("games", ascending=False).head(top_n)
    row_height = 50
    chart = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            y=alt.Y(
                f"{column_name}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=600)
            ),
            x=alt.X("games:Q", title="# Games"),
            color=alt.Color("win_rate:Q", scale=alt.Scale(scheme="blues")),
            tooltip=[
                column_name,
                alt.Tooltip("eco:N", title="ECO"),
                "games",
                "win",
                "draw",
                "loss",
                alt.Tooltip("win_rate:Q", format=".1%"),
            ],
        )
    ).properties(
        height=row_height * len(top),
        title=f"{title_prefix}: Top {top_n} openings (win rate color)",
    )
    return chart


def _render_viz(
    df: pd.DataFrame, column_name: Literal["opening_fullname", "opening_name"]
):
    # info toast once
    missing = int(df[column_name].isna().sum())
    if missing > 0:
        toast_once_page(
            PAGE_ID,
            "missing_opening",
            f"Ignored {missing} games with missing opening.",
            "ℹ️",
        )
    df = df.dropna(subset=[column_name])

    w_counts = counts_by_opening(df, column_name, "white")
    b_counts = counts_by_opening(df, column_name, "black")

    if w_counts.empty and b_counts.empty:
        st.warning("No data available for the selected filters.")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        if w_counts.empty:
            st.info("No games as White.")
        else:
            st.altair_chart(
                _chart_top(w_counts, column_name, "White"), use_container_width=True
            )
            st.text("White — Top 100 openings")
            cols = [column_name, "games", "win_rate", "win", "draw", "loss"]
            st.dataframe(w_counts[cols].sort_values("games", ascending=False).head(100))

    with c2:
        if b_counts.empty:
            st.info("No games as Black.")
        else:
            st.altair_chart(
                _chart_top(b_counts, column_name, "Black"), use_container_width=True
            )
            st.text("Black — Top 100 openings")
            cols = [column_name, "games", "win_rate", "win", "draw", "loss"]
            st.dataframe(b_counts[cols].sort_values("games", ascending=False).head(100))


def _get_radio_option(key_prefix: str):
    # ---- Select level of detail ----
    option = st.radio(
        "Opening Filter",
        key=f"{key_prefix}_opening_radio",
        label_visibility="collapsed",
        options=["Openings only", "Openings with Variations"],
        index=0,
        horizontal=True,
    )
    return "opening_name" if option == "Openings only" else "opening_fullname"


# ---- Load Data and Apply filters ----
load_validate_games()
df = add_header_with_slider(df, "📖 Openings Analysis")

# --- Layout
top_labels, classes = get_time_control_tabs(df)
top_tabs = st.tabs(top_labels)

with top_tabs[0]:
    c = _get_radio_option(key_prefix="all")
    _render_viz(df, c)

for i, cls in enumerate(classes, start=1):
    with top_tabs[i]:
        scope = df[df["time_class"].str.lower().fillna("unknown") == cls]
        if scope.empty:
            st.info("No games in this class.")
            continue
        filtered = time_filter_controls(scope, key_prefix=f"tc_{cls}")
        c = _get_radio_option(key_prefix=cls)
        _render_viz(filtered, c)
