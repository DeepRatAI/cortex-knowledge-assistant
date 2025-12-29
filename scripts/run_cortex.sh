#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==========================================="
echo "  Starting Cortex Knowledge Assistant"
echo "==========================================="
echo "Root: $ROOT"

# Load environment variables from .env if present
if [ -f .env ]; then
  echo "[1/5] Loading .env..."
  set -a
  . .env
  set +a
else
  echo "[WARN] No .env file found!"
fi

# Stop any existing processes to avoid conflicts
echo "[2/5] Cleaning up old processes..."
pkill -f "uvicorn cortex_ka" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true

# Use infrastructure-only compose (no API container - we run API locally for dev)
echo "[3/5] Starting infrastructure (Qdrant, Redis, Ollama)..."
docker compose -f docker/compose.infra.yml up -d

mkdir -p logs

echo "[4/5] Starting API (uvicorn) locally, logs -> logs/api.log"
# Use '::' to bind to both IPv4 and IPv6, solving localhost resolution issues
nohup bash -c "cd $ROOT && set -a && . .env && set +a && .venv/bin/uvicorn cortex_ka.api.main:app --host '::' --port 8088 --reload" > logs/api.log 2>&1 &
API_PID=$!

# Wait for API to be ready
echo "    Waiting for API to start..."
sleep 4

# Check if API started successfully
if curl -s http://localhost:8088/health > /dev/null 2>&1; then
  echo "    ✓ API is running on http://localhost:8088"
else
  echo "    ✗ API failed to start. Check logs/api.log"
  tail -20 logs/api.log
fi

echo "[5/5] Starting UI (Vite), logs -> logs/ui.log"
cd ui
if [ ! -d node_modules ]; then
  echo "    Installing UI dependencies (npm install)..."
  npm install
fi
nohup npm run dev > ../logs/ui.log 2>&1 &

# Wait a moment for Vite to start
sleep 2

# Get the actual UI port from logs
UI_PORT=$(grep -oP 'http://localhost:\K[0-9]+' ../logs/ui.log 2>/dev/null | head -1 || echo "3000")

echo ""
echo "==========================================="
echo "  Cortex is ready!"
echo "==========================================="
echo "  API:  http://localhost:8088"
echo "  UI:   http://localhost:${UI_PORT}"
echo ""
echo "  Demo credentials:"
echo "    Admin:   gguerra.admin / Admin!G0nzalo"
echo "    Cliente: cliente_cli-81093 / Demo!CLI-81093"
echo ""
echo "  To stop: ./scripts/stop_cortex.sh"
echo "           (or: pkill -f uvicorn && pkill -f vite && docker compose -f docker/compose.infra.yml down)"
echo "==========================================="
