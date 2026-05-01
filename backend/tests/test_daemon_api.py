"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SIKANDER-OS — DAEMON & API INTEGRATION TEST SUITE
  Covers: daemon_master.py · advanced_routes.py · admin_routes.py
          DaemonMaster orchestrator · WebSocket hub
  Run: python -m pytest tests/ -v --tb=short
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run(coro):
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════════════
# 1. BASE DAEMON
# ══════════════════════════════════════════════════════════════════════

class TestBaseDaemon:
    """Tests for BaseDaemon lifecycle."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.daemon_master import BaseDaemon, DaemonStatus
        self.BaseDaemon   = BaseDaemon
        self.DaemonStatus = DaemonStatus

    def test_initial_status_is_stopped(self):
        d = self.BaseDaemon("Test", "test_01", "A test daemon")
        assert d.status == self.DaemonStatus.STOPPED

    def test_start_changes_status(self):
        d = self.BaseDaemon("Test", "test_02", "A test daemon")
        run(d.start())
        assert d.status == self.DaemonStatus.RUNNING

    def test_stop_changes_status(self):
        d = self.BaseDaemon("Test", "test_03", "A test daemon")
        run(d.start())
        run(d.stop())
        assert d.status == self.DaemonStatus.STOPPED

    def test_double_start_returns_already_running(self):
        d = self.BaseDaemon("Test", "test_04", "desc")
        run(d.start())
        result = run(d.start())
        assert result["status"] == "already_running"

    def test_get_status_structure(self):
        d = self.BaseDaemon("MyDaemon", "my_d", "desc")
        s = d.get_status()
        assert "daemon_id" in s
        assert "name"      in s
        assert "status"    in s
        assert "is_running" in s


# ══════════════════════════════════════════════════════════════════════
# 2. BLOOD WARD DAEMON
# ══════════════════════════════════════════════════════════════════════

class TestBloodWardDaemon:

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.daemon_master import BloodWardDaemon
        self.bw = BloodWardDaemon()

    def test_initialization(self):
        assert self.bw.name == "Blood Ward"
        assert self.bw.daemon_id == "blood_ward_01"

    def test_add_blocked_ip(self):
        result = run(self.bw.add_blocked_ip("1.2.3.4"))
        assert result["status"] == "blocked"
        assert "1.2.3.4" in self.bw.blocked_ips

    def test_get_threats_empty(self):
        threats = self.bw.get_threats()
        assert isinstance(threats, list)

    def test_security_rules_loaded_on_init(self):
        run(self.bw._initialize())
        assert len(self.bw.security_rules) > 0


# ══════════════════════════════════════════════════════════════════════
# 3. DOMINION DAEMON
# ══════════════════════════════════════════════════════════════════════

class TestDominionDaemon:

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.daemon_master import DominionDaemon
        self.dom = DominionDaemon()

    def test_gather_system_info(self):
        self.dom._gather_system_info()
        assert "cpu_count" in self.dom.system_info
        assert "memory_total" in self.dom.system_info

    def test_queue_command(self):
        result = self.dom.queue_command({"type": "open_app", "app": "notepad"})
        assert result["status"] == "queued"
        assert len(self.dom.commands_queue) == 1

    def test_run_safe_system_command(self):
        result = run(self.dom._run_system_command("echo sikander_os_test"))
        assert result["status"] == "completed"
        assert "sikander_os_test" in result.get("stdout", "")

    def test_kill_nonexistent_pid(self):
        result = run(self.dom._kill_process(99999999))
        assert result["status"] == "error"

    def test_close_nonexistent_app(self):
        result = run(self.dom._close_application("__nonexistent_app__"))
        assert result["status"] == "not_found"


# ══════════════════════════════════════════════════════════════════════
# 4. SHADOW FORGE DAEMON
# ══════════════════════════════════════════════════════════════════════

class TestShadowForgeDaemon:

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.daemon_master import ShadowForgeDaemon
        self.sf = ShadowForgeDaemon()
        run(self.sf._initialize())

    def test_generate_python_function(self):
        code = run(self.sf.generate_code("python", "function", {
            "name": "my_func",
            "params": "x, y",
            "docstring": "Add two numbers",
            "body": "return x + y"
        }))
        assert "def my_func" in code
        assert "x + y" in code

    def test_analyze_code_finds_todos(self):
        code = "x = 1\n# TODO: fix this\ny = 2\n"
        result = run(self.sf.analyze_code(code, "python"))
        assert result["lines"] == 3
        assert "TODO" in str(result.get("issues", []))

    def test_analyze_large_code_suggestion(self):
        code = "\n".join([f"x{i} = {i}" for i in range(110)])
        result = run(self.sf.analyze_code(code, "python"))
        assert any("smaller" in s.lower() or "split" in s.lower()
                   for s in result.get("suggestions", []))

    def test_optimize_code_strips_trailing(self):
        code = "x = 1   \ny = 2   \n"
        result = run(self.sf.optimize_code(code, "python"))
        assert "optimized" in result
        assert "   " not in result["optimized"]

    def test_unknown_template(self):
        code = run(self.sf.generate_code("cobol", "subroutine", {}))
        assert "not found" in code.lower() or code.startswith("#")


# ══════════════════════════════════════════════════════════════════════
# 5. PHANTOM RECON DAEMON
# ══════════════════════════════════════════════════════════════════════

class TestPhantomReconDaemon:

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.daemon_master import PhantomReconDaemon
        self.pr = PhantomReconDaemon()

    def test_scan_closed_port(self):
        result = run(self.pr.scan_port("127.0.0.1", 19999))
        assert "is_open" in result
        assert result["host"] == "127.0.0.1"

    def test_network_scan_returns_dict(self):
        result = run(self.pr.network_scan("192.168.1.0/24"))
        assert "subnet" in result
        assert "status" in result

    def test_get_network_info_structure(self):
        info = self.pr.get_network_info()
        assert "stats"   in info
        assert "devices" in info


# ══════════════════════════════════════════════════════════════════════
# 6. ADVANCED API ROUTES — TestClient
# ══════════════════════════════════════════════════════════════════════

class TestAdvancedRoutesSecurity:
    """Integration tests for /advanced/security/* endpoints."""

    @pytest.fixture(autouse=True)
    def client(self):
        try:
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from app.api.advanced_routes import router
            app = FastAPI()
            app.include_router(router)
            self.client = TestClient(app, raise_server_exceptions=False)
        except Exception as e:
            pytest.skip(f"FastAPI TestClient unavailable: {e}")

    def test_security_status_endpoint(self):
        r = self.client.get("/api/advanced/security/status")
        assert r.status_code == 200
        body = r.json()
        assert "system_status" in body or "security_level" in body

    def test_encrypt_endpoint(self):
        r = self.client.post("/api/advanced/security/encrypt",
                             params={"data": "hello igris", "key_id": "test_enc_key"})
        assert r.status_code == 200
        body = r.json()
        assert "encrypted" in body

    def test_decrypt_endpoint_roundtrip(self):
        # Encrypt first
        r1 = self.client.post("/api/advanced/security/encrypt",
                              params={"data": "roundtrip_test", "key_id": "rt_key"})
        assert r1.status_code == 200
        ct = r1.json()["encrypted"]
        # Now decrypt
        r2 = self.client.post("/api/advanced/security/decrypt",
                              params={"encrypted_data": ct, "key_id": "rt_key"})
        assert r2.status_code == 200
        assert r2.json()["decrypted"] == "roundtrip_test"

    def test_dashboard_metrics_endpoint(self):
        r = self.client.get("/api/advanced/dashboard/metrics")
        assert r.status_code == 200
        body = r.json()
        assert "cpu_usage" in body
        assert "memory_usage" in body

    def test_dashboard_overview_endpoint(self):
        r = self.client.get("/api/advanced/dashboard/overview")
        assert r.status_code == 200
        body = r.json()
        assert "timestamp" in body

    def test_password_strength_endpoint(self):
        r = self.client.post("/api/advanced/cybersecurity/password-strength",
                             params={"password": "StrongP@ssw0rd!"})
        assert r.status_code == 200

    def test_scan_ports_endpoint(self):
        r = self.client.post("/api/advanced/cybersecurity/scan-ports",
                             params={"target": "127.0.0.1"})
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════
# 7. DATABASE — general ops
# ══════════════════════════════════════════════════════════════════════

class TestDatabaseOps:
    """Tests for non-user database operations."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from app.core.database import DatabaseManager
        self.db = DatabaseManager(db_path=str(tmp_path / "test_ops.db"))

    def test_cache_set_and_get(self):
        self.db.cache_set("my_key", "my_value", ttl=3600)
        val = self.db.cache_get("my_key")
        assert val == "my_value"

    def test_cache_miss_returns_none(self):
        assert self.db.cache_get("nonexistent_cache_key_xyz") is None

    def test_log_system_event(self):
        eid = self.db.log_system_event(
            "TEST_EVENT", "test_module", {"key": "val"}, severity="INFO"
        )
        assert isinstance(eid, int)
        assert eid > 0

    def test_log_metric(self):
        mid = self.db.log_metric("cpu_usage", 42.5, unit="%", tags={"host": "local"})
        assert isinstance(mid, int)

    def test_create_and_update_task(self):
        uid = self.db.create_user("task_user", "t@t.com", "h", "k")["id"]
        tid = self.db.create_task(uid, "analysis", "run_analysis", {"param": 1}, priority=3)
        assert isinstance(tid, int)
        updated = self.db.update_task(tid, "completed", result="done")
        assert updated is True

    def test_get_stats_returns_counts(self):
        stats = self.db.get_stats()
        assert "users_count" in stats
        assert "tasks_count" in stats

    def test_install_and_get_plugins(self):
        ok = self.db.install_plugin(
            "my_plugin", "1.0.0", "Me", "A plugin", {"key": "val"}
        )
        assert ok is True
        plugins = self.db.get_plugins(enabled_only=True)
        assert any(p["name"] == "my_plugin" for p in plugins)


# ══════════════════════════════════════════════════════════════════════
# RUN DIRECTLY
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
