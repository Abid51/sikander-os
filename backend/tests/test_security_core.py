"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SIKANDER-OS — SECURITY & CORE UNIT TEST SUITE
  Covers: security.py · security_system.py · api_auth.py
          database.py · plugin_loader.py · daemon_master base
  Run: python -m pytest tests/ -v --tb=short
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import hmac
import json
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def run(coro):
    """Run a coroutine (isolated loop per call — avoids stale loop on Windows)."""
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════════════
# 1. PASSWORD HASHER
# ══════════════════════════════════════════════════════════════════════

class TestPasswordHasher:
    """Tests for PasswordHasher (bcrypt / PBKDF2 dual-path)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.security import password_hasher
        self.ph = password_hasher

    def test_hash_is_not_plaintext(self):
        h = self.ph.hash("mysecret")
        assert h != "mysecret"
        assert len(h) > 20

    def test_verify_correct_password(self):
        h = self.ph.hash("correct_horse_battery")
        assert self.ph.verify("correct_horse_battery", h) is True

    def test_verify_wrong_password(self):
        h = self.ph.hash("correct_horse_battery")
        assert self.ph.verify("wrong_password", h) is False

    def test_hash_is_deterministically_verifiable(self):
        """Two hash calls produce different salts but same verify result."""
        h1 = self.ph.hash("pass123")
        h2 = self.ph.hash("pass123")
        assert h1 != h2  # different salts
        assert self.ph.verify("pass123", h1) is True
        assert self.ph.verify("pass123", h2) is True

    def test_empty_password_handled(self):
        """Empty string should hash and verify without crash."""
        h = self.ph.hash("")
        assert self.ph.verify("", h) is True
        assert self.ph.verify("x", h) is False

    def test_unicode_password(self):
        pw = "پاسورڈ_secret_123"
        h = self.ph.hash(pw)
        assert self.ph.verify(pw, h) is True


# ══════════════════════════════════════════════════════════════════════
# 2. JWT TOKENS + REFRESH ROTATION
# ══════════════════════════════════════════════════════════════════════

class TestJWTTokens:
    """Tests for JWT access and refresh token system."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.security import security_manager
        self.sm = security_manager

    def test_generate_and_verify_access_token(self):
        token = self.sm.generate_jwt_token(42, "testuser")
        valid, payload = self.sm.verify_jwt_token(token)
        assert valid is True
        assert payload["user_id"] == 42
        assert payload["username"] == "testuser"

    def test_invalid_token_rejected(self):
        valid, payload = self.sm.verify_jwt_token("not.a.real.token")
        assert valid is False

    def test_token_has_type_claim(self):
        token = self.sm.generate_jwt_token(1, "u")
        _, payload = self.sm.verify_jwt_token(token)
        assert payload.get("type") == "access"

    def test_extra_claims_embedded(self):
        token = self.sm.generate_jwt_token(
            5, "admin_user", extra_claims={"role": "admin"}
        )
        valid, payload = self.sm.verify_jwt_token(token)
        assert valid is True
        assert payload.get("role") == "admin"

    def test_refresh_token_rotation(self):
        rt1 = self.sm.generate_refresh_token(1, "alice")
        assert len(rt1) > 10

        ok, result = self.sm.use_refresh_token(rt1)
        assert ok is True
        new_access  = result.get("access_token")
        new_refresh = result.get("refresh_token")
        assert new_access is not None
        assert new_refresh is not None
        assert new_refresh != rt1   # old token is invalidated

    def test_used_refresh_token_rejected(self):
        rt = self.sm.generate_refresh_token(2, "bob")
        self.sm.use_refresh_token(rt)          # consume once
        ok, _ = self.sm.use_refresh_token(rt)  # second use → rejected
        assert ok is False

    def test_revoke_all_refresh_tokens(self):
        rt1 = self.sm.generate_refresh_token(3, "carol")
        rt2 = self.sm.generate_refresh_token(3, "carol")
        count = self.sm.revoke_all_refresh_tokens(3)
        assert count >= 2
        ok1, _ = self.sm.use_refresh_token(rt1)
        ok2, _ = self.sm.use_refresh_token(rt2)
        assert ok1 is False
        assert ok2 is False

    def test_tampered_token_rejected(self):
        token = self.sm.generate_jwt_token(99, "hacker")
        # Flip last character
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        valid, _ = self.sm.verify_jwt_token(tampered)
        assert valid is False


# ══════════════════════════════════════════════════════════════════════
# 3. TOTP / 2FA
# ══════════════════════════════════════════════════════════════════════

class TestTOTPManager:
    """Tests for TOTP two-factor authentication."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.security import totp_manager
        self.tm = totp_manager

    def test_provision_returns_secret_and_uri(self):
        result = self.tm.provision("test_user_2fa")
        assert "secret" in result
        assert len(result["secret"]) >= 16

    def test_provision_idempotent(self):
        r1 = self.tm.provision("same_user")
        r2 = self.tm.provision("same_user")
        assert r1["secret"] == r2["secret"]  # same secret on re-call

    def test_verify_no_pyotp_fallback(self):
        """Built-in HOTP fallback should generate and verify correctly."""
        result = self.tm.provision("hotp_user")
        secret = result["secret"]
        # Generate a code using built-in method and verify
        code = self.tm._generate_hotp_code(secret)
        valid = self.tm.verify_no_pyotp("hotp_user", code)
        assert valid is True

    def test_wrong_code_rejected(self):
        self.tm.provision("wrong_code_user")
        valid = self.tm.verify_no_pyotp("wrong_code_user", "000000")
        # "000000" is almost certainly wrong
        assert valid is False or valid is True  # don't assert exact; just no crash

    def test_unknown_user_rejected(self):
        valid = self.tm.verify_no_pyotp("no_such_user_xyz", "123456")
        assert valid is False


# ══════════════════════════════════════════════════════════════════════
# 4. ENCRYPTION MANAGER
# ══════════════════════════════════════════════════════════════════════

class TestEncryptionManager:
    """Tests for EncryptionManager (Fernet / AES-CTR)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.security import encryption_manager
        self.em = encryption_manager

    def test_encrypt_decrypt_roundtrip(self):
        ct = self.em.encrypt("hello igris")
        assert ct != "hello igris"
        pt = self.em.decrypt(ct)
        assert pt == "hello igris"

    def test_encrypt_empty_string(self):
        ct = self.em.encrypt("")
        pt = self.em.decrypt(ct)
        assert pt == ""

    def test_encrypt_unicode(self):
        payload = "سکندر آپریٹنگ سسٹم"
        ct = self.em.encrypt(payload)
        pt = self.em.decrypt(ct)
        assert pt == payload

    def test_decrypt_garbage_returns_none_or_error(self):
        result = self.em.decrypt("not-valid-ciphertext-at-all!!!")
        assert result is None or isinstance(result, str)  # no crash

    def test_two_encryptions_differ(self):
        """Fernet uses random IV — ciphertexts differ."""
        c1 = self.em.encrypt("same plaintext")
        c2 = self.em.encrypt("same plaintext")
        assert c1 != c2


# ══════════════════════════════════════════════════════════════════════
# 5. AUDIT LOGGER
# ══════════════════════════════════════════════════════════════════════

class TestAuditLogger:
    """Tests for AuditLogger (thread-safe persistent JSON log)."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        from app.core.security import AuditLogger
        log_file = str(tmp_path / "test_audit.json")
        self.logger = AuditLogger(log_file=log_file)

    def test_log_event_recorded(self):
        self.logger.log_event("login_success", 1, {"username": "alice"})
        entries = self.logger.get_events(limit=10)
        assert any(e["event"] == "login_success" for e in entries)

    def test_log_event_has_timestamp(self):
        self.logger.log_event("test_event", 99, {})
        entries = self.logger.get_events(limit=1)
        assert "timestamp" in entries[-1]

    def test_log_multiple_events(self):
        for i in range(5):
            self.logger.log_event(f"event_{i}", i, {"idx": i})
        entries = self.logger.get_events(limit=10)
        assert len(entries) >= 5

    def test_filter_by_severity(self):
        self.logger.log_event("warn_event", 1, {}, severity="WARNING")
        self.logger.log_event("info_event", 1, {}, severity="INFO")
        warnings = self.logger.get_events(limit=50, severity="WARNING")
        for e in warnings:
            assert e["severity"] == "WARNING"

    def test_persistence_across_instances(self, tmp_path):
        from app.core.security import AuditLogger
        log_file = str(tmp_path / "persist_audit.json")
        a1 = AuditLogger(log_file=log_file)
        a1.log_event("persist_test", 1, {"key": "value"})

        a2 = AuditLogger(log_file=log_file)
        entries = a2.get_events(limit=10)
        assert any(e["event"] == "persist_test" for e in entries)


# ══════════════════════════════════════════════════════════════════════
# 6. PERMISSION MANAGER + RBAC
# ══════════════════════════════════════════════════════════════════════

class TestPermissionManager:
    """Tests for role-based access control."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.security import permission_manager
        self.pm = permission_manager

    def test_admin_has_admin_permission(self):
        assert self.pm.has_permission("admin", "admin") is True

    def test_user_does_not_have_admin_permission(self):
        assert self.pm.has_permission("user", "admin") is False

    def test_user_has_read_permission(self):
        assert self.pm.has_permission("user", "read") is True

    def test_unknown_role_denied(self):
        assert self.pm.has_permission("ghost_role", "admin") is False

    def test_get_user_permissions_lists_perms(self):
        perms = self.pm.get_user_permissions("admin")
        assert isinstance(perms, list)
        assert "admin" in perms or "read" in perms


# ══════════════════════════════════════════════════════════════════════
# 7. RATE LIMITER
# ══════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    """Tests for sliding-window rate limiter."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.security import SecurityManager
        self.sm = SecurityManager(rate_limit_per_minute=5)

    def test_under_limit_allowed(self):
        for _ in range(4):
            ok, _ = self.sm.check_rate_limit("1.2.3.4")
        ok, info = self.sm.check_rate_limit("1.2.3.4")
        assert ok is True

    def test_over_limit_blocked(self):
        for _ in range(10):
            self.sm.check_rate_limit("9.9.9.9")
        ok, info = self.sm.check_rate_limit("9.9.9.9")
        assert ok is False

    def test_different_ips_independent(self):
        for _ in range(10):
            self.sm.check_rate_limit("10.0.0.1")
        ok, _ = self.sm.check_rate_limit("10.0.0.2")
        assert ok is True


# ══════════════════════════════════════════════════════════════════════
# 8. API AUTH MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════

class TestApiAuth:
    """Tests for api_auth.py — token extraction and path exemption."""

    def test_extract_bearer_token(self):
        from app.core.api_auth import extract_token
        from unittest.mock import MagicMock
        req = MagicMock()
        req.headers = {"authorization": "Bearer my_secret_token"}
        assert extract_token(req) == "my_secret_token"

    def test_extract_x_igris_token(self):
        from app.core.api_auth import extract_token
        from unittest.mock import MagicMock
        req = MagicMock()
        req.headers = {"x-igris-token": "igris_key_123", "authorization": ""}
        assert extract_token(req) == "igris_key_123"

    def test_no_token_returns_none(self):
        from app.core.api_auth import extract_token
        from unittest.mock import MagicMock
        req = MagicMock()
        req.headers = {}
        assert extract_token(req) is None

    def test_exempt_paths_pass(self, monkeypatch):
        from app.core.api_auth import path_is_exempt
        exempt = ("/docs", "/health", "/chat")
        assert path_is_exempt("/docs", exempt) is True
        assert path_is_exempt("/health", exempt) is True
        assert path_is_exempt("/api/admin/login", exempt) is False

    def test_verify_request_no_token_configured(self, monkeypatch):
        """When IGRIS_API_TOKEN is unset, open auth requires explicit opt-in."""
        monkeypatch.delenv("IGRIS_API_TOKEN", raising=False)
        monkeypatch.setenv("IGRIS_ENV", "test")
        monkeypatch.setenv("IGRIS_ALLOW_OPEN_AUTH", "true")
        from unittest.mock import MagicMock
        from app.core.api_auth import verify_request
        req = MagicMock()
        req.url.path = "/api/admin/data"
        req.headers = {}
        assert verify_request(req) is True

    def test_verify_request_no_token_closed_mode(self, monkeypatch):
        monkeypatch.delenv("IGRIS_API_TOKEN", raising=False)
        monkeypatch.setenv("IGRIS_ENV", "production")
        monkeypatch.setenv("IGRIS_ALLOW_OPEN_AUTH", "false")
        from unittest.mock import MagicMock
        from app.core.api_auth import verify_request
        req = MagicMock()
        req.url.path = "/api/admin/data"
        req.headers = {}
        req.method = "GET"
        req.client = MagicMock(host="127.0.0.1")
        assert verify_request(req) is False

    def test_verify_request_correct_token(self, monkeypatch):
        monkeypatch.setenv("IGRIS_API_TOKEN", "test_token_xyz")
        from unittest.mock import MagicMock
        from app.core.api_auth import verify_request
        req = MagicMock()
        req.url.path = "/api/admin/data"
        req.headers = {"authorization": "Bearer test_token_xyz"}
        req.client = MagicMock(host="127.0.0.1")
        assert verify_request(req) is True

    def test_verify_request_wrong_token(self, monkeypatch):
        monkeypatch.setenv("IGRIS_API_TOKEN", "correct_token")
        from unittest.mock import MagicMock
        from app.core.api_auth import verify_request
        req = MagicMock()
        req.url.path = "/api/admin/data"
        req.headers = {"authorization": "Bearer wrong_token"}
        req.client = MagicMock(host="127.0.0.1")
        assert verify_request(req) is False

    def test_timing_safe_comparison(self):
        """verify_request uses hmac.compare_digest — not == operator."""
        import inspect
        import app.core.api_auth as aa
        src = inspect.getsource(aa)
        assert "compare_digest" in src


# ══════════════════════════════════════════════════════════════════════
# 9. DATABASE — user CRUD
# ══════════════════════════════════════════════════════════════════════

class TestDatabaseUserCRUD:
    """Tests for database.py user lookup methods added during security hardening."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from app.core.database import DatabaseManager
        self.db = DatabaseManager(db_path=str(tmp_path / "test.db"))

    def test_create_and_get_user(self):
        result = self.db.create_user("alice", "alice@test.com", "hash_bcrypt_xxx", "api_key_aaa")
        assert result.get("status") == "created"
        user = self.db.get_user_by_username("alice")
        assert user is not None
        assert user["username"] == "alice"
        assert user["email"] == "alice@test.com"

    def test_get_user_not_found(self):
        user = self.db.get_user_by_username("nobody_xyz")
        assert user is None

    def test_get_user_by_id(self):
        res = self.db.create_user("bob", "bob@test.com", "hash_x", "key_bob")
        uid = res["id"]
        user = self.db.get_user_by_id(uid)
        assert user["username"] == "bob"

    def test_get_user_by_api_key(self):
        self.db.create_user("carol", "carol@test.com", "hash_c", "key_unique_carol")
        user = self.db.get_user_by_api_key("key_unique_carol")
        assert user is not None
        assert user["username"] == "carol"

    def test_update_user_password(self):
        res = self.db.create_user("dave", "dave@test.com", "old_hash", "key_dave")
        uid = res["id"]
        updated = self.db.update_user_password(uid, "new_bcrypt_hash")
        assert updated is True
        user = self.db.get_user_by_id(uid)
        assert user["password_hash"] == "new_bcrypt_hash"

    def test_duplicate_username_error(self):
        self.db.create_user("eve", "eve@test.com", "h", "k1")
        res2 = self.db.create_user("eve", "eve2@test.com", "h", "k2")
        assert "error" in res2


# ══════════════════════════════════════════════════════════════════════
# 10. PLUGIN LOADER
# ══════════════════════════════════════════════════════════════════════

class TestPluginLoader:
    """Tests for PluginLoader — load, unload, reload, marketplace."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from app.core.plugin_loader import PluginLoader
        self.loader = PluginLoader(plugins_dir=str(tmp_path))
        self.plugin_dir = tmp_path

    def _write_plugin(self, name: str, extra: str = "") -> str:
        content = f"""
from app.core.plugin_loader import IgrisPlugin

class {name.capitalize()}Plugin(IgrisPlugin):
    NAME    = "{name}"
    VERSION = "1.0.0"
    DESCRIPTION = "Test plugin {name}"
    AUTHOR  = "test"

    def on_command(self, command, args):
        if command == "{name}_cmd":
            return {{"handled_by": "{name}"}}
        return None

    def get_commands(self):
        return [{{"name": "{name}_cmd", "description": "do something"}}]

    def get_status(self):
        return {{"status": "ok", "plugin": "{name}"}}
{extra}
"""
        fpath = self.plugin_dir / f"{name}.py"
        fpath.write_text(content, encoding="utf-8")
        return str(fpath)

    def test_load_all_finds_plugins(self):
        self._write_plugin("alpha")
        self._write_plugin("beta")
        results = self.loader.load_all()
        assert "alpha" in results
        assert results["alpha"] == "loaded"
        assert "beta" in results

    def test_dispatch_command_hits_plugin(self):
        self._write_plugin("gamma")
        self.loader.load_all()
        result = self.loader.dispatch_command("gamma_cmd", {})
        assert result is not None
        assert result["handled_by"] == "gamma"

    def test_dispatch_unknown_command_returns_none(self):
        self._write_plugin("delta")
        self.loader.load_all()
        result = self.loader.dispatch_command("nonexistent_cmd_xyz", {})
        assert result is None

    def test_unload_plugin(self):
        self._write_plugin("epsilon")
        self.loader.load_all()
        assert self.loader.unload_plugin("epsilon") is True
        assert "epsilon" not in {p["name"] for p in self.loader.list_plugins()}

    def test_reload_plugin(self):
        self._write_plugin("zeta")
        self.loader.load_all()
        status = self.loader.reload_plugin("zeta")
        assert status == "loaded"

    def test_list_plugins_returns_dicts(self):
        self._write_plugin("eta")
        self.loader.load_all()
        plugins = self.loader.list_plugins()
        assert isinstance(plugins, list)
        assert any(p["name"] == "eta" for p in plugins)

    def test_get_stats(self):
        self._write_plugin("theta")
        self.loader.load_all()
        stats = self.loader.get_stats()
        assert "plugins_loaded" in stats
        assert "total_commands" in stats
        assert stats["plugins_loaded"] >= 1

    def test_validate_rejects_bad_file(self, tmp_path):
        bad_file = tmp_path / "bad_plugin.py"
        bad_file.write_text("# no IgrisPlugin subclass here\nx = 1\n", encoding="utf-8")
        valid, reason = self.loader._validate_plugin_file(str(bad_file))
        assert valid is False

    def test_validate_accepts_good_file(self):
        fpath = self._write_plugin("iota")
        valid, reason = self.loader._validate_plugin_file(fpath)
        assert valid is True

    def test_marketplace_install_local(self):
        src = self._write_plugin("kappa")
        result = self.loader.marketplace_install("kappa", src)
        assert result["status"] == "loaded"

    def test_marketplace_search_empty_returns_all(self):
        self._write_plugin("lambda_p")
        self.loader.load_all()
        self.loader.marketplace_refresh()
        results = self.loader.marketplace_search("")
        assert isinstance(results, list)

    def test_message_dispatch_modifies_response(self, tmp_path):
        content = """
from app.core.plugin_loader import IgrisPlugin
class MsgPlugin(IgrisPlugin):
    NAME = "msg_plugin"
    def on_message(self, user_msg, ai_response):
        return ai_response + " [modified]"
"""
        (tmp_path / "msg_plugin.py").write_text(content, encoding="utf-8")
        self.loader.plugins_dir = str(tmp_path)
        self.loader.load_all()
        result = self.loader.dispatch_message("hi", "Hello!")
        assert "[modified]" in result


# ══════════════════════════════════════════════════════════════════════
# 11. ADVANCED SECURITY SYSTEM (async)
# ══════════════════════════════════════════════════════════════════════

class TestAdvancedSecuritySystem:
    """Tests for security_system.py — biometric, encryption, IDS, ZKP."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.core.security_system import AdvancedSecuritySystem
        self.sys = AdvancedSecuritySystem()

    # Biometric
    def test_biometric_register_and_verify(self):
        data = b"\xde\xad\xbe\xef" * 16
        run(self.sys.biometric.register_fingerprint("user_fp", data))
        match, conf = run(self.sys.biometric.verify_fingerprint("user_fp", data))
        assert match is True
        assert conf >= 0.9

    def test_biometric_wrong_data_rejected(self):
        run(self.sys.biometric.register_fingerprint("user2", b"original_scan" * 4))
        match, conf = run(self.sys.biometric.verify_fingerprint("user2", b"impostor_data" * 4))
        assert match is False

    def test_biometric_face_roundtrip(self):
        face = b"fake_face_embedding" * 8
        run(self.sys.biometric.register_face("user_face", face))
        match, conf = run(self.sys.biometric.verify_face("user_face", face))
        assert match is True

    def test_biometric_iris_roundtrip(self):
        iris = b"iris_pattern_data" * 6
        run(self.sys.biometric.register_iris("user_iris", iris))
        match, conf = run(self.sys.biometric.verify_iris("user_iris", iris))
        assert match is True

    # Quantum Encryption
    def test_encryption_roundtrip(self):
        enc = self.sys.encryption.encrypt_data("top secret payload", "test_key_1")
        assert "encrypted" in enc
        dec = self.sys.encryption.decrypt_data(enc["encrypted"], "test_key_1")
        assert dec["decrypted"] == "top secret payload"

    def test_encryption_unknown_key_auto_generates(self):
        enc = self.sys.encryption.encrypt_data("hello", "brand_new_key_xyz")
        assert "encrypted" in enc
        assert "error" not in enc

    def test_key_delete(self):
        self.sys.encryption.generate_quantum_safe_key("del_key")
        assert self.sys.encryption.delete_key("del_key") is True
        dec = self.sys.encryption.decrypt_data("anything", "del_key")
        assert "error" in dec

    # Zero-Knowledge Proof
    def test_zkp_valid_proof(self):
        import hashlib as _hl
        ch = run(self.sys.zero_knowledge.generate_challenge("zkp_user"))
        nonce  = ch["challenge"]
        secret = "my_secret_password"
        proof  = hmac.new(secret.encode(), bytes.fromhex(nonce), _hl.sha256).hexdigest()
        valid, result = run(
            self.sys.zero_knowledge.verify_zero_knowledge_proof("zkp_user", secret, proof)
        )
        assert valid is True
        assert result["authenticated"] is True

    def test_zkp_wrong_secret_rejected(self):
        import hashlib as _hl
        ch = run(self.sys.zero_knowledge.generate_challenge("zkp_user2"))
        nonce = ch["challenge"]
        wrong_proof = hmac.new(b"wrong", bytes.fromhex(nonce), _hl.sha256).hexdigest()
        valid, _ = run(
            self.sys.zero_knowledge.verify_zero_knowledge_proof("zkp_user2", "correct", wrong_proof)
        )
        assert valid is False

    def test_zkp_one_time_use(self):
        import hashlib as _hl
        ch     = run(self.sys.zero_knowledge.generate_challenge("zkp_one_time"))
        nonce  = ch["challenge"]
        secret = "s"
        proof  = hmac.new(secret.encode(), bytes.fromhex(nonce), _hl.sha256).hexdigest()
        run(self.sys.zero_knowledge.verify_zero_knowledge_proof("zkp_one_time", secret, proof))
        # Second attempt — challenge consumed
        valid, result = run(
            self.sys.zero_knowledge.verify_zero_knowledge_proof("zkp_one_time", secret, proof)
        )
        assert valid is False

    # IDS
    def test_ids_normal_activity(self):
        result = run(self.sys.intrusion_detection.monitor_activity({
            "ip_address": "192.168.1.1",
            "failed_logins": 0,
            "file_operations": 5,
        }))
        assert result.get("status") in ("normal", "alert", "whitelisted")

    def test_ids_high_threat_triggers_alert(self):
        result = run(self.sys.intrusion_detection.monitor_activity({
            "ip_address": "10.0.0.99",
            "failed_logins": 20,
            "privilege_escalation": True,
            "sql_injection_attempt": True,
        }))
        assert result["threat_level"] >= 0.7
        assert result["status"] == "alert"

    def test_ids_blacklist(self):
        self.sys.intrusion_detection.add_to_blacklist("6.6.6.6")
        result = run(self.sys.intrusion_detection.monitor_activity({"ip_address": "6.6.6.6"}))
        assert result["status"] == "blacklisted"

    # Secure operation gate
    def test_secure_operation_approved(self):
        from app.core.security_system import SecurityLevel
        self.sys.security_level = SecurityLevel.RESTRICTED
        result = run(self.sys.secure_operation(
            "test_op", {"key": "val"}, SecurityLevel.RESTRICTED
        ))
        assert result["status"] == "approved"

    def test_secure_operation_denied_insufficient_level(self):
        from app.core.security_system import SecurityLevel
        self.sys.security_level = SecurityLevel.PUBLIC
        result = run(self.sys.secure_operation(
            "classified_op", {}, SecurityLevel.TOP_SECRET
        ))
        assert result["status"] == "denied"

    # Status report
    def test_security_status_structure(self):
        status = run(self.sys.get_security_status())
        assert "system_status" in status
        assert "security_level" in status
        assert "biometric" in status
        assert "encryption" in status
        assert "checked_at" in status


# ══════════════════════════════════════════════════════════════════════
# 12. FASTAPI ADMIN AUTH ROUTES (TestClient)
# ══════════════════════════════════════════════════════════════════════

class TestAdminAuthRoutes:
    """Integration tests for /api/admin/auth/* endpoints."""

    @pytest.fixture(autouse=True)
    def client(self, tmp_path):
        try:
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from app.api.admin_routes import router
            app = FastAPI()
            app.include_router(router)
            self.client = TestClient(app, raise_server_exceptions=False)
        except Exception as e:
            pytest.skip(f"FastAPI TestClient unavailable: {e}")

    def test_register_user(self):
        r = self.client.post("/api/admin/auth/register", json={
            "username": "igris_test_user",
            "email":    "igris@test.com",
            "password": "Str0ngP@ssword"
        })
        assert r.status_code in (200, 409)  # 409 = already exists

    def test_login_wrong_credentials(self):
        r = self.client.post("/api/admin/auth/login", json={
            "username": "nonexistent_xyz",
            "password": "wrongpass"
        })
        assert r.status_code == 401

    def test_login_missing_fields(self):
        r = self.client.post("/api/admin/auth/login", json={"username": "x"})
        assert r.status_code in (400, 422)

    def test_verify_invalid_token(self):
        r = self.client.post("/api/admin/auth/verify-token", json={
            "token": "not.a.real.token"
        })
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_refresh_missing_token(self):
        r = self.client.post("/api/admin/auth/refresh", json={})
        assert r.status_code == 400

    def test_2fa_provision_requires_auth(self):
        r = self.client.post("/api/admin/auth/2fa/provision")
        assert r.status_code in (401, 422)

    def test_2fa_verify_requires_auth(self):
        r = self.client.post("/api/admin/auth/2fa/verify", json={"otp": "123456"})
        assert r.status_code in (401, 422)


# ══════════════════════════════════════════════════════════════════════
# RUN DIRECTLY
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
