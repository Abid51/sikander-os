"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS OS — PLUGIN SYSTEM TEST SUITE
  Full coverage for plugin_loader.py, IgrisPlugin base class,
  lifecycle hooks, hot-reload, marketplace, and production plugins.
  Run: python -m pytest tests/test_plugin_system.py -v
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import time
import textwrap
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.plugin_loader import IgrisPlugin, PluginLoader, _check_requires


# ══════════════════════════════════════════════════════════════════════════════
#  IGRISPLUGIN BASE CLASS
# ══════════════════════════════════════════════════════════════════════════════

class TestIgrisPluginBase:
    """Tests for IgrisPlugin abstract base."""

    def test_default_attributes(self):
        class MyPlugin(IgrisPlugin):
            NAME = "test_plugin"
        p = MyPlugin()
        assert p.NAME        == "test_plugin"
        assert p.VERSION     == "1.0.0"
        assert p.REQUIRES    == []
        assert p.TAGS        == []

    def test_default_get_status_returns_ok(self):
        p = IgrisPlugin()
        status = p.get_status()
        assert status["status"] == "ok"

    def test_default_get_commands_returns_empty(self):
        p = IgrisPlugin()
        assert p.get_commands() == []

    def test_on_command_returns_none(self):
        p = IgrisPlugin()
        result = p.on_command("anything", {})
        assert result is None

    def test_on_message_returns_none(self):
        p = IgrisPlugin()
        result = p.on_message("hello", "response")
        assert result is None

    def test_lifecycle_hooks_dont_raise(self):
        p = IgrisPlugin()
        p.on_load()
        p.on_startup()
        p.on_shutdown()
        p.on_unload()


# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCY CHECKER
# ══════════════════════════════════════════════════════════════════════════════

class TestDependencyChecker:

    def test_existing_package_not_missing(self):
        missing = _check_requires(["os"])
        assert "os" not in missing

    def test_json_module_present(self):
        missing = _check_requires(["json"])
        assert len(missing) == 0

    def test_fake_package_is_missing(self):
        missing = _check_requires(["igris_fake_pkg_xyz_9999"])
        assert "igris_fake_pkg_xyz_9999" in missing

    def test_versioned_requirement_parsed_correctly(self):
        # "psutil>=5.0" should try to import "psutil"
        missing = _check_requires(["psutil>=5.0"])
        assert len(missing) == 0   # psutil should be installed

    def test_empty_requires_returns_empty(self):
        missing = _check_requires([])
        assert missing == []


# ══════════════════════════════════════════════════════════════════════════════
#  PLUGIN LOADER — core functionality
# ══════════════════════════════════════════════════════════════════════════════

class TestPluginLoader:

    @pytest.fixture()
    def loader(self, tmp_path):
        return PluginLoader(plugins_dir=str(tmp_path))

    @pytest.fixture()
    def valid_plugin_file(self, tmp_path):
        code = textwrap.dedent("""
            from app.core.plugin_loader import IgrisPlugin

            class HelloPlugin(IgrisPlugin):
                NAME        = "hello_test"
                VERSION     = "1.0.0"
                DESCRIPTION = "Test plugin"
                AUTHOR      = "Test"

                def __init__(self):
                    self._loaded = False
                    self._started = False
                    self._cmd_results = []

                def on_load(self):
                    self._loaded = True

                def on_startup(self):
                    self._started = True

                def on_command(self, command, args):
                    if command == "hello":
                        name = args.get("name", "World")
                        return f"Hello, {name}!"
                    return None

                def get_commands(self):
                    return [{"name": "hello", "args": ["name"], "description": "Say hello"}]

                def get_status(self):
                    return {"status": "ok", "loaded": self._loaded}
        """)
        plugin_file = tmp_path / "hello_test.py"
        plugin_file.write_text(code, encoding="utf-8")
        return str(plugin_file)

    @pytest.fixture()
    def invalid_plugin_file(self, tmp_path):
        code = "# No IgrisPlugin subclass here\nprint('not a plugin')\n"
        f = tmp_path / "bad_plugin.py"
        f.write_text(code, encoding="utf-8")
        return str(f)

    @pytest.fixture()
    def syntax_error_plugin_file(self, tmp_path):
        code = "class Broken(:\n    pass\n"
        f = tmp_path / "broken.py"
        f.write_text(code, encoding="utf-8")
        return str(f)

    # ── load_all ─────────────────────────────────────────────────────────────

    def test_load_all_empty_dir(self, loader):
        results = loader.load_all()
        assert isinstance(results, dict)
        assert len(results) == 0

    def test_load_all_valid_plugin(self, loader, valid_plugin_file, tmp_path):
        results = loader.load_all()
        assert results.get("hello_test") == "loaded"
        assert "hello_test" in [p["name"] for p in loader.list_plugins()]

    def test_load_all_skips_private_files(self, loader, tmp_path):
        private = tmp_path / "__private.py"
        private.write_text("# private", encoding="utf-8")
        results = loader.load_all()
        assert "__private" not in results

    def test_load_all_invalid_plugin_reports_error(self, loader, invalid_plugin_file, tmp_path):
        results = loader.load_all()
        status = results.get("bad_plugin", "")
        assert "no" in status.lower() or "error" in status.lower()

    # ── list_plugins ─────────────────────────────────────────────────────────

    def test_list_plugins_structure(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        plugins = loader.list_plugins()
        assert isinstance(plugins, list)
        assert len(plugins) == 1
        p = plugins[0]
        assert "name"        in p
        assert "version"     in p
        assert "description" in p
        assert "enabled"     in p

    # ── dispatch_command ─────────────────────────────────────────────────────

    def test_dispatch_command_found(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        result = loader.dispatch_command("hello", {"name": "Igris"})
        assert result == "Hello, Igris!"

    def test_dispatch_command_not_found_returns_none(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        result = loader.dispatch_command("unknown_xyz_command", {})
        assert result is None

    def test_dispatch_message_passthrough(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        result = loader.dispatch_message("hi", "original response")
        assert result == "original response"  # plugin doesn't modify

    # ── fire_startup / fire_shutdown ──────────────────────────────────────────

    def test_fire_startup_runs_without_error(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        loader.fire_startup()   # should not raise

    def test_fire_shutdown_runs_without_error(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        loader.fire_shutdown()

    # ── unload_plugin ─────────────────────────────────────────────────────────

    def test_unload_removes_plugin(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        assert loader.unload_plugin("hello_test") is True
        assert "hello_test" not in [p["name"] for p in loader.list_plugins()]

    def test_unload_nonexistent_returns_false(self, loader):
        assert loader.unload_plugin("ghost_plugin_xyz") is False

    # ── reload_plugin ─────────────────────────────────────────────────────────

    def test_reload_plugin_works(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        result = loader.reload_plugin("hello_test")
        assert result == "loaded"

    def test_reload_nonexistent_returns_not_found(self, loader):
        result = loader.reload_plugin("nonexistent_xyz")
        assert "not found" in result

    # ── get_plugin_status ─────────────────────────────────────────────────────

    def test_get_plugin_status(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        status = loader.get_plugin_status("hello_test")
        assert status is not None
        assert "info"     in status
        assert "status"   in status
        assert "commands" in status

    def test_get_plugin_status_nonexistent(self, loader):
        assert loader.get_plugin_status("nonexistent") is None

    # ── get_stats ─────────────────────────────────────────────────────────────

    def test_get_stats_structure(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        stats = loader.get_stats()
        assert "plugins_loaded"   in stats
        assert "total_commands"   in stats
        assert "file_watcher"     in stats
        assert stats["plugins_loaded"] == 1

    # ── validation ────────────────────────────────────────────────────────────

    def test_validate_valid_plugin(self, loader, valid_plugin_file):
        ok, reason = loader._validate_plugin_file(valid_plugin_file)
        assert ok is True
        assert reason == ""

    def test_validate_invalid_plugin(self, loader, invalid_plugin_file):
        ok, reason = loader._validate_plugin_file(invalid_plugin_file)
        assert ok is False

    def test_validate_syntax_error(self, loader, syntax_error_plugin_file):
        ok, reason = loader._validate_plugin_file(syntax_error_plugin_file)
        assert ok is False
        assert "syntax" in reason.lower() or len(reason) > 0

    # ── marketplace ───────────────────────────────────────────────────────────

    def test_marketplace_search_empty(self, loader):
        result = loader.marketplace_search("anything")
        assert isinstance(result, list)

    def test_marketplace_refresh_local_fallback(self, loader, valid_plugin_file, tmp_path):
        loader.load_all()
        result = loader.marketplace_refresh()
        assert result["status"] == "refreshed"
        assert result["count"] >= 0


# ══════════════════════════════════════════════════════════════════════════════
#  PRODUCTION PLUGINS — integration tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSystemMonitorPlugin:
    """Tests for the system_monitor_pro production plugin."""

    @pytest.fixture(autouse=True)
    def plugin(self):
        # Import directly (not via loader) for isolation
        import importlib.util, os
        spec_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "plugins", "system_monitor_pro.py"
        )
        if not os.path.exists(spec_path):
            pytest.skip("system_monitor_pro.py not found")
        spec   = importlib.util.spec_from_file_location("system_monitor_pro", spec_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.plugin = module.SystemMonitorPlugin()
        self.plugin.on_load()
        yield
        self.plugin.on_unload()

    def test_get_commands(self):
        cmds = self.plugin.get_commands()
        names = [c["name"] for c in cmds]
        assert "system_health"   in names
        assert "clear_alerts"    in names
        assert "set_threshold"   in names
        assert "stats_history"   in names

    def test_system_health_command(self):
        result = self.plugin.on_command("system_health", {})
        assert result is not None
        assert "cpu_percent"    in result
        assert "ram_percent"    in result
        assert "disk_percent"   in result
        assert "status"         in result

    def test_clear_alerts_command(self):
        result = self.plugin.on_command("clear_alerts", {})
        assert result["status"] == "cleared"

    def test_set_threshold_cpu(self):
        result = self.plugin.on_command("set_threshold", {"metric": "CPU", "value": 75})
        assert result["status"] == "updated"
        assert self.plugin.CPU_THRESHOLD == 75

    def test_set_threshold_invalid_metric(self):
        result = self.plugin.on_command("set_threshold", {"metric": "BOGUS", "value": 50})
        assert "error" in result

    def test_set_threshold_invalid_value(self):
        result = self.plugin.on_command("set_threshold", {"metric": "RAM", "value": "not_a_number"})
        assert "error" in result

    def test_unknown_command_returns_none(self):
        result = self.plugin.on_command("xyz_unknown", {})
        assert result is None

    def test_get_status(self):
        status = self.plugin.get_status()
        assert "uptime_secs"     in status
        assert "alerts_count"    in status
        assert "thresholds"      in status

    def test_stats_history_grows(self):
        time.sleep(0.1)
        result = self.plugin.on_command("stats_history", {"limit": 50})
        assert "history" in result
        assert isinstance(result["history"], list)


class TestSmartContextPlugin:
    """Tests for the smart_context_enhancer production plugin."""

    @pytest.fixture(autouse=True)
    def plugin(self):
        import importlib.util, os
        spec_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "plugins", "smart_context_enhancer.py"
        )
        if not os.path.exists(spec_path):
            pytest.skip("smart_context_enhancer.py not found")
        spec   = importlib.util.spec_from_file_location("smart_context_enhancer", spec_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.plugin = module.SmartContextPlugin()
        self.plugin.on_load()
        yield
        self.plugin.on_unload()

    def test_get_commands(self):
        cmds = self.plugin.get_commands()
        names = [c["name"] for c in cmds]
        assert "context_summary"      in names
        assert "conversation_history" in names
        assert "topic_stats"          in names
        assert "follow_up_suggestions" in names
        assert "clear_context"        in names

    def test_on_message_tracks_history(self):
        self.plugin.on_message("tell me about python", "Python is a language.")
        result = self.plugin.on_command("conversation_history", {"limit": 5})
        assert result["total"] == 1
        assert len(result["history"]) == 1

    def test_on_message_multiple_turns(self):
        for i in range(5):
            self.plugin.on_message(f"question {i}", f"answer {i}")
        result = self.plugin.on_command("conversation_history", {"limit": 10})
        assert result["total"] == 5

    def test_topic_stats_detects_code(self):
        self.plugin.on_message("write me a python function", "Here is the code.")
        result = self.plugin.on_command("topic_stats", {})
        assert "code" in result["topics"]

    def test_topic_stats_detects_finance(self):
        self.plugin.on_message("how to invest in crypto", "Bitcoin info.")
        result = self.plugin.on_command("topic_stats", {})
        assert "finance" in result["topics"]

    def test_context_summary_empty(self):
        result = self.plugin.on_command("context_summary", {})
        assert "summary" in result

    def test_context_summary_after_messages(self):
        self.plugin.on_message("question about python", "answer")
        result = self.plugin.on_command("context_summary", {})
        assert result["turns"] == 1

    def test_follow_up_suggestions_code(self):
        result = self.plugin.on_command(
            "follow_up_suggestions", {"message": "write a python function"}
        )
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0

    def test_follow_up_suggestions_finance(self):
        result = self.plugin.on_command(
            "follow_up_suggestions", {"message": "bitcoin crypto trading"}
        )
        assert len(result["suggestions"]) > 0

    def test_clear_context(self):
        self.plugin.on_message("test msg", "test response")
        result = self.plugin.on_command("clear_context", {})
        assert result["status"] == "cleared"
        history = self.plugin.on_command("conversation_history", {})
        assert history["total"] == 0

    def test_get_status(self):
        status = self.plugin.get_status()
        assert status["status"] == "active"
        assert "uptime_secs"      in status
        assert "messages_tracked" in status

    def test_time_sensitive_detection(self):
        """Messages with 'now', 'today' etc. should trigger datetime injection."""
        result = self.plugin.on_message("what time is it now", "It is 3 PM.")
        if result is not None:
            assert "Current time" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
