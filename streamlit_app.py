import logging

import duckdb
import streamlit as st

from data.openings_preprocessor import preprocess_openings
from services.duckdb_dao import create_openings_view
from utils.session import init_session

duckdb.install_extension("icu")
duckdb.load_extension("icu")

# Configure logging once
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

init_session()

# Ensure openings exist and view is created
preprocess_openings()
create_openings_view()

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
