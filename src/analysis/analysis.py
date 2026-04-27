import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from src.database.database import (
    fetch_network_metrics,
    fetch_process_metrics,
    fetch_system_metrics,
)
from src.config.config import (
    REPORT_DIR,
    RED,
    GREEN,
    ACCENT,
    ORANGE,
    MAX_TICKER,
    PROCESS_LIMIT,
)
from src.logger.logger import logger


class Analysis:
    def __init__(self, username: str):
        self.username = username
        self._ensure_report_dir()

    def _ensure_report_dir(self):
        os.makedirs(REPORT_DIR, exist_ok=True)

    def load(self, date: str):
        network_rows = fetch_network_metrics(self.username, date)
        process_rows = fetch_process_metrics(self.username, date)
        system_rows = fetch_system_metrics(self.username, date)

        network_df = pd.DataFrame(network_rows)
        process_df = pd.DataFrame(process_rows)
        system_df = pd.DataFrame(system_rows)

        for df in (network_df, process_df, system_df):
            if "timestamp" in df.columns and not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return network_df, process_df, system_df

    def _save(self, plot_name: str):
        path = os.path.join(REPORT_DIR, plot_name)
        plt.savefig(path, dpi=300, bbox_inches="tight")
        plt.close("all")
        return path

    def _plot_network(self, network_df: pd.DataFrame):
        plots = {}
        if network_df.empty:
            return plots

        # 1. Upload Speed Trend
        try:
            plt.subplots(figsize=(12, 6))
            plt.plot(network_df["timestamp"], network_df["upload_speed_mb"], color=RED)
            plt.xlabel("Timestamp")
            plt.ylabel("Download Speed (MB/s)")
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(MAX_TICKER))
            plt.xticks(rotation=45)
            plots["upload_speed_trend"] = self._save(
                f"upload_speed_trend_{self.username}.png"
            )
        except Exception as e:
            logger.error(f"Network plot - Upload Speed Plot: {e}")

        # 2. Download Speed Trend
        try:
            plt.subplots(figsize=(12, 6))
            plt.plot(
                network_df["timestamp"], network_df["download_speed_mb"], color=GREEN
            )
            plt.xlabel("Timestamp")
            plt.ylabel("Download Speed (MB/s)")
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(MAX_TICKER))
            plt.xticks(rotation=45)
            plots["download_speed_trend"] = self._save(
                f"download_speed_trend_{self.username}.png"
            )
        except Exception as e:
            logger.error(f"Network plot - Download Speed Plot: {e}")

        # 3. Bytes Rate Trend
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(
                network_df["timestamp"],
                network_df["bytes_sent"],
                label="Bytes Sent",
                color="red",
                linestyle="--",
            )
            ax.plot(
                network_df["timestamp"],
                network_df["bytes_received"],
                label="Bytes Received",
                color="green",
                linestyle="--",
            )
            ax.set_ylabel("Cumulative Bytes")
            ax.legend(loc="upper right")
            plt.title("Network Speed and Usage Over Time")
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(MAX_TICKER))
            plt.xticks(rotation=45)
            plt.grid(True, linestyle="--", alpha=0.3)
            plt.tight_layout()
            plots["byte_rate_trend"] = self._save(
                f"byte_rate_trend_{self.username}.png"
            )
        except Exception as e:
            logger.error(f"Network plot - Byte Rate Plot: {e}")

        return plots

    def _plot_process(self, process_df: pd.DataFrame):
        plots = {}
        if process_df.empty:
            return plots

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
            memory_total = agg_top_n.groupby("process_name")["memory_percent"].sum()
            # Normalize to 100%
            cpu_total_norm = cpu_total / cpu_total.sum() * 100
            memory_total_norm = memory_total / memory_total.sum() * 100

            # 4. CPU for Processes
            try:
                plt.figure(figsize=(12, 6))
                ax = cpu_total_norm.plot(kind="bar", color="skyblue")
                plt.title(f"Top {PROCESS_LIMIT} CPU-consuming Processes (Normalized %)")
                plt.ylabel("CPU % of Total")
                plt.ylim(0, 100)
                plt.xticks(rotation=80)
                for p in ax.patches:
                    height = p.get_height()
                    ax.annotate(
                        f"{height:.1f}%",
                        (p.get_x() + p.get_width() / 2, height),
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        xytext=(0, 3),
                        textcoords="offset points",
                    )
                plt.tight_layout()
                plt.grid(True)
                plots["top_cpu_process"] = self._save(
                    f"top_cpu_process_{self.username}.png"
                )
            except Exception as e:
                logger.error(f"Process plot - CPU for Processes: {e}")

            # 5. Memory for Processes
            try:
                plt.figure(figsize=(12, 6))
                ax = memory_total_norm.plot(kind="bar", color="lightgreen")
                plt.title(
                    f"Top {PROCESS_LIMIT} Memory-consuming Processes (Normalized %)"
                )
                plt.ylabel("Memory % of Total")
                plt.xticks(rotation=80)
                plt.ylim(0, 100)
                for p in ax.patches:
                    height = p.get_height()
                    ax.annotate(
                        f"{height:.1f}%",
                        (p.get_x() + p.get_width() / 2, height),
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        xytext=(0, 3),
                        textcoords="offset points",
                    )
                plt.tight_layout()
                plt.grid(True)
                plots["top_memory_process"] = self._save(
                    f"top_memory_process_{self.username}.png"
                )
            except Exception as e:
                logger.error(f"Process plot - Memory for Processes: {e}")
        except Exception as e:
            logger.error(f"Process - Data Pre Processing for plot: {e}")

        return plots

    def _plot_system(self, system_df: pd.DataFrame):
        plots = {}
        if system_df.empty:
            return plots

        # 6. CPU Load Trend Over Time
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(
                system_df["timestamp"], system_df["overall_cpu_load"], color=ACCENT
            )
            plt.title("CPU Load Trend Over Time")
            plt.xlabel("Time")
            plt.ylabel("CPU Load (%)")
            plt.ylim(0, 100)
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(5))
            plt.xticks(rotation=45)
            plt.grid(True)
            plt.tight_layout()
            plots["cpu_load_trend_over_time"] = self._save(
                f"cpu_load_trend_over_time_{self.username}.png"
            )
        except Exception as e:
            logger.error(f"System plot - CPU load trend over time: {e}")

        # 7. Memory Usage Trend Over Time
        try:
            plt.figure(figsize=(12, 6))
            plt.plot(system_df["timestamp"], system_df["vm_percent_used"], color=GREEN)
            plt.title("Memory Usage Trend Over Time")
            plt.xlabel("Time")
            plt.ylabel("Memory Used (%)")
            plt.ylim(0, 100)
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(5))
            plt.xticks(rotation=45)
            plt.grid(True)
            plots["memory_usage_trend_over_time"] = self._save(
                f"memory_usage_trend_over_time_{self.username}.png"
            )
        except Exception as e:
            logger.error(f"System plot - Memory Usage trend over time: {e}")

        # 8. Battery Percentage Trend Over Time
        try:
            plt.figure(figsize=(10, 4))
            plt.plot(
                system_df["timestamp"],
                system_df["battery_percent"],
                color=ORANGE,
            )
            plt.title("Battery Percentage Trend Over Time")
            plt.xlabel("Time")
            plt.ylabel("Battery (%)")
            plt.ylim(0, 100)
            plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(5))
            plt.xticks(rotation=45)
            plt.grid(True)
            plots["battery_pct_over_time"] = self._save(
                f"battery_pct_over_time_{self.username}.png"
            )
        except Exception as e:
            logger.error(f"System plot - Battery Percentage trend over time: {e}")

        return plots

    def run(self, date: str = None):
        if date is None:
            date = str(datetime.today().day)

        network_df, process_df, system_df = self.load(date)

        network_plot = self._plot_network(network_df)
        process_plot = self._plot_process(process_df)
        system_plot = self._plot_system(system_df)

        return (
            network_df,
            process_df,
            system_df,
            network_plot,
            process_plot,
            system_plot,
        )
