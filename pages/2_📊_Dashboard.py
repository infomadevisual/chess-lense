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

@st.cache_data(show_spinner=False)
def _daily_last(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    d = (df[df["rated"] == True]
         .dropna(subset=["end_time", "user_rating"])
         .sort_values("end_time")
         .loc[:, ["end_time", "user_rating", "opponent_rating", "time_class"]]
         .copy())
    d["date"] = d["end_time"].dt.normalize()
    return (d.groupby(["time_class", "date"], as_index=False)
              .agg(user_rating=("user_rating", "last"),
                   opponent_rating=("opponent_rating", "mean")))

def _rating_progress_daily(df: pd.DataFrame, title: str, multi: bool) -> alt.Chart | None:
    d = _daily_last(df)
    if d.empty:
        return None

    dmin, dmax = d["date"].min(), d["date"].max()
    n_months = (dmax.year - dmin.year) * 12 + (dmax.month - dmin.month) + 1
    if n_months <= 18:
        tick = {"interval": "month", "step": 1}; fmt = "%b %Y"
    elif n_months <= 48:
        tick = {"interval": "month", "step": 3}; fmt = "%b %Y"
    else:
        tick = {"interval": "year", "step": 1}; fmt = "%Y"

    x = alt.X("date:T", title="Date",
              axis=alt.Axis(format=fmt, labelAngle=0, tickCount=tick, labelOverlap=False),
              scale=alt.Scale(nice={"interval": tick["interval"], "step": tick["step"]}))
    y = alt.Y("user_rating:Q", title="Rating")

    base = alt.Chart(d).properties(title=title)
    if multi:
        tooltips = [
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("user_rating:Q", title="Rating", format=".0f"),
            alt.Tooltip("time_class:N", title="Class"),
        ]
        return base.mark_line().encode(x=x, y=y,
                                       color=alt.Color("time_class:N", title="Class",
                                                       sort=["bullet","blitz","rapid","daily","classical"]),
                                       tooltip=tooltips)
    else:
        tooltips = [
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("user_rating:Q", title="Rating", format=".0f"),
        ]
        return base.mark_line().encode(x=x, y=y, tooltip=tooltips)


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

def _render_viz(df: pd.DataFrame, tab_name: str, multi: bool = False):
    if df.empty:
        st.info(f"No games in this selection ({tab_name})."); return

    _kpi(df)

    chart = _rating_progress_daily(df, title=f"{tab_name} rating", multi=multi)
    if chart is None:
        st.info("No daily points after aggregation.")
    else:
        st.altair_chart(chart, use_container_width=True)

df = load_validate_df()
df = add_header_with_slider(df, "Dashboard")

#--- Layout
top_labels, classes = get_time_control_tabs(df)
top_tabs = st.tabs(top_labels)
with top_tabs[0]:
    _render_viz(df, "All", multi=True)

for i, cls in enumerate(classes, start=1):
    with top_tabs[i]:
        scope = df[df["time_class"].str.lower().fillna("unknown") == cls]
        if scope.empty:
            st.info(f"No games in {cls.title()}.")
            continue
        filtered = time_filter_controls(scope, key_prefix=f"tc_{cls}")
        _render_viz(filtered, tab_name=cls.title(), multi=False)