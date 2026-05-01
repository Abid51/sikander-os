from fastapi import APIRouter, HTTPException, UploadFile, File, Request
import json
import os
import asyncio
import time
import logging

logger = logging.getLogger(__name__)
from app.core.multi_agent_orchestrator import (
    MultiAgentOrchestrator, Task, AgentRole
)
from app.core import api_auth

router = APIRouter(prefix="/api", tags=["igris"])

# Reference to shared brain - will be set by main.py
shared_brain = None
shared_sys_ctrl = None
orchestrator = MultiAgentOrchestrator(agent_pool_size=10)


def _require_sensitive_auth(request: Request) -> None:
    if not api_auth.verify_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not api_auth.is_auth_enabled():
        raise HTTPException(
            status_code=503,
            detail="Sensitive endpoint disabled until IGRIS_API_TOKEN is configured.",
        )

def set_dependencies(brain, sys_ctrl):
    """Set the shared brain and system controller instances."""
    global shared_brain, shared_sys_ctrl
    shared_brain = brain
    shared_sys_ctrl = sys_ctrl

# ==================== MEMORY ROUTES ====================

@router.get("/memory/retrieve")
async def retrieve_memory(query: str = None):
    """Retrieve memory data."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        if query:
            # Search in history
            results = [h for h in shared_brain.memory.get("history", []) 
                      if query.lower() in str(h).lower()]
            return {"results": results, "query": query}
        
        return {"memory": shared_brain.memory}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/memory/save")
async def save_memory(data: dict):
    """Save custom memory data."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        shared_brain.memory.update(data)
        shared_brain.save_memory()
        return {"status": "saved", "memory": shared_brain.memory}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/memory/clear")
async def clear_memory():
    """Clear memory history."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        shared_brain.memory["history"] = []
        shared_brain.save_memory()
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== AGENT ROUTES ====================

@router.get("/agents/list")
async def list_agents():
    """List all active agents and daemons."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        daemons = {
            "blood_ward": shared_brain.blood_ward_active,
            "dominion": shared_brain.dominion_active,
            "phantom_recon": shared_brain.phantom_recon_active,
            "necromancy": shared_brain.necromancy_active,
            "soul_link": shared_brain.soul_link_active,
            "dream_space": shared_brain.dream_space_active,
            "singularity": shared_brain.singularity_active,
            "akashic": shared_brain.akashic_active,
            "omnipresence": shared_brain.omnipresence_active,
            "chronos": shared_brain.chronos_active,
            "legion": shared_brain.legion_active,
            "gods_eye": shared_brain.gods_eye_active,
        }
        return {
            "daemons": daemons,
            "shadow_army": shared_brain.shadow_army,
            "active_model": shared_brain.active_model
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/agents/spawn")
async def spawn_agent(agent_name: str, purpose: str):
    """Spawn a new shadow agent."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        result = shared_brain.spawn_shadow_agent(agent_name, purpose)
        return {"status": "spawned", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/agents/toggle-daemon")
async def toggle_daemon(daemon_name: str, state: bool):
    """Toggle a daemon on/off."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        if hasattr(shared_brain, f"{daemon_name}_active"):
            setattr(shared_brain, f"{daemon_name}_active", state)
            return {"status": f"{daemon_name} set to {state}"}
        raise HTTPException(status_code=400, detail=f"Daemon {daemon_name} not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== MODEL ROUTES ====================

@router.get("/models/available")
async def get_available_models():
    """Get list of available models."""
    models = [
        {"id": "igris-core", "name": "Igris Core (Local)", "type": "local"},
        {"id": "llama3", "name": "Llama 3 (Ollama)", "type": "local"},
        {"id": "mixtral", "name": "Mixtral (Ollama)", "type": "local"},
        {"id": "dolphin-mixtral", "name": "Dolphin Mixtral (Ollama)", "type": "local"},
        {"id": "gpt-4o", "name": "GPT-4o", "type": "api"},
        {"id": "claude-3-5", "name": "Claude 3.5 Sonnet", "type": "api"},
    ]
    return {"models": models}

@router.get("/models/current")
async def get_current_model():
    """Get currently active model."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    return {"current_model": shared_brain.active_model}

@router.post("/models/switch")
async def switch_model(model_name: str):
    """Switch to a different model."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        result = shared_brain.execute_tool("pull_and_switch_model", {"model_name": model_name})
        return {"status": "switched", "result": result, "current_model": shared_brain.active_model}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== SYSTEM ROUTES ====================

@router.get("/system/info")
async def get_system_info():
    """Get detailed system information."""
    if not shared_sys_ctrl:
        raise HTTPException(status_code=500, detail="System controller not initialized")
    
    try:
        result = shared_sys_ctrl.get_system_info()
        return {"system_info": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/system/execute-command")
async def execute_command(command: str, request: Request):
    """Execute a terminal command."""
    if not shared_sys_ctrl:
        raise HTTPException(status_code=500, detail="System controller not initialized")
    _require_sensitive_auth(request)
    
    try:
        # Security check - verify non-destructive
        dangerous_keywords = ["del", "rm", "format", "diskpart", "dd if="]
        if any(kw in command.lower() for kw in dangerous_keywords):
            raise HTTPException(status_code=403, detail="Destructive command rejected. Use API with explicit LLM approval.")
        
        result = shared_sys_ctrl.execute_terminal(command)
        return {"command": command, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/system/execute-python")
async def execute_python(code: str, request: Request):
    """Execute Python code."""
    if not shared_sys_ctrl:
        raise HTTPException(status_code=500, detail="System controller not initialized")
    _require_sensitive_auth(request)
    raise HTTPException(
        status_code=403,
        detail="Python execution endpoint is disabled for security hardening.",
    )

# ==================== FILE ROUTES ====================

@router.get("/files/read")
async def read_file_route(path: str):
    """Read a file."""
    if not shared_sys_ctrl:
        raise HTTPException(status_code=500, detail="System controller not initialized")
    
    try:
        result = shared_sys_ctrl.read_file(path)
        return {"path": path, "content": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/files/write")
async def write_file_route(path: str, content: str):
    """Write to a file."""
    if not shared_sys_ctrl:
        raise HTTPException(status_code=500, detail="System controller not initialized")
    
    try:
        result = shared_sys_ctrl.write_file(path, content)
        return {"path": path, "status": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/files/list")
async def list_files(path: str):
    """List files in a directory."""
    if not shared_sys_ctrl:
        raise HTTPException(status_code=500, detail="System controller not initialized")
    
    try:
        result = shared_sys_ctrl.list_directory(path)
        return {"path": path, "files": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== TOOL ROUTES ====================

@router.post("/tools/execute")
async def execute_tool(tool_name: str, tool_args: dict):
    """Execute a tool dynamically."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        result = shared_brain.execute_tool(tool_name, tool_args)
        return {"tool": tool_name, "args": tool_args, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== UI ROUTES ====================

@router.post("/ui/change-frontend")
async def change_frontend(request: str):
    """Change frontend design dynamically."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        if shared_brain.evolution_engine is None:
            return {"status": "failed", "result": "Evolution engine not available"}
        success, result = shared_brain.evolution_engine.change_frontend(request)
        return {"status": "success" if success else "failed", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ui/change-theme")
async def change_theme(color_theme: str):
    """Change global color theme."""
    if not shared_brain:
        raise HTTPException(status_code=500, detail="Brain not initialized")
    
    try:
        if shared_brain.evolution_engine is None:
            return {"status": "failed", "result": "Evolution engine not available"}
        success, result = shared_brain.evolution_engine.change_theme(color_theme)
        return {"status": "success" if success else "failed", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== HEALTH CHECK ====================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    if not shared_brain:
        return {"status": "degraded", "reason": "Brain not initialized"}
    
    return {
        "status": "healthy",
        "brain_active": True,
        "active_model": shared_brain.active_model,
        "daemons_running": sum([
            shared_brain.blood_ward_active,
            shared_brain.dominion_active,
            shared_brain.phantom_recon_active,
        ])
    }

# ==================== MULTI-AGENT ORCHESTRATOR ROUTES ====================

@router.post("/orchestrator/execute-task")
async def execute_collaborative_task(description: str, input_data: dict, required_roles: list = None):
    """Execute a task using multi-agent collaboration."""
    try:
        if required_roles is None:
            required_roles = ["analyst", "executor", "validator", "optimizer"]
        
        # Convert role strings to AgentRole enums
        roles = [AgentRole[role.upper()] if hasattr(AgentRole, role.upper()) else AgentRole.ANALYST for role in required_roles]
        
        # Create task
        task = Task(
            id=f"task_{int(time.time() * 1000)}",
            description=description,
            required_roles=roles,
            input_data=input_data,
            priority=5
        )
        
        # Execute collaboratively
        result = await orchestrator.execute_collaborative_task(task)
        return result
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orchestrator/stats")
async def get_orchestrator_stats():
    """Get multi-agent orchestrator statistics."""
    try:
        stats = orchestrator.get_orchestrator_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orchestrator/agent-stats/{agent_id}")
async def get_agent_stats(agent_id: str):
    """Get specific agent statistics."""
    try:
        stats = orchestrator.get_agent_stats(agent_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orchestrator/agents")
async def list_orchestrator_agents():
    """List all agents in orchestrator."""
    try:
        agents_info = [{
            "agent_id": agent_id,
            "role": agent.role.value,
            "status": agent.status,
            "tasks_completed": agent.performance_metrics["tasks_completed"],
            "success_rate": agent.performance_metrics["success_rate"]
        } for agent_id, agent in orchestrator.agents.items()]
        
        return {"agents": agents_info, "total_agents": len(agents_info)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== CACHE & PERFORMANCE ROUTES ====================

@router.get("/performance/cache-stats")
async def get_cache_stats():
    """Get cache performance statistics."""
    try:
        from app.core.cloud_ai import AdvancedCache
        
        # This would need to be integrated with actual cloud_ai instance
        return {
            "cache_system": "Advanced Cache with TTL",
            "features": [
                "Automatic TTL expiration",
                "Hash-based key indexing",
                "Auto-eviction on overflow",
                "Hit/miss statistics"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/performance/metrics")
async def get_performance_metrics():
    """Get system performance metrics."""
    try:
        metrics = {
            "orchestrator": orchestrator.performance_stats,
            "agents_active": sum(1 for a in orchestrator.agents.values() if a.status == "executing"),
            "total_agents": len(orchestrator.agents),
            "tasks_in_history": len(orchestrator.task_history)
        }
        return metrics
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
