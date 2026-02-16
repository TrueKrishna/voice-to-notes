#!/usr/bin/env bash
# =============================================================================
# Voice-to-Notes — Container Entrypoint
# =============================================================================
# This script:
# 1. Validates that /app/data is properly mounted (warns if not)
# 2. Ensures required subdirectories exist
# 3. Executes the original command (uvicorn or python run_watcher.py)
# =============================================================================

set -e

# ANSI color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# ============================================================================
# STEP 1: Check if /app/data is mounted
# ============================================================================
# If /app/data is on a different device/filesystem than /app, it's mounted.
# This prevents data loss from being stored only in the container layer.

APP_DEV=$(stat -c '%d' /app 2>/dev/null || stat -f '%d' /app 2>/dev/null)
DATA_DEV=$(stat -c '%d' /app/data 2>/dev/null || stat -f '%d' /app/data 2>/dev/null)

if [ "$APP_DEV" = "$DATA_DEV" ]; then
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                           ⚠️  WARNING  ⚠️                                ║${NC}"
    echo -e "${RED}╠════════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║  /app/data is NOT mounted as a volume!                                 ║${NC}"
    echo -e "${RED}║                                                                        ║${NC}"
    echo -e "${RED}║  Your data will be LOST when the container is removed.                ║${NC}"
    echo -e "${RED}║                                                                        ║${NC}"
    echo -e "${RED}║  To fix this, ensure docker-compose.yml has:                          ║${NC}"
    echo -e "${RED}║    volumes:                                                            ║${NC}"
    echo -e "${RED}║      - \${DATA_DIR:-~/voice-notes-data}:/app/data                       ║${NC}"
    echo -e "${RED}║                                                                        ║${NC}"
    echo -e "${RED}║  Starting anyway (for development/testing purposes)...                ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    sleep 3
else
    echo -e "${GREEN}✓${NC} /app/data is properly mounted as a volume"
fi

# ============================================================================
# STEP 2: Ensure subdirectories exist
# ============================================================================
echo "Ensuring data subdirectories exist..."
mkdir -p /app/data/engine/processing
mkdir -p /app/data/engine/failed
mkdir -p /app/data/uploads
echo -e "${GREEN}✓${NC} Data directory structure ready"

# ============================================================================
# STEP 3: Execute the original command
# ============================================================================
echo "Starting application: $@"
echo ""
exec "$@"
