# Sikander-OS — Security Architecture

> Last updated: April 2026 | Implementation: `backend/app/core/security.py` + `security_system.py`

---

## Overview

Sikander-OS implements a **multi-layer, production-grade security stack** covering:
authentication, authorization, encryption, 2FA, audit logging, biometric verification,
zero-knowledge proofs, and intrusion detection.

---

## Layer 1 — Password Hashing

### Algorithm
- **Primary:** bcrypt (work factor = 12) via `bcrypt` library
- **Fallback:** PBKDF2-HMAC-SHA256 (480,000 iterations, 32-byte salt) — Python stdlib

### Usage
```python
from app.core.security import password_hasher

hash_val = password_hasher.hash("user_password")
is_valid  = password_hasher.verify("user_password", hash_val)
```

### Why bcrypt?
- Adaptive cost factor — slow by design
- Built-in salt — no rainbow tables
- Industry standard (same as Django, Laravel, Spring Security)

---

## Layer 2 — JWT Authentication

### Token Types

| Type | Expiry | Purpose |
|---|---|---|
| Access Token | 1 hour | API request authorization |
| Refresh Token | 30 days | Obtain new access token |

### Claims Structure
```json
{
  "user_id":   1,
  "username":  "alice",
  "role":      "admin",
  "type":      "access",
  "jti":       "uuid4-unique-id",
  "iat":       1713700000,
  "exp":       1713703600
}
```

### Refresh Token Rotation
```
Client → POST /auth/refresh {refresh_token: "old_token"}
Server → Validates jti against server-side store
       → Invalidates old token (removed from store)
       → Issues NEW access_token + NEW refresh_token
Client → Uses new tokens
```

**Security property:** Each refresh token can only be used **once**. Replay attacks are blocked.

### Logout-All
```python
security_manager.revoke_all_refresh_tokens(user_id)
# Removes all JTIs for this user → all sessions invalidated
```

---

## Layer 3 — Two-Factor Authentication (TOTP)

### Standard
- RFC 6238 — TOTP (Time-based One-Time Password)
- 30-second window with ±1 clock drift tolerance
- Compatible with: **Google Authenticator**, **Authy**, **1Password**, **Microsoft Authenticator**

### Flow
```
1. POST /api/admin/auth/2fa/provision  →  {secret, qr_uri}
2. User scans QR in authenticator app
3. POST /api/admin/auth/2fa/verify     →  {otp: "123456"}
4. 2FA enabled on account
```

### Implementation
```python
from app.core.security import totp_manager

# Provisioning
info = totp_manager.provision("username")
# info = {"secret": "BASE32SECRET", "qr_uri": "otpauth://totp/..."}

# Verification
valid = totp_manager.verify("username", user_provided_code)
```

---

## Layer 4 — Encryption

### Algorithm Selection

| Scenario | Algorithm |
|---|---|
| `cryptography` installed | **Fernet** (AES-128-CBC + HMAC-SHA256) |
| Fallback | Authenticated XOR with PBKDF2-derived key |

### Fernet Properties
- Symmetric authenticated encryption
- Random IV per message (ciphertexts never repeat)
- Built-in message authentication (HMAC)
- Timestamp embedded (detect replay)

```python
from app.core.security import encryption_manager

ct = encryption_manager.encrypt("classified data")
pt = encryption_manager.decrypt(ct)  # "classified data"
```

---

## Layer 5 — API Authentication Middleware

### Token Sources (checked in order)
1. `Authorization: Bearer <token>` header
2. `x-igris-token: <token>` header

### Timing-Safe Comparison
```python
# ✅ Correct (in api_auth.py)
hmac.compare_digest(provided_token, expected_token)

# ❌ Wrong (not used)
provided_token == expected_token  # timing attack vulnerable
```

### Exempt Paths
Configurable via `IGRIS_AUTH_EXEMPT` env var:
```
/docs,/redoc,/openapi.json,/health,/chat,/chat/stream
```

---

## Layer 6 — Audit Logging

All security events are logged to `igris_audit_log.json`:

```json
{
  "timestamp":  "2026-04-21T18:30:00Z",
  "event":      "login_success",
  "user_id":    1,
  "severity":   "INFO",
  "details":    {"ip": "192.168.1.1", "user_agent": "..."},
  "session_id": "uuid4"
}
```

**Events logged:**
- `login_success` / `login_failure`
- `token_refresh` / `token_revoke`
- `2fa_provision` / `2fa_success` / `2fa_failure`
- `password_change`
- `rate_limit_exceeded`
- `intrusion_detected`
- `classified_access` / `encryption_keyrotation`

---

## Layer 7 — Advanced Security System

### Biometric Authentication

| Modality | Algorithm | Storage |
|---|---|---|
| Fingerprint | Salted SHA-512 | In-memory hash store |
| Face | Salted SHA-512 | In-memory hash store |
| Iris | Salted SHA-512 | In-memory hash store |

> **Production upgrade:** Replace SHA-512 hash comparison with FaceNet/ArcFace neural embeddings + cosine similarity for true biometric verification.

### Zero-Knowledge Proof
```
1. Client → POST /security/zkp/challenge?user_id=X
   Server → { challenge: "random_hex_nonce" }

2. Client computes: proof = HMAC-SHA256(secret, nonce)

3. Client → POST /security/zkp/verify
            { user_id, proof }
   Server → Recomputes expected proof, compare_digest
   Server → Destroys nonce (one-time use)
```

**Property:** Server never learns the secret. Proof cannot be replayed (nonce consumed after one use).

### Intrusion Detection (IDS)

Threat scoring based on weighted indicators:

| Indicator | Weight |
|---|---|
| Failed logins (>5) | +0.3 |
| SQL injection attempt | +0.4 |
| XSS attempt | +0.3 |
| Privilege escalation | +0.5 |
| Unusual file operations | +0.2 |
| Blacklisted IP | Automatic block |

Threshold: `≥ 0.7` → Alert triggered, event logged.

---

## Rate Limiting

Sliding window per IP address:

```python
ok, info = security_manager.check_rate_limit(ip_address)
# ok=False when rate_limit_per_minute exceeded
# info = {"requests": N, "window_start": timestamp}
```

Default: 60 requests/minute. Override via `SecurityManager(rate_limit_per_minute=N)`.

---

## RBAC — Roles & Permissions

| Role | Permissions |
|---|---|
| `admin` | `admin, read, write, execute, monitor, security_config` |
| `operator` | `read, write, execute, monitor` |
| `user` | `read, write` |
| `readonly` | `read` |

```python
from app.core.security import permission_manager
ok = permission_manager.has_permission("user", "admin")  # False
ok = permission_manager.has_permission("admin", "read")  # True
```

---

## Security Checklist (Production)

```
☑  bcrypt installed: pip install bcrypt
☑  IGRIS_JWT_SECRET set (min 32 random chars)
☑  IGRIS_ENCRYPTION_KEY set (Fernet key)
☑  IGRIS_API_TOKEN set + passed to frontend
☑  Run behind HTTPS only
☑  CORS restricted to production domain
☑  IGRIS_ALLOWED_FILE_ROOTS restricted
☑  Audit log rotation configured
☑  2FA enabled on admin accounts
```
