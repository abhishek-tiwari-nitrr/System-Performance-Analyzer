import streamlit as st
from src.config import TOKEN_PARAM
from src.user_session import verify_token
from src.logger import logger
from src.user_auth import get_auth_service
from src.pages import dashboard, monitor, report, setting, admin, auth_page
from src.database import init_db


init_db()

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
    .grade-badge{
            display:inline-block;
            font-size:1.8rem;
            font-weight:800;
            width:60px;
            height:60px;
            line-height:60px;
            text-align:center;
            border-radius:50%;
            color:white;
            }
    .grade-A{background:#198754}
    .grade-B{background:#0d6efd}
    .grade-C{
            background:#ffc107;
            color:#333
            }
    .grade-D{background:#fd7e14}
    .grade-F{background:#dc3545}
    .anomaly-banner{
            background:#fff3cd;
            border-left:4px solid #ffc107;
            padding:0.6rem 1rem;
            border-radius:4px;
            margin:0.5rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

_DEFAULTS = {
    "logged_in": False,
    "username": None,
    "is_admin": False,
    "svc": None,
    "monitor_running": False,
    "monitor_done": False,
    "monitor_samples": 0,
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)


def _restore_session():
    auth = get_auth_service()
    if st.session_state.logged_in:
        return

    token = st.query_params.get(TOKEN_PARAM)
    username = verify_token(token)

    if username:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.is_admin = auth.is_admin(username)
        logger.info(f"Session restored via JWT: {username}")


def _logout():
    st.query_params.clear()
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    logger.info("User logged out.")


# Restore before any UI renders
_restore_session()


def sidebar() -> str:
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.username}")
        if st.session_state.is_admin:
            st.markdown(
                '<span class="admin-banner">🔑 Administrator</span>',
                unsafe_allow_html=True,
            )
        st.markdown("---")

        nav_options = ["📈 Dashboard", "🔍 Monitor", "📊 Report", "⚙️ Settings"]
        if st.session_state.is_admin:
            nav_options.append("🛡️ Admin Panel")
        page = st.radio("Select a page", nav_options, label_visibility="collapsed")

        st.markdown("---")
        if st.button("🚪 Logout", width="stretch"):
            _logout()
            st.rerun()

    return page


def main():
    if not st.session_state.logged_in:
        auth_page.render()
        return

    page = sidebar()

    if page == "📈 Dashboard":
        dashboard.render()
    elif page == "🔍 Monitor":
        monitor.render()
    elif page == "📊 Report":
        report.render()
    elif page == "⚙️ Settings":
        setting.render()
    elif page == "🛡️ Admin Panel":
        admin.render()


if __name__ == "__main__":
    main()
