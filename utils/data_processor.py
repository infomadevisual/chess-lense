from typing import Literal
import pandas as pd
import streamlit as st

def counts_by_opening(df: pd.DataFrame, merge_column: Literal["opening_name", "opening_fullname"], player_color: Literal["w", "b"]) -> pd.DataFrame:
    color = df["user_played_as"].str.lower().eq(player_color)
    counts = (
        df[color].groupby([merge_column])["user_result_simple"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["win", "draw", "loss"], fill_value=0)
        .reset_index()
    )
    if counts.empty:
        return counts

    counts["games"] = counts[["win", "draw", "loss"]].sum(axis=1)
    counts["win_rate"] = counts["win"] / counts["games"]

    return counts
