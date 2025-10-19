# dashboard_checkboxes.py
import logging
from typing import Literal, Optional, Tuple

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from services.duckdb_dao import KpiSummary, get_kpis
from utils.data_processor import counts_by_opening
from utils.session import get_available_filters
from utils.ui import build_filters, load_validate_games, setup_global_page

setup_global_page("📊 Dashboard")

logger = logging.getLogger("Dashboard")


def _daily_last(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    d = (
        df[df["rated"] == True]
        .dropna(subset=["end_time_local", "user_rating"])
        .sort_values("end_time_local")
        .loc[:, ["end_time_local", "user_rating", "opponent_rating", "time_class"]]
        .copy()
    )
    d["date"] = d["end_time_local"].dt.normalize()
    return d.groupby(["time_class", "date"], as_index=False).agg(
        user_rating=("user_rating", "last"), opponent_rating=("opponent_rating", "mean")
    )


def get_best_worst_openings(
    counts_df: pd.DataFrame,
) -> Optional[Tuple[pd.Series, pd.Series]]:
    if counts_df is None or counts_df.empty:
        return None

    df = counts_df.copy()

    # Ensure required metrics exist
    if "games" not in df.columns:
        df["games"] = df.get("win", 0) + df.get("draw", 0) + df.get("loss", 0)

    if "win_rate" not in df.columns:
        # avoid division by zero
        denom = df["games"].replace({0: np.nan})
        df["win_rate"] = df.get("win", 0) / denom
        df["win_rate"] = df["win_rate"].fillna(0.0)

    # Filter with fallback
    scope = df[df["games"] >= 20]
    if scope.empty:
        scope = df[df["games"] >= 10]
    if scope.empty:
        scope = df

    # Pick best and worst
    best = scope.sort_values(["win_rate", "games"], ascending=[False, False]).iloc[0]
    worst = scope.sort_values(["win_rate", "games"], ascending=[True, False]).iloc[0]
    return best, worst


def _rating_progress_daily(
    df: pd.DataFrame, title: str, multi: bool
) -> alt.Chart | None:
    d = _daily_last(df)
    if d.empty:
        return None

    dmin, dmax = d["date"].min(), d["date"].max()
    n_months = (dmax.year - dmin.year) * 12 + (dmax.month - dmin.month) + 1
    if n_months <= 18:
        tick = {"interval": "month", "step": 1}
        fmt = "%b %Y"
    elif n_months <= 48:
        tick = {"interval": "month", "step": 3}
        fmt = "%b %Y"
    else:
        tick = {"interval": "year", "step": 1}
        fmt = "%Y"

    x = alt.X(
        "date:T",
        title="Date",
        axis=alt.Axis(format=fmt, labelAngle=0, tickCount=tick, labelOverlap=False),
        scale=alt.Scale(nice={"interval": tick["interval"], "step": tick["step"]}),
    )
    y = alt.Y("user_rating:Q", title="Rating")

    base = alt.Chart(d).properties(title=title)
    if multi:
        tooltips = [
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("user_rating:Q", title="Rating", format=".0f"),
            alt.Tooltip("time_class:N", title="Class"),
        ]
        return base.mark_line().encode(
            x=x,
            y=y,
            color=alt.Color(
                "time_class:N",
                title="Class",
                sort=["bullet", "blitz", "rapid", "daily", "classical"],
            ),
            tooltip=tooltips,
        )
    else:
        tooltips = [
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("user_rating:Q", title="Rating", format=".0f"),
        ]
        return base.mark_line().encode(x=x, y=y, tooltip=tooltips)


def _kpi(df: pd.DataFrame):
    # KPIs
    total = len(df)
    win_rate = (df["user_result_simple"] == "win").sum() / total if total else 0.0
    draw_rate = (df["user_result_simple"] == "draw").sum() / total if total else 0.0
    loss_rate = (df["user_result_simple"] == "loss").sum() / total if total else 0.0

    avg_opp = df["opponent_rating"].mean()

    # simple rated delta: last minus first by end_time within rated games
    rated = df[df["rated"] == True].sort_values("end_time_local")
    rated_delta = (
        (rated["user_rating"].iloc[-1] - rated["user_rating"].iloc[0])
        if len(rated) >= 2
        else 0
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Games", len(df), border=True)
    c2.metric("Win rate", f"{win_rate:.0%}", border=True)
    c3.metric("Draw rate", f"{draw_rate:.0%}", border=True)
    c4.metric("Loss rate", f"{loss_rate:.0%}", border=True)
    c5.metric(
        "⌀ Elo Opp", f"{avg_opp:.0f}" if np.isfinite(avg_opp) else "—", border=True
    )
    c6.metric("⌀ Elo Delta", f"{rated_delta:+.0f}", border=True)


def show_opening_kpis(label: str, data):
    if data is None:
        st.warning(f"No openings as {label}")
        return

    def get_metric(row, best_or_worst: Literal["Best", "Worst"]):
        st.markdown(
            """
        <style>
        [data-testid="stMetricValue"] {
            font-size: 1.5rem !important; /* default is ~2.5rem */
        }
        </style>
        """,
            unsafe_allow_html=True,
        )
        return st.metric(
            width="stretch",
            label=f"{best_or_worst} Opening for {label} ({row.games} games and {row.win_rate*100:.1f}% win-rate)",
            value=f"{row.opening_name}",
            help=f"With a minimum of 20/10/1 games depending on availability (# games: {row.games})",
            border=True,
        )

    best, worst = data
    c1, c2 = st.columns(2)
    with c1:
        get_metric(best, "Best")
    with c2:
        get_metric(worst, "Worst")


def _render_viz(df: pd.DataFrame, tab_name: str, multi: bool = False):
    if df.empty:
        st.info(f"No games in this selection ({tab_name}).")
        return

    _kpi(df)

    w_counts = counts_by_opening(df, "opening_name", "white")
    b_counts = counts_by_opening(df, "opening_name", "black")
    show_opening_kpis("White", get_best_worst_openings(w_counts))
    show_opening_kpis("Black", get_best_worst_openings(b_counts))

    chart = _rating_progress_daily(df, title=f"{tab_name} rating", multi=multi)
    if chart is None:
        st.info("No daily points after aggregation.")
    else:
        st.altair_chart(chart, use_container_width=True)


def render_kpi_cards(summary: KpiSummary):
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Games", summary.total, border=True)
    c2.metric("Win rate", f"{summary.win_rate:.0%}", border=True)
    c3.metric("Draw rate", f"{summary.draw_rate:.0%}", border=True)
    c4.metric("Loss rate", f"{summary.loss_rate:.0%}", border=True)
    c5.metric(
        "⌀ Elo Opp",
        (
            f"{summary.avg_opponent_rating:.0f}"
            if summary.avg_opponent_rating is not None
            else "—"
        ),
        border=True,
    )
    c6.metric("⌀ Elo Delta", f"{summary.rated_delta:+.0f}", border=True)


view = load_validate_games()

current_filters = build_filters()
logger.info(f"Current Filters: {current_filters}")

# KPIs
available_filters = get_available_filters()
render_kpi_cards(get_kpis(view, current_filters, available_filters))
