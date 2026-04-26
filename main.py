import streamlit as st
import time
import pandas as pd
from datetime import datetime
from src.auth.user_auth import UserAuthService
from src.config.config import TOKEN_PARAM, ACCENT, GREEN, ORANGE, PROCESS_LIMIT, RED
import plotly.graph_objects as go
import plotly.express as px
from src.services.service_orchestrator import ServiceOrchestrator
from src.user_session.user_session import create_token, verify_token
from src.analysis.analysis import Analysis
from src.logger.logger import Logger
from src.database.database import init_db, available_days


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

        nav_options = ["🔍 Monitor", "📊 Report"]
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


def page_report():
    user = st.session_state.username
    st.title("📊 Performance Report")
    st.markdown("---")

    days = available_days(user)
    if not days:
        st.warning("⚠️ No data yet. Run the monitor first.")
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        selected_day = st.selectbox(
            "Select day to Analyse",
            days,
            format_func=lambda d: datetime.strptime(d, "%Y-%m-%d").strftime(
                "Day %d - %B %Y"
            ),
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        analyse_button = st.button("🔍 Analyse", type="primary", width="stretch")

    if not analyse_button:
        return

    with st.spinner("Analysing your data…"):
        try:
            analysis = Analysis(user)
            (
                network_df,
                process_df,
                system_df,
                network_plot,
                process_plot,
                system_plot,
            ) = analysis.run(selected_day)
        except Exception as e:
            st.error(f"Analysis error: {e}")
            return

        if system_df.empty and process_df.empty:
            st.warning("No data found for this day.")
            return

        t_sys, t_proc, t_net, t_pdf = st.tabs(
            ["🖥️ System", "⚙️ Processes", "🌐 Network", "📥 PDF"]
        )

        with t_sys:
            if not system_df.empty:
                system_df["timestamp"] = pd.to_datetime(system_df["timestamp"])

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=system_df["timestamp"],
                        y=system_df["overall_cpu_load"],
                        line=dict(color=ACCENT),
                    )
                )
                fig.update_layout(
                    title="CPU Load %",
                    xaxis_title="Timestamp",
                    yaxis_title="CPU Usage (%)",
                    template="plotly_white",
                    height=300,
                    yaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig, width="stretch")

                fig2 = px.line(
                    system_df,
                    x="timestamp",
                    y="vm_percent_used",
                    color_discrete_sequence=[GREEN],
                )
                fig2.update_layout(
                    title="RAM Usage %",
                    xaxis_title="Timestamp",
                    yaxis_title="Memory Usage (%)",
                    template="plotly_white",
                    height=300,
                    yaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig2, width="stretch")

                if system_df["battery_percent"].notna().any():
                    fig3 = px.line(
                        system_df,
                        x="timestamp",
                        y="battery_percent",
                        color_discrete_sequence=[ORANGE],
                    )
                    fig3.update_layout(
                        title="Battery Usage %",
                        xaxis_title="Timestamp",
                        yaxis_title="Battery Level (%)",
                        template="plotly_white",
                        height=300,
                        yaxis=dict(range=[0, 100]),
                    )
                    st.plotly_chart(fig3, width="stretch")

        with t_proc:
            if not process_df.empty:
                process_df["timestamp"] = pd.to_datetime(process_df["timestamp"])

                # data processing for graph
                try:
                    process_clean = process_df[
                        process_df["process_name"] != "System Idle Process"
                    ]
                    process_agg = (
                        process_clean.groupby(["process_name", "timestamp"])
                        .agg({"cpu_percent": "sum", "memory_percent": "sum"})
                        .reset_index()
                    )
                    # Get top n CPU-consuming processes
                    top_n_cpu_processes = (
                        process_agg.groupby("process_name")["cpu_percent"]
                        .sum()
                        .sort_values(ascending=False)
                        .head(PROCESS_LIMIT)
                        .index
                    )
                    agg_top_n = process_agg[
                        process_agg["process_name"].isin(top_n_cpu_processes)
                    ]
                    cpu_total = agg_top_n.groupby("process_name")["cpu_percent"].sum()
                    memory_total = agg_top_n.groupby("process_name")[
                        "memory_percent"
                    ].sum()
                    # Normalize to 100%
                    cpu_total_norm = cpu_total / cpu_total.sum() * 100
                    memory_total_norm = memory_total / memory_total.sum() * 100

                    fig_cpu = go.Figure()
                    fig_cpu.add_trace(
                        go.Bar(
                            x=cpu_total_norm.index,
                            y=cpu_total_norm.values,
                            marker_color="skyblue",
                        )
                    )
                    fig_cpu.update_layout(
                        title=f"Top {PROCESS_LIMIT} CPU-consuming Processes (Normalized %)",
                        xaxis_title="Timestamp",
                        yaxis_title="CPU % of Total",
                        # yaxis=dict(range=[0, 100]),
                        xaxis=dict(tickangle=80),
                        template="plotly_white",
                        height=500,
                        width=900,
                    )
                    fig_cpu.update_yaxes(showgrid=True)
                    st.plotly_chart(fig_cpu, width="stretch")

                    fig_mem = go.Figure()
                    fig_mem.add_trace(
                        go.Bar(
                            x=memory_total_norm.index,
                            y=memory_total_norm.values,
                            marker_color="lightgreen",
                        )
                    )

                    fig_mem.update_layout(
                        title=f"Top {PROCESS_LIMIT} Memory-consuming Processes (Normalized %)",
                        xaxis_title="Timestamp",
                        yaxis_title="Memory % of Total",
                        xaxis=dict(tickangle=80),
                        # yaxis=dict(range=[0, 100]),
                        template="plotly_white",
                        height=500,
                        width=900,
                    )
                    fig_mem.update_yaxes(showgrid=True)

                    st.plotly_chart(fig_mem, width="stretch")

                except Exception as e:
                    st.error(f"Process Analysis error: {e}")
                    return

        with t_net:
            if not network_df.empty:
                network_df["timestamp"] = pd.to_datetime(network_df["timestamp"])

                fig_download = go.Figure()
                fig_download.add_trace(
                    go.Scatter(
                        x=network_df["timestamp"],
                        y=network_df["download_speed_mb"],
                        line=dict(color=ACCENT),
                    )
                )
                fig_download.update_layout(
                    title = "Download",
                    xaxis_title = "Timestamp",
                    yaxis_title = "Download Speed (MB/s)",
                    template="plotly_white",
                    height=300
                )
                st.plotly_chart(fig_download, width='stretch')


                fig_upload = go.Figure()
                fig_upload.add_trace(
                    go.Scatter(
                        x=network_df["timestamp"],
                        y=network_df["upload_speed_mb"],
                        line=dict(color=RED),
                    )
                )
                fig_upload.update_layout(
                    title = "Upload",
                    xaxis_title = "Timestamp",
                    yaxis_title = "Upload Speed (MB/s)",
                    template="plotly_white",
                    height=300
                )
                st.plotly_chart(fig_upload, width='stretch')

                


def main():
    if not st.session_state.logged_in:
        page_auth()
        return

    page = sidebar()

    if page == "🔍 Monitor":
        page_monitor()
    elif page == "📊 Report":
        page_report()
    else:
        page_monitor()


if __name__ == "__main__":
    main()
