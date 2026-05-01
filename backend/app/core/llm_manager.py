"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS LLM MANAGER — Upgraded & Complete
  Supports: Ollama (local) · OpenAI · Anthropic · Gemini · Groq
           · Mistral · Together · OpenRouter · Perplexity · HuggingFace
  Features: streaming, cheap health-check, multi-turn chat, analytics,
           model catalog with provider categories
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv

_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_BACKEND_ENV, override=False)

try:
    import litellm
    litellm.suppress_debug_info = True
    _LITELLM = True
except ImportError:
    litellm = None  # type: ignore
    _LITELLM = False


# ─────────────────────────────────────────────────────────────────────────────
#  PROVIDER METADATA
# ─────────────────────────────────────────────────────────────────────────────

# category: "local" | "cloud" | "api"  (UI grouping hint)
PROVIDER_META: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "label":    "Ollama (Local)",
        "category": "local",
        "needs_key": False,
        "site":     "https://ollama.com",
    },
    "openai": {
        "label":    "OpenAI",
        "category": "cloud",
        "needs_key": True,
        "site":     "https://platform.openai.com",
    },
    "anthropic": {
        "label":    "Anthropic (Claude)",
        "category": "cloud",
        "needs_key": True,
        "site":     "https://console.anthropic.com",
    },
    "gemini": {
        "label":    "Google Gemini",
        "category": "cloud",
        "needs_key": True,
        "site":     "https://aistudio.google.com",
    },
    "deepseek": {
        "label":    "DeepSeek",
        "category": "api",
        "needs_key": True,
        "site":     "https://platform.deepseek.com",
    },
    "groq": {
        "label":    "Groq (Fastest)",
        "category": "api",
        "needs_key": True,
        "site":     "https://console.groq.com",
    },
    "mistral": {
        "label":    "Mistral AI",
        "category": "cloud",
        "needs_key": True,
        "site":     "https://console.mistral.ai",
    },
    "together": {
        "label":    "Together AI",
        "category": "api",
        "needs_key": True,
        "site":     "https://api.together.xyz",
    },
    "openrouter": {
        "label":    "OpenRouter",
        "category": "api",
        "needs_key": True,
        "site":     "https://openrouter.ai",
    },
    "perplexity": {
        "label":    "Perplexity",
        "category": "api",
        "needs_key": True,
        "site":     "https://www.perplexity.ai",
    },
    "huggingface": {
        "label":    "HuggingFace Inference",
        "category": "api",
        "needs_key": True,
        "site":     "https://huggingface.co",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  DEFAULT CONFIG (models + providers)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_CONFIG: Dict[str, Any] = {
    "active_provider": "ollama",
    "active_model":    "llama3.1:8b",
    "auto_switch_on_provider_failure": True,
    "temperature":     0.7,
    "max_tokens":      2048,
    "providers": {
        "ollama": {
            "base_url": "http://localhost:11434",
            "models":   [
                "deepseek-r1:1.5b",
                "deepseek-r1:7b",
                "deepseek-r1:8b",
                "deepseek-r1:14b",
                "deepseek-r1:32b",
                "deepseek-r1:70b",
                "llama3.3:70b",
                "llama3.2:3b",
                "llama3.2:1b",
                "llama3.1:8b",
                "llama3.1:70b",
                "mistral",
                "mixtral",
                "gemma2:2b",
                "gemma2:9b",
                "gemma2:27b",
                "phi4",
                "phi3.5",
                "qwen2.5:7b",
                "qwen2.5:14b",
                "qwen2.5:32b",
                "qwen2.5-coder:7b",
                "dolphin-mistral",
                "nomic-embed-text"
            ],
        },
        "openai": {
            "api_key": "",
            "models":  [
                "o3-mini",
                "o1",
                "o1-mini",
                "o1-preview",
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
            ],
        },
        "anthropic": {
            "api_key": "",
            "models":  [
                "claude-3-7-sonnet-20250219",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
        },
        "gemini": {
            "api_key": "",
            "models":  [
                "gemini-2.5-pro",
                "gemini-2.0-flash",
                "gemini-2.0-flash-thinking-exp-01-21",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
            ],
        },
        "deepseek": {
            "api_key": "",
            "models":  [
                "deepseek-chat",
                "deepseek-reasoner",
            ],
        },
        "groq": {
            "api_key": "",
            "models":  [
                "deepseek-r1-distill-llama-70b",
                "deepseek-r1-distill-llama-8b",
                "deepseek-r1-distill-qwen-32b",
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "llama3-70b-8192",
                "llama3-8b-8192",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
                "qwen-2.5-32b",
            ],
        },
        "mistral": {
            "api_key": "",
            "models":  [
                "mistral-large-latest",
                "mistral-medium-latest",
                "mistral-small-latest",
                "codestral-latest",
                "open-mixtral-8x22b",
                "open-mixtral-8x7b",
            ],
        },
        "together": {
            "api_key": "",
            "models":  [
                "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
                "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "Qwen/Qwen2.5-72B-Instruct-Turbo",
            ],
        },
        "openrouter": {
            "api_key": "",
            "models":  [
                "openai/o3-mini",
                "openai/gpt-4o",
                "anthropic/claude-3.7-sonnet",
                "google/gemini-2.0-flash",
                "deepseek/deepseek-r1",
                "deepseek/deepseek-chat",
                "meta-llama/llama-3.3-70b-instruct",
                "mistralai/mistral-large",
            ],
        },
        "perplexity": {
            "api_key": "",
            "models":  [
                "sonar-reasoning-pro",
                "sonar-reasoning",
                "sonar-pro",
                "sonar",
                "llama-3.1-sonar-large-128k-online",
            ],
        },
        "huggingface": {
            "api_key": "",
            "models":  [
                "meta-llama/Meta-Llama-3-8B-Instruct",
                "mistralai/Mistral-7B-Instruct-v0.3",
                "HuggingFaceH4/zephyr-7b-beta",
            ],
        },
    },
}


# Providers that litellm expects as "provider/model"
_LITELLM_PREFIX_PROVIDERS = {
    "groq", "gemini", "anthropic", "mistral", "deepseek",
    "together_ai", "openrouter", "perplexity", "huggingface",
}

# Normalise our provider key → litellm provider key
_LITELLM_PROVIDER_MAP = {
    "together":   "together_ai",
    "openrouter": "openrouter",
}


# ─────────────────────────────────────────────────────────────────────────────
#  LLM MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class LLMManager:
    """
    Universal LLM gateway for Igris OS.

    Usage
    -----
    response = await universal_llm.generate_response(system, user)
    async for chunk in universal_llm.stream_response(system, user):
        print(chunk, end="", flush=True)
    """

    _CONFIG_FILE = "llm_config.json"

    def __init__(self) -> None:
        self.config    = self._load_config()
        self._call_log: List[dict] = []   # last 100 calls for analytics

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self) -> Dict[str, Any]:
        # 1. Start from defaults (deep copy)
        cfg = json.loads(json.dumps(_DEFAULT_CONFIG))

        # 2. Overlay stored config if present
        if os.path.exists(self._CONFIG_FILE):
            try:
                with open(self._CONFIG_FILE, "r", encoding="utf-8") as f:
                    stored = json.load(f)

                for k in ("active_provider", "active_model",
                          "temperature", "max_tokens",
                          "auto_switch_on_provider_failure"):
                    if k in stored:
                        cfg[k] = stored[k]

                stored_providers = stored.get("providers", {}) or {}
                for prov, data in stored_providers.items():
                    if prov not in cfg["providers"]:
                        cfg["providers"][prov] = data
                        continue
                    merged = {**cfg["providers"][prov], **data}
                    # Preserve default models if user file had empty list
                    if not merged.get("models"):
                        merged["models"] = cfg["providers"][prov].get("models", [])
                    cfg["providers"][prov] = merged
            except Exception:
                pass

        # 3. Overlay env-var API keys / base URL if stored values are empty
        for prov in cfg["providers"]:
            env_key = f"{prov.upper()}_API_KEY"
            val = os.getenv(env_key, "")
            if val and not cfg["providers"][prov].get("api_key"):
                cfg["providers"][prov]["api_key"] = val

        ollama_url = os.getenv("OLLAMA_BASE_URL", "")
        if ollama_url:
            cfg["providers"]["ollama"]["base_url"] = ollama_url

        return cfg

    def save_config(self) -> None:
        with open(self._CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def set_active_model(self, provider: str, model: str) -> None:
        if provider not in self.config["providers"]:
            raise ValueError(f"Unknown provider: {provider}")
        known = self.config["providers"][provider].get("models", [])
        if model not in known:
            # Allow custom/unknown models but remember them
            known.append(model)
            self.config["providers"][provider]["models"] = known
        self.config["active_provider"] = provider
        self.config["active_model"]    = model
        self.save_config()

    def set_auto_switch_mode(self, enabled: bool) -> None:
        self.config["auto_switch_on_provider_failure"] = bool(enabled)
        self.save_config()

    def set_api_key(self, provider: str, api_key: str) -> None:
        if provider not in self.config["providers"]:
            raise ValueError(f"Unknown provider: {provider}")
        self.config["providers"][provider]["api_key"] = api_key
        self.save_config()

    def get_safe_config(self) -> dict:
        """Return config with API keys masked — safe to send to frontend."""
        safe: Dict[str, Any] = {
            "active_provider": self.config["active_provider"],
            "active_model":    self.config["active_model"],
            "temperature":     self.config.get("temperature", 0.7),
            "max_tokens":      self.config.get("max_tokens", 2048),
            "providers":       {},
            "litellm_enabled": _LITELLM,
        }
        for prov, data in self.config["providers"].items():
            meta = PROVIDER_META.get(prov, {})
            safe["providers"][prov] = {
                "models":     list(data.get("models", [])),
                "base_url":   data.get("base_url"),
                "label":      meta.get("label", prov.title()),
                "category":   meta.get("category", "api"),
                "needs_key":  meta.get("needs_key", True),
                "site":       meta.get("site"),
                "api_key_set": bool(
                    data.get("api_key")
                    or os.getenv(f"{prov.upper()}_API_KEY", "")
                ),
            }
        return safe

    def get_catalog(self) -> List[dict]:
        """
        Flat, UI-friendly model catalog:
        [{ "id": "groq/llama3-70b-8192", "provider": "groq",
           "model": "llama3-70b-8192", "category": "api",
           "label": "Groq (Fastest)", "api_key_set": True }]
        """
        rows: List[dict] = []
        for prov, data in self.config["providers"].items():
            meta = PROVIDER_META.get(prov, {})
            key_set = bool(
                data.get("api_key")
                or os.getenv(f"{prov.upper()}_API_KEY", "")
            )
            for model in data.get("models", []):
                rows.append({
                    "id":          f"{prov}/{model}",
                    "provider":    prov,
                    "model":       model,
                    "category":    meta.get("category", "api"),
                    "label":       meta.get("label", prov.title()),
                    "needs_key":   meta.get("needs_key", True),
                    "api_key_set": key_set,
                })
        # Sort: local first, then cloud, then api; alpha within category
        order = {"local": 0, "cloud": 1, "api": 2}
        rows.sort(key=lambda r: (order.get(r["category"], 9), r["provider"], r["model"]))
        return rows

    # ── Core generation ───────────────────────────────────────────────────────

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt:   str,
        is_json:       bool = False,
        temperature:   Optional[float] = None,
        max_tokens:    Optional[int]   = None,
        history:       Optional[List[dict]] = None,
    ) -> str:
        """Generate a single response. Returns the text string."""
        provider = self.config["active_provider"]
        model    = self.config["active_model"]
        temp     = temperature if temperature is not None else self.config.get("temperature", 0.7)
        mtoks    = max_tokens  if max_tokens  is not None else self.config.get("max_tokens", 2048)

        messages = self._build_messages(system_prompt, user_prompt, history)

        t_start = time.time()
        try:
            if provider == "ollama":
                result = await self._ollama_generate(model, system_prompt, user_prompt, is_json)
            else:
                result = await self._litellm_generate(provider, model, messages, is_json, temp, mtoks)
            self._log_call(provider, model, True, time.time() - t_start)
            return result
        except Exception as exc:
            self._log_call(provider, model, False, time.time() - t_start, str(exc))
            # Auto-fallback: if cloud/API provider fails, try local Ollama silently.
            if provider != "ollama":
                fallback_model = self._pick_ollama_fallback_model()
                if fallback_model:
                    if self.config.get("auto_switch_on_provider_failure", True):
                        self.config["active_provider"] = "ollama"
                        self.config["active_model"] = fallback_model
                        self.save_config()
                    try:
                        result = await self._ollama_generate(
                            fallback_model, system_prompt, user_prompt, is_json
                        )
                        self._log_call("ollama", fallback_model, True, time.time() - t_start)
                        return result
                    except Exception as fallback_exc:
                        self._log_call(
                            "ollama", fallback_model, False, time.time() - t_start, str(fallback_exc)
                        )
            # Final graceful fallback so UI doesn't show raw provider stack traces.
            fallback_text = (
                "My Liege, current model is temporarily unavailable. "
                "Please switch to another available model and retry."
            )
            if is_json:
                return json.dumps(
                    {
                        "thought": "Provider and fallback are unavailable.",
                        "emotion": "analytical",
                        "tool_name": "None",
                        "tool_args": {},
                        "reply": fallback_text,
                    }
                )
            return fallback_text

    async def stream_response(
        self,
        system_prompt: str,
        user_prompt:   str,
        history:       Optional[List[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response chunks one token at a time."""
        provider = self.config["active_provider"]
        model    = self.config["active_model"]

        if provider == "ollama":
            async for chunk in self._ollama_stream(model, system_prompt, user_prompt):
                yield chunk
        else:
            try:
                async for chunk in self._litellm_stream(
                    provider, model,
                    self._build_messages(system_prompt, user_prompt, history)
                ):
                    yield chunk
            except Exception:
                fallback_model = self._pick_ollama_fallback_model()
                if not fallback_model:
                    yield (
                        "My Liege, streaming is temporarily unavailable right now. "
                        "Please switch to another available model and retry."
                    )
                    return
                try:
                    if self.config.get("auto_switch_on_provider_failure", True):
                        self.config["active_provider"] = "ollama"
                        self.config["active_model"] = fallback_model
                        self.save_config()
                    async for chunk in self._ollama_stream(fallback_model, system_prompt, user_prompt):
                        yield chunk
                except Exception:
                    yield (
                        "My Liege, streaming fallback also failed. "
                        "Please switch to another available model and retry."
                    )
                    return

    # ── Health check (cheap — no billable completion) ─────────────────────────

    async def health_check(self) -> dict:
        """
        Ping current provider and return latency / status.
        Does NOT burn tokens on cloud providers — checks key presence +
        reachability only. Ollama is verified via /api/tags.
        """
        provider = self.config["active_provider"]
        model    = self.config["active_model"]
        t = time.time()
        try:
            if provider == "ollama":
                url = self.config["providers"]["ollama"]["base_url"] + "/api/tags"
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        ok = r.status == 200
                        data = await r.json() if ok else {}
                available_models = [m["name"] for m in data.get("models", [])]
                status = "online" if ok else "offline"
            else:
                # Cheap check: API key present + litellm library available
                api_key = (
                    self.config["providers"][provider].get("api_key")
                    or os.getenv(f"{provider.upper()}_API_KEY", "")
                )
                if not api_key:
                    status = "no_key"
                elif not _LITELLM:
                    status = "litellm_missing"
                else:
                    status = "online"
                available_models = self.config["providers"][provider].get("models", [])

            return {
                "status":           status,
                "provider":         provider,
                "model":            model,
                "latency_ms":       round((time.time() - t) * 1000, 1),
                "available_models": available_models,
                "litellm_enabled":  _LITELLM,
            }
        except Exception as exc:
            return {
                "status":    "error",
                "provider":  provider,
                "model":     model,
                "error":     str(exc),
                "latency_ms": round((time.time() - t) * 1000, 1),
            }

    async def list_ollama_models(self) -> List[str]:
        """Return models currently pulled in the local Ollama instance."""
        url = self.config["providers"]["ollama"]["base_url"] + "/api/tags"
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    async def pull_ollama_model(self, model: str) -> dict:
        """Trigger `ollama pull` via local API and return completion status."""
        model = (model or "").strip()
        if not model:
            raise ValueError("model is required")

        base = self.config["providers"]["ollama"]["base_url"]
        payload = {"name": model, "stream": False}
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    f"{base}/api/pull",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=600),
                ) as r:
                    text = await r.text()
                    if r.status != 200:
                        raise RuntimeError(f"Ollama pull failed: HTTP {r.status}: {text[:300]}")
                    data = json.loads(text) if text.strip().startswith("{") else {"response": text}
        except Exception as exc:
            return {"ok": False, "model": model, "error": str(exc)}

        # Keep provider model list in sync so UI can switch immediately.
        known = self.config.get("providers", {}).get("ollama", {}).get("models", []) or []
        if model not in known:
            known.append(model)
            self.config["providers"]["ollama"]["models"] = known
            self.save_config()
        return {"ok": True, "model": model, "result": data}

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        total   = len(self._call_log)
        success = sum(1 for c in self._call_log if c["success"])
        avg_lat = (
            sum(c["latency"] for c in self._call_log) / total
            if total else 0.0
        )
        return {
            "total_calls":      total,
            "successful_calls": success,
            "failed_calls":     total - success,
            "success_rate":     round(success / total * 100, 1) if total else 100.0,
            "avg_latency_ms":   round(avg_lat * 1000, 1),
            "recent_calls":     self._call_log[-10:],
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_messages(
        system: str,
        user:   str,
        history: Optional[List[dict]] = None,
    ) -> List[dict]:
        msgs: List[dict] = [{"role": "system", "content": system}]
        if history:
            for h in history[-10:]:  # keep last 10 turns
                msgs.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        msgs.append({"role": "user", "content": user})
        return msgs

    async def _ollama_generate(
        self, model: str, system: str, user: str, is_json: bool
    ) -> str:
        base = self.config["providers"]["ollama"]["base_url"]
        payload: Dict[str, Any] = {
            "model":  model,
            "prompt": f"{system}\n\nUser: {user}",
            "stream": False,
        }
        if is_json:
            payload["format"] = "json"

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{base}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as r:
                if r.status != 200:
                    raise RuntimeError(f"Ollama returned HTTP {r.status}")
                data = await r.json()
                return data.get("response", "")

    async def _ollama_stream(
        self, model: str, system: str, user: str
    ) -> AsyncGenerator[str, None]:
        base = self.config["providers"]["ollama"]["base_url"]
        payload = {
            "model":  model,
            "prompt": f"{system}\n\nUser: {user}",
            "stream": True,
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{base}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as r:
                if r.status != 200:
                    raise RuntimeError(f"Ollama returned HTTP {r.status}")
                buffer = ""
                async for raw in r.content:
                    buffer += raw.decode("utf-8", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            tok = chunk.get("response", "")
                            if tok:
                                yield tok
                            if chunk.get("done"):
                                return
                        except json.JSONDecodeError:
                            continue
                line = buffer.strip()
                if line:
                    try:
                        chunk = json.loads(line)
                        tok = chunk.get("response", "")
                        if tok:
                            yield tok
                    except json.JSONDecodeError:
                        pass

    def _litellm_model_id(self, provider: str, model: str) -> str:
        p = _LITELLM_PROVIDER_MAP.get(provider, provider)
        if p in _LITELLM_PREFIX_PROVIDERS:
            return f"{p}/{model}"
        return model

    def _pick_ollama_fallback_model(self) -> Optional[str]:
        models = self.config.get("providers", {}).get("ollama", {}).get("models", []) or []
        if not models:
            return None
        preferred = self.config.get("active_model")
        if isinstance(preferred, str) and preferred in models:
            return preferred
        return models[0]

    async def _litellm_generate(
        self,
        provider: str,
        model:    str,
        messages: List[dict],
        is_json:  bool,
        temp:     float,
        max_tok:  int,
    ) -> str:
        if not _LITELLM:
            raise RuntimeError("litellm is not installed. Run: pip install litellm")

        api_key = (
            self.config["providers"][provider].get("api_key")
            or os.getenv(f"{provider.upper()}_API_KEY", "")
        )
        if not api_key:
            raise RuntimeError(f"API key not set for provider: {provider}")

        os.environ[f"{provider.upper()}_API_KEY"] = api_key

        kwargs: Dict[str, Any] = {
            "model":       self._litellm_model_id(provider, model),
            "messages":    messages,
            "temperature": temp,
            "max_tokens":  max_tok,
            "timeout":     60,
        }
        if is_json and provider in ("openai", "groq", "mistral"):
            kwargs["response_format"] = {"type": "json_object"}

        resp = await litellm.acompletion(**kwargs)
        return resp.choices[0].message.content

    async def _litellm_stream(
        self,
        provider: str,
        model:    str,
        messages: List[dict],
    ) -> AsyncGenerator[str, None]:
        if not _LITELLM:
            raise RuntimeError("litellm not installed")

        api_key = (
            self.config["providers"][provider].get("api_key")
            or os.getenv(f"{provider.upper()}_API_KEY", "")
        )
        if not api_key:
            raise RuntimeError(f"API key not set for provider: {provider}")
        os.environ[f"{provider.upper()}_API_KEY"] = api_key

        resp = await litellm.acompletion(
            model=self._litellm_model_id(provider, model),
            messages=messages,
            stream=True,
            timeout=120,
        )
        async for chunk in resp:
            tok = chunk.choices[0].delta.content or ""
            if tok:
                yield tok

    def _log_call(
        self,
        provider: str,
        model:    str,
        success:  bool,
        latency:  float,
        error:    str = "",
    ) -> None:
        entry = {
            "provider":  provider,
            "model":     model,
            "success":   success,
            "latency":   latency,
            "error":     error,
            "timestamp": time.time(),
        }
        self._call_log.append(entry)
        if len(self._call_log) > 100:
            self._call_log.pop(0)


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

universal_llm = LLMManager()
