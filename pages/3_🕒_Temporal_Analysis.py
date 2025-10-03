import streamlit as st
import pandas as pd
from utils.app_session import AppSession
from utils.ui import add_year_slider, inject_page_styles, time_filter_controls 
import altair as alt

st.set_page_config(page_title="Temporal Analysis", page_icon="🕒", layout="wide")
inject_page_styles()

session = AppSession.from_streamlit()
if session.game_count == 0:
    st.warning("No data loaded. Go back to Home and load games.")
    st.stop()

df = session.games_df.copy()

# ---- Apply filters ----
hdr_left, hdr_right = st.columns([1, 2])
with hdr_left:
    st.header("Temporal Analysis")

with hdr_right:
    df_range = add_year_slider(df)

df = time_filter_controls(df, key_prefix="temporal")

# ---- Add temporal columns ----
df_range["year"] = df_range["end_time_local"].dt.year
df_range["month"] = df_range["end_time_local"].dt.month
df_range["weekday"] = df_range["end_time_local"].dt.day_name()
df_range["hour"] = df_range["end_time_local"].dt.hour

# ---- Aggregations ----
tabs = st.tabs(["By Hour", "By Weekday", "By Month", "By Year"])

with tabs[0]:
    tmp = (
        df_range.groupby("hour")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )

    counts = df_range.groupby("hour").size().rename("n").reset_index()
    tmp = tmp.merge(counts, on="hour", how="left")
    tmp["label"] = tmp["hour"].astype(str) + " (" + tmp["n"].astype(str) + ")"

    tmp["hour"] = tmp["hour"].astype("Int64").astype(str)
    tmp["share"] = tmp["share"]*100
    tmp = tmp[tmp["share"] > 0]

    chart = (
        alt.Chart(tmp)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Hours", sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("share:Q", title="Share (%)"),
            color=alt.Color("user_result_simple:N", sort=["win","draw","loss"])
        )
    )
    st.altair_chart(chart, use_container_width=True)

with tabs[1]:
    order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    weekday_long = (
        df_range.groupby("weekday")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )

    # enforce order
    weekday_long["weekday"] = pd.Categorical(weekday_long["weekday"], categories=order, ordered=True)
    weekday_long = weekday_long.sort_values("weekday")

    # add counts per weekday
    counts = df_range.groupby("weekday").size().rename("n").reset_index()
    weekday_long = weekday_long.merge(counts, on="weekday", how="left")

    # build x labels and percentage
    weekday_long["label"] = weekday_long["weekday"].astype(str) + " (" + weekday_long["n"].astype(str) + ")"
    weekday_long["pct"] = weekday_long["share"] * 100

    chart = (
        alt.Chart(weekday_long)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Weekdays", sort=None, axis=alt.Axis(labelAngle=0, title=None)),
            y=alt.Y("pct:Q", title="Share (%)"),
            color=alt.Color("user_result_simple:N", sort=["win","draw","loss"])
        )
    )

    st.altair_chart(chart, use_container_width=True)

with tabs[2]:
    tmp = (
        df_range.groupby("month")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )

    counts = df_range.groupby("month").size().rename("n").reset_index()
    tmp = tmp.merge(counts, on="month", how="left")
    tmp["label"] = tmp["month"].astype(str) + " (" + tmp["n"].astype(str) + ")"

    tmp["month"] = tmp["month"].astype("Int64").astype(str)
    tmp["share"] = tmp["share"]*100
    tmp = tmp[tmp["share"] > 0]

    chart = (
        alt.Chart(tmp)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Months", sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("share:Q", title="Share (%)"),
            color=alt.Color("user_result_simple:N", sort=["win","draw","loss"])
        )
    )
    st.altair_chart(chart, use_container_width=True)
    
with tabs[3]:
    tmp = (
        df_range.groupby("year")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )

    counts = df_range.groupby("year").size().rename("n").reset_index()
    tmp = tmp.merge(counts, on="year", how="left")
    tmp["label"] = tmp["year"].astype(str) + " (" + tmp["n"].astype(str) + ")"

    tmp["year"] = tmp["year"].astype("Int64").astype(str)
    tmp["share"] = tmp["share"]*100
    tmp = tmp[tmp["share"] > 0]

    chart = (
        alt.Chart(tmp)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Years", sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("share:Q", title="Share (%)"),
            color=alt.Color("user_result_simple:N", sort=["win","draw","loss"])
        )
    )
    st.altair_chart(chart, use_container_width=True)