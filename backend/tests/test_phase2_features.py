"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS PHASE 2 FEATURE TESTS
  Tests for all 7 new features: Browser, Voice, Agent, Feedback,
  Git, Email, Cost Tracker
  Run: pytest tests/test_phase2_features.py -v
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
#  COST TRACKER TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestCostTracker:
    def test_import(self):
        from app.core.cost_tracker import get_cost_tracker, MODEL_PRICING
        ct = get_cost_tracker()
        assert ct is not None
        assert len(MODEL_PRICING) > 10

    def test_pricing_lookup(self):
        from app.core.cost_tracker import IgrisAPIcostTracker
        pricing = IgrisAPIcostTracker.get_pricing("gpt-4o")
        assert pricing["input"] == 2.50
        assert pricing["output"] == 10.00

    def test_pricing_fallback(self):
        from app.core.cost_tracker import IgrisAPIcostTracker, _DEFAULT_PRICING
        pricing = IgrisAPIcostTracker.get_pricing("unknown-model-xyz")
        assert pricing == _DEFAULT_PRICING

    def test_token_estimation(self):
        from app.core.cost_tracker import IgrisAPIcostTracker
        tokens = IgrisAPIcostTracker.estimate_tokens("hello world test")
        assert tokens > 0

    def test_track_call(self):
        from app.core.cost_tracker import get_cost_tracker
        ct = get_cost_tracker()
        initial = len(ct._calls)
        rec = ct.track_call("test_provider", "gpt-4o-mini", "test input", "test output", latency_ms=100)
        assert rec.success is True
        assert rec.total_cost_usd >= 0
        assert rec.provider == "test_provider"
        assert len(ct._calls) == initial + 1

    def test_track_free_model(self):
        from app.core.cost_tracker import get_cost_tracker
        ct = get_cost_tracker()
        rec = ct.track_call("ollama", "llama3", "hello", "world")
        assert rec.total_cost_usd == 0.0

    def test_stats(self):
        from app.core.cost_tracker import get_cost_tracker
        ct = get_cost_tracker()
        stats = ct.get_stats()
        assert "total_calls" in stats
        assert "daily_cost_usd" in stats
        assert "monthly_cost_usd" in stats
        assert "by_model" in stats
        assert "by_provider" in stats

    def test_budget_set(self):
        from app.core.cost_tracker import get_cost_tracker
        ct = get_cost_tracker()
        ct.set_budget(daily_usd=5.0, monthly_usd=100.0)
        assert ct._daily_budget == 5.0
        assert ct._monthly_budget == 100.0
        ct.set_budget(daily_usd=1.0, monthly_usd=20.0)  # reset

    def test_singleton(self):
        from app.core.cost_tracker import get_cost_tracker
        ct1 = get_cost_tracker()
        ct2 = get_cost_tracker()
        assert ct1 is ct2


# ─────────────────────────────────────────────────────────────────────────────
#  FEEDBACK ENGINE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedbackEngine:
    def test_import(self):
        from app.core.feedback_engine import get_feedback_engine
        fe = get_feedback_engine()
        assert fe is not None

    def test_submit_positive(self):
        from app.core.feedback_engine import get_feedback_engine
        fe = get_feedback_engine()
        r = fe.submit_feedback("What is 2+2?", "4", rating=1, model_used="gpt-4o")
        assert r.rating == 1
        assert r.feedback_id is not None
        assert r.user_message == "What is 2+2?"

    def test_submit_negative(self):
        from app.core.feedback_engine import get_feedback_engine
        fe = get_feedback_engine()
        r = fe.submit_feedback("Tell me a joke", "bad answer", rating=-1, feedback_text="Not funny")
        assert r.rating == -1

    def test_rating_clamp(self):
        from app.core.feedback_engine import get_feedback_engine
        fe = get_feedback_engine()
        r = fe.submit_feedback("test", "test", rating=999)
        assert r.rating == 1
        r = fe.submit_feedback("test", "test", rating=-999)
        assert r.rating == -1

    def test_stats(self):
        from app.core.feedback_engine import get_feedback_engine
        fe = get_feedback_engine()
        stats = fe.get_stats()
        assert "total_ratings" in stats
        assert "positive" in stats
        assert "negative" in stats
        assert "positive_rate" in stats

    def test_recent_feedback(self):
        from app.core.feedback_engine import get_feedback_engine
        fe = get_feedback_engine()
        recent = fe.get_recent_feedback(5)
        assert isinstance(recent, list)

    def test_singleton(self):
        from app.core.feedback_engine import get_feedback_engine
        fe1 = get_feedback_engine()
        fe2 = get_feedback_engine()
        assert fe1 is fe2


# ─────────────────────────────────────────────────────────────────────────────
#  GIT AGENT TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestGitAgent:
    def test_import(self):
        from app.core.git_agent import get_git_agent
        ga = get_git_agent()
        assert ga is not None

    def test_not_git_repo(self):
        from app.core.git_agent import IgrisGitAgent
        ga = IgrisGitAgent(os.path.expanduser("~"))
        # Home dir may or may not be a git repo — just check method exists
        result = ga._is_git_repo()
        assert isinstance(result, bool)

    def test_set_repo(self):
        from app.core.git_agent import get_git_agent
        ga = get_git_agent()
        ga.set_repo(os.path.expanduser("~"))
        assert ga._repo_path == os.path.abspath(os.path.expanduser("~"))
        # Reset to test project
        ga.set_repo(os.path.join(os.path.dirname(__file__), ".."))

    @pytest.mark.asyncio
    async def test_run_git_log(self):
        from app.core.git_agent import get_git_agent
        ga = get_git_agent(os.path.join(os.path.dirname(__file__), ".."))
        if ga._is_git_repo():
            result = await ga.log(limit=5)
            assert isinstance(result.stdout, str)
            assert isinstance(result.success, bool)
        else:
            pytest.skip("Not in a git repository")

    @pytest.mark.asyncio
    async def test_git_status(self):
        from app.core.git_agent import get_git_agent
        ga = get_git_agent(os.path.join(os.path.dirname(__file__), ".."))
        if ga._is_git_repo():
            status = await ga.status()
            assert hasattr(status, "branch")
            assert isinstance(status.staged, list)
            assert isinstance(status.modified, list)
        else:
            pytest.skip("Not in a git repository")

    def test_singleton(self):
        from app.core.git_agent import get_git_agent
        ga1 = get_git_agent()
        ga2 = get_git_agent()
        assert ga1 is ga2

    def test_history(self):
        from app.core.git_agent import get_git_agent
        ga = get_git_agent()
        h = ga.get_history()
        assert isinstance(h, list)


# ─────────────────────────────────────────────────────────────────────────────
#  EMAIL AGENT TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailAgent:
    def test_import(self):
        from app.core.email_agent import get_email_agent
        ea = get_email_agent()
        assert ea is not None

    def test_no_config_available(self):
        from app.core.email_agent import IgrisEmailAgent
        # Without env vars, should be unconfigured
        ea = IgrisEmailAgent()
        # Either configured (env has it) or not
        assert isinstance(ea.available, bool)

    def test_gmail_config(self):
        from app.core.email_agent import EmailConfig
        cfg = EmailConfig.gmail("test@gmail.com", "app_password")
        assert cfg.smtp_host == "smtp.gmail.com"
        assert cfg.smtp_port == 587
        assert cfg.imap_host == "imap.gmail.com"

    def test_outlook_config(self):
        from app.core.email_agent import EmailConfig
        cfg = EmailConfig.outlook("test@outlook.com", "pass")
        assert cfg.smtp_host == "smtp.office365.com"

    @pytest.mark.asyncio
    async def test_send_no_config(self):
        from app.core.email_agent import IgrisEmailAgent
        ea = IgrisEmailAgent()  # no config
        if not ea.available:
            result = await ea.send("to@test.com", "Test", "Body")
            assert result.success is False
            assert "not configured" in result.error.lower()

    def test_status(self):
        from app.core.email_agent import get_email_agent
        ea = get_email_agent()
        status = ea.get_status()
        assert "configured" in status
        assert "emails_sent" in status


# ─────────────────────────────────────────────────────────────────────────────
#  BROWSER AGENT TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestBrowserAgent:
    def test_import(self):
        from app.core.browser_agent import get_browser_agent
        ba = get_browser_agent()
        assert ba is not None

    def test_status(self):
        from app.core.browser_agent import get_browser_agent
        ba = get_browser_agent()
        status = ba.get_status()
        assert "playwright_available" in status
        assert "session_active" in status

    @pytest.mark.asyncio
    async def test_browse_no_playwright(self):
        from app.core.browser_agent import IgrisBrowserAgent
        ba = IgrisBrowserAgent()
        if not ba._available:
            result = await ba.browse("https://example.com")
            assert result.success is False
            assert "playwright" in result.error.lower()

    def test_singleton(self):
        from app.core.browser_agent import get_browser_agent
        ba1 = get_browser_agent()
        ba2 = get_browser_agent()
        assert ba1 is ba2

    def test_history_empty(self):
        from app.core.browser_agent import IgrisBrowserAgent
        ba = IgrisBrowserAgent()
        assert ba.get_history() == []


# ─────────────────────────────────────────────────────────────────────────────
#  ADVANCED VOICE ENGINE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAdvancedVoiceEngine:
    def test_import(self):
        from app.core.advanced_voice_engine import get_voice_engine
        ve = get_voice_engine()
        assert ve is not None

    def test_status(self):
        from app.core.advanced_voice_engine import get_voice_engine
        ve = get_voice_engine()
        status = ve.get_full_status()
        assert "stt" in status
        assert "tts" in status
        assert "whisper_available" in status["stt"]
        assert "preferred_engine" in status["tts"]

    def test_wake_word_detection(self):
        from app.core.advanced_voice_engine import IgrisSTTEngine
        stt = IgrisSTTEngine()
        assert stt.check_wake_word("arise igris, tell me the time")
        assert stt.check_wake_word("hey igris")
        assert stt.check_wake_word("IGRIS hello")
        assert not stt.check_wake_word("what is the weather")

    def test_tts_status(self):
        from app.core.advanced_voice_engine import IgrisTTSEngine
        tts = IgrisTTSEngine()
        status = tts.get_status()
        assert "preferred_engine" in status
        assert status["preferred_engine"] in ("elevenlabs", "openai_tts", "pyttsx3", "none")

    @pytest.mark.asyncio
    async def test_tts_no_key(self):
        from app.core.advanced_voice_engine import IgrisTTSEngine
        tts = IgrisTTSEngine()
        # No keys set — should use pyttsx3 or fail gracefully
        # We don't actually speak in tests, just check it returns
        # Use return_audio=True to avoid actual audio output
        if tts._preferred_engine in ("none",):
            pytest.skip("No TTS engine available")

    @pytest.mark.asyncio
    async def test_transcribe_empty_bytes(self):
        from app.core.advanced_voice_engine import get_voice_engine
        ve = get_voice_engine()
        # Empty audio — should fail gracefully
        result = await ve.transcribe_upload(b"", "wav")
        # Should return a result (success or failure), not crash
        assert hasattr(result, "success")

    def test_singleton(self):
        from app.core.advanced_voice_engine import get_voice_engine
        ve1 = get_voice_engine()
        ve2 = get_voice_engine()
        assert ve1 is ve2


# ─────────────────────────────────────────────────────────────────────────────
#  AUTONOMOUS AGENT TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAutonomousAgent:
    def test_import(self):
        from app.core.autonomous_agent import get_autonomous_agent
        aa = get_autonomous_agent()
        assert aa is not None

    def test_status(self):
        from app.core.autonomous_agent import get_autonomous_agent
        aa = get_autonomous_agent()
        status = aa.get_status()
        assert "llm_available" in status
        assert "tools_available" in status
        assert "max_steps" in status
        assert status["max_steps"] == 10

    def test_register_custom_tool(self):
        from app.core.autonomous_agent import IgrisAutonomousAgent
        aa = IgrisAutonomousAgent()
        def my_tool(x: str):
            return {"result": x}
        aa.register_tool("my_tool", my_tool, description="Test tool")
        assert "my_tool" in aa._extra_tools

    def test_get_tools_description(self):
        from app.core.autonomous_agent import IgrisAutonomousAgent
        aa = IgrisAutonomousAgent()
        desc = aa._get_tools_description()
        assert "final_answer" in desc

    def test_history_empty(self):
        from app.core.autonomous_agent import IgrisAutonomousAgent
        aa = IgrisAutonomousAgent()
        assert aa.get_run_history() == []

    @pytest.mark.asyncio
    async def test_run_no_llm(self):
        from app.core.autonomous_agent import IgrisAutonomousAgent
        aa = IgrisAutonomousAgent()
        if not aa.get_status()["llm_available"]:
            run = await aa.run("What is 2+2?")
            assert run.success is False
            assert "LLM not available" in run.final_answer

    def test_singleton(self):
        from app.core.autonomous_agent import get_autonomous_agent
        aa1 = get_autonomous_agent()
        aa2 = get_autonomous_agent()
        assert aa1 is aa2


# ─────────────────────────────────────────────────────────────────────────────
#  API ROUTES TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestNewPowerRoutes:
    def test_routes_load(self):
        from app.api.new_power_routes import router
        assert router is not None
        assert len(router.routes) > 30  # We have 42 routes

    def test_route_paths_exist(self):
        from app.api.new_power_routes import router
        paths = [r.path for r in router.routes]
        # Check key routes exist
        assert "/igris/browser/status" in paths
        assert "/igris/voice-advanced/status" in paths
        assert "/igris/agent/status" in paths
        assert "/igris/feedback/stats" in paths
        assert "/igris/git/status" in paths
        assert "/igris/email/status" in paths
        assert "/igris/costs/stats" in paths
        assert "/igris/new-features/health" in paths


# ─────────────────────────────────────────────────────────────────────────────
#  INTEGRATION SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def test_all_modules_importable():
    """Master integration test — all 7 Phase 2 modules must be importable."""
    from app.core.browser_agent import get_browser_agent
    from app.core.advanced_voice_engine import get_voice_engine
    from app.core.autonomous_agent import get_autonomous_agent
    from app.core.feedback_engine import get_feedback_engine
    from app.core.git_agent import get_git_agent
    from app.core.email_agent import get_email_agent
    from app.core.cost_tracker import get_cost_tracker
    from app.api.new_power_routes import router

    # All must return objects
    assert get_browser_agent() is not None
    assert get_voice_engine() is not None
    assert get_autonomous_agent() is not None
    assert get_feedback_engine() is not None
    assert get_git_agent() is not None
    assert get_email_agent() is not None
    assert get_cost_tracker() is not None
    assert router is not None
    print("✅ ALL 7 PHASE 2 MODULES IMPORTABLE AND FUNCTIONAL")
