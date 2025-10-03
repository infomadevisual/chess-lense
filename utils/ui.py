from typing import Tuple
import pandas as pd
import streamlit as st

from utils.app_session import AppSession


def load_validate_df() -> pd.DataFrame:
    session = AppSession.from_streamlit()
    df = session.games_df
    if df is None or df.empty:
        st.warning("No games loaded. Go to Home and load your games first.")
        st.stop()

    if session.username is None:
        st.error("No user loaded. Go to Home and load your games first.")
        st.stop()

    return df.copy()

def inject_page_styles():
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2.5rem !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
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

def add_header_with_slider(df_scope: pd.DataFrame, header_title:str) -> pd.DataFrame:
    hdr_left, hdr_right = st.columns([1, 1])
    with hdr_left:
        st.header(header_title)

    with hdr_right:
        return _add_year_slider(df_scope)

def _add_year_slider(df_scope: pd.DataFrame) -> pd.DataFrame:
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

def _order_classes(classes):
    order = ["bullet", "blitz", "rapid", "daily", "classical"]
    lower = [c.lower() if isinstance(c, str) else "unknown" for c in classes]
    seen = set()
    ordered = [c for c in order if c in lower and not (c in seen or seen.add(c))]
    rest = [c for c in lower if c not in seen]
    return ordered + sorted(rest)

def get_time_control_tabs(df: pd.DataFrame) -> Tuple[list[str], list[str]]:
    total_n = len(df)
    class_counts = df["time_class"].fillna("unknown").str.lower().value_counts()
    classes = _order_classes(class_counts.index.tolist())
    top_labels = [f"All ({total_n})"] + [f"{c.title()} ({int(class_counts.get(c, 0))})" for c in classes]
    return (top_labels, classes)
