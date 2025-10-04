import time
import streamlit as st
import pandas as pd
import altair as alt
from utils.app_session import AppSession
from utils.ui import add_header_with_slider, get_time_control_tabs, load_validate_df, setup_global_page, time_filter_controls, toast_once_page
from urllib.parse import urlparse, unquote
import re

st.set_page_config(page_title="ChessCom Analyzer • Openings", page_icon="📖", layout="wide")
PAGE_ID = "Openings"
setup_global_page(PAGE_ID)

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

    # after computing `missing`
    missing = int(df["opening"].isna().sum())
    if missing > 0:
        toast_once_page(PAGE_ID, "missing_opening", f"Ignored {missing} games with missing opening.", "ℹ️")

    df = df.dropna(subset=["opening"])

    # Count openings
    counts = (
        df.groupby("opening")["user_result_simple"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["win", "draw", "loss"], fill_value=0)
        .reset_index()
    )

    if counts.empty:
        st.warning("No data available for the selected filters.")
        st.stop()

    # Winrate
    counts["games"] = counts.sum(axis=1, numeric_only=True)
    counts["win_rate"] = counts["win"] / counts["games"]

    # Top 15 openings by number of games
    top_n = 10
    st.text(f"Top {top_n} openings played showing your win-rate from white (low) to blue (high)")
    top = counts.sort_values("games", ascending=False).head(top_n)
    top["opening_wrapped"] = top["opening"].str.replace(" ", "\n", 2)

    row_height = 50

    chart = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            y=alt.Y("opening:N", sort="-x", title=None,
                    axis=alt.Axis(labelLimit=600)),  # no truncation
            x=alt.X("games:Q", title="# Games"),
            color=alt.Color("win_rate:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["opening", "games", "win", "draw", "loss",
                    alt.Tooltip("win_rate:Q", format=".1%")]
        )
    ).properties(height=row_height * len(top))

    st.altair_chart(chart, use_container_width=True)

    top_n = 100
    st.text(f"Top {top_n} openings played and win-rate")
    cols = ["opening", "games", "win_rate", "win", "draw", "loss"]  # desired order
    st.dataframe(counts[cols].sort_values("games", ascending=False).head(top_n))

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


