import streamlit as st
import pandas as pd
from utils.app_session import AppSession
from utils.ui import add_header_with_slider, get_time_control_tabs, load_validate_df, setup_global_page, time_filter_controls, toast_once_page 
import altair as alt

st.set_page_config(page_title="Seasonality Analysis", page_icon="🕒", layout="wide")
PAGE_ID = "Openings"
setup_global_page(PAGE_ID)

def _render_viz(df:pd.DataFrame):
    missing = int(df["end_time_local"].isna().sum())
    if missing > 0:
        toast_once_page("missing_timestamp", f"Ignored {missing} games with missing timestamp.", "ℹ️")

    # ---- Add temporal columns ----
    df["year"] = df["end_time_local"].dt.year
    df["month"] = df["end_time_local"].dt.month
    df["weekday"] = df["end_time_local"].dt.day_name()
    df["hour"] = df["end_time_local"].dt.hour

    # ---- Aggregations ----
    order_map = {"win": 0, "draw": 1, "loss": 2}
    color_legend=alt.Color("user_result_simple:N", sort= ["loss", "draw", "win"])
    bar_order=alt.Order("order_key:Q", sort="ascending")
    y_axis = alt.Y("share:Q", title="Share (%)")

    # Hour
    st.text(f"Hour of the day performance")
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
    tmp["order_key"] = tmp["user_result_simple"].map(order_map)

    chart = (
        alt.Chart(tmp)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Hours", sort=None, axis=alt.Axis(labelAngle=0)),
            y=y_axis,
            color=color_legend,
            order=bar_order
        )
    )
    st.altair_chart(chart, use_container_width=True)

    # Weekday
    st.text(f"Day of the week performance")
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
    weekday_long["share"] = weekday_long["share"] * 100
    weekday_long["order_key"] = weekday_long["user_result_simple"].map(order_map)

    chart = (
        alt.Chart(weekday_long)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Weekdays", sort=None, axis=alt.Axis(labelAngle=0, title=None)),
            y=y_axis,
            color=color_legend,
            order=bar_order
        )
    )

    st.altair_chart(chart, use_container_width=True)

    # Month
    st.text(f"Month of the year performance")
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
    tmp["order_key"] = tmp["user_result_simple"].map(order_map)

    chart = (
        alt.Chart(tmp)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Months", sort=None, axis=alt.Axis(labelAngle=0)),
            y=y_axis,
            color=color_legend,
            order=bar_order
        )
    )
    st.altair_chart(chart, use_container_width=True)
        
    # Year
    st.text(f"Yearly performance.")
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
    tmp["order_key"] = tmp["user_result_simple"].map(order_map)

    chart = (
        alt.Chart(tmp)
        .mark_bar()
        .encode(
            x=alt.X("label:N", title="Years", sort=None, axis=alt.Axis(labelAngle=0)),
            y=y_axis,
            color=color_legend,
            order=bar_order
        )
    )
    st.altair_chart(chart, use_container_width=True)

# ---- Load Data and Apply filters ----
df = load_validate_df()
df = add_header_with_slider(df, "🕒 Seasonality Analysis")

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

