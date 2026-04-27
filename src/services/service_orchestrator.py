import threading, time
from datetime import datetime, timezone, timedelta
from src.services.system_metrics import SystemMetrics
from src.services.process_monitor import ProcessMonitor
from src.services.network_monitor import NetworkMonitor
from src.config import SYSTEM_METRICS_INTERVAL, MAX_MONITOR_MINUTES
from src.database import (
    insert_system_metric,
    insert_process_metrics,
    insert_network_metric,
    get_setting,
)
from src.logger import logger


IST = timezone(timedelta(hours=5, minutes=30))


class ServiceOrchestrator:
    """
    Orchestrates periodic collection of system, process and network metrics in a background thread and persists them to the database.

    This class manages the lifecycle of a monitoring session, including starting, stopping, progress tracking, and enforcing duration limits

    Args:
        username(str): Identifier used to associate collected metrics
        interval(int | optional): Time in seconds between metric collections. Defaults to SYSTEM_METRICS_INTERVAL from config

    Attributes:
        - username(str): User identifier for metric
        - interval(int): Sampling interval in seconds
        - _running(bool): Indicates if monitoring is currently active
        - _thread(threading.Thread | None): Background worker thread
        - _progress(float): Progress of current session (0.0 to 1.0)
        - _samples(int): Number of samples collected
        - _status(str): Current state ("idle", "running", "done")

    Methods:
        - max_allowed_minutes(duration_minutes): Monitoring duration from settings
        - clamp_duration(requested_minutes): Restricts duration to allowed maximum
        - start(duration_minutes): Starts monitoring for a given duration
        - stop(): Stops monitoring prematurely
        - is_running: Returns whether monitoring is active
        - progress: Returns current progress(0-1)
        - samples: Returns number of collected samples
        - status: Returns current state of the service

    Private Method:
        - _collect_once: Collects system, process, and network metrics once and stores them in the database
        - _run: Executes the monitoring loop in a background thread for a specified duration
    """

    def __init__(self, username: str, interval: int = SYSTEM_METRICS_INTERVAL):
        """
        Initializes the ServiceOrchestrator instance and monitoring services.

        Sets up the database, initializes monitoring components, and prepares internal state variables used for tracking execution

        Args:
            - username(str): Identifier used to associate collected metrics
            - interval(int | optional): Time interval (in seconds) between metric collections. Defaults to SYSTEM_METRICS_INTERVAL
        """
        self.username = username
        self.interval = interval
        self._running = False
        self._thread = None
        self._progress = 0.0
        self._samples = 0
        self._status = "idle"

        self._sys = SystemMetrics()
        self._proc = ProcessMonitor()
        self._net = NetworkMonitor()

    @staticmethod
    def max_allowed_minutes() -> int:
        """
        Retrieves the maximum allowed monitoring duration from configuration.

        Returns:
            - int: Maximum permitted monitoring duration in minutes
        Note:
            - If max_monitor_minutes is not present in the settings table, the value from config.py will be used
        """
        return int(get_setting("max_monitor_minutes", MAX_MONITOR_MINUTES))

    def clamp_duration(self, requested_minutes: int) -> int:
        """
        Restricts the requested monitoring duration to the maximum allowed limit.

        Args:
            - requested_minutes(int): Desired monitoring duration in minutes
        Returns:
            - int: Adjusted duration that does not exceed the allowed maximum
        """
        limit = self.max_allowed_minutes()
        return min(requested_minutes, limit)

    def _collect_once(self):
        """
        Collects system, process, and network metrics once and stores them in the database.
        """
        ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        try:
            s = self._sys.collect()
            insert_system_metric(
                self.username,
                {
                    "timestamp": ts,
                    "overall_cpu_load": s.get("cpu_metrics", {}).get(
                        "overall_cpu_load"
                    ),
                    "vm_total_memory": s.get("memory_metrics", {}).get(
                        "vm_total_memory"
                    ),
                    "vm_available_memory": s.get("memory_metrics", {}).get(
                        "vm_available_memory"
                    ),
                    "vm_used_memory": s.get("memory_metrics", {}).get("vm_used_memory"),
                    "vm_percent_used": s.get("memory_metrics", {}).get(
                        "vm_percent_used"
                    ),
                    "swap_memory_available_total": s.get("memory_metrics", {}).get(
                        "swap_memory_available_total"
                    ),
                    "swap_memory_used": s.get("memory_metrics", {}).get(
                        "swap_memory_used"
                    ),
                    "current_battery_percent": s.get("battery_metrics", {}).get(
                        "current_battery_percent"
                    ),
                },
            )
        except Exception as e:
            logger.error(f"System collect error [{self.username}]: {e}")

        try:
            procs = self._proc.collect()
            insert_process_metrics(self.username, ts, procs)
        except Exception as e:
            logger.error(f"Process collect error [{self.username}]: {e}")

        try:
            n = self._net.collect()
            insert_network_metric(self.username, {"timestamp": ts, **n})
        except Exception as e:
            logger.error(f"Network collect error [{self.username}]: {e}")

        self._samples += 1

    def _run(self, duration_sec: int):
        """
        Executes the monitoring loop in a background thread for a specified duration.

        Args:
            duration_sec(int): Total duration for monitoring in seconds
        """
        end = time.time() + duration_sec
        self._running = True
        self._status = "running"
        logger.info(f"Monitoring started [{self.username}] for {duration_sec}s")
        while self._running and time.time() < end:
            self._collect_once()
            elapsed = duration_sec - (end - time.time())
            self._progress = min(elapsed / duration_sec, 1.0)
            time.sleep(self.interval)
        self._running = False
        self._progress = 1.0
        self._status = "done"
        logger.info(f"Monitoring done [{self.username}] — {self._samples} samples")

    def start(self, duration_minutes: int):
        """
        Starts the monitoring process in a background thread.

        Args:
            - duration_minutes(int): Desired monitoring duration in minutes
        Returns:
            - int: The actual duration used after applying limits.
        """
        clamped = self.clamp_duration(duration_minutes)
        self._samples = 0
        self._progress = 0.0
        self._thread = threading.Thread(
            target=self._run, args=(clamped * 60,), daemon=True
        )
        self._thread.start()
        return clamped

    def stop(self):
        """
        Stops the ongoing monitoring process.
        """
        self._running = False

    @property
    def is_running(self) -> bool:
        """
        Indicates whether the monitoring process is currently active.

        Returns:
            - bool: True if monitoring is running, False otherwise
        """
        return self._running

    @property
    def progress(self) -> float:
        """
        Returns the progress of the current monitoring session.

        Returns:
            - float: Fraction of monitoring completed
        """
        return self._progress

    @property
    def samples(self) -> int:
        """
        Returns the number of metric samples collected so far.

        Returns:
            - int: Total number of collected samples
        """
        return self._samples

    @property
    def status(self) -> str:
        """
        Returns the current status of the monitoring process.

        Possible values:
            - "idle": Not started
            - "running": Currently collecting metrics
            - "done": Completed execution

        Returns:
            - str: Current monitoring status
        """
        return self._status
