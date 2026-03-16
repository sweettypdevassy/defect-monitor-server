#!/bin/bash
# Automated Cookie Refresh Script with Scheduling
# Automatically refreshes cookies from Chrome and updates config.yaml

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔄 Automated Cookie Refresh${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python script exists
if [ ! -f "auto_update_cookies.py" ]; then
    echo -e "${RED}❌ Error: auto_update_cookies.py not found${NC}"
    exit 1
fi

# Make Python script executable
chmod +x auto_update_cookies.py

# Run the cookie update script
echo -e "${BLUE}Running cookie extraction and update...${NC}"
echo ""

if python3 auto_update_cookies.py; then
    echo ""
    echo -e "${GREEN}✅ Cookies refreshed successfully!${NC}"
    
    # Check if running in Docker
    if [ -f "docker-compose.yml" ]; then
        echo ""
        echo -e "${YELLOW}🐳 Detected Docker setup${NC}"
        echo -e "${YELLOW}Restarting Docker containers...${NC}"
        
        if docker-compose restart; then
            echo -e "${GREEN}✅ Docker containers restarted${NC}"
        else
            echo -e "${YELLOW}⚠️  Failed to restart Docker containers${NC}"
            echo -e "${YELLOW}Please restart manually: docker-compose restart${NC}"
        fi
    fi
    
    # Log the refresh
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Cookies refreshed successfully" >> logs/cookie_refresh.log
    
    exit 0
else
    echo ""
    echo -e "${RED}❌ Failed to refresh cookies${NC}"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Cookie refresh failed" >> logs/cookie_refresh.log
    exit 1
fi

# Made with Bob
