import pandas as pd
import streamlit as st


def inject_page_styles():
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2.5rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
            .stApp {
                padding: 0 !important;
                margin: 0 !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

def time_filter_controls(df_scope: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    # counts sorted desc by default
    s = df_scope["time_label"].astype("string")
    counts = s.value_counts()
    labels: list[str] = [str(x) for x in counts.index.tolist()]
    counts_map: dict[str, int] = {str(k): int(v) for k, v in counts.items()}

    options = [f"{lbl} ({counts_map[lbl]})" for lbl in labels]
    default = options  # select all
    selected_opts = st.pills(
            label="Time controls",
            options=options,
            selection_mode="multi",
            default=default,
            key=f"{key_prefix}_pills",
            label_visibility="collapsed",
        )

    selected_labels = [s.split(" (", 1)[0] for s in selected_opts]

    if not selected_labels:
        return df_scope.iloc[0:0]

    mask = df_scope["time_label"].astype(str).isin(selected_labels)
    return df_scope[mask]

def add_year_slider(df_scope: pd.DataFrame) -> pd.DataFrame:
    st.markdown("""
    <style>
    div[data-testid="column"]:has(div[data-testid="stSelectSlider"]) {
        padding-top: 3rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # derive available months from end_time
    s = pd.to_datetime(df_scope["end_time_local"], errors="coerce")
    min_p, max_p = s.min().to_period("M"), s.max().to_period("M")
    months = []
    cur = min_p
    while cur <= max_p:
        months.append(cur)
        cur += 1
    labels = [p.strftime("%Y-%m") for p in months]
    start_lbl, end_lbl = st.select_slider(
        "Range", options=labels, value=(labels[0], labels[-1]),
        key="month_slider", label_visibility="collapsed",
    )
    start_p, end_p = pd.Period(start_lbl, "M"), pd.Period(end_lbl, "M")
    start_ts = start_p.to_timestamp(how="start").tz_localize("UTC")
    end_ts   = (end_p + 1).to_timestamp(how="start").tz_localize("UTC")
    t = pd.to_datetime(df_scope["end_time"], errors="coerce", utc=True)
    return df_scope[(t >= start_ts) & (t < end_ts)].copy()