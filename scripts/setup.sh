#!/usr/bin/env bash
# Local dev setup — run from repo root
set -euo pipefail

echo "[setup] Creating Python virtual environment..."
python -m venv .venv
source .venv/bin/activate

echo "[setup] Installing backend dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[setup] Copying .env.example → .env (edit with your keys)..."
[ -f .env ] || cp .env.example .env

echo "[setup] Installing frontend dependencies..."
cd frontend && npm install && cd ..

echo ""
echo "✓ Setup complete. Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Start backend: uvicorn app.main:app --reload --port 8000"
echo "  3. Start frontend: cd frontend && npm run dev"
