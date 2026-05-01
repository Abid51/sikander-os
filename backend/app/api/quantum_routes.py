"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS QUANTUM THINKING — API Routes  ⚛️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional
import time

router = APIRouter(prefix="/quantum", tags=["Quantum Thinking"])

# ── Request / Response Models ─────────────────────────────────────────────────

class QuantumThinkRequest(BaseModel):
    query: str = Field("", min_length=0, description="The question or problem to think about")
    question: str = ""  # alias used by some clients / integration tests
    depth: int = Field(3, ge=1, le=6, description="Number of quantum thinking angles (1-6)")
    angles: Optional[List[str]] = Field(None, description="Specific angle IDs to use")
    options: Optional[List[str]] = None
    context: str = Field("", description="Additional context")

class QuickThinkRequest(BaseModel):
    query: str = ""
    angle_id: str = "first_principles"
    # Backward-compatible aliases used by older frontend builds.
    prompt: str = ""
    angle: str = ""

# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/think")
async def quantum_think(req: QuantumThinkRequest):
    """
    Full quantum thinking pipeline.
    Executes superposition → interference → entanglement → collapse → synthesis.
    """
    try:
        from app.core.quantum_thinking_engine import get_quantum_thinking_engine
        engine = get_quantum_thinking_engine()

        q = (req.query or req.question or "").strip()
        if not q or len(q) < 3:
            return {"status": "error", "error": "query or question required (min 3 chars)"}
        ctx = req.context
        if req.options:
            ctx = (ctx or "") + "\n[Options] " + ", ".join(req.options)
        result = await engine.think_async(
            query=q,
            depth=req.depth,
            angles=req.angles,
            context=ctx,
        )

        return {
            "status": "collapsed",
            "result": result.to_dict(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time(),
        }


@router.post("/quick-think")
async def quick_think(req: QuickThinkRequest):
    """
    Single-angle quick thinking — faster, focused on one cognitive lens.
    """
    try:
        query = req.query or req.prompt
        angle_id = req.angle_id or req.angle or "first_principles"
        from app.core.quantum_thinking_engine import get_quantum_thinking_engine
        engine = get_quantum_thinking_engine()

        result = await engine.think_async(
            query=query,
            depth=1,
            angles=[angle_id],
        )

        return {
            "status": "ok",
            "answer": result.final_answer,
            "confidence": result.confidence,
            "angle": angle_id,
            "processing_ms": result.processing_time_ms,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Retrieve a cached quantum thinking session."""
    try:
        from app.core.quantum_thinking_engine import get_quantum_thinking_engine
        engine = get_quantum_thinking_engine()
        result = engine.get_session(session_id)
        if not result:
            return {"error": "Session not found", "session_id": session_id}
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/history")
async def get_history(limit: int = 20):
    """Get recent quantum thinking history."""
    try:
        from app.core.quantum_thinking_engine import get_quantum_thinking_engine
        engine = get_quantum_thinking_engine()
        return {
            "history": engine.get_history(limit),
            "total": len(engine._history),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats")
async def get_stats():
    """Get quantum engine performance statistics."""
    try:
        from app.core.quantum_thinking_engine import get_quantum_thinking_engine
        engine = get_quantum_thinking_engine()
        return engine.get_stats()
    except Exception as e:
        return {"error": str(e)}


@router.get("/angles")
async def get_angles():
    """Get all available thinking angles."""
    from app.core.quantum_thinking_engine import QUANTUM_ANGLES
    return {
        "angles": [
            {"id": a["id"], "name": a["name"], "icon": a["icon"], "color": a["color"]}
            for a in QUANTUM_ANGLES
        ]
    }
