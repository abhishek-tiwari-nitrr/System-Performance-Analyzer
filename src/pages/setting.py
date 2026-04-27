import streamlit as st
from src.user_auth import get_auth_service


def render() -> None:
    user = st.session_state.username
    st.title("⚙️ Settings")
    st.markdown("---")

    with st.expander("🔐 Change Password", expanded=True):
        current_password = st.text_input(
            "Current password", type="password", key="pass_cur"
        )
        new_password = st.text_input("New password", type="password", key="pass_new")
        confirm_new_password = st.text_input(
            "Confirm new", type="password", key="pass_con"
        )
        if st.button("Update Password", type="primary"):
            auth = get_auth_service()
            if not current_password or not new_password:
                st.warning("Fill all fields.")
            elif new_password != confirm_new_password:
                st.error("Passwords don't match.")
            elif len(new_password) < 6:
                st.error("Must be ≥ 6 characters.")
            elif auth.change_password(user, current_password, new_password):
                st.success("✅ Password updated!")
            else:
                st.error("❌ Current password incorrect.")
