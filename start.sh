#!/usr/bin/env bash
###############################################################################
# start.sh — Script de arranque único para Cortex Knowledge Assistant
#
# Este es el ÚNICO script que un usuario necesita ejecutar.
# Detecta automáticamente si es primer arranque y guía al usuario.
#
# Uso:
#   ./start.sh              # Arranque normal (detecta primer uso)
#   ./start.sh --setup      # Forzar modo setup
#   ./start.sh --headless   # Sin abrir navegador
#
# Autor: Cortex Engineering Team
###############################################################################

set -euo pipefail

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Directorio raíz
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Flags
HEADLESS=false
FORCE_SETUP=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --headless) HEADLESS=true; shift ;;
        --setup) FORCE_SETUP=true; shift ;;
        *) shift ;;
    esac
done

###############################################################################
# FUNCIONES
###############################################################################

print_banner() {
    clear
    echo -e "${CYAN}"
    cat << 'EOF'
   ____           _            
  / ___|___  _ __| |_ _____  __
 | |   / _ \| '__| __/ _ \ \/ /
 | |__| (_) | |  | ||  __/>  < 
  \____\___/|_|   \__\___/_/\_\
                               
  Knowledge Assistant
EOF
    echo -e "${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

log_info()  { echo -e "  ${BLUE}ℹ${NC}  $1"; }
log_ok()    { echo -e "  ${GREEN}✓${NC}  $1"; }
log_warn()  { echo -e "  ${YELLOW}⚠${NC}  $1"; }
log_error() { echo -e "  ${RED}✗${NC}  $1"; }
log_step()  { echo -e "\n${BOLD}▸ $1${NC}"; }

is_first_run() {
    # Es primer arranque si no existe .env O no existe login.db con usuarios admin
    if [ ! -f "$ROOT/.env" ]; then
        return 0  # true, es primer run
    fi
    if [ ! -f "$ROOT/login.db" ]; then
        return 0  # true, es primer run
    fi
    # Verificar si hay admins en la DB
    if command -v sqlite3 &>/dev/null; then
        local admin_count
        admin_count=$(sqlite3 "$ROOT/login.db" "SELECT COUNT(*) FROM login_users WHERE role='admin';" 2>/dev/null || echo "0")
        if [ "$admin_count" = "0" ]; then
            return 0  # true, no hay admins
        fi
    fi
    return 1  # false, no es primer run
}

check_dependencies() {
    log_step "Verificando dependencias..."
    
    local missing=()
    
    # Docker
    if ! command -v docker &>/dev/null; then
        missing+=("docker")
    fi
    
    # Docker Compose
    if ! docker compose version &>/dev/null 2>&1; then
        missing+=("docker-compose")
    fi
    
    # Python 3.10+
    if ! command -v python3 &>/dev/null; then
        missing+=("python3")
    else
        local py_version
        py_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [[ $(echo "$py_version < 3.10" | bc -l 2>/dev/null || echo "0") == "1" ]]; then
            log_warn "Python $py_version detectado. Se recomienda 3.10+"
        fi
    fi
    
    # Node.js
    if ! command -v node &>/dev/null; then
        missing+=("nodejs")
    fi
    
    # npm
    if ! command -v npm &>/dev/null; then
        missing+=("npm")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Faltan dependencias: ${missing[*]}"
        echo ""
        echo "  Instala las dependencias faltantes:"
        echo "    Ubuntu/Debian: sudo apt install docker.io docker-compose nodejs npm python3 python3-venv"
        echo "    Fedora:        sudo dnf install docker docker-compose nodejs npm python3"
        echo "    macOS:         brew install docker docker-compose node python@3.11"
        echo ""
        exit 1
    fi
    
    log_ok "Todas las dependencias están instaladas"
}

setup_first_run() {
    log_step "Configuración de primer arranque..."
    
    # Crear .env desde template
    if [ ! -f "$ROOT/.env" ]; then
        if [ -f "$ROOT/.env.example" ]; then
            cp "$ROOT/.env.example" "$ROOT/.env"
            log_ok "Creado .env desde template"
        else
            log_error "No existe .env.example"
            exit 1
        fi
    fi
    
    # Solicitar HuggingFace API Key
    echo ""
    echo -e "  ${CYAN}┌─────────────────────────────────────────────────────────┐${NC}"
    echo -e "  ${CYAN}│${NC}  Cortex necesita una API key de HuggingFace para el LLM ${CYAN}│${NC}"
    echo -e "  ${CYAN}│${NC}  Obtén tu key gratis en: https://huggingface.co/settings/tokens ${CYAN}│${NC}"
    echo -e "  ${CYAN}└─────────────────────────────────────────────────────────┘${NC}"
    echo ""
    
    read -rp "  Ingresa tu HuggingFace API Key (o Enter para saltar): " hf_key
    
    if [ -n "$hf_key" ]; then
        # Actualizar .env con la key
        if grep -q "^HF_API_KEY=" "$ROOT/.env"; then
            sed -i "s|^HF_API_KEY=.*|HF_API_KEY=$hf_key|" "$ROOT/.env"
        else
            echo "HF_API_KEY=$hf_key" >> "$ROOT/.env"
        fi
        log_ok "API Key configurada"
    else
        log_warn "Sin API Key. Podrás configurarla luego en .env"
    fi
    
    # Generar JWT secret único
    local jwt_secret
    jwt_secret=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p)
    sed -i "s|^CKA_JWT_SECRET=.*|CKA_JWT_SECRET=$jwt_secret|" "$ROOT/.env"
    log_ok "JWT Secret generado"
    
    echo ""
}

setup_python_env() {
    log_step "Configurando entorno Python..."
    
    if [ ! -d "$ROOT/.venv" ]; then
        python3 -m venv "$ROOT/.venv"
        log_ok "Entorno virtual creado"
    fi
    
    # Instalar dependencias
    "$ROOT/.venv/bin/pip" install --upgrade pip -q
    "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt" -q
    log_ok "Dependencias Python instaladas"
}

setup_node_env() {
    log_step "Configurando entorno Node.js (UI)..."
    
    if [ ! -d "$ROOT/ui/node_modules" ]; then
        (cd "$ROOT/ui" && npm install --silent)
        log_ok "Dependencias Node.js instaladas"
    else
        log_ok "Dependencias Node.js ya existen"
    fi
}

start_docker() {
    log_step "Iniciando servicios Docker..."
    
    # Verificar que Docker está corriendo
    if ! docker info &>/dev/null; then
        log_error "Docker no está corriendo. Inicia Docker primero."
        exit 1
    fi
    
    # Levantar servicios de infraestructura (Qdrant, Redis, Ollama)
    docker compose -f "$ROOT/docker/compose.infra.yml" up -d qdrant 2>/dev/null || true
    
    # Esperar Qdrant
    local retries=30
    while ! curl -s http://localhost:6333/healthz &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            log_error "Qdrant no respondió"
            exit 1
        fi
        sleep 1
    done
    log_ok "Qdrant listo (vectores)"
}

start_api() {
    log_step "Iniciando API..."
    
    # Limpiar proceso anterior
    pkill -f "uvicorn cortex_ka.api.main" 2>/dev/null || true
    sleep 1
    
    mkdir -p "$ROOT/logs"
    
    # Arrancar API
    nohup bash -c "
        cd '$ROOT'
        source .venv/bin/activate
        set -a; source .env; set +a
        export PYTHONPATH='$ROOT/src'
        exec python -m uvicorn cortex_ka.api.main:app --host 0.0.0.0 --port 8088
    " > "$ROOT/logs/api.log" 2>&1 &
    
    # Esperar API
    local retries=30
    while ! curl -s http://localhost:8088/health &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            log_error "API no respondió. Ver: logs/api.log"
            exit 1
        fi
        sleep 1
    done
    log_ok "API lista en http://localhost:8088"
}

start_ui() {
    log_step "Iniciando UI..."
    
    # Limpiar proceso anterior
    pkill -f "node.*vite" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    sleep 1
    
    mkdir -p "$ROOT/logs"
    
    # Arrancar UI
    nohup bash -c "
        cd '$ROOT/ui'
        exec npm run dev -- --host 0.0.0.0
    " > "$ROOT/logs/ui.log" 2>&1 &
    
    # Esperar UI
    sleep 3
    local retries=20
    while ! curl -s http://localhost:3000 &>/dev/null; do
        retries=$((retries - 1))
        if [ $retries -le 0 ]; then
            log_warn "UI puede tardar unos segundos más"
            break
        fi
        sleep 1
    done
    log_ok "UI lista en http://localhost:3000"
}

open_browser() {
    if [ "$HEADLESS" = true ]; then
        return
    fi
    
    local url="http://localhost:3000"
    
    # Detectar comando para abrir browser
    if command -v xdg-open &>/dev/null; then
        xdg-open "$url" 2>/dev/null &
    elif command -v open &>/dev/null; then
        open "$url" 2>/dev/null &
    elif command -v start &>/dev/null; then
        start "$url" 2>/dev/null &
    fi
}

print_success() {
    local is_first=$1
    
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}${BOLD}  ✓ CORTEX ESTÁ LISTO${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BOLD}Accede a Cortex:${NC}"
    echo -e "    → ${CYAN}http://localhost:3000${NC}"
    echo ""
    
    if [ "$is_first" = true ]; then
        echo -e "  ${YELLOW}⚡ PRIMER ARRANQUE DETECTADO${NC}"
        echo -e "  ${YELLOW}   Serás redirigido a crear tu usuario administrador.${NC}"
        echo ""
    fi
    
    echo -e "  ${BOLD}Para detener Cortex:${NC}"
    echo -e "    ./stop.sh"
    echo ""
    echo -e "  ${BOLD}Logs:${NC}"
    echo -e "    tail -f logs/api.log"
    echo -e "    tail -f logs/ui.log"
    echo ""
}

###############################################################################
# MAIN
###############################################################################

main() {
    print_banner
    
    # Determinar si es primer arranque
    local first_run=false
    if is_first_run || [ "$FORCE_SETUP" = true ]; then
        first_run=true
    fi
    
    if [ "$first_run" = true ]; then
        echo -e "  ${YELLOW}${BOLD}Primer arranque detectado. Iniciando configuración...${NC}"
        echo ""
    else
        echo -e "  ${GREEN}Iniciando Cortex...${NC}"
        echo ""
    fi
    
    check_dependencies
    
    if [ "$first_run" = true ]; then
        setup_first_run
    fi
    
    setup_python_env
    setup_node_env
    start_docker
    start_api
    start_ui
    
    print_success "$first_run"
    
    # Abrir navegador
    open_browser
}

main
