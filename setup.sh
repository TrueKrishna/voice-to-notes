#!/usr/bin/env bash
# =============================================================================
# Voice-to-Notes — First-Run Setup
# =============================================================================
# This script:
# 1. Creates the data directory structure
# 2. Copies .env.example to .env if needed
# 3. Prompts for required configuration
# 4. Explains where data lives and what's safe
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Voice-to-Notes — First-Run Setup                        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Determine data directory
if [ -f .env ] && grep -q "^DATA_DIR=" .env; then
    DATA_DIR=$(grep "^DATA_DIR=" .env | cut -d'=' -f2)
    # Expand tilde if present
    DATA_DIR="${DATA_DIR/#\~/$HOME}"
else
    DATA_DIR="$HOME/voice-notes-data"
fi

echo -e "${YELLOW}Step 1: Data Directory${NC}"
echo "Data will be stored in: ${GREEN}$DATA_DIR${NC}"
echo ""
read -p "Use this location? (Y/n): " confirm
if [[ "$confirm" =~ ^[Nn]$ ]]; then
    read -p "Enter custom path: " custom_path
    DATA_DIR="${custom_path/#\~/$HOME}"
fi

# Create directory structure
echo ""
echo -e "${YELLOW}Step 2: Creating Directory Structure${NC}"
mkdir -p "$DATA_DIR/engine/processing"
mkdir -p "$DATA_DIR/engine/failed"
mkdir -p "$DATA_DIR/uploads"
echo -e "${GREEN}✓${NC} Created data directories"

# Copy .env.example to .env if it doesn't exist
echo ""
echo -e "${YELLOW}Step 3: Environment Configuration${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✓${NC} Created .env from .env.example"
    
    # Update DATA_DIR in .env if custom path was chosen
    if [ "$DATA_DIR" != "$HOME/voice-notes-data" ]; then
        if grep -q "^# DATA_DIR=" .env; then
            # Use portable sed approach with temporary file
            sed "s|^# DATA_DIR=.*|DATA_DIR=$DATA_DIR|" .env > .env.tmp && mv .env.tmp .env
        else
            echo "DATA_DIR=$DATA_DIR" >> .env
        fi
        echo -e "${GREEN}✓${NC} Set DATA_DIR in .env"
    fi
else
    echo -e "${BLUE}ℹ${NC}  .env already exists, skipping"
fi

# Prompt for required configuration
echo ""
echo -e "${YELLOW}Step 4: Required Configuration${NC}"
echo ""
echo "Please edit .env and configure the following:"
echo ""
echo "1. ${BLUE}GDRIVE_MOUNT_PATH${NC} - Path to your Google Drive folder"
echo "   Example: /Users/yourname/Google Drive"
echo ""
echo "2. ${BLUE}GEMINI_API_KEYS${NC} - Your Gemini API keys (comma-separated)"
echo "   Get keys from: https://aistudio.google.com/apikey"
echo ""

read -p "Press Enter to open .env in your default editor..." 
${EDITOR:-nano} .env

# Summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                        Setup Complete!                           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Data Location:${NC}"
echo "  All your voice notes data will be stored in:"
echo "  ${GREEN}$DATA_DIR${NC}"
echo ""
echo -e "${BLUE}What's Safe:${NC}"
echo "  ${GREEN}✓${NC} docker-compose down"
echo "  ${GREEN}✓${NC} docker-compose down -v (only removes named volumes, you have none)"
echo "  ${GREEN}✓${NC} docker system prune"
echo "  ${GREEN}✓${NC} rm -rf voice-to-notes (deleting project folder)"
echo "  ${GREEN}✓${NC} git clean -fdx"
echo "  ${GREEN}✓${NC} switching branches, re-cloning repo"
echo ""
echo -e "${RED}What's NOT Safe:${NC}"
echo "  ${RED}✗${NC} rm -rf $DATA_DIR"
echo "  ${RED}✗${NC} Deleting the data directory manually"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Review and complete configuration in .env"
echo "  2. Start the application: ${GREEN}docker-compose up -d${NC}"
echo "  3. Open in browser: ${GREEN}http://localhost:9123${NC}"
echo "  4. Run backups regularly: ${GREEN}./backup.sh${NC}"
echo ""
