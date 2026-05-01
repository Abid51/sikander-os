"""
Advanced Features API Routes
Analytics, logging, caching, command suggestions
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, Any
import logging

from app.core.advanced_logging import advanced_logger, EventType
from app.core.caching_retry import request_cache, cached_request
from app.core.command_suggester import command_suggester

logger = logging.getLogger(__name__)

router = APIRouter()


# ============= ANALYTICS & MONITORING =============

@router.get("/api/analytics/dashboard")
async def get_analytics_dashboard() -> Dict[str, Any]:
    """Get comprehensive analytics dashboard"""
    try:
        analytics = advanced_logger.get_analytics()
        health = advanced_logger.get_health_score()
        performance = advanced_logger.get_performance_report()
        errors = advanced_logger.get_error_report()
        
        advanced_logger.log_event(
            EventType.API_REQUEST,
            "/api/analytics/dashboard",
            {"action": "fetch_analytics"}
        )
        
        return {
            "status": "success",
            "health_score": health,
            "analytics": analytics,
            "performance": performance,
            "errors": errors
        }
    except Exception as e:
        advanced_logger.log_error(
            "analytics_error",
            "/api/analytics/dashboard",
            str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/health")
async def get_system_health() -> Dict[str, Any]:
    """Get real-time system health status"""
    health_score = advanced_logger.get_health_score()
    
    return {
        "health_score": health_score,
        "status": "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "critical",
        "last_updated": advanced_logger.events[-1]["timestamp"] if advanced_logger.events else None
    }


@router.get("/api/analytics/performance")
async def get_performance_metrics() -> Dict[str, Any]:
    """Get detailed performance metrics"""
    return {
        "performance": advanced_logger.get_performance_report(),
        "cache_stats": request_cache.get_stats()
    }


@router.get("/api/analytics/errors")
async def get_error_analytics(
    limit: int = Query(50, ge=1, le=1000)
) -> Dict[str, Any]:
    """Get error analytics and trends"""
    return {
        "error_report": advanced_logger.get_error_report(),
        "recent_errors": advanced_logger.events[-limit:] if advanced_logger.events else []
    }


@router.post("/api/analytics/events")
async def get_recent_events(
    event_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000)
) -> Dict[str, Any]:
    """Get recent events with optional filtering"""
    events = advanced_logger.events[-limit:] if advanced_logger.events else []
    
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    
    return {
        "total_events": len(advanced_logger.events),
        "filtered_events": len(events),
        "events": events
    }


# ============= COMMAND SUGGESTIONS =============

@router.get("/api/commands/suggestions")
async def get_command_suggestions(
    partial: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20)
) -> Dict[str, Any]:
    """Get command suggestions for partial input"""
    try:
        suggestions = command_suggester.get_suggestions(partial, limit)
        
        advanced_logger.log_event(
            EventType.API_REQUEST,
            "/api/commands/suggestions",
            {"partial": partial, "suggestions_count": len(suggestions)}
        )
        
        return {
            "suggestions": suggestions,
            "count": len(suggestions)
        }
    except Exception as e:
        logger.error(f"Suggestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/commands/categories")
async def get_command_categories() -> Dict[str, Any]:
    """Get all available command categories"""
    categories = command_suggester.get_command_categories()
    
    return {
        "categories": categories,
        "total_commands": sum(len(cmds) for cmds in categories.values())
    }


@router.get("/api/commands/frequently-used")
async def get_frequently_used_commands(
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """Get most frequently used commands"""
    commands = command_suggester.get_frequently_used(limit)
    
    return {
        "commands": commands,
        "count": len(commands)
    }


@router.get("/api/commands/search")
async def search_command_history(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100)
) -> Dict[str, Any]:
    """Search command execution history"""
    results = command_suggester.search_history(query, limit)
    
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }


@router.get("/api/commands/analytics")
async def get_command_analytics() -> Dict[str, Any]:
    """Get comprehensive command analytics"""
    return command_suggester.get_analytics()


@router.get("/api/commands/quick-reference")
async def get_quick_reference() -> Dict[str, Any]:
    """Get quick reference for all commands"""
    reference = command_suggester.get_quick_reference()
    
    return {
        "reference": reference,
        "total_commands": sum(len(cmds) for cmds in reference.values())
    }


@router.post("/api/commands/record")
async def record_command_execution(
    command: str,
    success: bool,
    execution_time_ms: float,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """Record command execution for analytics"""
    command_suggester.add_to_history(command, success, execution_time_ms, category)
    
    advanced_logger.log_voice_command(command, "unknown", success, execution_time_ms)
    
    return {
        "status": "recorded",
        "command": command,
        "success": success
    }


# ============= CACHE MANAGEMENT =============

@router.get("/api/cache/stats")
async def get_cache_statistics() -> Dict[str, Any]:
    """Get caching system statistics"""
    return {
        "cache_stats": request_cache.get_stats(),
        "total_entries": len(request_cache.cache)
    }


@router.post("/api/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """Clear all cache"""
    request_cache.clear()
    
    advanced_logger.log_event(
        EventType.SYSTEM,
        "/api/cache/clear",
        {"action": "cache_cleared"}
    )
    
    return {
        "status": "cleared",
        "message": "All cache entries have been cleared"
    }


# ============= SYSTEM STATUS =============

@router.get("/api/system/status/full")
async def get_full_system_status() -> Dict[str, Any]:
    """Get comprehensive system status"""
    return {
        "health": {
            "score": advanced_logger.get_health_score(),
            "status": "operational"
        },
        "analytics": advanced_logger.get_analytics(),
        "performance": advanced_logger.get_performance_report(),
        "cache": request_cache.get_stats(),
        "commands": command_suggester.get_analytics()
    }
