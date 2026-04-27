import streamlit as st
import pandas as pd
from src.database import (
    get_setting,
    set_setting,
    all_users,
    delete_user,
    global_stats,
    user_stats,
)
from src.config import DB_PATH
from src.logger import logger


def render() -> None:
    if not st.session_state.is_admin:
        st.error("Access denied.")
        return

    st.title("🛡️ Admin Panel")
    st.markdown("---")

    tab_set, tab_users, tab_db = st.tabs(["⚙️ App Settings", "👥 Users", "🗄️ Database"])

    with tab_set:
        st.subheader("Application Settings")

        current_max = int(get_setting("max_monitor_minutes", "10"))
        new_max = st.number_input(
            "Max monitoring duration per session (minutes)",
            min_value=1,
            max_value=1440,
            value=current_max,
            step=1,
            help="Users cannot start a monitoring session longer than this.",
        )
        if st.button("💾 Save Duration Limit", type="primary"):
            set_setting("max_monitor_minutes", str(new_max))
            st.success(f"✅ Max duration set to **{new_max} minutes**.")
            logger.info(f"Admin changed max_monitor_minutes to {new_max}")

        st.markdown("---")
        allow_reg = get_setting("allow_registration", "1") == "1"
        new_allow = st.toggle("Allow new user registration", value=allow_reg)
        if st.button("💾 Save Registration Setting"):
            set_setting("allow_registration", "1" if new_allow else "0")
            st.success("✅ Setting saved.")

    with tab_users:
        st.subheader("All Users")
        users = all_users()
        if users:
            df = pd.DataFrame(users)
            df["is_admin"] = df["is_admin"].apply(lambda v: "✅ Admin" if v else "User")
            st.dataframe(df, width='stretch')

            st.markdown("---")
            st.subheader("Delete a User & their data")
            del_options = [u["username"] for u in users if u["username"] != "Admin"]
            if del_options:
                to_del = st.selectbox("Select user to delete", del_options)
                confirm = st.text_input(f"Type **{to_del}** to confirm deletion")
                if st.button("🗑️ Delete User", type="secondary"):
                    if confirm == to_del:
                        delete_user(to_del)
                        st.success(f"✅ User '{to_del}' and all their data deleted.")
                        logger.info(f"Admin deleted user: {to_del}")
                        st.rerun()
                    else:
                        st.error("Confirmation text does not match.")
            else:
                st.info("No non-admin users to delete.")

    with tab_db:
        st.subheader("Database Statistics")
        gs = global_stats()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Users", gs["total_users"])
        c2.metric("System rows", gs["system_rows"])
        c3.metric("Process rows", gs["process_rows"])
        c4.metric("Network rows", gs["network_rows"])
        c5.metric("DB size", f"{gs['db_size_kb']} KB")

        st.markdown("---")

        st.subheader("Per User Data")
        users = all_users()
        rows = []
        for u in users:
            s = user_stats(u["username"])
            rows.append(
                {
                    "username": u["username"],
                    "system_rows": s["system_rows"],
                    "process_rows": s["process_rows"],
                    "network_rows": s["network_rows"],
                }
            )
        st.dataframe(pd.DataFrame(rows), width='stretch')

        st.markdown("---")
        if DB_PATH.exists():
            with open(DB_PATH, "rb") as f:
                st.download_button(
                    "📥 Download spa.db backup",
                    f.read(),
                    "spa_backup.db",
                    "application/octet-stream",
                )
