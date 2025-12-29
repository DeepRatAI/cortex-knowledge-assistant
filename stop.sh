#!/usr/bin/env bash
###############################################################################
# stop.sh — Detiene Cortex Knowledge Assistant
#
# Uso:
#   ./stop.sh           # Detiene API y UI
#   ./stop.sh --all     # También detiene Docker
###############################################################################

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT="$(cd "$(dirname "$0")" && pwd)"

STOP_DOCKER=false
[[ "${1:-}" == "--all" ]] && STOP_DOCKER=true

echo ""
echo -e "${YELLOW}Deteniendo Cortex...${NC}"
echo ""

# Detener API
if pkill -f "uvicorn cortex_ka.api.main" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} API detenida"
else
    echo -e "  ${YELLOW}○${NC} API no estaba corriendo"
fi

# Detener UI
if pkill -f "node.*vite" 2>/dev/null || pkill -f "npm run dev" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} UI detenida"
else
    echo -e "  ${YELLOW}○${NC} UI no estaba corriendo"
fi

# Detener Docker si se pidió
if [ "$STOP_DOCKER" = true ]; then
    echo ""
    echo -e "  Deteniendo servicios Docker..."
    docker compose -f "$ROOT/docker/compose.infra.yml" down 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Docker detenido"
fi

echo ""
echo -e "${GREEN}Cortex detenido.${NC}"
echo ""
