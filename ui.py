import streamlit as st

def inject_page_styles():
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