import streamlit as st

from utils.chesscom_downloader import ChesscomDownloader
from utils.config import Config
from utils.app_session import AppSession

session = AppSession.from_streamlit()

# Debug Loader
if Config.debug == True and Config.load_user != None:
    session.username = Config.load_user
    df = ChesscomDownloader(timeout=20.0, sleep_sec=0.2, username=Config.load_user,timezone=st.context.timezone).load_from_cache()
    session.games_df = df
    session.persist()

# Global Styling
st.markdown(
    """
    <style>
        .block-container {
            padding: 2rem !important;
        }
        .stApp {
            padding: 0 !important;
            margin: 0 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

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
Welcome to **chess.com Analyzer** — your personal analysis for deep insights into your chess games.
Current features:
- 📥 Load Games: Load your full game history directly from chess.com
- 📊 Dashboard: Explore your general performance and patterns
- 📖 Openings: Overview of your best- and worst-performing openings
- 🕒 Seasonalities: Shows you when you perform the best and the worst
- 🔍 Compare your play against **other players**  
"""
)
st.info("Get started by entering your **chess.com username** in the *Load Games* page from the sidebar.")

c1, c2 = st.columns(2)
with c1:
    if st.button("Go to 📥 Load Games", type="primary"):
        st.switch_page("pages/1_📥_Load_Games.py")

# --- Feedback ---
st.divider()
st.subheader("💡 Feedback & Feature Requests")
st.markdown(
    """
Your ideas help shape **chess.com Analyzer**.  
If you have suggestions, bug reports, or feature requests:

- 📬 **Email:** [infomadevisual@gmail.com](mailto:infomadevisual@gmail.com)
- 🐙 **GitHub Issues:** [github.com/yourusername/chess-com-streamlit/issues](https://github.com/yourusername/chess-com-streamlit/issues)

Whether it's a new visualization, a missing stat, or an idea for improvement — I'd love to hear from you.
"""
)

# --- Feedback ---
st.divider()
upcoming = [
    "🔍 Compare your play against **other players**",
    "👑 Discover how top grandmasters approach the same openings/positions",
    "Tactics: Discover which tactics (forks, pins, ...) you fall for the most.",
    "Opponent Analysis: performance by rating gap and opponent strength",
    "Time Control Insights: bullet/blitz/rapid breakdowns",
    "Opening Explorer: interactive tree with win rates",
    "Rating Progress Tracker: milestones and streaks",
]
st.subheader("🚧 Roadmap")
st.markdown("\n".join(f"- {x}" for x in upcoming))
st.caption("Order not final. Subject to change.")

st.divider()
changelog = [
    {
        "date": "2025-10-05",
        "version": "v0.1.0",
        "items": [
            "Load games: Load games from chess.com",
            "Dashboard: An overview with rather simple performance statistics",
            "Openings: Discovery of win-rates for openings and their variations",
            "Seasonalites: Analysis of yearly, monthly, daily, hourly patterns"
        ],
    }
]
st.subheader("📝 Changelog")
for entry in changelog:
    st.markdown(f"**{entry['version']}** · {entry['date']}")
    st.markdown("\n".join(f"- {it}" for it in entry["items"]))
    st.markdown("---")