# dashboard_checkboxes.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from utils.app_session import AppSession
from utils.ui import add_header_with_slider, get_time_control_tabs, load_validate_df, setup_global_page, time_filter_controls

st.set_page_config(page_title="ChessCom Analyzer • Dashboard", page_icon="📊", layout="wide")
PAGE_ID = "Dashboard"
setup_global_page(PAGE_ID)

def _kpi(df:pd.DataFrame):
    # KPIs
    total = len(df)
    win_rate = (df["user_result_simple"] == "win").sum() / total if total else 0.0
    draw_rate = (df["user_result_simple"] == "draw").sum() / total if total else 0.0
    loss_rate = (df["user_result_simple"] == "loss").sum() / total if total else 0.0
    
    avg_opp = df["opponent_rating"].mean()

    # simple rated delta: last minus first by end_time within rated games
    rated = df[df["rated"] == True].sort_values("end_time")
    rated_delta = (rated["user_rating"].iloc[-1] - rated["user_rating"].iloc[0]) if len(rated) >= 2 else 0

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Games", len(df))
    c2.metric("Win-rate", f"{win_rate:.0%}")
    c3.metric("Draw-rate", f"{draw_rate:.0%}")
    c4.metric("Loss-rate", f"{loss_rate:.0%}")
    c5.metric("Opponent Elo (Avg)", f"{avg_opp:.0f}" if np.isfinite(avg_opp) else "—")
    c6.metric("Rating Improvement", f"{rated_delta:+.0f}")

def _render_viz(df: pd.DataFrame):
    st.caption(f"{len(df)} games")
    if df.empty:
        st.info("No games for this selection.")
        return
    
    _kpi(df)


df = load_validate_df()
df = add_header_with_slider(df, "Dashboard")

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