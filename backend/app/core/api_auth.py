"""
API Authentication Middleware
─────────────────────────────
Static Bearer / X-IGRIS-Token auth gate (optional — disabled when
IGRIS_API_TOKEN is unset, e.g., local development).

Environment variables
─────────────────────
IGRIS_API_TOKEN
    The expected token value.  If empty/unset, all routes pass (dev mode).

IGRIS_AUTH_EXEMPT
    Comma-separated path prefixes that skip auth regardless.
    Defaults to docs, health, and public endpoints.

Security note:  token comparison uses hmac.compare_digest to prevent
timing side-channel attacks.
"""

from __future__ import annotations

import os
import hmac
import logging
from typing import Optional

from starlette.requests import Request

logger = logging.getLogger(__name__)

# ─── Default exempt paths ─────────────────────────────────────────────────────
_DEFAULT_EXEMPT: tuple[str, ...] = (
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/health",
    "/health",
    "/monitor/stats",
    "/chat",
    "/chat/stream",
    "/observability/snapshot",
    "/auth/status",        # frontend must be able to detect if auth is enabled
    "/ws",                 # WebSocket upgrade is authenticated at the WS layer
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _token_config() -> tuple[str, tuple[str, ...]]:
    """Read current token + exempt list from environment (re-evaluated each call
    so hot-reloads and tests can change env vars without restarting)."""
    tok = os.getenv("IGRIS_API_TOKEN", "").strip()
    raw = os.getenv("IGRIS_AUTH_EXEMPT", ",".join(_DEFAULT_EXEMPT))
    exempt = tuple(p.strip() for p in raw.split(",") if p.strip())
    return tok, exempt


def is_auth_enabled() -> bool:
    """Returns True if token auth is active (IGRIS_API_TOKEN is set)."""
    tok, _ = _token_config()
    return bool(tok)


def is_production_env() -> bool:
    """Return True when running in a production-like environment."""
    env = os.getenv("IGRIS_ENV") or os.getenv("ENV") or os.getenv("APP_ENV") or ""
    return env.strip().lower() in {"prod", "production"}


def validate_auth_configuration() -> None:
    """
    Enforce secure auth defaults in production.

    - Production requires IGRIS_API_TOKEN by default.
    - Can only be bypassed by explicitly setting IGRIS_ALLOW_OPEN_AUTH=true.
    """
    token, _ = _token_config()
    allow_open = os.getenv("IGRIS_ALLOW_OPEN_AUTH", "").strip().lower() in {"1", "true", "yes"}
    if is_production_env() and not token and not allow_open:
        raise RuntimeError(
            "Unsafe auth configuration: production mode requires IGRIS_API_TOKEN "
            "(or explicitly set IGRIS_ALLOW_OPEN_AUTH=true to override)."
        )


def _open_auth_allowed() -> bool:
    """
    Allow open mode only when explicitly enabled for local development.
    """
    allow_open = os.getenv("IGRIS_ALLOW_OPEN_AUTH", "").strip().lower() in {"1", "true", "yes"}
    env = (os.getenv("IGRIS_ENV") or os.getenv("ENV") or os.getenv("APP_ENV") or "").strip().lower()
    return allow_open and env in {"dev", "development", "local", "test"}


def extract_token(request: Request) -> Optional[str]:
    """
    Extract the bearer token from the request.
    Accepts:
      - Authorization: Bearer <token>
      - X-IGRIS-Token: <token>
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip() or None
    return request.headers.get("x-igris-token") or None


def path_is_exempt(path: str, exempt: tuple[str, ...]) -> bool:
    """Return True if *path* starts with any prefix in *exempt*."""
    for prefix in exempt:
        if path == prefix or path.startswith(prefix):
            return True
    return False


def verify_request(request: Request) -> bool:
    """
    Return True if the request is authorized to proceed.

    Logic:
    1. If token missing and open auth explicitly enabled for dev/test → allow.
    2. If the path is exempt → allow.
    3. Extract token from headers; accept static IGRIS_API_TOKEN OR valid JWT login token.
    """
    token, exempt = _token_config()

    path = request.url.path
    if path_is_exempt(path, exempt):
        return True

    if not token:
        supplied_nt = extract_token(request)
        if supplied_nt:
            try:
                from app.core.security import security_manager

                valid_jwt, _pl = security_manager.verify_jwt_token(supplied_nt)
                if valid_jwt:
                    return True
            except Exception:
                pass
        if _open_auth_allowed():
            return True
        logger.warning("[API AUTH] Denied %s %s: missing IGRIS_API_TOKEN and open auth disabled", request.method, path)
        return False

    supplied = extract_token(request)
    if not supplied:
        logger.warning("[API AUTH] Missing token for %s %s", request.method, path)
        return False

    # Static gate token (timing-safe)
    if hmac.compare_digest(
        supplied.encode("utf-8"),
        token.encode("utf-8"),
    ):
        return True

    # Same Bearer slot often carries JWT after /api/admin/auth/login
    try:
        from app.core.security import security_manager

        valid, _payload = security_manager.verify_jwt_token(supplied)
        if valid:
            return True
    except Exception:
        pass

    ip = request.client.host if request.client else "unknown"
    logger.warning("[API AUTH] Invalid token from %s for %s %s", ip, request.method, path)
    return False


def get_auth_status() -> dict:
    """Return human-readable auth configuration (safe to expose in /health)."""
    enabled = is_auth_enabled()
    _, exempt = _token_config()
    return {
        "auth_enabled":   enabled,
        "mode":           "token" if enabled else ("open (dev)" if _open_auth_allowed() else "locked (no token)"),
        "exempt_paths":   list(exempt),
    }


def verify_ws_token(supplied: Optional[str]) -> bool:
    """
    Validate token for WebSocket handshakes.
    Accepts token from header/query provided by caller.
    Static IGRIS_API_TOKEN or valid JWT (same as HTTP middleware).
    """
    token, _ = _token_config()
    if not supplied:
        return False
    if not token:
        try:
            from app.core.security import security_manager

            valid, _payload = security_manager.verify_jwt_token(supplied)
            if valid:
                return True
        except Exception:
            pass
        return _open_auth_allowed()
    if hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
        return True
    try:
        from app.core.security import security_manager

        valid, _payload = security_manager.verify_jwt_token(supplied)
        return bool(valid)
    except Exception:
        return False
