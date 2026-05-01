"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS PLUGIN LOADER — Dynamic Plugin System
  Load Python plugins from the plugins/ directory at runtime.

  Features
  ────────
  • Auto-discovery — scans plugins/ on load_all()
  • Hot-reload     — reload a single plugin without restart
  • Marketplace    — search, validate, sandbox-import from URL/local path
  • Hook dispatch  — on_command, on_message, on_startup, on_shutdown
  • Dependency check — warn if plugin's REQUIRES list is missing
  • File-watcher   — background thread re-loads changed plugins
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

PLUGINS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "plugins")
)
MARKETPLACE_CACHE_FILE = os.path.join(PLUGINS_DIR, ".marketplace_cache.json")


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PluginInfo:
    name:        str
    version:     str
    description: str
    author:      str
    file_path:   str
    enabled:     bool       = True
    loaded_at:   float      = field(default_factory=time.time)
    error:       str        = ""
    commands:    List[str]  = field(default_factory=list)
    hooks:       List[str]  = field(default_factory=list)
    requires:    List[str]  = field(default_factory=list)
    tags:        List[str]  = field(default_factory=list)
    last_modified: float    = 0.0


@dataclass
class MarketplaceEntry:
    name:        str
    version:     str
    description: str
    author:      str
    tags:        List[str]
    download_url: str = ""
    rating:      float = 0.0
    installs:    int   = 0


# ══════════════════════════════════════════════════════════════════════════════
# BASE PLUGIN CLASS
# ══════════════════════════════════════════════════════════════════════════════

class IgrisPlugin:
    """
    Base class for all Igris plugins.

    All lifecycle methods are intentionally empty — plugins override only
    what they need.  This is the correct design for a base/mixin class.
    """

    NAME        = "unnamed_plugin"
    VERSION     = "1.0.0"
    DESCRIPTION = "An Igris plugin"
    AUTHOR      = "unknown"
    REQUIRES: List[str] = []   # pip package names
    TAGS:     List[str] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_load(self) -> None:
        """Called immediately after the plugin module is imported and instantiated."""

    def on_unload(self) -> None:
        """Called before the plugin is removed from the loader."""

    def on_startup(self) -> None:
        """Called once when the Igris system finishes booting."""

    def on_shutdown(self) -> None:
        """Called when the Igris system is shutting down gracefully."""

    # ── Hooks ────────────────────────────────────────────────────────────────

    def on_command(self, command: str, args: dict) -> Optional[Any]:
        """
        Handle a named command.
        Return a result to stop propagation, or None to pass to the next plugin.
        """
        return None

    def on_message(self, user_msg: str, ai_response: str) -> Optional[str]:
        """
        Intercept every chat turn.
        Return a modified response string, or None to leave it unchanged.
        """
        return None

    # ── Info ─────────────────────────────────────────────────────────────────

    def get_commands(self) -> List[dict]:
        """
        Return a list of command descriptors this plugin provides.
        Example: [{"name": "hello", "description": "Say hello"}]
        """
        return []

    def get_status(self) -> dict:
        """Return plugin health/status info displayed in the admin dashboard."""
        return {"status": "ok", "name": self.NAME, "version": self.VERSION}


# ══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def _check_requires(requires: List[str]) -> List[str]:
    """Return a list of missing pip packages from the REQUIRES list."""
    missing = []
    for pkg in requires:
        pkg_import = pkg.replace("-", "_").split(">=")[0].split("==")[0].strip()
        try:
            importlib.import_module(pkg_import)
        except ImportError:
            missing.append(pkg)
    return missing


# ══════════════════════════════════════════════════════════════════════════════
# PLUGIN LOADER
# ══════════════════════════════════════════════════════════════════════════════

class PluginLoader:
    """
    Dynamic plugin loader for Igris OS.

    Plugins are Python files in the plugins/ directory.
    Each must define exactly one class that inherits from IgrisPlugin.

    Usage
    ─────
        loader = get_plugin_loader()
        loader.load_all()
        loader.fire_startup()
        result = loader.dispatch_command("my_command", {"arg": "val"})
        loader.start_file_watcher()   # optional hot-reload
    """

    def __init__(self, plugins_dir: str = PLUGINS_DIR) -> None:
        self.plugins_dir = plugins_dir
        self._plugins: Dict[str, IgrisPlugin]  = {}
        self._info:    Dict[str, PluginInfo]   = {}
        self._hooks: Dict[str, List[Callable]] = {
            "on_command":  [],
            "on_message":  [],
            "on_startup":  [],
            "on_shutdown": [],
        }
        self._lock     = threading.RLock()
        self._watcher: Optional[threading.Thread] = None
        self._watching = False
        self._marketplace_cache: List[dict] = []
        os.makedirs(self.plugins_dir, exist_ok=True)

    # ── Load / Unload ─────────────────────────────────────────────────────────

    def load_all(self) -> Dict[str, str]:
        """Scan and load all plugins from plugins_dir. Returns {name: status}."""
        results: Dict[str, str] = {}
        if not os.path.isdir(self.plugins_dir):
            return results

        for fname in sorted(os.listdir(self.plugins_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            fpath = os.path.join(self.plugins_dir, fname)
            name  = fname[:-3]
            try:
                status = self._load_plugin(name, fpath)
                results[name] = status
            except Exception as e:
                results[name] = f"error: {e}"
                logger.error("[PLUGIN] Failed to load %s: %s", name, e)

        logger.info("[PLUGIN] Loaded %d plugins from %s", len(self._plugins), self.plugins_dir)
        return results

    def _load_plugin(self, name: str, fpath: str) -> str:
        """Internal: import a plugin file and register it."""
        spec = importlib.util.spec_from_file_location(f"igris_plugin_{name}", fpath)
        if not spec or not spec.loader:
            return "invalid module"

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the IgrisPlugin subclass
        plugin_cls = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, IgrisPlugin)
                and attr is not IgrisPlugin
            ):
                plugin_cls = attr
                break

        if not plugin_cls:
            return "no IgrisPlugin subclass found"

        # Check dependencies
        requires = getattr(plugin_cls, "REQUIRES", [])
        missing  = _check_requires(requires)
        if missing:
            logger.warning("[PLUGIN] %s: missing packages %s", name, missing)

        instance = plugin_cls()
        instance.on_load()

        mtime = os.path.getmtime(fpath)
        with self._lock:
            self._plugins[name] = instance
            self._info[name]    = PluginInfo(
                name=getattr(instance, "NAME", name),
                version=getattr(instance, "VERSION", "1.0.0"),
                description=getattr(instance, "DESCRIPTION", ""),
                author=getattr(instance, "AUTHOR", "unknown"),
                file_path=fpath,
                commands=[c.get("name", "") for c in instance.get_commands()],
                requires=requires,
                tags=getattr(instance, "TAGS", []),
                last_modified=mtime,
            )
            self._hooks["on_command"].append(instance.on_command)
            self._hooks["on_message"].append(instance.on_message)
            self._hooks["on_startup"].append(instance.on_startup)
            self._hooks["on_shutdown"].append(instance.on_shutdown)

        return "loaded"

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin and remove its hooks."""
        with self._lock:
            plugin = self._plugins.pop(name, None)
            if plugin:
                try:
                    plugin.on_unload()
                except Exception:
                    pass
                # Remove this plugin's methods from all hook lists
                for hook_list in self._hooks.values():
                    hook_list[:] = [
                        h for h in hook_list
                        if not (hasattr(h, "__self__") and h.__self__ is plugin)
                    ]
                self._info.pop(name, None)
                logger.info("[PLUGIN] Unloaded: %s", name)
                return True
        return False

    def reload_plugin(self, name: str) -> str:
        """Hot-reload a single plugin without restarting the system."""
        with self._lock:
            info = self._info.get(name)
        if not info:
            # Try to find by scanning directory
            fpath = os.path.join(self.plugins_dir, f"{name}.py")
            if not os.path.exists(fpath):
                return "plugin not found"
            return self._load_plugin(name, fpath)

        self.unload_plugin(name)
        result = self._load_plugin(name, info.file_path)
        logger.info("[PLUGIN] Reloaded %s: %s", name, result)
        return result

    def reload_all(self) -> Dict[str, str]:
        """Hot-reload all currently loaded plugins."""
        names = list(self._plugins.keys())
        results = {}
        for name in names:
            results[name] = self.reload_plugin(name)
        return results

    # ── File Watcher (hot-reload on file change) ──────────────────────────────

    def start_file_watcher(self, interval: float = 5.0) -> None:
        """
        Start a background thread that auto-reloads plugins when their
        source file changes (mtime differs).
        """
        if self._watching:
            return
        self._watching = True
        self._watcher  = threading.Thread(
            target=self._watch_loop, args=(interval,), daemon=True
        )
        self._watcher.start()
        logger.info("[PLUGIN] File watcher started (interval=%.1fs)", interval)

    def stop_file_watcher(self) -> None:
        """Stop the background file watcher."""
        self._watching = False
        logger.info("[PLUGIN] File watcher stopped.")

    def _watch_loop(self, interval: float) -> None:
        while self._watching:
            try:
                self._check_for_changes()
                self._check_for_new_plugins()
            except Exception as e:
                logger.debug("[PLUGIN] Watcher error: %s", e)
            time.sleep(interval)

    def _check_for_changes(self) -> None:
        """Reload plugins whose source file has been modified."""
        with self._lock:
            snapshot = {n: i.file_path for n, i in self._info.items()}
        for name, fpath in snapshot.items():
            try:
                mtime = os.path.getmtime(fpath)
                with self._lock:
                    info = self._info.get(name)
                if info and mtime != info.last_modified:
                    logger.info("[PLUGIN] Change detected: %s — reloading.", name)
                    self.reload_plugin(name)
                    with self._lock:
                        if name in self._info:
                            self._info[name].last_modified = mtime
            except FileNotFoundError:
                logger.warning("[PLUGIN] %s removed — unloading.", name)
                self.unload_plugin(name)

    def _check_for_new_plugins(self) -> None:
        """Load any new .py files that appeared in the plugins directory."""
        with self._lock:
            known = set(self._info.keys())
        for fname in os.listdir(self.plugins_dir):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            name = fname[:-3]
            if name not in known:
                logger.info("[PLUGIN] New plugin discovered: %s", name)
                fpath = os.path.join(self.plugins_dir, fname)
                self._load_plugin(name, fpath)

    # ── Hook Dispatch ─────────────────────────────────────────────────────────

    def dispatch_command(self, command: str, args: dict = None) -> Optional[Any]:
        """Send command to all plugins. First non-None response wins."""
        with self._lock:
            handlers = list(self._hooks["on_command"])
        for handler in handlers:
            try:
                result = handler(command, args or {})
                if result is not None:
                    return result
            except Exception as e:
                logger.error("[PLUGIN] Command handler error: %s", e)
        return None

    def dispatch_message(self, user_msg: str, ai_response: str) -> str:
        """Let plugins modify the AI response. Last modifier wins."""
        modified = ai_response
        with self._lock:
            handlers = list(self._hooks["on_message"])
        for handler in handlers:
            try:
                result = handler(user_msg, modified)
                if result is not None:
                    modified = result
            except Exception:
                pass
        return modified

    def fire_startup(self) -> None:
        """Call on_startup() on all loaded plugins."""
        with self._lock:
            handlers = list(self._hooks["on_startup"])
        for handler in handlers:
            try:
                handler()
            except Exception as e:
                logger.error("[PLUGIN] Startup hook error: %s", e)

    def fire_shutdown(self) -> None:
        """Call on_shutdown() on all loaded plugins then unload all."""
        with self._lock:
            handlers = list(self._hooks["on_shutdown"])
        for handler in handlers:
            try:
                handler()
            except Exception as e:
                logger.error("[PLUGIN] Shutdown hook error: %s", e)
        # Clean unload
        for name in list(self._plugins.keys()):
            self.unload_plugin(name)

    # ── Plugin Enable / Disable ───────────────────────────────────────────────

    def enable_plugin(self, name: str) -> bool:
        """Enable a previously disabled plugin (re-loads it)."""
        with self._lock:
            info = self._info.get(name)
        if info and not info.enabled:
            result = self._load_plugin(name, info.file_path)
            if result == "loaded":
                with self._lock:
                    self._info[name].enabled = True
                return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin (unloads it but keeps metadata)."""
        with self._lock:
            info = self._info.get(name)
        if info and info.enabled:
            self.unload_plugin(name)
            # Restore metadata stub so it shows up in list
            with self._lock:
                self._info[name] = PluginInfo(
                    **{**asdict(info), "enabled": False, "error": "disabled"}
                )
            return True
        return False

    # ── Marketplace ──────────────────────────────────────────────────────────

    def marketplace_search(self, query: str = "") -> List[dict]:
        """
        Search the local marketplace cache.
        The cache is populated by marketplace_refresh() or by placing a
        marketplace.json file in the plugins directory.
        """
        cache = self._load_marketplace_cache()
        query_lower = query.lower()
        if not query_lower:
            return cache
        return [
            entry for entry in cache
            if query_lower in entry.get("name", "").lower()
            or query_lower in entry.get("description", "").lower()
            or any(query_lower in t for t in entry.get("tags", []))
        ]

    def marketplace_refresh(self) -> Dict[str, Any]:
        """
        Refresh the marketplace cache from a remote index or local json.
        Falls back to scanning installed plugins as the catalogue.
        """
        # Try remote fetch
        try:
            import urllib.request, json as _json
            index_url = os.getenv("IGRIS_PLUGIN_INDEX_URL", "")
            if index_url:
                with urllib.request.urlopen(index_url, timeout=5) as resp:
                    data = _json.loads(resp.read())
                    self._marketplace_cache = data.get("plugins", [])
                    self._save_marketplace_cache()
                    return {"status": "refreshed", "count": len(self._marketplace_cache), "source": "remote"}
        except Exception as e:
            logger.debug("[PLUGIN] Remote marketplace refresh failed: %s", e)

        # Local fallback: treat installed plugins as the catalogue
        installed = self.list_plugins()
        self._marketplace_cache = installed
        self._save_marketplace_cache()
        return {"status": "refreshed", "count": len(installed), "source": "local"}

    def marketplace_install(self, plugin_name: str, source_path: str) -> Dict[str, str]:
        """
        Install a plugin from a local file path or URL into plugins_dir.
        Validates that the file contains an IgrisPlugin subclass before copying.
        """
        import shutil

        # Handle URL download
        if source_path.startswith("http://") or source_path.startswith("https://"):
            try:
                import urllib.request
                fname    = plugin_name.replace(" ", "_").lower() + ".py"
                dest     = os.path.join(self.plugins_dir, fname)
                urllib.request.urlretrieve(source_path, dest)
                source_path = dest
            except Exception as e:
                return {"status": "error", "reason": f"Download failed: {e}"}

        if not os.path.exists(source_path):
            return {"status": "error", "reason": "Source file not found"}

        # Validate before installing
        valid, reason = self._validate_plugin_file(source_path)
        if not valid:
            return {"status": "error", "reason": reason}

        fname = os.path.basename(source_path)
        dest  = os.path.join(self.plugins_dir, fname)
        src_abs = os.path.abspath(source_path)
        dst_abs = os.path.abspath(dest)
        if src_abs != dst_abs:
            shutil.copy2(source_path, dest)
        else:
            dest = source_path

        name   = fname[:-3]
        result = self._load_plugin(name, dest)
        logger.info("[PLUGIN] Marketplace install %s: %s", name, result)
        return {"status": result, "plugin": name, "path": dest}

    def marketplace_uninstall(self, name: str) -> Dict[str, str]:
        """Unload and delete a plugin from disk."""
        with self._lock:
            info = self._info.get(name)
        if not info:
            return {"status": "error", "reason": "Plugin not found"}
        self.unload_plugin(name)
        try:
            os.remove(info.file_path)
            logger.info("[PLUGIN] Uninstalled and deleted: %s", name)
            return {"status": "uninstalled", "plugin": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def _validate_plugin_file(self, fpath: str) -> tuple[bool, str]:
        """Return (True, '') if file contains a valid IgrisPlugin subclass."""
        try:
            import ast
            src  = open(fpath, encoding="utf-8").read()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_name = getattr(base, "id", "") or getattr(base, "attr", "")
                        if base_name == "IgrisPlugin":
                            return True, ""
            return False, "No IgrisPlugin subclass found in file"
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, str(e)

    def _load_marketplace_cache(self) -> List[dict]:
        if self._marketplace_cache:
            return self._marketplace_cache
        try:
            if os.path.exists(MARKETPLACE_CACHE_FILE):
                with open(MARKETPLACE_CACHE_FILE, encoding="utf-8") as f:
                    self._marketplace_cache = json.load(f)
        except Exception:
            pass
        return self._marketplace_cache

    def _save_marketplace_cache(self) -> None:
        try:
            with open(MARKETPLACE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._marketplace_cache, f, indent=2)
        except Exception:
            pass

    # ── Info & Stats ──────────────────────────────────────────────────────────

    def list_plugins(self) -> List[dict]:
        """List all loaded plugins as dicts."""
        with self._lock:
            return [asdict(info) for info in self._info.values()]

    def get_plugin_status(self, name: str) -> Optional[dict]:
        """Get detailed status of a single plugin."""
        with self._lock:
            plugin = self._plugins.get(name)
            info   = self._info.get(name)
        if plugin and info:
            return {
                "info":     asdict(info),
                "status":   plugin.get_status(),
                "commands": plugin.get_commands(),
                "missing_deps": _check_requires(info.requires),
            }
        return None

    def get_stats(self) -> dict:
        """Return loader-level statistics."""
        with self._lock:
            return {
                "plugins_loaded":   len(self._plugins),
                "plugins_dir":      self.plugins_dir,
                "total_commands":   sum(len(i.commands) for i in self._info.values()),
                "file_watcher":     "active" if self._watching else "inactive",
                "marketplace_entries": len(self._marketplace_cache),
                "plugins": [
                    {
                        "name":    i.name,
                        "version": i.version,
                        "enabled": i.enabled,
                        "tags":    i.tags,
                        "error":   i.error,
                    }
                    for i in self._info.values()
                ],
            }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_instance: Optional[PluginLoader] = None
_create_lock = threading.Lock()


def get_plugin_loader() -> PluginLoader:
    global _instance
    if _instance is None:
        with _create_lock:
            if _instance is None:
                _instance = PluginLoader()
    return _instance
