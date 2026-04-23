import psutil
from src.services.base_service import BaseService
from src.config.config import PROCESS_LIMIT
from src.logger.logger import Logger

logger = Logger().setup_logs()


class ProcessMonitor(BaseService):
    """
    Monitor running system processes.

    This class gathers process statistics such as process ID, name, CPU usage, and memory usage. Processes are sorted by CPU usage and only the top configured results are returned

    Inherits: BaseService

    Attributes:
        limit (int): Maximum number of top processes to return.

    Methods:
        collect(): collect process metrics and return them as a list
    """

    def __init__(self):
        """
        Initialize the process monitor.

        Loads the maximum process result limit from configuration.
        """
        self.limit = PROCESS_LIMIT

    def collect(self) -> list[dict]:
        """
        Collect running process statistics.

        Retrieves active process information, sorts by CPU usage in descending order and returns the top configured processes

        Returns:
            list[dict]:
                List of dictionaries containing:
                    - pid (int): Process ID
                    - name (str): Process name
                    - cpu_percent (float): CPU usage percentage
                    - memory_percent (float): Memory usage percentage
        Example:
            [
                {
                    "pid": 1234,
                    "name": "python",
                    "cpu_percent": 20.5,
                    "memory_percent": 3.2
                }
            ]

        """
        try:
            logger.info("Collecting process metrics...")
            processes = []
            for proc in psutil.process_iter(
                attrs=["pid", "name", "cpu_percent", "memory_percent"]
            ):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
            logger.info(f"Top {self.limit} processes collected.")
            return processes[: self.limit]
        except Exception as e:
            logger.error(f"Error collecting process metrics: {e}")
            return []
