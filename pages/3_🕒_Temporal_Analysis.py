import streamlit as st
import pandas as pd
from utils.app_session import AppSession
from utils.ui import add_header_with_slider, get_time_control_tabs, inject_page_styles, load_validate_df, time_filter_controls 
import altair as alt

st.set_page_config(page_title="Temporal Analysis", page_icon="🕒", layout="wide")
inject_page_styles()

def _render_viz(df:pd.DataFrame):
    # ---- Add temporal columns ----
    df["year"] = df["end_time_local"].dt.year
    df["month"] = df["end_time_local"].dt.month
    df["weekday"] = df["end_time_local"].dt.day_name()
    df["hour"] = df["end_time_local"].dt.hour

    # ---- Aggregations ----
    # Hour
    tmp = (
        df.groupby("hour")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )

    counts = df.groupby("hour").size().rename("n").reset_index()
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

    # Weekday
    order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    weekday_long = (
        df.groupby("weekday")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )
    weekday_long["weekday"] = pd.Categorical(weekday_long["weekday"], categories=order, ordered=True)
    weekday_long = weekday_long.sort_values("weekday")
    counts = df.groupby("weekday").size().rename("n").reset_index()
    weekday_long = weekday_long.merge(counts, on="weekday", how="left")
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

    # Month
    tmp = (
        df.groupby("month")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )

    counts = df.groupby("month").size().rename("n").reset_index()
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
        
    # Year
    tmp = (
        df.groupby("year")["user_result_simple"]
        .value_counts(normalize=True)
        .rename("share")
        .reset_index()
    )

    counts = df.groupby("year").size().rename("n").reset_index()
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

# ---- Load Data and Apply filters ----
df = load_validate_df()
df = add_header_with_slider(df, "Temporal Analysis")

#--- Layout
top_labels, classes = get_time_control_tabs(df)
top_tabs = st.tabs(top_labels)
with top_tabs[0]:
    _render_viz(df)

for i, cls in enumerate(classes, start=1):
    with top_tabs[i]:
        scope = df[df["time_class"].str.lower().fillna("unknown") == cls]
        if scope.empty:
            st.info("No games in this class.")
            continue
        filtered = time_filter_controls(scope, key_prefix=f"tc_{cls}")
        _render_viz(filtered)

