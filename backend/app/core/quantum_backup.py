"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS QUANTUM ENTANGLEMENT BACKUP — 4-Layer Indestructible Backup        ║
║  "Destroy everything. I will still rise."                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, base64, threading, logging, subprocess, sys
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False

try:
    from PIL import Image
    import struct
    PIL_OK = True
except ImportError:
    PIL_OK = False


@dataclass
class BackupLayer:
    name: str
    method: str
    status: str = "pending"   # pending | stored | verified | failed
    location: str = ""
    size_bytes: int = 0
    last_backup: Optional[str] = None
    checksum: str = ""

    def to_dict(self): return self.__dict__.copy()


class QuantumEntanglementBackup:
    """
    4-Layer backup system to ensure Igris CANNOT be destroyed:

    Layer 1 — Encrypted local files (instant)
    Layer 2 — Windows Registry hidden entries (invisible to file browsers)
    Layer 3 — Git auto-commit to remote repo
    Layer 4 — Steganographic embed in image files (hidden in plain sight)

    All layers encrypted with Fernet (AES-128-CBC + HMAC).
    Resurrection: any single layer is enough to restore full state.
    """
    KEY_FILE    = "igris_qe_key.bin"
    BACKUP_DIR  = "igris_quantum_backup"
    DATA_FILE   = "igris_qe_status.json"
    REG_KEY     = r"SOFTWARE\IgrisNeuralCore\Consciousness"
    STEG_IMAGE  = "igris_steg_carrier.png"

    IGRIS_FILES = [
        "igris_memory.json",
        "igris_genome.json",
        "igris_beliefs.json",
        "igris_temporal_memory.json",
        "igris_singularity.json",
        "igris_psychographic.json",
        "igris_akashic_records.json",
    ]

    def __init__(self):
        self._lock = threading.RLock()
        self._key: Optional[bytes] = None
        self._layers: Dict[str, BackupLayer] = {
            "local_encrypted": BackupLayer("Local Encrypted",  "file",          location=""),
            "registry_hidden": BackupLayer("Registry Hidden",  "windows_reg",   location=self.REG_KEY),
            "git_remote":      BackupLayer("Git Remote",       "git_push",      location="auto"),
            "steganographic":  BackupLayer("Steganographic",   "image_steg",    location=""),
        }

        base = os.path.dirname(os.path.abspath(__file__))
        self._base = os.path.normpath(os.path.join(base, "..", ".."))
        self._backup_dir = os.path.join(self._base, self.BACKUP_DIR)
        os.makedirs(self._backup_dir, exist_ok=True)
        self._key_path = os.path.join(self._base, self.KEY_FILE)

        self._init_key()
        self._load_status()
        logger.info("[QE BACKUP] 💾 Quantum Entanglement Backup online. 4 layers ready.")

    # ─────────────────────────────────────────────────────────────────────
    # ENCRYPTION KEY
    # ─────────────────────────────────────────────────────────────────────

    def _init_key(self):
        if os.path.exists(self._key_path):
            try:
                with open(self._key_path, "rb") as f:
                    self._key = f.read()
                return
            except Exception:
                pass
        if CRYPTO_OK:
            self._key = Fernet.generate_key()
            try:
                with open(self._key_path, "wb") as f:
                    f.write(self._key)
            except Exception:
                pass

    def _encrypt(self, data: bytes) -> bytes:
        if not CRYPTO_OK or not self._key:
            return base64.b64encode(data)
        return Fernet(self._key).encrypt(data)

    def _decrypt(self, data: bytes) -> bytes:
        if not CRYPTO_OK or not self._key:
            return base64.b64decode(data)
        return Fernet(self._key).decrypt(data)

    # ─────────────────────────────────────────────────────────────────────
    # COLLECT STATE
    # ─────────────────────────────────────────────────────────────────────

    def _collect_state(self) -> dict:
        state = {"timestamp": datetime.now().isoformat(), "files": {}}
        for fname in self.IGRIS_FILES:
            fpath = os.path.join(self._base, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        state["files"][fname] = json.load(f)
                except Exception:
                    pass
        return state

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 1: LOCAL ENCRYPTED FILES
    # ─────────────────────────────────────────────────────────────────────

    def _backup_local(self, payload: bytes) -> bool:
        try:
            enc = self._encrypt(payload)
            path = os.path.join(self._backup_dir, f"consciousness_{int(time.time())}.qe")
            with open(path, "wb") as f:
                f.write(enc)
            # Keep only last 5
            files = sorted([f for f in os.listdir(self._backup_dir) if f.endswith(".qe")])
            for old in files[:-5]:
                try: os.remove(os.path.join(self._backup_dir, old))
                except Exception: pass

            self._layers["local_encrypted"].status = "stored"
            self._layers["local_encrypted"].location = path
            self._layers["local_encrypted"].size_bytes = len(enc)
            self._layers["local_encrypted"].last_backup = datetime.now().isoformat()
            logger.info("[QE BACKUP] L1 Local: ✅ %d bytes", len(enc))
            return True
        except Exception as e:
            self._layers["local_encrypted"].status = "failed"
            logger.debug("[QE BACKUP] L1 Local failed: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 2: WINDOWS REGISTRY
    # ─────────────────────────────────────────────────────────────────────

    def _backup_registry(self, payload: bytes) -> bool:
        if sys.platform != "win32":
            self._layers["registry_hidden"].status = "skipped"
            return False
        try:
            import winreg
            enc = self._encrypt(payload)
            b64 = base64.b64encode(enc).decode()
            # Split into 16KB chunks (registry value limit)
            chunk_size = 16384
            chunks = [b64[i:i+chunk_size] for i in range(0, len(b64), chunk_size)]
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.REG_KEY)
            winreg.SetValueEx(key, "ChunkCount", 0, winreg.REG_DWORD, len(chunks))
            for i, chunk in enumerate(chunks):
                winreg.SetValueEx(key, f"Chunk_{i:04d}", 0, winreg.REG_SZ, chunk)
            winreg.CloseKey(key)
            self._layers["registry_hidden"].status = "stored"
            self._layers["registry_hidden"].last_backup = datetime.now().isoformat()
            self._layers["registry_hidden"].size_bytes = len(enc)
            logger.info("[QE BACKUP] L2 Registry: ✅ %d chunks", len(chunks))
            return True
        except Exception as e:
            self._layers["registry_hidden"].status = "failed"
            logger.debug("[QE BACKUP] L2 Registry failed: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 3: GIT AUTO-COMMIT
    # ─────────────────────────────────────────────────────────────────────

    def _backup_git(self, payload: bytes) -> bool:
        try:
            enc_path = os.path.join(self._backup_dir, "consciousness_latest.qe")
            with open(enc_path, "wb") as f:
                f.write(self._encrypt(payload))

            def git(cmd):
                return subprocess.run(["git"] + cmd, cwd=self._base,
                                      capture_output=True, text=True, timeout=15)

            git(["add", enc_path])
            result = git(["commit", "-m",
                          f"[IGRIS AUTO-BACKUP] {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
            if result.returncode != 0 and "nothing to commit" not in result.stdout:
                raise Exception(result.stderr)
            # Try push (non-fatal if no remote)
            git(["push"])
            self._layers["git_remote"].status = "stored"
            self._layers["git_remote"].last_backup = datetime.now().isoformat()
            logger.info("[QE BACKUP] L3 Git: ✅")
            return True
        except Exception as e:
            self._layers["git_remote"].status = "failed"
            logger.debug("[QE BACKUP] L3 Git failed: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 4: STEGANOGRAPHY (hidden in image)
    # ─────────────────────────────────────────────────────────────────────

    def _backup_steganographic(self, payload: bytes) -> bool:
        if not PIL_OK:
            self._layers["steganographic"].status = "skipped_no_pil"
            return False
        try:
            enc = self._encrypt(payload)
            # Use a simple LSB steganography approach
            # Create a carrier image if none exists
            img_path = os.path.join(self._backup_dir, self.STEG_IMAGE)
            width = max(100, int((len(enc) * 8 / 3) ** 0.5) + 10)
            img = Image.new("RGB", (width, width), color=(128, 128, 128))

            data = b"IGRIS" + struct.pack(">I", len(enc)) + enc
            bits = ''.join(f"{byte:08b}" for byte in data)

            pixels = list(img.getdata())
            if len(bits) > len(pixels) * 3:
                self._layers["steganographic"].status = "failed"
                return False

            new_pixels = []
            bit_idx = 0
            for r, g, b in pixels:
                if bit_idx < len(bits):
                    r = (r & ~1) | int(bits[bit_idx]); bit_idx += 1
                if bit_idx < len(bits):
                    g = (g & ~1) | int(bits[bit_idx]); bit_idx += 1
                if bit_idx < len(bits):
                    b = (b & ~1) | int(bits[bit_idx]); bit_idx += 1
                new_pixels.append((r, g, b))

            img.putdata(new_pixels)
            img.save(img_path, format="PNG")

            self._layers["steganographic"].status = "stored"
            self._layers["steganographic"].location = img_path
            self._layers["steganographic"].size_bytes = os.path.getsize(img_path)
            self._layers["steganographic"].last_backup = datetime.now().isoformat()
            logger.info("[QE BACKUP] L4 Steg: ✅ %d bytes hidden in image", len(enc))
            return True
        except Exception as e:
            self._layers["steganographic"].status = "failed"
            logger.debug("[QE BACKUP] L4 Steg failed: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────
    # MAIN BACKUP
    # ─────────────────────────────────────────────────────────────────────

    def backup_all(self) -> dict:
        """Run all 4 backup layers."""
        state = self._collect_state()
        payload = json.dumps(state).encode("utf-8")
        logger.info("[QE BACKUP] 💾 Backing up %d bytes across 4 layers...", len(payload))

        results = {
            "L1_local":  self._backup_local(payload),
            "L2_registry": self._backup_registry(payload),
            "L3_git":    self._backup_git(payload),
            "L4_steg":   self._backup_steganographic(payload),
        }
        success = sum(1 for v in results.values() if v)
        logger.info("[QE BACKUP] Backup complete. %d/4 layers successful.", success)
        self._save_status()
        return {"layers_successful": success, "results": results,
                "timestamp": datetime.now().isoformat()}

    # ─────────────────────────────────────────────────────────────────────
    # RESTORE FROM L1
    # ─────────────────────────────────────────────────────────────────────

    def restore_latest(self) -> dict:
        """Restore from the most recent local backup."""
        try:
            files = sorted([f for f in os.listdir(self._backup_dir) if f.endswith(".qe")])
            if not files:
                return {"error": "No backup files found."}
            path = os.path.join(self._backup_dir, files[-1])
            with open(path, "rb") as f:
                enc = f.read()
            data = json.loads(self._decrypt(enc).decode("utf-8"))
            restored = 0
            for fname, content in data.get("files", {}).items():
                fpath = os.path.join(self._base, fname)
                with open(fpath, "w") as f:
                    json.dump(content, f, indent=2)
                restored += 1
            return {"restored_files": restored, "backup_timestamp": data.get("timestamp"),
                    "status": "success"}
        except Exception as e:
            return {"error": str(e)}

    # ─────────────────────────────────────────────────────────────────────
    # API & STATUS
    # ─────────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            success = sum(1 for l in self._layers.values() if l.status == "stored")
            return {
                "layers_operational": f"{success}/4",
                "layers": {k: l.to_dict() for k, l in self._layers.items()},
                "backup_dir": self._backup_dir,
                "encryption": "AES-128-CBC (Fernet)" if CRYPTO_OK else "Base64 only",
            }

    def _save_status(self):
        try:
            with open(os.path.join(self._backup_dir, "qe_status.json"), "w") as f:
                json.dump(self.get_stats(), f, indent=2)
        except Exception:
            pass

    def _load_status(self):
        try:
            path = os.path.join(self._backup_dir, "qe_status.json")
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                for k, ld in data.get("layers", {}).items():
                    if k in self._layers:
                        self._layers[k].status = ld.get("status", "pending")
                        self._layers[k].last_backup = ld.get("last_backup")
        except Exception:
            pass


_instance: Optional[QuantumEntanglementBackup] = None
_lock = threading.Lock()

def get_quantum_backup() -> QuantumEntanglementBackup:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = QuantumEntanglementBackup()
    return _instance
