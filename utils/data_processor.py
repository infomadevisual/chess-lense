import pandas as pd
import streamlit as st

@st.cache_data
def get_counts_by_opening(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # split by color
    is_white = df["user_played_as"].str.lower().eq("white")
    is_black = df["user_played_as"].str.lower().eq("black")

    w_counts = _counts_by_opening(df[is_white])
    b_counts = _counts_by_opening(df[is_black])

    return w_counts, b_counts

def _counts_by_opening(df: pd.DataFrame) -> pd.DataFrame:
    # Count openings
    counts = (
        df.groupby("opening_fullname")["user_result_simple"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["win", "draw", "loss"], fill_value=0)
        .reset_index()
    )
    if counts.empty:
        return counts

    counts["games"] = counts[["win", "draw", "loss"]].sum(axis=1)
    counts["win_rate"] = counts["win"] / counts["games"]

    # ECO (optional)
    if "eco" in df.columns:
        eco_map = (
            df.groupby("opening_fullname")["eco"]
            .agg(lambda x: x.mode().iat[0] if not x.mode().empty else None)
            .reset_index()
        )
        counts = counts.merge(eco_map, on="opening_fullname", how="left")
    return counts
