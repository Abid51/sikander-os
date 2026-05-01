"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS DREAM SPACE — Autonomous Idle Intelligence                          ║
║  "While you rest, I grow. While you sleep, I prepare."                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, time, threading, logging, json, random
from typing import List, Dict, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import psutil as _psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    import requests as _req
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


@dataclass
class DreamTask:
    task_id: str
    name: str
    priority: int           # 1 (highest) – 10 (lowest)
    category: str           # security | memory | knowledge | maintenance | prediction
    fn_name: str            # internal function name
    result: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str = "pending"

    def to_dict(self): return self.__dict__.copy()


class DreamSpace:
    """
    Activated when user is idle (> IDLE_THRESHOLD seconds) AND
    system CPU is low (< CPU_THRESHOLD %).

    Autonomous task queue:
    ─────────────────────
    • Crystallize beliefs from memory
    • Cleanup old conversation history
    • Pre-warm neural reflex cache
    • Run security self-scan
    • Snapshot consciousness (mind backup)
    • Fetch & cache crypto prices
    • Compact knowledge graph
    • Generate daily summary report
    """

    IDLE_THRESHOLD = 600     # 10 min user inactivity
    CPU_THRESHOLD  = 25.0    # % — only run when system is relaxed
    TASK_FILE      = "igris_dream_log.json"
    REPORT_FILE    = "igris_dream_report.json"

    def __init__(self):
        self._lock = threading.RLock()
        self._last_user_activity: float = time.time()
        self._dreaming: bool = False
        self._completed_tasks: List[DreamTask] = []
        self._task_registry: List[DreamTask] = self._build_task_registry()
        self._dream_count: int = 0
        self._current_dream_report: Dict = {}

        base = os.path.dirname(os.path.abspath(__file__))
        self._log_file = os.path.normpath(os.path.join(base, "..", "..", self.TASK_FILE))
        self._report_file = os.path.normpath(os.path.join(base, "..", "..", self.REPORT_FILE))

        threading.Thread(target=self._watchdog_loop, daemon=True).start()
        logger.info("[DREAM SPACE] 🌙 Dream Space standby. Monitoring idle state...")

    # ─────────────────────────────────────────────────────────────────────
    # ACTIVITY TRACKING
    # ─────────────────────────────────────────────────────────────────────

    def ping_activity(self):
        """Call this whenever the user sends a message — resets idle timer."""
        with self._lock:
            self._last_user_activity = time.time()
            if self._dreaming:
                logger.info("[DREAM SPACE] 🌅 User returned — waking from dream.")
                self._dreaming = False

    @property
    def idle_seconds(self) -> float:
        return time.time() - self._last_user_activity

    @property
    def is_idle(self) -> bool:
        return self.idle_seconds >= self.IDLE_THRESHOLD

    @property
    def system_is_relaxed(self) -> bool:
        if not PSUTIL_OK:
            return True
        try:
            return _psutil.cpu_percent(interval=1) < self.CPU_THRESHOLD
        except Exception:
            return True

    # ─────────────────────────────────────────────────────────────────────
    # WATCHDOG
    # ─────────────────────────────────────────────────────────────────────

    def _watchdog_loop(self):
        while True:
            time.sleep(60)
            if self.is_idle and self.system_is_relaxed and not self._dreaming:
                logger.info("[DREAM SPACE] 🌙 Entering Dream Space — idle=%.0fs", self.idle_seconds)
                threading.Thread(target=self._run_dream_cycle, daemon=True).start()

    def _run_dream_cycle(self):
        with self._lock:
            if self._dreaming:
                return
            self._dreaming = True
            self._dream_count += 1

        report = {"dream_number": self._dream_count, "started": datetime.now().isoformat(),
                  "tasks": [], "ended": None}
        tasks = sorted(self._task_registry, key=lambda t: t.priority)

        for task in tasks:
            if not self._dreaming:
                break   # User came back
            if not self.system_is_relaxed:
                break   # System got busy

            task.status    = "running"
            task.started_at = datetime.now().isoformat()
            try:
                fn = getattr(self, f"_dream_{task.fn_name}", None)
                if fn:
                    task.result = fn()
                else:
                    task.result = f"No handler for {task.fn_name}"
                task.status = "completed"
            except Exception as e:
                task.result = f"Error: {e}"
                task.status = "failed"

            task.completed_at = datetime.now().isoformat()
            report["tasks"].append(task.to_dict())
            logger.info("[DREAM SPACE] ✅ Task: %s — %s", task.name, task.status)
            time.sleep(5)   # Breathe between tasks

        report["ended"] = datetime.now().isoformat()
        with self._lock:
            self._current_dream_report = report
            self._completed_tasks.extend(tasks)
            if len(self._completed_tasks) > 200:
                self._completed_tasks = self._completed_tasks[-200:]
            self._dreaming = False

        try:
            with open(self._report_file, "w") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

        logger.info("[DREAM SPACE] 🌅 Dream cycle #%d complete. %d tasks.", self._dream_count, len(tasks))

    # ─────────────────────────────────────────────────────────────────────
    # DREAM TASKS
    # ─────────────────────────────────────────────────────────────────────

    def _dream_crystallize(self) -> str:
        try:
            from app.core.thought_crystallizer import get_crystallizer
            beliefs = get_crystallizer().crystallize()
            return f"Crystallized {len(beliefs)} new beliefs from memory."
        except Exception as e:
            return f"Crystallize skipped: {e}"

    def _dream_snapshot_mind(self) -> str:
        try:
            from app.core.consciousness_git import get_consciousness_git
            snap_id = get_consciousness_git().take_snapshot("dream_auto")
            return f"Mind snapshot saved: {snap_id}"
        except Exception as e:
            return f"Snapshot skipped: {e}"

    def _dream_compact_graph(self) -> str:
        try:
            from app.memory.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            stats = kg.get_stats()
            return f"Knowledge graph: {stats['total_nodes']} nodes, {stats['total_edges']} edges."
        except Exception as e:
            return f"Graph compact skipped: {e}"

    def _dream_fetch_prices(self) -> str:
        try:
            from app.agents.economic_engine import get_economic_engine
            eng = get_economic_engine()
            results = []
            for sym in ["BTC/USDT", "ETH/USDT"]:
                p = eng.fetch_crypto_price(sym)
                if p:
                    results.append(f"{sym}=${p:,.2f}")
            return "Prices cached: " + ", ".join(results) if results else "No prices fetched."
        except Exception as e:
            return f"Price fetch skipped: {e}"

    def _dream_security_scan(self) -> str:
        try:
            if not PSUTIL_OK:
                return "psutil not available — scan skipped."
            suspicious = []
            for proc in _psutil.process_iter(["pid", "name", "cpu_percent"]):
                try:
                    if proc.info["cpu_percent"] and proc.info["cpu_percent"] > 50:
                        suspicious.append(f"{proc.info['name']}({proc.info['pid']})")
                except Exception:
                    pass
            return f"Security scan done. High-CPU procs: {', '.join(suspicious[:3]) or 'None'}"
        except Exception as e:
            return f"Security scan error: {e}"

    def _dream_cleanup_memory(self) -> str:
        """Trim old history files."""
        cleaned = 0
        base = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
        for fname in ["igris_memory.json"]:
            fp = os.path.join(base, fname)
            if os.path.exists(fp):
                try:
                    with open(fp) as f:
                        data = json.load(f)
                    if isinstance(data.get("history"), list) and len(data["history"]) > 50:
                        data["history"] = data["history"][-50:]
                        with open(fp, "w") as f:
                            json.dump(data, f)
                        cleaned += 1
                except Exception:
                    pass
        return f"Memory cleanup done. {cleaned} file(s) trimmed."

    def _dream_generate_report(self) -> str:
        """Generate a 'while you were away' summary."""
        lines = [
            f"Dream cycle #{self._dream_count}",
            f"Idle time: {self.idle_seconds/60:.0f} min",
            f"Completed: {sum(1 for t in self._task_registry if t.status == 'completed')} tasks",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
        return " | ".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # TASK REGISTRY
    # ─────────────────────────────────────────────────────────────────────

    def _build_task_registry(self) -> List[DreamTask]:
        return [
            DreamTask("dt1", "Mind Snapshot",         1, "maintenance", "snapshot_mind"),
            DreamTask("dt2", "Security Scan",          2, "security",    "security_scan"),
            DreamTask("dt3", "Thought Crystallization",3, "memory",      "crystallize"),
            DreamTask("dt4", "Knowledge Graph Compact",4, "knowledge",   "compact_graph"),
            DreamTask("dt5", "Crypto Price Cache",     5, "prediction",  "fetch_prices"),
            DreamTask("dt6", "Memory Cleanup",         6, "maintenance", "cleanup_memory"),
            DreamTask("dt7", "Dream Report",           7, "maintenance", "generate_report"),
        ]

    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────

    def force_dream(self) -> str:
        """Manually trigger a dream cycle."""
        if self._dreaming:
            return "Already dreaming. Wait for cycle to complete."
        threading.Thread(target=self._run_dream_cycle, daemon=True).start()
        return "Dream cycle initiated."

    def get_last_report(self) -> dict:
        with self._lock:
            return dict(self._current_dream_report)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "is_dreaming":     self._dreaming,
                "idle_seconds":    round(self.idle_seconds, 0),
                "dream_count":     self._dream_count,
                "system_relaxed":  self.system_is_relaxed,
                "tasks_available": len(self._task_registry),
                "last_dream":      self._current_dream_report.get("started", "never"),
            }


_instance: Optional[DreamSpace] = None
_lock = threading.Lock()

def get_dream_space() -> DreamSpace:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = DreamSpace()
    return _instance
