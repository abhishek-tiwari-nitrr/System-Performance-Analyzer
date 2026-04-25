import streamlit as st
import time
from src.auth.user_auth import UserAuthService
from src.config.config import TOKEN_PARAM
from src.services.service_orchestrator import ServiceOrchestrator
from src.user_session.user_session import create_token, verify_token
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

st.markdown(
    """
<style>
    .admin-banner{
            background-color:#28a745;
            color:white;
            padding:6px 10px;
            border-radius:6px;
            font-size:12px;
            display:inline-block;
            font-weight:500;
            }
</style>
""",
    unsafe_allow_html=True,
)

DEFAULTS = dict(
    logged_in=False,
    username=None,
    is_admin=False,
    svc=None,
    monitor_running=False,
    monitor_done=False,
    monitor_samples=0,
    monitor_clamped=None,
)

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _restore_session():
    if st.session_state.logged_in:
        return

    token = st.query_params.get(TOKEN_PARAM)
    username = verify_token(token)

    if username:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.is_admin = auth.is_admin(username)
        logger.info(f"Session restored via JWT: {username}")


def _login_success(username: str):
    token = create_token(username)
    st.query_params[TOKEN_PARAM] = token
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.is_admin = auth.is_admin(username)
    logger.info(f"Login Done: {username}")


def _logout():
    st.query_params.clear()
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    logger.info("User logged out.")


# Restore before any UI renders
_restore_session()


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
            if st.button("Login", width="stretch", type="primary"):
                if login_username and login_password:
                    if auth.login_user(login_username, login_password):
                        _login_success(login_username.strip())
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
                if st.button("Create Account", width="stretch", type="primary"):
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


def sidebar() -> str:
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.username}")
        if st.session_state.is_admin:
            st.markdown(
                '<span class="admin-banner">🔑 Administrator</span>',
                unsafe_allow_html=True,
            )
        st.markdown("---")

        nav_options = ["🔍 Monitor"]
        page = st.radio("Select a page", nav_options, label_visibility="collapsed")

        st.markdown("---")
        if st.button("🚪 Logout", width="stretch"):
            _logout()
            st.rerun()

    return page


def page_monitor():
    user = st.session_state.username
    st.title("🔍 Monitor System")
    max_min = ServiceOrchestrator.max_allowed_minutes()
    st.info(
        f"ℹ️ Maximum monitoring duration allowed by administrator: **{max_min} minutes**"
    )
    st.markdown("---")

    duration = st.slider("Duration (minutes)", 1, max_min, min(2, max_min))

    start = st.button(
        "▶️ Start Monitoring",
        type="primary",
        disabled=st.session_state.monitor_running,
        width="stretch",
    )

    if start:
        svc = ServiceOrchestrator(username=user, interval=5)
        actual = svc.start(duration)
        st.session_state.update(
            svc=svc, monitor_running=True, monitor_done=False, monitor_clamped=actual
        )
        st.rerun()

    if st.session_state.monitor_running:
        svc = st.session_state.svc
        st.progress(svc.progress)
        st.info(f"🔄 Collecting… **{svc.samples}** samples recorded.")
        if not svc.is_running:
            st.session_state.update(
                monitor_running=False, monitor_done=True, monitor_samples=svc.samples
            )
            st.success("✅ Done! Head to **Report** to analyse your data.")
            st.balloons()
        else:
            time.sleep(2)
            st.rerun()

    elif st.session_state.monitor_done:
        st.success(
            f"✅ Last session: **{st.session_state.monitor_samples}** samples stored for **{user}**."
        )

    st.markdown("---")

    col, _ = st.columns(2)
    with col:
        st.markdown("**Collected metrics:**")
        st.markdown(
            "- 💻 CPU load (all cores averaged)\n"
            "- 💾 RAM & swap usage\n"
            "- 🔋 Battery status\n"
            "- 🌐 Network upload / download\n"
            "- ⚙️ Top 10 processes"
        )


def main():
    if not st.session_state.logged_in:
        page_auth()
        return

    page = sidebar()

    if page == "🔍 Monitor":
        page_monitor()


if __name__ == "__main__":
    main()
