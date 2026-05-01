"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS SCHEDULER — Background Cron-like Job System
  Run tasks at intervals, specific times, or on events
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    id: str
    name: str
    job_type: str            # "interval" | "daily" | "once" | "cron_like"
    action_type: str         # "tool" | "workflow" | "command" | "python"
    action_config: Dict[str, Any]
    enabled: bool = True
    interval_secs: float = 0         # for "interval" type
    run_at_hour: int = -1            # for "daily" (0-23)
    run_at_minute: int = 0           # for "daily" (0-59)
    next_run: float = 0.0
    last_run: float = 0.0
    last_result: str = ""
    last_status: str = "pending"
    run_count: int = 0
    fail_count: int = 0
    max_failures: int = 10           # disable after this many consecutive failures
    created_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)


class Scheduler:
    """
    Igris's background job scheduler.

    Supports:
    • Interval-based jobs (every N seconds)
    • Daily jobs (at specific hour:minute)
    • One-time jobs (run once at a specific time)
    • Tool execution, workflow triggers, Python snippets
    """

    PERSIST_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "scheduler_jobs.json")

    def __init__(self) -> None:
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running_jobs: set[str] = set()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._load()
        logger.info(f"[SCHEDULER] ⚡ Scheduler online — {len(self._jobs)} job(s) loaded.")

    # ── Job Management ────────────────────────────────────────────────────────

    def add_job(
        self,
        name: str,
        job_type: str = None,
        action_type: str = None,
        action_config: Dict[str, Any] = None,
        interval_secs: float = 0,
        interval_seconds: float = 0,
        run_at_hour: int = -1,
        run_at_minute: int = 0,
        tags: List[str] = None,
    ) -> ScheduledJob:
        ival = float(interval_seconds or interval_secs or 0)
        if callable(job_type) and action_type is None:
            return self.add_job(
                name,
                "interval",
                "python",
                {"fn_name": getattr(job_type, "__name__", "job")},
                interval_secs=ival or 60.0,
                tags=tags,
            )
        if action_config is None:
            action_config = {}
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        now = time.time()

        next_run = now
        if job_type == "interval" and ival > 0:
            next_run = now + ival
        elif job_type == "daily" and 0 <= run_at_hour <= 23:
            next_run = self._next_daily_time(run_at_hour, run_at_minute)

        job = ScheduledJob(
            id=job_id,
            name=name,
            job_type=job_type,
            action_type=action_type,
            action_config=action_config,
            interval_secs=ival,
            run_at_hour=run_at_hour,
            run_at_minute=run_at_minute,
            next_run=next_run,
            tags=tags or [],
        )
        self._jobs[job_id] = job
        self._save()
        return job

    def remove_job(self, job_id: str) -> bool:
        removed = self._jobs.pop(job_id, None) is not None
        if removed:
            self._running_jobs.discard(job_id)
            self._save()
        return removed

    def enable_job(self, job_id: str, enabled: bool = True) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.enabled = enabled
        self._save()
        return True

    def list_jobs(self) -> List[dict]:
        return [asdict(j) for j in sorted(self._jobs.values(), key=lambda j: j.next_run)]

    def get_job(self, job_id: str) -> Optional[dict]:
        job = self._jobs.get(job_id)
        return asdict(job) if job else None

    # ── Execution Loop ────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[SCHEDULER] Background loop started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[SCHEDULER] Background loop stopped.")

    async def _loop(self) -> None:
        while self._running:
            now = time.time()
            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                if job.id in self._running_jobs:
                    continue
                if now >= job.next_run:
                    # Claim next run before task starts to avoid duplicate scheduling.
                    if job.job_type == "interval" and job.interval_secs > 0:
                        job.next_run = now + job.interval_secs
                    elif job.job_type == "daily":
                        job.next_run = self._next_daily_time(job.run_at_hour, job.run_at_minute)
                    elif job.job_type == "once":
                        job.enabled = False
                    self._running_jobs.add(job.id)
                    asyncio.create_task(self._execute_job(job))
            await asyncio.sleep(5)  # Check every 5 seconds

    async def _execute_job(self, job: ScheduledJob) -> None:
        logger.info(f"[SCHEDULER] Running job '{job.name}' ({job.action_type})")
        job.last_run = time.time()
        job.run_count += 1

        try:
            result = await self._run_action(job.action_type, job.action_config)
            job.last_result = str(result)[:500]
            job.last_status = "success"
            job.fail_count = 0

        except Exception as e:
            job.last_result = str(e)[:500]
            job.last_status = "failed"
            job.fail_count += 1
            logger.error(f"[SCHEDULER] Job '{job.name}' failed: {e}")

            if job.fail_count >= job.max_failures:
                job.enabled = False
                logger.warning(f"[SCHEDULER] Job '{job.name}' disabled after {job.fail_count} failures")

        self._running_jobs.discard(job.id)
        self._save()

    async def _run_action(self, action_type: str, config: dict) -> Any:
        if action_type == "tool":
            from app.tools.igris_tools import get_tool_registry
            reg = get_tool_registry()
            return reg.run(config.get("tool_name", ""), **config.get("kwargs", {}))

        elif action_type == "workflow":
            from app.core.workflow_engine import get_workflow_engine
            engine = get_workflow_engine()
            run = await engine.run_workflow(config.get("workflow_id", ""), config.get("input_data", {}))
            # Wait for it to complete
            for _ in range(60):
                if run.status not in ("pending", "running"):
                    break
                await asyncio.sleep(1)
            return {"run_id": run.id, "status": run.status}

        elif action_type == "command":
            import subprocess
            cmd = config.get("command", "echo hello")
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return {"stdout": proc.stdout[:1000], "stderr": proc.stderr[:500], "return_code": proc.returncode}

        elif action_type == "python":
            from app.tools.igris_tools import PythonSandboxTool
            sb = PythonSandboxTool()
            return sb.run(config.get("code", "print('hello')"))

        return {"error": f"Unknown action type: {action_type}"}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _next_daily_time(hour: int, minute: int) -> float:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            from datetime import timedelta
            target += timedelta(days=1)
        return target.timestamp()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        try:
            data = {jid: asdict(j) for jid, j in self._jobs.items()}
            os.makedirs(os.path.dirname(os.path.abspath(self.PERSIST_FILE)), exist_ok=True)
            with open(self.PERSIST_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[SCHEDULER] Save failed: {e}")

    def _load(self) -> None:
        if not os.path.exists(self.PERSIST_FILE):
            return
        try:
            with open(self.PERSIST_FILE, "r") as f:
                data = json.load(f)
            for jid, jdata in data.items():
                self._jobs[jid] = ScheduledJob(**jdata)
        except Exception as e:
            logger.error(f"[SCHEDULER] Load failed: {e}")

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        enabled  = sum(1 for j in self._jobs.values() if j.enabled)
        total_runs = sum(j.run_count for j in self._jobs.values())
        total_fails = sum(j.fail_count for j in self._jobs.values())
        return {
            "total_jobs": len(self._jobs),
            "enabled_jobs": enabled,
            "disabled_jobs": len(self._jobs) - enabled,
            "total_executions": total_runs,
            "total_failures": total_fails,
            "scheduler_running": self._running,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _instance
    if _instance is None:
        _instance = Scheduler()
    return _instance
