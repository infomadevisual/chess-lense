# Home / Load page

import logging

import streamlit as st

from utils.session import (
    get_session_username,
    get_session_username_normalized,
    set_session_username,
)
from utils.ui import load_validate_games, setup_global_page

# ---------- Page config must be first ----------
setup_global_page("📥 Load games", "centered")

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("load-games")

# ---------- Constants ----------
DASHBOARD_PAGE_PATH = "pages/2_📊_Dashboard.py"  # adjust if your filename differs

# ---------- One-shot state ----------
if "ready_for_dashboard" not in st.session_state:
    st.session_state.ready_for_dashboard = False

# ---------- UI helpers ----------
st.header("Load games")

# ---------- Form ----------
with st.form("user_form", clear_on_submit=False):
    username_input = st.text_input(
        "Chess.com username",
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
st.markdown(
    """
### ℹ️ Data Privacy Notice

Game data is fetched from the public [Chess.com Published-Data API](https://support.chess.com/en/articles/9650547-published-data-api) and cached locally for faster analysis.  
No data is shared, sold, or stored permanently.  
All caching is solely for performance optimization.  
This tool is **unaﬃliated with Chess.com** and complies with their API terms.
"""
)

# ---------- Handle actions ----------
if demo_hikaru:
    username_input = "hikaru"
    logger.info("Demo user 'hikaru' selected")
    submit = True

if demo_gotham:
    username_input = "gothamchess"
    logger.info("Demo user 'gothamchess' selected")
    submit = True

if submit:
    if not username_input:
        st.error("Please enter a valid username")
        st.stop()

    set_session_username(username_input)
    username = get_session_username()

    with st.spinner("Loading games..."):
        prog = st.progress(0.0, text="Initializing download")

        def update_progress(i, total):
            frac = 0.0 if total == 0 else i / total
            prog.progress(frac, text=f"{i}/{total} months loaded")

        normalized = get_session_username_normalized()
        df = load_validate_games(progress_cb=update_progress)

    prog.empty()

    if df.empty:
        st.warning("No games found.")
    else:
        st.success(f"{len(df)} games loaded from {username}.")

        if st.button("Go to 📊 Dashboard", type="primary", key="go_dash"):
            st.switch_page(DASHBOARD_PAGE_PATH)

        with st.expander("Summary", expanded=True):
            st.write(f"User: **{username}** | Games: **{len(df)}**")

            cols = [
                "end_time_local",
                "username",
                "opponent_username",
                "user_played_as",
                "user_result",
                "opponent_result",
                "user_rating",
                "opponent_rating",
                "rated",
                "rules",
                "time_class",
                "time_control",
            ]
            cols = [c for c in cols if c in df.columns]

            try:
                st.dataframe(df.sample(min(10, len(df)))[cols] if len(df) else df[cols])
            except Exception:
                st.dataframe(df.head(10)[cols])
