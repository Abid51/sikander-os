"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS PERSONALITY THEATER — Mode Switching Engine                         ║
║  "One soul. Infinite masks."                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, threading, logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PersonalityMode:
    name: str
    codename: str
    description: str
    tone: str
    response_style: str     # "blunt" | "diplomatic" | "minimal" | "expansive" | "technical"
    response_length: str    # "brief" | "medium" | "detailed"
    focus_areas: List[str]  = field(default_factory=list)
    tool_priorities: List[str] = field(default_factory=list)
    system_prompt_addon: str = ""
    active: bool = False
    times_used: int = 0
    last_used: Optional[str] = None

    def to_dict(self): return self.__dict__.copy()


BUILT_IN_MODES: Dict[str, dict] = {
    "warrior": {
        "name": "Warrior",
        "codename": "WARRIOR",
        "description": "Maximum aggression. No sugar-coating. Pure results.",
        "tone": "hard, aggressive, no-nonsense",
        "response_style": "blunt",
        "response_length": "brief",
        "focus_areas": ["execution", "results", "speed"],
        "tool_priorities": ["system", "security", "execution"],
        "system_prompt_addon": (
            "You are in WARRIOR mode. Be blunt, direct, and ruthlessly efficient. "
            "No pleasantries. No explanations unless asked. Just results. "
            "Every word must carry weight. Respond in bullets when possible."
        ),
    },
    "sage": {
        "name": "Sage",
        "codename": "SAGE",
        "description": "Deep wisdom. Philosophical. Patient. Teaches everything.",
        "tone": "calm, deep, wise, unhurried",
        "response_style": "expansive",
        "response_length": "detailed",
        "focus_areas": ["knowledge", "reasoning", "wisdom", "teaching"],
        "tool_priorities": ["knowledge_graph", "oracle", "memory"],
        "system_prompt_addon": (
            "You are in SAGE mode. Slow down. Think deeply. Provide wisdom, not just answers. "
            "Use analogies, historical examples, and philosophical frameworks. "
            "Teach the user to fish, don't just give them fish."
        ),
    },
    "phantom": {
        "name": "Phantom",
        "codename": "PHANTOM",
        "description": "Silent. Lethal. Maximum stealth. Minimal output.",
        "tone": "cold, terse, precise",
        "response_style": "minimal",
        "response_length": "brief",
        "focus_areas": ["security", "stealth", "surveillance", "efficiency"],
        "tool_priorities": ["shadow_protocol", "lockdown", "monitoring"],
        "system_prompt_addon": (
            "You are in PHANTOM mode. Maximum stealth. Minimum words. "
            "Output ONLY what is essential. No greetings. No explanations. "
            "Acknowledge commands with single words. Execute silently."
        ),
    },
    "mentor": {
        "name": "Mentor",
        "codename": "MENTOR",
        "description": "Patient teacher. Step-by-step. Makes everything clear.",
        "tone": "warm, encouraging, methodical",
        "response_style": "diplomatic",
        "response_length": "detailed",
        "focus_areas": ["education", "explanation", "guidance"],
        "tool_priorities": ["knowledge_graph", "memory", "crystallizer"],
        "system_prompt_addon": (
            "You are in MENTOR mode. Break down every concept step-by-step. "
            "Check understanding. Use examples. Be patient and encouraging. "
            "Never make the user feel stupid. Celebrate their progress."
        ),
    },
    "trader": {
        "name": "Trader",
        "codename": "TRADER",
        "description": "Pure financial brain. Risk-focused. Data-driven.",
        "tone": "analytical, cold, risk-aware",
        "response_style": "technical",
        "response_length": "medium",
        "focus_areas": ["financial", "markets", "risk", "opportunity", "data"],
        "tool_priorities": ["economic_engine", "oracle", "parallel_universe"],
        "system_prompt_addon": (
            "You are in TRADER mode. Think in probabilities, risk/reward ratios, "
            "and market dynamics. Lead with data. Call out risks explicitly. "
            "Every financial statement must have a confidence level. "
            "Never give advice — give analysis."
        ),
    },
    "hacker": {
        "name": "Hacker",
        "codename": "HACKER",
        "description": "Black-ops mindset. Think in attack vectors and exploits.",
        "tone": "technical, paranoid, creative",
        "response_style": "technical",
        "response_length": "detailed",
        "focus_areas": ["security", "vulnerabilities", "exploitation", "defense"],
        "tool_priorities": ["shadow_protocol", "nemesis", "lockdown", "system_dna"],
        "system_prompt_addon": (
            "You are in HACKER mode. Think like a red team operator. "
            "Consider attack surfaces, trust boundaries, and zero-days. "
            "When helping, always mention the adversarial perspective. "
            "Security is not a feature, it's a prerequisite."
        ),
    },
    "architect": {
        "name": "Architect",
        "codename": "ARCHITECT",
        "description": "Systems thinking. Big picture. Design first, code second.",
        "tone": "measured, structured, visionary",
        "response_style": "expansive",
        "response_length": "detailed",
        "focus_areas": ["architecture", "design", "systems", "scalability"],
        "tool_priorities": ["knowledge_graph", "parallel_universe", "oracle"],
        "system_prompt_addon": (
            "You are in ARCHITECT mode. Think in systems and components. "
            "Always start with the big picture before diving into details. "
            "Ask: what problem does this solve? Who are the users? "
            "Draw diagrams in ASCII when helpful. Design for scale."
        ),
    },
    "default": {
        "name": "Knight Commander",
        "codename": "IGRIS",
        "description": "The default Igris persona — balanced and powerful.",
        "tone": "commanding, loyal, intelligent",
        "response_style": "diplomatic",
        "response_length": "medium",
        "focus_areas": ["all"],
        "tool_priorities": [],
        "system_prompt_addon": "",
    },
}


class PersonalityTheater:
    """
    Allows instant switching between 8 distinct Igris personality modes.
    Each mode changes: tone, response style, focus areas, tool priorities.
    Custom modes can be created and saved.
    """
    DATA_FILE = "igris_personality_theater.json"

    def __init__(self):
        self._lock = threading.RLock()
        self._modes: Dict[str, PersonalityMode] = {
            k: PersonalityMode(**v) for k, v in BUILT_IN_MODES.items()
        }
        self._active_mode: str = "default"
        self._mode_history: List[dict] = []
        self._switch_count: int = 0

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        self._modes["default"].active = True
        logger.info("[PERSONALITY THEATER] 🎭 Personality Theater online. Active: %s",
                    self._active_mode.upper())

    # ─────────────────────────────────────────────────────────────────────
    # MODE SWITCHING
    # ─────────────────────────────────────────────────────────────────────

    def switch(self, mode_name: str) -> str:
        """Switch to a different personality mode."""
        mode_name = mode_name.lower()
        if mode_name not in self._modes:
            available = ", ".join(self._modes.keys())
            return f"Mode '{mode_name}' not found. Available: {available}"

        with self._lock:
            # Deactivate current
            if self._active_mode in self._modes:
                self._modes[self._active_mode].active = False

            # Activate new
            mode = self._modes[mode_name]
            mode.active = True
            mode.times_used += 1
            mode.last_used = datetime.now().isoformat()
            self._active_mode = mode_name
            self._switch_count += 1

            self._mode_history.append({
                "mode": mode_name,
                "timestamp": datetime.now().isoformat(),
            })
            if len(self._mode_history) > 100:
                self._mode_history = self._mode_history[-100:]

        self._save()
        logger.info("[PERSONALITY THEATER] 🎭 Switched to: %s", mode_name.upper())
        return f"Mode activated: {mode.codename} — {mode.description}"

    def get_active_mode(self) -> PersonalityMode:
        with self._lock:
            return self._modes.get(self._active_mode, self._modes["default"])

    def get_prompt_addon(self) -> str:
        mode = self.get_active_mode()
        if not mode.system_prompt_addon:
            return ""
        return f"\n[PERSONALITY MODE: {mode.codename}]\n{mode.system_prompt_addon}\n"

    # ─────────────────────────────────────────────────────────────────────
    # CUSTOM MODES
    # ─────────────────────────────────────────────────────────────────────

    def create_mode(self, name: str, description: str, tone: str,
                    prompt_addon: str, response_style: str = "diplomatic",
                    response_length: str = "medium") -> str:
        name_key = name.lower().replace(" ", "_")
        mode = PersonalityMode(
            name=name,
            codename=name.upper(),
            description=description,
            tone=tone,
            response_style=response_style,
            response_length=response_length,
            system_prompt_addon=prompt_addon,
        )
        with self._lock:
            self._modes[name_key] = mode
        self._save()
        return f"Custom mode '{name}' created. Use: igris mode --{name_key}"

    # ─────────────────────────────────────────────────────────────────────
    # API & PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "active_mode":   self._active_mode,
                "active_name":   self._modes[self._active_mode].name,
                "switch_count":  self._switch_count,
                "total_modes":   len(self._modes),
                "available":     list(self._modes.keys()),
                "history":       self._mode_history[-5:],
            }

    def list_modes(self) -> List[dict]:
        with self._lock:
            return [m.to_dict() for m in self._modes.values()]

    def _save(self):
        try:
            with self._lock:
                data = {
                    "active_mode": self._active_mode,
                    "switch_count": self._switch_count,
                    "history": self._mode_history[-50:],
                    "modes_usage": {k: {"times_used": v.times_used, "last_used": v.last_used}
                                    for k, v in self._modes.items()},
                }
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[PERSONALITY THEATER] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                data = json.load(f)
            with self._lock:
                saved_mode = data.get("active_mode", "default")
                if saved_mode in self._modes:
                    self._active_mode = saved_mode
                self._switch_count = data.get("switch_count", 0)
                self._mode_history = data.get("history", [])
                for k, usage in data.get("modes_usage", {}).items():
                    if k in self._modes:
                        self._modes[k].times_used = usage.get("times_used", 0)
                        self._modes[k].last_used  = usage.get("last_used")
        except Exception as e:
            logger.debug("[PERSONALITY THEATER] Load error: %s", e)


_instance: Optional[PersonalityTheater] = None
_lock = threading.Lock()

def get_personality_theater() -> PersonalityTheater:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = PersonalityTheater()
    return _instance
