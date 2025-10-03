import logging
import streamlit as st

from chesscom_downloader import ChesscomDownloader
from config import Config
from lib.app_session import AppSession

session = AppSession.from_streamlit()

# Debug Loader
if Config.debug == True and Config.load_user != None:
    downloader = ChesscomDownloader(timeout=20.0, sleep_sec=0.2)
    session.username = Config.load_user
    session.games_df = downloader.load_from_cache(Config.load_user)
    session.persist()

# Page Setup
st.set_page_config(
    page_title="chess.com Analyzer • Home",
    page_icon="♟️",
    layout="centered",
)

st.title("♟️ chess.com Analyzer")
st.subheader("Analyze your chess.com games like never before")

st.markdown(
    """
Welcome to **chess.com Analyzer** — your personal dashboard for deep insights into your chess.com games.  
Here you can:
- 📥 Load your full game history directly from chess.com
- 📊 Explore your **openings, strengths, and weaknesses**  
- 🔍 Compare your play against **other players**  
- 👑 Discover how top grandmasters approach the same positions  

Get started by entering your **chess.com username** in the *Load Games* page from the sidebar.
"""
)

st.info("Tip: Use the navigation bar on the left to switch between pages.")

c1, c2 = st.columns(2)
with c1:
    if st.button("Load games", type="primary"):
        st.switch_page("pages/1_📥_Load_Games.py")