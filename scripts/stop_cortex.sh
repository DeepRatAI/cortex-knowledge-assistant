#!/usr/bin/env bash
###############################################################################
# stop_cortex.sh — Detención limpia de Cortex Knowledge Assistant
#
# Detiene todos los servicios de forma ordenada:
#   1. API FastAPI (uvicorn)
#   2. UI React/Vite
#   3. Servicios Docker (Qdrant, Redis, Ollama) — opcional
#
# Uso:
#   ./scripts/stop_cortex.sh           # Detiene API y UI, mantiene Docker
#   ./scripts/stop_cortex.sh --all     # Detiene todo incluyendo Docker
#
###############################################################################

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }

stop_api() {
    log_info "Deteniendo API (uvicorn)..."
    
    if [ -f "$ROOT/logs/api.pid" ]; then
        local pid
        pid=$(cat "$ROOT/logs/api.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$ROOT/logs/api.pid"
    fi
    
    # Por si acaso, matar cualquier uvicorn cortex_ka
    pkill -f "uvicorn.*cortex_ka" 2>/dev/null || true
    
    log_ok "API detenida."
}

stop_ui() {
    log_info "Deteniendo UI (Vite)..."
    
    if [ -f "$ROOT/logs/ui.pid" ]; then
        local pid
        pid=$(cat "$ROOT/logs/ui.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$ROOT/logs/ui.pid"
    fi
    
    # Por si acaso
    pkill -f "node.*vite" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    
    log_ok "UI detenida."
}

stop_docker() {
    log_info "Deteniendo servicios Docker..."
    docker compose -f "$ROOT/docker/compose.infra.yml" down 2>/dev/null || true
    docker compose -f "$ROOT/docker/compose.yml" down 2>/dev/null || true
    log_ok "Servicios Docker detenidos."
}

main() {
    echo ""
    echo "============================================================"
    echo "  CORTEX KNOWLEDGE ASSISTANT - Detención"
    echo "============================================================"
    echo ""

    stop_api
    stop_ui

    if [[ "${1:-}" == "--all" ]]; then
        stop_docker
    else
        log_info "Servicios Docker (Qdrant, Redis, Ollama) siguen corriendo."
        log_info "Usa --all para detenerlos también."
    fi

    echo ""
    log_ok "Cortex detenido correctamente."
    echo ""
}

main "$@"
