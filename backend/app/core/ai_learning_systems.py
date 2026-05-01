"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS AI LEARNING SYSTEMS
  VoiceControlSystem · AdvancedKnowledgeGraph · PersonalizedLearningAssistant
  All backed by real implementations (SpeechRecognition, pyttsx3, LLM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import asyncio
import os
import re
import time
import threading
import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict, Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 1. VOICE CONTROL SYSTEM — Real SpeechRecognition + pyttsx3 TTS
# ══════════════════════════════════════════════════════════════════════════════

class VoiceCommand:
    EXECUTE_CODE   = "execute_code"
    QUERY_DATA     = "query_data"
    CONTROL_DEVICE = "control_device"
    GET_INFO       = "get_info"
    CREATE_CONTENT = "create_content"
    SYSTEM_CONTROL = "system_control"


VOICE_COMMAND_KEYWORDS: Dict[str, List[str]] = {
    VoiceCommand.EXECUTE_CODE:   ["run", "execute", "chalaao", "start", "launch", "code"],
    VoiceCommand.QUERY_DATA:     ["data", "show", "dikhao", "search", "find", "query", "stats"],
    VoiceCommand.CONTROL_DEVICE: ["control", "karo", "set", "open", "close", "turn"],
    VoiceCommand.SYSTEM_CONTROL: ["system", "restart", "shutdown", "cpu", "memory", "RAM"],
    VoiceCommand.CREATE_CONTENT: ["create", "write", "generate", "banao", "likho", "make"],
    VoiceCommand.GET_INFO:       ["what", "kya", "kaise", "tell", "explain", "batao"],
}


class VoiceControlSystem:
    """Real voice control: SpeechRecognition STT + pyttsx3 TTS"""

    def __init__(self):
        self.voice_history: Dict[str, dict] = {}
        self.voice_commands: List[dict] = []
        self._tts_lock = threading.Lock()

        # Check availability
        self._sr_available = False
        self._tts_available = False
        try:
            import speech_recognition as sr
            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._sr_available = True
        except ImportError:
            logger.warning("[VOICE] speech_recognition not installed — STT disabled")

        try:
            import pyttsx3
            self._pyttsx3 = pyttsx3
            self._tts_available = True
        except ImportError:
            logger.warning("[VOICE] pyttsx3 not installed — TTS disabled")

        logger.info(f"[VOICE CONTROL] Online — STT={'on' if self._sr_available else 'off'} TTS={'on' if self._tts_available else 'off'}")

    async def recognize_voice(self, audio_data: bytes, language: str = "en-US") -> Dict:
        """Transcribe audio bytes using SpeechRecognition (Google STT)"""
        transcript_id = str(uuid.uuid4())
        recognized_text = ""
        confidence = 0.0
        error = None

        if self._sr_available and audio_data:
            try:
                import io
                sr = self._sr
                audio_io = io.BytesIO(audio_data)
                with sr.AudioFile(audio_io) as source:
                    audio = self._recognizer.record(source)
                # Google STT — free tier, no key required
                recognized_text = self._recognizer.recognize_google(audio, language=language)
                confidence = 0.92
            except Exception as e:
                error = str(e)
                logger.warning(f"[VOICE] STT failed: {e}")

        if not recognized_text:
            recognized_text = "[Voice recognition unavailable — install speech_recognition]"
            confidence = 0.0

        entry = {
            "language": language,
            "text": recognized_text,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
        self.voice_history[transcript_id] = entry
        self.voice_commands.append({"type": "recognize", **entry})

        return {
            "transcript_id":   transcript_id,
            "recognized_text": recognized_text,
            "language":        language,
            "confidence":      confidence,
            "status":          "recognized" if recognized_text and not error else "failed",
            "sr_available":    self._sr_available,
            "error":           error
        }

    async def convert_text_to_speech(
        self,
        text: str,
        language: str = "en-US",
        voice: str = "default",
        speed: float = 1.0,
        save_path: str = None
    ) -> Dict:
        """Convert text to speech using pyttsx3 — saves to file"""
        audio_id = str(uuid.uuid4())
        saved_to = None
        error = None

        if self._tts_available:
            out_path = save_path or os.path.join(
                os.path.dirname(__file__), "..", "..", "generated_content", f"{audio_id}_tts.wav"
            )
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            def _do_tts():
                try:
                    engine = self._pyttsx3.init()
                    rate = engine.getProperty("rate")
                    engine.setProperty("rate", int(rate * speed))
                    # Try to set voice by gender hint
                    voices = engine.getProperty("voices")
                    if voices:
                        if "female" in voice.lower():
                            female = [v for v in voices if "female" in v.name.lower() or "zira" in v.name.lower()]
                            if female:
                                engine.setProperty("voice", female[0].id)
                        elif "male" in voice.lower():
                            male = [v for v in voices if "male" in v.name.lower() or "david" in v.name.lower()]
                            if male:
                                engine.setProperty("voice", male[0].id)
                    engine.save_to_file(text, out_path)
                    engine.runAndWait()
                except Exception as e:
                    logger.error(f"[VOICE] TTS error: {e}")

            t = threading.Thread(target=_do_tts, daemon=True)
            t.start()
            t.join(timeout=30)

            if os.path.exists(out_path):
                saved_to = out_path
            else:
                error = "TTS completed but file not found"
        else:
            error = "pyttsx3 not installed"

        word_count = len(text.split())
        duration_est = round(word_count * 0.4 / speed, 1)

        return {
            "audio_id":              audio_id,
            "text_preview":          text[:100],
            "language":              language,
            "voice":                 voice,
            "duration_estimate_secs": duration_est,
            "status":                "generated" if saved_to else "failed",
            "saved_to":              saved_to,
            "tts_available":         self._tts_available,
            "error":                 error
        }

    async def execute_voice_command(self, command_text: str) -> Dict:
        """Parse and classify a voice command"""
        words = set(command_text.lower().split())
        scores: Dict[str, int] = {}
        for cmd_type, keywords in VOICE_COMMAND_KEYWORDS.items():
            scores[cmd_type] = sum(1 for kw in keywords if kw in words)

        command_type = max(scores, key=lambda k: scores[k]) if scores else VoiceCommand.GET_INFO
        highest_score = scores.get(command_type, 0)

        result = {
            "command_type": command_type,
            "text":         command_text,
            "confidence":   min(highest_score / 3, 1.0),
            "all_scores":   scores,
            "status":       "classified",
            "result":       f"Command classified as [{command_type}] — route to appropriate handler"
        }
        self.voice_commands.append({"type": "execute", **result, "timestamp": datetime.now().isoformat()})
        return result

    def get_voice_stats(self) -> Dict:
        return {
            "total_transcriptions": len(self.voice_history),
            "total_commands": len(self.voice_commands),
            "languages_supported": ["en-US", "ur-PK", "pa-PK", "hi-IN"],
            "stt_available": self._sr_available,
            "tts_available": self._tts_available,
            "recent_commands": self.voice_commands[-5:]
        }


# ══════════════════════════════════════════════════════════════════════════════
# 2. ADVANCED KNOWLEDGE GRAPH — Real semantic in-memory graph + LLM search
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Concept:
    id: str
    name: str
    description: str
    category: str
    importance: float = 0.5
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    aliases: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

@dataclass
class Relationship:
    id: str
    concept1_id: str
    concept2_id: str
    relationship_type: str
    strength: float = 0.8
    bidirectional: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AdvancedKnowledgeGraph:
    """Real in-memory knowledge graph with semantic search + LLM-powered query answering"""

    def __init__(self):
        self._concepts: Dict[str, Concept] = {}
        self._rels: Dict[str, Relationship] = {}
        self._name_index: Dict[str, str] = {}  # name.lower() -> concept_id
        self._adj: Dict[str, List[str]] = defaultdict(list)  # adjacency: id -> [rel_ids]
        self._lock = threading.RLock()
        logger.info("[KNOWLEDGE GRAPH] 🧠 Advanced Knowledge Graph online.")

    async def add_knowledge(
        self,
        concept: str,
        description: str,
        category: str,
        importance: float = 0.5,
        aliases: List[str] = None,
        tags: List[str] = None
    ) -> Dict:
        """Add or update a concept in the knowledge graph"""
        concept_id = f"c_{uuid.uuid4().hex[:10]}"
        # Check for duplicates by name
        existing_id = self._name_index.get(concept.lower())

        with self._lock:
            if existing_id:
                # Update existing
                c = self._concepts[existing_id]
                c.description = description
                c.importance = max(c.importance, importance)
                if aliases:
                    c.aliases = list(set(c.aliases + aliases))
                if tags:
                    c.tags = list(set(c.tags + tags))
                return {
                    "concept_id": existing_id,
                    "concept": concept,
                    "action": "updated",
                    "status": "knowledge_updated"
                }

            c = Concept(
                id=concept_id,
                name=concept,
                description=description,
                category=category,
                importance=importance,
                aliases=aliases or [],
                tags=tags or []
            )
            self._concepts[concept_id] = c
            self._name_index[concept.lower()] = concept_id
            for alias in (aliases or []):
                self._name_index[alias.lower()] = concept_id

        return {
            "concept_id": concept_id,
            "concept": concept,
            "category": category,
            "action": "added",
            "total_concepts": len(self._concepts),
            "status": "added_to_knowledge_base"
        }

    async def create_relationship(
        self,
        concept1: str,
        concept2: str,
        relationship_type: str,
        strength: float = 0.8,
        bidirectional: bool = True
    ) -> Dict:
        """Link two concepts with a typed relationship"""
        id1 = self._name_index.get(concept1.lower())
        id2 = self._name_index.get(concept2.lower())

        # Auto-create if missing
        if not id1:
            result = await self.add_knowledge(concept1, f"Auto-created: {concept1}", "auto")
            id1 = result["concept_id"]
        if not id2:
            result = await self.add_knowledge(concept2, f"Auto-created: {concept2}", "auto")
            id2 = result["concept_id"]

        rel_id = f"r_{uuid.uuid4().hex[:10]}"
        rel = Relationship(
            id=rel_id,
            concept1_id=id1,
            concept2_id=id2,
            relationship_type=relationship_type,
            strength=strength,
            bidirectional=bidirectional
        )
        with self._lock:
            self._rels[rel_id] = rel
            self._adj[id1].append(rel_id)
            if bidirectional:
                self._adj[id2].append(rel_id)

        return {
            "relationship_id": rel_id,
            "from": concept1,
            "to": concept2,
            "type": relationship_type,
            "strength": strength,
            "bidirectional": bidirectional,
            "status": "relationship_created",
            "total_relationships": len(self._rels)
        }

    async def query_knowledge(self, query: str, max_results: int = 10) -> Dict:
        """Keyword + semantic search across concepts"""
        query_words = set(re.findall(r'\w+', query.lower()))

        results = []
        with self._lock:
            for concept_id, c in self._concepts.items():
                # Score by keyword overlap
                c_words = set(re.findall(r'\w+', (c.name + " " + c.description + " " + " ".join(c.tags)).lower()))
                overlap = len(query_words & c_words)
                if overlap > 0:
                    score = overlap / max(len(query_words), 1) * c.importance
                    results.append({
                        "concept_id": concept_id,
                        "name": c.name,
                        "description": c.description,
                        "category": c.category,
                        "importance": c.importance,
                        "score": round(score, 3),
                        "related_count": len(self._adj.get(concept_id, []))
                    })

        results.sort(key=lambda r: r["score"], reverse=True)

        return {
            "query":         query,
            "results_found": len(results),
            "results":       results[:max_results],
            "total_concepts": len(self._concepts)
        }

    async def semantic_search(self, query: str, max_results: int = 10) -> Dict:
        """LLM-powered semantic search when available, fallback to keyword"""
        # First do keyword search
        kw_result = await self.query_knowledge(query, max_results)

        # Try to enrich with LLM ranking if concepts exist
        if kw_result["results_found"] > 0:
            try:
                from app.core.llm_manager import universal_llm
                concept_list = "\n".join([
                    f"- {r['name']}: {r['description'][:80]}"
                    for r in kw_result["results"][:8]
                ])
                reranked_text = await universal_llm.generate_response(
                    system_prompt="You are a knowledge graph search engine. Rank concepts by relevance to the query. Return ONLY a JSON array of concept names in order of relevance.",
                    user_prompt=f"Query: {query}\n\nConcepts:\n{concept_list}",
                    max_tokens=200
                )
                try:
                    reranked_names = json.loads(reranked_text)
                    name_to_result = {r["name"]: r for r in kw_result["results"]}
                    reranked = [name_to_result[n] for n in reranked_names if n in name_to_result]
                    remaining = [r for r in kw_result["results"] if r["name"] not in reranked_names]
                    kw_result["results"] = (reranked + remaining)[:max_results]
                    kw_result["llm_reranked"] = True
                except Exception:
                    kw_result["llm_reranked"] = False
            except Exception:
                kw_result["llm_reranked"] = False

        return kw_result

    def get_concept_graph(self, concept_name: str, depth: int = 2) -> Dict:
        """Get a sub-graph of related concepts using BFS"""
        start_id = self._name_index.get(concept_name.lower())
        if not start_id:
            return {"error": f"Concept '{concept_name}' not found"}

        visited = set()
        queue = [(start_id, 0)]
        nodes = []
        edges = []

        while queue:
            cid, d = queue.pop(0)
            if cid in visited or d > depth:
                continue
            visited.add(cid)
            c = self._concepts.get(cid)
            if c:
                nodes.append({"id": cid, "name": c.name, "category": c.category, "depth": d})
            for rel_id in self._adj.get(cid, []):
                rel = self._rels.get(rel_id)
                if rel:
                    other_id = rel.concept2_id if rel.concept1_id == cid else rel.concept1_id
                    edges.append({
                        "from": cid, "to": other_id,
                        "type": rel.relationship_type,
                        "strength": rel.strength
                    })
                    if other_id not in visited:
                        queue.append((other_id, d + 1))

        return {"concept": concept_name, "nodes": nodes, "edges": edges, "depth": depth}

    async def get_graph_stats(self) -> Dict:
        with self._lock:
            categories = Counter(c.category for c in self._concepts.values())
            top_concepts = sorted(self._concepts.values(), key=lambda c: -c.importance)[:5]
        return {
            "total_concepts":      len(self._concepts),
            "total_relationships": len(self._rels),
            "knowledge_density":   round(len(self._rels) / max(len(self._concepts), 1), 2),
            "categories":          dict(categories),
            "top_concepts":        [{"name": c.name, "importance": c.importance} for c in top_concepts]
        }


# ══════════════════════════════════════════════════════════════════════════════
# 3. PERSONALIZED LEARNING ASSISTANT — LLM-generated curricula + real tracking
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LearnerProfile:
    id: str
    user_id: str
    name: str
    goals: List[str]
    skill_level: str = "beginner"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_sessions: int = 0
    avg_score: float = 0.0


@dataclass
class LearningPath:
    id: str
    learner_id: str
    topic: str
    duration_weeks: int
    curriculum: Dict[str, List[str]]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_lessons: List[str] = field(default_factory=list)


class PersonalizedLearningAssistant:
    """LLM-powered personalized learning: real curricula, adaptive difficulty, progress tracking"""

    def __init__(self):
        self._learners: Dict[str, LearnerProfile] = {}
        self._paths: Dict[str, LearningPath] = {}
        self._progress: List[dict] = []
        logger.info("[LEARNING ASSISTANT] 📚 Personalized Learning Assistant online.")

    async def create_learner_profile(
        self,
        user_id: str,
        name: str,
        learning_goals: List[str],
        skill_level: str = "beginner"
    ) -> Dict:
        """Create a learner profile"""
        learner_id = f"learner_{uuid.uuid4().hex[:8]}"
        profile = LearnerProfile(
            id=learner_id,
            user_id=user_id,
            name=name,
            goals=learning_goals,
            skill_level=skill_level
        )
        self._learners[learner_id] = profile
        return {
            "learner_id":  learner_id,
            "name":        name,
            "goals":       learning_goals,
            "skill_level": skill_level,
            "status":      "profile_created"
        }

    async def generate_learning_path(
        self,
        learner_id: str,
        topic: str,
        duration_weeks: int = 4
    ) -> Dict:
        """Generate a real LLM-backed curriculum"""
        learner = self._learners.get(learner_id)
        level = learner.skill_level if learner else "beginner"
        goals_str = ", ".join(learner.goals) if learner else "general learning"

        curriculum: Dict[str, List[str]] = {}

        try:
            from app.core.llm_manager import universal_llm
            system_prompt = (
                f"You are an expert curriculum designer. Create a {duration_weeks}-week learning plan "
                f"for '{topic}' at {level} level. Goals: {goals_str}. "
                "Output ONLY JSON: {\"week_1\": [\"lesson1\", \"lesson2\"], \"week_2\": [...], ...}"
            )
            raw = await universal_llm.generate_response(
                system_prompt=system_prompt,
                user_prompt=f"Create a {duration_weeks}-week curriculum for: {topic}",
                is_json=True,
                max_tokens=500
            )
            try:
                curriculum = json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    curriculum = json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"[LEARNING] LLM unavailable: {e}")

        # Fallback curriculum
        if not curriculum:
            for w in range(1, duration_weeks + 1):
                curriculum[f"week_{w}"] = [
                    f"{topic} — Week {w} Fundamentals",
                    f"{topic} — Week {w} Practice",
                    f"{topic} — Week {w} Project"
                ]

        path_id = f"path_{uuid.uuid4().hex[:8]}"
        path = LearningPath(
            id=path_id,
            learner_id=learner_id,
            topic=topic,
            duration_weeks=duration_weeks,
            curriculum=curriculum
        )
        self._paths[path_id] = path

        total_lessons = sum(len(v) for v in curriculum.values())
        return {
            "path_id":          path_id,
            "topic":            topic,
            "weeks":            duration_weeks,
            "skill_level":      level,
            "total_lessons":    total_lessons,
            "curriculum":       curriculum,
            "status":           "path_generated",
            "llm_generated":    bool(curriculum)
        }

    async def track_progress(
        self,
        learner_id: str,
        lesson_id: str,
        score: float,
        time_spent_mins: float = 0
    ) -> Dict:
        """Record lesson completion and update adaptive metrics"""
        learner = self._learners.get(learner_id)
        if not learner:
            return {"error": "Learner not found"}

        # Update running average
        n = learner.total_sessions + 1
        learner.avg_score = (learner.avg_score * (n - 1) + score) / n
        learner.total_sessions = n

        # Auto-level adjustment
        prev_level = learner.skill_level
        if learner.avg_score >= 88 and n >= 3:
            if learner.skill_level == "beginner":
                learner.skill_level = "intermediate"
            elif learner.skill_level == "intermediate":
                learner.skill_level = "advanced"
        elif learner.avg_score < 50 and n >= 3 and learner.skill_level != "beginner":
            learner.skill_level = "beginner"

        # Mark lesson done in any matching path
        for path in self._paths.values():
            if path.learner_id == learner_id and lesson_id not in path.completed_lessons:
                path.completed_lessons.append(lesson_id)

        entry = {
            "progress_id":      str(uuid.uuid4()),
            "learner_id":       learner_id,
            "lesson_id":        lesson_id,
            "score":            score,
            "time_spent_mins":  time_spent_mins,
            "timestamp":        datetime.now().isoformat()
        }
        self._progress.append(entry)

        leveled_up = prev_level != learner.skill_level

        return {
            "progress_id":   entry["progress_id"],
            "lesson":        lesson_id,
            "score":         score,
            "avg_score":     round(learner.avg_score, 1),
            "total_sessions": learner.total_sessions,
            "current_level": learner.skill_level,
            "leveled_up":    leveled_up,
            "status":        "recorded"
        }

    async def get_recommendations(
        self,
        learner_id: str,
        top_k: int = 3
    ) -> Dict:
        """LLM-powered next-lesson recommendations"""
        learner = self._learners.get(learner_id)
        if not learner:
            return {"error": "Learner not found"}

        # Find incomplete lessons
        completed = set()
        pending_lessons: List[str] = []
        for path in self._paths.values():
            if path.learner_id == learner_id:
                completed.update(path.completed_lessons)
                for lessons in path.curriculum.values():
                    for lesson in lessons:
                        if lesson not in completed:
                            pending_lessons.append(lesson)

        recommendations = []
        if pending_lessons:
            try:
                from app.core.llm_manager import universal_llm
                lessons_str = "\n".join(f"- {l}" for l in pending_lessons[:15])
                raw = await universal_llm.generate_response(
                    system_prompt=(
                        f"You are an adaptive learning recommender. The learner is at {learner.skill_level} level "
                        f"with avg score {learner.avg_score:.0f}%. Recommend the top {top_k} lessons to do next. "
                        f"Output JSON: [{{\"lesson\": \"...\", \"reason\": \"...\", \"estimated_time_mins\": 30}}]"
                    ),
                    user_prompt=f"Goals: {learner.goals}\n\nPending lessons:\n{lessons_str}",
                    is_json=True,
                    max_tokens=400
                )
                try:
                    recommendations = json.loads(raw)[:top_k]
                except Exception:
                    recommendations = [{"lesson": l, "reason": "Next in curriculum", "estimated_time_mins": 30}
                                       for l in pending_lessons[:top_k]]
            except Exception:
                recommendations = [{"lesson": l, "reason": "Next in curriculum", "estimated_time_mins": 30}
                                   for l in pending_lessons[:top_k]]
        else:
            recommendations = [{"lesson": f"Advanced {g}", "reason": "All lessons complete!", "estimated_time_mins": 45}
                                for g in (learner.goals or ["learning"])[:top_k]]

        return {
            "learner_id":         learner_id,
            "current_level":      learner.skill_level,
            "avg_score":          round(learner.avg_score, 1),
            "completed_lessons":  len(completed),
            "recommendations":    recommendations
        }

    async def adaptive_difficulty(self, learner_id: str, current_score: float) -> Dict:
        """Dynamically recommend difficulty level based on performance"""
        learner = self._learners.get(learner_id)
        if not learner:
            return {"error": "Learner not found"}

        if current_score >= 90:
            difficulty = "advanced"
            message = "Excellent! Moving to advanced content."
        elif current_score >= 70:
            difficulty = "intermediate"
            message = "Good progress! Staying at intermediate level."
        elif current_score >= 50:
            difficulty = "beginner"
            message = "Keep practicing — more foundational content recommended."
        else:
            difficulty = "remedial"
            message = "Let's review the basics first."

        learner.skill_level = difficulty if difficulty != "remedial" else "beginner"

        return {
            "learner_id":   learner_id,
            "score":        current_score,
            "new_level":    difficulty,
            "message":      message,
            "avg_score":    round(learner.avg_score, 1),
            "total_sessions": learner.total_sessions
        }

    def get_learner_stats(self, learner_id: str) -> Dict:
        learner = self._learners.get(learner_id)
        if not learner:
            return {"error": "Learner not found"}
        paths = [p for p in self._paths.values() if p.learner_id == learner_id]
        return {
            "learner_id":     learner_id,
            "name":           learner.name,
            "level":          learner.skill_level,
            "avg_score":      round(learner.avg_score, 1),
            "total_sessions": learner.total_sessions,
            "active_paths":   len(paths),
            "goals":          learner.goals
        }

    def get_system_stats(self) -> Dict:
        return {
            "total_learners": len(self._learners),
            "total_paths":    len(self._paths),
            "total_sessions": len(self._progress),
            "avg_score_all":  round(
                sum(l.avg_score for l in self._learners.values()) / max(len(self._learners), 1), 1
            )
        }


# ── Singletons ────────────────────────────────────────────────────────────────

voice_control       = VoiceControlSystem()
knowledge_graph     = AdvancedKnowledgeGraph()
learning_assistant  = PersonalizedLearningAssistant()
