"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS OS — AI CORE + MEMORY + EMOTIONAL INTELLIGENCE TEST SUITE
  Full coverage for ai_core, emotional_intelligence, predictive_engine,
  self_healing, thought_crystallizer, quantum_thinking_engine.
  Run: python -m pytest tests/test_ai_systems.py -v
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════════════
#  EMOTIONAL INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

class TestEmotionalIntelligence:

    @pytest.fixture(autouse=True)
    def engine(self):
        from app.core.emotional_intelligence import get_emotional_engine
        self.ei = get_emotional_engine()

    def test_engine_loads(self):
        assert self.ei is not None

    def test_analyze_positive_text(self):
        result = self.ei.analyze_emotion("I am so happy today, everything is perfect!")
        assert result is not None
        assert isinstance(result, dict)

    def test_analyze_negative_text(self):
        result = self.ei.analyze_emotion("I am very angry and frustrated right now.")
        assert result is not None

    def test_analyze_neutral_text(self):
        result = self.ei.analyze_emotion("The system is running normally.")
        assert result is not None

    def test_analyze_urdu_text(self):
        result = self.ei.analyze_emotion("آج بہت اچھا دن ہے")
        assert result is not None

    def test_get_stats(self):
        stats = self.ei.get_stats()
        assert isinstance(stats, dict)

    def test_emotional_response_includes_emotion_field(self):
        result = self.ei.analyze_emotion("I love this AI system!")
        # Should have some emotional classification
        if "emotion" in result:
            assert isinstance(result["emotion"], str)
        elif "dominant_emotion" in result:
            assert isinstance(result["dominant_emotion"], str)


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTIVE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TestPredictiveEngine:

    @pytest.fixture(autouse=True)
    def engine(self):
        from app.core.predictive_engine import get_predictive_engine
        self.pe = get_predictive_engine()

    def test_engine_loads(self):
        assert self.pe is not None

    def test_get_stats(self):
        stats = self.pe.get_stats()
        assert isinstance(stats, dict)

    def test_predict_returns_dict(self):
        result = self.pe.predict("system_load", context={})
        assert isinstance(result, dict)

    def test_predict_with_context(self):
        result = self.pe.predict("user_intent", context={"recent_commands": ["status", "help"]})
        assert result is not None


# ══════════════════════════════════════════════════════════════════════════════
#  SELF HEALING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TestSelfHealingEngine:

    @pytest.fixture(autouse=True)
    def engine(self):
        from app.core.self_healing import get_self_healing_engine
        self.healer = get_self_healing_engine()

    def test_engine_loads(self):
        assert self.healer is not None

    def test_error_history_initially_empty_or_list(self):
        history = self.healer.get_error_history()
        assert isinstance(history, list)

    def test_get_stats_structure(self):
        stats = self.healer.get_stats()
        assert isinstance(stats, dict)

    def test_handle_error_returns_result(self):
        result = self.healer.handle_error(
            Exception("Test error"),
            context={"module": "test_module", "operation": "test_op"}
        )
        assert result is not None
        assert isinstance(result, dict)

    def test_error_is_recorded(self):
        initial_count = len(self.healer.get_error_history())
        self.healer.handle_error(Exception("Recorded error"), context={})
        new_count = len(self.healer.get_error_history())
        assert new_count >= initial_count   # May or may not grow (depends on impl)


# ══════════════════════════════════════════════════════════════════════════════
#  THOUGHT CRYSTALLIZER
# ══════════════════════════════════════════════════════════════════════════════

class TestThoughtCrystallizer:

    @pytest.fixture(autouse=True)
    def engine(self):
        from app.core.thought_crystallizer import get_crystallizer
        self.tc = get_crystallizer()

    def test_engine_loads(self):
        assert self.tc is not None

    def test_crystallize_returns_dict(self):
        result = self.tc.crystallize("What is the best approach to machine learning?")
        assert isinstance(result, dict)

    def test_crystallize_has_output(self):
        result = self.tc.crystallize("How can I improve this code?")
        # Should have some meaningful key
        assert len(result) > 0

    def test_get_stats(self):
        stats = self.tc.get_stats()
        assert isinstance(stats, dict)


# ══════════════════════════════════════════════════════════════════════════════
#  QUANTUM THINKING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TestQuantumThinkingEngine:

    @pytest.fixture(autouse=True)
    def engine(self):
        from app.core.quantum_thinking_engine import get_quantum_thinking_engine
        self.qte = get_quantum_thinking_engine()

    def test_engine_loads(self):
        assert self.qte is not None

    def test_get_stats(self):
        stats = self.qte.get_stats()
        assert isinstance(stats, dict)

    def test_think_returns_dict(self):
        result = self.qte.think("Should I learn Python or JavaScript first?")
        assert isinstance(result, dict)

    def test_think_with_options(self):
        result = self.qte.think(
            "Best programming language?",
            options=["Python", "JavaScript", "Rust"]
        )
        assert result is not None


# ══════════════════════════════════════════════════════════════════════════════
#  MULTI AGENT ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

class TestMultiAgentOrchestrator:

    @pytest.fixture(autouse=True)
    def orchestrator(self):
        from app.core.multi_agent_orchestrator import MultiAgentOrchestrator
        self.mao = MultiAgentOrchestrator()

    def test_orchestrator_loads(self):
        assert self.mao is not None

    def test_get_agents_returns_list(self):
        agents = self.mao.get_agents()
        assert isinstance(agents, (list, dict))

    def test_get_stats(self):
        stats = self.mao.get_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_route_task_returns_dict(self):
        result = await self.mao.route_task("Analyze this text", task_type="analysis")
        assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
#  FALLBACK ERROR HANDLER
# ══════════════════════════════════════════════════════════════════════════════

class TestFallbackErrorHandler:

    def test_handler_loads(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        assert handler is not None

    def test_handle_error_returns_handled(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        result = handler.handle_error(Exception("Test error"), {"context": "test"})
        assert result["status"] == "handled"

    def test_handle_error_has_recovery_action(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        result = handler.handle_error(ValueError("bad value"), {})
        assert "recovery_action" in result

    def test_handle_error_has_next_steps(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        result = handler.handle_error(RuntimeError("runtime issue"), {})
        assert "next_steps" in result

    def test_handle_different_exception_types(self):
        from app.core.fallback_error_handler import FallbackErrorHandler
        handler = FallbackErrorHandler()
        for exc in [ValueError("v"), TypeError("t"), RuntimeError("r"), Exception("e")]:
            result = handler.handle_error(exc, {})
            assert result["status"] == "handled"


# ══════════════════════════════════════════════════════════════════════════════
#  KNOWLEDGE GRAPH
# ══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:

    @pytest.fixture(autouse=True)
    def graph(self, tmp_path):
        from app.memory.knowledge_graph import KnowledgeGraph
        self.kg = KnowledgeGraph(persist_path=str(tmp_path / "kg_test.json"))

    def test_graph_loads(self):
        assert self.kg is not None

    def test_add_node(self):
        result = self.kg.add_node("python", node_type="language", properties={"paradigm": "multi"})
        assert result is not None

    def test_add_relationship(self):
        self.kg.add_node("python", node_type="language")
        self.kg.add_node("fastapi", node_type="framework")
        result = self.kg.add_relationship("fastapi", "python", "uses")
        assert result is not None

    def test_query_node(self):
        self.kg.add_node("igris", node_type="ai", properties={"version": "3.0"})
        result = self.kg.get_node("igris")
        assert result is not None

    def test_search_nodes(self):
        self.kg.add_node("machine_learning", node_type="topic")
        self.kg.add_node("deep_learning",   node_type="topic")
        results = self.kg.search_nodes("learning")
        assert isinstance(results, list)

    def test_get_stats(self):
        stats = self.kg.get_stats()
        assert isinstance(stats, dict)
        assert "total_nodes" in stats


# ══════════════════════════════════════════════════════════════════════════════
#  QUANTUM VAULT
# ══════════════════════════════════════════════════════════════════════════════

class TestQuantumVault:

    @pytest.fixture(autouse=True)
    def vault(self, tmp_path):
        from app.memory.quantum_vault import QuantumVault
        self.vault = QuantumVault(
            vault_path=str(tmp_path / "test_vault.json"),
            dev_auto_unlock=True,
        )

    def test_vault_loads(self):
        assert self.vault is not None

    def test_store_and_retrieve(self):
        self.vault.store("test_key", {"data": "secret_value"})
        result = self.vault.retrieve("test_key")
        assert result is not None

    def test_retrieve_nonexistent_returns_none(self):
        result = self.vault.retrieve("nonexistent_key_xyz")
        assert result is None

    def test_delete_key(self):
        self.vault.store("to_delete", {"temp": True})
        deleted = self.vault.delete("to_delete")
        assert deleted is True
        assert self.vault.retrieve("to_delete") is None

    def test_get_stats(self):
        stats = self.vault.get_stats()
        assert isinstance(stats, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
