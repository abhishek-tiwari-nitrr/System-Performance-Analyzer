import psutil
from src.services.base_service import BaseService
from src.config.config import PROCESS_LIMIT
from src.logger.logger import Logger

logger = Logger().setup_logs()


class ProcessMonitor(BaseService):
    def __init__(self):
        self.limit = PROCESS_LIMIT

    def collect(self) -> list[dict]:
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
