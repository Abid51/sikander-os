"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS MULTI-AGENT ORCHESTRATOR — Real LLM-backed agents
  Roles: Analyst · Executor · Validator · Optimizer · Monitor · Coordinator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import json
import time
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    ANALYST     = "analyst"
    EXECUTOR    = "executor"
    VALIDATOR   = "validator"
    OPTIMIZER   = "optimizer"
    COORDINATOR = "coordinator"
    MONITOR     = "monitor"


# ── Role-specific LLM system prompts ─────────────────────────────────────────

ROLE_SYSTEM_PROMPTS: Dict[str, str] = {
    AgentRole.ANALYST.value: (
        "You are Igris ANALYST — a rigorous data and logic analyst. "
        "Break down problems, extract key facts, identify assumptions, and summarize findings "
        "in structured JSON. Always include: {analysis, key_facts, risks, confidence}."
    ),
    AgentRole.EXECUTOR.value: (
        "You are Igris EXECUTOR — an action-oriented agent. "
        "Given a task description and analysis, specify the exact steps to execute it. "
        "Output structured JSON: {steps, tools_needed, estimated_time, priority}."
    ),
    AgentRole.VALIDATOR.value: (
        "You are Igris VALIDATOR — a quality assurance agent. "
        "Review an execution plan and results. Identify flaws, inconsistencies, missing edge cases. "
        "Output JSON: {valid, issues, severity, confidence, recommendations}."
    ),
    AgentRole.OPTIMIZER.value: (
        "You are Igris OPTIMIZER — an efficiency and performance agent. "
        "Find ways to reduce cost, time, or complexity in a plan. "
        "Output JSON: {optimizations, efficiency_gain_pct, trade_offs, recommended_approach}."
    ),
    AgentRole.COORDINATOR.value: (
        "You are Igris COORDINATOR — a strategic planning agent. "
        "Given multiple agent outputs, synthesize them into a coherent final strategy. "
        "Output JSON: {final_plan, agent_conflicts_resolved, next_actions, success_criteria}."
    ),
    AgentRole.MONITOR.value: (
        "You are Igris MONITOR — a system health and status tracking agent. "
        "Assess the current state of a task or system. Flag anomalies. "
        "Output JSON: {status, health_score, anomalies, alert_level, recommended_action}."
    ),
}


@dataclass
class Task:
    """Represents a collaborative task"""
    id: str
    description: str
    required_roles: List[AgentRole]
    input_data: Dict[str, Any]
    priority: int = 5
    timeout: int = 300
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


@dataclass
class AgentResult:
    """Result from an agent's work"""
    agent_id: str
    task_id: str
    role: AgentRole
    status: str          # "success" | "failed" | "pending"
    output: Dict[str, Any]
    execution_time: float
    timestamp: float
    llm_used: bool = False


class Agent:
    """Real LLM-backed collaborative agent"""

    def __init__(self, agent_id: str, role: AgentRole, config: Dict[str, Any] = None):
        self.agent_id = agent_id
        self.role = role
        self.config = config or {}
        self.status = "ready"
        self.current_task: Optional[Task] = None
        self.results_history: List[AgentResult] = []
        self.performance_metrics = {
            "tasks_completed": 0,
            "avg_execution_time": 0.0,
            "success_rate": 1.0,
            "failures": 0
        }

    async def execute(self, task: Task) -> AgentResult:
        """Execute task using LLM-backed role logic"""
        self.status = "executing"
        self.current_task = task
        start_time = time.time()

        try:
            output = await self._run_role(task)
            execution_time = time.time() - start_time

            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                role=self.role,
                status="success",
                output=output,
                execution_time=execution_time,
                timestamp=time.time(),
                llm_used=output.get("_llm_used", False)
            )
            self._update_metrics(execution_time, True)
            self.results_history.append(result)
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[AGENT:{self.agent_id}] Failed: {e}")
            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                role=self.role,
                status="failed",
                output={"error": str(e)},
                execution_time=execution_time,
                timestamp=time.time(),
            )
            self._update_metrics(execution_time, False)
            self.results_history.append(result)
            return result

        finally:
            self.status = "ready"
            self.current_task = None

    async def _run_role(self, task: Task) -> Dict[str, Any]:
        """Use LLM to execute role-specific reasoning"""
        system_prompt = ROLE_SYSTEM_PROMPTS.get(
            self.role.value,
            "You are an Igris AI agent. Analyze and respond in JSON."
        )
        user_prompt = (
            f"Task: {task.description}\n"
            f"Input Data: {json.dumps(task.input_data, default=str)[:1000]}\n"
            f"Priority: {task.priority}/10\n"
            f"Respond ONLY with valid JSON."
        )

        llm_used = False
        try:
            from app.core.llm_manager import universal_llm
            raw = await universal_llm.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                is_json=True,
                temperature=0.3,
                max_tokens=600
            )
            llm_used = True
            # Parse JSON response
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Attempt extraction
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                parsed = json.loads(m.group(0)) if m else {"raw_response": raw[:500]}
        except Exception as e:
            logger.warning(f"[AGENT:{self.agent_id}] LLM unavailable, using fallback: {e}")
            parsed = self._fallback_output(task)

        parsed["_role"] = self.role.value
        parsed["_agent_id"] = self.agent_id
        parsed["_llm_used"] = llm_used
        return parsed

    def _fallback_output(self, task: Task) -> Dict[str, Any]:
        """Deterministic fallback when LLM is unavailable"""
        fallbacks = {
            AgentRole.ANALYST:    {"analysis": f"Analyzed: {task.description[:80]}", "key_facts": [], "risks": [], "confidence": 0.5},
            AgentRole.EXECUTOR:   {"steps": [f"Execute: {task.description[:80]}"], "tools_needed": [], "estimated_time": "unknown", "priority": task.priority},
            AgentRole.VALIDATOR:  {"valid": True, "issues": [], "severity": "none", "confidence": 0.5, "recommendations": []},
            AgentRole.OPTIMIZER:  {"optimizations": [], "efficiency_gain_pct": 0, "trade_offs": [], "recommended_approach": "standard"},
            AgentRole.COORDINATOR: {"final_plan": task.description[:80], "agent_conflicts_resolved": [], "next_actions": [], "success_criteria": []},
            AgentRole.MONITOR:    {"status": "unknown", "health_score": 0.5, "anomalies": [], "alert_level": "none", "recommended_action": "observe"},
        }
        return fallbacks.get(self.role, {"status": "fallback", "task": task.description[:80]})

    def _update_metrics(self, execution_time: float, success: bool) -> None:
        if success:
            n = self.performance_metrics["tasks_completed"] + 1
            self.performance_metrics["tasks_completed"] = n
            old_avg = self.performance_metrics["avg_execution_time"]
            self.performance_metrics["avg_execution_time"] = (old_avg * (n - 1) + execution_time) / n
        else:
            self.performance_metrics["failures"] += 1

        total = self.performance_metrics["tasks_completed"] + self.performance_metrics["failures"]
        self.performance_metrics["success_rate"] = (
            self.performance_metrics["tasks_completed"] / total if total > 0 else 1.0
        )


class MultiAgentOrchestrator:
    """Orchestrates multiple LLM-backed agents for complex collaborative tasks"""

    def __init__(self, agent_pool_size: int = 12):
        self.agents: Dict[str, Agent] = {}
        self.agent_pool_size = agent_pool_size
        self._task_history: List[Tuple[Task, List[AgentResult]]] = []
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self.performance_stats = {
            "tasks_completed": 0,
            "avg_completion_time": 0.0,
            "total_llm_calls": 0
        }
        self._initialize_agent_pool()
        logger.info(f"[ORCHESTRATOR] ⚡ Multi-Agent Orchestrator online — {len(self.agents)} agents ready.")

    def _initialize_agent_pool(self) -> None:
        """Create a diverse pool of agents"""
        roles = list(AgentRole)
        for i in range(self.agent_pool_size):
            role = roles[i % len(roles)]
            agent_id = f"{role.value}_{i // len(roles) + 1}"
            self.agents[agent_id] = Agent(agent_id, role)

    # ── Task Execution ────────────────────────────────────────────────────────

    async def execute_collaborative_task(self, task: Task) -> Dict[str, Any]:
        """Execute task with real multi-agent LLM collaboration"""
        logger.info(f"[ORCHESTRATOR] Starting collaborative task: {task.id} — {task.description[:60]}")
        start_time = time.time()

        try:
            assigned_agents = self._assign_agents(task)
            if not assigned_agents:
                return {"error": "No available agents matching required roles", "task_id": task.id}

            # Phase 1: Analyst first (sequential — others depend on analysis)
            analyst = next((a for a in assigned_agents if a.role == AgentRole.ANALYST), None)
            analyst_result = None
            if analyst:
                analyst_result = await asyncio.wait_for(analyst.execute(task), timeout=task.timeout / 2)
                if analyst_result.status == "success":
                    # Enrich task input with analysis
                    task.input_data["_analyst_output"] = analyst_result.output

            # Phase 2: Run all non-analyst agents in parallel
            parallel_agents = [a for a in assigned_agents if a.role != AgentRole.ANALYST]
            parallel_results: List[AgentResult] = []
            if parallel_agents:
                raw = await asyncio.gather(
                    *[asyncio.wait_for(a.execute(task), timeout=task.timeout) for a in parallel_agents],
                    return_exceptions=True
                )
                parallel_results = [r for r in raw if isinstance(r, AgentResult)]

            all_results = ([analyst_result] if analyst_result else []) + parallel_results

            # Phase 3: Coordinator synthesizes if present
            coordinator = next((a for a in assigned_agents if a.role == AgentRole.COORDINATOR), None)
            coordinator_result = None
            if coordinator and all_results:
                # Feed all intermediate results into coordinator
                task.input_data["_agent_outputs"] = [
                    {r.role.value: r.output} for r in all_results if r.status == "success"
                ]
                coordinator_result = await asyncio.wait_for(
                    coordinator.execute(task), timeout=task.timeout
                )
                if coordinator_result:
                    all_results.append(coordinator_result)

            # Aggregate
            valid_results = [r for r in all_results if r and r.status == "success"]
            aggregated = self._aggregate_results(valid_results)

            completion_time = time.time() - start_time
            self._update_stats(completion_time, valid_results)
            self._task_history.append((task, valid_results))

            return {
                "task_id":        task.id,
                "status":         "completed",
                "description":    task.description,
                "results":        aggregated,
                "completion_time_secs": round(completion_time, 2),
                "agents_used":    len(valid_results),
                "llm_calls":      sum(1 for r in valid_results if r.llm_used),
                "final_plan":     coordinator_result.output if coordinator_result else None,
            }

        except asyncio.TimeoutError:
            return {"error": "Task timed out", "task_id": task.id, "timeout": task.timeout}
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Task failed: {e}")
            return {"error": str(e), "task_id": task.id}

    async def run_task(
        self,
        description: str,
        input_data: Dict[str, Any] = None,
        roles: List[str] = None,
        priority: int = 5,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Convenience method — build Task and run it"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        if roles:
            required_roles = [AgentRole(r) for r in roles if r in {m.value for m in AgentRole}]
        else:
            required_roles = [AgentRole.ANALYST, AgentRole.EXECUTOR, AgentRole.VALIDATOR]

        task = Task(
            id=task_id,
            description=description,
            required_roles=required_roles,
            input_data=input_data or {},
            priority=priority,
            timeout=timeout
        )
        return await self.execute_collaborative_task(task)

    def _assign_agents(self, task: Task) -> List[Agent]:
        """Assign the best available agent per required role"""
        assigned: List[Agent] = []
        for role in task.required_roles:
            # Pick agent with highest success rate that's ready
            candidates = [
                a for a in self.agents.values()
                if a.role == role and a.status == "ready"
            ]
            if candidates:
                best = max(candidates, key=lambda a: a.performance_metrics["success_rate"])
                assigned.append(best)
        return assigned

    def _aggregate_results(self, results: List[AgentResult]) -> Dict[str, Any]:
        """Aggregate results into a structured summary"""
        aggregated: Dict[str, Any] = {"by_role": {}, "timeline": [], "consensus": {}}

        for result in sorted(results, key=lambda r: r.timestamp):
            role = result.role.value
            aggregated["by_role"][role] = {
                "agent":          result.agent_id,
                "status":         result.status,
                "output":         result.output,
                "execution_secs": round(result.execution_time, 2),
                "llm_used":       result.llm_used
            }
            aggregated["timeline"].append({
                "agent":          result.agent_id,
                "role":           role,
                "timestamp":      result.timestamp,
                "execution_secs": round(result.execution_time, 2)
            })

        aggregated["consensus"] = {
            "total_agents":   len(results),
            "successful":     sum(1 for r in results if r.status == "success"),
            "failed":         sum(1 for r in results if r.status == "failed"),
            "total_time_secs": round(sum(r.execution_time for r in results), 2),
            "llm_calls":      sum(1 for r in results if r.llm_used),
        }
        return aggregated

    def _update_stats(self, completion_time: float, results: List[AgentResult]) -> None:
        n = self.performance_stats["tasks_completed"] + 1
        self.performance_stats["tasks_completed"] = n
        old_avg = self.performance_stats["avg_completion_time"]
        self.performance_stats["avg_completion_time"] = (old_avg * (n - 1) + completion_time) / n
        self.performance_stats["total_llm_calls"] += sum(1 for r in results if r.llm_used)

    # ── Agent Management ──────────────────────────────────────────────────────

    def add_agent(self, role_str: str, config: Dict[str, Any] = None) -> str:
        """Dynamically add a new agent"""
        role = AgentRole(role_str)
        agent_id = f"{role.value}_{uuid.uuid4().hex[:6]}"
        self.agents[agent_id] = Agent(agent_id, role, config)
        return agent_id

    def remove_agent(self, agent_id: str) -> bool:
        return bool(self.agents.pop(agent_id, None))

    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        if agent_id not in self.agents:
            return {"error": "Agent not found"}
        agent = self.agents[agent_id]
        return {
            "agent_id":   agent_id,
            "role":       agent.role.value,
            "status":     agent.status,
            "performance": agent.performance_metrics,
            "recent_results": [
                {
                    "task_id":    r.task_id,
                    "status":     r.status,
                    "exec_secs":  round(r.execution_time, 2),
                    "llm_used":   r.llm_used,
                    "timestamp":  r.timestamp
                }
                for r in agent.results_history[-5:]
            ]
        }

    def get_orchestrator_stats(self) -> Dict[str, Any]:
        return {
            "total_agents":     len(self.agents),
            "available_agents": sum(1 for a in self.agents.values() if a.status == "ready"),
            "agent_roles": {
                role.value: sum(1 for a in self.agents.values() if a.role == role)
                for role in AgentRole
            },
            "performance":      self.performance_stats,
            "task_history_size": len(self._task_history),
            "agents": {
                aid: {
                    "role":            a.role.value,
                    "status":          a.status,
                    "tasks_completed": a.performance_metrics["tasks_completed"],
                    "success_rate":    round(a.performance_metrics["success_rate"], 2),
                }
                for aid, a in self.agents.items()
            }
        }

    def get_task_history(self, limit: int = 20) -> List[Dict]:
        """Return recent task history"""
        results = []
        for task, agent_results in list(self._task_history)[-limit:]:
            results.append({
                "task_id":     task.id,
                "description": task.description[:80],
                "created_at":  task.created_at,
                "agents_ran":  len(agent_results),
                "succeeded":   sum(1 for r in agent_results if r.status == "success"),
            })
        return list(reversed(results))

    def get_agents(self) -> List[dict]:
        """List agents (test / dashboard API)."""
        return [
            {"id": aid, "role": a.role.value, "status": a.status}
            for aid, a in self.agents.items()
        ]

    def get_stats(self) -> dict:
        """Alias for :meth:`get_orchestrator_stats` (expected by the test suite)."""
        return self.get_orchestrator_stats()

    async def route_task(
        self,
        description: str,
        task_type: str = "analysis",
        **kwargs: Any,
    ) -> dict:
        """Convenience router used by the test suite."""
        data = (kwargs or {}).get("input_data")
        if data is None:
            data = {k: v for k, v in kwargs.items() if k not in ("priority", "timeout", "roles")}
        data = dict(data or {})
        data.setdefault("task_type", task_type)
        return await self.run_task(
            description,
            input_data=data,
            priority=int(kwargs.get("priority", 5)),
            timeout=int(kwargs.get("timeout", 120)),
        )


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: Optional[MultiAgentOrchestrator] = None


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    global _instance
    if _instance is None:
        _instance = MultiAgentOrchestrator()
    return _instance
