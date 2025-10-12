# Home / Load page

import logging

import pandas as pd
import streamlit as st

from services.duckdb_dao import (
    count_rows,
    create_user_view,
    get_distinct_rated,
    get_distinct_time_class,
    min_max_months_from_end_time,
    sample_preview,
)
from services.services import get_data_manager
from utils.session import (
    FilterOptionsAvailable,
    get_session_username,
    get_session_username_normalized,
    set_available_filters,
    set_session_username,
)
from utils.ui import setup_global_page

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
    username_n = get_session_username_normalized()
    data_manager = get_data_manager()

    with st.spinner("Loading games..."):
        prog = st.progress(0.0, text="Initializing download")

        def update_progress(i, total):
            num_months = total - 2
            cache_step = total - 1
            frac = 0.0 if total == 0 else i / total

            if i <= num_months:
                text = f"Loading {i}/{num_months} months..."
            elif i == cache_step:
                text = "Updating local cache..."
            else:
                text = "Preprocessing and saving games..."

            logger.info(text)
            prog.progress(frac, text)

        data_manager.check_for_updates_and_init(username_n, update_progress)

    prog.empty()

    tz = st.context.timezone or "UTC"
    con, view = create_user_view(
        username_n, data_manager.get_games_path(username_n), tz
    )

    # Build available Filter options
    # Slider
    min_m, max_m = min_max_months_from_end_time(con, view)
    min_pd = pd.to_datetime(min_m)
    max_pd = pd.to_datetime(max_m)

    # build continuous month sequence
    months = pd.period_range(start=min_m, end=max_m, freq="M")
    labels = months.strftime("%Y-%m").tolist()

    # Rated Only
    rated_vals = get_distinct_rated(con, view)

    time_class = get_distinct_time_class(con, view)
    time_class = ["All"] + time_class
    order = ["All", "bullet", "blitz", "rapid", "daily"]
    time_class = [x for x in order if x in time_class]

    set_available_filters(
        FilterOptionsAvailable(months=labels, rated=rated_vals, time_class=time_class)
    )

    games_count = count_rows(con, view)
    if games_count == 0:
        st.warning("No games found.")
    else:
        st.success(f"{games_count} games loaded from {username}.")

        if st.button("Go to 📊 Dashboard", type="primary", key="go_dash"):
            st.switch_page(DASHBOARD_PAGE_PATH)

        with st.expander("Summary", expanded=True):
            st.write(f"User: **{username}** | Games: **{games_count}**")
            st.dataframe(sample_preview(con, view))
