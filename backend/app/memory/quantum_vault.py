"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         IGRIS QUANTUM VAULT — AES-256-GCM Encrypted Storage               ║
║         "My secrets are buried in mathematics."                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import base64
import hashlib
import hmac
import threading
import secrets
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── Crypto Imports ───────────────────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("[QUANTUM VAULT] cryptography not installed. Vault disabled. Run: pip install cryptography")


# ═══════════════════════════════════════════════════════════════════════════════
#                          VAULT ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VaultEntry:
    """A single encrypted entry in the Vault."""
    entry_id: str
    label: str
    category: str              # api_key | password | wallet | note | identity | token
    encrypted_data: str        # base64-encoded ciphertext
    nonce: str                 # base64-encoded nonce
    created_at: str
    last_accessed: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    access_count: int = 0

    def to_dict(self) -> dict:
        """Returns metadata only — never the encrypted_data to external callers by default."""
        return {
            "entry_id": self.entry_id,
            "label": self.label,
            "category": self.category,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "tags": self.tags,
            "access_count": self.access_count,
        }

    def to_full_dict(self) -> dict:
        """Full dict including ciphertext for storage."""
        return {**self.to_dict(), "encrypted_data": self.encrypted_data, "nonce": self.nonce}


# ═══════════════════════════════════════════════════════════════════════════════
#                          QUANTUM VAULT
# ═══════════════════════════════════════════════════════════════════════════════

class QuantumVault:
    """
    AES-256-GCM Encrypted Secrets Vault for Igris.

    Security Model:
    ───────────────
    • Key Derivation : PBKDF2-SHA256 with 600,000 iterations (NIST 2023 recommendation)
    • Encryption     : AES-256-GCM (authenticated encryption — tamper-proof)
    • Nonce          : 12 bytes random per entry (never reused)
    • Master Key     : Never stored — derived from password on-the-fly
    • Auto-lock      : Vault locks after configurable inactivity timeout
    • Audit Log      : Every access is logged with timestamp
    • Backup         : Encrypted export for cloud sync
    """

    PBKDF2_ITERATIONS = 600_000
    SALT_SIZE = 32               # bytes
    NONCE_SIZE = 12              # bytes (GCM standard)
    AUTO_LOCK_MINUTES = 15
    MAX_FAILED_ATTEMPTS = 5

    def __init__(
        self,
        vault_path: str = None,
        dev_auto_unlock: bool = False,
        dev_unlock_password: str = "_igris_vault_test_",
    ):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.vault_path = vault_path or os.path.join(base_dir, "..", "..", "igris_vault.enc")
        self.vault_path = os.path.normpath(self.vault_path)

        self._lock = threading.RLock()
        self._vault_data: Dict[str, VaultEntry] = {}
        self._meta: dict = {}
        self._unlocked = False
        self._session_key: Optional[bytes] = None
        self._last_access = 0
        self._failed_attempts = 0
        self._locked_until: Optional[float] = None
        self._audit_log: List[dict] = []

        # Auto-lock watchdog
        threading.Thread(target=self._auto_lock_watchdog, daemon=True).start()

        if dev_auto_unlock and CRYPTO_AVAILABLE:
            if not os.path.exists(self.vault_path):
                self.initialize(dev_unlock_password)
            else:
                self.unlock(dev_unlock_password)

        if self._unlocked:
            logger.info("[QUANTUM VAULT] 🔓 Unlocked (dev auto).")
        else:
            logger.info("[QUANTUM VAULT] 🔐 Vault initialized. Locked.")

    # ──────────────────────────────────────────────────────────────────────────
    # KEY DERIVATION
    # ──────────────────────────────────────────────────────────────────────────

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive AES-256 key from password using PBKDF2-SHA256."""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography library not installed")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))

    # ──────────────────────────────────────────────────────────────────────────
    # VAULT LIFECYCLE
    # ──────────────────────────────────────────────────────────────────────────

    def initialize(self, master_password: str) -> str:
        """Create a new vault with a master password."""
        if os.path.exists(self.vault_path):
            return "Vault already exists. Use unlock() to open it."
        if not CRYPTO_AVAILABLE:
            return "ERROR: cryptography library not installed."
        salt = secrets.token_bytes(self.SALT_SIZE)
        key = self._derive_key(master_password, salt)
        # Store salt + empty encrypted store
        vault_container = {
            "salt": base64.b64encode(salt).decode(),
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "entries": {},
        }
        encrypted = self._encrypt_blob(json.dumps(vault_container), key)
        with open(self.vault_path, 'w') as f:
            json.dump({
                "salt": vault_container["salt"],
                "data": encrypted["ciphertext"],
                "nonce": encrypted["nonce"],
            }, f)
        self._session_key = key
        self._unlocked = True
        self._last_access = time.time()
        logger.info("[QUANTUM VAULT] ✅ New vault created and unlocked.")
        return "Quantum Vault initialized. NEVER forget your master password — it cannot be recovered."

    def unlock(self, master_password: str) -> bool:
        """Unlock the vault with the master password."""
        if not CRYPTO_AVAILABLE:
            logger.error("[QUANTUM VAULT] cryptography not installed")
            return False
        # Check lockout
        if self._locked_until and time.time() < self._locked_until:
            remaining = int(self._locked_until - time.time())
            logger.warning(f"[QUANTUM VAULT] 🔒 Locked out for {remaining}s due to failed attempts.")
            return False

        if not os.path.exists(self.vault_path):
            logger.error("[QUANTUM VAULT] Vault file not found. Call initialize() first.")
            return False

        try:
            with open(self.vault_path, 'r') as f:
                container = json.load(f)
            salt = base64.b64decode(container["salt"])
            key = self._derive_key(master_password, salt)
            plaintext = self._decrypt_blob(container["data"], container["nonce"], key)
            vault_data = json.loads(plaintext)

            with self._lock:
                self._session_key = key
                self._unlocked = True
                self._last_access = time.time()
                self._failed_attempts = 0
                self._locked_until = None
                # Load entries
                self._vault_data = {}
                for eid, edata in vault_data.get("entries", {}).items():
                    self._vault_data[eid] = VaultEntry(**edata)

            self._audit("UNLOCK", "vault_opened", success=True)
            logger.info(f"[QUANTUM VAULT] 🔓 Unlocked. {len(self._vault_data)} entries loaded.")
            return True

        except Exception as e:
            self._failed_attempts += 1
            self._audit("UNLOCK_FAIL", "wrong_password", success=False)
            logger.warning(f"[QUANTUM VAULT] ❌ Failed unlock attempt {self._failed_attempts}/{self.MAX_FAILED_ATTEMPTS}")
            if self._failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                self._locked_until = time.time() + 300  # 5 min lockout
                logger.warning("[QUANTUM VAULT] 🚨 Too many failed attempts. Locked for 5 minutes.")
            return False

    def lock(self) -> str:
        """Lock the vault and clear session key from memory."""
        with self._lock:
            self._session_key = None
            self._unlocked = False
            self._vault_data = {}
        self._audit("LOCK", "vault_locked", success=True)
        logger.info("[QUANTUM VAULT] 🔐 Vault locked.")
        return "Vault locked. Session key destroyed."

    def _auto_lock_watchdog(self):
        """Auto-lock vault after inactivity."""
        while True:
            time.sleep(60)
            if self._unlocked and self._last_access:
                elapsed = time.time() - self._last_access
                if elapsed > self.AUTO_LOCK_MINUTES * 60:
                    logger.info(f"[QUANTUM VAULT] ⏱️ Auto-locking after {self.AUTO_LOCK_MINUTES}min inactivity.")
                    self.lock()

    # ──────────────────────────────────────────────────────────────────────────
    # CRYPTO PRIMITIVES
    # ──────────────────────────────────────────────────────────────────────────

    def _encrypt_blob(self, plaintext: str, key: bytes) -> dict:
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        aesgcm = AESGCM(key)
        ct = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        return {
            "ciphertext": base64.b64encode(ct).decode(),
            "nonce": base64.b64encode(nonce).decode(),
        }

    def _decrypt_blob(self, ciphertext_b64: str, nonce_b64: str, key: bytes) -> str:
        nonce = base64.b64decode(nonce_b64)
        ct = base64.b64decode(ciphertext_b64)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode('utf-8')

    def _encrypt_entry(self, plaintext: str) -> Tuple:
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        aesgcm = AESGCM(self._session_key)
        ct = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        return base64.b64encode(ct).decode(), base64.b64encode(nonce).decode()

    def _decrypt_entry(self, ct_b64: str, nonce_b64: str) -> str:
        nonce = base64.b64decode(nonce_b64)
        ct = base64.b64decode(ct_b64)
        aesgcm = AESGCM(self._session_key)
        return aesgcm.decrypt(nonce, ct, None).decode('utf-8')

    def _assert_unlocked(self):
        if not self._unlocked or not self._session_key:
            raise PermissionError("Vault is locked. Call unlock() first.")
        self._last_access = time.time()

    # ──────────────────────────────────────────────────────────────────────────
    # CRUD OPERATIONS
    # ──────────────────────────────────────────────────────────────────────────

    def store(self, label: str, secret, category: str = "note",
              tags: List[str] = None) -> str:
        """Store a secret in the vault. ``secret`` may be a string or a JSON-serializable object."""
        self._assert_unlocked()
        if not isinstance(secret, str):
            secret = json.dumps(secret, ensure_ascii=False)
        entry_id = hashlib.sha256(f"{label}{time.time()}".encode()).hexdigest()[:16]
        ct, nonce = self._encrypt_entry(secret)
        entry = VaultEntry(
            entry_id=entry_id,
            label=label,
            category=category,
            encrypted_data=ct,
            nonce=nonce,
            created_at=datetime.now().isoformat(),
            tags=tags or [],
        )
        with self._lock:
            self._vault_data[entry_id] = entry
        self._save_vault()
        self._audit("STORE", f"stored:{label}", success=True)
        logger.info(f"[QUANTUM VAULT] 💾 Stored: {label} [{category}]")
        return entry_id

    def retrieve(self, key: str) -> Optional[str]:
        """Retrieve and decrypt a secret by entry_id or by human label."""
        self._assert_unlocked()
        with self._lock:
            entry = self._vault_data.get(key)
        if not entry:
            with self._lock:
                for e in self._vault_data.values():
                    if e.label == key or e.label.lower() == (key or "").lower():
                        entry = e
                        key = e.entry_id
                        break
        if not entry:
            return None
        try:
            plaintext = self._decrypt_entry(entry.encrypted_data, entry.nonce)
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
            self._save_vault()
            self._audit("RETRIEVE", f"retrieved:{entry.label}", success=True)
            return plaintext
        except Exception:
            self._audit("RETRIEVE_FAIL", f"tamper_detected:{entry.label}", success=False)
            logger.error(f"[QUANTUM VAULT] ⚠️ Tamper detected on entry: {entry.label}")
            return None

    def retrieve_by_label(self, label: str) -> Optional[str]:
        """Retrieve secret by human label."""
        self._assert_unlocked()
        with self._lock:
            for entry in self._vault_data.values():
                if entry.label.lower() == label.lower():
                    return self.retrieve(entry.entry_id)
        return None

    def delete(self, key: str) -> bool:
        """Permanently delete a vault entry by id or by label."""
        self._assert_unlocked()
        with self._lock:
            eid = key
            if key not in self._vault_data:
                for e in self._vault_data.values():
                    if e.label == key or e.label.lower() == (key or "").lower():
                        eid = e.entry_id
                        break
            if eid in self._vault_data:
                label = self._vault_data[eid].label
                del self._vault_data[eid]
                self._save_vault()
                self._audit("DELETE", f"deleted:{label}", success=True)
                return True
        return False

    def list_entries(self) -> List[dict]:
        """List all vault entries (metadata only — no secrets)."""
        self._assert_unlocked()
        with self._lock:
            return [e.to_dict() for e in self._vault_data.values()]

    def search(self, query: str) -> List[dict]:
        """Search entries by label or tag."""
        self._assert_unlocked()
        q = query.lower()
        with self._lock:
            return [
                e.to_dict() for e in self._vault_data.values()
                if q in e.label.lower() or any(q in t.lower() for t in e.tags)
            ]

    # ──────────────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────────────────────────────────

    def _save_vault(self):
        """Encrypt the entire vault and write to disk."""
        if not self._unlocked or not self._session_key:
            return
        try:
            with open(self.vault_path, 'r') as f:
                container = json.load(f)
            vault_data_plain = json.dumps({
                "version": "1.0",
                "created_at": container.get("created_at", datetime.now().isoformat()),
                "entries": {eid: e.to_full_dict() for eid, e in self._vault_data.items()},
            })
            encrypted = self._encrypt_blob(vault_data_plain, self._session_key)
            with open(self.vault_path, 'w') as f:
                json.dump({
                    "salt": container["salt"],
                    "data": encrypted["ciphertext"],
                    "nonce": encrypted["nonce"],
                }, f)
        except Exception as e:
            logger.error(f"[QUANTUM VAULT] Save error: {e}")

    def export_encrypted_backup(self, path: str) -> str:
        """Export encrypted vault backup."""
        self._assert_unlocked()
        try:
            with open(self.vault_path, 'rb') as f_in, open(path, 'wb') as f_out:
                f_out.write(f_in.read())
            return f"Encrypted backup saved: {path}"
        except Exception as e:
            return f"Backup failed: {e}"

    # ──────────────────────────────────────────────────────────────────────────
    # AUDIT LOG
    # ──────────────────────────────────────────────────────────────────────────

    def _audit(self, action: str, detail: str, success: bool):
        entry = {
            "time": datetime.now().isoformat(),
            "action": action,
            "detail": detail,
            "success": success,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > 500:
            self._audit_log = self._audit_log[-500:]

    def get_audit_log(self, limit: int = 50) -> List[dict]:
        return self._audit_log[-limit:]

    def get_stats(self) -> dict:
        return {
            "unlocked": self._unlocked,
            "entry_count": len(self._vault_data) if self._unlocked else "???",
            "auto_lock_minutes": self.AUTO_LOCK_MINUTES,
            "failed_attempts": self._failed_attempts,
            "locked_until": datetime.fromtimestamp(self._locked_until).isoformat() if self._locked_until else None,
            "vault_path": self.vault_path,
            "crypto_available": CRYPTO_AVAILABLE,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[QuantumVault] = None
_lock = threading.Lock()

def get_quantum_vault(vault_path: str = None) -> QuantumVault:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = QuantumVault(vault_path=vault_path)
    return _instance
