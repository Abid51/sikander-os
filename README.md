# Sikander-OS (Igris) — Complete Documentation

> **AI Operating System** — FastAPI backend · React + Vite dashboard  
> 81 Python modules · ~1,450+ functions · 99.3% production-ready

---

## Table of Contents

1. [Requirements](#requirements)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Security Layer](#security-layer)
5. [API Reference](#api-reference)
6. [Daemon System](#daemon-system)
7. [Plugin System](#plugin-system)
8. [Configuration](#configuration)
9. [Testing](#testing)
10. [Docker](#docker)
11. [Troubleshooting](#troubleshooting)

---

## Requirements

| Component | Version |
|-----------|---------|
| Python | 3.10+ (3.11 recommended) |
| Node.js | 18+ |
| Ollama | Optional — for local LLMs |

**Recommended Python packages (install once):**
```bash
pip install bcrypt pyotp cryptography   # security hardening
pip install psutil psutil               # system metrics
pip install fastapi uvicorn httpx       # core API
```

---

## Quick Start

### Option A — Two terminals (recommended)

**Terminal 1 — Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
copy .env.example .env         # edit keys if needed
python main.py
```
API live at → **http://127.0.0.1:8000** | Docs → **http://127.0.0.1:8000/docs**

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```
UI live at → **http://localhost:5173**

---

### Option B — One-shot scripts

```bash
# Windows PowerShell
.\scripts\start-local.ps1

# Linux / macOS
chmod +x scripts/start-local.sh && ./scripts/start-local.sh
```

---

### Option C — npm helpers (from repo root)

```bash
npm run install:all
npm run dev:backend    # terminal 1
npm run dev:frontend   # terminal 2
```

---

## Architecture

```
sikander-os/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── conftest.py              # pytest shared fixtures
│   ├── pytest.ini               # test configuration
│   ├── requirements.txt         # Python dependencies
│   ├── .env / .env.example      # environment variables
│   ├── app/
│   │   ├── core/                # 69 core modules
│   │   │   ├── security.py          ← Auth/JWT/bcrypt/TOTP
│   │   │   ├── security_system.py   ← Biometric/ZKP/IDS/Encryption
│   │   │   ├── api_auth.py          ← Middleware (timing-safe)
│   │   │   ├── database.py          ← SQLite ORM
│   │   │   ├── daemon_master.py     ← 13 daemon orchestrator
│   │   │   ├── plugin_loader.py     ← Dynamic plugin system
│   │   │   ├── ai_core.py           ← AI brain
│   │   │   ├── llm_manager.py       ← Multi-provider LLM
│   │   │   └── ... (63 more)
│   │   └── api/                 # 13 route files
│   │       ├── admin_routes.py       ← Auth + monitoring
│   │       ├── advanced_routes.py    ← Security/analytics/gaming
│   │       ├── routes.py             ← Core chat/voice
│   │       └── ... (10 more)
│   ├── tests/
│   │   ├── test_security_core.py    ← 100+ security tests
│   │   ├── test_daemon_api.py       ← Daemon + API tests
│   │   ├── test_backend.py          ← Memory/tools/LLM tests
│   │   └── test_power_pack.py       ← Power features
│   └── plugins/                 # Drop .py plugins here
├── frontend/                    # Vite + React dashboard
├── scripts/                     # start-local.* helpers
├── docker-compose.yml
└── README.md
```

---

## Security Layer

Sikander-OS implements **production-grade security** across 6 modules:

### Password Hashing
```python
from app.core.security import password_hasher

hashed = password_hasher.hash("my_password")       # bcrypt (rounds=12)
valid  = password_hasher.verify("my_password", hashed)  # True
```
- **Primary:** bcrypt (rounds=12)  
- **Fallback:** PBKDF2-SHA256 (480,000 iterations) if bcrypt not installed

### JWT Authentication
```python
from app.core.security import security_manager

# Generate access + refresh tokens
access  = security_manager.generate_jwt_token(user_id=1, username="alice",
              expires_in_hours=1, extra_claims={"role": "admin"})
refresh = security_manager.generate_refresh_token(user_id=1, username="alice")

# Verify
valid, payload = security_manager.verify_jwt_token(access)

# Rotate refresh token (old one invalidated)
ok, result = security_manager.use_refresh_token(refresh)
# result contains new access_token + refresh_token

# Logout-all
security_manager.revoke_all_refresh_tokens(user_id=1)
```

### Two-Factor Authentication (TOTP)
```python
from app.core.security import totp_manager

# Provision (returns secret + QR URI for Google Authenticator)
info = totp_manager.provision("alice")

# Verify code from authenticator app
valid = totp_manager.verify("alice", "123456")
```

### Encryption
```python
from app.core.security import encryption_manager

ct = encryption_manager.encrypt("sensitive data")   # Fernet/AES
pt = encryption_manager.decrypt(ct)                 # → "sensitive data"
```

### Audit Logging
```python
from app.core.security import audit_logger

audit_logger.log_event("login_success", user_id=1,
    details={"ip": "192.168.1.1"}, severity="INFO")

recent = audit_logger.get_events(limit=50, severity="WARNING")
```

### Environment Variables (Security)

| Variable | Required | Description |
|---|---|---|
| `IGRIS_JWT_SECRET` | ✅ Prod | JWT signing key (min 32 chars) |
| `IGRIS_ENCRYPTION_KEY` | ✅ Prod | Fernet encryption key (base64) |
| `IGRIS_API_TOKEN` | Optional | Bearer token for API auth gate |
| `IGRIS_AUTH_EXEMPT` | Optional | Comma-separated exempt paths |

---

## API Reference

### Authentication Endpoints (`/api/admin/auth/`)

| Method | Path | Description |
|---|---|---|
| POST | `/register` | Register new user |
| POST | `/login` | Login → `{access_token, refresh_token}` |
| POST | `/refresh` | Rotate refresh token |
| POST | `/logout` | Revoke all sessions |
| POST | `/verify-token` | Validate JWT |
| POST | `/change-password` | Change password + revoke sessions |
| POST | `/2fa/provision` | Get TOTP secret + QR URI |
| POST | `/2fa/verify` | Verify TOTP code |

**Login example:**
```bash
curl -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "Str0ngP@ss"}'
```

---

### Security Endpoints (`/api/advanced/security/`)

| Method | Path | Description |
|---|---|---|
| GET  | `/status` | Full security posture report |
| POST | `/authenticate` | Biometric MFA |
| POST | `/encrypt` | Fernet/AES data encryption |
| POST | `/decrypt` | Decrypt data |
| POST | `/scan` | Vulnerability assessment |
| POST | `/lockdown` | Engage neural lockdown (level 1–4) |
| GET  | `/lockdown/status` | Lockdown state |
| POST | `/lockdown/disengage` | Lift lockdown |
| POST | `/shadow/authorize` | Authorize pentest target |
| POST | `/shadow/recon` | Full recon pipeline |
| GET  | `/shadow/reports` | Recon history |

---

### Dashboard Endpoints (`/api/advanced/dashboard/`)

| Method | Path | Description |
|---|---|---|
| GET | `/overview` | System status + uptime |
| GET | `/metrics` | Real-time CPU/RAM/disk via psutil |
| POST | `/create` | Create custom dashboard |

---

### Cybersecurity (`/api/advanced/cybersecurity/`)

| Method | Path | Description |
|---|---|---|
| POST | `/scan-ports` | TCP port scan |
| POST | `/vulnerability-assessment` | CVE check |
| POST | `/security-audit` | Full audit report |
| POST | `/network-analysis` | Traffic analysis |
| POST | `/password-strength` | Entropy scoring |
| POST | `/ssl-check` | Certificate analysis |

---

### Core Endpoints

| Method | Path | Description |
|---|---|---|
| GET  | `/health` | Liveness check |
| POST | `/chat` | Full AI agent (tools + memory) |
| POST | `/chat/stream` | SSE streaming response |
| GET  | `/observability/snapshot` | Metrics + queue depth |
| GET  | `/docs` | OpenAPI UI |
| GET  | `/api/admin/monitor/health` | Admin health |
| GET  | `/api/admin/monitor/metrics` | Admin metrics |
| GET  | `/api/admin/audit/logs` | Audit log |

---

## Daemon System

13 autonomous background daemons:

| # | Daemon | ID | Purpose |
|---|---|---|---|
| 1 | Blood Ward | `blood_ward_01` | Security & threat detection |
| 2 | Dominion | `dominion_02` | OS & process control |
| 3 | Phantom Recon | `phantom_recon_03` | Network intelligence |
| 4 | Crimson Ledger | `crimson_ledger_04` | Finance & crypto |
| 5 | Shadow Forge | `shadow_forge_05` | Code generation |
| 6 | Soul Weaver | `soul_weaver_06` | Memory & learning |
| 7 | Storm Caller | `storm_caller_07` | Automation & scheduling |
| 8 | Void Walker | `void_walker_08` | File management |
| 9 | Aether Eye | `aether_eye_09` | Vision & OCR |
| 10 | Whisper Wind | `whisper_wind_10` | Voice & audio |
| 11 | Data Drake | `data_drake_11` | Data analysis |
| 12 | Iron Crown | `iron_crown_12` | Hardware control |
| 13 | Chronos | `chronos_13` | Time & prediction |

**Control via API:**
```bash
# Start a daemon
POST /api/daemon/start?daemon_id=blood_ward_01

# Stop a daemon
POST /api/daemon/stop?daemon_id=blood_ward_01

# Status of all daemons
GET /api/daemon/status
```

---

## Plugin System

Drop any `.py` file into `backend/plugins/` — it auto-loads on startup.

### Minimal plugin example
```python
# backend/plugins/my_plugin.py
from app.core.plugin_loader import IgrisPlugin

class MyPlugin(IgrisPlugin):
    NAME        = "my_plugin"
    VERSION     = "1.0.0"
    DESCRIPTION = "My custom plugin"
    AUTHOR      = "Your Name"
    REQUIRES    = []  # pip packages this plugin needs

    def on_load(self):
        print("My plugin loaded!")

    def on_command(self, command: str, args: dict):
        if command == "my_command":
            return {"result": f"Hello from plugin! args={args}"}
        return None  # pass to next plugin

    def on_message(self, user_msg: str, ai_response: str):
        # Optionally modify every AI response
        return None  # return None to leave unchanged

    def get_commands(self):
        return [{"name": "my_command", "description": "Custom command"}]
```

### Hot-reload (file watcher)
```python
from app.core.plugin_loader import get_plugin_loader
loader = get_plugin_loader()
loader.start_file_watcher(interval=5.0)   # auto-reloads on file change
```

### Marketplace API
```bash
GET  /api/plugins/list          # list installed
POST /api/plugins/reload        # reload all
POST /api/plugins/install       # install from path/URL
POST /api/plugins/uninstall     # remove plugin
```

---

## Configuration

### `backend/.env` (full reference)

```env
# ── LLM ──────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
GROQ_API_KEY=...

# ── Security ──────────────────────────────────────────────
IGRIS_JWT_SECRET=your-super-secret-jwt-key-min-32-chars
IGRIS_ENCRYPTION_KEY=your-fernet-compatible-base64-key
IGRIS_API_TOKEN=optional-bearer-token-for-api-auth
IGRIS_AUTH_EXEMPT=/docs,/health,/chat,/chat/stream

# ── File Access ───────────────────────────────────────────
IGRIS_ALLOWED_FILE_ROOTS=C:\Users\AABI\Documents

# ── Plugin Marketplace ────────────────────────────────────
IGRIS_PLUGIN_INDEX_URL=     # optional remote plugin index URL

# ── Database ──────────────────────────────────────────────
# Default: backend/igris.db (SQLite)  Override if needed:
# DATABASE_URL=sqlite:///./igris.db
```

---

## Testing

### Run all tests
```bash
cd backend
python -m pytest tests/ -v --tb=short
```

### Run specific suites
```bash
# Security & core module tests only
python -m pytest tests/test_security_core.py -v

# Daemon & API integration tests
python -m pytest tests/test_daemon_api.py -v

# Original backend tests (memory, tools, LLM)
python -m pytest tests/test_backend.py -v

# All tests with coverage report
python -m pytest tests/ --cov=app --cov-report=term-missing
```

### Test suites summary

| File | Tests | Covers |
|---|---|---|
| `test_security_core.py` | 60+ | Passwords, JWT, TOTP, Encryption, AuditLogger, RBAC, RateLimit, API auth, DB CRUD, PluginLoader, AdvancedSecuritySystem |
| `test_daemon_api.py` | 30+ | BaseDaemon, BloodWard, Dominion, ShadowForge, PhantomRecon, REST API integration |
| `test_backend.py` | 50+ | Neural memory, Calculator, Python sandbox, FileManager, LLM config, Embeddings |
| `test_power_pack.py` | 5+ | Power features |

---

## Docker

```bash
# Copy env file (optional — edit API keys)
copy backend\.env.example backend\.env   # Windows
# cp backend/.env.example backend/.env  # Linux/macOS

# Build and start
docker compose build
docker compose up
```

| URL | Service |
|---|---|
| http://127.0.0.1:8000 | API |
| http://localhost:8080 | UI (nginx) |

> **Linux only:** uses `backend/requirements-docker.txt` (no WMI). Full Windows features need native install.

---

## Production Hardening Checklist

```
☐ Set IGRIS_JWT_SECRET (min 32 chars, random)
☐ Set IGRIS_ENCRYPTION_KEY (Fernet-compatible base64)
☐ Set IGRIS_API_TOKEN in backend + VITE_IGRIS_TOKEN in frontend
☐ Restrict IGRIS_ALLOWED_FILE_ROOTS to safe dirs only
☐ pip install bcrypt pyotp cryptography
☐ Run behind HTTPS (nginx/caddy reverse proxy)
☐ Narrow CORS in main.py to your domain
☐ Build frontend: cd frontend && npm run build
☐ Serve frontend dist/ via nginx
☐ Set up log rotation for igris_audit_log.json
☐ Schedule periodic DB backup (quantum_backup module)
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Unicode/emoji errors on Windows console | Windows Terminal recommended; stdout reconfigured to UTF-8 in `main.py` |
| Chat returns error | Ensure Ollama is running (`ollama serve`) or cloud API key is set |
| CORS error in browser | Frontend must use origins allowed in `main.py` (default: localhost Vite ports) |
| JWT verification fails | Check `IGRIS_JWT_SECRET` is same between restarts |
| bcrypt not found | `pip install bcrypt` — fallback PBKDF2 is used automatically |
| Plugin not loading | Ensure plugin class inherits `IgrisPlugin`; check `plugins/` dir path |
| Database locked | Only one process should write; ensure no zombie processes |
| Rate limit exceeded (429) | Increase `rate_limit_per_minute` in `SecurityManager` init |

---

## License

Released under the [MIT License](LICENSE). Change the copyright line to your name.
