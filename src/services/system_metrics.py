import psutil
import numpy as np
from datetime import datetime, timezone, timedelta
from src.services.base_service import BaseService
from src.config.config import SYSTEM_METRICS_INTERVAL
from src.logger.logger import Logger

logger = Logger().setup_logs()
IST = timezone(timedelta(hours=5, minutes=30))

class SystemMetrics(BaseService):
    def _cpu_metrics(self) -> dict:
        per_core_usage = psutil.cpu_percent(
            interval=SYSTEM_METRICS_INTERVAL, percpu=True
        )
        overall_cpu_load = float(np.array(per_core_usage, dtype=np.float64).mean())
        return {"overall_cpu_load": overall_cpu_load}

    def _memory_metrics(self) -> dict:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "vm_total_memory": round(vm.total / 1e9, 2),
            "vm_available_memory": round(vm.available / 1e9, 2),
            "vm_used_memory": round(vm.used / 1e9, 2),
            "vm_percent_used": vm.percent,
            "swap_memory_available_total": round(swap.total / 1e9, 2),
            "swap_memory_used": round(swap.used / 1e9, 2)
        }

    def _battery_metrics(self) -> dict:
        battery = psutil.sensors_battery()
        if battery:
            current_battery_percentage = battery.percent
            return {"current_battery_percent": current_battery_percentage}
        return {"current_battery_percent": None}

    def collect(self) -> dict:
        try:
            logger.info("Collecting system metrics...")
            data = {
                "timestamp": datetime.now(IST),
                "cpu_metrics": self._cpu_metrics(),
                "memory_metrics": self._memory_metrics(),
                "battery_metrics": self._battery_metrics(),
            }
            logger.info("System metrics collected successfully.")
            return data
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}
