import streamlit as st
from src.database import available_days, user_stats


def render() -> None:
    user = st.session_state.username
    st.title("📈 Dashboard")

    stats = user_stats(user)
    days = available_days(user)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("System Readings", stats["system_rows"])
    c2.metric("Process Readings", stats["process_rows"])
    c3.metric("Network Readings", stats["network_rows"])
    c4.metric("Days with Data", len(days))

    if not days:
        st.info("📭 No data yet. Go to **Monitor** to collect your first readings.")
        return
