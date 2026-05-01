"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS NEW POWER ROUTES — Phase 2 Missing Features
  Browser Agent, Advanced Voice, Autonomous Agent, Feedback,
  Git Agent, Email Agent, Cost Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/igris", tags=["igris-new-power"])


# ─────────────────────────────────────────────────────────────────────────────
#  LAZY MODULE IMPORTS (safe — won't crash if optional deps missing)
# ─────────────────────────────────────────────────────────────────────────────

def _get_browser():
    try:
        from app.core.browser_agent import get_browser_agent
        return get_browser_agent()
    except Exception as e:
        logger.warning(f"[ROUTES] Browser agent unavailable: {e}")
        return None


def _get_voice():
    try:
        from app.core.advanced_voice_engine import get_voice_engine
        return get_voice_engine()
    except Exception as e:
        logger.warning(f"[ROUTES] Voice engine unavailable: {e}")
        return None


def _get_agent():
    try:
        from app.core.autonomous_agent import get_autonomous_agent
        return get_autonomous_agent()
    except Exception as e:
        logger.warning(f"[ROUTES] Autonomous agent unavailable: {e}")
        return None


def _get_feedback():
    try:
        from app.core.feedback_engine import get_feedback_engine
        return get_feedback_engine()
    except Exception as e:
        logger.warning(f"[ROUTES] Feedback engine unavailable: {e}")
        return None


def _get_git():
    try:
        from app.core.git_agent import get_git_agent
        return get_git_agent()
    except Exception as e:
        logger.warning(f"[ROUTES] Git agent unavailable: {e}")
        return None


def _get_email():
    try:
        from app.core.email_agent import get_email_agent
        return get_email_agent()
    except Exception as e:
        logger.warning(f"[ROUTES] Email agent unavailable: {e}")
        return None


def _get_cost():
    try:
        from app.core.cost_tracker import get_cost_tracker
        return get_cost_tracker()
    except Exception as e:
        logger.warning(f"[ROUTES] Cost tracker unavailable: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  REQUEST MODELS
# ─────────────────────────────────────────────────────────────────────────────

class BrowseRequest(BaseModel):
    url: str = Field(..., min_length=1)
    screenshot: bool = False


class ClickRequest(BaseModel):
    selector: str = Field(..., min_length=1)


class ClickTextRequest(BaseModel):
    text: str = Field(..., min_length=1)


class FillRequest(BaseModel):
    selector: str = Field(..., min_length=1)
    value: str


class GoogleSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    max_results: int = Field(default=5, ge=1, le=20)


class MultiStepRequest(BaseModel):
    steps: List[Dict[str, Any]] = Field(..., min_length=1)


class SpeakAdvancedRequest(BaseModel):
    text: str = Field(..., min_length=1)
    return_audio: bool = False


class AgentRunRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    context: Optional[str] = None


class FeedbackRequest(BaseModel):
    user_message: str = Field(..., min_length=1)
    igris_response: str = Field(..., min_length=1)
    rating: int = Field(..., ge=-1, le=1)
    message_id: Optional[str] = None
    feedback_text: Optional[str] = None
    model_used: str = "unknown"


class GitCommitRequest(BaseModel):
    message: Optional[str] = None
    add_all: bool = True


class GitPushRequest(BaseModel):
    remote: str = "origin"
    branch: Optional[str] = None


class GitCheckoutRequest(BaseModel):
    branch: str = Field(..., min_length=1)


class GitCloneRequest(BaseModel):
    url: str = Field(..., min_length=1)
    dest: Optional[str] = None


class GitRepoRequest(BaseModel):
    repo_path: str = Field(..., min_length=1)


class EmailSendRequest(BaseModel):
    to: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    html: Optional[str] = None
    cc: Optional[List[str]] = None


class EmailDraftRequest(BaseModel):
    instruction: str = Field(..., min_length=1)
    context: Optional[str] = None
    tone: str = "professional"


class BudgetRequest(BaseModel):
    daily_usd: Optional[float] = None
    monthly_usd: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
#  BROWSER AGENT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/browser/status")
async def browser_status():
    """Check browser agent availability."""
    agent = _get_browser()
    if not agent:
        return {"available": False, "error": "Browser agent not loaded"}
    return agent.get_status()


@router.post("/browser/start")
async def browser_start():
    """Start browser session."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available. Run: pip install playwright && playwright install chromium")
    ok = await agent.start()
    return {"success": ok, "status": agent.get_status()}


@router.post("/browser/stop")
async def browser_stop():
    """Stop browser session."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    await agent.stop()
    return {"success": True, "message": "Browser session closed"}


@router.post("/browser/browse")
async def browser_browse(req: BrowseRequest):
    """Navigate to URL and extract content."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available. Install: pip install playwright && playwright install chromium")
    result = await agent.browse(req.url, take_screenshot=req.screenshot)
    return result.to_dict()


@router.post("/browser/click")
async def browser_click(req: ClickRequest):
    """Click element by CSS selector."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    result = await agent.click(req.selector)
    return result.__dict__


@router.post("/browser/click-text")
async def browser_click_text(req: ClickTextRequest):
    """Click element by visible text."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    result = await agent.click_text(req.text)
    return result.__dict__


@router.post("/browser/fill")
async def browser_fill(req: FillRequest):
    """Fill an input field."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    result = await agent.fill_input(req.selector, req.value)
    return result.__dict__


@router.post("/browser/google-search")
async def browser_google_search(req: GoogleSearchRequest):
    """Search Google and return structured results."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    results = await agent.google_search(req.query, req.max_results)
    return {"query": req.query, "results": results, "count": len(results)}


@router.post("/browser/multi-step")
async def browser_multi_step(req: MultiStepRequest):
    """Execute multiple browser actions in sequence."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    results = await agent.multi_step_task(req.steps)
    return {"results": [r.__dict__ for r in results], "total_steps": len(results)}


@router.get("/browser/screenshot")
async def browser_screenshot():
    """Take screenshot of current page."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    b64 = await agent.screenshot()
    if not b64:
        raise HTTPException(500, "Screenshot failed")
    return {"screenshot_b64": b64, "format": "png"}


@router.get("/browser/history")
async def browser_history():
    """Get browser action history."""
    agent = _get_browser()
    if not agent:
        raise HTTPException(503, "Browser agent not available")
    return {"history": agent.get_history()}


# ─────────────────────────────────────────────────────────────────────────────
#  ADVANCED VOICE ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/voice-advanced/status")
async def voice_advanced_status():
    """Check advanced voice engine status."""
    engine = _get_voice()
    if not engine:
        return {"available": False, "error": "Voice engine not loaded"}
    return {"available": True, **engine.get_full_status()}


@router.post("/voice-advanced/speak")
async def voice_advanced_speak(req: SpeakAdvancedRequest):
    """Convert text to speech using ElevenLabs or OpenAI TTS."""
    engine = _get_voice()
    if not engine:
        raise HTTPException(503, "Voice engine not available")
    result = await engine.speak(req.text, return_audio=req.return_audio)
    return {
        "success": result.success,
        "engine": result.engine,
        "audio_b64": result.audio_b64,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


@router.post("/voice-advanced/transcribe")
async def voice_advanced_transcribe(audio: UploadFile = File(...)):
    """Upload audio file and transcribe it using Whisper."""
    engine = _get_voice()
    if not engine:
        raise HTTPException(503, "Voice engine not available")
    content = await audio.read()
    ext = audio.filename.split(".")[-1] if audio.filename else "wav"
    result = await engine.transcribe_upload(content, ext)
    return result.to_dict()


@router.post("/voice-advanced/record")
async def voice_advanced_record(duration: float = 5.0):
    """Record from microphone and transcribe."""
    engine = _get_voice()
    if not engine:
        raise HTTPException(503, "Voice engine not available")
    result = await engine.stt.record_and_transcribe(duration)
    return result.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
#  AUTONOMOUS AGENT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/agent/status")
async def agent_status():
    """Check autonomous agent status."""
    agent = _get_agent()
    if not agent:
        return {"available": False}
    return {"available": True, **agent.get_status()}


@router.post("/agent/run")
async def agent_run(req: AgentRunRequest):
    """Run autonomous agent to achieve a goal."""
    agent = _get_agent()
    if not agent:
        raise HTTPException(503, "Autonomous agent not available")
    run = await agent.run(req.goal, req.context)
    return run.to_dict()


@router.post("/agent/stream")
async def agent_stream(req: AgentRunRequest):
    """Stream autonomous agent steps in real-time (SSE)."""
    agent = _get_agent()
    if not agent:
        raise HTTPException(503, "Autonomous agent not available")

    import json

    async def event_generator():
        async for event in agent.stream_run(req.goal, req.context):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/agent/history")
async def agent_history(limit: int = 10):
    """Get agent run history."""
    agent = _get_agent()
    if not agent:
        raise HTTPException(503, "Autonomous agent not available")
    return {"runs": agent.get_run_history(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  FEEDBACK ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/feedback/stats")
async def feedback_stats():
    """Get feedback statistics."""
    engine = _get_feedback()
    if not engine:
        return {"available": False}
    return {"available": True, **engine.get_stats()}


@router.post("/feedback/submit")
async def feedback_submit(req: FeedbackRequest):
    """Submit thumbs up/down feedback for a response."""
    engine = _get_feedback()
    if not engine:
        raise HTTPException(503, "Feedback engine not available")
    record = engine.submit_feedback(
        user_message=req.user_message,
        igris_response=req.igris_response,
        rating=req.rating,
        message_id=req.message_id,
        feedback_text=req.feedback_text,
        model_used=req.model_used,
    )
    return {"success": True, "feedback_id": record.feedback_id, "rating": record.rating}


@router.get("/feedback/recent")
async def feedback_recent(limit: int = 20):
    """Get recent feedback records."""
    engine = _get_feedback()
    if not engine:
        raise HTTPException(503, "Feedback engine not available")
    return {"feedback": engine.get_recent_feedback(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  GIT AGENT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/git/status")
async def git_status():
    """Get git repository status."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    status = await agent.status()
    return status.to_dict()


@router.post("/git/set-repo")
async def git_set_repo(req: GitRepoRequest):
    """Change the active git repository."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    agent.set_repo(req.repo_path)
    return {"success": True, "repo_path": req.repo_path}


@router.get("/git/diff")
async def git_diff(staged: bool = False):
    """Get git diff."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    result = await agent.diff(staged=staged)
    return result.to_dict()


@router.get("/git/log")
async def git_log(limit: int = 10):
    """Get commit history."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    result = await agent.log(limit=limit)
    return result.to_dict()


@router.post("/git/commit")
async def git_commit(req: GitCommitRequest):
    """Commit changes (optionally with AI-generated message)."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    if req.message:
        result = await agent.commit(req.message, add_all=req.add_all)
    else:
        result = await agent.smart_commit()
    return result.to_dict()


@router.post("/git/push")
async def git_push(req: GitPushRequest):
    """Push commits to remote."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    result = await agent.push(req.remote, req.branch)
    return result.to_dict()


@router.post("/git/pull")
async def git_pull():
    """Pull latest changes."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    result = await agent.pull()
    return result.to_dict()


@router.post("/git/checkout")
async def git_checkout(req: GitCheckoutRequest):
    """Checkout a branch."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    result = await agent.checkout(req.branch)
    return result.to_dict()


@router.get("/git/branches")
async def git_branches():
    """List all branches."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    return await agent.list_branches()


@router.post("/git/clone")
async def git_clone(req: GitCloneRequest):
    """Clone a repository."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    result = await agent.clone(req.url, req.dest)
    return result.to_dict()


@router.get("/git/history")
async def git_command_history(limit: int = 20):
    """Get git command history."""
    agent = _get_git()
    if not agent:
        raise HTTPException(503, "Git agent not available")
    return {"history": agent.get_history(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  EMAIL AGENT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/email/status")
async def email_status():
    """Check email agent configuration."""
    agent = _get_email()
    if not agent:
        return {"available": False}
    return {"available": True, **agent.get_status()}


@router.post("/email/send")
async def email_send(req: EmailSendRequest):
    """Send an email."""
    agent = _get_email()
    if not agent:
        raise HTTPException(503, "Email agent not available")
    result = await agent.send(req.to, req.subject, req.body, req.html, req.cc)
    return {
        "success": result.success,
        "to": result.to,
        "subject": result.subject,
        "error": result.error,
    }


@router.get("/email/inbox")
async def email_inbox(limit: int = 10, unread_only: bool = False):
    """Read inbox emails."""
    agent = _get_email()
    if not agent:
        raise HTTPException(503, "Email agent not available")
    emails = await agent.read_inbox(limit=limit, unread_only=unread_only)
    return {"emails": [e.to_dict() for e in emails], "count": len(emails)}


@router.post("/email/draft")
async def email_draft(req: EmailDraftRequest):
    """Use AI to draft an email."""
    agent = _get_email()
    if not agent:
        raise HTTPException(503, "Email agent not available")
    draft = await agent.ai_draft(req.instruction, req.context, req.tone)
    return {"draft": draft}


# ─────────────────────────────────────────────────────────────────────────────
#  COST TRACKER ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/costs/stats")
async def costs_stats():
    """Get API cost statistics."""
    tracker = _get_cost()
    if not tracker:
        return {"available": False}
    return {"available": True, **tracker.get_stats()}


@router.get("/costs/recent")
async def costs_recent(limit: int = 20):
    """Get recent API calls with costs."""
    tracker = _get_cost()
    if not tracker:
        raise HTTPException(503, "Cost tracker not available")
    return {"calls": tracker.get_recent_calls(limit)}


@router.post("/costs/budget")
async def costs_set_budget(req: BudgetRequest):
    """Set daily/monthly budget limits."""
    tracker = _get_cost()
    if not tracker:
        raise HTTPException(503, "Cost tracker not available")
    tracker.set_budget(req.daily_usd, req.monthly_usd)
    return {"success": True, "daily_usd": req.daily_usd, "monthly_usd": req.monthly_usd}


@router.get("/costs/pricing")
async def costs_pricing():
    """Get pricing table for all models."""
    from app.core.cost_tracker import MODEL_PRICING
    return {"pricing": MODEL_PRICING, "currency": "USD_per_1M_tokens"}


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 3 LAZY IMPORTS
# ─────────────────────────────────────────────────────────────────────────────

def _get_image():
    try:
        from app.core.image_analysis import get_image_analyzer
        return get_image_analyzer()
    except Exception as e:
        logger.warning(f"[ROUTES] Image analyzer unavailable: {e}")
        return None


def _get_doc():
    try:
        from app.core.document_parser import get_document_parser
        return get_document_parser()
    except Exception as e:
        logger.warning(f"[ROUTES] Document parser unavailable: {e}")
        return None


def _get_db():
    try:
        from app.core.database_agent import get_database_agent
        return get_database_agent()
    except Exception as e:
        logger.warning(f"[ROUTES] Database agent unavailable: {e}")
        return None


def _get_discord():
    try:
        from app.core.discord_bot import get_discord_bot
        return get_discord_bot()
    except Exception as e:
        logger.warning(f"[ROUTES] Discord bot unavailable: {e}")
        return None


def _get_whatsapp():
    try:
        from app.core.whatsapp_agent import get_whatsapp_agent
        return get_whatsapp_agent()
    except Exception as e:
        logger.warning(f"[ROUTES] WhatsApp agent unavailable: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 3 REQUEST MODELS
# ─────────────────────────────────────────────────────────────────────────────

class ImageAnalyzeRequest(BaseModel):
    prompt: Optional[str] = None
    provider: Optional[str] = None


class ImageAnalyzeB64Request(BaseModel):
    image_b64: str = Field(..., min_length=10)
    mime: str = "image/png"
    prompt: Optional[str] = None
    provider: Optional[str] = None


class ImageCompareRequest(BaseModel):
    image1_b64: str = Field(..., min_length=10)
    image2_b64: str = Field(..., min_length=10)
    mime: str = "image/png"
    prompt: Optional[str] = None


class DocumentParseRequest(BaseModel):
    file_path: str = Field(..., min_length=1)


class DBConnectRequest(BaseModel):
    db_path: str = Field(..., min_length=1)


class DBQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)


class DBAskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class WhatsAppSendRequest(BaseModel):
    to: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    media_url: Optional[str] = None


class WhatsAppBroadcastRequest(BaseModel):
    numbers: List[str] = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class DiscordWebhookRequest(BaseModel):
    content: str = Field(..., min_length=1)
    username: str = "Igris AI"


# ─────────────────────────────────────────────────────────────────────────────
#  IMAGE ANALYSIS ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/image/status")
async def image_status():
    """Check image analysis engine availability."""
    engine = _get_image()
    if not engine:
        return {"available": False}
    return {"available": True, **engine.get_status()}


@router.post("/image/analyze")
async def image_analyze(file: UploadFile = File(...), prompt: Optional[str] = None, provider: Optional[str] = None):
    """Upload an image and analyze it."""
    engine = _get_image()
    if not engine:
        raise HTTPException(503, "Image analyzer not available")
    content = await file.read()
    ext = file.filename.split(".")[-1] if file.filename else "png"
    result = await engine.analyze_bytes(content, ext, prompt, provider)
    return result.to_dict()


@router.post("/image/analyze-b64")
async def image_analyze_b64(req: ImageAnalyzeB64Request):
    """Analyze a base64-encoded image."""
    engine = _get_image()
    if not engine:
        raise HTTPException(503, "Image analyzer not available")
    result = await engine.analyze_b64(req.image_b64, req.mime, req.prompt, req.provider)
    return result.to_dict()


@router.post("/image/compare")
async def image_compare(req: ImageCompareRequest):
    """Compare two images."""
    engine = _get_image()
    if not engine:
        raise HTTPException(503, "Image analyzer not available")
    result = await engine.compare_images(req.image1_b64, req.image2_b64, req.mime, req.prompt)
    return result.to_dict()


@router.post("/image/ocr")
async def image_ocr(file: UploadFile = File(...)):
    """Extract text (OCR) from an image."""
    engine = _get_image()
    if not engine:
        raise HTTPException(503, "Image analyzer not available")
    import base64
    content = await file.read()
    b64 = base64.b64encode(content).decode("utf-8")
    ext = file.filename.split(".")[-1] if file.filename else "png"
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
    text = await engine.extract_text(b64, mime)
    return {"text": text, "filename": file.filename}


@router.get("/image/history")
async def image_history(limit: int = 20):
    """Get image analysis history."""
    engine = _get_image()
    if not engine:
        raise HTTPException(503, "Image analyzer not available")
    return {"history": engine.get_history(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  DOCUMENT PARSER ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/document/status")
async def document_status():
    """Check document parser status."""
    parser = _get_doc()
    if not parser:
        return {"available": False}
    return {"available": True, **parser.get_status()}


@router.post("/document/parse")
async def document_parse(file: UploadFile = File(...)):
    """Upload and parse a document (PDF, DOCX, CSV, etc.)."""
    parser = _get_doc()
    if not parser:
        raise HTTPException(503, "Document parser not available")
    content = await file.read()
    result = await parser.parse_bytes(content, file.filename or "document.txt")
    return result.to_dict()


@router.post("/document/parse-path")
async def document_parse_path(req: DocumentParseRequest):
    """Parse a document from a local file path."""
    parser = _get_doc()
    if not parser:
        raise HTTPException(503, "Document parser not available")
    result = await parser.parse_file(req.file_path)
    return result.to_dict()


@router.post("/document/summarize")
async def document_summarize(file: UploadFile = File(...)):
    """Upload a document, parse it, and generate an AI summary."""
    parser = _get_doc()
    if not parser:
        raise HTTPException(503, "Document parser not available")
    content = await file.read()
    parsed = await parser.parse_bytes(content, file.filename or "document.txt")
    if not parsed.success:
        raise HTTPException(400, f"Parse failed: {parsed.error}")
    summary = await parser.summarize(parsed.text, parsed.filename)
    return {
        "filename": parsed.filename,
        "file_type": parsed.file_type,
        "pages": parsed.page_count,
        "word_count": parsed.word_count,
        "summary": summary.summary,
        "key_points": summary.key_points,
        "model_used": summary.model_used,
    }


@router.get("/document/history")
async def document_history(limit: int = 20):
    """Get document parse history."""
    parser = _get_doc()
    if not parser:
        raise HTTPException(503, "Document parser not available")
    return {"history": parser.get_history(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE AGENT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/db/status")
async def db_status():
    """Check database agent status."""
    agent = _get_db()
    if not agent:
        return {"available": False}
    return {"available": True, **agent.get_status()}


@router.post("/db/connect")
async def db_connect(req: DBConnectRequest):
    """Connect to a SQLite database."""
    agent = _get_db()
    if not agent:
        raise HTTPException(503, "Database agent not available")
    ok = agent.connect(req.db_path)
    return {"success": ok, "database": req.db_path}


@router.get("/db/tables")
async def db_tables():
    """List all tables with schemas."""
    agent = _get_db()
    if not agent:
        raise HTTPException(503, "Database agent not available")
    tables = await agent.list_tables()
    return {"tables": [t.to_dict() for t in tables], "count": len(tables)}


@router.get("/db/schema")
async def db_schema():
    """Get database schema as text."""
    agent = _get_db()
    if not agent:
        raise HTTPException(503, "Database agent not available")
    return {"schema": await agent.get_schema_text()}


@router.post("/db/query")
async def db_query(req: DBQueryRequest):
    """Execute a SQL query."""
    agent = _get_db()
    if not agent:
        raise HTTPException(503, "Database agent not available")
    result = await agent.execute(req.sql)
    return result.to_dict()


@router.post("/db/ask")
async def db_ask(req: DBAskRequest):
    """Ask a natural language question → generates and executes SQL."""
    agent = _get_db()
    if not agent:
        raise HTTPException(503, "Database agent not available")
    result = await agent.ask(req.question)
    return result.to_dict()


@router.get("/db/history")
async def db_history(limit: int = 20):
    """Get query history."""
    agent = _get_db()
    if not agent:
        raise HTTPException(503, "Database agent not available")
    return {"history": agent.get_history(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  DISCORD BOT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/discord/status")
async def discord_status():
    """Check Discord bot status."""
    bot = _get_discord()
    if not bot:
        return {"available": False}
    return {"available": True, **bot.get_status()}


@router.post("/discord/start")
async def discord_start():
    """Start the Discord bot (runs in background)."""
    bot = _get_discord()
    if not bot:
        raise HTTPException(503, "Discord bot not available")
    if not bot.available:
        raise HTTPException(503, "Discord not configured. Set DISCORD_BOT_TOKEN in .env and pip install discord.py")
    import asyncio
    asyncio.create_task(bot.start_bot())
    return {"success": True, "message": "Discord bot starting in background..."}


@router.post("/discord/stop")
async def discord_stop():
    """Stop the Discord bot."""
    bot = _get_discord()
    if not bot:
        raise HTTPException(503, "Discord bot not available")
    await bot.stop_bot()
    return {"success": True, "message": "Discord bot stopped"}


@router.post("/discord/webhook")
async def discord_webhook(req: DiscordWebhookRequest):
    """Send a message via Discord webhook."""
    bot = _get_discord()
    if not bot:
        raise HTTPException(503, "Discord bot not available")
    ok = await bot.send_webhook(req.content, req.username)
    return {"success": ok}


@router.get("/discord/messages")
async def discord_messages(limit: int = 20):
    """Get Discord message history."""
    bot = _get_discord()
    if not bot:
        raise HTTPException(503, "Discord bot not available")
    return {"messages": bot.get_message_history(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  WHATSAPP ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/whatsapp/status")
async def whatsapp_status():
    """Check WhatsApp agent status."""
    agent = _get_whatsapp()
    if not agent:
        return {"available": False}
    return {"available": True, **agent.get_status()}


@router.post("/whatsapp/send")
async def whatsapp_send(req: WhatsAppSendRequest):
    """Send a WhatsApp message."""
    agent = _get_whatsapp()
    if not agent:
        raise HTTPException(503, "WhatsApp agent not available")
    result = await agent.send(req.to, req.body, req.media_url)
    return {"success": result.success, "to": result.to, "sid": result.sid, "error": result.error}


@router.post("/whatsapp/broadcast")
async def whatsapp_broadcast(req: WhatsAppBroadcastRequest):
    """Broadcast message to multiple numbers."""
    agent = _get_whatsapp()
    if not agent:
        raise HTTPException(503, "WhatsApp agent not available")
    results = await agent.broadcast(req.numbers, req.message)
    return {
        "success": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "total": len(results),
    }


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request_data: Dict[str, Any]):
    """Twilio WhatsApp webhook endpoint for incoming messages."""
    agent = _get_whatsapp()
    if not agent:
        raise HTTPException(503, "WhatsApp agent not available")
    result = await agent.process_incoming(request_data)
    return result


@router.get("/whatsapp/messages")
async def whatsapp_messages(limit: int = 20):
    """Get WhatsApp message history."""
    agent = _get_whatsapp()
    if not agent:
        raise HTTPException(503, "WhatsApp agent not available")
    return {"messages": agent.get_message_log(limit)}


# ─────────────────────────────────────────────────────────────────────────────
#  COMPLETE FEATURE HEALTH CHECK (Phase 2 + Phase 3)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/new-features/health")
async def new_features_health():
    """Health check for all new features (Phase 2 + Phase 3)."""
    browser = _get_browser()
    voice = _get_voice()
    agent = _get_agent()
    feedback = _get_feedback()
    git = _get_git()
    email_a = _get_email()
    cost = _get_cost()
    image = _get_image()
    doc = _get_doc()
    db = _get_db()
    disc = _get_discord()
    wa = _get_whatsapp()

    return {
        "phase_2": {
            "browser_agent": {"loaded": browser is not None},
            "advanced_voice": {"loaded": voice is not None},
            "autonomous_agent": {"loaded": agent is not None},
            "feedback_engine": {"loaded": feedback is not None},
            "git_agent": {"loaded": git is not None},
            "email_agent": {"loaded": email_a is not None, "configured": email_a.available if email_a else False},
            "cost_tracker": {"loaded": cost is not None},
        },
        "phase_3": {
            "image_analyzer": {"loaded": image is not None, "providers": image.get_status().get("providers", {}) if image else {}},
            "document_parser": {"loaded": doc is not None, "status": doc.get_status() if doc else None},
            "database_agent": {"loaded": db is not None, "connected": db._connected if db else False},
            "discord_bot": {"loaded": disc is not None, "running": disc._running if disc else False},
            "whatsapp_agent": {"loaded": wa is not None, "configured": wa.available if wa else False},
        },
    }
