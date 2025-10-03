import streamlit as st
import pandas as pd
import altair as alt
from utils.app_session import AppSession
from utils.ui import add_header_with_slider, get_time_control_tabs, inject_page_styles, load_validate_df, time_filter_controls
from urllib.parse import urlparse, unquote
import re

st.set_page_config(page_title="ChessCom Analyzer • Openings", page_icon="📖", layout="wide")
inject_page_styles()

def _opening_from_eco_url(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        slug = unquote(urlparse(url).path.strip("/").split("/")[-1])
        slug = slug.replace("-", " ").strip()
        # drop move list like " ... 1.e4 e5 2.Nf3 Nc6"
        name = re.split(r"\s+\d+\.", slug, maxsplit=1)[0].strip()
        return name or None
    except Exception:
        return None

def _render_viz(df:pd.DataFrame):
    if "eco_url" in df.columns:
        df["opening"] = df["eco_url"].apply(_opening_from_eco_url)
    else:
        df["opening"] = None  # placeholder if nothing available

    # Count openings
    counts = (
        df.groupby("opening")["user_result_simple"]
        .value_counts()
        .unstack(fill_value=0)
        .reset_index()
    )

    # Winrate
    counts["games"] = counts.sum(axis=1, numeric_only=True)
    counts["win_rate"] = counts["win"] / counts["games"]

    # Top 15 openings by number of games
    top = counts.sort_values("games", ascending=False).head(10)

    chart = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            x=alt.X("opening:N", sort="-y", title="Opening"),
            y=alt.Y("games:Q", title="# Games"),
            color=alt.Color("win_rate:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["opening", "games", "win", "draw", "loss", "win_rate"]
        )
    )

    st.altair_chart(chart, use_container_width=True)

    st.dataframe(counts.sort_values("games", ascending=False).head(100))

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


