"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS OS — COMPLETE ROOT-LEVEL TEST SUITE
  Tests that run from project root (not backend/).
  Covers: fallback error handler, desktop launcher checks,
  config validation, environment setup.
  Run: python -m pytest tests/ -v
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import pytest
from pathlib import Path

# Add both root and backend to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


# ══════════════════════════════════════════════════════════════════════════════
#  FALLBACK ERROR HANDLER
# ══════════════════════════════════════════════════════════════════════════════

class TestFallbackErrorHandlerRoot:

    def test_handler_loads(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        assert handler is not None

    def test_handle_error_returns_handled(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        result = handler.handle_error(Exception("Test error"), {"context": "test"})
        assert result["status"] == "handled"
        assert "recovery_action" in result
        assert "next_steps" in result

    def test_handle_error_basic_logging_in_recovery(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        result = handler.handle_error(Exception("Test error"), {"context": "test"})
        assert "basic_error_logging" in result["recovery_action"]

    def test_next_steps_contain_check_logs(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        result = handler.handle_error(Exception("Test error"), {"context": "test"})
        assert "Check system logs" in result["next_steps"]

    def test_handles_various_exception_types(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        for exc in [ValueError("bad"), TypeError("type"), RuntimeError("rt"), MemoryError("mem")]:
            result = handler.handle_error(exc, {})
            assert result["status"] == "handled"


# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT STRUCTURE VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestProjectStructure:
    """Validate that all critical project files and directories exist."""

    ROOT = Path(__file__).parent.parent

    def test_backend_main_exists(self):
        assert (self.ROOT / "backend" / "main.py").exists()

    def test_frontend_package_json_exists(self):
        assert (self.ROOT / "frontend" / "package.json").exists()

    def test_requirements_txt_exists(self):
        assert (self.ROOT / "requirements.txt").exists()

    def test_env_example_exists(self):
        assert (self.ROOT / ".env.example").exists()

    def test_gitignore_exists(self):
        assert (self.ROOT / ".gitignore").exists()

    def test_docker_compose_exists(self):
        assert (self.ROOT / "docker-compose.yml").exists()

    def test_backend_app_directory_exists(self):
        assert (self.ROOT / "backend" / "app").is_dir()

    def test_core_modules_directory_exists(self):
        assert (self.ROOT / "backend" / "app" / "core").is_dir()

    def test_api_routes_directory_exists(self):
        assert (self.ROOT / "backend" / "app" / "api").is_dir()

    def test_memory_modules_directory_exists(self):
        assert (self.ROOT / "backend" / "app" / "memory").is_dir()

    def test_plugins_directory_exists(self):
        assert (self.ROOT / "backend" / "plugins").is_dir()

    def test_assets_directory_exists(self):
        assert (self.ROOT / "assets").is_dir()

    def test_igris_icon_exists(self):
        assert (self.ROOT / "assets" / "igris_icon.png").exists()

    def test_version_info_exists(self):
        assert (self.ROOT / "version_info.txt").exists()

    def test_igris_spec_exists(self):
        assert (self.ROOT / "igris.spec").exists()

    def test_production_plugins_exist(self):
        plugins_dir = self.ROOT / "backend" / "plugins"
        plugin_files = [f.name for f in plugins_dir.glob("*.py") if not f.name.startswith("_")]
        assert len(plugin_files) >= 3, f"Expected at least 3 plugins, found: {plugin_files}"

    def test_ai_core_file_exists(self):
        assert (self.ROOT / "backend" / "app" / "core" / "ai_core.py").exists()

    def test_daemon_master_file_exists(self):
        assert (self.ROOT / "backend" / "app" / "core" / "daemon_master.py").exists()

    def test_frontend_src_exists(self):
        assert (self.ROOT / "frontend" / "src").is_dir()

    def test_frontend_app_tsx_exists(self):
        assert (self.ROOT / "frontend" / "src" / "App.tsx").exists()

    def test_frontend_index_css_exists(self):
        assert (self.ROOT / "frontend" / "src" / "index.css").exists()


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigValidation:
    """Validate config_igris.json structure and contents."""

    ROOT = Path(__file__).parent.parent

    @pytest.fixture(autouse=True)
    def load_config(self):
        config_path = self.ROOT / "backend" / "config_igris.json"
        with open(config_path, encoding="utf-8") as f:
            self.config = json.load(f)

    def test_config_has_bot_settings(self):
        assert "bot_settings" in self.config

    def test_bot_name_is_igris(self):
        assert self.config["bot_settings"]["name"] == "Igris"

    def test_bot_version_set(self):
        assert "version" in self.config["bot_settings"]

    def test_config_has_voice_control(self):
        assert "voice_control" in self.config

    def test_voice_language_includes_urdu(self):
        lang = self.config["voice_control"].get("language_default", "")
        assert "ur" in lang or "PK" in lang

    def test_config_has_commands(self):
        assert "commands" in self.config
        assert "core_commands" in self.config["commands"]

    def test_commands_have_required_fields(self):
        for cmd in self.config["commands"]["core_commands"]:
            assert "pattern"  in cmd
            assert "command"  in cmd
            assert "priority" in cmd

    def test_config_has_responses(self):
        assert "responses" in self.config
        responses = self.config["responses"]
        assert "success" in responses
        assert "error"   in responses

    def test_config_has_logging(self):
        assert "logging" in self.config
        assert "level" in self.config["logging"]


# ══════════════════════════════════════════════════════════════════════════════
#  REQUIREMENTS VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestRequirementsValidation:
    """Validate that requirements.txt contains all critical packages."""

    ROOT = Path(__file__).parent.parent

    @pytest.fixture(autouse=True)
    def load_requirements(self):
        req_path = self.ROOT / "requirements.txt"
        content = req_path.read_text(encoding="utf-8")
        # Parse package names (ignore comments and version specifiers)
        self.packages = set()
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                pkg = line.split(">=")[0].split("==")[0].split("[")[0].strip().lower()
                self.packages.add(pkg)

    def test_fastapi_present(self):         assert "fastapi" in self.packages
    def test_uvicorn_present(self):         assert "uvicorn" in self.packages
    def test_pydantic_present(self):        assert "pydantic" in self.packages
    def test_psutil_present(self):          assert "psutil" in self.packages
    def test_openai_present(self):          assert "openai" in self.packages
    def test_speech_recognition_present(self):
        assert "speechrecognition" in self.packages
    def test_pyautogui_present(self):       assert "pyautogui" in self.packages
    def test_ccxt_present(self):            assert "ccxt" in self.packages
    def test_chromadb_present(self):        assert "chromadb" in self.packages
    def test_pytest_present(self):          assert "pytest" in self.packages
    def test_bcrypt_present(self):          assert "bcrypt" in self.packages
    def test_cryptography_present(self):    assert "cryptography" in self.packages
    def test_pillow_present(self):          assert "pillow" in self.packages
    def test_httpx_present(self):           assert "httpx" in self.packages


# ══════════════════════════════════════════════════════════════════════════════
#  ENV EXAMPLE VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestEnvExampleValidation:
    """Validate that .env.example has all required variable placeholders."""

    ROOT = Path(__file__).parent.parent

    @pytest.fixture(autouse=True)
    def load_env(self):
        env_path = self.ROOT / ".env.example"
        self.content = env_path.read_text(encoding="utf-8")

    def test_has_groq_api_key(self):      assert "GROQ_API_KEY"      in self.content
    def test_has_hf_api_key(self):        assert "HF_API_KEY"        in self.content
    def test_has_database_url(self):      assert "DATABASE_URL"      in self.content
    def test_has_secret_key(self):        assert "SECRET_KEY"        in self.content
    def test_has_api_port(self):          assert "API_PORT"          in self.content
    def test_has_voice_languages(self):   assert "VOICE_LANGUAGES"   in self.content
    def test_has_enable_monitoring(self): assert "ENABLE_MONITORING" in self.content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])