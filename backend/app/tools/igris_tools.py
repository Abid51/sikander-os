"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS TOOLS — Web Search, Calculator, Code Runner, File Manager
  God-tier utility belt for the Igris AI assistant
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


# ─────────────────────────────────────────────────────────────────────────────
#  1. WEB SEARCH  — DuckDuckGo HTML scrape (no API key needed)
# ─────────────────────────────────────────────────────────────────────────────

class WebSearchTool:
    """Scrape DuckDuckGo for real-time web results."""

    _BASE = "https://html.duckduckgo.com/html/?q="
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }
    _cache: Dict[str, Tuple[List[dict], float]] = {}
    _TTL = 300  # seconds

    def search(self, query: str, max_results: int = 5) -> List[dict]:
        """Return [{title, url, snippet}] for query."""
        key = hashlib.md5(query.encode()).hexdigest()
        if key in self._cache:
            cached, ts = self._cache[key]
            if time.time() - ts < self._TTL:
                return cached

        url = self._BASE + quote_plus(query)
        try:
            resp = requests.get(url, headers=self._HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            results: List[dict] = []
            for result in soup.select(".result"):
                title_el  = result.select_one(".result__title")
                url_el    = result.select_one(".result__url")
                snip_el   = result.select_one(".result__snippet")
                if not title_el:
                    continue
                results.append({
                    "title":   title_el.get_text(strip=True),
                    "url":     url_el.get_text(strip=True) if url_el else "",
                    "snippet": snip_el.get_text(strip=True) if snip_el else "",
                })
                if len(results) >= max_results:
                    break
            self._cache[key] = (results, time.time())
            return results
        except Exception as exc:
            return [{"error": str(exc), "title": "", "url": "", "snippet": ""}]

    def fetch_page(self, url: str, max_chars: int = 3000) -> str:
        """Fetch and return the plain text of a web page."""
        try:
            resp = requests.get(url, headers=self._HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)[:max_chars]
        except Exception as exc:
            return f"[fetch error: {exc}]"


# ─────────────────────────────────────────────────────────────────────────────
#  2. CALCULATOR — safe expression evaluator
# ─────────────────────────────────────────────────────────────────────────────

class CalculatorTool:
    """Safe arithmetic + math expression evaluator."""

    _ALLOWED_NAMES = {
        k: v for k, v in math.__dict__.items() if not k.startswith("_")
    }
    _ALLOWED_NAMES.update({"abs": abs, "round": round, "int": int, "float": float})

    def evaluate(self, expression: str) -> dict:
        """Evaluate a math expression safely. Returns {result, expression, error}."""
        try:
            # Sanitise: only allow safe characters
            cleaned = re.sub(r"[^0-9+\-*/().,%^ a-zA-Z_]", "", expression)
            # Replace ^ with ** for power
            cleaned = cleaned.replace("^", "**")

            tree = ast.parse(cleaned, mode="eval")
            # Walk AST and reject any unsafe nodes
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id not in self._ALLOWED_NAMES:
                            raise ValueError(f"Function '{node.func.id}' not allowed")
                    else:
                        raise ValueError("Method calls not allowed")

            result = eval(  # nosec  (AST-validated)
                compile(tree, "<calc>", "eval"),
                {"__builtins__": {}},
                self._ALLOWED_NAMES,
            )
            return {"expression": expression, "result": result, "error": None}
        except Exception as exc:
            return {"expression": expression, "result": None, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
#  3. PYTHON SANDBOX — execute untrusted snippets in isolation
# ─────────────────────────────────────────────────────────────────────────────

class PythonSandboxTool:
    """Execute Python code in a temporary subprocess (isolated)."""

    _TIMEOUT = 10  # seconds

    def run(self, code: str) -> dict:
        """
        Run *code* in a completely separate Python process.
        Returns {stdout, stderr, exit_code, timed_out}.
        """
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self._TIMEOUT,
            )
            return {
                "stdout":    proc.stdout[:4000],
                "stderr":    proc.stderr[:2000],
                "exit_code": proc.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Execution timed out", "exit_code": -1, "timed_out": True}
        except Exception as exc:
            return {"stdout": "", "stderr": str(exc), "exit_code": -1, "timed_out": False}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  4. FILE MANAGER — read / write / list / search inside workspace
# ─────────────────────────────────────────────────────────────────────────────

def _path_under_root(root: str, candidate: str) -> bool:
    try:
        return os.path.commonpath([root, candidate]) == os.path.abspath(root)
    except ValueError:
        return False


class FileManagerTool:
    """Safe file operations within allowed root directory(ies).

    Set IGRIS_ALLOWED_FILE_ROOTS to a comma-separated list for multiple sandboxes
    (otherwise *root* or cwd is used).
    """

    def __init__(self, root: Optional[str] = None) -> None:
        env_roots = os.getenv("IGRIS_ALLOWED_FILE_ROOTS", "").strip()
        if env_roots:
            self.roots = [os.path.abspath(p.strip()) for p in env_roots.split(",") if p.strip()]
        else:
            self.roots = [os.path.abspath(root or os.getcwd())]
        self.root = self.roots[0]

    def _safe(self, path: str) -> str:
        norm = path.replace("\\", "/").lstrip("/")
        for r in self.roots:
            full = os.path.normpath(os.path.join(r, norm))
            if _path_under_root(r, full):
                return full
        raise PermissionError(f"Access outside allowed workspace(s) denied: {path}")

    def list_dir(self, path: str = "") -> dict:
        full = self._safe(path)
        if not os.path.isdir(full):
            return {"error": f"{path} is not a directory"}
        entries = []
        for name in sorted(os.listdir(full)):
            fp = os.path.join(full, name)
            entries.append({
                "name": name,
                "is_dir": os.path.isdir(fp),
                "size": os.path.getsize(fp) if os.path.isfile(fp) else None,
            })
        return {"path": path, "entries": entries, "count": len(entries)}

    def read_file(self, path: str, max_chars: int = 8000) -> dict:
        full = self._safe(path)
        if not os.path.isfile(full):
            return {"error": f"{path} not found"}
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            return {"path": path, "content": content, "truncated": os.path.getsize(full) > max_chars}
        except Exception as exc:
            return {"error": str(exc)}

    def write_file(self, path: str, content: str, append: bool = False) -> dict:
        full = self._safe(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        mode = "a" if append else "w"
        try:
            with open(full, mode, encoding="utf-8") as f:
                f.write(content)
            return {"status": "ok", "path": path, "bytes_written": len(content.encode())}
        except Exception as exc:
            return {"error": str(exc)}

    def search_files(self, query: str, path: str = "", ext_filter: str = "") -> dict:
        """Recursively search file contents for query string."""
        full = self._safe(path)
        matches: List[dict] = []
        query_lower = query.lower()

        for dirpath, _, files in os.walk(full):
            for fname in files:
                if ext_filter and not fname.endswith(ext_filter):
                    continue
                fpath = os.path.join(dirpath, fname)
                rel   = os.path.relpath(fpath, self.roots[0])
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, 1):
                            if query_lower in line.lower():
                                matches.append({
                                    "file": rel,
                                    "line": lineno,
                                    "content": line.rstrip()[:200],
                                })
                                if len(matches) >= 100:
                                    return {"query": query, "matches": matches, "truncated": True}
                except Exception:
                    pass

        return {"query": query, "matches": matches, "truncated": False}


# ─────────────────────────────────────────────────────────────────────────────
#  5. SYSTEM INFO TOOL
# ─────────────────────────────────────────────────────────────────────────────

class SystemInfoTool:
    """Live system telemetry snapshot."""

    def snapshot(self) -> dict:
        try:
            import psutil
            cpu   = psutil.cpu_percent(interval=0.3)
            mem   = psutil.virtual_memory()
            disk_root = os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
            disk  = psutil.disk_usage(disk_root)
            procs = [
                {"pid": p.pid, "name": p.info["name"], "cpu": p.info["cpu_percent"]}
                for p in sorted(
                    psutil.process_iter(["name", "cpu_percent"]),
                    key=lambda p: p.info.get("cpu_percent") or 0,
                    reverse=True,
                )[:10]
            ]
            return {
                "cpu_percent":    cpu,
                "memory_total_gb": round(mem.total / 1e9, 2),
                "memory_used_gb":  round(mem.used  / 1e9, 2),
                "memory_percent":  mem.percent,
                "disk_total_gb":   round(disk.total / 1e9, 2),
                "disk_used_gb":    round(disk.used  / 1e9, 2),
                "disk_percent":    disk.percent,
                "top_processes":   procs,
                "timestamp":       time.time(),
            }
        except ImportError:
            return {"error": "psutil not available"}


# ─────────────────────────────────────────────────────────────────────────────
#  6. JSON / DATA TRANSFORMER
# ─────────────────────────────────────────────────────────────────────────────

class DataTransformerTool:
    """Parse, transform, and query JSON/CSV data."""

    def parse_json(self, raw: str) -> dict:
        try:
            return {"data": json.loads(raw), "error": None}
        except Exception as exc:
            return {"data": None, "error": str(exc)}

    def flatten(self, obj: Any, prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dict to dot-notation keys."""
        flat: Dict[str, Any] = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                flat.update(self.flatten(v, f"{prefix}.{k}" if prefix else k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                flat.update(self.flatten(v, f"{prefix}[{i}]"))
        else:
            flat[prefix] = obj
        return flat

    def summarise(self, data: List[dict]) -> dict:
        """Basic stats summary for a list of dicts."""
        if not data:
            return {"error": "empty dataset"}
        keys = list(data[0].keys())
        stats = {"count": len(data), "keys": keys, "fields": {}}
        for k in keys:
            vals = [row[k] for row in data if k in row]
            nums = []
            for v in vals:
                try:
                    nums.append(float(v))
                except (TypeError, ValueError):
                    pass
            if nums:
                stats["fields"][k] = {
                    "type":   "numeric",
                    "min":    min(nums),
                    "max":    max(nums),
                    "mean":   round(sum(nums) / len(nums), 4),
                    "count":  len(nums),
                }
            else:
                unique = list(set(str(v) for v in vals))
                stats["fields"][k] = {
                    "type":    "categorical",
                    "unique":  len(unique),
                    "samples": unique[:5],
                }
        return stats


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRY — single entry point for ai_core.execute_tool()
# ─────────────────────────────────────────────────────────────────────────────

class IgrisToolRegistry:
    """Central registry: brain calls run(tool_name, **kwargs)."""

    def __init__(self) -> None:
        self.web       = WebSearchTool()
        self.calc      = CalculatorTool()
        self.sandbox   = PythonSandboxTool()
        self.files     = FileManagerTool()
        self.sysinfo   = SystemInfoTool()
        self.data      = DataTransformerTool()
        # 7 categories x 300 = 2100 virtual tools
        self._virtual_count_per_family = 300
        self._virtual_families = {
            "web_tool_": "web_search",
            "calc_tool_": "calculate",
            "python_tool_": "run_python",
            "file_tool_": "read_file",
            "write_tool_": "write_file",
            "search_tool_": "search_files",
            "system_tool_": "system_info",
        }

    def _resolve_virtual_tool(self, name: str) -> str:
        for prefix, target in self._virtual_families.items():
            if name.startswith(prefix):
                suffix = name[len(prefix):]
                if suffix.isdigit():
                    idx = int(suffix)
                    if idx >= 1:
                        return target
        return name

    def run(self, tool_name: str, **kwargs: Any) -> Any:
        canonical = str(tool_name or "").strip().lower().replace(" ", "_")
        alias_map = {
            "web": "web_search",
            "browser": "web_search",
            "web_browser": "web_search",
            "internet_search": "web_search",
            "ui_designer_tool": "web_search",
        }
        tool_name = alias_map.get(canonical, canonical)
        tool_name = self._resolve_virtual_tool(tool_name)
        dispatch = {
            # Web
            "web_search":  lambda: self.web.search(kwargs.get("query", ""), kwargs.get("max_results", 5)),
            "fetch_page":  lambda: self.web.fetch_page(kwargs.get("url", "")),
            # Math
            "calculate":   lambda: self.calc.evaluate(kwargs.get("expression", "")),
            # Code
            "run_python":  lambda: self.sandbox.run(kwargs.get("code", "")),
            # Files
            "list_dir":    lambda: self.files.list_dir(kwargs.get("path", "")),
            "read_file":   lambda: self.files.read_file(kwargs.get("path", ""), kwargs.get("max_chars", 8000)),
            "write_file":  lambda: self.files.write_file(kwargs.get("path", ""), kwargs.get("content", ""), kwargs.get("append", False)),
            "search_files":lambda: self.files.search_files(kwargs.get("query", ""), kwargs.get("path", ""), kwargs.get("ext_filter", "")),
            # System
            "system_info": lambda: self.sysinfo.snapshot(),
            # Data
            "parse_json":  lambda: self.data.parse_json(kwargs.get("raw", "")),
            "summarise":   lambda: self.data.summarise(kwargs.get("data", [])),
        }
        fn = dispatch.get(tool_name)
        if fn is None:
            return {"error": f"Tool '{tool_name}' not found in registry"}
        return fn()

    def available_tools(self) -> List[dict]:
        base_tools = [
            {"name": "web_search",   "args": ["query", "max_results"], "desc": "Search the web via DuckDuckGo"},
            {"name": "fetch_page",   "args": ["url"],                  "desc": "Fetch plain text of a web page"},
            {"name": "calculate",    "args": ["expression"],           "desc": "Evaluate a math expression"},
            {"name": "run_python",   "args": ["code"],                 "desc": "Execute Python code in sandbox"},
            {"name": "list_dir",     "args": ["path"],                 "desc": "List files in a directory"},
            {"name": "read_file",    "args": ["path", "max_chars"],    "desc": "Read file contents"},
            {"name": "write_file",   "args": ["path", "content"],      "desc": "Write to a file"},
            {"name": "search_files", "args": ["query", "path"],        "desc": "Search file contents for a string"},
            {"name": "system_info",  "args": [],                       "desc": "Get live system telemetry"},
            {"name": "parse_json",   "args": ["raw"],                  "desc": "Parse raw JSON string"},
            {"name": "summarise",    "args": ["data"],                 "desc": "Statistical summary of a list of dicts"},
        ]
        virtual_tools: List[dict] = []
        for prefix, target in self._virtual_families.items():
            for i in range(1, self._virtual_count_per_family + 1):
                virtual_tools.append({
                    "name": f"{prefix}{i}",
                    "args": ["query", "path", "content", "expression", "code"],
                    "desc": f"Virtual alias mapped to `{target}`",
                })
        return base_tools + virtual_tools


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_registry: Optional[IgrisToolRegistry] = None


def get_tool_registry() -> IgrisToolRegistry:
    global _registry
    if _registry is None:
        _registry = IgrisToolRegistry()
    return _registry
