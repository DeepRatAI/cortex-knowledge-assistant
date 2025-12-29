#!/bin/bash
# =============================================================================
# Cortex Backup Script
# Creates timestamped backups of PostgreSQL and Qdrant data
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Container names (from docker-compose.yml)
POSTGRES_CONTAINER="cortex_postgres"
QDRANT_CONTAINER="cortex_qdrant"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Pre-flight checks
# =============================================================================

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running"
        exit 1
    fi
    
    # Check containers are running
    if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        log_error "PostgreSQL container '${POSTGRES_CONTAINER}' is not running"
        exit 1
    fi
    
    if ! docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
        log_warn "Qdrant container '${QDRANT_CONTAINER}' is not running - skipping Qdrant backup"
        SKIP_QDRANT=true
    else
        SKIP_QDRANT=false
    fi
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    log_info "Backup directory: $BACKUP_DIR"
}

# =============================================================================
# PostgreSQL Backup
# =============================================================================

backup_postgres() {
    POSTGRES_BACKUP_FILE="$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"
    
    log_info "Backing up PostgreSQL database..."
    
    # Use pg_dump with compression
    if docker exec "$POSTGRES_CONTAINER" pg_dump -U cortex cortex 2>/dev/null | gzip > "$POSTGRES_BACKUP_FILE"; then
        if [ -s "$POSTGRES_BACKUP_FILE" ]; then
            local size=$(du -h "$POSTGRES_BACKUP_FILE" | cut -f1)
            log_info "PostgreSQL backup complete: $POSTGRES_BACKUP_FILE ($size)"
            return 0
        else
            log_error "PostgreSQL backup created empty file"
            rm -f "$POSTGRES_BACKUP_FILE"
            POSTGRES_BACKUP_FILE=""
            return 1
        fi
    else
        log_error "PostgreSQL backup failed"
        rm -f "$POSTGRES_BACKUP_FILE"
        POSTGRES_BACKUP_FILE=""
        return 1
    fi
}

# =============================================================================
# Qdrant Backup (Snapshot)
# =============================================================================

backup_qdrant() {
    QDRANT_BACKUP_FILE=""
    
    if [ "$SKIP_QDRANT" = true ]; then
        log_warn "Skipping Qdrant backup (container not running)"
        return 0
    fi
    
    QDRANT_BACKUP_FILE="$BACKUP_DIR/qdrant_${TIMESTAMP}.snapshot"
    local collection_name="corporate_docs"
    
    log_info "Creating Qdrant snapshot for collection '$collection_name'..."
    
    # Create snapshot via Qdrant API (using cortex_api container which has curl)
    local snapshot_response
    snapshot_response=$(docker exec cortex_api curl -s -X POST "http://qdrant:6333/collections/${collection_name}/snapshots" 2>/dev/null)
    
    if echo "$snapshot_response" | grep -q '"status":"ok"'; then
        local snapshot_name
        snapshot_name=$(echo "$snapshot_response" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
        
        log_info "Snapshot created: $snapshot_name"
        
        # Copy snapshot file from Qdrant container's storage
        # Qdrant stores snapshots at /qdrant/snapshots/<collection>/<snapshot_name>
        local qdrant_snapshot_path="/qdrant/snapshots/${collection_name}/${snapshot_name}"
        
        if docker cp "${QDRANT_CONTAINER}:${qdrant_snapshot_path}" "$QDRANT_BACKUP_FILE" 2>/dev/null; then
            if [ -s "$QDRANT_BACKUP_FILE" ]; then
                local size=$(du -h "$QDRANT_BACKUP_FILE" | cut -f1)
                log_info "Qdrant backup complete: $QDRANT_BACKUP_FILE ($size)"
                
                # Clean up snapshot in Qdrant (using API via cortex_api)
                docker exec cortex_api curl -s -X DELETE \
                    "http://qdrant:6333/collections/${collection_name}/snapshots/${snapshot_name}" >/dev/null 2>&1
                return 0
            fi
        fi
        
        log_error "Failed to copy Qdrant snapshot from container"
        rm -f "$QDRANT_BACKUP_FILE"
        QDRANT_BACKUP_FILE=""
        return 1
    else
        log_error "Failed to create Qdrant snapshot: $snapshot_response"
        QDRANT_BACKUP_FILE=""
        return 1
    fi
}

# =============================================================================
# Cleanup old backups
# =============================================================================

cleanup_old_backups() {
    log_info "Cleaning up backups older than ${RETENTION_DAYS} days..."
    
    local count
    count=$(find "$BACKUP_DIR" -name "*.sql.gz" -o -name "*.tar.gz" -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)
    
    if [ "$count" -gt 0 ]; then
        find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
        find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
        log_info "Removed $count old backup(s)"
    else
        log_info "No old backups to clean up"
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo "=============================================="
    echo "  Cortex Backup - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=============================================="
    
    check_prerequisites
    
    POSTGRES_BACKUP_FILE=""
    QDRANT_BACKUP_FILE=""
    local errors=0
    
    # Backup PostgreSQL
    if ! backup_postgres; then
        errors=$((errors + 1))
    fi
    
    # Backup Qdrant
    if ! backup_qdrant; then
        errors=$((errors + 1))
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    echo ""
    echo "=============================================="
    echo "  Backup Summary"
    echo "=============================================="
    
    if [ -n "$POSTGRES_BACKUP_FILE" ] && [ -f "$POSTGRES_BACKUP_FILE" ]; then
        log_info "PostgreSQL: $(basename "$POSTGRES_BACKUP_FILE")"
    else
        log_error "PostgreSQL: FAILED"
    fi
    
    if [ -n "$QDRANT_BACKUP_FILE" ] && [ -f "$QDRANT_BACKUP_FILE" ]; then
        log_info "Qdrant: $(basename "$QDRANT_BACKUP_FILE")"
    elif [ "$SKIP_QDRANT" = true ]; then
        log_warn "Qdrant: SKIPPED"
    else
        log_error "Qdrant: FAILED"
    fi
    
    if [ $errors -gt 0 ]; then
        log_error "Backup completed with $errors error(s)"
        exit 1
    else
        log_info "Backup completed successfully!"
        exit 0
    fi
}

main "$@"
