"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS CLOUD AI — Thin wrapper bridging voice_routes to LLM Manager
  Provides the cloud_ai singleton expected by voice_routes.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import time
import hashlib
from typing import Any, Dict, List, Optional
from collections import OrderedDict

from app.core.llm_manager import universal_llm


# ─────────────────────────────────────────────────────────────────────────────
#  ADVANCED CACHE — LRU + TTL for repeated prompts
# ─────────────────────────────────────────────────────────────────────────────

class AdvancedCache:
    """LRU-based response cache with TTL expiry."""

    def __init__(self, max_size: int = 200, ttl: int = 600) -> None:
        self._store: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl           # seconds
        self._hits = 0
        self._misses = 0

    def _key(self, prompt: str) -> str:
        return hashlib.md5(prompt.encode()).hexdigest()

    def get(self, prompt: str) -> Optional[str]:
        k = self._key(prompt)
        entry = self._store.get(k)
        if entry and time.time() - entry["ts"] < self._ttl:
            self._hits += 1
            self._store.move_to_end(k)
            return entry["value"]
        if entry:
            del self._store[k]
        self._misses += 1
        return None

    def put(self, prompt: str, response: str) -> None:
        k = self._key(prompt)
        self._store[k] = {"value": response, "ts": time.time()}
        self._store.move_to_end(k)
        if len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits":      self._hits,
            "misses":    self._misses,
            "hit_rate":  round(self._hits / total * 100, 1) if total else 0.0,
            "entries":   len(self._store),
            "max_size":  self._max_size,
            "ttl_secs":  self._ttl,
        }

    def clear(self) -> None:
        self._store.clear()


# ─────────────────────────────────────────────────────────────────────────────
#  CLOUD AI FACADE
# ─────────────────────────────────────────────────────────────────────────────

class CloudAI:
    """
    Thin bridge used by voice_routes and anywhere else that expects
    a ``cloud_ai`` singleton with ``.generate()`` and ``.active_provider``.
    Delegates everything to the universal LLM manager.
    """

    SYSTEM_PROMPT = (
        "You are Igris, a supreme AI assistant. Respond concisely and helpfully. "
        "You understand Roman Urdu and English both."
    )

    def __init__(self) -> None:
        self.cache = AdvancedCache()
        self._call_count = 0
        self._error_count = 0

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def active_provider(self) -> str:
        return universal_llm.config.get("active_provider", "ollama")

    @property
    def active_model(self) -> str:
        return universal_llm.config.get("active_model", "llama3")

    # ── main generate ─────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> str:
        """Generate a response via the universal LLM. Uses cache when possible."""
        # Check cache first
        if use_cache:
            cached = self.cache.get(prompt)
            if cached is not None:
                return cached

        sys_prompt = system_prompt or self.SYSTEM_PROMPT
        self._call_count += 1

        try:
            response = await universal_llm.generate_response(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                **kwargs,
            )
            if use_cache and response:
                self.cache.put(prompt, response)
            return response
        except Exception as exc:
            self._error_count += 1
            raise RuntimeError(f"Cloud AI generation failed: {exc}") from exc

    # ── multi-turn chat ───────────────────────────────────────────────────────

    async def chat(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Multi-turn chat using the underlying LLM manager."""
        sys_prompt = system_prompt or self.SYSTEM_PROMPT
        # Extract history (everything except the last user message)
        history = messages[:-1] if len(messages) > 1 else []
        user_msg = messages[-1]["content"] if messages else ""

        return await universal_llm.generate_response(
            system_prompt=sys_prompt,
            user_prompt=user_msg,
            history=history,
        )

    # ── health & analytics ────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        return await universal_llm.health_check()

    def get_stats(self) -> dict:
        return {
            "provider":     self.active_provider,
            "model":        self.active_model,
            "total_calls":  self._call_count,
            "errors":       self._error_count,
            "cache":        self.cache.stats(),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

cloud_ai = CloudAI()
