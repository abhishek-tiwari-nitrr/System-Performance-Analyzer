import streamlit as st
import time
import pandas as pd
from datetime import datetime
import glob
import os
from src.auth.user_auth import UserAuthService
from src.config.config import (
    TOKEN_PARAM,
    ACCENT,
    GREEN,
    ORANGE,
    PROCESS_LIMIT,
    RED,
    DB_PATH,
)
import plotly.graph_objects as go
import plotly.express as px
from src.report_gen.report_generator import ReportGenerator
from src.services.service_orchestrator import ServiceOrchestrator
from src.user_session.user_session import create_token, verify_token
from src.analysis.analysis import Analysis
from src.logger.logger import Logger
from src.ml_engine.ml_engine import (
    compute_health_score,
    detect_anomalies,
    rank_anomalous_processes,
    detect_network_anomalies,
)
from src.database.database import (
    init_db,
    available_days,
    user_stats,
    get_setting,
    set_setting,
    all_settings,
    all_users,
    global_stats,
    delete_user,
)


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

        nav_options = ["📈 Dashboard", "🔍 Monitor", "📊 Report", "⚙️ Settings"]
        if st.session_state.is_admin:
            nav_options.append("🛡️ Admin Panel")
        page = st.radio("Select a page", nav_options, label_visibility="collapsed")

        st.markdown("---")
        if st.button("🚪 Logout", width="stretch"):
            _logout()
            st.rerun()

    return page


def page_dashboard():
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

        t_sys, t_proc, t_net, t_ml, t_pdf = st.tabs(
            [
                "🖥️ System",
                "⚙️ Processes",
                "🌐 Network",
                "🧠 Intelligent Anomaly Detection",
                "📥 Download PDF",
            ]
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
                    title="Download",
                    xaxis_title="Timestamp",
                    yaxis_title="Download Speed (MB/s)",
                    template="plotly_white",
                    height=300,
                )
                st.plotly_chart(fig_download, width="stretch")

                fig_upload = go.Figure()
                fig_upload.add_trace(
                    go.Scatter(
                        x=network_df["timestamp"],
                        y=network_df["upload_speed_mb"],
                        line=dict(color=RED),
                    )
                )
                fig_upload.update_layout(
                    title="Upload",
                    xaxis_title="Timestamp",
                    yaxis_title="Upload Speed (MB/s)",
                    template="plotly_white",
                    height=300,
                )
                st.plotly_chart(fig_upload, width="stretch")

        with t_ml:
            system_df["timestamp"] = pd.to_datetime(system_df["timestamp"])
            process_df["timestamp"] = pd.to_datetime(process_df["timestamp"])
            network_df["timestamp"] = pd.to_datetime(network_df["timestamp"])

            st.subheader("🏥 Health Score")
            health = compute_health_score(system_df)
            grade = health["grade"]

            hc1, hc2, hc3, hc4, hc5 = st.columns(5)
            hc1.markdown(
                f"<div class='grade-badge grade-{grade}'>{grade}</div>"
                f"<br><b>{health['overall']}/100</b>",
                unsafe_allow_html=True,
            )
            hc2.metric("CPU", f"{health.get('avg_cpu', 0):.1f}%")
            hc3.metric("RAM", f"{health.get('avg_mem', 0):.1f}%")
            hc4.metric("Anomalies", f"{health.get('anomaly_rate', 0):.1f}%")
            hc5.metric("Grade", grade)
            st.info(f"💡 {health['summary']}")
            st.markdown("---")

            st.subheader("🔍 Anomaly Detection")
            anomaly_df = detect_anomalies(system_df)
            n_anom = (
                int(anomaly_df["anomaly"].sum())
                if "anomaly" in anomaly_df.columns
                else 0
            )

            if n_anom:
                st.markdown(
                    f"<div class='anomaly-banner'>⚠️ <b>{n_anom} anomalous readings</b> "
                    "detected - marked in red on the chart below.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.success("✅ No anomalies detected.")

            fig_anom = go.Figure()
            fig_anom.add_trace(
                go.Scatter(
                    x=system_df["timestamp"],
                    y=system_df["overall_cpu_load"],
                    name="CPU %",
                    line=dict(color=ACCENT),
                )
            )
            if n_anom:
                anom_rows = anomaly_df[anomaly_df["anomaly"] == 1]
                fig_anom.add_trace(
                    go.Scatter(
                        x=anom_rows["timestamp"],
                        y=anom_rows["overall_cpu_load"],
                        mode="markers",
                        name="Anomaly",
                        marker=dict(color="red", size=8, symbol="x"),
                    )
                )
            fig_anom.update_layout(
                title="CPU Load - Anomalies",
                xaxis_title="Timestamp",
                yaxis_title="CPU %",
                template="plotly_white",
                height=300,
            )
            st.plotly_chart(fig_anom, width="stretch")

            if n_anom:
                adf = anomaly_df[anomaly_df["anomaly"] == 1][
                    [
                        "timestamp",
                        "overall_cpu_load",
                        "vm_percent_used",
                        "battery_percent",
                    ]
                ].reset_index(drop=True)
                st.dataframe(
                    adf.style.map(
                        lambda v: (
                            "background-color:#fff3cd"
                            if isinstance(v, float) and v > 80
                            else ""
                        ),
                        subset=["overall_cpu_load", "vm_percent_used"],
                    ),
                    width="stretch",
                )
            st.markdown("---")

            st.subheader("⚙️ Process Anomaly Ranking")
            process_clean = process_df[
                process_df["process_name"] != "System Idle Process"
            ]
            ranked = rank_anomalous_processes(process_clean)
            if not ranked.empty:
                st.dataframe(
                    ranked.style.map(
                        lambda v: (
                            "background-color:#f8d7da;color:#721c24"
                            if v is True
                            else ""
                        ),
                        subset=["flagged"],
                    ),
                    width="stretch",
                )

                fig_proc = go.Figure()
                fig_proc.add_trace(
                    go.Bar(
                        x=ranked["process_name"],
                        y=ranked["avg_cpu"],
                        marker_color=[RED if f else ACCENT for f in ranked["flagged"]],
                    )
                )
                fig_proc.update_layout(
                    title="Average CPU by Process",
                    xaxis_title="Process",
                    yaxis_title="Avg CPU %",
                    xaxis=dict(tickangle=45),
                    template="plotly_white",
                    height=350,
                )
                st.plotly_chart(fig_proc, width="stretch")
            else:
                st.info("Not enough process data for ranking.")
            st.markdown("---")

            st.subheader("🌐 Network Spike Detection")
            net_anom = detect_network_anomalies(network_df)
            spikes = net_anom[net_anom["net_anomaly"]]
            if not spikes.empty:
                st.warning(f"⚠️ {len(spikes)} network spike(s) detected")
                st.dataframe(
                    spikes[["timestamp", "upload_speed_mb", "download_speed_mb"]],
                    width="stretch",
                )
            else:
                st.success("✅ No network spikes detected.")

        with t_pdf:
            try:
                pdf_path = f"Report_{user}.pdf"
                ReportGenerator(network_plot, process_plot, system_plot, user)
                if not os.path.exists(pdf_path):
                    st.error("❌ PDF could not be created.")
                else:
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    os.remove(pdf_path)
                    for img_path in glob.glob(f"report/*_{user}.png"):
                        try:
                            os.remove(img_path)
                        except Exception as e:
                            logger.error(f"Error in Plot Delete: {e}")
                    st.download_button(
                        label="⬇️ Click here to Download",
                        data=pdf_bytes,
                        file_name=f"SPA_{user}_Day{selected_day}.pdf",
                        mime="application/pdf",
                    )
            except Exception as e:
                st.error(f"PDF error: {e}")
                logger.exception(f"PDF generation failed: {e}")


def page_settings():
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


def page_admin():
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
            st.dataframe(df, use_container_width=True)

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
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        st.markdown("---")
        if DB_PATH.exists():
            with open(DB_PATH, "rb") as f:
                st.download_button(
                    "📥 Download spa.db backup",
                    f.read(),
                    "spa_backup.db",
                    "application/octet-stream",
                )


def main():
    if not st.session_state.logged_in:
        page_auth()
        return

    page = sidebar()

    if page == "📈 Dashboard":
        page_dashboard()
    elif page == "🔍 Monitor":
        page_monitor()
    elif page == "📊 Report":
        page_report()
    elif page == "⚙️ Settings":
        page_settings()
    elif page == "🛡️ Admin Panel":
        page_admin()


if __name__ == "__main__":
    main()
