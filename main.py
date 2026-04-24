import streamlit as st
from src.auth.user_auth import UserAuthService
from src.logger.logger import Logger
from src.database.database import init_db


init_db()
logger = Logger().setup_logs()
auth = UserAuthService()


st.set_page_config(
    page_title="System Performance Analyzer",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def page_auth():
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
            login_username = st.text_input("Username", key="login_username")
            login_password = st.text_input(
                "Password", type="password", key="login_password"
            )
            if st.button("Login", use_container_width=True, type="primary"):
                if login_username and login_password:
                    if auth.login_user(login_username, login_password):
                        st.session_state.logged_in = True
                        st.session_state.username = login_username.strip()
                        st.session_state.is_admin = auth.is_admin(
                            login_username.strip()
                        )
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password.")
                else:
                    st.warning("Enter both fields.")

        with tab_right:
            if not auth.registration_allowed():
                st.info("Registration is currently disabled by the administrator.")
            else:
                register_username = st.text_input("Username", key="register_username")
                register_email = st.text_input("Email", key="register_email")
                register_password = st.text_input(
                    "Password", type="password", key="register_password"
                )
                register_confirm = st.text_input(
                    "Confirm", type="password", key="register_confirm"
                )
                if st.button(
                    "Create Account", use_container_width=True, type="primary"
                ):
                    if not (register_username and register_email and register_password):
                        st.warning("All fields required.")
                    elif register_password != register_confirm:
                        st.error("Passwords don't match.")
                    elif len(register_password) < 6:
                        st.error("Password must be ≥ 6 characters.")
                    elif auth.register_user(
                        register_username, register_password, register_email
                    ):
                        st.success("✅ Account created! Please log in.")
                    else:
                        st.error("❌ Username already taken.")


def main():
    page_auth()

if __name__ == "__main__":
    main()
