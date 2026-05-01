"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS SYSTEM DNA — Full Machine Identity & Clone Restore                  ║
║  "Your entire digital existence, compressed into one file."                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time, platform, subprocess, threading, logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import psutil as _psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False


@dataclass
class SystemDNASnapshot:
    dna_id: str
    created_at: str
    platform_info: dict = field(default_factory=dict)
    python_packages: List[str] = field(default_factory=list)
    environment_vars: dict = field(default_factory=dict)
    running_processes: List[str] = field(default_factory=list)
    disk_layout: List[dict] = field(default_factory=list)
    network_interfaces: List[dict] = field(default_factory=list)
    igris_config: dict = field(default_factory=dict)
    restore_script: str = ""

    def to_dict(self): return self.__dict__.copy()


class SystemDNA:
    """
    Creates a complete fingerprint of the user's system and Igris setup.

    DNA includes:
    ─────────────
    • OS, hardware, Python version
    • All pip packages + versions
    • Environment variables (filtered — no secrets)
    • Disk layout and usage
    • Network interfaces
    • Igris config files snapshot
    • Auto-generated PowerShell restore script
    """

    DNA_DIR  = "igris_dna"
    DNA_FILE = "system_dna.json"

    def __init__(self):
        base = os.path.dirname(os.path.abspath(__file__))
        self._base = os.path.normpath(os.path.join(base, "..", ".."))
        self._dna_dir = os.path.join(self._base, self.DNA_DIR)
        os.makedirs(self._dna_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._latest_dna: Optional[SystemDNASnapshot] = None
        self._load_latest()
        logger.info("[SYSTEM DNA] 🧬 System DNA engine ready.")

    # ─────────────────────────────────────────────────────────────────────
    # CAPTURE
    # ─────────────────────────────────────────────────────────────────────

    def capture(self) -> SystemDNASnapshot:
        """Capture a full system DNA snapshot."""
        logger.info("[SYSTEM DNA] 📸 Capturing system DNA...")
        dna_id = f"dna_{int(time.time())}"
        snap = SystemDNASnapshot(
            dna_id=dna_id,
            created_at=datetime.now().isoformat(),
        )

        # Platform
        snap.platform_info = self._capture_platform()

        # Python packages
        snap.python_packages = self._capture_packages()

        # Environment vars (filter sensitive)
        snap.environment_vars = self._capture_env()

        # Disk layout
        snap.disk_layout = self._capture_disk()

        # Network interfaces
        snap.network_interfaces = self._capture_network()

        # Running processes (top 20 by name)
        snap.running_processes = self._capture_procs()

        # Igris config snapshot
        snap.igris_config = self._capture_igris_config()

        # Generate restore script
        snap.restore_script = self._generate_restore_script(snap)

        # Save
        snap_path = os.path.join(self._dna_dir, f"{dna_id}.json")
        with open(snap_path, "w") as f:
            json.dump(snap.to_dict(), f, indent=2)

        # Update latest
        latest_path = os.path.join(self._dna_dir, self.DNA_FILE)
        with open(latest_path, "w") as f:
            json.dump(snap.to_dict(), f, indent=2)

        with self._lock:
            self._latest_dna = snap

        logger.info("[SYSTEM DNA] ✅ DNA captured: %s (%d packages)",
                    dna_id, len(snap.python_packages))
        return snap

    # ─────────────────────────────────────────────────────────────────────
    # CAPTURE HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _capture_platform(self) -> dict:
        info = {
            "os":          platform.system(),
            "os_version":  platform.version(),
            "release":     platform.release(),
            "machine":     platform.machine(),
            "processor":   platform.processor(),
            "python":      sys.version,
            "hostname":    platform.node(),
        }
        if PSUTIL_OK:
            try:
                cpu = _psutil.cpu_count()
                ram = _psutil.virtual_memory().total // 1024 // 1024
                info["cpu_cores"] = cpu
                info["ram_mb"]    = ram
            except Exception:
                pass
        return info

    def _capture_packages(self) -> List[str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip().splitlines()
        except Exception:
            return []

    def _capture_env(self) -> dict:
        SKIP = {"PATH", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES",
                "WINDIR", "SYSTEMROOT", "COMSPEC", "PASSWORD", "SECRET", "KEY",
                "TOKEN", "API_KEY", "AWS", "AZURE"}
        env = {}
        for k, v in os.environ.items():
            if any(skip in k.upper() for skip in SKIP):
                continue
            if len(v) < 200:
                env[k] = v
        return env

    def _capture_disk(self) -> List[dict]:
        if not PSUTIL_OK:
            return []
        disks = []
        for part in _psutil.disk_partitions():
            try:
                usage = _psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device":     part.device,
                    "mountpoint": part.mountpoint,
                    "fstype":     part.fstype,
                    "total_gb":   round(usage.total / 1024**3, 1),
                    "used_gb":    round(usage.used / 1024**3, 1),
                    "free_gb":    round(usage.free / 1024**3, 1),
                    "percent":    usage.percent,
                })
            except Exception:
                pass
        return disks

    def _capture_network(self) -> List[dict]:
        if not PSUTIL_OK:
            return []
        ifaces = []
        for name, addrs in _psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family.name in ("AF_INET", "AF_INET6"):
                    ifaces.append({"interface": name, "family": addr.family.name,
                                   "address": addr.address})
        return ifaces

    def _capture_procs(self) -> List[str]:
        if not PSUTIL_OK:
            return []
        try:
            names = sorted({p.name() for p in _psutil.process_iter(["name"])
                            if p.name()})
            return names[:50]
        except Exception:
            return []

    def _capture_igris_config(self) -> dict:
        config = {}
        for fname in ["igris_genome.json", "config_igris.json", ".env"]:
            fpath = os.path.join(self._base, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        raw = f.read()
                    if fname.endswith(".json"):
                        config[fname] = json.loads(raw)
                    else:
                        # Strip secrets from .env
                        lines = [l for l in raw.splitlines()
                                 if not any(s in l.upper() for s in ["KEY", "SECRET", "PASSWORD", "TOKEN"])]
                        config[fname] = "\n".join(lines)
                except Exception:
                    pass
        return config

    # ─────────────────────────────────────────────────────────────────────
    # RESTORE SCRIPT GENERATOR
    # ─────────────────────────────────────────────────────────────────────

    def _generate_restore_script(self, snap: SystemDNASnapshot) -> str:
        """Generate a PowerShell restore script."""
        pkg_lines = "\n".join([f"pip install {p}" for p in snap.python_packages[:100]])
        env_lines = "\n".join([f'[System.Environment]::SetEnvironmentVariable("{k}", "{v}", "User")'
                               for k, v in list(snap.environment_vars.items())[:20]])
        script = f"""# IGRIS SYSTEM DNA RESTORE SCRIPT
# Generated: {snap.created_at}
# DNA ID: {snap.dna_id}
# Python: {snap.platform_info.get('python', 'unknown')}

Write-Host "Restoring Igris DNA: {snap.dna_id}..." -ForegroundColor Cyan

# Step 1: Install Python packages
Write-Host "Installing packages..."
{pkg_lines}

# Step 2: Restore environment variables
Write-Host "Restoring environment..."
{env_lines}

# Step 3: Clone Igris repo (if needed)
# git clone <your-repo-url> sikander-os
# cd sikander-os
# pip install -r backend/requirements.txt

Write-Host "DNA Restore Complete!" -ForegroundColor Green
"""
        # Save script file
        script_path = os.path.join(self._dna_dir, f"{snap.dna_id}_restore.ps1")
        try:
            with open(script_path, "w") as f:
                f.write(script)
        except Exception:
            pass
        return script_path

    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────

    def list_snapshots(self) -> List[dict]:
        snaps = []
        for f in sorted(os.listdir(self._dna_dir)):
            if f.endswith(".json") and f.startswith("dna_") and f != self.DNA_FILE:
                fpath = os.path.join(self._dna_dir, f)
                try:
                    size = os.path.getsize(fpath)
                    snaps.append({"file": f, "size_kb": round(size/1024, 1)})
                except Exception:
                    pass
        return snaps

    def get_latest(self) -> Optional[dict]:
        with self._lock:
            return self._latest_dna.to_dict() if self._latest_dna else None

    def _load_latest(self):
        fp = os.path.join(self._dna_dir, self.DNA_FILE)
        if not os.path.exists(fp):
            return
        try:
            with open(fp) as f:
                data = json.load(f)
            self._latest_dna = SystemDNASnapshot(**{k: v for k, v in data.items()
                                                    if k in SystemDNASnapshot.__dataclass_fields__})
        except Exception:
            pass

    def get_stats(self) -> dict:
        with self._lock:
            latest = self._latest_dna
        return {
            "snapshots_count":   len(self.list_snapshots()),
            "dna_dir":           self._dna_dir,
            "latest_id":         latest.dna_id if latest else None,
            "latest_created":    latest.created_at if latest else None,
            "packages_captured": len(latest.python_packages) if latest else 0,
        }


_instance: Optional[SystemDNA] = None
_lock = threading.Lock()

def get_system_dna() -> SystemDNA:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SystemDNA()
    return _instance
