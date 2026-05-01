"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS AUTONOMOUS AGENT LOOP
  Plan → Execute → Observe → Reflect → Repeat
  ReAct-style agent with tool use, memory, and self-correction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Internal imports ──────────────────────────────────────────────────────────
try:
    from app.core.llm_manager import universal_llm
    _LLM = True
except Exception:
    universal_llm = None
    _LLM = False

try:
    from app.tools.igris_tools import get_tool_registry
    _TOOLS = True
except Exception:
    get_tool_registry = None
    _TOOLS = False

try:
    from app.memory.vector_memory import get_neural_memory
    _MEMORY = True
except Exception:
    get_neural_memory = None
    _MEMORY = False


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentStep:
    step_num: int
    thought: str
    action: str           # tool name or "final_answer"
    action_input: Dict[str, Any]
    observation: str      # tool output
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentRun:
    run_id: str
    goal: str
    steps: List[AgentStep]
    final_answer: str
    success: bool
    total_steps: int
    duration_ms: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ─────────────────────────────────────────────────────────────────────────────
#  AUTONOMOUS AGENT
# ─────────────────────────────────────────────────────────────────────────────

class IgrisAutonomousAgent:
    """
    ReAct-style autonomous agent for Igris.

    How it works:
    ─────────────
    1. User gives a GOAL
    2. Agent thinks (Thought) → picks a tool (Action) → gets result (Observation)
    3. Repeats until it has enough info to answer
    4. Returns final_answer

    Available tools are auto-discovered from IgrisToolRegistry + extras.
    """

    MAX_STEPS = 10
    MAX_RETRIES = 2

    SYSTEM_PROMPT = """You are Igris — an autonomous AI agent. You have access to tools.

For each step, respond with ONLY valid JSON in this format:
{
  "thought": "your reasoning about what to do next",
  "action": "tool_name_or_final_answer",
  "action_input": {"key": "value"}
}

If you have enough information, use action = "final_answer" and put your complete answer in action_input.answer.

Available tools:
{tools}

Rules:
- Think step by step
- Use tools to gather real information, do not guess
- If a tool fails, try a different approach
- When you have a complete answer, use final_answer
- Never loop more than {max_steps} steps"""

    def __init__(self) -> None:
        self._tool_registry = get_tool_registry() if _TOOLS else None
        self._memory = get_neural_memory() if _MEMORY else None
        self._run_history: List[AgentRun] = []
        self._extra_tools: Dict[str, Callable] = {}
        self._event_callbacks: List[Callable] = []

    def register_tool(self, name: str, fn: Callable, description: str = "") -> None:
        """Register a custom tool beyond the default registry."""
        self._extra_tools[name] = {"fn": fn, "description": description}
        logger.info(f"[AGENT] Custom tool registered: {name}")

    def on_step(self, callback: Callable) -> None:
        """Register callback called after each agent step (for streaming to UI)."""
        self._event_callbacks.append(callback)

    def _get_tools_description(self) -> str:
        """Build tools list for the system prompt."""
        tools = []
        if self._tool_registry:
            for t in self._tool_registry.available_tools():
                tools.append(f"- {t['name']}({', '.join(t['args'])}): {t['desc']}")
        for name, info in self._extra_tools.items():
            tools.append(f"- {name}: {info.get('description', '')}")
        tools.append("- final_answer(answer): Return your final complete answer to the user")
        return "\n".join(tools)

    async def _run_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool and return its output as string."""
        # Check extra tools first
        if tool_name in self._extra_tools:
            try:
                fn = self._extra_tools[tool_name]["fn"]
                if asyncio.iscoroutinefunction(fn):
                    result = await fn(**tool_input)
                else:
                    result = await asyncio.to_thread(fn, **tool_input)
                return json.dumps(result, ensure_ascii=False)[:2000]
            except Exception as e:
                return f"Tool error: {e}"

        # Use standard tool registry
        if self._tool_registry:
            try:
                result = await asyncio.to_thread(
                    self._tool_registry.run, tool_name, **tool_input
                )
                if isinstance(result, (dict, list)):
                    return json.dumps(result, ensure_ascii=False)[:2000]
                return str(result)[:2000]
            except Exception as e:
                return f"Tool error: {e}"

        return f"Tool '{tool_name}' not found. No tool registry available."

    async def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response as JSON, with repair attempts."""
        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON block
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Last resort: ask LLM to fix it
        try:
            fixed = await universal_llm.generate_response(
                system_prompt="Extract the JSON from this text. Return ONLY valid JSON, nothing else.",
                user_prompt=response,
                is_json=True,
            )
            return json.loads(fixed)
        except Exception:
            pass

        return None

    async def run(self, goal: str, context: Optional[str] = None) -> AgentRun:
        """
        Run the autonomous agent loop for a given goal.
        Returns AgentRun with all steps and final answer.
        """
        run_id = str(uuid.uuid4())[:8]
        t_start = time.time()
        steps: List[AgentStep] = []

        logger.info(f"[AGENT] 🚀 Starting agent run {run_id}: {goal[:100]}")

        if not _LLM or universal_llm is None:
            return AgentRun(
                run_id=run_id, goal=goal, steps=[],
                final_answer="LLM not available for agent loop.",
                success=False, total_steps=0,
                duration_ms=(time.time() - t_start) * 1000,
            )

        # Build conversation history
        messages: List[Dict[str, str]] = []
        system_prompt = self.SYSTEM_PROMPT.format(
            tools=self._get_tools_description(),
            max_steps=self.MAX_STEPS,
        )

        # Initial user message
        initial_msg = f"Goal: {goal}"
        if context:
            initial_msg += f"\n\nContext: {context}"

        # Retrieve relevant memories
        if self._memory:
            try:
                memories = self._memory.recall(goal, top_k=3)
                if memories:
                    mem_text = "\n".join([f"- {m[0].content[:200]}" for m in memories])
                    initial_msg += f"\n\nRelevant memory:\n{mem_text}"
            except Exception:
                pass

        current_input = initial_msg

        for step_num in range(1, self.MAX_STEPS + 1):
            logger.info(f"[AGENT] Step {step_num}/{self.MAX_STEPS}")

            # Generate LLM response
            try:
                response = await universal_llm.generate_response(
                    system_prompt=system_prompt,
                    user_prompt=current_input,
                    history=messages,
                    is_json=True,
                )
            except Exception as e:
                logger.error(f"[AGENT] LLM error at step {step_num}: {e}")
                break

            # Parse response
            parsed = await self._parse_llm_response(response)
            if not parsed:
                logger.warning(f"[AGENT] Could not parse LLM response: {response[:200]}")
                break

            thought = parsed.get("thought", "")
            action = parsed.get("action", "").strip()
            action_input = parsed.get("action_input", {})

            # Check for final answer
            if action == "final_answer":
                answer = action_input.get("answer", str(action_input))
                step = AgentStep(
                    step_num=step_num,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation="[COMPLETE]",
                )
                steps.append(step)

                # Notify callbacks
                for cb in self._event_callbacks:
                    try:
                        await cb(step) if asyncio.iscoroutinefunction(cb) else cb(step)
                    except Exception:
                        pass

                # Save to memory
                if self._memory:
                    try:
                        self._memory.remember(
                            content=f"Goal: {goal}\nAnswer: {answer[:500]}",
                            memory_type="episodic",
                            tags=["agent_run", run_id],
                            importance=0.7,
                        )
                    except Exception:
                        pass

                run = AgentRun(
                    run_id=run_id, goal=goal, steps=steps,
                    final_answer=answer, success=True,
                    total_steps=step_num,
                    duration_ms=(time.time() - t_start) * 1000,
                )
                self._run_history.append(run)
                logger.info(f"[AGENT] ✅ Run {run_id} complete in {step_num} steps.")
                return run

            # Execute tool
            observation = await self._run_tool(action, action_input)
            step = AgentStep(
                step_num=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
            )
            steps.append(step)

            # Notify callbacks (for streaming to UI)
            for cb in self._event_callbacks:
                try:
                    await cb(step) if asyncio.iscoroutinefunction(cb) else cb(step)
                except Exception:
                    pass

            # Update conversation
            messages.append({"role": "assistant", "content": response})
            current_input = f"Observation: {observation}\n\nContinue toward the goal."

            logger.info(f"[AGENT] Step {step_num}: {action} → {observation[:100]}")

        # Max steps reached
        final_answer = "I reached the maximum steps limit. Here is what I found so far:\n"
        if steps:
            last_obs = steps[-1].observation
            final_answer += last_obs[:500]

        run = AgentRun(
            run_id=run_id, goal=goal, steps=steps,
            final_answer=final_answer, success=False,
            total_steps=len(steps),
            duration_ms=(time.time() - t_start) * 1000,
        )
        self._run_history.append(run)
        return run

    async def stream_run(self, goal: str, context: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream agent steps as they happen — for real-time UI updates.
        Yields dicts: {"type": "step"|"final", "data": ...}
        """
        steps_received = []

        async def collect_step(step: AgentStep):
            steps_received.append(step)

        self.on_step(collect_step)

        # Run in background task, yield steps as they come
        run_task = asyncio.create_task(self.run(goal, context))

        last_yielded = 0
        while not run_task.done():
            while last_yielded < len(steps_received):
                yield {"type": "step", "data": steps_received[last_yielded].to_dict()}
                last_yielded += 1
            await asyncio.sleep(0.1)

        # Yield remaining steps
        while last_yielded < len(steps_received):
            yield {"type": "step", "data": steps_received[last_yielded].to_dict()}
            last_yielded += 1

        run = await run_task
        yield {"type": "final", "data": run.to_dict()}

        # Remove the callback
        if collect_step in self._event_callbacks:
            self._event_callbacks.remove(collect_step)

    def get_run_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._run_history[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        return {
            "llm_available": _LLM,
            "tools_available": _TOOLS,
            "memory_available": _MEMORY,
            "max_steps": self.MAX_STEPS,
            "extra_tools": list(self._extra_tools.keys()),
            "total_runs": len(self._run_history),
            "tool_count": len(self._tool_registry.available_tools()) if self._tool_registry else 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisAutonomousAgent] = None


def get_autonomous_agent() -> IgrisAutonomousAgent:
    global _instance
    if _instance is None:
        _instance = IgrisAutonomousAgent()
    return _instance
