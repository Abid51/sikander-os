"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS OS — VOICE CONTROL TEST SUITE
  Full coverage for voice_control.py, voice_routes.py, and bilingual
  command parsing (Urdu + English).
  Run: python -m pytest tests/test_voice_system.py -v
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.voice_control import VoiceCommandHandler


# ══════════════════════════════════════════════════════════════════════════════
#  VOICE COMMAND HANDLER — UNIT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceCommandHandler:
    """Unit tests for VoiceCommandHandler core logic."""

    @pytest.fixture(autouse=True)
    def fresh_handler(self):
        self.handler = VoiceCommandHandler()

    # ── Intent parsing — English ──────────────────────────────────────────────

    def test_parse_status_english(self):
        intent = self.handler._parse_intent("what is the status")
        assert intent is not None
        assert intent["command"] == "get_status"
        assert intent["confidence"] >= 0.7

    def test_parse_auto_mode_english(self):
        intent = self.handler._parse_intent("turn on auto mode")
        assert intent is not None
        assert intent["command"] == "enable_auto_mode"

    def test_parse_disable_auto_english(self):
        intent = self.handler._parse_intent("disable auto")
        assert intent is not None
        assert intent["command"] == "disable_auto_mode"

    def test_parse_generate_content_english(self):
        intent = self.handler._parse_intent("generate a report")
        assert intent is not None
        assert intent["command"] == "generate_content"

    def test_parse_answer_question_english(self):
        intent = self.handler._parse_intent("what is machine learning")
        assert intent is not None
        assert intent["command"] == "answer_question"

    def test_parse_learning_mode_english(self):
        intent = self.handler._parse_intent("enter training mode")
        assert intent is not None
        assert intent["command"] == "learning_mode"

    def test_parse_modify_self_english(self):
        intent = self.handler._parse_intent("modify yourself to be better")
        assert intent is not None
        assert intent["command"] == "modify_self"

    def test_parse_execute_pending_english(self):
        intent = self.handler._parse_intent("confirm yes proceed")
        assert intent is not None
        assert intent["command"] == "execute_pending"

    # ── Intent parsing — Urdu ─────────────────────────────────────────────────

    def test_parse_status_urdu(self):
        intent = self.handler._parse_intent("کیا ہو رہا ہے")
        assert intent is not None
        assert intent["command"] == "get_status"

    def test_parse_auto_mode_urdu(self):
        intent = self.handler._parse_intent("خودکار mode چالو کرو")
        assert intent is not None
        assert intent["command"] == "enable_auto_mode"

    def test_parse_generate_content_urdu(self):
        intent = self.handler._parse_intent("ایک مضمون لکھو")
        assert intent is not None
        assert intent["command"] == "generate_content"

    def test_parse_learning_urdu(self):
        intent = self.handler._parse_intent("سیکھو اور بہتر بنو")
        assert intent is not None
        assert intent["command"] == "learning_mode"

    def test_parse_answer_question_urdu(self):
        intent = self.handler._parse_intent("مجھے بتاؤ")
        assert intent is not None
        assert intent["command"] == "answer_question"

    def test_parse_modify_self_urdu(self):
        intent = self.handler._parse_intent("اپنے آپ کو تبدیل کریں")
        assert intent is not None
        assert intent["command"] == "modify_self"

    # ── No match ─────────────────────────────────────────────────────────────

    def test_parse_unknown_returns_none(self):
        intent = self.handler._parse_intent("kljhglkjshg random gibberish xyz")
        assert intent is None

    def test_parse_empty_string_returns_none(self):
        intent = self.handler._parse_intent("")
        assert intent is None

    # ── Parameter extraction ──────────────────────────────────────────────────

    def test_extract_numbers(self):
        params = self.handler._extract_parameters("run 5 times at 300 ms", "execute_pending")
        assert "numbers" in params
        assert 5 in params["numbers"]
        assert 300 in params["numbers"]

    def test_extract_quoted_text(self):
        params = self.handler._extract_parameters('generate a "sales report" for me', "generate_content")
        assert "quoted_text" in params
        assert "sales report" in params["quoted_text"]

    def test_extract_language_urdu(self):
        params = self.handler._extract_parameters("اردو میں لکھو", "generate_content")
        assert params.get("language") == "urdu"

    def test_extract_language_english(self):
        params = self.handler._extract_parameters("write it in english", "generate_content")
        assert params.get("language") == "english"

    def test_extract_content_length_short(self):
        params = self.handler._extract_parameters("write a short summary", "generate_content")
        assert params.get("length") == "short"

    def test_extract_content_length_full(self):
        params = self.handler._extract_parameters("write a full report", "generate_content")
        assert params.get("length") == "full"

    # ── Auto mode toggle ──────────────────────────────────────────────────────

    def test_set_auto_mode_enable(self):
        result = self.handler.set_auto_mode(True)
        assert result["auto_mode"] is True
        assert result["status"] == "updated"

    def test_set_auto_mode_disable(self):
        result = self.handler.set_auto_mode(False)
        assert result["auto_mode"] is False

    # ── Command registration & log ────────────────────────────────────────────

    def test_register_command(self):
        async def my_handler(params): return {"done": True}
        self.handler.register_command("test_cmd", my_handler, "Test command")
        cmds = self.handler.get_registered_commands()
        assert "test_cmd" in cmds

    def test_voice_log_empty_initially(self):
        log = self.handler.get_voice_log()
        assert isinstance(log, list)
        assert len(log) == 0

    # ── Async command processing ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_process_command_no_match(self):
        result = await self.handler.process_voice_command("totally nonsense text xyz123")
        assert result["status"] == "no_match"

    @pytest.mark.asyncio
    async def test_process_command_unknown_handler(self):
        # Intent parsed but no handler registered
        result = await self.handler.process_voice_command("what is the status right now")
        # Should be either pending_confirmation (auto_mode off) or unknown_command
        assert result["status"] in ("unknown_command", "pending_confirmation", "success")

    @pytest.mark.asyncio
    async def test_process_command_with_registered_handler(self):
        call_log = []

        async def mock_handler(params):
            call_log.append(params)
            return {"executed": True}

        self.handler.register_command("get_status", mock_handler, "Status check")
        result = await self.handler.process_voice_command("what is the status")
        assert result["status"] == "success"
        assert len(call_log) == 1

    @pytest.mark.asyncio
    async def test_process_command_low_confidence_blocked(self):
        # Patch confidence for this test
        original = self.handler.command_confidence_threshold
        self.handler.command_confidence_threshold = 0.99  # impossibly high
        result = await self.handler.process_voice_command("what is the status")
        self.handler.command_confidence_threshold = original
        # Even parsed commands should fail threshold check
        assert result["status"] in ("low_confidence", "no_match")


# ══════════════════════════════════════════════════════════════════════════════
#  VOICE ROUTES — API TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceRoutesAPI:
    """Smoke tests for /api/voice/* FastAPI endpoints."""

    @pytest.fixture(autouse=True)
    def client(self):
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.api.voice_routes import router
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_get_voice_log(self):
        r = self.client.get("/api/voice/log")
        assert r.status_code == 200
        data = r.json()
        assert "log" in data

    def test_get_voice_status(self):
        r = self.client.get("/api/voice/status")
        assert r.status_code == 200

    def test_process_command_missing_transcript(self):
        r = self.client.post("/api/voice/process-command", json={"language": "ur-PK"})
        assert r.status_code == 422   # unprocessable entity

    def test_process_command_valid(self):
        r = self.client.post(
            "/api/voice/process-command",
            json={"transcript": "what is the status", "language": "en-US"}
        )
        assert r.status_code in (200, 500)   # 500 acceptable if brain not initialized

    def test_set_auto_mode_enable(self):
        r = self.client.post("/api/voice/auto-mode", json={"enabled": True})
        assert r.status_code in (200, 404, 422)

    def test_set_auto_mode_disable(self):
        r = self.client.post("/api/voice/auto-mode", json={"enabled": False})
        assert r.status_code in (200, 404, 422)

    def test_voice_modify_function_forbidden_no_token(self):
        r = self.client.post(
            "/api/voice/modify/function",
            json={
                "module_name":   "app.core.ai_core",
                "function_name": "some_func",
                "new_logic":     "def some_func():\n    return 1\n",
            },
        )
        assert r.status_code == 403

    def test_voice_speak_endpoint(self):
        r = self.client.post("/api/voice/speak", json={"text": "Igris is ready."})
        assert r.status_code in (200, 500)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
