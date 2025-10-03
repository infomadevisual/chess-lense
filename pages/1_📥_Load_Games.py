# Home / Load page

import logging
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo, available_timezones  # Python 3.9+
from chesscom_downloader import ChesscomDownloader
from config import Config
from app_session import AppSession
from ui import inject_page_styles
import pytz
from streamlit_javascript import st_javascript
from streamlit_tz import streamlit_tz
import streamlit.components.v1 as components


# ---------- Page config must be first ----------
st.set_page_config(page_title="📥 Load games", page_icon="♟️", layout="centered")

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load-games")

# ---------- Constants ----------
DASHBOARD_PAGE_PATH = "pages/2_📊_Dashboard.py"  # adjust if your filename differs

# ---------- One-shot state ----------
if "ready_for_dashboard" not in st.session_state:
    st.session_state.ready_for_dashboard = False

# ---------- UI helpers ----------
inject_page_styles()
st.header("Load games")

# ---------- Session + downloader ----------
session = AppSession.from_streamlit()
downloader = ChesscomDownloader(timeout=20.0, sleep_sec=0.2)

if session.game_count > 0:
    st.success(f"Loaded {session.game_count} games from {session.username}.")


# ---------- Form ----------
with st.form("user_form", clear_on_submit=False):
    username_input = st.text_input(
        "Chess.com username",
        value=session.username,
        help="Lowercase enforced",
    )

    c1, c2 = st.columns(2)
    with c1:
        submit = st.form_submit_button("Load", type="primary")
    with c2:
        demo = st.form_submit_button("Demo: hikaru")

# ---------- Handle actions ----------
if demo:
    username_input = "hikaru"
    session.username = username_input.strip().lower()
    logger.info("Demo user selected")
    submit = True

if submit:
    if not username_input:
        st.error("Please enter a valid username")
        st.stop()

    session.username = username_input.strip().lower()

    with st.spinner("Loading games..."):
        prog = st.progress(0.0, text="Initializing download")

        def update_progress(i, total):
            frac = 0.0 if total == 0 else i / total
            prog.progress(frac, text=f"{i}/{total} months loaded")

        if not Config.debug:
            df = downloader.download_all(session.username, progress_cb=update_progress)
        else:
            df = downloader.load_from_cache(session.username, progress_cb=update_progress)

    prog.empty()

    session.games_df = df
    session.persist()

    if df.empty:
        st.warning("No games found.")
    else:
        st.success(f"{session.game_count} games loaded from {session.username}.")

if session.game_count > 0:
    if st.button("Go to 📊 Dashboard", type="primary", key="go_dash"):
        st.switch_page(DASHBOARD_PAGE_PATH)

    with st.expander("Summary", expanded=True):
        st.write(f"User: **{session.username}** | Games: **{session.game_count}**")
        df = session.games_df

        # Convert to TZ
        df["end_time_local"] = df["end_time"].dt.tz_convert(st.context.timezone)

        # --- derive extra columns ---
        df["year"] = df["end_time_local"].dt.year
        df["month"] = df["end_time_local"].dt.month          # 1–12
        df["month_name"] = df["end_time_local"].dt.strftime("%B")
        df["weekday"] = df["end_time_local"].dt.dayofweek    # 0=Mon .. 6=Sun
        df["weekday_name"] = df["end_time_local"].dt.strftime("%A")

        cols = [
            "end_time_local","username","opponent_username",
            "user_played_as","user_result","opponent_result",
            "user_rating","opponent_rating","rated",
            "rules","time_class","time_control",
        ]
        cols = [c for c in cols if c in df.columns]

        try:
            st.dataframe(df.sample(min(10, len(df)))[cols] if len(df) else df[cols])
        except Exception:
            st.dataframe(df.head(10)[cols])
