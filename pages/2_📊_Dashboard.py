# dashboard_checkboxes.py
import streamlit as st
import pandas as pd

from lib.app_session import AppSession
from ui import inject_page_styles, time_filter_controls

_ORDER = ["bullet", "blitz", "rapid", "daily", "classical"]

def _normalize_time_label(tc: str) -> str:
    if not tc or not isinstance(tc, str):
        return "unknown"
    try:
        if "+" in tc:
            base, inc = tc.split("+", 1)
            mins = int(int(base) / 60)
            inc_s = int(inc)
            return f"{mins}+{inc_s} min" if inc_s else f"{mins} min"
        if "/" in tc:
            return "daily (correspondence)"
        return tc
    except Exception:
        return tc

def _order_classes(classes):
    lower = [c.lower() if isinstance(c, str) else "unknown" for c in classes]
    seen = set()
    ordered = [c for c in _ORDER if c in lower and not (c in seen or seen.add(c))]
    rest = [c for c in lower if c not in seen]
    return ordered + sorted(rest)

def _render_viz(df: pd.DataFrame):
    st.caption(f"{len(df)} games")
    if df.empty:
        st.info("No games for this selection.")
        return
    if "end_time" in df.columns and pd.api.types.is_datetime64_any_dtype(df["end_time"]):
        monthly = df.resample("ME", on="end_time").size().rename("games")
        st.line_chart(monthly)
    if "opening" in df.columns:
        top_open = df["opening"].fillna("unknown").value_counts().head(10)
        st.bar_chart(top_open)
    show_cols = [c for c in ["game_url","time_class","time_control","opening","eco","rated","end_time"] if c in df.columns]
    st.dataframe(df[show_cols].head(50), width="stretch")


def run():
    inject_page_styles()
    st.markdown("""
    <style>
    div[data-testid="column"]:has(div[data-testid="stSelectSlider"]) {
        padding-top: 3rem;
    }
    </style>
    """, unsafe_allow_html=True)

    st.set_page_config(page_title="ChessCom Analyzer • Dashboard", page_icon="📊", layout="wide")

    session = AppSession.from_streamlit()
    df = session.games_df
    if df is None or df.empty:
        st.warning("No games loaded. Go to Home and load your games first.")
        return

    total_n = len(df)
    class_counts = df["time_class"].fillna("unknown").str.lower().value_counts()
    classes = _order_classes(class_counts.index.tolist())

    top_labels = [f"All ({total_n})"] + [f"{c.title()} ({int(class_counts.get(c, 0))})" for c in classes]
    
    # --- Layout
    hdr_left, hdr_right = st.columns([1, 2])

    with hdr_left:
        st.header("Dashboard")

    with hdr_right:
            # derive available months from end_time
        s = pd.to_datetime(df["end_time"], utc=True, errors="coerce").dropna()
        if s.empty:
            df_range = df.copy()
        else:
            min_p = s.min().to_period("M")
            max_p = s.max().to_period("M")

            # build labels YYYY-MM
            months = []
            cur = min_p
            while cur <= max_p:
                months.append(cur)
                cur += 1
            labels = [p.strftime("%Y-%m") for p in months]

        start_lbl, end_lbl = st.select_slider(
            "Range",
            options=labels,
            value=(labels[0], labels[-1]),
            key="month_slider",
            label_visibility="collapsed",
        )

    # compute filtered df once
    start_p = pd.Period(start_lbl, freq="M")
    end_p   = pd.Period(end_lbl, freq="M")
    start_ts = start_p.to_timestamp(how="start").tz_localize("UTC")
    end_ts   = (end_p + 1).to_timestamp(how="start").tz_localize("UTC")
    t = pd.to_datetime(df["end_time"], errors="coerce", utc=True)
    df_range = df[(t >= start_ts) & (t < end_ts)].copy()

    top_tabs = st.tabs(top_labels)
    with top_tabs[0]:
        _render_viz(df_range)

    for i, cls in enumerate(classes, start=1):
        with top_tabs[i]:
            scope = df_range[df_range["time_class"].str.lower().fillna("unknown") == cls]
            if scope.empty:
                st.info("No games in this class.")
                continue
            filtered = time_filter_controls(scope, key_prefix=f"tc_{cls}")
            _render_viz(filtered)

if __name__ == "__main__":
    run()
