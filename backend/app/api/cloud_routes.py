from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from app.core.cloud_ai import cloud_ai
from app.core import api_auth
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cloud", tags=["cloud-ai"])

def verify_token(request: Request):
    if not api_auth.verify_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

class CloudChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    use_cache: bool = True

class CloudHistoryRequest(BaseModel):
    messages: List[Dict[str, str]]
    system_prompt: Optional[str] = None

@router.post("/chat", dependencies=[Depends(verify_token)])
async def cloud_chat(data: CloudChatRequest):
    """Generate response via Cloud AI"""
    try:
        response = await cloud_ai.generate(
            prompt=data.prompt,
            system_prompt=data.system_prompt,
            use_cache=data.use_cache
        )
        return {
            "status": "success",
            "response": response,
            "provider": cloud_ai.active_provider,
            "model": cloud_ai.active_model
        }
    except Exception as e:
        logger.error(f"Cloud chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/history", dependencies=[Depends(verify_token)])
async def cloud_chat_history(data: CloudHistoryRequest):
    """Multi-turn chat via Cloud AI"""
    try:
        response = await cloud_ai.chat(
            messages=data.messages,
            system_prompt=data.system_prompt
        )
        return {
            "status": "success",
            "response": response,
            "provider": cloud_ai.active_provider
        }
    except Exception as e:
        logger.error(f"Cloud history error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", dependencies=[Depends(verify_token)])
async def get_cloud_status():
    """Get Cloud AI status and stats"""
    return cloud_ai.get_stats()
