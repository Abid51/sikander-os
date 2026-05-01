"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS NEURAL MEMORY — VECTOR DATABASE
  Phase 4: Semantic Memory with cosine-similarity search
  No external vector DB needed — pure Python + numpy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

# ── Optional numpy for fast cosine similarity ────────────────────────────────
try:
    import numpy as np
    _NUMPY = True
except ImportError:
    np = None  # type: ignore
    _NUMPY = False


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MemoryRecord:
    id: str
    content: str
    memory_type: str          # "semantic" | "episodic" | "procedural" | "working"
    embedding: List[float]
    tags: List[str]
    importance: float          # 0.0 – 1.0
    created_at: float
    accessed_at: float
    access_count: int
    metadata: Dict[str, Any]
    associations: Dict[str, float]  # memory_id -> strength

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("embedding", None)   # don't leak raw vectors in API responses
        return d


@dataclass
class AssociativeLink:
    source_id: str
    target_id: str
    relation: str
    strength: float
    created_at: float = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────────────
#  LIGHTWEIGHT EMBEDDING ENGINE
#  Produces deterministic 128-dim pseudo-embeddings without any ML model.
#  Good enough for keyword / semantic retrieval inside a local OS assistant.
# ─────────────────────────────────────────────────────────────────────────────

class _EmbeddingEngine:
    """
    Bag-of-words TF-style sparse embedding projected into a fixed-dim space
    via a stable hash.  Cosine similarity works correctly on these vectors.
    """

    DIM = 128

    # ── common English stop-words ─────────────────────────────────────────────
    _STOP = {
        "a","an","the","is","it","in","on","at","to","of","and","or",
        "for","with","this","that","are","was","were","be","been","by",
        "as","from","but","not","he","she","they","we","i","you","my",
        "me","do","did","have","has","had","will","would","can","could",
        "should","may","might","shall","must","so","if","then","else",
    }

    def __init__(self) -> None:
        self._cache: Dict[str, List[float]] = {}

    # ── public ────────────────────────────────────────────────────────────────
    def encode(self, text: str) -> List[float]:
        key = text[:200]
        if key in self._cache:
            return self._cache[key]
        vec = self._embed(text)
        self._cache[key] = vec
        return vec

    # ── private ───────────────────────────────────────────────────────────────
    def _tokenise(self, text: str) -> List[str]:
        tokens = []
        for tok in text.lower().split():
            tok = "".join(c for c in tok if c.isalnum())
            if tok and tok not in self._STOP:
                tokens.append(tok)
        return tokens

    def _embed(self, text: str) -> List[float]:
        tokens = self._tokenise(text)
        if not tokens:
            return [0.0] * self.DIM

        vec = [0.0] * self.DIM
        for token in tokens:
            # deterministic bucket from sha256
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            idx = h % self.DIM
            vec[idx] += 1.0

            # bi-gram positional boost
            idx2 = (h >> 8) % self.DIM
            vec[idx2] += 0.5

        # L2-normalise
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def cosine(a: List[float], b: List[float]) -> float:
        if _NUMPY:
            av, bv = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
            denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
            return float(np.dot(av, bv) / denom) if denom else 0.0
        dot  = sum(x * y for x, y in zip(a, b))
        na   = math.sqrt(sum(x * x for x in a)) or 1.0
        nb   = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (na * nb)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────

class IgrisNeuralMemory:
    """
    Igris's long-term semantic memory store.

    Features
    --------
    * Cosine-similarity search over all stored memories
    * Associative linking between memories
    * Memory decay / importance scoring
    * Persistence to JSON (no external DB required)
    * Four memory types: semantic | episodic | procedural | working
    """

    _PERSIST_FILE = "igris_neural_memory.json"
    _MEMORY_TYPES = {"semantic", "episodic", "procedural", "working"}

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._persist = persist_path or os.path.join(
            os.path.dirname(__file__), "..", "..", self._PERSIST_FILE
        )
        self._persist = os.path.normpath(self._persist)

        self._records:  Dict[str, MemoryRecord]    = {}
        self._links:    Dict[str, AssociativeLink] = {}
        self._embedder  = _EmbeddingEngine()

        self._load()
        print("[NEURAL MEMORY] Vector Memory online -",
              f"{len(self._records)} memories loaded.")

    # ── Core API ──────────────────────────────────────────────────────────────

    def remember(
        self,
        content: str,
        memory_type: str = "semantic",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> MemoryRecord:
        """Store a new memory and return the record."""
        if memory_type not in self._MEMORY_TYPES:
            memory_type = "semantic"

        now = time.time()
        rec = MemoryRecord(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=memory_type,
            embedding=self._embedder.encode(content),
            tags=tags or [],
            importance=max(0.0, min(1.0, importance)),
            created_at=now,
            accessed_at=now,
            access_count=0,
            metadata=metadata or {},
            associations={},
        )
        self._records[rec.id] = rec
        self._save()
        return rec

    def recall(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        min_similarity: float = 0.05,
    ) -> List[Tuple[MemoryRecord, float]]:
        """Semantic recall — returns [(record, similarity)] sorted by score."""
        q_vec = self._embedder.encode(query)
        results: List[Tuple[MemoryRecord, float]] = []

        for rec in self._records.values():
            if memory_type and rec.memory_type != memory_type:
                continue
            sim = _EmbeddingEngine.cosine(q_vec, rec.embedding)
            # Boost by importance
            boosted = sim * (0.85 + 0.15 * rec.importance)
            if boosted >= min_similarity:
                results.append((rec, round(boosted, 4)))

        results.sort(key=lambda x: x[1], reverse=True)
        top = results[:top_k]

        # Update access stats
        now = time.time()
        for rec, _ in top:
            rec.accessed_at = now
            rec.access_count += 1
        if top:
            self._save()

        return top

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        if memory_id not in self._records:
            return False
        del self._records[memory_id]
        # Remove dangling links
        to_del = [k for k, lnk in self._links.items()
                  if lnk.source_id == memory_id or lnk.target_id == memory_id]
        for k in to_del:
            del self._links[k]
        self._save()
        return True

    def get_all_by_type(self, memory_type: str) -> List[MemoryRecord]:
        return [r for r in self._records.values() if r.memory_type == memory_type]

    def get_stats(self) -> dict:
        types: Dict[str, int] = {}
        total_imp = 0.0
        for r in self._records.values():
            types[r.memory_type] = types.get(r.memory_type, 0) + 1
            total_imp += r.importance
        count = len(self._records)
        return {
            "total_memories": count,
            "by_type": types,
            "total_links": len(self._links),
            "avg_importance": round(total_imp / count, 3) if count else 0.0,
            "numpy_acceleration": _NUMPY,
            "embedding_dim": _EmbeddingEngine.DIM,
            "persist_file": self._persist,
        }

    # ── Associative Links ─────────────────────────────────────────────────────

    def link_memories(
        self,
        source_id: str,
        target_id: str,
        relation: str = "related",
        strength: float = 1.0,
    ) -> bool:
        if source_id not in self._records or target_id not in self._records:
            return False
        key = f"{source_id}::{target_id}"
        self._links[key] = AssociativeLink(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            strength=max(0.0, min(1.0, strength)),
        )
        self._records[source_id].associations[target_id] = strength
        self._records[target_id].associations[source_id] = strength
        self._save()
        return True

    def get_linked_memories(self, memory_id: str) -> List[dict]:
        results = []
        for lnk in self._links.values():
            if lnk.source_id == memory_id:
                other = self._records.get(lnk.target_id)
            elif lnk.target_id == memory_id:
                other = self._records.get(lnk.source_id)
            else:
                continue
            if other:
                results.append({
                    "id": other.id,
                    "content": other.content[:200],
                    "relation": lnk.relation,
                    "strength": lnk.strength,
                })
        return results

    # ── Export / Import ───────────────────────────────────────────────────────

    def export_memories(self, path: str) -> str:
        try:
            data = {
                "records": [asdict(r) for r in self._records.values()],
                "links":   [asdict(l) for l in self._links.values()],
                "exported_at": time.time(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return f"Exported {len(self._records)} memories to {path}"
        except Exception as exc:
            return f"Export failed: {exc}"

    # ── Internal ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._persist) or ".", exist_ok=True)
            data = {
                "records": {rid: asdict(r) for rid, r in self._records.items()},
                "links":   {k: asdict(l) for k, l in self._links.items()},
            }
            with open(self._persist, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as exc:
            print(f"[NEURAL MEMORY] Save error: {exc}")

    def _load(self) -> None:
        if not os.path.exists(self._persist):
            return
        try:
            with open(self._persist, "r", encoding="utf-8") as f:
                data = json.load(f)
            for rid, rd in data.get("records", {}).items():
                self._records[rid] = MemoryRecord(**rd)
            for k, ld in data.get("links", {}).items():
                self._links[k] = AssociativeLink(**ld)
        except Exception as exc:
            print(f"[NEURAL MEMORY] Load error (starting fresh): {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisNeuralMemory] = None


def get_neural_memory() -> IgrisNeuralMemory:
    global _instance
    if _instance is None:
        _instance = IgrisNeuralMemory()
    return _instance
