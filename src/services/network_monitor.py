import psutil
import time
from src.services.base_service import BaseService
from src.config.config import NETWORK_MONITOR_INTERVAL
from src.logger.logger import Logger

logger = Logger().setup_logs()


class NetworkMonitor(BaseService):
    def collect(self) -> dict:
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
