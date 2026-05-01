"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS MODEL ROUTES — Complete & Upgraded
  Manage LLM providers, switch models, stream responses, analytics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.llm_manager import universal_llm
from app.core import api_auth

router = APIRouter(prefix="/models", tags=["Models"])


def _require_admin_config_auth(request: Request) -> None:
    if not api_auth.verify_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    # In explicit dev open mode, allow provider key setup from local UI.
    mode = str(api_auth.get_auth_status().get("mode", ""))
    if not api_auth.is_auth_enabled() and not mode.startswith("open"):
        raise HTTPException(
            status_code=503,
            detail="Model config updates require IGRIS_API_TOKEN to be enabled.",
        )


# ─────────────────────────────────────────────────────────────────────────────
#  REQUEST MODELS
# ─────────────────────────────────────────────────────────────────────────────

class APIKeyUpdate(BaseModel):
    provider: str
    api_key:  str

class ModelSelection(BaseModel):
    provider: str
    model:    str

class ModelRegister(BaseModel):
    provider: str
    model: str

class GenerateRequest(BaseModel):
    system_prompt: str = "You are Igris, a supreme AI assistant."
    user_prompt:   str
    is_json:       bool = False
    temperature:   Optional[float] = None
    max_tokens:    Optional[int]   = None
    history:       Optional[List[dict]] = None

class StreamRequest(BaseModel):
    system_prompt: str = "You are Igris, a supreme AI assistant."
    user_prompt:   str
    history:       Optional[List[dict]] = None

class TemperatureUpdate(BaseModel):
    temperature: float
    max_tokens:  Optional[int] = None

class OllamaPullRequest(BaseModel):
    model: str


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_model_config():
    """Get current LLM config (API keys masked)."""
    return universal_llm.get_safe_config()


@router.get("/catalog")
async def get_model_catalog():
    """
    Flat, UI-friendly model catalog across all providers.
    Grouped by category: local / cloud / api.
    """
    catalog = universal_llm.get_catalog()
    # Merge real-time Ollama pulled models into catalog if available.
    try:
        ollama_live = await universal_llm.list_ollama_models()
        if ollama_live:
            prov = universal_llm.config.get("providers", {}).get("ollama", {})
            models = list(prov.get("models", []))
            changed = False
            for model in ollama_live:
                if model not in models:
                    models.append(model)
                    changed = True
            if changed:
                universal_llm.config["providers"]["ollama"]["models"] = models
                universal_llm.save_config()
                catalog = universal_llm.get_catalog()
    except Exception:
        pass
    by_category: Dict[str, List[dict]] = {"local": [], "cloud": [], "api": []}
    for row in catalog:
        by_category.setdefault(row["category"], []).append(row)
    return {
        "total":       len(catalog),
        "by_category": by_category,
        "items":       catalog,
        "active": {
            "provider": universal_llm.config["active_provider"],
            "model":    universal_llm.config["active_model"],
            "id":       f"{universal_llm.config['active_provider']}/"
                        f"{universal_llm.config['active_model']}",
        },
    }


@router.get("/providers")
async def get_providers():
    """List providers with metadata (label, category, needs_key, api_key_set)."""
    safe = universal_llm.get_safe_config()
    return {
        "providers": [
            {
                "id":           prov,
                "label":        data.get("label", prov.title()),
                "category":     data.get("category", "api"),
                "needs_key":    data.get("needs_key", True),
                "api_key_set":  data.get("api_key_set", False),
                "site":         data.get("site"),
                "model_count":  len(data.get("models", [])),
                "models":       data.get("models", []),
            }
            for prov, data in safe.get("providers", {}).items()
        ],
        "litellm_enabled": safe.get("litellm_enabled", False),
    }


@router.post("/apikey")
async def update_api_key(data: APIKeyUpdate, request: Request):
    """Set or update an API key for a provider."""
    _require_admin_config_auth(request)
    try:
        universal_llm.set_api_key(data.provider, data.api_key)
        return {"status": "success", "message": f"API key updated for {data.provider}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/active")
async def set_active_model(data: ModelSelection):
    """Switch the active provider and model."""
    try:
        universal_llm.set_active_model(data.provider, data.model)
        return {
            "status":   "success",
            "provider": data.provider,
            "model":    data.model,
            "message":  f"Switched to {data.provider}/{data.model}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register")
async def register_model(data: ModelRegister):
    """Add a model to provider catalog without changing active selection."""
    provider = data.provider.strip().lower()
    model = data.model.strip()
    if not provider or not model:
        raise HTTPException(status_code=400, detail="provider and model are required")
    if provider not in universal_llm.config.get("providers", {}):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    current_provider = universal_llm.config.get("active_provider", "ollama")
    current_model = universal_llm.config.get("active_model", "llama3")
    universal_llm.set_active_model(provider, model)  # also persists unknown models
    # restore currently active selection
    universal_llm.set_active_model(current_provider, current_model)
    return {"status": "success", "provider": provider, "model": model}


@router.post("/settings")
async def update_generation_settings(data: TemperatureUpdate):
    """Update temperature and max_tokens."""
    universal_llm.config["temperature"] = max(0.0, min(2.0, data.temperature))
    if data.max_tokens:
        universal_llm.config["max_tokens"] = max(64, min(32768, data.max_tokens))
    universal_llm.save_config()
    return {
        "status":      "updated",
        "temperature": universal_llm.config["temperature"],
        "max_tokens":  universal_llm.config["max_tokens"],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  OLLAMA LOCAL MODEL MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ollama/list")
async def list_ollama_models():
    """List models currently available in your local Ollama instance."""
    models = await universal_llm.list_ollama_models()
    return {"models": models, "count": len(models)}


@router.post("/ollama/pull")
async def pull_ollama_model(data: OllamaPullRequest):
    """Download a model into local Ollama (for later use)."""
    result = await universal_llm.pull_ollama_model(data.model)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "pull failed"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  GENERATION ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate(req: GenerateRequest):
    """Generate a single response from the active LLM."""
    try:
        text = await universal_llm.generate_response(
            system_prompt=req.system_prompt,
            user_prompt=req.user_prompt,
            is_json=req.is_json,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            history=req.history,
        )
        return {
            "status":   "success",
            "response": text,
            "provider": universal_llm.config["active_provider"],
            "model":    universal_llm.config["active_model"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream(req: StreamRequest):
    """
    Stream response tokens from the active LLM.
    Returns a text/event-stream (Server-Sent Events).
    """
    async def _gen():
        try:
            async for chunk in universal_llm.stream_response(
                system_prompt=req.system_prompt,
                user_prompt=req.user_prompt,
                history=req.history,
            ):
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            yield f"data: [ERROR] {exc}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.post("/test")
async def test_connection():
    """Quick test: ping active provider. Returns latency + status."""
    result = await universal_llm.health_check()
    status_code = 200 if result["status"] == "online" else 503
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_llm_stats():
    """LLM call analytics — total calls, success rate, avg latency."""
    return universal_llm.get_stats()


@router.get("/health")
async def health():
    """Full health check with provider ping."""
    return await universal_llm.health_check()
