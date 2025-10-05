import time
import streamlit as st
import pandas as pd
import altair as alt
from utils.app_session import AppSession
from utils.data_processor import get_counts_by_opening
from utils.openings_catalog import _load_openings_catalog
from utils.ui import add_header_with_slider, get_time_control_tabs, load_validate_df, setup_global_page, time_filter_controls, toast_once_page

st.set_page_config(page_title="ChessCom Analyzer • Openings", page_icon="📖", layout="wide")
PAGE_ID = "Openings"
setup_global_page(PAGE_ID)

def _chart_top(counts: pd.DataFrame, title_prefix: str, top_n: int = 10):
    top = counts.sort_values("games", ascending=False).head(top_n)
    row_height = 50
    chart = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            y=alt.Y("opening_fullname:N", sort="-x", title=None,
                    axis=alt.Axis(labelLimit=600)),
            x=alt.X("games:Q", title="# Games"),
            color=alt.Color("win_rate:Q", scale=alt.Scale(scheme="blues")),
            tooltip=[
                "opening_fullname",
                alt.Tooltip("eco:N", title="ECO"),
                "games","win","draw","loss",
                alt.Tooltip("win_rate:Q", format=".1%")
            ],
        )
    ).properties(
        height=row_height * len(top),
        title=f"{title_prefix}: Top {top_n} openings (win-rate color)"
    )
    return chart


def _render_viz(df: pd.DataFrame):
    # info toast once
    missing = int(df["opening_fullname"].isna().sum())
    if missing > 0:
        toast_once_page(PAGE_ID, "missing_opening", f"Ignored {missing} games with missing opening.", "ℹ️")
    df = df.dropna(subset=["opening_fullname"])

    w_counts, b_counts = get_counts_by_opening(df)

    if w_counts.empty and b_counts.empty:
        st.warning("No data available for the selected filters.")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        if w_counts.empty:
            st.info("No games as White.")
        else:
            st.altair_chart(_chart_top(w_counts, "White"), use_container_width=True)
            st.text("White — Top 100 openings")
            cols = ["opening_fullname","games","win_rate","win","draw","loss"]
            st.dataframe(w_counts[cols].sort_values("games", ascending=False).head(100))

    with c2:
        if b_counts.empty:
            st.info("No games as Black.")
        else:
            st.altair_chart(_chart_top(b_counts, "Black"), use_container_width=True)
            st.text("Black — Top 100 openings")
            cols = ["opening_fullname","games","win_rate","win","draw","loss"]
            st.dataframe(b_counts[cols].sort_values("games", ascending=False).head(100))


# ---- Load Data and Apply filters ----
df = load_validate_df()
df = add_header_with_slider(df, "📖 Openings Analysis")

#--- Layout
top_labels, classes = get_time_control_tabs(df)
top_tabs = st.tabs(top_labels)
with top_tabs[0]:
    _render_viz(df)

for i, cls in enumerate(classes, start=1):
    with top_tabs[i]:
        scope = df[df["time_class"].str.lower().fillna("unknown") == cls]
        if scope.empty:
            st.info("No games in this class.")
            continue
        filtered = time_filter_controls(scope, key_prefix=f"tc_{cls}")
        _render_viz(filtered)


