import streamlit as st
import time
from src.services.service_orchestrator import ServiceOrchestrator


def render() -> None:
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
        st.session_state.update(svc=svc, monitor_running=True, monitor_done=False)
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
