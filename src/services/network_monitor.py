import psutil
import time
from src.services.base_service import BaseService
from src.config import NETWORK_MONITOR_INTERVAL
from src.logger import logger


class NetworkMonitor(BaseService):
    """
    Monitor system network activity.

    This class collects network I/O metrics by comparing network counters over a short interval to estimate upload and download speed

    Inherits: BaseService

    Methods:
        collect(): collect network metrics and return them as a dictionary.
    """

    def collect(self) -> dict:
        """
        Collect network usage statistics.

        Captures network counters before and after the configured interval, then calculates upload and download speed during that period

        Returns:
            dict:
                Dictionary containing:
                    - upload_speed_mb (float): Upload speed during interval in MB.
                    - download_speed_mb (float): Download speed during interval in MB.
                    - bytes_sent (int): Total bytes sent since system boot.
                    - bytes_received (int): Total bytes received since system boot.
        Example:
            {
                "upload_speed_mb": 1.23,
                "download_speed_mb": 1.23,
                "bytes_sent": 123456789,
                "bytes_received": 123456789
            }
        """
        try:
            logger.info("Collecting network metrics...")
            net_start = psutil.net_io_counters()
            time.sleep(NETWORK_MONITOR_INTERVAL)
            net_end = psutil.net_io_counters()
            data = {
                "upload_speed_mb": round(
                    (net_end.bytes_sent - net_start.bytes_sent) / (1024**2), 2
                ),
                "download_speed_mb": round(
                    (net_end.bytes_recv - net_start.bytes_recv) / (1024**2), 2
                ),
                "bytes_sent": net_end.bytes_sent,
                "bytes_received": net_end.bytes_recv,
            }
            logger.info("Network metrics collected successfully.")
            return data
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
            return {}
