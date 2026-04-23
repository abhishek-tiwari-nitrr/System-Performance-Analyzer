import psutil
import numpy as np
from datetime import datetime, timezone, timedelta
from src.services.base_service import BaseService
from src.config.config import SYSTEM_METRICS_INTERVAL
from src.logger.logger import Logger

logger = Logger().setup_logs()
IST = timezone(timedelta(hours=5, minutes=30))

class SystemMetrics(BaseService):
    """
    Collect system-level health and performance metrics.

    This class gathers CPU load, memory usage, and battery percentage. Metrics are organized into separate sections and returned with a timestamp

    Inherits: BaseService

    Methods:
        collect(): collect all system metrics
        
    Private Methods:
        _cpu_metrics(): measure per-core CPU usage and return the mean
        _memory_metrics(): read virtual and swap memory statistics
        _battery_metrics(): read current battery charge level, if available

    """
    def _cpu_metrics(self) -> dict:
        """
        Measure CPU usage averaged across all cores.

        Measures per-core CPU usage over a sampling interval and calculates the average CPU load across all cores

        Returns:
            dict:
                Dictionary containing:
                    overall_cpu_load (float): Mean CPU utilisation across all logical cores, expressed as a percentage (0.0-100.0)
        Example:
            {
                "overall_cpu_load": 12.0
            }
                
        """
        per_core_usage = psutil.cpu_percent(
            interval=SYSTEM_METRICS_INTERVAL, percpu=True
        )
        overall_cpu_load = float(np.array(per_core_usage, dtype=np.float64).mean())
        return {"overall_cpu_load": overall_cpu_load}

    def _memory_metrics(self) -> dict:
        """
        Collect memory usage metrics.

        Retrieves virtual memory and swap memory statistics

        Returns:
            dict:
                Dictionary containing:
                    - vm_total_memory(float): Total installed RAM, in GB
                    - vm_available_memory(float): RAM available for new processes without swapping, in GB
                    - vm_used_memory(float): RAM actively in use, in GB
                    - vm_percent_used(float): Percentage of total RAM currently in use (0.0-100.0)
                    - swap_memory_available_total: Total swap memory configured on system, in GB
                    - swap_memory_used(float): Swap space currently occupied, in GB
        Example:
            {
                "vm_total_memory": 16.0,
                "vm_available_memory": 8.4,
                "vm_used_memory": 7.2,
                "vm_percent_used": 45.0,
                "swap_memory_available_total": 4.0,
                "swap_memory_used": 0.8
            }
        """
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
        """
        Collect battery metrics.

        Retrieves current battery percentage if available

        Returns:
            dict:
                Dictionary containing:
                    - current_battery_percent(float): current battery percentage (0.0-100.0)
        Example (battery present):
            {
                "current_battery_percent": 75.0
            }
        Example (no battery):
            {
                "current_battery_percent": None
            }
        """
        battery = psutil.sensors_battery()
        if battery:
            current_battery_percentage = battery.percent
            return {"current_battery_percent": current_battery_percentage}
        return {"current_battery_percent": None}

    def collect(self) -> dict:
        """
        Collect all system metrics.

        Returns:
            dict:
                Dictionary containing:
                    - timestamp (datetime): UTC datetime when the collection completed
                    - cpu_metrics(dict): output of _cpu_metrics
                    - memory_metrics(dict): output of _memory_metrics
                    - battery_metrics(dict): output of _battery_metrics
        Example:
            {
            "timestamp": datetime(2026, 4, 23, 15, 31, 0, tzinfo=IST),
            "cpu_metrics": {
                                "overall_cpu_load": 12.0
                            },
            "memory_metrics": {
                                "vm_total_memory": 16.0,
                                "vm_available_memory": 8.4,
                                "vm_used_memory": 7.2,
                                "vm_percent_used": 45.0,
                                "swap_memory_available_total": 4.0,
                                "swap_memory_used": 0.8
                                },
            "battery_metrics": {
                                "current_battery_percent": 75.0
                                } 
            }
        """
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
