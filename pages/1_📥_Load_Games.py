# Home / Load page

import logging
import streamlit as st
from utils.chesscom_downloader import ChesscomDownloader
from utils.config import Config
from utils.app_session import AppSession
from utils.ui import setup_global_page

# ---------- Page config must be first ----------
st.set_page_config(page_title="📥 Load games", page_icon="♟️", layout="centered")
PAGE_ID = "Dashboard"
setup_global_page(PAGE_ID)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load-games")

# ---------- Constants ----------
DASHBOARD_PAGE_PATH = "pages/2_📊_Dashboard.py"  # adjust if your filename differs

# ---------- One-shot state ----------
if "ready_for_dashboard" not in st.session_state:
    st.session_state.ready_for_dashboard = False

# ---------- UI helpers ----------
st.header("Load games")

# ---------- Session + downloader ----------
session = AppSession.from_streamlit()

if session.game_count > 0:
    st.success(f"Loaded {session.game_count} games from {session.username}.")


# ---------- Form ----------
with st.form("user_form", clear_on_submit=False):
    username_input = st.text_input(
        "Chess.com username",
        value=session.username,
        help="Lowercase enforced",
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        submit = st.form_submit_button("Load", type="primary")
    with c2:
        demo_hikaru = st.form_submit_button("Demo: hikaru")
    with c3:
        demo_gotham = st.form_submit_button("Demo: gothamchess")

# Privacy notice
st.markdown("""
### ℹ️ Data Privacy Notice

Game data is fetched from the public [Chess.com Published-Data API](https://support.chess.com/en/articles/9650547-published-data-api) and cached locally for faster analysis.  
No data is shared, sold, or stored permanently.  
All caching is solely for performance optimization.  
This tool is **unaﬃliated with Chess.com** and complies with their API terms.
""")

# ---------- Handle actions ----------
if demo_hikaru:
    username_input = "hikaru"
    session.username = username_input.strip().lower()
    logger.info("Demo user 'hikaru' selected")
    submit = True

if demo_gotham:
    username_input = "gothamchess"
    session.username = username_input.strip().lower()
    logger.info("Demo user 'gothamchess' selected")
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

        downloader = ChesscomDownloader(timeout=20.0, sleep_sec=0.2, username=session.username, timezone=st.context.timezone)
        if not Config.debug:
            df = downloader.download_all(progress_cb=update_progress)
        else:
            df = downloader.load_from_cache()

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
