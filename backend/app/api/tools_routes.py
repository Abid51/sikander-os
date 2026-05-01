"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS TOOLS API ROUTES
  Exposes all tools (web search, calculator, code sandbox, etc.) via REST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core import api_auth
from app.tools.igris_tools import get_tool_registry

router = APIRouter(prefix="/tools", tags=["Tools"])
_reg = get_tool_registry()
def _require_sensitive_tool_auth(request: Request) -> None:
    if not api_auth.is_auth_enabled():
        allow_open = os.getenv("IGRIS_ALLOW_OPEN_AUTH", "").strip().lower() in {"1", "true", "yes"}
        env = (os.getenv("IGRIS_ENV") or "").strip().lower()
        if allow_open and env in {"dev", "development", "local", "test"}:
            return
        raise HTTPException(
            status_code=503,
            detail="Sensitive tools are disabled until IGRIS_API_TOKEN is configured.",
        )
    if not api_auth.verify_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized")




# ─────────────────────────────────────────────────────────────────────────────
#  REQUEST MODELS
# ─────────────────────────────────────────────────────────────────────────────

class WebSearchRequest(BaseModel):
    query:       str
    max_results: int = 5

class FetchPageRequest(BaseModel):
    url: str

class CalculateRequest(BaseModel):
    expression: str

class RunPythonRequest(BaseModel):
    code: str

class ListDirRequest(BaseModel):
    path: str = ""

class ReadFileRequest(BaseModel):
    path:      str
    max_chars: int = 8000

class WriteFileRequest(BaseModel):
    path:    str
    content: str
    append:  bool = False

class SearchFilesRequest(BaseModel):
    query:      str
    path:       str = ""
    ext_filter: str = ""

class ParseJsonRequest(BaseModel):
    raw: str

class SummariseRequest(BaseModel):
    data: List[Dict[str, Any]]

class GenericToolRequest(BaseModel):
    tool_name: str
    kwargs:    Dict[str, Any] = {}


# ─────────────────────────────────────────────────────────────────────────────
#  ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/list")
async def list_tools():
    """Return all available tools and their argument schemas."""
    return {"tools": _reg.available_tools()}


@router.post("/web/search")
async def web_search(req: WebSearchRequest):
    """Search the web via DuckDuckGo (no API key required)."""
    try:
        results = _reg.web.search(req.query, req.max_results)
        return {"query": req.query, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/web/fetch")
async def fetch_page(req: FetchPageRequest):
    """Fetch plain text content of a web page."""
    try:
        content = _reg.web.fetch_page(req.url)
        return {"url": req.url, "content": content, "chars": len(content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate")
async def calculate(req: CalculateRequest):
    """Evaluate a math expression safely."""
    result = _reg.calc.evaluate(req.expression)
    if result["error"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/code/run")
async def run_python_code(req: RunPythonRequest, request: Request):
    """Execute Python code in an isolated subprocess sandbox."""
    _require_sensitive_tool_auth(request)
    result = _reg.sandbox.run(req.code)
    return result


@router.get("/files/list")
async def list_directory(path: str = ""):
    """List directory contents within workspace."""
    try:
        return _reg.files.list_dir(path)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/read")
async def read_file(req: ReadFileRequest):
    """Read file contents from workspace."""
    try:
        return _reg.files.read_file(req.path, req.max_chars)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/files/write")
async def write_file(req: WriteFileRequest, request: Request):
    """Write or append content to a file in workspace."""
    _require_sensitive_tool_auth(request)
    try:
        return _reg.files.write_file(req.path, req.content, req.append)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/search")
async def search_files(req: SearchFilesRequest):
    """Search file contents for a string across workspace."""
    try:
        return _reg.files.search_files(req.query, req.path, req.ext_filter)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/system/info")
async def system_info():
    """Live CPU, memory, disk, and top processes snapshot."""
    return _reg.sysinfo.snapshot()


@router.post("/data/parse-json")
async def parse_json_data(req: ParseJsonRequest):
    """Parse a raw JSON string and return structured data."""
    result = _reg.data.parse_json(req.raw)
    if result["error"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/data/summarise")
async def summarise_data(req: SummariseRequest):
    """Return statistical summary for a list of dicts."""
    return _reg.data.summarise(req.data)


@router.post("/run")
async def run_generic_tool(req: GenericToolRequest, request: Request):
    """
    Generic tool runner — pass any registered tool name + kwargs.
    Useful for AI agent tool-calling via a single endpoint.
    """
    _require_sensitive_tool_auth(request)
    try:
        result = _reg.run(req.tool_name, **req.kwargs)
        if isinstance(result, dict) and "error" in result and result["error"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"tool": req.tool_name, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
