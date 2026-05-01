"""
Voice Control and Self-Modification API Routes
"""

from fastapi import APIRouter, WebSocket, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import json
import logging

from app.core.voice_control import voice_command_handler
from app.core.self_modification import self_modification_system
from app.core.cloud_ai import cloud_ai
from app.core import api_auth
from app.core.security import security_manager, permission_manager

# Optional but not required
try:
    from app.core.ai_core import brain
except ImportError:
    brain = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice-control"])


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    language: str = "ur-PK"
    use_cloud_ai: bool = True


class ModifyFunctionRequest(BaseModel):
    module_name: str = Field(..., min_length=1)
    function_name: str = Field(..., min_length=1)
    new_logic: str = Field(..., min_length=1)


class ModifyParameterRequest(BaseModel):
    system_name: str = Field(..., min_length=1)
    param_name: str = Field(..., min_length=1)
    param_value: Any


class AddCapabilityRequest(BaseModel):
    module_name: str = Field(..., min_length=1)
    capability_code: str = Field(..., min_length=1)


class RollbackRequest(BaseModel):
    modification_id: int = Field(..., ge=0)


class AutoModeRequest(BaseModel):
    enabled: bool = True


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1)


def require_admin_role(request: Request) -> None:
    """
    Guard for destructive self-modification routes.
    Prefer JWT role verification; fallback to legacy X-IGRIS-Role flow.
    """
    if not api_auth.is_auth_enabled():
        raise HTTPException(
            status_code=403,
            detail="Self-modification requires IGRIS_API_TOKEN to be enabled.",
        )
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        valid, payload = security_manager.verify_jwt_token(token)
        if valid and permission_manager.has_permission(payload.get("role", "user"), "admin"):
            return

    # Legacy fallback for older clients.
    if not api_auth.verify_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if (request.headers.get("x-igris-role") or "").strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

# Store for dependency injection
_dependencies = {
    "brain": None,
    "sys_ctrl": None
}

def set_dependencies(brain_instance, sys_ctrl_instance):
    """Set dependencies"""
    _dependencies["brain"] = brain_instance
    _dependencies["sys_ctrl"] = sys_ctrl_instance


@router.post("/process-command")
async def process_voice_command(data: VoiceCommandRequest):
    """
    Process voice command with auto execution + Cloud AI response
    """
    transcript = data.transcript
    language = data.language
    use_cloud_ai = data.use_cloud_ai
    
    # Process command through voice handler
    result = await voice_command_handler.process_voice_command(transcript, language)
    
    # If command was executed and use_cloud_ai is enabled, get AI response
    if use_cloud_ai and result.get("status") == "success":
        try:
            ai_response = await cloud_ai.generate(transcript)
            result["ai_response"] = ai_response
            result["provider"] = cloud_ai.active_provider
        except Exception as e:
            logger.error(f"Cloud AI error: {str(e)}")
            result["ai_response"] = "خرابی! Cloud AI سے جواب نہیں ملا۔"
    
    return result


@router.get("/auto-mode")
async def get_auto_mode():
    """Get current auto mode status"""
    return {
        "auto_mode": voice_command_handler.auto_mode,
        "confidence_threshold": voice_command_handler.command_confidence_threshold
    }


@router.post("/auto-mode")
async def set_auto_mode_json(body: AutoModeRequest):
    """Set auto mode (body: ``{ \"enabled\": true }``) — used by the web client tests."""
    return voice_command_handler.set_auto_mode(body.enabled)


@router.post("/auto-mode/toggle")
async def toggle_auto_mode(enabled: bool = True):
    """Enable or disable auto mode"""
    result = voice_command_handler.set_auto_mode(enabled)
    return result


@router.get("/commands")
async def get_registered_commands():
    """Get list of all registered voice commands"""
    return voice_command_handler.get_registered_commands()


@router.get("/voice-log")
async def get_voice_log(limit: int = 100):
    """Get voice command log"""
    return {
        "total": len(voice_command_handler.voice_log),
        "log": voice_command_handler.get_voice_log(limit)
    }


@router.get("/log")
async def get_voice_log_alias(limit: int = 100):
    """Alias of ``/voice-log`` for older clients and tests."""
    return {
        "total": len(voice_command_handler.voice_log),
        "log": voice_command_handler.get_voice_log(limit)
    }


@router.get("/status")
async def get_voice_status():
    """High-level voice subsystem status for dashboards."""
    reg = voice_command_handler.get_registered_commands()
    n = len(reg) if reg is not None and hasattr(reg, "__len__") else 0
    return {
        "ok":                  True,
        "auto_mode":         voice_command_handler.auto_mode,
        "confidence":        voice_command_handler.command_confidence_threshold,
        "commands_registered": n,
    }


@router.post("/speak")
async def post_voice_speak(body: SpeakRequest):
    """TTS queue hook — returns OK; actual audio depends on local TTS availability."""
    return {"ok": True, "text": body.text, "method": "echo"}


# Self-Modification Routes

@router.post("/modify/function")
async def modify_function(
    data: ModifyFunctionRequest,
    _admin_guard: None = Depends(require_admin_role),
):
    """
    AI modifies its own function
    
    Required fields:
    - module_name: str
    - function_name: str
    - new_logic: str
    """
    result = self_modification_system.modify_function(
        data.module_name,
        data.function_name,
        data.new_logic
    )
    return result


@router.post("/modify/parameter")
async def modify_parameter(
    data: ModifyParameterRequest,
    _admin_guard: None = Depends(require_admin_role),
):
    """
    AI modifies system parameters
    
    Required fields:
    - system_name: str
    - param_name: str
    - param_value: Any
    """
    result = self_modification_system.modify_parameter(
        data.system_name,
        data.param_name,
        data.param_value
    )
    return result


@router.post("/modify/capability")
async def add_capability(
    data: AddCapabilityRequest,
    _admin_guard: None = Depends(require_admin_role),
):
    """
    AI adds new capability to itself
    
    Required fields:
    - module_name: str
    - capability_code: str
    """
    result = self_modification_system.add_capability(
        data.module_name,
        data.capability_code
    )
    return result


@router.post("/modify/rollback")
async def rollback_modification(
    data: RollbackRequest,
    _admin_guard: None = Depends(require_admin_role),
):
    """
    Rollback a previous modification
    
    Required fields:
    - modification_id: int
    """
    result = self_modification_system.rollback_modification(
        data.modification_id
    )
    return result


@router.get("/modify/history")
async def get_modification_history():
    """Get history of all modifications"""
    return {
        "total_modifications": len(self_modification_system.modification_history),
        "history": self_modification_system.get_modification_history()
    }


# Integrated WebSocket for voice + modification

@router.websocket("/ws/voice-control")
async def websocket_voice_control(websocket: WebSocket):
    """
    WebSocket for real-time voice control and auto-execution
    """
    auth = websocket.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    supplied = (
        websocket.headers.get("x-igris-token")
        or websocket.query_params.get("token")
        or bearer
    )
    if not api_auth.verify_ws_token(supplied):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "voice_command":
                result = await voice_command_handler.process_voice_command(
                    data.get("transcript", ""),
                    data.get("language", "ur-PK")
                )
                await websocket.send_json(result)
            
            elif data.get("type") == "modify":
                mod_type = data.get("modification_type", "function")
                
                if mod_type == "function":
                    result = self_modification_system.modify_function(
                        data.get("module_name"),
                        data.get("function_name"),
                        data.get("new_logic")
                    )
                elif mod_type == "parameter":
                    result = self_modification_system.modify_parameter(
                        data.get("system_name"),
                        data.get("param_name"),
                        data.get("param_value")
                    )
                elif mod_type == "capability":
                    result = self_modification_system.add_capability(
                        data.get("module_name"),
                        data.get("capability_code")
                    )
                else:
                    result = {"status": "error", "message": "Unknown modification type"}
                
                await websocket.send_json(result)
            
            elif data.get("type") == "status":
                await websocket.send_json({
                    "auto_mode": voice_command_handler.auto_mode,
                    "total_modifications": len(self_modification_system.modification_history),
                    "registered_commands": len(voice_command_handler.command_registry)
                })
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=1000)
        except:
            pass
