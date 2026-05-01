"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS ORACLE PROTOCOL — Multi-Domain Prediction Engine                    ║
║  "I do not guess. I calculate the future."                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import math
import time
import json
import threading
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class Prediction:
    domain: str              # system | productivity | security | finance
    metric: str
    current_value: float
    predicted_value: float
    predicted_at: str        # when prediction is for
    confidence: float        # 0–1
    direction: str           # up | down | stable
    alert: bool
    alert_message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class OracleProtocol:
    """
    Igris Oracle — uses time-series trend analysis to predict:

    • System health      → CPU/RAM/Disk trend → will it crash?
    • Productivity       → Command rate → burnout prediction
    • Security           → Unusual process patterns → threat prediction
    • Finance            → Basic momentum indicator on price series

    Algorithm: Exponential weighted moving average (EWMA) + linear regression
    on recent window. No external ML deps required.
    """

    COLLECT_INTERVAL = 60       # seconds between system readings
    PREDICT_INTERVAL = 300      # seconds between prediction reports
    WINDOW           = 60       # number of points in prediction window
    CPU_ALERT_PCT    = 90.0
    RAM_ALERT_PCT    = 88.0
    DISK_ALERT_PCT   = 92.0

    def __init__(self):
        self._lock = threading.RLock()

        # Time-series buffers
        self._cpu_series:   deque = deque(maxlen=self.WINDOW)
        self._ram_series:   deque = deque(maxlen=self.WINDOW)
        self._disk_series:  deque = deque(maxlen=self.WINDOW)
        self._cmd_series:   deque = deque(maxlen=self.WINDOW)   # commands/min

        self._latest_predictions: List[Prediction] = []
        self._prophecy_log: deque = deque(maxlen=500)
        self._command_times: deque = deque(maxlen=200)

        # Start background loops
        threading.Thread(target=self._collect_loop, daemon=True).start()
        threading.Thread(target=self._predict_loop, daemon=True).start()
        logger.info("[ORACLE] 🔮 Oracle Protocol activated.")

    # ──────────────────────────────────────────────────────────────────
    # DATA INGESTION
    # ──────────────────────────────────────────────────────────────────

    def record_command(self):
        """Call whenever a user command is processed."""
        self._command_times.append(time.time())

    def feed_price_series(self, symbol: str, prices: List[float]):
        """Feed a price series for financial prediction."""
        if len(prices) < 3:
            return
        with self._lock:
            pred = self._predict_finance(symbol, prices)
            if pred:
                self._latest_predictions.append(pred)
                self._prophecy_log.append(pred)

    # ──────────────────────────────────────────────────────────────────
    # COLLECTION LOOP
    # ──────────────────────────────────────────────────────────────────

    def _collect_loop(self):
        while True:
            try:
                if PSUTIL_AVAILABLE:
                    cpu  = psutil.cpu_percent(interval=1)
                    ram  = psutil.virtual_memory().percent
                    disk = psutil.disk_usage('/').percent
                    with self._lock:
                        self._cpu_series.append(cpu)
                        self._ram_series.append(ram)
                        self._disk_series.append(disk)

                # Commands per minute
                now = time.time()
                recent = sum(1 for t in self._command_times if now - t < 60)
                with self._lock:
                    self._cmd_series.append(recent)

            except Exception as e:
                logger.debug("[ORACLE] Collect error: %s", e)
            time.sleep(self.COLLECT_INTERVAL)

    # ──────────────────────────────────────────────────────────────────
    # PREDICTION LOOP
    # ──────────────────────────────────────────────────────────────────

    def _predict_loop(self):
        time.sleep(60)   # Initial warm-up
        while True:
            try:
                preds = self._run_all_predictions()
                with self._lock:
                    self._latest_predictions = preds
                    for p in preds:
                        self._prophecy_log.append(p)
                        if p.alert:
                            logger.warning("[ORACLE] ⚠️  ALERT: %s", p.alert_message)
            except Exception as e:
                logger.debug("[ORACLE] Predict error: %s", e)
            time.sleep(self.PREDICT_INTERVAL)

    def _run_all_predictions(self) -> List[Prediction]:
        preds = []
        with self._lock:
            cpu_series  = list(self._cpu_series)
            ram_series  = list(self._ram_series)
            disk_series = list(self._disk_series)
            cmd_series  = list(self._cmd_series)

        for series, metric, alert_thresh, domain in [
            (cpu_series,  "CPU Usage",  self.CPU_ALERT_PCT,  "system"),
            (ram_series,  "RAM Usage",  self.RAM_ALERT_PCT,  "system"),
            (disk_series, "Disk Usage", self.DISK_ALERT_PCT, "system"),
        ]:
            if len(series) >= 5:
                p = self._predict_trend(series, metric, domain, alert_thresh, unit="%")
                if p:
                    preds.append(p)

        # Productivity prediction
        if len(cmd_series) >= 5:
            p = self._predict_trend(cmd_series, "Commands/min", "productivity", 15.0, unit="cmd/min")
            if p:
                preds.append(p)

        return preds

    # ──────────────────────────────────────────────────────────────────
    # MATH: EWMA + LINEAR REGRESSION
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _ewma(series: List[float], alpha: float = 0.3) -> List[float]:
        smoothed = [series[0]]
        for v in series[1:]:
            smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
        return smoothed

    @staticmethod
    def _linear_regression(y: List[float]) -> Tuple[float, float]:
        """Returns (slope, intercept) of best-fit line."""
        n = len(y)
        if n < 2:
            return 0.0, y[-1] if y else 0.0
        x_mean = (n - 1) / 2
        y_mean = sum(y) / n
        num = sum((i - x_mean) * (yi - y_mean) for i, yi in enumerate(y))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0
        intercept = y_mean - slope * x_mean
        return slope, intercept

    def _predict_trend(
        self, series: List[float], metric: str, domain: str,
        alert_threshold: float, steps_ahead: int = 5, unit: str = ""
    ) -> Optional[Prediction]:
        if len(series) < 3:
            return None
        smoothed = self._ewma(series)
        slope, intercept = self._linear_regression(smoothed)
        n = len(smoothed)
        predicted = slope * (n - 1 + steps_ahead) + intercept
        predicted = max(0.0, min(100.0, predicted))
        current   = smoothed[-1]
        direction = "up" if predicted > current + 1 else ("down" if predicted < current - 1 else "stable")
        confidence = min(0.95, max(0.3, 1.0 - abs(slope) * 0.5))

        alert = predicted >= alert_threshold
        msg   = (f"⚠️ {metric} predicted to reach {predicted:.1f}{unit} "
                 f"in {steps_ahead} min — ALERT threshold {alert_threshold}{unit}") if alert else ""

        return Prediction(
            domain=domain,
            metric=metric,
            current_value=round(current, 1),
            predicted_value=round(predicted, 1),
            predicted_at=(datetime.now() + timedelta(minutes=steps_ahead)).isoformat(),
            confidence=round(confidence, 2),
            direction=direction,
            alert=alert,
            alert_message=msg,
        )

    def _predict_finance(self, symbol: str, prices: List[float]) -> Optional[Prediction]:
        """Simple momentum predictor for price series."""
        if len(prices) < 5:
            return None
        short_ma = sum(prices[-3:]) / 3
        long_ma  = sum(prices[-10:]) / min(10, len(prices))
        momentum = (short_ma - long_ma) / long_ma * 100
        direction = "up" if momentum > 0.5 else ("down" if momentum < -0.5 else "stable")
        predicted = prices[-1] * (1 + momentum / 100)
        return Prediction(
            domain="finance",
            metric=f"{symbol} Price",
            current_value=round(prices[-1], 4),
            predicted_value=round(predicted, 4),
            predicted_at=(datetime.now() + timedelta(hours=24)).isoformat(),
            confidence=min(0.7, abs(momentum) / 10),
            direction=direction,
            alert=abs(momentum) > 5.0,
            alert_message=f"{symbol} momentum: {momentum:+.2f}%" if abs(momentum) > 5 else "",
        )

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    def get_latest_predictions(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._latest_predictions]

    def get_alerts(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._latest_predictions if p.alert]

    def get_prophecy_log(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in list(self._prophecy_log)[-limit:]]

    def get_stats(self) -> dict:
        with self._lock:
            total    = len(self._prophecy_log)
            alerts   = sum(1 for p in self._prophecy_log if p.alert)
            return {
                "total_predictions": total,
                "total_alerts": alerts,
                "latest": self.get_latest_predictions(),
                "active_alerts": self.get_alerts(),
                "data_points": {
                    "cpu":  len(self._cpu_series),
                    "ram":  len(self._ram_series),
                    "disk": len(self._disk_series),
                    "cmd":  len(self._cmd_series),
                },
            }


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[OracleProtocol] = None
_lock = threading.Lock()

def get_oracle_protocol() -> OracleProtocol:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = OracleProtocol()
    return _instance
