import streamlit as st
from datetime import datetime
import os, glob
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from src.analysis import Analysis
from src.database import available_days
from src.ml_engine import (
    compute_health_score,
    detect_anomalies,
    rank_anomalous_processes,
    detect_network_anomalies,
)
from src.report_generator import ReportGenerator
from src.config import ACCENT, GREEN, ORANGE, RED, PROCESS_LIMIT
from src.logger import logger


def render() -> None:
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
