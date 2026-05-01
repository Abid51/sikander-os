"""
conftest.py — Shared pytest fixtures for Sikander-OS backend tests.
"""
import os
import sys
import pytest

# ─── ensure project root is on PYTHONPATH ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ─── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_db(tmp_path_factory):
    """Isolated SQLite database for the entire test session."""
    from app.core.database import DatabaseManager
    db_path = tmp_path_factory.mktemp("db") / "test_session.db"
    return DatabaseManager(db_path=str(db_path))


@pytest.fixture(scope="session")
def security_manager():
    """Shared SecurityManager instance (session-scoped for performance)."""
    from app.core.security import SecurityManager
    return SecurityManager(rate_limit_per_minute=100)


@pytest.fixture(scope="session")
def audit_logger(tmp_path_factory):
    """Shared AuditLogger writing to a tmp file."""
    from app.core.security import AuditLogger
    log_path = tmp_path_factory.mktemp("logs") / "test_audit.json"
    return AuditLogger(log_file=str(log_path))


@pytest.fixture(scope="session")
def plugin_loader(tmp_path_factory):
    """PluginLoader with an isolated plugins directory."""
    from app.core.plugin_loader import PluginLoader
    plugins_dir = tmp_path_factory.mktemp("plugins")
    return PluginLoader(plugins_dir=str(plugins_dir))


@pytest.fixture()
def fresh_security_manager():
    """Per-test SecurityManager (fresh state, no shared rate-limit counters)."""
    from app.core.security import SecurityManager
    return SecurityManager(rate_limit_per_minute=5)


@pytest.fixture()
def fastapi_admin_client():
    """FastAPI TestClient pre-loaded with admin_routes."""
    pytest.importorskip("fastapi", reason="FastAPI not installed")
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.admin_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def fastapi_advanced_client():
    """FastAPI TestClient pre-loaded with advanced_routes."""
    pytest.importorskip("fastapi", reason="FastAPI not installed")
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.advanced_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """
    Remove IGRIS_API_TOKEN from environment for every test by default,
    so auth tests start from a clean slate.
    Individual tests that need a token should set it via monkeypatch.
    """
    monkeypatch.delenv("IGRIS_API_TOKEN", raising=False)
    monkeypatch.setenv("IGRIS_ENV", "test")
    monkeypatch.setenv("IGRIS_ALLOW_OPEN_AUTH", "true")
