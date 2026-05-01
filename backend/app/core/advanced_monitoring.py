"""
Advanced Logging, Monitoring & Observability System
Real-time metrics, performance tracking, and distributed tracing
"""

import logging
import time
import asyncio
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data point"""
    operation: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    status: str = "success"  # success, failed
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DistributedTraceSpan:
    """Distributed trace span"""
    trace_id: str
    span_id: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    parent_span_id: Optional[str] = None
    status: str = "active"
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def duration_ms(self) -> float:
        """Get span duration in milliseconds"""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000


class MetricsCollector:
    """Collects and aggregates performance metrics"""
    
    def __init__(self, window_size: int = 300):
        self.metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self.window_size = window_size  # seconds
        self.lock = threading.Lock()
    
    def record_metric(self, operation: str, duration_ms: float, status: str = "success", metadata: Dict = None):
        """Record a performance metric"""
        metric = PerformanceMetric(
            operation=operation,
            duration_ms=duration_ms,
            status=status,
            metadata=metadata or {}
        )
        
        with self.lock:
            self.metrics[operation].append(metric)
            self._cleanup_old_metrics(operation)
    
    def _cleanup_old_metrics(self, operation: str):
        """Remove metrics older than window"""
        current_time = time.time()
        cutoff = current_time - self.window_size
        
        self.metrics[operation] = [
            m for m in self.metrics[operation]
            if m.timestamp > cutoff
        ]
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for an operation"""
        with self.lock:
            metrics = self.metrics.get(operation, [])
        
        if not metrics:
            return {"error": "No metrics found"}
        
        durations = [m.duration_ms for m in metrics]
        success_count = sum(1 for m in metrics if m.status == "success")
        
        return {
            "operation": operation,
            "count": len(metrics),
            "success_count": success_count,
            "error_count": len(metrics) - success_count,
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "avg_duration_ms": sum(durations) / len(durations),
            "p50_duration_ms": sorted(durations)[len(durations) // 2],
            "p99_duration_ms": sorted(durations)[int(len(durations) * 0.99)]
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all operations"""
        with self.lock:
            operations = list(self.metrics.keys())
        
        return {
            op: self.get_operation_stats(op)
            for op in operations
        }


class DistributedTracer:
    """Manages distributed tracing"""
    
    def __init__(self):
        self.traces: Dict[str, Dict[str, DistributedTraceSpan]] = {}
        self.active_spans: Dict[str, DistributedTraceSpan] = {}
        self.lock = threading.Lock()
    
    def create_trace(self, trace_id: str) -> str:
        """Create a new trace"""
        with self.lock:
            if trace_id not in self.traces:
                self.traces[trace_id] = {}
        return trace_id
    
    def start_span(self, trace_id: str, span_id: str, operation: str, parent_span_id: str = None) -> DistributedTraceSpan:
        """Start a new trace span"""
        span = DistributedTraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            operation=operation,
            start_time=time.time(),
            parent_span_id=parent_span_id
        )
        
        with self.lock:
            if trace_id not in self.traces:
                self.traces[trace_id] = {}
            self.traces[trace_id][span_id] = span
            self.active_spans[span_id] = span
        
        return span
    
    def end_span(self, span_id: str, status: str = "success", tags: Dict = None):
        """End a trace span"""
        with self.lock:
            if span_id in self.active_spans:
                span = self.active_spans[span_id]
                span.end_time = time.time()
                span.status = status
                if tags:
                    span.tags.update(tags)
                del self.active_spans[span_id]
    
    def add_log_to_span(self, span_id: str, message: str, level: str = "info", context: Dict = None):
        """Add a log entry to a span"""
        with self.lock:
            if span_id in self.active_spans:
                self.active_spans[span_id].logs.append({
                    "timestamp": time.time(),
                    "level": level,
                    "message": message,
                    "context": context or {}
                })
    
    def get_trace(self, trace_id: str) -> Optional[Dict[str, DistributedTraceSpan]]:
        """Get a complete trace"""
        with self.lock:
            return self.traces.get(trace_id)
    
    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """Get summary of a trace"""
        with self.lock:
            spans = self.traces.get(trace_id, {})
        
        if not spans:
            return {"error": "Trace not found"}
        
        spans_list = list(spans.values())
        total_duration = max(s.end_time or time.time() for s in spans_list) - min(s.start_time for s in spans_list)
        
        return {
            "trace_id": trace_id,
            "span_count": len(spans),
            "total_duration_ms": total_duration * 1000,
            "spans": {
                span_id: {
                    "operation": span.operation,
                    "duration_ms": span.duration_ms(),
                    "status": span.status,
                    "logs_count": len(span.logs)
                }
                for span_id, span in spans.items()
            }
        }


class AdvancedMonitor:
    """Advanced monitoring and observability system"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.tracer = DistributedTracer()
        self.system_state = {
            "uptime_seconds": 0,
            "start_time": time.time(),
            "last_update": None
        }
        self.alert_thresholds = {
            "high_latency_ms": 5000,
            "error_rate_percent": 10
        }
        self.alerts = []
    
    def record_operation(self, operation: str, duration_ms: float, status: str = "success", metadata: Dict = None):
        """Record an operation metric"""
        self.metrics_collector.record_metric(operation, duration_ms, status, metadata)
        
        # Check thresholds
        if duration_ms > self.alert_thresholds["high_latency_ms"]:
            self._trigger_alert(f"High latency detected for {operation}: {duration_ms}ms")
    
    def start_distributed_trace(self, operation: str) -> tuple[str, str]:
        """Start a new distributed trace"""
        import uuid
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        self.tracer.create_trace(trace_id)
        self.tracer.start_span(trace_id, span_id, operation)
        
        return trace_id, span_id
    
    def _trigger_alert(self, message: str):
        """Trigger an alert"""
        alert = {
            "timestamp": time.time(),
            "message": message,
            "severity": "warning"
        }
        self.alerts.append(alert)
        logger.warning(f"ALERT: {message}")
        
        # Keep only recent alerts
        if len(self.alerts) > 100:
            self.alerts.pop(0)
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get comprehensive monitoring statistics"""
        uptime = time.time() - self.system_state["start_time"]
        
        return {
            "system": {
                "uptime_seconds": uptime,
                "start_time": self.system_state["start_time"]
            },
            "operations": self.metrics_collector.get_all_stats(),
            "recent_alerts": self.alerts[-10:],
            "active_traces": len(self.tracer.active_spans)
        }


class RealTimeMonitoringWebSocket:
    """WebSocket handler for real-time monitoring"""
    
    def __init__(self, monitor: AdvancedMonitor):
        self.monitor = monitor
        self.subscribers = []
    
    async def subscribe(self, callback):
        """Subscribe to monitoring updates"""
        self.subscribers.append(callback)
    
    async def broadcast_metrics(self):
        """Broadcast metrics to all subscribers"""
        while True:
            stats = self.monitor.get_monitoring_stats()
            
            for callback in self.subscribers:
                try:
                    await callback(stats)
                except Exception as e:
                    logger.error(f"Error sending metrics: {e}")
            
            await asyncio.sleep(1)  # Update every second


# Global monitoring instance
advanced_monitor = AdvancedMonitor()
