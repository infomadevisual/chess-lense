import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import duckdb
import pandas as pd
import streamlit as st
from duckdb import DuckDBPyConnection
from pydantic import BaseModel

from utils.session import CurrentFilters, FilterOptionsAvailable, TimeClassGamesCount


class KpiSummary(BaseModel):
    total: int
    win_rate: float
    draw_rate: float
    loss_rate: float
    avg_opponent_rating: float | None = None
    rated_delta: int


class BestWorstOpening(BaseModel):
    opening_name: str
    color: Literal["white", "black"]
    games: int
    win_rate: float


@st.cache_resource
def get_duckdb() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    return con


logger = logging.getLogger("DuckDBDAO")


def short_hash(s: str, length: int = 8) -> str:
    """Return a lowercase short hash of the input string."""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:length]


def create_openings_view(openings_path: str):
    con = get_duckdb()
    con.execute(
        f"""
        CREATE OR REPLACE VIEW openings AS
        SELECT * FROM parquet_scan('{openings_path}');
    """
    )


def create_user_view(username: str, games_path: Path, tz: str) -> str:
    con = get_duckdb()
    con.execute(f"SET TimeZone = '{tz}';")

    view = f"games_{short_hash(username)}"

    con.execute(
        f"""
        CREATE OR REPLACE VIEW {view} AS
        SELECT
            *
        FROM parquet_scan('{games_path.as_posix()}');
    """
    )
    return view


def list_existing_columns(view: str) -> set[str]:
    con = get_duckdb()
    q = """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = ?
    """
    return {r[0] for r in con.execute(q, [view]).fetchall()}


def get_distinct_rated(view: str) -> list[bool]:
    con = get_duckdb()
    rows = con.execute(f"SELECT DISTINCT rated FROM {view} ORDER BY rated;").fetchall()
    return [r[0] for r in rows]


def get_distinct_time_class(view: str) -> list[TimeClassGamesCount]:
    con = get_duckdb()
    return con.execute(
        f"SELECT time_class, COUNT(*) FROM {view} GROUP BY time_class;"
    ).fetchall()


def min_max_months_from_end_time(view: str) -> tuple[datetime, datetime]:
    con = get_duckdb()
    min_max = con.execute(
        f"""
        SELECT
        date_trunc('month', MIN(end_time)) AS min_month,
        date_trunc('month', MAX(end_time)) AS max_month
        FROM {view};
    """
    ).fetchone()

    if min_max is None:
        raise ValueError("Cannot get min/max from end_time")

    return min_max


def count_rows(view: str) -> int:
    con = get_duckdb()
    row = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()
    return int(row[0]) if row else 0


def sample_preview(view: str, k: int = 10):
    con = get_duckdb()
    cols_sql = ", ".join(list_existing_columns(view))
    return con.execute(
        f"""
        SELECT {cols_sql} FROM {view}
        ORDER BY random() LIMIT ?
    """,
        [k],
    ).fetch_df()


def winrate_by_timeclass(view: str):
    con = get_duckdb()
    return con.execute(
        f"""
        SELECT time_class,
               AVG((CASE WHEN white_result='win' AND rules='chess' THEN 1
                         WHEN black_result='win' AND rules='chess' THEN 0
                         ELSE NULL END))::DOUBLE AS winrate_proxy
        FROM {view}
        GROUP BY 1
        ORDER BY 1
    """
    ).fetch_df()


def rating_progress(view: str, color: str):
    con = get_duckdb()
    col = "white_rating" if color == "white" else "black_rating"
    return con.execute(
        f"""
        SELECT date_trunc('day', end_ts) AS d, AVG({col}) AS avg_rating, COUNT(*) AS games
        FROM {view}
        GROUP BY 1 ORDER BY 1
    """
    ).fetch_df()


def _get_filtered_cte(
    view: str, filters: CurrentFilters, available_filters: FilterOptionsAvailable
) -> tuple[str, list[Any]]:
    sql = """
    WITH filtered AS (
    SELECT *
    FROM {view}
    WHERE 1=1
        {w_time}
        {w_class}
        {w_rated}
    )"""
    w_time, w_class, w_rated = "", "", ""
    params: list[Any] = []

    if filters.month_start != available_filters.months[0]:
        start = pd.Period(filters.month_start, freq="M").to_timestamp(how="start")
        w_time += " AND end_time >= ?"
        params.append(pd.Timestamp(start).to_pydatetime())

    if filters.month_end != available_filters.months[-1]:
        end = (pd.Period(filters.month_end, freq="M") + 1).to_timestamp(how="start")
        w_time += " AND end_time < ?"
        params.append(pd.Timestamp(end).to_pydatetime())

    if filters.time_classes:  # None or empty => no filter
        w_class += " AND time_class IN (SELECT * FROM UNNEST(?))"
        params.append(filters.time_classes)

    if filters.rated_only is True:
        w_rated += " AND rated = TRUE"

    return (
        sql.format(view=view, w_time=w_time, w_class=w_class, w_rated=w_rated),
        params,
    )


def get_kpis(
    view: str, filters: CurrentFilters, available_filters: FilterOptionsAvailable
) -> KpiSummary:
    filtered_cte = _get_filtered_cte(view, filters, available_filters)

    sql = (
        filtered_cte[0]
        + """
    ,
    base AS (
    SELECT
        COUNT(*)                            AS total,
        AVG(opponent_rating)                AS avg_opponent_rating,
        SUM(user_result_simple = 'win')     AS wins,
        SUM(user_result_simple = 'draw')    AS draws,
        SUM(user_result_simple = 'loss')    AS losses
    FROM filtered
    ),
    rated AS (
    SELECT
        COUNT(*)                          AS n_rated,
        arg_min(user_rating, end_time)    AS first_r,
        arg_max(user_rating, end_time)    AS last_r
    FROM filtered
    WHERE rated = TRUE
    )
    SELECT
    base.total,
    COALESCE(wins::DOUBLE  / NULLIF(base.total, 0), 0) AS win_rate,
    COALESCE(draws::DOUBLE / NULLIF(base.total, 0), 0) AS draw_rate,
    COALESCE(losses::DOUBLE/ NULLIF(base.total, 0), 0) AS loss_rate,
    base.avg_opponent_rating,
    CASE WHEN rated.n_rated >= 2 THEN last_r - first_r ELSE 0 END AS rated_delta
    FROM base CROSS JOIN rated;
    """
    )
    con = get_duckdb()
    logger.info("Executing KPI SQL: %s | ARGS: %s", sql, filtered_cte[1])
    cur = con.execute(sql, filtered_cte[1])  # used in both CTEs by position
    row = cur.fetchone()
    if not row:
        return KpiSummary(
            total=0,
            win_rate=0.0,
            draw_rate=0.0,
            loss_rate=0.0,
            avg_opponent_rating=None,
            rated_delta=0,
        )
    cols = [d[0] for d in cur.description]
    return KpiSummary.model_validate(dict(zip(cols, row)))


def get_best_worst_openings(
    con: DuckDBPyConnection,
    view: str,
    filters: CurrentFilters,
    color: Literal["white", "black"],
    top_n: int = 5,
) -> list[BestWorstOpening]:
    # TODO:
    pass
