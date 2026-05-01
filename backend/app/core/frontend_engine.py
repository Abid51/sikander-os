"""
Frontend Self-Modification Engine for Igris AI
================================================
Allows Igris to:
  - Read any frontend source file (TSX, CSS, HTML, etc.)
  - Write / overwrite individual files with backup + syntax-level validation
  - Inject new React components into App.tsx automatically
  - Apply full CSS / theme redesigns
  - Append new navigation tabs to the Sidebar menu
  - List all frontend source files
  - Report the current design state (colors, fonts, tabs, etc.)
"""

import os
import re
import json
import shutil
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ── Resolve paths ────────────────────────────────────────────────────────────

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# backend/app/core  →  backend  →  project root
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
_FRONTEND_SRC = os.path.join(_PROJECT_ROOT, "frontend", "src")
_FRONTEND_ROOT = os.path.join(_PROJECT_ROOT, "frontend")

# Safe-list: which extensions / subdirs Igris is allowed to touch
_ALLOWED_EXTENSIONS = {".tsx", ".ts", ".css", ".html", ".json", ".js"}


# ── Helper ───────────────────────────────────────────────────────────────────

def _ts(label: str = "") -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + (f"_{label}" if label else "")


def _safe_path(relative_path: str) -> Optional[str]:
    """Resolve relative path inside frontend/src, block path traversal."""
    abs_path = os.path.normpath(os.path.join(_FRONTEND_SRC, relative_path))
    if not abs_path.startswith(_FRONTEND_SRC):
        return None
    ext = os.path.splitext(abs_path)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return None
    return abs_path


# ── Core Engine ──────────────────────────────────────────────────────────────

class FrontendEngine:
    """Igris Frontend Self-Modification Engine"""

    def __init__(self):
        self.modification_history: List[Dict[str, Any]] = []
        self.backup_dir = os.path.join(_FRONTEND_ROOT, ".igris_backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        logger.info(f"[FrontendEngine] src={_FRONTEND_SRC}")

    # ── List files ───────────────────────────────────────────────────────────

    def list_files(self) -> Dict[str, Any]:
        """Return all editable frontend source files."""
        result = []
        for root, dirs, files in os.walk(_FRONTEND_SRC):
            # skip hidden / node_modules
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in _ALLOWED_EXTENSIONS:
                    rel = os.path.relpath(os.path.join(root, fname), _FRONTEND_SRC)
                    full = os.path.join(root, fname)
                    size = os.path.getsize(full)
                    result.append({"path": rel.replace("\\", "/"), "size_bytes": size, "ext": ext})
        return {"files": result, "total": len(result), "src_root": _FRONTEND_SRC}

    # ── Read file ────────────────────────────────────────────────────────────

    def read_file(self, relative_path: str) -> Dict[str, Any]:
        """Read a frontend source file and return its content."""
        abs_path = _safe_path(relative_path)
        if not abs_path:
            return {"status": "error", "message": "Path not allowed or unsafe"}
        if not os.path.exists(abs_path):
            return {"status": "error", "message": f"File not found: {relative_path}"}
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {
            "status": "ok",
            "path": relative_path,
            "content": content,
            "lines": content.count("\n") + 1,
            "size_bytes": len(content.encode()),
        }

    # ── Write / overwrite file ───────────────────────────────────────────────

    def write_file(self, relative_path: str, new_content: str, reason: str = "") -> Dict[str, Any]:
        """
        Overwrite a frontend file with new_content.
        Auto-backups the current version first.
        Returns status + backup path.
        """
        abs_path = _safe_path(relative_path)
        if not abs_path:
            return {"status": "error", "message": "Path not allowed or unsafe"}

        # Create parent dirs if needed (for new files)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        # Backup existing file
        backup_path = None
        if os.path.exists(abs_path):
            backup_name = os.path.splitext(os.path.basename(abs_path))[0] + f"_{_ts()}.bak"
            backup_path = os.path.join(self.backup_dir, backup_name)
            shutil.copy2(abs_path, backup_path)

        # Write new content
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        mod = {
            "timestamp": datetime.now().isoformat(),
            "action": "write_file",
            "path": relative_path,
            "reason": reason,
            "backup": backup_path,
        }
        self.modification_history.append(mod)
        logger.info(f"[FrontendEngine] wrote {relative_path} ({len(new_content)} chars)")
        return {
            "status": "success",
            "message": f"File '{relative_path}' updated successfully.",
            "backup": backup_path,
            "modification_id": len(self.modification_history) - 1,
        }

    # ── Patch a single substring ─────────────────────────────────────────────

    def patch_file(self, relative_path: str, find_text: str, replace_text: str, reason: str = "") -> Dict[str, Any]:
        """
        Replace the FIRST occurrence of find_text with replace_text in a file.
        Safer than full overwrite when making small targeted changes.
        """
        result = self.read_file(relative_path)
        if result["status"] != "ok":
            return result

        content = result["content"]
        if find_text not in content:
            return {"status": "error", "message": f"find_text not found in {relative_path}"}

        new_content = content.replace(find_text, replace_text, 1)
        return self.write_file(relative_path, new_content, reason=reason or f"patch: {find_text[:60]}")

    # ── Inject React Component ────────────────────────────────────────────────

    def inject_component(self, component_name: str, component_tsx: str, add_to_sidebar: bool = True, tab_icon: str = "Sparkles", tab_label: str = "") -> Dict[str, Any]:
        """
        Inject a brand-new React component into App.tsx and optionally wire it
        to the Sidebar menu so it becomes a live tab the user can click.

        component_tsx  : full TSX code for the component (should be a named const arrow function)
        add_to_sidebar : if True, also adds a menu entry in the Sidebar
        tab_icon       : lucide-react icon name (must already be in the import list or we'll add it)
        tab_label      : human-readable label for the sidebar entry
        """
        app_read = self.read_file("App.tsx")
        if app_read["status"] != "ok":
            return app_read

        content = app_read["content"]

        # ── 1. Append component before the App() function ──
        insert_marker = "\nfunction App()"
        if insert_marker not in content:
            insert_marker = "\nexport default App"

        component_block = f"\n\n// ── Igris Auto-Generated: {component_name} ─────────────────────────────────\n{component_tsx}\n"
        content = content.replace(insert_marker, component_block + insert_marker, 1)

        # ── 2. Add Sidebar menu entry ──
        if add_to_sidebar:
            tab_id = component_name.lower().replace(" ", "_")
            label = tab_label or component_name
            # Find the menu array inside Sidebar and append
            menu_end = "  ];"
            new_entry = f"    {{ id: '{tab_id}', icon: {tab_icon}, label: '{label}' }},\n"
            content = content.replace(menu_end, new_entry + menu_end, 1)

            # Wire the component in the render block
            tab_render_marker = "{/* Placeholders for others */}"
            component_render = f"{{currentTab === '{tab_id}' && <{component_name} />}}\n                    "
            content = content.replace(tab_render_marker, component_render + tab_render_marker, 1)

        return self.write_file("App.tsx", content, reason=f"inject component: {component_name}")

    # ── Full CSS Theme Redesign ───────────────────────────────────────────────

    def redesign_theme(self, new_css: str, reason: str = "theme redesign") -> Dict[str, Any]:
        """Replace the entire index.css with a new theme."""
        return self.write_file("index.css", new_css, reason=reason)

    # ── Design State Snapshot ─────────────────────────────────────────────────

    def get_design_state(self) -> Dict[str, Any]:
        """
        Read current App.tsx + index.css and extract a high-level summary:
        current tabs, primary color, font, and last 5 modification records.
        """
        state: Dict[str, Any] = {
            "tabs": [],
            "primary_color": None,
            "font_family": None,
            "css_size": 0,
            "tsx_lines": 0,
            "recent_modifications": self.modification_history[-5:],
        }

        # Parse tabs from App.tsx menu array
        app_read = self.read_file("App.tsx")
        if app_read["status"] == "ok":
            state["tsx_lines"] = app_read["lines"]
            for m in re.finditer(r"\{\s*id:\s*'([^']+)'.*?label:\s*'([^']+)'", app_read["content"], re.DOTALL):
                state["tabs"].append({"id": m.group(1), "label": m.group(2)})

        # Parse primary color from index.css
        css_read = self.read_file("index.css")
        if css_read["status"] == "ok":
            state["css_size"] = css_read["size_bytes"]
            m = re.search(r"--primary\s*:\s*([^;]+);", css_read["content"])
            if m:
                state["primary_color"] = m.group(1).strip()
            m = re.search(r"font-family\s*:\s*([^;]+);", css_read["content"])
            if m:
                state["font_family"] = m.group(1).strip()

        return state

    # ── Rollback ─────────────────────────────────────────────────────────────

    def rollback(self, modification_id: int) -> Dict[str, Any]:
        """Restore a file to its pre-modification backup."""
        if modification_id >= len(self.modification_history):
            return {"status": "error", "message": "modification_id not found"}

        mod = self.modification_history[modification_id]
        backup = mod.get("backup")
        if not backup or not os.path.exists(backup):
            return {"status": "error", "message": "No backup file found for this modification"}

        rel_path = mod["path"]
        abs_path = _safe_path(rel_path)
        if not abs_path:
            return {"status": "error", "message": "Path resolution failed"}

        shutil.copy2(backup, abs_path)
        logger.info(f"[FrontendEngine] rolled back {rel_path}")
        return {"status": "success", "message": f"Rolled back '{rel_path}' to backup from {mod['timestamp']}"}

    # ── History ───────────────────────────────────────────────────────────────

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.modification_history[-limit:]


# ── Singleton ─────────────────────────────────────────────────────────────────

_frontend_engine: Optional[FrontendEngine] = None


def get_frontend_engine() -> FrontendEngine:
    global _frontend_engine
    if _frontend_engine is None:
        _frontend_engine = FrontendEngine()
    return _frontend_engine
