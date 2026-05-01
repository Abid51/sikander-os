"""
Advanced Logging, Monitoring & Analytics System
Real-time performance tracking, error analytics, and insights
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events to track"""
    API_REQUEST = "api_request"
    AI_RESPONSE = "ai_response"
    ERROR = "error"
    CLOUD_AI_FALLBACK = "cloud_ai_fallback"
    VOICE_COMMAND = "voice_command"
    PERFORMANCE = "performance"
    SECURITY = "security"
    SYSTEM = "system"


class AdvancedLogger:
    """Enterprise-grade logging system with analytics"""
    
    def __init__(self, max_events: int = 10000):
        self.events: List[Dict[str, Any]] = []
        self.max_events = max_events
        self.metrics = defaultdict(list)
        self.errors_by_type = defaultdict(int)
        self.endpoints_performance = defaultdict(list)
        self.response_times = []
        
    def log_event(
        self,
        event_type: EventType,
        endpoint: Optional[str],
        data: Dict[str, Any],
        status: str = "SUCCESS"
    ):
        """Log an event with full context"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type.value,
            "endpoint": endpoint,
            "data": data,
            "status": status
        }
        
        self.events.append(event)
        
        # Keep only recent events
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Track metrics
        self._update_metrics(event)
        logger.info(f"[{event_type.value}] {status}: {endpoint}")
    
    def log_api_request(
        self,
        endpoint: str,
        method: str,
        params: Dict[str, Any],
        ip_address: str
    ):
        """Log API request"""
        self.log_event(
            EventType.API_REQUEST,
            endpoint,
            {
                "method": method,
                "params": params,
                "ip": ip_address
            }
        )
    
    def log_ai_response(
        self,
        provider: str,
        endpoint: Optional[str],
        prompt: str,
        response: str,
        latency_ms: float,
        is_fallback: bool = False
    ):
        """Log AI response with latency"""
        event_type = EventType.CLOUD_AI_FALLBACK if is_fallback else EventType.AI_RESPONSE
        
        self.log_event(
            event_type,
            endpoint,
            {
                "provider": provider,
                "prompt_length": len(prompt),
                "response_length": len(response),
                "latency_ms": latency_ms
            }
        )
        
        self.response_times.append(latency_ms)
    
    def log_error(
        self,
        error_type: str,
        endpoint: Optional[str],
        error_message: str,
        traceback: Optional[str] = None
    ):
        """Log error with full details"""
        self.errors_by_type[error_type] += 1
        
        self.log_event(
            EventType.ERROR,
            endpoint,
            {
                "error_type": error_type,
                "message": error_message,
                "traceback": traceback
            },
            status="ERROR"
        )
    
    def log_voice_command(
        self,
        command: str,
        language: str,
        success: bool,
        execution_time_ms: float
    ):
        """Log voice command execution"""
        self.log_event(
            EventType.VOICE_COMMAND,
            None,
            {
                "command": command,
                "language": language,
                "success": success,
                "execution_time": execution_time_ms
            }
        )
    
    def _update_metrics(self, event: Dict[str, Any]):
        """Update internal metrics"""
        event_type = event["type"]
        self.metrics[event_type].append(event)
        
        if event.get("endpoint"):
            self.endpoints_performance[event["endpoint"]].append(event)
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get comprehensive analytics"""
        total_events = len(self.events)
        recent_events = self.events[-100:] if self.events else []
        
        avg_response_time = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times
            else 0
        )
        
        endpoint_stats = {}
        for endpoint, events in self.endpoints_performance.items():
            endpoint_stats[endpoint] = {
                "total_requests": len(events),
                "success_rate": sum(1 for e in events if e["status"] == "SUCCESS") / len(events) * 100
            }
        
        return {
            "total_events": total_events,
            "recent_events": recent_events,
            "avg_response_time_ms": avg_response_time,
            "error_summary": dict(self.errors_by_type),
            "endpoint_stats": endpoint_stats,
            "event_type_summary": {
                k: len(v) for k, v in self.metrics.items()
            }
        }
    
    def get_health_score(self) -> float:
        """Calculate system health score (0-100)"""
        if not self.events:
            return 100.0
        
        recent = self.events[-1000:] if len(self.events) > 1000 else self.events
        success_count = sum(1 for e in recent if e["status"] == "SUCCESS")
        error_count = self.errors_by_type.get("total", 0)
        
        health = (success_count / len(recent) * 100) - (error_count * 2)
        return max(0, min(100, health))
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate detailed performance report"""
        if not self.response_times:
            return {"status": "No data"}
        
        sorted_times = sorted(self.response_times)
        count = len(sorted_times)
        
        return {
            "min_ms": sorted_times[0],
            "max_ms": sorted_times[-1],
            "avg_ms": sum(sorted_times) / count,
            "p50_ms": sorted_times[count // 2],
            "p95_ms": sorted_times[int(count * 0.95)],
            "p99_ms": sorted_times[int(count * 0.99)],
            "total_requests": count
        }
    
    def get_error_report(self) -> Dict[str, Any]:
        """Get detailed error analysis"""
        error_events = [e for e in self.events if e["status"] == "ERROR"]
        
        return {
            "total_errors": len(error_events),
            "errors_by_type": dict(self.errors_by_type),
            "recent_errors": error_events[-20:],
            "error_trend": self._calculate_error_trend()
        }
    
    def _calculate_error_trend(self) -> str:
        """Determine if errors are increasing or decreasing"""
        if len(self.events) < 100:
            return "INSUFFICIENT_DATA"
        
        first_half = self.events[:len(self.events)//2]
        second_half = self.events[len(self.events)//2:]
        
        first_errors = sum(1 for e in first_half if e["status"] == "ERROR")
        second_errors = sum(1 for e in second_half if e["status"] == "ERROR")
        
        if second_errors > first_errors * 1.2:
            return "INCREASING"
        elif second_errors < first_errors * 0.8:
            return "DECREASING"
        else:
            return "STABLE"


# Global logger instance
advanced_logger = AdvancedLogger()
