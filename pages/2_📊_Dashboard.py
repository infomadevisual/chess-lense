# dashboard_checkboxes.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from utils.app_session import AppSession
from utils.ui import add_year_slider, inject_page_styles, time_filter_controls

st.set_page_config(page_title="ChessCom Analyzer • Dashboard", page_icon="📊", layout="wide")

_ORDER = ["bullet", "blitz", "rapid", "daily", "classical"]

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

def _order_classes(classes):
    lower = [c.lower() if isinstance(c, str) else "unknown" for c in classes]
    seen = set()
    ordered = [c for c in _ORDER if c in lower and not (c in seen or seen.add(c))]
    rest = [c for c in lower if c not in seen]
    return ordered + sorted(rest)

inject_page_styles()
st.markdown("""
<style>
div[data-testid="column"]:has(div[data-testid="stSelectSlider"]) {
    padding-top: 3rem;
}
</style>
""", unsafe_allow_html=True)

session = AppSession.from_streamlit()
df = session.games_df
if df is None or df.empty:
    st.warning("No games loaded. Go to Home and load your games first.")
    st.stop()

if session.username is None:
    st.error("No user loaded. Go to Home and load your games first.")
    st.stop()

total_n = len(df)
class_counts = df["time_class"].fillna("unknown").str.lower().value_counts()
classes = _order_classes(class_counts.index.tolist())

top_labels = [f"All ({total_n})"] + [f"{c.title()} ({int(class_counts.get(c, 0))})" for c in classes]

# --- Layout
hdr_left, hdr_right = st.columns([1, 2])

with hdr_left:
    st.header("Dashboard")

with hdr_right:
    df_range = add_year_slider(df)

top_tabs = st.tabs(top_labels)
with top_tabs[0]:
    _render_viz(df_range)

for i, cls in enumerate(classes, start=1):
    with top_tabs[i]:
        scope = df_range[df_range["time_class"].str.lower().fillna("unknown") == cls]
        if scope.empty:
            st.info("No games in this class.")
            continue
        filtered = time_filter_controls(scope, key_prefix=f"tc_{cls}")
        _render_viz(filtered)
