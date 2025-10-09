import streamlit as st

from utils.session import init_app

init_app()

pg = st.navigation(
    [
        "pages/0_♟️_Home.py",
        "pages/1_📥_Load_Games.py",
        "pages/2_📊_Dashboard.py",
        "pages/3_📖_Openings.py",
        "pages/4_🕒_Seasonalities.py",
    ]
)
pg.run()
