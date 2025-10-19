import duckdb
import streamlit as st

from services.data_manager import DataManager


@st.cache_resource
def get_data_manager() -> DataManager:
    return DataManager()
