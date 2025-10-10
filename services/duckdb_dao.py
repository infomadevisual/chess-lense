import hashlib
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import streamlit as st
from duckdb import DuckDBPyConnection
from pydantic import BaseModel

from services.services import get_duckdb
from utils.session import CurrentFilters


class Summary(BaseModel):
    total: int
    win_rate: float
    draw_rate: float
    loss_rate: float
    avg_opponent_rating: float | None = None
    rated_delta: int


def short_hash(s: str, length: int = 8) -> str:
    """Return a lowercase short hash of the input string."""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:length]


def create_openings_view(con: DuckDBPyConnection, openings_path: str):
    con.execute(
        f"""
        CREATE OR REPLACE VIEW openings AS
        SELECT * FROM parquet_scan('{openings_path}');
    """
    )


def create_user_view(
    username: str, games_path: Path, tz: str
) -> tuple[DuckDBPyConnection, str]:
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
    return con, view


def list_existing_columns(con: DuckDBPyConnection, view: str) -> set[str]:
    q = """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = ?
    """
    return {r[0] for r in con.execute(q, [view]).fetchall()}


def get_distinct_rated(con: DuckDBPyConnection, view: str) -> list[bool]:
    return [
        r[0]
        for r in con.execute(
            f"SELECT DISTINCT rated FROM {view} ORDER BY rated;"
        ).fetchall()
    ]


def get_distinct_time_class(con: DuckDBPyConnection, view: str) -> list[str]:
    return [
        r[0] for r in con.execute(f"SELECT DISTINCT time_class FROM {view};").fetchall()
    ]


def min_max_months_from_end_time(con: DuckDBPyConnection, view: str) -> tuple[str, str]:
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


def count_rows(con: DuckDBPyConnection, view: str) -> int:
    row = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()
    return int(row[0]) if row else 0


def sample_preview(con: DuckDBPyConnection, view: str, k: int = 10):
    cols_sql = ", ".join(list_existing_columns(con, view))
    return con.execute(
        f"""
        SELECT {cols_sql} FROM {view}
        ORDER BY random() LIMIT ?
    """,
        [k],
    ).fetch_df()


def winrate_by_timeclass(con: DuckDBPyConnection, view: str):
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


def rating_progress(con: DuckDBPyConnection, view: str, color: str):
    col = "white_rating" if color == "white" else "black_rating"
    return con.execute(
        f"""
        SELECT date_trunc('day', end_ts) AS d, AVG({col}) AS avg_rating, COUNT(*) AS games
        FROM {view}
        GROUP BY 1 ORDER BY 1
    """
    ).fetch_df()


def get_kpis(con: DuckDBPyConnection, view: str, filters: CurrentFilters) -> Summary:
    SQL = """
    WITH filtered AS (
    SELECT *
    FROM {view}
    WHERE 1=1
        {w_time}
        {w_class}
        {w_rated}
    ),
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
        COUNT(*)                                AS n_rated,
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

    w_time, w_class, w_rated = "", "", ""
    params: list[Any] = []
    start = (
        pd.Period(filters.month_start, freq="M").to_timestamp("M")
        if filters.month_start
        else None
    )
    end = (
        (pd.Period(filters.month_end, freq="M") + 1).to_timestamp("M")
        if filters.month_end
        else None
    )
    if start is not None:
        w_time += " AND end_time >= ?"
        params.append(pd.Timestamp(start).to_pydatetime())
    if end is not None:
        w_time += " AND end_time < ?"
        params.append(pd.Timestamp(end).to_pydatetime())

    if filters.time_class and filters.time_class != "All":
        w_class += " AND time_class = ?"
        params.append(filters.time_class)

    if filters.rated_only is True:
        w_rated += " AND rated = TRUE"
    elif filters.rated_only is False:
        w_rated += " AND rated = FALSE"

    q = SQL.format(view=view, w_time=w_time, w_class=w_class, w_rated=w_rated)
    cur = con.execute(q, params)  # used in both CTEs by position

    row = cur.fetchone()
    if not row:
        return Summary(
            total=0,
            win_rate=0.0,
            draw_rate=0.0,
            loss_rate=0.0,
            avg_opponent_rating=None,
            rated_delta=0,
        )
    cols = [d[0] for d in cur.description]
    return Summary.model_validate(dict(zip(cols, row)))
