#!/usr/bin/env bash
###############################################################################
# start_cortex_full.sh — Arranque canónico de Cortex Knowledge Assistant
#
# Este script levanta la plataforma completa:
#   1. Infraestructura Docker: Qdrant (vectores), Redis (cache), Ollama (LLM local backup)
#   2. API FastAPI con uvicorn (puerto 8088)
#   3. UI React/Vite (puerto 3000)
#
# Requisitos:
#   - Docker y docker compose instalados
#   - Python 3.11+ con virtualenv en .venv/
#   - Node.js 18+ (para la UI)
#   - Archivo .env configurado en la raíz del proyecto
#
# Uso:
#   ./scripts/start_cortex_full.sh          # Arranque normal
#   ./scripts/start_cortex_full.sh --clean  # Limpia procesos anteriores primero
#
# Autor: Cortex Engineering Team
# Fecha: 2025-12-02
###############################################################################

set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directorio raíz del proyecto
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

###############################################################################
# FUNCIONES AUXILIARES
###############################################################################

check_prerequisites() {
    log_info "Verificando prerequisitos..."

    # Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker no está instalado. Instálalo primero."
        exit 1
    fi

    # Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose no está disponible. Instálalo primero."
        exit 1
    fi

    # Python venv
    if [ ! -d "$ROOT/.venv" ]; then
        log_warn "No existe .venv. Creando entorno virtual..."
        python3 -m venv "$ROOT/.venv"
        "$ROOT/.venv/bin/pip" install --upgrade pip
        "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
    fi

    # Node modules para UI
    if [ ! -d "$ROOT/ui/node_modules" ]; then
        log_warn "No existen node_modules en ui/. Instalando dependencias..."
        (cd "$ROOT/ui" && npm install)
    fi

    # Archivo .env
    if [ ! -f "$ROOT/.env" ]; then
        log_error "No existe archivo .env en la raíz del proyecto."
        log_error "Copia .env.example a .env y configura las variables necesarias."
        exit 1
    fi

    log_ok "Prerequisitos verificados."
}

cleanup_previous() {
    log_info "Limpiando procesos anteriores..."

    # Matar uvicorn anterior si existe
    pkill -f "uvicorn cortex_ka.api.main" 2>/dev/null || true

    # Matar Vite/npm anterior si existe
    pkill -f "node.*vite" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true

    sleep 1

    # Verificar que los puertos están libres
    if lsof -i :8088 &>/dev/null; then
        log_error "Puerto 8088 sigue ocupado. Cierra el proceso manualmente."
        lsof -i :8088
        exit 1
    fi

    if lsof -i :3000 &>/dev/null; then
        log_error "Puerto 3000 sigue ocupado. Cierra el proceso manualmente."
        lsof -i :3000
        exit 1
    fi

    log_ok "Puertos 8088 y 3000 libres."
}

load_env() {
    log_info "Cargando variables de entorno desde .env..."
    set -a
    # shellcheck source=/dev/null
    source "$ROOT/.env"
    set +a
    log_ok "Variables de entorno cargadas."
}

start_docker_services() {
    log_info "Levantando servicios Docker (Qdrant, Redis, Ollama)..."

    docker compose -f "$ROOT/docker/compose.yml" up -d qdrant redis ollama

    # Esperar a que Qdrant esté listo
    log_info "Esperando a que Qdrant esté listo..."
    local retries=30
    while ! curl -s http://localhost:6333/healthz &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            log_error "Qdrant no respondió después de 30 segundos."
            exit 1
        fi
        sleep 1
    done
    log_ok "Qdrant listo en http://localhost:6333"

    # Verificar Redis
    if docker exec cortex_redis redis-cli ping &>/dev/null; then
        log_ok "Redis listo."
    else
        log_warn "Redis no respondió al ping (puede estar deshabilitado en .env)."
    fi

    # Verificar Ollama (healthcheck)
    log_info "Esperando a que Ollama esté listo..."
    local ollama_retries=60
    while ! docker exec cortex_ollama ollama list &>/dev/null; do
        ollama_retries=$((ollama_retries - 1))
        if [ $ollama_retries -le 0 ]; then
            log_warn "Ollama tardó en arrancar (puede requerir descarga de modelo)."
            break
        fi
        sleep 1
    done
    log_ok "Ollama disponible en http://localhost:11434"
}

start_api() {
    log_info "Iniciando API FastAPI (uvicorn) en puerto 8088..."

    mkdir -p "$ROOT/logs"

    # Activar venv y arrancar uvicorn en background
    # Usamos nohup para que sobreviva al cierre de la terminal
    nohup bash -c "
        cd '$ROOT'
        source .venv/bin/activate
        set -a; source .env; set +a
        export PYTHONPATH='$ROOT/src:\$PYTHONPATH'
        exec uvicorn cortex_ka.api.main:app --host 0.0.0.0 --port 8088 --reload
    " > "$ROOT/logs/api.log" 2>&1 &

    local api_pid=$!
    echo "$api_pid" > "$ROOT/logs/api.pid"

    # Esperar a que la API responda
    log_info "Esperando a que la API responda..."
    local retries=30
    while ! curl -s http://localhost:8088/health &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            log_error "La API no respondió después de 30 segundos."
            log_error "Revisa logs/api.log para más detalles:"
            tail -20 "$ROOT/logs/api.log"
            exit 1
        fi
        sleep 1
    done

    log_ok "API lista en http://localhost:8088"
    log_info "  → Health: http://localhost:8088/health"
    log_info "  → Logs: $ROOT/logs/api.log"
}

start_ui() {
    log_info "Iniciando UI React/Vite en puerto 3000..."

    mkdir -p "$ROOT/logs"

    nohup bash -c "
        cd '$ROOT/ui'
        exec npm run dev
    " > "$ROOT/logs/ui.log" 2>&1 &

    local ui_pid=$!
    echo "$ui_pid" > "$ROOT/logs/ui.pid"

    # Esperar a que Vite arranque
    sleep 3

    # Verificar que Vite está corriendo
    if curl -s http://localhost:3000 &>/dev/null; then
        log_ok "UI lista en http://localhost:3000"
    else
        log_warn "UI puede tardar unos segundos más. Revisa logs/ui.log"
    fi

    log_info "  → Logs: $ROOT/logs/ui.log"
}

print_summary() {
    echo ""
    echo "============================================================"
    echo -e "${GREEN}✓ CORTEX KNOWLEDGE ASSISTANT - ARRANCADO${NC}"
    echo "============================================================"
    echo ""
    echo "Servicios activos:"
    echo "  • API FastAPI:     http://localhost:8088"
    echo "  • UI React/Vite:   http://localhost:3000"
    echo "  • Qdrant:          http://localhost:6333"
    echo "  • Ollama:          http://localhost:11434"
    echo ""
    echo "Logs:"
    echo "  • API: $ROOT/logs/api.log"
    echo "  • UI:  $ROOT/logs/ui.log"
    echo ""
    echo "Credenciales demo:"
    echo "  • Admin:   gguerra.admin / Admin@123"
    echo "  • Cliente: cliente_cli-81093 / Demo!CLI-81093"
    echo ""
    echo "Para detener todo:"
    echo "  make cortex-down"
    echo "  # o manualmente:"
    echo "  docker compose -f docker/compose.yml down"
    echo "  pkill -f 'uvicorn cortex_ka'"
    echo "  pkill -f 'node.*vite'"
    echo ""
    echo "============================================================"
}

###############################################################################
# MAIN
###############################################################################

main() {
    echo ""
    echo "============================================================"
    echo "  CORTEX KNOWLEDGE ASSISTANT - Arranque Full"
    echo "============================================================"
    echo ""

    # Procesar argumentos
    if [[ "${1:-}" == "--clean" ]]; then
        cleanup_previous
    fi

    check_prerequisites
    cleanup_previous
    load_env
    start_docker_services
    start_api
    start_ui
    print_summary
}

main "$@"
