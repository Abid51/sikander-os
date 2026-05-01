"""
Igris Background Job Queue — Production-grade async job queue.
Features: priorities, named jobs, concurrency cap, retry, stats, cancellation.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    LOW    = 10
    NORMAL = 5
    HIGH   = 1
    URGENT = 0


@dataclass(order=True)
class _JobItem:
    priority: int
    seq: int                   # tiebreaker (FIFO within same priority)
    job_id: str = field(compare=False)
    name: str   = field(compare=False)
    coro_fn: Any = field(compare=False, repr=False)   # Callable[[], Coroutine]
    retries_left: int = field(compare=False, default=0)
    enqueued_at: float = field(compare=False, default_factory=time.time)


class JobStatus:
    QUEUED    = "queued"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class JobQueue:
    """
    Async priority job queue for Igris OS.

    Usage:
        queue = get_job_queue()
        job_id = await queue.enqueue(my_coroutine(), name="my_job", priority=Priority.HIGH)
        await queue.wait(job_id)
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        self._pq: asyncio.PriorityQueue[_JobItem] = asyncio.PriorityQueue()
        self._seq = 0
        self._max_concurrent = max_concurrent
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._jobs: Dict[str, dict] = {}           # job_id -> status record
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._total_enqueued = 0
        self._total_completed = 0
        self._total_failed = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_worker(self) -> None:
        if self._running:
            return
        self._running = True
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._task = asyncio.create_task(self._dispatcher())
        logger.info(f"[JOB QUEUE] ⚡ Worker started (max_concurrent={self._max_concurrent})")

    async def stop(self, wait_drain: bool = True) -> None:
        self._running = False
        if wait_drain:
            await self._pq.join()
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[JOB QUEUE] Stopped.")

    # ── Enqueue ───────────────────────────────────────────────────────────────

    async def enqueue(
        self,
        coro_or_factory: Coroutine[Any, Any, Any] | Callable[[], Coroutine[Any, Any, Any]],
        name: str = "",
        priority: int = Priority.NORMAL,
        retries: int = 0,
    ) -> str:
        """Enqueue a coroutine (or coroutine factory). Returns job_id."""
        job_id = uuid.uuid4().hex[:12]
        self._seq += 1
        self._total_enqueued += 1

        # Always keep a factory so retries create a fresh coroutine.
        if callable(coro_or_factory):
            coro_factory = coro_or_factory
        else:
            coro = coro_or_factory
            used_once = False

            def coro_factory() -> Coroutine[Any, Any, Any]:
                nonlocal used_once
                if used_once:
                    raise RuntimeError(
                        "This job cannot be retried because a coroutine object was passed. "
                        "Pass a coroutine factory (lambda/def) to enable retries."
                    )
                used_once = True
                return coro

        item = _JobItem(
            priority=int(priority),
            seq=self._seq,
            job_id=job_id,
            name=name or f"job_{job_id[:6]}",
            coro_fn=coro_factory,
            retries_left=retries,
        )
        self._jobs[job_id] = {
            "id": job_id, "name": item.name,
            "status": JobStatus.QUEUED, "priority": priority,
            "enqueued_at": item.enqueued_at, "started_at": None,
            "finished_at": None, "result": None, "error": None,
            "attempts": 0
        }
        await self._pq.put(item)
        return job_id

    def enqueue_nowait(
        self,
        coro_or_factory: Coroutine[Any, Any, Any] | Callable[[], Coroutine[Any, Any, Any]],
        name: str = "",
        priority: int = Priority.NORMAL,
        retries: int = 0,
    ) -> str:
        """Thread-safe non-async enqueue."""
        try:
            loop = asyncio.get_running_loop()
            raise RuntimeError("enqueue_nowait cannot run from inside an active event loop")
        except RuntimeError:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None

            if loop and not loop.is_running():
                return loop.run_until_complete(self.enqueue(coro_or_factory, name, priority, retries))
            raise RuntimeError("No active event loop available for enqueue_nowait")

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued job (running jobs cannot be cancelled here)."""
        job = self._jobs.get(job_id)
        if job and job["status"] == JobStatus.QUEUED:
            job["status"] = JobStatus.CANCELLED
            job["finished_at"] = time.time()
            return True
        return False

    # ── Wait / Query ──────────────────────────────────────────────────────────

    async def wait(self, job_id: str, timeout: float = 60.0) -> Optional[Any]:
        """Block until a job finishes and return its result."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self._jobs.get(job_id)
            if job and job["status"] in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
                if job["status"] == JobStatus.FAILED:
                    raise RuntimeError(job.get("error", "Job failed"))
                return job.get("result")
            await asyncio.sleep(0.1)
        raise asyncio.TimeoutError(f"Job {job_id} did not complete within {timeout}s")

    def get_job(self, job_id: str) -> Optional[dict]:
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        # Sort by enqueue time descending
        jobs.sort(key=lambda j: j.get("enqueued_at", 0), reverse=True)
        return jobs[:limit]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def queue_depth(self) -> int:
        return self._pq.qsize()

    def get_stats(self) -> dict:
        status_counts: Dict[str, int] = {}
        for j in self._jobs.values():
            s = j["status"]
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "queue_depth":       self._pq.qsize(),
            "max_concurrent":    self._max_concurrent,
            "total_enqueued":    self._total_enqueued,
            "total_completed":   self._total_completed,
            "total_failed":      self._total_failed,
            "running":           self._running,
            "by_status":         status_counts,
        }

    # ── Dispatcher ────────────────────────────────────────────────────────────

    async def _dispatcher(self) -> None:
        while self._running:
            try:
                item: _JobItem = await asyncio.wait_for(self._pq.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            job = self._jobs.get(item.job_id)
            if not job or job["status"] == JobStatus.CANCELLED:
                self._pq.task_done()
                continue

            # Run with concurrency cap
            asyncio.create_task(self._run_job(item))

    async def _run_job(self, item: _JobItem) -> None:
        assert self._semaphore is not None
        async with self._semaphore:
            job = self._jobs.get(item.job_id)
            if not job or job["status"] == JobStatus.CANCELLED:
                self._pq.task_done()
                return

            job["status"]     = JobStatus.RUNNING
            job["started_at"] = time.time()
            job["attempts"]  += 1

            try:
                result = await item.coro_fn()
                job["status"]      = JobStatus.DONE
                job["result"]      = result
                job["finished_at"] = time.time()
                self._total_completed += 1
                logger.debug(f"[JOB QUEUE] ✅ '{item.name}' completed in "
                             f"{(job['finished_at'] - job['started_at'])*1000:.0f}ms")

            except Exception as exc:
                if item.retries_left > 0:
                    logger.warning(f"[JOB QUEUE] ↩️ '{item.name}' failed, retrying ({item.retries_left} left): {exc}")
                    item.retries_left -= 1
                    job["status"] = JobStatus.QUEUED
                    await asyncio.sleep(1.0)
                    await self._pq.put(item)
                else:
                    job["status"]      = JobStatus.FAILED
                    job["error"]       = str(exc)
                    job["finished_at"] = time.time()
                    self._total_failed += 1
                    logger.error(f"[JOB QUEUE] ❌ '{item.name}' failed: {exc}")

            finally:
                self._pq.task_done()


# ── Backwards-compatible module-level helpers ─────────────────────────────────

_queue_instance: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = JobQueue()
    return _queue_instance


def start_worker() -> None:
    get_job_queue().start_worker()


async def enqueue(
    coro_or_factory: Coroutine[Any, Any, Any] | Callable[[], Coroutine[Any, Any, Any]],
    name: str = "",
    priority: int = Priority.NORMAL,
) -> str:
    return await get_job_queue().enqueue(coro_or_factory, name=name, priority=priority)


def queue_depth() -> int:
    return get_job_queue().queue_depth()
