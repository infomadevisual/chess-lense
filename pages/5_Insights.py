# dashboard_checkboxes.py
from typing import Any, Literal
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from utils.app_session import AppSession
from utils.data_processor import get_counts_by_opening_fullname
from utils.ui import add_header_with_slider, get_time_control_tabs, load_validate_df, setup_global_page, time_filter_controls

st.set_page_config(page_title="ChessCom Analyzer • Dashboard", page_icon="📊", layout="wide")
PAGE_ID = "Insights"
setup_global_page(PAGE_ID)


def _render_viz(df: pd.DataFrame, tab_name: str, multi: bool = False):
    st.info("Hi")

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