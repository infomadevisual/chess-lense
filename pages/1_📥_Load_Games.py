import logging
import pandas as pd
import streamlit as st
from pathlib import Path
from chesscom_downloader import ChesscomDownloader
from config import Config
from app_session import AppSession
from ui import inject_page_styles

st.set_page_config(page_title="📥 Load games", page_icon="♟️", layout="centered")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load-games")

inject_page_styles()
session = AppSession.from_streamlit()
downloader = ChesscomDownloader(timeout=20.0, sleep_sec=0.2)

st.header("Load games")

if session.game_count > 0:
    st.success(f"Loaded {session.game_count} games from {session.username}.")

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

if demo:
    username_input = "hikaru"
    session.username = username_input
    logger.info("Demo user selected")

if submit or demo:
    if not username_input:
        st.error("Please enter a valid username")
        st.stop()
    
    session.username = username_input.strip().lower()

    with st.spinner("Loading games..."):
        prog = st.progress(0.0, text="Initializing download")

        def update_progress(i, total):
            frac = 0 if total == 0 else i / total
            prog.progress(frac, text=f"{i}/{total} months loaded")

        if Config.debug == False:
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

        if st.button("Go to 📊 Dashboard", type="primary"):
            st.switch_page("pages/2_📊_Dashboard.py")

        with st.expander("Summary", expanded=True):
            st.write(f"User: **{session.username}** | Games: **{session.game_count}**")
            cols = [
                "end_time","username","opponent_username",
                "user_played_as","user_result","opponent_result",
                "user_rating","opponent_rating","rated",
                "rules","time_class","time_control",
            ]
            st.dataframe(df.sample(min(10, len(df)))[cols] if len(df) else df)
