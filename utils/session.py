import streamlit as st

SESSION_USERNAME = "username"
SESSION_USERNAME_NORMALIZED = "username_normalized"


def init_app():
    st.session_state.setdefault(SESSION_USERNAME, None)
    st.session_state.initialized = True


def ensure_app_initialized():
    if "initialized" not in st.session_state:
        init_app()


def get_session_username() -> str | None:
    return st.session_state[SESSION_USERNAME]


def get_session_username_normalized() -> str | None:
    return st.session_state[SESSION_USERNAME_NORMALIZED]


def set_session_username(username: str | None):
    st.session_state[SESSION_USERNAME] = username

    if username is not None:
        st.session_state[SESSION_USERNAME_NORMALIZED] = username.strip().lower()
    else:
        st.session_state[SESSION_USERNAME_NORMALIZED] = None
