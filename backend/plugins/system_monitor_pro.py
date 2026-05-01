"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS PLUGIN — System Monitor Pro
  Real-time system health monitoring + alerts plugin.
  Tracks CPU, RAM, Disk, Network — raises warnings when thresholds exceeded.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import time
import threading
import logging
from datetime import datetime
from typing import Optional
from app.core.plugin_loader import IgrisPlugin

logger = logging.getLogger(__name__)


class SystemMonitorPlugin(IgrisPlugin):
    """
    Monitors system resources in real-time.
    Raises alerts when CPU > 85%, RAM > 90%, or Disk > 95%.
    Commands: system_health, clear_alerts, set_threshold
    """

    NAME        = "system_monitor_pro"
    VERSION     = "2.0.0"
    DESCRIPTION = "Real-time system health monitoring with intelligent threshold alerts"
    AUTHOR      = "Igris OS Core Team"
    REQUIRES    = ["psutil"]
    TAGS        = ["system", "monitoring", "alerts", "production"]

    # Default alert thresholds (%)
    CPU_THRESHOLD    = 85
    RAM_THRESHOLD    = 90
    DISK_THRESHOLD   = 95
    TEMP_THRESHOLD   = 80   # Celsius

    def __init__(self):
        self._alerts: list       = []
        self._stats_history: list = []
        self._loaded_at: Optional[float] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._running: bool      = False
        self._check_interval: float = 10.0   # seconds

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_load(self) -> None:
        self._loaded_at = time.time()
        self._running   = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True, name="IgrisSystemMonitor"
        )
        self._monitor_thread.start()
        logger.info("[SystemMonitorPlugin] Started background monitoring ✅")

    def on_unload(self) -> None:
        self._running = False
        logger.info(
            "[SystemMonitorPlugin] Stopped. %d alerts generated.", len(self._alerts)
        )

    def on_startup(self) -> None:
        logger.info("[SystemMonitorPlugin] System monitoring is ACTIVE 🛡️")

    def on_shutdown(self) -> None:
        self._running = False
        logger.info("[SystemMonitorPlugin] Shutdown — monitoring stopped.")

    # ── Hook: Commands ───────────────────────────────────────────────────────

    def on_command(self, command: str, args: dict):
        if command == "system_health":
            return self._get_health_report()
        if command == "clear_alerts":
            count = len(self._alerts)
            self._alerts.clear()
            return {"status": "cleared", "alerts_removed": count}
        if command == "set_threshold":
            return self._set_threshold(
                args.get("metric", ""),
                args.get("value", 0)
            )
        if command == "stats_history":
            limit = int(args.get("limit", 20))
            return {"history": self._stats_history[-limit:]}
        return None

    def on_message(self, user_msg: str, ai_response: str) -> Optional[str]:
        """Append active alerts notice to AI responses if system is critical."""
        critical = [a for a in self._alerts if a.get("level") == "CRITICAL"]
        if critical and len(critical) > 0:
            warning_text = (
                f"\n\n⚠️ **System Alert:** {len(critical)} critical resource "
                f"alert(s) active — use `system_health` command to inspect."
            )
            return ai_response + warning_text
        return None

    # ── Internal monitoring loop ─────────────────────────────────────────────

    def _monitoring_loop(self) -> None:
        while self._running:
            try:
                self._check_resources()
            except Exception as e:
                logger.error("[SystemMonitorPlugin] Monitor error: %s", e)
            time.sleep(self._check_interval)

    def _check_resources(self) -> None:
        try:
            import psutil
            cpu    = psutil.cpu_percent(interval=1)
            ram    = psutil.virtual_memory().percent
            disk   = psutil.disk_usage("/").percent if not __import__("os").name == "nt" \
                     else psutil.disk_usage("C:").percent
            net    = psutil.net_io_counters()
            now    = datetime.now().isoformat()

            snapshot = {
                "timestamp": now,
                "cpu":   cpu,
                "ram":   ram,
                "disk":  disk,
                "net_sent_mb":  round(net.bytes_sent / 1_048_576, 2),
                "net_recv_mb":  round(net.bytes_recv / 1_048_576, 2),
            }
            self._stats_history.append(snapshot)
            # Keep last 500 snapshots
            if len(self._stats_history) > 500:
                self._stats_history = self._stats_history[-500:]

            # Alert checks
            if cpu  > self.CPU_THRESHOLD:
                self._raise_alert("CPU",  cpu,  self.CPU_THRESHOLD, now)
            if ram  > self.RAM_THRESHOLD:
                self._raise_alert("RAM",  ram,  self.RAM_THRESHOLD, now)
            if disk > self.DISK_THRESHOLD:
                self._raise_alert("DISK", disk, self.DISK_THRESHOLD, now)

        except Exception as e:
            logger.debug("[SystemMonitorPlugin] Resource check failed: %s", e)

    def _raise_alert(self, metric: str, value: float, threshold: float, ts: str) -> None:
        level = "CRITICAL" if value > threshold + 5 else "WARNING"
        alert = {
            "metric":    metric,
            "value":     value,
            "threshold": threshold,
            "level":     level,
            "timestamp": ts,
        }
        self._alerts.append(alert)
        # Keep last 200 alerts
        if len(self._alerts) > 200:
            self._alerts = self._alerts[-200:]
        logger.warning(
            "[SystemMonitorPlugin] %s ALERT — %s at %.1f%% (threshold %.1f%%)",
            level, metric, value, threshold
        )

    def _get_health_report(self) -> dict:
        try:
            import psutil
            cpu    = psutil.cpu_percent(interval=0.5)
            vm     = psutil.virtual_memory()
            disk   = psutil.disk_usage("/") if not __import__("os").name == "nt" \
                     else psutil.disk_usage("C:")
            net    = psutil.net_io_counters()
            return {
                "status":      "healthy" if cpu < self.CPU_THRESHOLD and vm.percent < self.RAM_THRESHOLD else "degraded",
                "cpu_percent": cpu,
                "ram_percent": vm.percent,
                "ram_available_gb": round(vm.available / 1_073_741_824, 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / 1_073_741_824, 2),
                "net_sent_mb":  round(net.bytes_sent / 1_048_576, 2),
                "net_recv_mb":  round(net.bytes_recv / 1_048_576, 2),
                "active_alerts": len(self._alerts),
                "recent_alerts": self._alerts[-5:],
                "thresholds": {
                    "cpu":  self.CPU_THRESHOLD,
                    "ram":  self.RAM_THRESHOLD,
                    "disk": self.DISK_THRESHOLD,
                },
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    def _set_threshold(self, metric: str, value) -> dict:
        try:
            value = float(value)
            if metric.upper() == "CPU":
                self.CPU_THRESHOLD = value
            elif metric.upper() == "RAM":
                self.RAM_THRESHOLD = value
            elif metric.upper() == "DISK":
                self.DISK_THRESHOLD = value
            else:
                return {"error": f"Unknown metric: {metric}. Use CPU, RAM, or DISK."}
            return {"status": "updated", "metric": metric.upper(), "new_threshold": value}
        except (ValueError, TypeError):
            return {"error": "value must be a number (0-100)"}

    # ── Info ─────────────────────────────────────────────────────────────────

    def get_commands(self) -> list:
        return [
            {"name": "system_health",  "args": [],                    "description": "Get full system health report"},
            {"name": "clear_alerts",   "args": [],                    "description": "Clear all active alerts"},
            {"name": "set_threshold",  "args": ["metric", "value"],   "description": "Set alert threshold (CPU/RAM/DISK %)"},
            {"name": "stats_history",  "args": ["limit"],             "description": "Get last N resource snapshots"},
        ]

    def get_status(self) -> dict:
        uptime = time.time() - self._loaded_at if self._loaded_at else 0
        return {
            "status":          "active" if self._running else "stopped",
            "uptime_secs":     round(uptime, 1),
            "alerts_count":    len(self._alerts),
            "history_entries": len(self._stats_history),
            "thresholds": {
                "cpu":  self.CPU_THRESHOLD,
                "ram":  self.RAM_THRESHOLD,
                "disk": self.DISK_THRESHOLD,
            },
            "monitor_interval_secs": self._check_interval,
        }
