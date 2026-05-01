#!/usr/bin/env bash
# Sikander OS — run backend + frontend (requires two terminals or tmux)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
python main.py &
sleep 2
cd "$ROOT/frontend"
exec npm run dev
