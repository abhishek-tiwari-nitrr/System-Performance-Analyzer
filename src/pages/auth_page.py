import streamlit as st
from src.user_auth import get_auth_service
from src.config import TOKEN_PARAM
from src.logger import logger
from src.user_auth import create_token


def _login_success(username: str):
    auth = get_auth_service()
    token = create_token(username)
    st.query_params[TOKEN_PARAM] = token
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.is_admin = auth.is_admin(username)
    logger.info(f"Login Done: {username}")


def _login_form() -> None:
    auth = get_auth_service()
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", width="stretch", type="primary"):
        if not (username and password):
            st.warning("Enter both fields.")
            return
        if auth.login_user(username, password):
            _login_success(username.strip())
            st.rerun()
        else:
            st.error("❌ Invalid username or password.")


def _register_form() -> None:
    auth = get_auth_service()
    if not auth.registration_allowed():
        st.info("Registration is currently disabled by the administrator.")
        return

    username = st.text_input("Username", key="reg_username")
    email = st.text_input("Email", key="reg_email")
    password = st.text_input("Password", type="password", key="reg_password")
    confirm = st.text_input("Confirm", type="password", key="reg_confirm")

    if st.button("Create Account", width="stretch", type="primary"):
        if not (username and email and password):
            st.warning("All fields required.")
        elif password != confirm:
            st.error("Passwords don't match.")
        elif len(password) < 6:
            st.error("Password must be ≥ 6 characters.")
        elif auth.register_user(username, password, email):
            st.success("✅ Account created! Please log in.")
        else:
            st.error("❌ Username already taken.")


def render() -> None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            "<h1 style='text-align:center'>🖥️ System Performance Analyzer</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#666'>Monitor | Analyse | Optimise</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        tab_left, tab_right = st.tabs(["🔐 Login", "📝 Register"])

        with tab_left:
            _login_form()
        with tab_right:
            _register_form()
