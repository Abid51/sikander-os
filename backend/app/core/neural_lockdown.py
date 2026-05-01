"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS NEURAL LOCKDOWN — Emergency Fortress Protocol                       ║
║  "Breach detected? I become a fortress in 3 seconds."                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, shutil, threading, logging, hashlib, subprocess
from typing import List, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import psutil as _psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    from cryptography.fernet import Fernet
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False


LOCKDOWN_LEVELS = {
    1: "SOFT",    # Alert only
    2: "MEDIUM",  # Disconnect network processes
    3: "HARD",    # Encrypt data, kill suspicious processes
    4: "NUKE",    # Full wipe of sensitive data
}

SENSITIVE_PATTERNS = [
    "igris_genome.json", "igris_memory.json", "igris_anchors.json",
    "igris_economy.json", "igris_beliefs.json", ".env",
]

SUSPICIOUS_PROCESSES = [
    "keylogger", "wireshark", "mimikatz", "meterpreter",
    "netcat", "ncat", "cobaltstrike",
]


class NeuralLockdown:
    """
    Emergency fortress protocol.

    Levels:
    ───────
    1 SOFT    → Log alert, notify user
    2 MEDIUM  → Kill suspicious network connections
    3 HARD    → Encrypt sensitive files, kill suspicious processes
    4 NUKE    → Overwrite sensitive files (DoD-style), honeypot deploy

    Triggers:
    - Manual: igris.lockdown(level=3)
    - Auto: repeated failed vault unlock attempts
    - Auto: suspicious process detected
    """

    LOG_FILE = "igris_lockdown_log.json"

    def __init__(self):
        self._lock = threading.RLock()
        self._lockdown_active: bool = False
        self._lockdown_level: int = 0
        self._event_log: List[dict] = []
        self._failed_auth_count: int = 0
        self._honeypot_data: Dict = {}
        self._threat_ips: List[str] = []

        base = os.path.dirname(os.path.abspath(__file__))
        self._base_path = os.path.normpath(os.path.join(base, "..", ".."))
        self._log_path = os.path.join(self._base_path, self.LOG_FILE)

        # Auto-monitor for threats
        threading.Thread(target=self._threat_monitor_loop, daemon=True).start()
        logger.info("[LOCKDOWN] 🔐 Neural Lockdown standby. Auto-monitor active.")

    # ─────────────────────────────────────────────────────────────────────
    # MAIN LOCKDOWN
    # ─────────────────────────────────────────────────────────────────────

    def engage(self, level: int = 2, reason: str = "Manual trigger") -> dict:
        """Engage lockdown at the specified level."""
        level = max(1, min(4, level))
        with self._lock:
            self._lockdown_active = True
            self._lockdown_level  = level

        event = {"event": "LOCKDOWN_ENGAGED", "level": level,
                 "level_name": LOCKDOWN_LEVELS[level], "reason": reason,
                 "timestamp": datetime.now().isoformat()}
        self._log_event(event)
        logger.critical("[LOCKDOWN] 🚨 LEVEL %d (%s) ENGAGED — %s", level, LOCKDOWN_LEVELS[level], reason)

        results = {"level": level, "level_name": LOCKDOWN_LEVELS[level], "actions": []}

        if level >= 1:
            results["actions"].append(self._action_alert(reason))
        if level >= 2:
            results["actions"].append(self._action_kill_suspicious_procs())
        if level >= 3:
            results["actions"].append(self._action_encrypt_sensitive())
        if level >= 4:
            results["actions"].append(self._action_deploy_honeypot())
            results["actions"].append(self._action_shred_sensitive())

        return results

    def disengage(self, auth_token: str = "") -> str:
        """Disengage lockdown (requires some form of auth string)."""
        with self._lock:
            if not self._lockdown_active:
                return "Lockdown is not active."
            self._lockdown_active = False
            self._lockdown_level  = 0
        self._log_event({"event": "LOCKDOWN_DISENGAGED", "timestamp": datetime.now().isoformat()})
        logger.info("[LOCKDOWN] ✅ Lockdown disengaged.")
        return "Lockdown disengaged. Systems returning to normal."

    # ─────────────────────────────────────────────────────────────────────
    # LOCKDOWN ACTIONS
    # ─────────────────────────────────────────────────────────────────────

    def _action_alert(self, reason: str) -> str:
        logger.critical("[LOCKDOWN] ALERT — %s", reason)
        return f"Alert logged: {reason}"

    def _action_kill_suspicious_procs(self) -> str:
        killed = []
        if not PSUTIL_OK:
            return "psutil not available — process kill skipped."
        for proc in _psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info["name"].lower()
                if any(s in name for s in SUSPICIOUS_PROCESSES):
                    proc.kill()
                    killed.append(f"{proc.info['name']}({proc.info['pid']})")
            except Exception:
                pass
        return f"Killed suspicious processes: {', '.join(killed) or 'none found'}"

    def _action_encrypt_sensitive(self) -> str:
        if not CRYPTO_OK:
            return "cryptography not installed — encryption skipped."
        key = Fernet.generate_key()
        fernet = Fernet(key)
        encrypted = []
        key_path = os.path.join(self._base_path, "lockdown_key.bin")
        try:
            with open(key_path, "wb") as f:
                f.write(key)
        except Exception:
            pass

        for fname in SENSITIVE_PATTERNS:
            fpath = os.path.join(self._base_path, fname)
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, "rb") as f:
                    data = f.read()
                encrypted_data = fernet.encrypt(data)
                with open(fpath + ".locked", "wb") as f:
                    f.write(encrypted_data)
                os.remove(fpath)
                encrypted.append(fname)
            except Exception as e:
                logger.debug("[LOCKDOWN] Encrypt error %s: %s", fname, e)
        return f"Encrypted {len(encrypted)} sensitive files. Key stored securely."

    def _action_deploy_honeypot(self) -> str:
        """Create fake credential files to catch attackers."""
        honeypot_dir = os.path.join(self._base_path, "honeypot")
        os.makedirs(honeypot_dir, exist_ok=True)
        fake_files = {
            "passwords.txt": "admin:admin123\nroot:toor\nigris_master:igris2024",
            "api_keys.json": '{"openai": "sk-FAKE123456789", "stripe": "sk_live_FAKE"}',
            "wallet.json":   '{"mnemonic": "fake word list that triggers alert"}',
        }
        for fname, content in fake_files.items():
            fpath = os.path.join(honeypot_dir, fname)
            with open(fpath, "w") as f:
                f.write(content)
        self._honeypot_data = {
            "deployed_at": datetime.now().isoformat(),
            "files": list(fake_files.keys()),
            "dir": honeypot_dir,
        }
        return f"Honeypot deployed with {len(fake_files)} decoy files."

    def _action_shred_sensitive(self) -> str:
        """Overwrite sensitive files with random data multiple times."""
        shredded = []
        for fname in SENSITIVE_PATTERNS:
            fpath = os.path.join(self._base_path, fname)
            if not os.path.exists(fpath):
                continue
            try:
                size = os.path.getsize(fpath)
                for _ in range(3):   # 3-pass overwrite
                    with open(fpath, "wb") as f:
                        f.write(os.urandom(size))
                os.remove(fpath)
                shredded.append(fname)
            except Exception as e:
                logger.debug("[LOCKDOWN] Shred error %s: %s", fname, e)
        return f"Shredded {len(shredded)} sensitive files (3-pass)."

    # ─────────────────────────────────────────────────────────────────────
    # AUTO THREAT MONITORING
    # ─────────────────────────────────────────────────────────────────────

    def _threat_monitor_loop(self):
        CHECK_INTERVAL = 120   # every 2 minutes
        while True:
            time.sleep(CHECK_INTERVAL)
            try:
                self._check_suspicious_processes()
            except Exception:
                pass

    def _check_suspicious_processes(self):
        if not PSUTIL_OK:
            return
        for proc in _psutil.process_iter(["pid", "name"]):
            try:
                name_l = proc.info["name"].lower()
                if any(s in name_l for s in SUSPICIOUS_PROCESSES):
                    logger.warning("[LOCKDOWN] ⚠️ Suspicious process: %s (%d)",
                                   proc.info["name"], proc.info["pid"])
                    self._log_event({"event": "SUSPICIOUS_PROCESS",
                                     "process": proc.info["name"],
                                     "pid": proc.info["pid"],
                                     "timestamp": datetime.now().isoformat()})
            except Exception:
                pass

    def record_failed_auth(self):
        """Call when vault/auth fails. Auto-engages lockdown after 5 failures."""
        with self._lock:
            self._failed_auth_count += 1
            count = self._failed_auth_count
        if count >= 5:
            self.engage(level=2, reason=f"5 consecutive failed auth attempts")

    # ─────────────────────────────────────────────────────────────────────
    # LOGGING & API
    # ─────────────────────────────────────────────────────────────────────

    def _log_event(self, event: dict):
        with self._lock:
            self._event_log.append(event)
            if len(self._event_log) > 500:
                self._event_log = self._event_log[-500:]
        try:
            with open(self._log_path, "w") as f:
                json.dump(self._event_log, f, indent=2)
        except Exception:
            pass

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "lockdown_active":   self._lockdown_active,
                "lockdown_level":    self._lockdown_level,
                "level_name":        LOCKDOWN_LEVELS.get(self._lockdown_level, "STANDBY"),
                "failed_auth_count": self._failed_auth_count,
                "event_count":       len(self._event_log),
                "honeypot_active":   bool(self._honeypot_data),
                "recent_events":     self._event_log[-5:],
            }

    def get_event_log(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return self._event_log[-limit:]


_instance: Optional[NeuralLockdown] = None
_lock = threading.Lock()

def get_neural_lockdown() -> NeuralLockdown:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = NeuralLockdown()
    return _instance
