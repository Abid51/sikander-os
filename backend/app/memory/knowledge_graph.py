"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS KNOWLEDGE GRAPH — Akashic Web of Everything                         ║
║  "Every truth is connected. I find the hidden path between them."          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import threading
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime
from collections import defaultdict, deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False
    logger.info("[KNOWLEDGE GRAPH] networkx not installed. Using built-in graph. Install: pip install networkx")


# ─── Data Structures ──────────────────────────────────────────────────────────────

@dataclass
class KGNode:
    node_id: str
    label: str
    node_type: str          # concept | person | tool | event | place | fact
    mentions: int = 1
    importance: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)
    properties: dict = field(default_factory=dict)  # alias storage for test API


@dataclass
class KGEdge:
    source: str
    target: str
    relation: str           # related_to | causes | enables | opposite_of | part_of | uses
    weight: float = 1.0
    evidence: str = ""


class KnowledgeGraph:
    """
    Igris Akashic Knowledge Graph.

    Automatically extracts entities and relationships from every conversation,
    builds an ever-growing semantic web, and can:
    • Find unexpected connections between concepts
    • Answer "tell me everything about X"
    • Discover the shortest path between any two ideas
    • Identify the most central/important concepts (PageRank)
    • Export as JSON for frontend visualization
    """

    GRAPH_FILE = "igris_knowledge_graph.json"
    MAX_NODES  = 5000
    MAX_EDGES  = 20000

    ENTITY_PATTERNS = [
        r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b',           # Proper nouns
        r'\b(python|javascript|react|docker|api|ai|ml|llm|database|server|'
        r'blockchain|crypto|bitcoin|ethereum|gpt|ollama|fastapi|electron)\b',  # Tech
        r'\b(\w+(?:\.py|\.js|\.ts|\.json|\.yaml|\.env))\b',  # File names
    ]

    RELATION_MAP = {
        ("uses", "using", "with"):           "uses",
        ("causes", "leads to", "results in"): "causes",
        ("is a", "type of", "kind of"):      "is_a",
        ("part of", "inside", "within"):     "part_of",
        ("opposite", "unlike", "vs"):        "opposite_of",
        ("enables", "allows", "helps"):      "enables",
        ("replaces", "instead of"):          "replaces",
    }

    def __init__(self, persist_path: Optional[str] = None):
        self._lock = threading.RLock()
        self._nodes: Dict[str, KGNode] = {}
        self._edges: Dict[str, KGEdge] = {}   # key: source:relation:target
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        if persist_path:
            self._file = os.path.normpath(persist_path)
        else:
            self._file = os.path.normpath(os.path.join(base_dir, "..", "..", self.GRAPH_FILE))
        self._load()
        logger.info("[KNOWLEDGE GRAPH] 🕸️  Online. Nodes: %d  Edges: %d",
                    len(self._nodes), len(self._edges))

    @staticmethod
    def _norm_id(label: str) -> str:
        s = label.strip().lower().replace(" ", "_").replace("-", "_")
        return re.sub(r"[^a-z0-9_]", "", s) or "node"

    def add_node(
        self,
        label: str,
        node_type: str = "concept",
        properties: Optional[dict] = None,
    ) -> dict:
        """Explicitly add a node (used by tests and admin tools)."""
        nid = self._norm_id(label)
        with self._lock:
            if len(self._nodes) >= self.MAX_NODES:
                self._evict_least_important()
            if nid in self._nodes:
                self._nodes[nid].mentions += 1
                if properties:
                    self._nodes[nid].metadata.update(properties)
                    self._nodes[nid].properties.update(properties)
            else:
                self._nodes[nid] = KGNode(
                    node_id=nid,
                    label=label,
                    node_type=node_type,
                    metadata=dict(properties or {}),
                    properties=dict(properties or {}),
                )
        self._save()
        return {"id": nid, "label": label, "type": node_type}

    def get_node(self, key: str) -> Optional[dict]:
        k = self._norm_id(key)
        with self._lock:
            n = self._nodes.get(k) or self._nodes.get(key)
        if not n:
            return None
        return {
            "id":    n.node_id,
            "label": n.label,
            "type":  n.node_type,
            "metadata": {**n.metadata, **n.properties},
        }

    def add_relationship(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
    ) -> Optional[dict]:
        """Add an edge if both nodes exist; creates nodes if missing (minimal)."""
        s_id = self._norm_id(source)
        t_id = self._norm_id(target)
        if s_id not in self._nodes:
            self.add_node(source, "concept", {})
        if t_id not in self._nodes:
            self.add_node(target, "concept", {})
        self._add_edge(s_id, t_id, relation, weight, "manual")
        self._save()
        return {
            "source": s_id,
            "target": t_id,
            "relation": relation,
        }

    def search_nodes(self, query: str, top_k: int = 20) -> List[dict]:
        """Convenience alias for :meth:`search`."""
        return self.search(query, top_k=top_k)

    # ──────────────────────────────────────────────────────────────────
    # INGESTION
    # ──────────────────────────────────────────────────────────────────

    def ingest_text(self, text: str, source: str = "conversation") -> int:
        """Extract entities and relations from text. Returns number of new nodes added."""
        entities = self._extract_entities(text)
        if not entities:
            return 0

        added = 0
        with self._lock:
            for entity in entities:
                nid = entity.lower().replace(" ", "_")
                if nid in self._nodes:
                    self._nodes[nid].mentions += 1
                    self._nodes[nid].importance = min(1.0, self._nodes[nid].mentions / 50)
                else:
                    if len(self._nodes) >= self.MAX_NODES:
                        self._evict_least_important()
                    self._nodes[nid] = KGNode(
                        node_id=nid,
                        label=entity,
                        node_type=self._classify_entity(entity),
                        metadata={"source": source},
                    )
                    added += 1

            # Co-occurrence edges: entities appearing together are related
            elist = list(entities)
            for i in range(len(elist)):
                for j in range(i + 1, min(i + 4, len(elist))):
                    self._add_edge(
                        elist[i].lower().replace(" ", "_"),
                        elist[j].lower().replace(" ", "_"),
                        "co_occurs",
                        weight=0.5,
                        evidence=text[:80],
                    )

            # Explicit relations
            rels = self._extract_relations(text, elist)
            for src, rel, tgt in rels:
                self._add_edge(
                    src.lower().replace(" ", "_"),
                    tgt.lower().replace(" ", "_"),
                    rel, weight=1.0, evidence=text[:80],
                )

        if added > 0:
            self._save()
        return added

    def _extract_entities(self, text: str) -> Set[str]:
        entities: Set[str] = set()
        for pattern in self.ENTITY_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                raw = m.group(1).strip()
                if 2 < len(raw) < 50 and not raw.lower() in STOPWORDS:
                    entities.add(raw.lower())
        return entities

    def _classify_entity(self, label: str) -> str:
        label_l = label.lower()
        if any(ext in label_l for ext in [".py", ".js", ".ts", ".json"]):
            return "file"
        if any(kw in label_l for kw in ["api", "server", "db", "database"]):
            return "tool"
        if label[0].isupper():
            return "concept"
        return "concept"

    def _extract_relations(self, text: str, entities: List[str]) -> List[Tuple[str, str, str]]:
        rels = []
        t = text.lower()
        for kws, rel in self.RELATION_MAP.items():
            for kw in kws:
                idx = t.find(kw)
                if idx < 0:
                    continue
                # Find nearest entities on left and right
                before = [e for e in entities if t.rfind(e.lower(), 0, idx) >= 0]
                after  = [e for e in entities if t.find(e.lower(), idx) >= 0]
                if before and after and before[-1] != after[0]:
                    rels.append((before[-1], rel, after[0]))
        return rels

    def _add_edge(self, src: str, tgt: str, relation: str, weight: float, evidence: str):
        if src not in self._nodes or tgt not in self._nodes:
            return
        if src == tgt:
            return
        key = f"{src}:{relation}:{tgt}"
        if key in self._edges:
            self._edges[key].weight = min(self._edges[key].weight + 0.1, 5.0)
        else:
            if len(self._edges) >= self.MAX_EDGES:
                return
            self._edges[key] = KGEdge(src, tgt, relation, weight, evidence)
        self._adjacency[src].add(tgt)
        self._adjacency[tgt].add(src)

    # ──────────────────────────────────────────────────────────────────
    # QUERY
    # ──────────────────────────────────────────────────────────────────

    def neighbours(self, node_id: str, depth: int = 1) -> List[dict]:
        """Get all nodes connected to node_id within `depth` hops."""
        visited: Set[str] = set()
        frontier = {node_id.lower().replace(" ", "_")}
        result = []
        for _ in range(depth):
            next_frontier: Set[str] = set()
            for nid in frontier:
                with self._lock:
                    for neighbour in self._adjacency.get(nid, set()):
                        if neighbour not in visited:
                            visited.add(neighbour)
                            next_frontier.add(neighbour)
                            node = self._nodes.get(neighbour)
                            if node:
                                result.append({
                                    "id": node.node_id, "label": node.label,
                                    "type": node.node_type, "importance": node.importance,
                                })
            frontier = next_frontier
        return result

    def shortest_path(self, from_id: str, to_id: str) -> List[str]:
        """BFS shortest path between two nodes."""
        start = from_id.lower().replace(" ", "_")
        end   = to_id.lower().replace(" ", "_")
        if start not in self._nodes or end not in self._nodes:
            return []
        visited    = {start}
        queue      = deque([[start]])
        while queue:
            path = queue.popleft()
            node = path[-1]
            if node == end:
                return [self._nodes[n].label for n in path if n in self._nodes]
            for nb in self._adjacency.get(node, set()):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(path + [nb])
        return []

    def most_important_nodes(self, top_k: int = 10) -> List[dict]:
        """Return top-K nodes by importance (mentions + connections)."""
        with self._lock:
            ranked = sorted(
                self._nodes.values(),
                key=lambda n: n.importance * (1 + len(self._adjacency.get(n.node_id, set())) * 0.1),
                reverse=True,
            )[:top_k]
        return [{"id": n.node_id, "label": n.label, "type": n.node_type,
                 "importance": n.importance, "connections": len(self._adjacency.get(n.node_id, set()))}
                for n in ranked]

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """Fuzzy search nodes by label."""
        q = query.lower()
        with self._lock:
            matches = [n for n in self._nodes.values()
                       if q in n.label.lower() or q in n.node_id]
        matches.sort(key=lambda n: n.importance, reverse=True)
        return [{"id": n.node_id, "label": n.label, "type": n.node_type,
                 "importance": n.importance} for n in matches[:top_k]]

    def export_for_viz(self, max_nodes: int = 300) -> dict:
        """Export graph as {nodes, links} for D3.js / Three.js frontend."""
        with self._lock:
            top_nodes = sorted(self._nodes.values(), key=lambda n: n.importance, reverse=True)[:max_nodes]
            node_ids  = {n.node_id for n in top_nodes}
            edges     = [{"source": e.source, "target": e.target, "relation": e.relation, "weight": e.weight}
                         for e in self._edges.values()
                         if e.source in node_ids and e.target in node_ids]
        return {
            "nodes": [{"id": n.node_id, "label": n.label, "type": n.node_type,
                       "importance": n.importance, "mentions": n.mentions}
                      for n in top_nodes],
            "links": edges,
        }

    # ──────────────────────────────────────────────────────────────────
    # MAINTENANCE
    # ──────────────────────────────────────────────────────────────────

    def _evict_least_important(self):
        if not self._nodes:
            return
        least = min(self._nodes.values(), key=lambda n: n.importance * (n.mentions + 1))
        del self._nodes[least.node_id]
        self._adjacency.pop(least.node_id, None)

    def _save(self):
        try:
            data = {
                "nodes": {nid: {"label": n.label, "type": n.node_type,
                                "mentions": n.mentions, "importance": n.importance}
                          for nid, n in self._nodes.items()},
                "edges": {k: {"source": e.source, "target": e.target,
                               "relation": e.relation, "weight": e.weight}
                          for k, e in self._edges.items()},
            }
            with open(self._file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.debug("[KNOWLEDGE GRAPH] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file) as f:
                data = json.load(f)
            for nid, nd in data.get("nodes", {}).items():
                self._nodes[nid] = KGNode(node_id=nid, **{k: v for k, v in nd.items()
                                                           if k in KGNode.__dataclass_fields__})
            for k, ed in data.get("edges", {}).items():
                e = KGEdge(**{k2: v for k2, v in ed.items() if k2 in KGEdge.__dataclass_fields__})
                self._edges[k] = e
                self._adjacency[e.source].add(e.target)
                self._adjacency[e.target].add(e.source)
            logger.info("[KNOWLEDGE GRAPH] Loaded %d nodes, %d edges.", len(self._nodes), len(self._edges))
        except Exception as e:
            logger.debug("[KNOWLEDGE GRAPH] Load error: %s", e)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_nodes":    len(self._nodes),
                "total_edges":    len(self._edges),
                "top_concepts":   self.most_important_nodes(5),
                "graph_file":     self._file,
            }


STOPWORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "and", "or", "but",
    "not", "be", "was", "are", "for", "this", "that", "with", "from", "by",
    "have", "has", "do", "does", "will", "can", "you", "i", "we", "they",
    "my", "your", "our", "its", "me", "him", "her", "us", "them",
    "yeh", "woh", "main", "tum", "aap", "kya", "hai", "hain", "tha",
}


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[KnowledgeGraph] = None
_lock = threading.Lock()

def get_knowledge_graph() -> KnowledgeGraph:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = KnowledgeGraph()
    return _instance
