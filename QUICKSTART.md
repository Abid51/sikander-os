# 🚀 SIKANDER OS — QUICK START GUIDE

> **AI Operating System** — FastAPI backend · React + Vite frontend · 13 Daemons

---

## ⚡ Quick Setup (5 minutes)

### **Option A: Windows (Easiest)**

```bash
# 1. Clone & navigate
git clone https://github.com/Abid51/sikander-os.git
cd sikander-os

# 2. One-command setup
.\scripts\start-local.ps1
```

### **Option B: Linux / macOS**

```bash
# 1. Clone & navigate
git clone https://github.com/Abid51/sikander-os.git
cd sikander-os

# 2. Make executable & run
chmod +x scripts/start-local.sh
./scripts/start-local.sh
```

### **Option C: Manual Setup (Two terminals)**

**Terminal 1 — Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
python main.py
```
✅ API ready at: **http://127.0.0.1:8000**
📖 Docs at: **http://127.0.0.1:8000/docs**

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```
✅ UI ready at: **http://localhost:5173**

---

## 🎯 Next Steps

- **Full Documentation:** See [README.md](README.md)
- **Security Setup:** See [SECURITY.md](SECURITY.md)
- **Cloud Deployment:** See [CLOUD_AI_SETUP.md](CLOUD_AI_SETUP.md)
- **Testing:** `cd backend && python -m pytest tests/ -v`
- **Docker:** `docker compose up`

---

## ✅ Verify Installation

```bash
curl http://localhost:8000/health
# Should return: {"status": "ok", "service": "sikander-os-api"}
```

**Troubleshooting?** Check [README.md#Troubleshooting](README.md#troubleshooting)
