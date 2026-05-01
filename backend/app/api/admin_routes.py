"""
Advanced Administration & Monitoring API Routes
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from typing import Dict, Any, Optional, List
import logging

from app.core.database import db
from app.core.security import (
    security_manager, permission_manager, audit_logger, totp_manager
)
from app.core.monitoring import performance_monitor, analytics, health_check
from app.core.task_orchestrator import task_orchestrator
from app.core.plugin_loader import get_plugin_loader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

# ── Dependency: require a valid access token ─────────────────────────────────
async def require_token(request: Request) -> Dict:
    """Validate JWT access token and return the payload."""
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    valid, payload = security_manager.verify_jwt_token(token)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def verify_admin_token(request: Request) -> int:
    """Dependency: token must belong to a user with the 'admin' role."""
    payload = await require_token(request)
    role    = payload.get("role", "user")
    if not permission_manager.has_permission(role, "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload.get("user_id")


# ==================== Authentication Routes ====================

@router.post("/auth/register")
async def register_user(data: Dict[str, Any]):
    """Register a new user account."""
    username = data.get("username", "").strip()
    email    = data.get("email", "").strip()
    password = data.get("password", "")

    if not all([username, email, password]):
        raise HTTPException(status_code=400, detail="username, email, and password are required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    password_hash = security_manager.hash_password(password)
    api_key       = security_manager.generate_api_key(0)   # placeholder; real ID assigned by DB

    result = db.create_user(username, email, password_hash, api_key)
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])

    # Regenerate API key with the real user_id
    real_api_key = security_manager.generate_api_key(result["id"])
    db.update_user_api_key(result["id"], real_api_key)

    audit_logger.log_event(
        "user_registered", result["id"],
        {"username": username, "email": email},
        severity="INFO",
    )
    return {"status": "created", "user_id": result["id"], "api_key": real_api_key}


@router.post("/auth/login")
async def login(request: Request, data: Dict[str, Any]):
    """
    Authenticate with username + password.
    Returns a short-lived access token (1 h) and a long-lived refresh token (30 d).
    """
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ip       = request.client.host if request.client else "unknown"

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")

    # Rate-limit by IP
    allowed, limit_info = security_manager.check_rate_limit(ip)
    if not allowed:
        raise HTTPException(status_code=429, detail=limit_info.get("reason", "Rate limit exceeded"))

    # Lookup user
    user = db.get_user_by_username(username)
    if not user:
        # Use constant-time dummy work to prevent user enumeration timing
        security_manager.hash_password("dummy-work-to-prevent-timing")
        audit_logger.log_event("login_failed", None,
                               {"username": username, "reason": "user_not_found"},
                               ip_address=ip, severity="WARNING")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    stored_hash = user.get("password_hash", "")
    if not security_manager.verify_password(password, stored_hash):
        audit_logger.log_event("login_failed", user["id"],
                               {"username": username, "reason": "wrong_password"},
                               ip_address=ip, severity="WARNING")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role         = user.get("role", "user")
    access_token = security_manager.generate_jwt_token(
        user["id"], username, expires_in_hours=1,
        extra_claims={"role": role, "email": user.get("email", "")},
    )
    refresh_token = security_manager.generate_refresh_token(user["id"], username)

    audit_logger.log_event("login_success", user["id"], {"username": username}, ip_address=ip)
    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "Bearer",
        "expires_in":    3600,
        "user_id":       user["id"],
        "role":          role,
    }


@router.post("/auth/refresh")
async def refresh_token(data: Dict[str, Any]):
    """
    Exchange a refresh token for a new access + refresh token pair.
    The old refresh token is invalidated (rotation).
    """
    rt = data.get("refresh_token", "").strip()
    if not rt:
        raise HTTPException(status_code=400, detail="refresh_token is required")
    ok, result = security_manager.use_refresh_token(rt)
    if not ok:
        raise HTTPException(status_code=401, detail=result.get("error", "Invalid refresh token"))
    return result


@router.post("/auth/logout")
async def logout(data: Dict[str, Any], payload: Dict = Depends(require_token)):
    """Revoke all refresh tokens for the authenticated user (logout-all)."""
    user_id  = payload.get("user_id")
    revoked  = security_manager.revoke_all_refresh_tokens(user_id)
    audit_logger.log_event("logout", user_id, {"refresh_tokens_revoked": revoked})
    return {"status": "logged_out", "refresh_tokens_revoked": revoked}


@router.post("/auth/verify-token")
async def verify_token(data: Dict[str, Any]):
    """Verify whether a JWT access token is valid."""
    token = data.get("token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")
    valid, token_payload = security_manager.verify_jwt_token(token)
    return {"valid": valid, "payload": token_payload if valid else None}


@router.post("/auth/change-password")
async def change_password(data: Dict[str, Any], payload: Dict = Depends(require_token)):
    """Change the authenticated user's password."""
    current_pw = data.get("current_password", "")
    new_pw     = data.get("new_password", "")
    if not current_pw or not new_pw:
        raise HTTPException(status_code=400, detail="current_password and new_password are required")
    if len(new_pw) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user_id = payload.get("user_id")
    user    = db.get_user_by_id(user_id)
    if not user or not security_manager.verify_password(current_pw, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    new_hash = security_manager.hash_password(new_pw)
    db.update_user_password(user_id, new_hash)
    # Revoke all refresh tokens — user must re-login
    security_manager.revoke_all_refresh_tokens(user_id)
    audit_logger.log_event("password_changed", user_id, {}, severity="WARNING")
    return {"status": "password_changed", "note": "All sessions have been invalidated. Please log in again."}


# ── TOTP / 2FA ────────────────────────────────────────────────────────────────

@router.post("/auth/2fa/provision")
async def provision_2fa(payload: Dict = Depends(require_token)):
    """Generate a TOTP secret and provisioning QR URI for the authenticated user."""
    username = payload.get("username", f"user_{payload.get('user_id')}")
    result   = totp_manager.provision(username)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@router.post("/auth/2fa/verify")
async def verify_2fa(data: Dict[str, Any], payload: Dict = Depends(require_token)):
    """Verify a TOTP code for the authenticated user."""
    otp      = data.get("otp", "").strip()
    username = payload.get("username", "")
    if not otp:
        raise HTTPException(status_code=400, detail="otp is required")
    valid = totp_manager.verify(username, otp) or totp_manager.verify_no_pyotp(username, otp)
    if not valid:
        audit_logger.log_event("2fa_failed", payload.get("user_id"), {"username": username}, severity="WARNING")
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    audit_logger.log_event("2fa_success", payload.get("user_id"), {"username": username})
    return {"status": "verified", "2fa": "passed"}


# ==================== Analytics & Monitoring ====================

@router.get("/analytics/overview")
async def get_analytics_overview(user_id: int = Depends(verify_admin_token)):
    """Get analytics overview"""
    return {
        "user_engagement": analytics.get_user_engagement(),
        "top_commands": analytics.get_top_commands(10),
        "trends_24h": analytics.get_trends(24),
        "error_stats": performance_monitor.get_error_stats()
    }


@router.get("/analytics/user/{user_id}")
async def get_user_analytics(user_id: int, days: int = Query(7, ge=1, le=90),
                           admin_id: int = Depends(verify_admin_token)):
    """Get individual user analytics"""
    return analytics.get_user_activity(user_id, days)


@router.get("/analytics/commands/top")
async def get_top_commands(limit: int = Query(10, ge=1, le=100),
                          admin_id: int = Depends(verify_admin_token)):
    """Get top used commands"""
    return {
        "top_commands": analytics.get_top_commands(limit)
    }


@router.get("/monitoring/health")
async def get_system_health(admin_id: int = Depends(verify_admin_token)):
    """Get system health status"""
    return health_check.get_health_status()


@router.get("/monitoring/performance")
async def get_performance_metrics(admin_id: int = Depends(verify_admin_token)):
    """Get performance metrics"""
    return {
        "api_stats": performance_monitor.get_api_stats(),
        "error_stats": performance_monitor.get_error_stats(),
        "uptime": performance_monitor.get_uptime()
    }


@router.get("/monitoring/metrics/{metric_name}")
async def get_metric_stats(metric_name: str, admin_id: int = Depends(verify_admin_token)):
    """Get specific metric statistics"""
    return performance_monitor.get_metric_stats(metric_name)


# ==================== Task Orchestration ====================

@router.get("/tasks/queue-stats")
async def get_queue_stats(admin_id: int = Depends(verify_admin_token)):
    """Get task queue statistics"""
    return task_orchestrator.get_queue_stats()


@router.get("/tasks/recent")
async def get_recent_tasks(limit: int = Query(20, ge=1, le=100),
                          admin_id: int = Depends(verify_admin_token)):
    """Get recent completed tasks"""
    return {
        "tasks": task_orchestrator.get_recent_tasks(limit)
    }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, admin_id: int = Depends(verify_admin_token)):
    """Get task status"""
    status = task_orchestrator.get_task_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return status


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, admin_id: int = Depends(verify_admin_token)):
    """Cancel pending task"""
    cancelled = await task_orchestrator.cancel_task(task_id)
    
    if not cancelled:
        raise HTTPException(status_code=404, detail="Task not found or already running")
    
    audit_logger.log_event("task_cancelled", admin_id, {"task_id": task_id})
    
    return {"status": "cancelled", "task_id": task_id}


# ==================== Plugin Management ====================

@router.post("/plugins/load")
async def load_plugin(data: Dict[str, Any], admin_id: int = Depends(verify_admin_token)):
    """Load all plugins from plugins directory"""
    loader = get_plugin_loader()
    results = loader.load_all()
    loader.fire_startup()
    
    audit_logger.log_event("plugins_loaded", admin_id, {"results": results})
    
    return {"status": "loaded", "results": results}


@router.post("/plugins/unload")
async def unload_plugin(data: Dict[str, Any], admin_id: int = Depends(verify_admin_token)):
    """Unload plugin"""
    plugin_name = data.get("plugin_name")
    
    if not plugin_name:
        raise HTTPException(status_code=400, detail="Missing plugin_name")
    
    loader = get_plugin_loader()
    success = loader.unload_plugin(plugin_name)
    
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    audit_logger.log_event("plugin_unloaded", admin_id, {"plugin": plugin_name})
    
    return {"status": "unloaded", "plugin": plugin_name}


@router.get("/plugins/list")
async def list_plugins(admin_id: int = Depends(verify_admin_token)):
    """List all plugins"""
    loader = get_plugin_loader()
    return {
        "plugins": loader.list_plugins(),
        "stats": loader.get_stats()
    }


@router.get("/plugins/marketplace/search")
async def search_plugins(query: str = Query(..., min_length=1),
                        admin_id: int = Depends(verify_admin_token)):
    """Search loaded plugins by name"""
    loader = get_plugin_loader()
    all_plugins = loader.list_plugins()
    results = [p for p in all_plugins if query.lower() in p.get("name", "").lower()]
    return {"query": query, "results": results}


@router.get("/plugins/marketplace/recommended")
async def get_recommended_plugins(admin_id: int = Depends(verify_admin_token)):
    """Get plugin stats"""
    loader = get_plugin_loader()
    return loader.get_stats()


# ==================== Security & Audit ====================

@router.get("/security/audit-log")
async def get_audit_log(limit: int = Query(100, ge=1, le=1000),
                       admin_id: int = Depends(verify_admin_token)):
    """Get audit log"""
    return {
        "events": audit_logger.get_recent_events(limit)
    }


@router.get("/security/rate-limits")
async def get_rate_limits(admin_id: int = Depends(verify_admin_token)):
    """Get rate limit configuration"""
    return {
        "max_requests_per_minute": security_manager.max_requests_per_minute,
        "max_requests_per_hour": security_manager.max_requests_per_hour,
        "blocked_ips_count": len(security_manager.blocked_ips)
    }


@router.post("/security/unblock-ip")
async def unblock_ip(data: Dict[str, Any], admin_id: int = Depends(verify_admin_token)):
    """Unblock an IP address"""
    ip_address = data.get("ip_address")
    
    if not ip_address:
        raise HTTPException(status_code=400, detail="Missing ip_address")
    
    success = security_manager.unblock_ip(ip_address)
    
    if not success:
        raise HTTPException(status_code=404, detail="IP not in blocked list")
    
    audit_logger.log_event("ip_unblocked", admin_id, {"ip": ip_address}, severity="WARNING")
    
    return {"status": "unblocked", "ip": ip_address}


@router.get("/security/permissions")
async def get_permissions(admin_id: int = Depends(verify_admin_token)):
    """Get available permissions by role"""
    return {
        "roles": permission_manager.ROLES
    }


# ==================== Database Stats ====================

@router.get("/database/stats")
async def get_db_stats(admin_id: int = Depends(verify_admin_token)):
    """Get database statistics"""
    return db.get_stats()


# ==================== System Configuration ====================

@router.get("/system/config")
async def get_system_config(admin_id: int = Depends(verify_admin_token)):
    """Get system configuration"""
    return {
        "security_headers": security_manager.get_security_headers(),
        "rate_limiting": {
            "per_minute": security_manager.max_requests_per_minute,
            "per_hour": security_manager.max_requests_per_hour
        },
        "orchestrator": task_orchestrator.get_queue_stats(),
        "plugins_loaded": get_plugin_loader().get_stats().get("plugins_loaded", 0)
    }


@router.post("/system/config/update")
async def update_system_config(data: Dict[str, Any],
                              admin_id: int = Depends(verify_admin_token)):
    """Update system configuration"""
    # Update rate limits
    if "rate_limit_per_minute" in data:
        security_manager.max_requests_per_minute = data["rate_limit_per_minute"]
    
    if "rate_limit_per_hour" in data:
        security_manager.max_requests_per_hour = data["rate_limit_per_hour"]
    
    audit_logger.log_event("config_updated", admin_id, data)
    
    return {"status": "updated"}
