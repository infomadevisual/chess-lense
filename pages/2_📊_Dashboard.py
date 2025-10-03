# dashboard_checkboxes.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from app_session import AppSession
from ui import inject_page_styles, time_filter_controls

_ORDER = ["bullet", "blitz", "rapid", "daily", "classical"]

DRAW_CODES = {"stalemate","agreed","repetition","insufficient","threecheck","50move","timevsinsufficient","abandoned"}  # be liberal

def _perspective_cols(df: pd.DataFrame, me: str) -> pd.DataFrame:
    me = (me or "").strip().lower()
    is_white = df["white_username"].str.lower().eq(me)
    is_black = df["black_username"].str.lower().eq(me)

    # opponent rating
    opp_rating = np.where(is_white, df["black_rating"], df["white_rating"])
    my_rating  = np.where(is_white, df["white_rating"], df["black_rating"])

    # perspective result
    wr = df["white_result"].fillna("").str.lower()
    br = df["black_result"].fillna("").str.lower()

    win  = (is_white & wr.eq("win")) | (is_black & br.eq("win"))
    loss = (is_white & br.eq("win")) | (is_black & wr.eq("win"))
    draw = (
        (is_white & wr.isin(DRAW_CODES)) |
        (is_black & br.isin(DRAW_CODES)) |
        # fallback: both not "win" and not empty -> treat as draw-ish
        (~win & ~loss & (wr.ne("") | br.ne("")))
    )

    result = np.where(win, "win", np.where(draw, "draw", np.where(loss, "loss", "other")))
    color  = np.where(is_white, "white", np.where(is_black, "black", "unknown"))

    out = df.copy()
    out["me_color"] = color
    out["opp_rating"] = pd.to_numeric(opp_rating, errors="coerce")
    out["my_rating"]  = pd.to_numeric(my_rating, errors="coerce")
    out["result_me"]  = result
    # monthly bucket
    if "end_time" in out.columns:
        out["month"] = pd.to_datetime(out["end_time"], utc=True, errors="coerce").dt.to_period("M").dt.to_timestamp()
    return out

def _kpi(win_rate: float, n: int, avg_opp: float, rated_delta: float):
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Games", n)
    c2.metric("Win-rate", f"{win_rate:.0%}")
    c3.metric("Avg opp Elo", f"{avg_opp:.0f}" if np.isfinite(avg_opp) else "—")
    c4.metric("Rated Δ (latest-first)", f"{rated_delta:+.0f}")

def _render_viz(df: pd.DataFrame, username:str):
    st.caption(f"{len(df)} games")
    if df.empty:
        st.info("No games for this selection.")
        return
    
    dfp = _perspective_cols(df, username)
    dfp = dfp.dropna(subset=["end_time"])
    # KPIs
    wins = (dfp["result_me"] == "win").sum()
    draws = (dfp["result_me"] == "draw").sum()
    total = len(dfp)
    win_rate = wins / total if total else 0.0
    avg_opp = dfp["opp_rating"].mean()
    # simple rated delta: last minus first by end_time within rated games
    rated = dfp[dfp["rated"] == True].sort_values("end_time")
    rated_delta = (rated["my_rating"].iloc[-1] - rated["my_rating"].iloc[0]) if len(rated) >= 2 else 0
    _kpi(win_rate, total, avg_opp, rated_delta)

def _order_classes(classes):
    lower = [c.lower() if isinstance(c, str) else "unknown" for c in classes]
    seen = set()
    ordered = [c for c in _ORDER if c in lower and not (c in seen or seen.add(c))]
    rest = [c for c in lower if c not in seen]
    return ordered + sorted(rest)

def run():
    inject_page_styles()
    st.markdown("""
    <style>
    div[data-testid="column"]:has(div[data-testid="stSelectSlider"]) {
        padding-top: 3rem;
    }
    </style>
    """, unsafe_allow_html=True)

    st.set_page_config(page_title="ChessCom Analyzer • Dashboard", page_icon="📊", layout="wide")

    session = AppSession.from_streamlit()
    df = session.games_df
    if df is None or df.empty:
        st.warning("No games loaded. Go to Home and load your games first.")
        return

    if session.username is None:
        st.error("No user loaded. Go to Home and load your games first.")
        return

    total_n = len(df)
    class_counts = df["time_class"].fillna("unknown").str.lower().value_counts()
    classes = _order_classes(class_counts.index.tolist())

    top_labels = [f"All ({total_n})"] + [f"{c.title()} ({int(class_counts.get(c, 0))})" for c in classes]
    
    # --- Layout
    hdr_left, hdr_right = st.columns([1, 2])

    with hdr_left:
        st.header("Dashboard")

    with hdr_right:
            # derive available months from end_time
        s = pd.to_datetime(df["end_time"], utc=True, errors="coerce").dropna()
        if s.empty:
            df_range = df.copy()
        else:
            min_p = s.min().to_period("M")
            max_p = s.max().to_period("M")

            # build labels YYYY-MM
            months = []
            cur = min_p
            while cur <= max_p:
                months.append(cur)
                cur += 1
            labels = [p.strftime("%Y-%m") for p in months]

        start_lbl, end_lbl = st.select_slider(
            "Range",
            options=labels,
            value=(labels[0], labels[-1]),
            key="month_slider",
            label_visibility="collapsed",
        )

    # compute filtered df once
    start_p = pd.Period(start_lbl, freq="M")
    end_p   = pd.Period(end_lbl, freq="M")
    start_ts = start_p.to_timestamp(how="start").tz_localize("UTC")
    end_ts   = (end_p + 1).to_timestamp(how="start").tz_localize("UTC")
    t = pd.to_datetime(df["end_time"], errors="coerce", utc=True)
    df_range = df[(t >= start_ts) & (t < end_ts)].copy()

    top_tabs = st.tabs(top_labels)
    with top_tabs[0]:
        _render_viz(df_range, session.username)

    for i, cls in enumerate(classes, start=1):
        with top_tabs[i]:
            scope = df_range[df_range["time_class"].str.lower().fillna("unknown") == cls]
            if scope.empty:
                st.info("No games in this class.")
                continue
            filtered = time_filter_controls(scope, key_prefix=f"tc_{cls}")
            _render_viz(filtered, session.username)

if __name__ == "__main__":
    run()
