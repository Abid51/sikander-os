"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS OS — COMPLETE BACKEND TEST SUITE
  Run with:  python -m pytest tests/ -v
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import math
import os
import sys
import time
import uuid
import asyncio

import pytest

# ─── allow imports from backend root ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════════════
#  NEURAL MEMORY TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestNeuralMemory:
    """Tests for app/memory/vector_memory.py"""

    @pytest.fixture(autouse=True)
    def fresh_memory(self, tmp_path):
        from app.memory.vector_memory import IgrisNeuralMemory
        self.mem = IgrisNeuralMemory(persist_path=str(tmp_path / "test_mem.json"))

    def test_remember_returns_record(self):
        rec = self.mem.remember("The sky is blue", memory_type="semantic")
        assert rec.id is not None
        assert rec.content == "The sky is blue"
        assert rec.memory_type == "semantic"
        assert 0 <= rec.importance <= 1

    def test_recall_finds_similar(self):
        self.mem.remember("Python is a programming language", memory_type="semantic", importance=0.9)
        self.mem.remember("The weather is sunny today",       memory_type="episodic")
        results = self.mem.recall("coding language Python", top_k=3)
        assert len(results) > 0
        top_content = results[0][0].content
        assert "Python" in top_content or "programming" in top_content

    def test_recall_by_type_filter(self):
        self.mem.remember("procedural memory A", memory_type="procedural")
        self.mem.remember("semantic memory B",   memory_type="semantic")
        proc = self.mem.recall("memory", top_k=5, memory_type="procedural")
        for rec, _ in proc:
            assert rec.memory_type == "procedural"

    def test_forget_removes_record(self):
        rec = self.mem.remember("to be forgotten")
        assert self.mem.forget(rec.id) is True
        results = self.mem.recall("to be forgotten")
        assert all(r.id != rec.id for r, _ in results)

    def test_forget_nonexistent_returns_false(self):
        assert self.mem.forget("nonexistent-id-xyz") is False

    def test_link_memories(self):
        a = self.mem.remember("memory A")
        b = self.mem.remember("memory B")
        assert self.mem.link_memories(a.id, b.id, relation="sibling", strength=0.8) is True
        links = self.mem.get_linked_memories(a.id)
        assert any(lnk["id"] == b.id for lnk in links)

    def test_link_with_invalid_ids(self):
        a = self.mem.remember("valid memory")
        assert self.mem.link_memories(a.id, "bad-id") is False

    def test_get_all_by_type(self):
        self.mem.remember("w1", memory_type="working")
        self.mem.remember("w2", memory_type="working")
        self.mem.remember("s1", memory_type="semantic")
        working = self.mem.get_all_by_type("working")
        assert len(working) >= 2
        for r in working:
            assert r.memory_type == "working"

    def test_stats_structure(self):
        self.mem.remember("test")
        stats = self.mem.get_stats()
        assert "total_memories" in stats
        assert "by_type" in stats
        assert "total_links" in stats
        assert "embedding_dim" in stats

    def test_persistence(self, tmp_path):
        from app.memory.vector_memory import IgrisNeuralMemory
        p = str(tmp_path / "persist_test.json")
        m1 = IgrisNeuralMemory(persist_path=p)
        rec = m1.remember("persistent memory", importance=0.8)
        rid = rec.id

        # Load fresh instance from same file
        m2 = IgrisNeuralMemory(persist_path=p)
        assert rid in m2._records
        assert m2._records[rid].content == "persistent memory"

    def test_export(self, tmp_path):
        self.mem.remember("export me")
        out = str(tmp_path / "export.json")
        msg = self.mem.export_memories(out)
        assert os.path.exists(out)
        with open(out) as f:
            data = json.load(f)
        assert "records" in data


# ══════════════════════════════════════════════════════════════════════════════
#  TOOLS TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculator:
    """Tests for CalculatorTool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.tools.igris_tools import CalculatorTool
        self.calc = CalculatorTool()

    def test_basic_arithmetic(self):
        r = self.calc.evaluate("2 + 3 * 4")
        assert r["error"] is None
        assert r["result"] == 14

    def test_float_division(self):
        r = self.calc.evaluate("10 / 3")
        assert r["error"] is None
        assert abs(r["result"] - 3.333) < 0.01

    def test_power(self):
        r = self.calc.evaluate("2^10")
        assert r["error"] is None
        assert r["result"] == 1024

    def test_math_functions(self):
        r = self.calc.evaluate("sqrt(144)")
        assert r["error"] is None
        assert r["result"] == 12.0

    def test_pi(self):
        r = self.calc.evaluate("pi * 2")
        assert r["error"] is None
        assert abs(r["result"] - 6.283) < 0.01

    def test_invalid_expression(self):
        r = self.calc.evaluate("import os")
        # Should either eval to error or strip the offending part
        assert r is not None   # should not crash

    def test_parentheses(self):
        r = self.calc.evaluate("(3 + 7) * (10 - 5)")
        assert r["error"] is None
        assert r["result"] == 50


class TestPythonSandbox:
    """Tests for PythonSandboxTool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.tools.igris_tools import PythonSandboxTool
        self.sb = PythonSandboxTool()

    def test_hello_world(self):
        r = self.sb.run('print("hello world")')
        assert r["exit_code"] == 0
        assert "hello world" in r["stdout"]

    def test_math_output(self):
        r = self.sb.run("print(2 ** 32)")
        assert "4294967296" in r["stdout"]

    def test_stderr_capture(self):
        r = self.sb.run("raise ValueError('test error')")
        assert r["exit_code"] != 0
        assert "ValueError" in r["stderr"]

    def test_multiline_code(self):
        code = "result = sum(range(101))\nprint(result)"
        r = self.sb.run(code)
        assert "5050" in r["stdout"]

    def test_timeout_flag(self):
        # 1s timeout override would be needed; just check structure
        r = self.sb.run("x = 1 + 1\nprint(x)")
        assert "timed_out" in r


class TestFileManager:
    """Tests for FileManagerTool."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from app.tools.igris_tools import FileManagerTool
        self.fm = FileManagerTool(root=str(tmp_path))
        self.root = tmp_path

    def test_write_and_read(self):
        w = self.fm.write_file("hello.txt", "hello igris")
        assert w["status"] == "ok"
        r = self.fm.read_file("hello.txt")
        assert r["content"] == "hello igris"

    def test_append_mode(self):
        self.fm.write_file("append.txt", "line1\n")
        self.fm.write_file("append.txt", "line2\n", append=True)
        r = self.fm.read_file("append.txt")
        assert "line1" in r["content"]
        assert "line2" in r["content"]

    def test_list_dir(self):
        self.fm.write_file("a.txt", "a")
        self.fm.write_file("b.txt", "b")
        result = self.fm.list_dir()
        names = [e["name"] for e in result["entries"]]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_path_traversal_blocked(self):
        with pytest.raises(PermissionError):
            self.fm.read_file("../../etc/passwd")

    def test_search_files(self):
        self.fm.write_file("code.py", "def igris_function():\n    pass\n")
        result = self.fm.search_files("igris_function")
        assert len(result["matches"]) > 0
        assert result["matches"][0]["file"].endswith("code.py")

    def test_read_nonexistent_file(self):
        r = self.fm.read_file("does_not_exist.txt")
        assert "error" in r


class TestDataTransformer:
    """Tests for DataTransformerTool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.tools.igris_tools import DataTransformerTool
        self.dt = DataTransformerTool()

    def test_parse_valid_json(self):
        r = self.dt.parse_json('{"name": "igris", "power": 9000}')
        assert r["error"] is None
        assert r["data"]["name"] == "igris"

    def test_parse_invalid_json(self):
        r = self.dt.parse_json("{bad json}")
        assert r["error"] is not None

    def test_flatten(self):
        nested = {"a": {"b": {"c": 42}}}
        flat = self.dt.flatten(nested)
        assert flat["a.b.c"] == 42

    def test_summarise_numeric(self):
        data = [{"val": i} for i in range(1, 11)]
        stats = self.dt.summarise(data)
        assert stats["count"] == 10
        assert stats["fields"]["val"]["min"] == 1.0
        assert stats["fields"]["val"]["max"] == 10.0
        assert stats["fields"]["val"]["mean"] == 5.5

    def test_summarise_empty(self):
        r = self.dt.summarise([])
        assert "error" in r


class TestToolRegistry:
    """Tests for IgrisToolRegistry dispatch."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.tools.igris_tools import IgrisToolRegistry
        self.reg = IgrisToolRegistry()

    def test_available_tools_list(self):
        tools = self.reg.available_tools()
        names = [t["name"] for t in tools]
        assert "web_search"   in names
        assert "calculate"    in names
        assert "run_python"   in names
        assert "system_info"  in names

    def test_run_calculate(self):
        r = self.reg.run("calculate", expression="7 * 6")
        assert r["result"] == 42

    def test_run_unknown_tool(self):
        r = self.reg.run("nonexistent_tool_xyz")
        assert "error" in r

    def test_system_info_structure(self):
        r = self.reg.run("system_info")
        assert "cpu_percent" in r
        assert "memory_percent" in r


# ══════════════════════════════════════════════════════════════════════════════
#  LLM MANAGER TESTS  (no actual API calls)
# ══════════════════════════════════════════════════════════════════════════════

class TestLLMManager:
    """Tests for app/core/llm_manager.py — offline/config tests only."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        # Redirect config file to tmp
        import app.core.llm_manager as lm_mod
        monkeypatch.chdir(tmp_path)
        from app.core.llm_manager import LLMManager
        self.mgr = LLMManager()

    def test_default_provider(self):
        assert self.mgr.config["active_provider"] in ("ollama", "openai", "anthropic", "gemini", "groq")

    def test_set_active_model_valid(self):
        self.mgr.set_active_model("openai", "gpt-4")
        assert self.mgr.config["active_provider"] == "openai"
        assert self.mgr.config["active_model"] == "gpt-4"

    def test_set_active_model_invalid(self):
        with pytest.raises(ValueError):
            self.mgr.set_active_model("nonexistent_provider", "model")

    def test_set_api_key(self):
        self.mgr.set_api_key("openai", "sk-test-key")
        assert self.mgr.config["providers"]["openai"]["api_key"] == "sk-test-key"

    def test_set_api_key_invalid_provider(self):
        with pytest.raises(ValueError):
            self.mgr.set_api_key("unknown_prov", "key")

    def test_get_safe_config_masks_keys(self):
        self.mgr.set_api_key("openai", "sk-secret")
        safe = self.mgr.get_safe_config()
        for prov in safe["providers"].values():
            assert "api_key" not in prov

    def test_stats_structure(self):
        stats = self.mgr.get_stats()
        assert "total_calls"      in stats
        assert "successful_calls" in stats
        assert "success_rate"     in stats

    def test_build_messages(self):
        from app.core.llm_manager import LLMManager
        msgs = LLMManager._build_messages("sys", "hi", history=[
            {"role": "assistant", "content": "hello"}
        ])
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"


# ══════════════════════════════════════════════════════════════════════════════
#  EMBEDDING ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestEmbeddingEngine:
    """Tests for the internal _EmbeddingEngine used by NeuralMemory."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.memory.vector_memory import _EmbeddingEngine
        self.eng = _EmbeddingEngine()

    def test_encode_returns_128_dims(self):
        vec = self.eng.encode("hello world")
        assert len(vec) == 128

    def test_encode_is_normalised(self):
        vec = self.eng.encode("some text here")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-5

    def test_same_text_same_vector(self):
        v1 = self.eng.encode("deterministic test")
        v2 = self.eng.encode("deterministic test")
        assert v1 == v2

    def test_different_texts_different_vectors(self):
        from app.memory.vector_memory import _EmbeddingEngine
        v1 = self.eng.encode("Python programming language")
        v2 = self.eng.encode("grilled chicken sandwich")
        sim = _EmbeddingEngine.cosine(v1, v2)
        assert sim < 0.95  # should not be identical

    def test_similar_texts_higher_cosine(self):
        from app.memory.vector_memory import _EmbeddingEngine
        v_a = self.eng.encode("machine learning neural network")
        v_b = self.eng.encode("deep learning neural nets")
        v_c = self.eng.encode("grilled chicken recipe dinner")
        sim_ab = _EmbeddingEngine.cosine(v_a, v_b)
        sim_ac = _EmbeddingEngine.cosine(v_a, v_c)
        assert sim_ab > sim_ac, "Similar texts should score higher than unrelated ones"

    def test_empty_string(self):
        vec = self.eng.encode("")
        assert len(vec) == 128
        assert all(v == 0.0 for v in vec)

    def test_cosine_self_similarity(self):
        from app.memory.vector_memory import _EmbeddingEngine
        v = self.eng.encode("igris supreme AI")
        sim = _EmbeddingEngine.cosine(v, v)
        assert abs(sim - 1.0) < 1e-5


# ══════════════════════════════════════════════════════════════════════════════
#  FAST API INTEGRATION — smoke tests (no real db/daemons)
# ══════════════════════════════════════════════════════════════════════════════

class TestToolsAPIRoutes:
    """Smoke tests for /tools/* endpoints using FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def client(self):
        try:
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from app.api.tools_routes import router
            app = FastAPI()
            app.include_router(router)
            self.client = TestClient(app)
        except Exception:
            pytest.skip("FastAPI TestClient unavailable")

    def test_list_tools(self):
        r = self.client.get("/tools/list")
        assert r.status_code == 200
        data = r.json()
        assert "tools" in data
        assert len(data["tools"]) > 0

    def test_calculate_endpoint(self):
        r = self.client.post("/tools/calculate", json={"expression": "100 / 4"})
        assert r.status_code == 200
        assert r.json()["result"] == 25.0

    def test_calculate_bad_expression(self):
        r = self.client.post("/tools/calculate", json={"expression": "!!bad!!"})
        # Should return 400 or result with None
        assert r.status_code in (200, 400)

    def test_run_python(self, monkeypatch):
        monkeypatch.setenv("IGRIS_API_TOKEN", "secret")
        r = self.client.post(
            "/tools/code/run",
            headers={"x-igris-token": "secret"},
            json={"code": "print('igris test')"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "igris test" in body.get("stdout", "")

    def test_system_info_endpoint(self):
        r = self.client.get("/tools/system/info")
        assert r.status_code == 200
        body = r.json()
        assert "cpu_percent" in body

    def test_generic_run_tool(self, monkeypatch):
        monkeypatch.setenv("IGRIS_API_TOKEN", "secret")
        r = self.client.post("/tools/run", headers={"x-igris-token": "secret"}, json={
            "tool_name": "calculate",
            "kwargs": {"expression": "9 * 9"}
        })
        assert r.status_code == 200
        assert r.json()["result"]["result"] == 81


class TestVoiceModifyGuards:
    """Security checks for self-modification voice endpoints."""

    @pytest.fixture(autouse=True)
    def client(self):
        from fastapi import FastAPI
        from app.api.voice_routes import router
        try:
            from fastapi.testclient import TestClient
            app = FastAPI()
            app.include_router(router)
            self.client = TestClient(app)
        except Exception:
            pytest.skip("FastAPI TestClient unavailable")

    def test_modify_function_denied_without_token_mode(self):

        r = self.client.post(
            "/api/voice/modify/function",
            json={
                "module_name": "app.core.ai_core",
                "function_name": "x",
                "new_logic": "def x():\n    return 1\n",
            },
        )
        assert r.status_code == 403

    def test_modify_function_denied_without_admin_role(self, monkeypatch):
        monkeypatch.setenv("IGRIS_API_TOKEN", "secret")

        r = self.client.post(
            "/api/voice/modify/function",
            headers={"x-igris-token": "secret", "x-igris-role": "user"},
            json={
                "module_name": "app.core.ai_core",
                "function_name": "x",
                "new_logic": "def x():\n    return 1\n",
            },
        )
        assert r.status_code == 403

    def test_process_command_requires_typed_payload(self):
        r = self.client.post("/api/voice/process-command", json={"language": "ur-PK"})
        assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
#  BACKEND ENHANCEMENT REGRESSION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestBackendEnhancements:
    """Regression tests for recently enhanced backend behaviors."""

    def test_economic_engine_validates_invalid_side(self):
        from app.agents.economic_engine import EconomicEngine
        eng = EconomicEngine(live_mode=False)
        out = eng.paper_trade("BTC/USDT", "hold", 100)
        assert "error" in out
        assert "buy" in out["error"].lower() and "sell" in out["error"].lower()

    def test_economic_engine_exposes_streams(self):
        from app.agents.economic_engine import EconomicEngine
        eng = EconomicEngine(live_mode=False)
        streams = eng.list_streams()
        assert isinstance(streams, dict)
        assert len(streams) > 0
        assert "Social Media Creator" in streams
        assert "Freelance Services" in streams

    def test_daemon_emit_event_queues_payload(self):
        from app.core.daemon_master import DaemonMaster
        master = DaemonMaster()
        result = asyncio.run(master.emit_event("broadcast", "noop", {"k": "v"}))
        assert result["status"] == "queued"
        queued = master.event_bus.get_nowait()
        assert queued["target"] == "broadcast"
        assert queued["command"] == "noop"

    def test_economic_engine_records_income(self):
        from app.agents.economic_engine import EconomicEngine
        eng = EconomicEngine(live_mode=False)
        result = eng.record_income(
            stream_name="Freelance Services",
            amount_usd=250.0,
            source="Upwork",
            notes="Landing page job",
            metadata={"client": "demo"},
        )
        assert result["status"] == "recorded"
        summary = eng.get_income_summary()
        assert summary["total_income_usd"] >= 250.0
        assert summary["by_stream"].get("Freelance Services", 0) >= 250.0


class TestSelfModificationEnhanced:
    """Safety and tracking tests for self modification engine."""

    def test_modify_function_blocks_unsafe_code(self):
        from app.core.self_modification import SelfModificationSystem
        sm = SelfModificationSystem()
        out = sm.modify_function(
            "app.core.ai_core",
            "run",
            "def run():\n    os.system('dir')\n",
        )
        assert out["status"] == "error"
        assert out["error_code"] == "UNSAFE_CODE"

    def test_modify_function_requires_target_function_in_file(self, tmp_path):
        from app.core.self_modification import SelfModificationSystem
        sm = SelfModificationSystem()
        sm.system_root = str(tmp_path)
        sm.allowed_modules = ["app.core.ai_core"]

        module_file = tmp_path / "app" / "core" / "ai_core.py"
        module_file.parent.mkdir(parents=True, exist_ok=True)
        module_file.write_text("def another_function():\n    return 1\n", encoding="utf-8")

        out = sm.modify_function(
            "app.core.ai_core",
            "target_function",
            "def target_function():\n    return 2\n",
        )
        assert out["status"] == "error"
        assert out["error_code"] == "FUNCTION_NOT_FOUND"

    def test_modify_parameter_tracks_old_value(self, tmp_path):
        from app.core.self_modification import SelfModificationSystem
        sm = SelfModificationSystem()
        sm.system_root = str(tmp_path)
        first = sm.modify_parameter("igris_test", "temperature", 0.2)
        assert first["status"] == "success"
        second = sm.modify_parameter("igris_test", "temperature", 0.8)
        assert second["status"] == "success"
        last = sm.get_modification_history()[-1]
        assert last["old_value"] == 0.2
        assert last["new_value"] == 0.8


# ══════════════════════════════════════════════════════════════════════════════
#  RUN DIRECTLY
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
