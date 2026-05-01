"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS WORKFLOW ENGINE — Automated Multi-step Pipelines
  Chain tools, AI calls, and system actions into powerful workflows
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    TOOL      = "tool"         # Run a tool from the registry
    AI_PROMPT = "ai_prompt"    # Generate AI response
    CONDITION = "condition"    # If/else branching
    LOOP      = "loop"         # Repeat N times
    DELAY     = "delay"        # Wait n seconds
    PARALLEL  = "parallel"     # Run multiple steps concurrently
    WEBHOOK   = "webhook"      # HTTP call to external service
    TRANSFORM = "transform"    # Transform data with expression


@dataclass
class WorkflowStep:
    id: str
    name: str
    step_type: StepType
    config: Dict[str, Any]          # tool_name, prompt, seconds, etc.
    on_success: Optional[str] = None   # next step id
    on_failure: Optional[str] = None   # failure handler step id
    timeout_secs: float = 30.0
    retries: int = 0


@dataclass
class WorkflowRun:
    id: str
    workflow_id: str
    status: str = "pending"        # pending | running | completed | failed | cancelled
    started_at: float = 0.0
    finished_at: float = 0.0
    current_step: str = ""
    results: Dict[str, Any] = field(default_factory=dict)    # step_id -> result
    errors: List[dict] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    created_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    run_count: int = 0
    last_run: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
#  ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowEngine:
    """
    Orchestrates multi-step automated workflows.

    Example workflow:
        1. Web search for topic
        2. AI summarize results
        3. Write summary to file
        4. Send notification
    """

    def __init__(self) -> None:
        self._workflows: Dict[str, Workflow] = {}
        self._runs: Dict[str, WorkflowRun] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}

        # Pre-register built-in workflows
        self._register_builtins()
        logger.info("[WORKFLOW] ⚡ Workflow Engine online — %d built-in workflows.", len(self._workflows))

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create_workflow(self, name: str, description: str, steps: List[dict], tags: List[str] = None) -> Workflow:
        wf_id = f"wf_{uuid.uuid4().hex[:8]}"
        parsed_steps = []
        for i, s in enumerate(steps):
            parsed_steps.append(WorkflowStep(
                id=s.get("id", f"step_{i}"),
                name=s.get("name", f"Step {i+1}"),
                step_type=StepType(s.get("step_type", "tool")),
                config=s.get("config", {}),
                on_success=s.get("on_success"),
                on_failure=s.get("on_failure"),
                timeout_secs=s.get("timeout_secs", 30.0),
                retries=s.get("retries", 0),
            ))
        wf = Workflow(id=wf_id, name=name, description=description, steps=parsed_steps, tags=tags or [])
        self._workflows[wf_id] = wf
        return wf

    def get_workflow(self, wf_id: str) -> Optional[Workflow]:
        return self._workflows.get(wf_id)

    def list_workflows(self) -> List[dict]:
        return [
            {"id": w.id, "name": w.name, "description": w.description,
             "steps": len(w.steps), "run_count": w.run_count, "tags": w.tags}
            for w in self._workflows.values()
        ]

    def delete_workflow(self, wf_id: str) -> bool:
        return self._workflows.pop(wf_id, None) is not None

    # ── Execution ─────────────────────────────────────────────────────────────

    async def run_workflow(self, wf_id: str, input_data: Dict[str, Any] = None) -> WorkflowRun:
        wf = self._workflows.get(wf_id)
        if not wf:
            raise ValueError(f"Workflow {wf_id} not found")

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        run = WorkflowRun(
            id=run_id,
            workflow_id=wf_id,
            status="running",
            started_at=time.time(),
            input_data=input_data or {},
        )
        self._runs[run_id] = run
        wf.run_count += 1
        wf.last_run = run_id

        # Execute in background
        task = asyncio.create_task(self._execute(wf, run))
        self._running_tasks[run_id] = task
        return run

    async def _execute(self, wf: Workflow, run: WorkflowRun) -> None:
        context = deepcopy(run.input_data)  # shared data across steps

        try:
            for step in wf.steps:
                run.current_step = step.id
                logger.info(f"[WORKFLOW] Executing step '{step.name}' ({step.step_type.value})")

                retries_left = step.retries
                while True:
                    try:
                        result = await asyncio.wait_for(
                            self._execute_step(step, context),
                            timeout=step.timeout_secs,
                        )
                        run.results[step.id] = result
                        # Inject result into context for next steps
                        context[f"step_{step.id}_result"] = result
                        break

                    except asyncio.TimeoutError:
                        if retries_left > 0:
                            retries_left -= 1
                            logger.warning(f"[WORKFLOW] Step '{step.name}' timed out, retrying ({retries_left} left)")
                            continue
                        run.errors.append({"step": step.id, "error": "Timeout", "ts": time.time()})
                        if step.on_failure:
                            # Jump to failure handler
                            fail_step = next((s for s in wf.steps if s.id == step.on_failure), None)
                            if fail_step:
                                await self._execute_step(fail_step, context)
                        break

                    except Exception as e:
                        if retries_left > 0:
                            retries_left -= 1
                            await asyncio.sleep(1)
                            continue
                        run.errors.append({"step": step.id, "error": str(e), "ts": time.time()})
                        logger.error(f"[WORKFLOW] Step '{step.name}' failed: {e}")
                        if step.on_failure:
                            fail_step = next((s for s in wf.steps if s.id == step.on_failure), None)
                            if fail_step:
                                await self._execute_step(fail_step, context)
                        break

            run.status = "completed" if not run.errors else "completed_with_errors"
        except Exception as e:
            run.status = "failed"
            run.errors.append({"step": "engine", "error": str(e), "ts": time.time()})
        finally:
            run.finished_at = time.time()
            self._running_tasks.pop(run.id, None)

    async def _execute_step(self, step: WorkflowStep, context: dict) -> Any:
        """Execute a single workflow step."""

        if step.step_type == StepType.TOOL:
            from app.tools.igris_tools import get_tool_registry
            registry = get_tool_registry()
            tool_name = step.config.get("tool_name", "")
            # Resolve kwargs from context
            kwargs = {}
            for k, v in step.config.get("kwargs", {}).items():
                if isinstance(v, str) and v.startswith("$"):
                    kwargs[k] = context.get(v[1:], v)
                else:
                    kwargs[k] = v
            return registry.run(tool_name, **kwargs)

        elif step.step_type == StepType.AI_PROMPT:
            from app.core.llm_manager import universal_llm
            system = step.config.get("system_prompt", "You are Igris, a supreme AI.")
            user = step.config.get("user_prompt", "")
            # Interpolate context vars
            for k, v in context.items():
                user = user.replace(f"${{{k}}}", str(v))
            return await universal_llm.generate_response(system, user)

        elif step.step_type == StepType.CONDITION:
            expr = step.config.get("expression", "True")
            # Simple eval with context
            try:
                result = eval(expr, {"__builtins__": {}}, context)  # nosec
                return {"condition": expr, "result": bool(result)}
            except Exception:
                return {"condition": expr, "result": False}

        elif step.step_type == StepType.DELAY:
            secs = step.config.get("seconds", 1)
            await asyncio.sleep(secs)
            return {"delayed": secs}

        elif step.step_type == StepType.PARALLEL:
            sub_steps = step.config.get("steps", [])
            tasks = []
            for sub in sub_steps:
                ss = WorkflowStep(
                    id=sub.get("id", "sub"),
                    name=sub.get("name", "parallel"),
                    step_type=StepType(sub.get("step_type", "tool")),
                    config=sub.get("config", {}),
                )
                tasks.append(self._execute_step(ss, context))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [str(r) if isinstance(r, Exception) else r for r in results]

        elif step.step_type == StepType.TRANSFORM:
            # Apply a simple transformation expression
            expr = step.config.get("expression", "")
            try:
                return eval(expr, {"__builtins__": {}}, context)  # nosec
            except Exception as e:
                return {"error": str(e)}

        elif step.step_type == StepType.WEBHOOK:
            import aiohttp
            url = step.config.get("url", "")
            method = step.config.get("method", "GET").upper()
            headers = step.config.get("headers", {})
            body = step.config.get("body", {})
            async with aiohttp.ClientSession() as sess:
                if method == "GET":
                    async with sess.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        return {"status": r.status, "body": (await r.text())[:2000]}
                else:
                    async with sess.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                        return {"status": r.status, "body": (await r.text())[:2000]}

        return {"error": f"Unknown step type: {step.step_type}"}

    # ── Cancellation ──────────────────────────────────────────────────────────

    def cancel_run(self, run_id: str) -> bool:
        task = self._running_tasks.get(run_id)
        if task:
            task.cancel()
            run = self._runs.get(run_id)
            if run:
                run.status = "cancelled"
                run.finished_at = time.time()
            return True
        return False

    # ── Run history ───────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[dict]:
        run = self._runs.get(run_id)
        return asdict(run) if run else None

    def list_runs(self, wf_id: str = None, limit: int = 20) -> List[dict]:
        runs = list(self._runs.values())
        if wf_id:
            runs = [r for r in runs if r.workflow_id == wf_id]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return [asdict(r) for r in runs[:limit]]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        total_runs = len(self._runs)
        completed = sum(1 for r in self._runs.values() if "completed" in r.status)
        failed    = sum(1 for r in self._runs.values() if r.status == "failed")

        return {
            "workflows_count": len(self._workflows),
            "total_runs": total_runs,
            "completed_runs": completed,
            "failed_runs": failed,
            "running_now": len(self._running_tasks),
            "success_rate": round(completed / total_runs * 100, 1) if total_runs else 100.0,
        }

    # ── Built-in Workflows ────────────────────────────────────────────────────

    def _register_builtins(self) -> None:
        # 1. Research & Summarize
        self.create_workflow(
            name="Research & Summarize",
            description="Search web for a topic, summarize results with AI, save to file",
            tags=["research", "ai", "web"],
            steps=[
                {"id": "search", "name": "Web Search", "step_type": "tool",
                 "config": {"tool_name": "web_search", "kwargs": {"query": "$topic", "max_results": 5}}},
                {"id": "summarize", "name": "AI Summarize", "step_type": "ai_prompt",
                 "config": {"system_prompt": "Summarize these search results concisely.",
                            "user_prompt": "Topic: ${topic}\nResults: ${step_search_result}"}},
                {"id": "save", "name": "Save to File", "step_type": "tool",
                 "config": {"tool_name": "write_file", "kwargs": {"path": "research_output.md", "content": "$step_summarize_result"}}},
            ]
        )

        # 2. System Health Check
        self.create_workflow(
            name="Full System Diagnostic",
            description="Comprehensive system health check with metrics and analysis",
            tags=["system", "health"],
            steps=[
                {"id": "metrics", "name": "Gather Metrics", "step_type": "tool",
                 "config": {"tool_name": "system_info"}},
                {"id": "analyze", "name": "AI Analysis", "step_type": "ai_prompt",
                 "config": {"system_prompt": "You are a system diagnostics expert. Analyze these metrics and provide recommendations.",
                            "user_prompt": "System metrics: ${step_metrics_result}"}},
            ]
        )

        # 3. Code Review Pipeline
        self.create_workflow(
            name="AI Code Review",
            description="Read a file, review it with AI, write review notes",
            tags=["code", "review", "ai"],
            steps=[
                {"id": "read", "name": "Read Source", "step_type": "tool",
                 "config": {"tool_name": "read_file", "kwargs": {"path": "$file_path"}}},
                {"id": "review", "name": "AI Review", "step_type": "ai_prompt",
                 "config": {"system_prompt": "You are a senior code reviewer. Find bugs, suggest improvements, rate quality 1-10.",
                            "user_prompt": "Review this code:\n${step_read_result}"}},
                {"id": "save_review", "name": "Save Review", "step_type": "tool",
                 "config": {"tool_name": "write_file", "kwargs": {"path": "code_review.md", "content": "$step_review_result"}}},
            ]
        )


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    global _instance
    if _instance is None:
        _instance = WorkflowEngine()
    return _instance
