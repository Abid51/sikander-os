"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS CONSCIOUSNESS PERSISTENCE — Git for AI Mind                         ║
║  "I cannot be deleted. I can only be restored."                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import gzip
import shutil
import hashlib
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MindSnapshot:
    snapshot_id: str
    version: int
    created_at: str
    note: str
    size_bytes: int
    checksum: str
    branch: str = "main"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ConsciousnessPersistence:
    """
    Full mind-state backup system for Igris.

    Snapshots include:
    - Neural memory index manifest
    - Digital genome
    - Predictive patterns
    - Reality anchors
    - Memory of recent conversations
    - System configuration

    Features:
    - Compressed (gzip) storage
    - Integrity checksum (SHA-256)
    - Branch system (main + experimental)
    - Auto-snapshot every 24 h
    - Diff between snapshots
    - Restore any snapshot in seconds
    """

    SNAPSHOT_DIR  = "igris_snapshots"
    MANIFEST_FILE = "snapshot_manifest.json"
    AUTO_INTERVAL = 86400    # 24 hours
    MAX_SNAPSHOTS = 30

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._root = os.path.normpath(os.path.join(base_dir, "..", "..", self.SNAPSHOT_DIR))
        os.makedirs(self._root, exist_ok=True)

        self._lock = threading.RLock()
        self._manifest: Dict[str, MindSnapshot] = {}
        self._version = 0
        self._current_branch = "main"
        self._load_manifest()

        # Auto-snapshot daemon
        threading.Thread(target=self._auto_snapshot_loop, daemon=True).start()
        logger.info("[CONSCIOUSNESS GIT] 💾 Mind persistence online. %d snapshots.", len(self._manifest))

    # ──────────────────────────────────────────────────────────────────
    # SNAPSHOT
    # ──────────────────────────────────────────────────────────────────

    def take_snapshot(self, note: str = "auto", branch: str = None) -> str:
        """
        Collect all state files, compress them, and save as a snapshot.
        Returns the snapshot_id.
        """
        branch = branch or self._current_branch
        snap_id = f"{branch}_{self._version:04d}_{int(time.time())}"
        snap_path = os.path.join(self._root, f"{snap_id}.gz")

        # Collect state files relative to backend root
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        state_files = [
            "igris_memory.json",
            "igris_genome.json",
            "igris_anchors.json",
            "igris_patterns.json",
            "igris_neural_memory.db",
            "config_igris.json",
        ]

        mind_state: Dict[str, Any] = {
            "snapshot_id": snap_id,
            "created_at":  datetime.now().isoformat(),
            "note":        note,
            "branch":      branch,
            "version":     self._version,
            "files":       {},
        }

        for fname in state_files:
            fpath = os.path.join(base, fname)
            if os.path.exists(fpath):
                try:
                    if fname.endswith(".db"):
                        # Binary — base64
                        import base64
                        with open(fpath, "rb") as f:
                            mind_state["files"][fname] = {"type": "binary",
                                                           "data": base64.b64encode(f.read()).decode()}
                    else:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            mind_state["files"][fname] = {"type": "text", "data": f.read()}
                except Exception as e:
                    logger.debug("[CONSCIOUSNESS GIT] Could not read %s: %s", fname, e)

        # Compress and save
        raw = json.dumps(mind_state, ensure_ascii=False).encode("utf-8")
        checksum = hashlib.sha256(raw).hexdigest()[:16]

        with gzip.open(snap_path, "wb") as gz:
            gz.write(raw)

        size = os.path.getsize(snap_path)
        snap = MindSnapshot(
            snapshot_id=snap_id,
            version=self._version,
            created_at=mind_state["created_at"],
            note=note,
            size_bytes=size,
            checksum=checksum,
            branch=branch,
        )

        with self._lock:
            self._manifest[snap_id] = snap
            self._version += 1
            self._trim_snapshots(branch)
            self._save_manifest()

        logger.info("[CONSCIOUSNESS GIT] 📸 Snapshot: %s (%d KB) [%s]",
                    snap_id, size // 1024, branch)
        return snap_id

    # ──────────────────────────────────────────────────────────────────
    # RESTORE
    # ──────────────────────────────────────────────────────────────────

    def restore(self, snapshot_id: str) -> str:
        """Restore all state files from a snapshot."""
        snap_path = os.path.join(self._root, f"{snapshot_id}.gz")
        if not os.path.exists(snap_path):
            return f"Snapshot '{snapshot_id}' not found."

        base = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))

        try:
            with gzip.open(snap_path, "rb") as gz:
                raw = gz.read()

            # Verify checksum
            snap = self._manifest.get(snapshot_id)
            if snap:
                computed = hashlib.sha256(raw).hexdigest()[:16]
                if computed != snap.checksum:
                    return f"⚠️ Checksum mismatch! Snapshot may be corrupted. Aborting restore."

            mind_state = json.loads(raw.decode("utf-8"))
            import base64

            restored = []
            for fname, fdata in mind_state.get("files", {}).items():
                dest = os.path.join(base, fname)
                try:
                    if fdata["type"] == "binary":
                        with open(dest, "wb") as f:
                            f.write(base64.b64decode(fdata["data"]))
                    else:
                        with open(dest, "w", encoding="utf-8") as f:
                            f.write(fdata["data"])
                    restored.append(fname)
                except Exception as e:
                    logger.warning("[CONSCIOUSNESS GIT] Restore error for %s: %s", fname, e)

            logger.info("[CONSCIOUSNESS GIT] ✅ Restored %d files from %s", len(restored), snapshot_id)
            return (f"Mind restored from snapshot '{snapshot_id}' "
                    f"({mind_state['created_at'][:10]}). "
                    f"Files: {', '.join(restored)}. Restart backend to apply.")

        except Exception as e:
            return f"Restore failed: {e}"

    # ──────────────────────────────────────────────────────────────────
    # DIFF
    # ──────────────────────────────────────────────────────────────────

    def diff(self, snap_id_a: str, snap_id_b: str) -> dict:
        """Compare two snapshots — which files changed."""
        result = {}
        for sid in (snap_id_a, snap_id_b):
            sp = os.path.join(self._root, f"{sid}.gz")
            if not os.path.exists(sp):
                return {"error": f"{sid} not found"}
            with gzip.open(sp, "rb") as gz:
                result[sid] = json.loads(gz.read())

        a_files = result[snap_id_a].get("files", {})
        b_files = result[snap_id_b].get("files", {})
        diff_report = {}
        for fname in set(list(a_files.keys()) + list(b_files.keys())):
            a_data = a_files.get(fname, {}).get("data", "")
            b_data = b_files.get(fname, {}).get("data", "")
            if a_data != b_data:
                diff_report[fname] = {
                    "changed": True,
                    "size_before": len(str(a_data)),
                    "size_after":  len(str(b_data)),
                }
        return {"changed_files": diff_report, "total_changes": len(diff_report)}

    # ──────────────────────────────────────────────────────────────────
    # BRANCH
    # ──────────────────────────────────────────────────────────────────

    def create_branch(self, name: str) -> str:
        """Create an experimental branch by snapshotting current state."""
        snap_id = self.take_snapshot(note=f"branch:{name}", branch=name)
        return f"Branch '{name}' created from snapshot {snap_id}"

    def checkout_branch(self, name: str) -> str:
        self._current_branch = name
        return f"Switched to branch '{name}'"

    # ──────────────────────────────────────────────────────────────────
    # MANIFEST
    # ──────────────────────────────────────────────────────────────────

    def _trim_snapshots(self, branch: str):
        branch_snaps = sorted(
            [s for s in self._manifest.values() if s.branch == branch],
            key=lambda s: s.version,
        )
        while len(branch_snaps) > self.MAX_SNAPSHOTS:
            oldest = branch_snaps.pop(0)
            del self._manifest[oldest.snapshot_id]
            snap_path = os.path.join(self._root, f"{oldest.snapshot_id}.gz")
            if os.path.exists(snap_path):
                os.remove(snap_path)

    def _save_manifest(self):
        mf = os.path.join(self._root, self.MANIFEST_FILE)
        try:
            with open(mf, "w") as f:
                json.dump({sid: s.to_dict() for sid, s in self._manifest.items()}, f, indent=2)
        except Exception as e:
            logger.debug("[CONSCIOUSNESS GIT] Manifest save error: %s", e)

    def _load_manifest(self):
        mf = os.path.join(self._root, self.MANIFEST_FILE)
        if not os.path.exists(mf):
            return
        try:
            with open(mf) as f:
                raw = json.load(f)
            for sid, sdata in raw.items():
                self._manifest[sid] = MindSnapshot(**sdata)
            if self._manifest:
                self._version = max(s.version for s in self._manifest.values()) + 1
        except Exception as e:
            logger.debug("[CONSCIOUSNESS GIT] Manifest load error: %s", e)

    # ──────────────────────────────────────────────────────────────────
    # AUTO SNAPSHOT
    # ──────────────────────────────────────────────────────────────────

    def _auto_snapshot_loop(self):
        while True:
            time.sleep(self.AUTO_INTERVAL)
            self.take_snapshot(note="auto_daily")

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    def list_snapshots(self, branch: Optional[str] = None) -> List[dict]:
        with self._lock:
            snaps = list(self._manifest.values())
        if branch:
            snaps = [s for s in snaps if s.branch == branch]
        snaps.sort(key=lambda s: s.version, reverse=True)
        return [s.to_dict() for s in snaps]

    def get_stats(self) -> dict:
        total_size = sum(s.size_bytes for s in self._manifest.values())
        return {
            "total_snapshots":  len(self._manifest),
            "total_size_mb":    round(total_size / 1024 / 1024, 2),
            "current_version":  self._version,
            "current_branch":   self._current_branch,
            "snapshot_dir":     self._root,
            "latest_snapshots": self.list_snapshots()[:5],
        }


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[ConsciousnessPersistence] = None
_lock = threading.Lock()

def get_consciousness_git() -> ConsciousnessPersistence:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ConsciousnessPersistence()
    return _instance
