# Home.py  — Streamlit-UI, nutzt die Klasse
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from chesscom_downloader import ChesscomDownloader

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("chesscom")

# ---------- Streamlit ----------
st.set_page_config(page_title="ChessCom Analyzer • Load", page_icon="♟️", layout="centered")
st.title("chess.com Analyzer")
st.subheader("Load your games and analyze!")

SESSION_KEY_USERNAME = "cc_username"
SESSION_KEY_DF = "games_df"
SESSION_KEY_META = "games_meta"

downloader = ChesscomDownloader(
    timeout=20.0,
    sleep_sec=0.2,
)

with st.form("user_form", clear_on_submit=False):
    username_input = st.text_input(
        "Chess.com Username",
        value=st.session_state.get(SESSION_KEY_USERNAME, ""),
        help="lower-case enforced",
    )
    c1, c2 = st.columns(2)
    with c1:
        submit = st.form_submit_button("Load", type="primary")
    with c2:
        demo = st.form_submit_button("Demo: hikaru")

if demo:
    username_input = "hikaru"
    st.session_state[SESSION_KEY_USERNAME] = username_input
    logger.info("Demo-User gewählt")

if submit or demo:
    if username_input == None:
        st.error("Please enter valid chess.com username")
        st.stop()

    u = username_input.strip().lower()

    st.session_state[SESSION_KEY_USERNAME] = u

    with st.spinner("Loading games..."):
        prog = st.progress(0.0, text="Initializing Download")

        def update_progress(i, total):
            frac = i / total
            prog.progress(frac, text=f"{i}/{total} months loaded")

        df, meta = downloader.download_all(u, progress_cb=update_progress)

    prog.empty()  # Leert die Progressbar nach Abschluss

    st.session_state[SESSION_KEY_DF] = df
    st.session_state[SESSION_KEY_META] = meta

    if df.empty:
        st.warning("No Games found.")
    else:
        st.success(f"{meta.games_count} Games loaded.")
        with st.expander("Summary", expanded=True):
            st.write(
                f"User: **{meta.username}** | Games: **{meta.games_count}**"
            )
            st.write(f"Files: `{meta.parquet_path}`")
            cols = [
                "end_time","time_class","rated",
                "white_username","white_rating","white_result",
                "black_username","black_rating","black_result",
                "eco","opening","termination",
            ]
            st.dataframe(df.sample(min(10, len(df)))[cols] if len(df) else df)

    try:
        st.switch_page("pages/Dashboard.py")
    except Exception:
        st.info("Dashboard fehlt. Lege pages/Dashboard.py an.")
