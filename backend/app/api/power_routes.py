"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS POWER ROUTES — Workflow, Scheduler, Self-Healing, Plugin APIs
  GOD-TIER enhancement endpoints
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["power-systems"])


# ─────────────────────────────────────────────────────────────────────────────
#  REQUEST MODELS
# ─────────────────────────────────────────────────────────────────────────────

class CreateWorkflowRequest(BaseModel):
    name: str
    description: str
    steps: List[Dict[str, Any]]
    tags: List[str] = []

class RunWorkflowRequest(BaseModel):
    workflow_id: str
    input_data: Dict[str, Any] = {}

class CreateScheduleRequest(BaseModel):
    name: str
    job_type: str = "interval"
    action_type: str = "tool"
    action_config: Dict[str, Any] = {}
    interval_secs: float = 0
    run_at_hour: int = -1
    run_at_minute: int = 0
    tags: List[str] = []

class SnapshotRequest(BaseModel):
    file_path: str

class RollbackRequest(BaseModel):
    file_path: str


# ══════════════════════════════════════════════════════════════════════════════
#  WORKFLOW ENGINE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/workflows")
async def list_workflows():
    """List all registered workflows."""
    from app.core.workflow_engine import get_workflow_engine
    engine = get_workflow_engine()
    return {"workflows": engine.list_workflows(), "stats": engine.get_stats()}


@router.post("/workflows")
async def create_workflow(req: CreateWorkflowRequest):
    """Create a new automation workflow."""
    from app.core.workflow_engine import get_workflow_engine
    engine = get_workflow_engine()
    wf = engine.create_workflow(req.name, req.description, req.steps, req.tags)
    return {"status": "created", "workflow_id": wf.id, "name": wf.name, "steps": len(wf.steps)}


@router.post("/workflows/run")
async def run_workflow(req: RunWorkflowRequest):
    """Execute a workflow with input data."""
    from app.core.workflow_engine import get_workflow_engine
    engine = get_workflow_engine()
    try:
        run = await engine.run_workflow(req.workflow_id, req.input_data)
        return {"status": "started", "run_id": run.id, "workflow_id": run.workflow_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/workflows/runs")
async def list_runs(workflow_id: str = None, limit: int = 20):
    """List workflow run history."""
    from app.core.workflow_engine import get_workflow_engine
    engine = get_workflow_engine()
    return {"runs": engine.list_runs(workflow_id, limit)}


@router.get("/workflows/runs/{run_id}")
async def get_run(run_id: str):
    """Get details of a specific workflow run."""
    from app.core.workflow_engine import get_workflow_engine
    engine = get_workflow_engine()
    run = engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/workflows/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running workflow."""
    from app.core.workflow_engine import get_workflow_engine
    engine = get_workflow_engine()
    ok = engine.cancel_run(run_id)
    return {"cancelled": ok}


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow."""
    from app.core.workflow_engine import get_workflow_engine
    engine = get_workflow_engine()
    ok = engine.delete_workflow(workflow_id)
    return {"deleted": ok}


@router.get("/workflows/stats")
async def workflow_stats():
    """Get workflow engine statistics."""
    from app.core.workflow_engine import get_workflow_engine
    return get_workflow_engine().get_stats()


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/scheduler/jobs")
async def list_scheduled_jobs():
    """List all scheduled jobs."""
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    return {"jobs": scheduler.list_jobs(), "stats": scheduler.get_stats()}


@router.post("/scheduler/jobs")
async def create_scheduled_job(req: CreateScheduleRequest):
    """Create a new scheduled job."""
    from app.core.scheduler import get_scheduler
    scheduler = get_scheduler()
    job = scheduler.add_job(
        name=req.name,
        job_type=req.job_type,
        action_type=req.action_type,
        action_config=req.action_config,
        interval_secs=req.interval_secs,
        run_at_hour=req.run_at_hour,
        run_at_minute=req.run_at_minute,
        tags=req.tags,
    )
    return {"status": "created", "job_id": job.id, "name": job.name, "next_run": job.next_run}


@router.delete("/scheduler/jobs/{job_id}")
async def remove_scheduled_job(job_id: str):
    """Remove a scheduled job."""
    from app.core.scheduler import get_scheduler
    ok = get_scheduler().remove_job(job_id)
    return {"removed": ok}


@router.post("/scheduler/jobs/{job_id}/toggle")
async def toggle_job(job_id: str, enabled: bool = True):
    """Enable or disable a job."""
    from app.core.scheduler import get_scheduler
    ok = get_scheduler().enable_job(job_id, enabled)
    return {"toggled": ok, "enabled": enabled}


@router.get("/scheduler/stats")
async def scheduler_stats():
    """Get scheduler statistics."""
    from app.core.scheduler import get_scheduler
    return get_scheduler().get_stats()


# ══════════════════════════════════════════════════════════════════════════════
#  SELF-HEALING ENGINE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/healer/stats")
async def healer_stats():
    """Get self-healing engine statistics."""
    from app.core.self_healing import get_self_healing_engine
    return get_self_healing_engine().get_stats()


@router.get("/healer/errors")
async def healer_errors(limit: int = 50):
    """Get captured error history."""
    from app.core.self_healing import get_self_healing_engine
    return {"errors": get_self_healing_engine().get_error_history(limit)}


@router.post("/healer/snapshot")
async def take_snapshot(req: SnapshotRequest):
    """Take a backup snapshot of a file."""
    from app.core.self_healing import get_self_healing_engine
    snap = get_self_healing_engine().snapshot(req.file_path)
    if snap:
        return {"status": "snapshot_taken", "hash": snap.content_hash, "backup": snap.backup_path}
    raise HTTPException(status_code=404, detail="File not found or snapshot failed")


@router.post("/healer/rollback")
async def rollback_file(req: RollbackRequest):
    """Rollback a file to its last snapshot."""
    from app.core.self_healing import get_self_healing_engine
    msg = get_self_healing_engine().rollback(req.file_path)
    return {"status": msg}


@router.get("/healer/snapshots")
async def list_snapshots(file_path: str = None):
    """List all file snapshots."""
    from app.core.self_healing import get_self_healing_engine
    return get_self_healing_engine().get_snapshots(file_path)


@router.get("/healer/health")
async def health_report():
    """Get health report for all monitored components."""
    from app.core.self_healing import get_self_healing_engine
    return get_self_healing_engine().get_health_report()


# ══════════════════════════════════════════════════════════════════════════════
#  PLUGIN SYSTEM ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/plugins")
async def list_plugins():
    """List all loaded plugins."""
    from app.core.plugin_loader import get_plugin_loader
    return {"plugins": get_plugin_loader().list_plugins(), "stats": get_plugin_loader().get_stats()}


@router.post("/plugins/load")
async def load_all_plugins():
    """Scan and load all plugins from the plugins directory."""
    from app.core.plugin_loader import get_plugin_loader
    results = get_plugin_loader().load_all()
    return {"status": "loaded", "results": results}


@router.post("/plugins/{name}/unload")
async def unload_plugin(name: str):
    """Unload a specific plugin."""
    from app.core.plugin_loader import get_plugin_loader
    ok = get_plugin_loader().unload_plugin(name)
    return {"unloaded": ok}


@router.post("/plugins/{name}/reload")
async def reload_plugin(name: str):
    """Reload a specific plugin."""
    from app.core.plugin_loader import get_plugin_loader
    result = get_plugin_loader().reload_plugin(name)
    return {"status": result}


@router.get("/plugins/{name}/status")
async def get_plugin_status(name: str):
    """Get detailed plugin status."""
    from app.core.plugin_loader import get_plugin_loader
    status = get_plugin_loader().get_plugin_status(name)
    if not status:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return status


@router.get("/plugins/stats")
async def plugin_stats():
    """Get plugin system statistics."""
    from app.core.plugin_loader import get_plugin_loader
    return get_plugin_loader().get_stats()
