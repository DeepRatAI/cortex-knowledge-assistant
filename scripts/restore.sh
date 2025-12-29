#!/bin/bash
# =============================================================================
# Cortex Restore Script
# Restores PostgreSQL and/or Qdrant from backup files
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"

# Container names
POSTGRES_CONTAINER="cortex_postgres"
QDRANT_CONTAINER="cortex_qdrant"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Usage
# =============================================================================

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Restore Cortex data from backup files.

Options:
    --postgres FILE     Restore PostgreSQL from specified .sql.gz file
    --qdrant FILE       Restore Qdrant from specified .snapshot.tar.gz file
    --list              List available backups
    --latest            Restore from the most recent backup
    -h, --help          Show this help message

Examples:
    $(basename "$0") --list
    $(basename "$0") --latest
    $(basename "$0") --postgres backups/postgres_20241218_120000.sql.gz
    $(basename "$0") --qdrant backups/qdrant_20241218_120000.snapshot.tar.gz

EOF
    exit 0
}

# =============================================================================
# List backups
# =============================================================================

list_backups() {
    echo "Available PostgreSQL backups:"
    echo "-----------------------------"
    if ls -1t "$BACKUP_DIR"/postgres_*.sql.gz 2>/dev/null; then
        :
    else
        echo "  (none)"
    fi
    
    echo ""
    echo "Available Qdrant backups:"
    echo "-------------------------"
    if ls -1t "$BACKUP_DIR"/qdrant_*.snapshot.tar.gz 2>/dev/null; then
        :
    else
        echo "  (none)"
    fi
}

# =============================================================================
# Find latest backups
# =============================================================================

find_latest_postgres() {
    ls -1t "$BACKUP_DIR"/postgres_*.sql.gz 2>/dev/null | head -1
}

find_latest_qdrant() {
    ls -1t "$BACKUP_DIR"/qdrant_*.snapshot.tar.gz 2>/dev/null | head -1
}

# =============================================================================
# Restore PostgreSQL
# =============================================================================

restore_postgres() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    log_info "Restoring PostgreSQL from: $backup_file"
    
    # Check container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        log_error "PostgreSQL container is not running"
        return 1
    fi
    
    # Warning
    log_warn "This will DROP and recreate all tables. Existing data will be lost!"
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        return 0
    fi
    
    # Drop existing tables and restore
    log_info "Dropping existing tables..."
    docker exec "$POSTGRES_CONTAINER" psql -U cortex -d cortex -c "
        DROP TABLE IF EXISTS audit_logs CASCADE;
        DROP TABLE IF EXISTS subject_services CASCADE;
        DROP TABLE IF EXISTS user_subjects CASCADE;
        DROP TABLE IF EXISTS subjects CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
    " >/dev/null
    
    log_info "Restoring data..."
    if gunzip -c "$backup_file" | docker exec -i "$POSTGRES_CONTAINER" psql -U cortex -d cortex >/dev/null 2>&1; then
        log_info "PostgreSQL restore complete!"
        
        # Show counts
        docker exec "$POSTGRES_CONTAINER" psql -U cortex -d cortex -c "
            SELECT 'users' as table_name, COUNT(*) as count FROM users
            UNION ALL SELECT 'subjects', COUNT(*) FROM subjects
            UNION ALL SELECT 'user_subjects', COUNT(*) FROM user_subjects
            UNION ALL SELECT 'subject_services', COUNT(*) FROM subject_services
            UNION ALL SELECT 'audit_logs', COUNT(*) FROM audit_logs;
        "
    else
        log_error "PostgreSQL restore failed"
        return 1
    fi
}

# =============================================================================
# Restore Qdrant
# =============================================================================

restore_qdrant() {
    local backup_file="$1"
    local collection_name="corporate_docs"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    log_info "Restoring Qdrant collection '$collection_name' from: $backup_file"
    
    # Check containers are running
    if ! docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
        log_error "Qdrant container is not running"
        return 1
    fi
    
    if ! docker ps --format '{{.Names}}' | grep -q "^cortex_api$"; then
        log_error "Cortex API container is not running (needed for restore)"
        return 1
    fi
    
    # Warning
    log_warn "This will replace the existing collection. Current data will be lost!"
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        return 0
    fi
    
    # Copy snapshot to Qdrant container
    log_info "Copying snapshot to Qdrant container..."
    local snapshot_filename=$(basename "$backup_file")
    
    docker cp "$backup_file" "${QDRANT_CONTAINER}:/qdrant/snapshots/${snapshot_filename}" 2>/dev/null
    
    # Restore using Qdrant API via cortex_api container
    log_info "Restoring from snapshot..."
    
    local response
    response=$(docker exec cortex_api curl -s -X PUT \
        "http://qdrant:6333/collections/${collection_name}/snapshots/recover" \
        -H "Content-Type: application/json" \
        -d "{\"location\": \"/qdrant/snapshots/${snapshot_filename}\"}")
    
    if echo "$response" | grep -q '"status":"ok"'; then
        log_info "Qdrant restore complete!"
        
        # Show document count
        local count
        count=$(docker exec cortex_api curl -s "http://qdrant:6333/collections/${collection_name}" | grep -o '"points_count":[0-9]*' | cut -d: -f2)
        log_info "Documents in collection: $count"
        
        # Cleanup temporary snapshot
        docker exec "$QDRANT_CONTAINER" rm -f "/qdrant/snapshots/${snapshot_filename}" 2>/dev/null || true
    else
        log_error "Qdrant restore failed: $response"
        return 1
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    local postgres_file=""
    local qdrant_file=""
    local do_latest=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --postgres)
                postgres_file="$2"
                shift 2
                ;;
            --qdrant)
                qdrant_file="$2"
                shift 2
                ;;
            --list)
                list_backups
                exit 0
                ;;
            --latest)
                do_latest=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done
    
    # Handle --latest
    if [ "$do_latest" = true ]; then
        postgres_file=$(find_latest_postgres)
        qdrant_file=$(find_latest_qdrant)
        
        if [ -z "$postgres_file" ] && [ -z "$qdrant_file" ]; then
            log_error "No backup files found in $BACKUP_DIR"
            exit 1
        fi
    fi
    
    # Check if anything to restore
    if [ -z "$postgres_file" ] && [ -z "$qdrant_file" ]; then
        log_error "No backup files specified. Use --help for usage."
        exit 1
    fi
    
    echo "=============================================="
    echo "  Cortex Restore - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=============================================="
    
    # Restore PostgreSQL
    if [ -n "$postgres_file" ]; then
        restore_postgres "$postgres_file"
    fi
    
    # Restore Qdrant
    if [ -n "$qdrant_file" ]; then
        restore_qdrant "$qdrant_file"
    fi
    
    log_info "Restore process complete!"
}

main "$@"
