#!/usr/bin/env bash
# =============================================================================
# Voice-to-Notes — Database Backup Script
# =============================================================================
# This script creates hot backups of both SQLite databases using SQLite's
# built-in backup API. These backups are safe to run while the app is running.
#
# Usage: ./backup.sh
#
# Backups are stored in ~/voice-notes-data/backups/ (or custom DATA_DIR)
# Automatically keeps only the last 5 backups to prevent disk space issues.
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Determine data directory
if [ -f .env ] && grep -q "^DATA_DIR=" .env; then
    DATA_DIR=$(grep "^DATA_DIR=" .env | cut -d'=' -f2)
    # Expand tilde if present
    DATA_DIR="${DATA_DIR/#\~/$HOME}"
else
    DATA_DIR="$HOME/voice-notes-data"
fi

# Check if data directory exists
if [ ! -d "$DATA_DIR" ]; then
    echo -e "${RED}Error: Data directory not found: $DATA_DIR${NC}"
    echo "Run ./setup.sh first to initialize the data directory."
    exit 1
fi

# Create backup directory
BACKUP_DIR="$DATA_DIR/backups"
mkdir -p "$BACKUP_DIR"

# Timestamp for backup files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}Voice-to-Notes Database Backup${NC}"
echo "Data directory: $DATA_DIR"
echo "Backup directory: $BACKUP_DIR"
echo ""

# Backup main database
MAIN_DB="$DATA_DIR/voice_notes.db"
if [ -f "$MAIN_DB" ]; then
    BACKUP_FILE="$BACKUP_DIR/voice_notes_${TIMESTAMP}.db"
    echo -e "${YELLOW}Backing up voice_notes.db...${NC}"
    
    # Use SQLite's .backup command for hot backup
    sqlite3 "$MAIN_DB" ".backup '$BACKUP_FILE'"
    
    # Verify the backup is a valid SQLite database
    if sqlite3 "$BACKUP_FILE" "SELECT count(*) FROM recordings" > /dev/null 2>&1; then
        SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        echo -e "${GREEN}✓${NC} Created: voice_notes_${TIMESTAMP}.db (${SIZE})"
    else
        echo -e "${RED}✗${NC} Backup verification failed!"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠${NC}  voice_notes.db not found, skipping"
fi

# Backup registry database
REGISTRY_DB="$DATA_DIR/engine/registry.db"
if [ -f "$REGISTRY_DB" ]; then
    REGISTRY_BACKUP="$BACKUP_DIR/registry_${TIMESTAMP}.db"
    echo -e "${YELLOW}Backing up registry.db...${NC}"
    
    # Use SQLite's .backup command for hot backup
    sqlite3 "$REGISTRY_DB" ".backup '$REGISTRY_BACKUP'"
    
    # Verify the backup is a valid SQLite database
    if sqlite3 "$REGISTRY_BACKUP" "SELECT count(*) FROM processed_files" > /dev/null 2>&1; then
        SIZE=$(du -h "$REGISTRY_BACKUP" | cut -f1)
        echo -e "${GREEN}✓${NC} Created: registry_${TIMESTAMP}.db (${SIZE})"
    else
        echo -e "${RED}✗${NC} Backup verification failed!"
        rm -f "$REGISTRY_BACKUP"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠${NC}  registry.db not found, skipping"
fi

# Clean up old backups (keep last 5)
echo ""
echo -e "${YELLOW}Cleaning up old backups (keeping last 5)...${NC}"

cleanup_backups() {
    local pattern=$1
    local count=$(ls -1 "$BACKUP_DIR"/$pattern 2>/dev/null | wc -l)
    if [ "$count" -gt 5 ]; then
        local to_delete=$((count - 5))
        (cd "$BACKUP_DIR" && ls -1t "$pattern") | tail -n "$to_delete" | while read file; do
            rm -f "$BACKUP_DIR/$file"
            echo -e "${BLUE}  Deleted: $file${NC}"
        done
    fi
}

cleanup_backups "voice_notes_*.db"
cleanup_backups "registry_*.db"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                     Backup Complete!                             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Backups stored in: $BACKUP_DIR"
echo ""
echo -e "${BLUE}To restore a backup:${NC}"
echo "  1. Stop the application: docker-compose down"
echo "  2. Copy backup file: cp $BACKUP_DIR/voice_notes_TIMESTAMP.db $DATA_DIR/voice_notes.db"
echo "  3. Start the application: docker-compose up -d"
echo ""
