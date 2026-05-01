"""
Advanced Monitoring & Analytics System
Real-time performance tracking and insights
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Real-time performance monitoring"""
    
    def __init__(self, max_samples: int = 10000):
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.max_samples = max_samples
        self.query_times: List[float] = []
        self.api_response_times: Dict[str, List[float]] = defaultdict(list)
        self.error_count: Dict[str, int] = defaultdict(int)
        self.uptime_start = datetime.now()
    
    def record_metric(self, metric_name: str, value: float) -> None:
        """Record a metric value"""
        self.metrics[metric_name].append(value)
        
        # Keep only recent samples
        if len(self.metrics[metric_name]) > self.max_samples:
            self.metrics[metric_name] = self.metrics[metric_name][-self.max_samples:]
    
    def record_api_response_time(self, endpoint: str, response_time_ms: float) -> None:
        """Record API response time"""
        self.api_response_times[endpoint].append(response_time_ms)
        
        if len(self.api_response_times[endpoint]) > self.max_samples:
            self.api_response_times[endpoint] = self.api_response_times[endpoint][-self.max_samples:]
    
    def record_error(self, error_type: str) -> None:
        """Record error occurrence"""
        self.error_count[error_type] += 1
    
    def get_metric_stats(self, metric_name: str) -> Dict[str, Any]:
        """Get statistics for a metric"""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return {"error": "No data"}
        
        values = self.metrics[metric_name]
        
        return {
            "metric_name": metric_name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "sum": sum(values)
        }
    
    def get_api_stats(self, endpoint: str = None) -> Dict[str, Any]:
        """Get API response time statistics"""
        if endpoint:
            if endpoint not in self.api_response_times or not self.api_response_times[endpoint]:
                return {"error": f"No data for {endpoint}"}
            
            times = self.api_response_times[endpoint]
            return {
                "endpoint": endpoint,
                "requests": len(times),
                "min_ms": min(times),
                "max_ms": max(times),
                "mean_ms": statistics.mean(times),
                "p95_ms": self._percentile(times, 95),
                "p99_ms": self._percentile(times, 99)
            }
        
        # All endpoints
        stats = {}
        for ep, times in self.api_response_times.items():
            if times:
                stats[ep] = {
                    "requests": len(times),
                    "mean_ms": statistics.mean(times),
                    "p99_ms": self._percentile(times, 99)
                }
        
        return stats
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            "total_errors": sum(self.error_count.values()),
            "errors_by_type": dict(self.error_count),
            "most_common": sorted(self.error_count.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def get_uptime(self) -> Dict[str, Any]:
        """Get system uptime"""
        uptime = datetime.now() - self.uptime_start
        
        return {
            "started_at": self.uptime_start.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": self._format_timedelta(uptime)
        }
    
    @staticmethod
    def _percentile(data: List[float], percentile: float) -> float:
        """Calculate percentile"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """Format timedelta as human readable"""
        total_seconds = int(td.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        if seconds: parts.append(f"{seconds}s")
        
        return " ".join(parts) if parts else "0s"


class Analytics:
    """Advanced analytics and insights"""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.user_activity: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self.command_frequency: Dict[str, int] = defaultdict(int)
    
    def track_event(self, event_type: str, user_id: Optional[int], 
                   details: Dict[str, Any]) -> None:
        """Track analytics event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details
        }
        
        self.events.append(event)
        
        if user_id:
            self.user_activity[user_id].append(event)
    
    def track_command(self, command: str, user_id: Optional[int] = None) -> None:
        """Track command usage"""
        self.command_frequency[command] += 1
        self.track_event("command_executed", user_id, {"command": command})
    
    def get_user_activity(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Get user activity for past N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        activities = [
            e for e in self.user_activity.get(user_id, [])
            if datetime.fromisoformat(e["timestamp"]) > cutoff_date
        ]
        
        return {
            "user_id": user_id,
            "days": days,
            "total_events": len(activities),
            "event_types": self._count_events_by_type(activities),
            "recent_activity": activities[-20:]
        }
    
    def get_top_commands(self, limit: int = 10) -> List[tuple]:
        """Get top used commands"""
        sorted_commands = sorted(
            self.command_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_commands[:limit]
    
    def get_user_engagement(self) -> Dict[str, Any]:
        """Get user engagement metrics"""
        total_users = len(self.user_activity)
        active_users = len([u for u in self.user_activity if self.user_activity[u]])
        
        avg_events_per_user = (
            sum(len(events) for events in self.user_activity.values()) / total_users
            if total_users > 0 else 0
        )
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "average_events_per_user": avg_events_per_user,
            "engagement_rate": (active_users / total_users * 100) if total_users > 0 else 0
        }
    
    def get_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get event trends"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_events = [
            e for e in self.events
            if datetime.fromisoformat(e["timestamp"]) > cutoff_time
        ]
        
        # Group by hour
        hourly_counts = defaultdict(int)
        for event in recent_events:
            dt = datetime.fromisoformat(event["timestamp"])
            hour_key = dt.strftime("%Y-%m-%d %H:00")
            hourly_counts[hour_key] += 1
        
        return {
            "period_hours": hours,
            "total_events": len(recent_events),
            "hourly_distribution": dict(sorted(hourly_counts.items())),
            "events_per_hour": sum(hourly_counts.values()) / max(len(hourly_counts), 1)
        }
    
    @staticmethod
    def _count_events_by_type(events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count events by type"""
        counts = defaultdict(int)
        for event in events:
            counts[event["event_type"]] += 1
        return dict(counts)


class HealthCheck:
    """System health monitoring"""
    
    def __init__(self):
        self.component_status: Dict[str, Dict[str, Any]] = {}
        self.checks_performed: int = 0
        self.last_check: Optional[datetime] = None
    
    def register_component(self, name: str, description: str) -> None:
        """Register component for health checks"""
        self.component_status[name] = {
            "name": name,
            "description": description,
            "status": "unknown",
            "last_check": None,
            "response_time_ms": 0
        }
    
    def update_component_status(self, name: str, status: str, 
                               response_time_ms: float = 0) -> None:
        """Update component status"""
        if name in self.component_status:
            self.component_status[name]["status"] = status
            self.component_status[name]["last_check"] = datetime.now().isoformat()
            self.component_status[name]["response_time_ms"] = response_time_ms
        
        self.checks_performed += 1
        self.last_check = datetime.now()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        if not self.component_status:
            return {"status": "unknown", "components": {}}
        
        statuses = [c["status"] for c in self.component_status.values()]
        
        # Determine overall status
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif all(s in ["healthy", "degraded"] for s in statuses):
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "components": dict(self.component_status),
            "checks_performed": self.checks_performed,
            "healthy_components": sum(1 for s in statuses if s == "healthy"),
            "degraded_components": sum(1 for s in statuses if s == "degraded"),
            "unhealthy_components": sum(1 for s in statuses if s == "unhealthy")
        }


# Initialize global instances
performance_monitor = PerformanceMonitor()
analytics = Analytics()
health_check = HealthCheck()
