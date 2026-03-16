#!/bin/bash
# Quick setup for 2-hour automatic cookie refresh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}⏰ Setting up 2-hour Cookie Refresh${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define cron command
CRON_CMD="0 */2 * * * cd $SCRIPT_DIR && ./refresh_cookies_auto.sh >> logs/cookie_refresh.log 2>&1"

echo -e "${BLUE}This will set up automatic cookie refresh every 2 hours${NC}"
echo ""
echo "Cron job to be added:"
echo -e "${YELLOW}$CRON_CMD${NC}"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "refresh_cookies_auto.sh"; then
    echo -e "${YELLOW}⚠️  Existing cron job found${NC}"
    echo ""
    read -p "Update to 2-hour interval? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove old cron job and add new one
        (crontab -l 2>/dev/null | grep -v "refresh_cookies_auto.sh"; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}✅ Cron job updated to 2-hour interval!${NC}"
    else
        echo -e "${YELLOW}Keeping existing cron job${NC}"
        exit 0
    fi
else
    read -p "Add cron job? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Add cron job
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}✅ Cron job added successfully!${NC}"
    else
        echo -e "${YELLOW}Cron job not added${NC}"
        exit 0
    fi
fi

echo ""
echo -e "${GREEN}Current crontab:${NC}"
crontab -l | grep "refresh_cookies_auto.sh" || echo "No cookie refresh jobs found"

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}📝 What happens now:${NC}"
echo ""
echo "1. Cookies will be refreshed automatically every 2 hours"
echo "2. First refresh will occur at the next even hour (e.g., 12:00, 14:00, 16:00)"
echo "3. All refresh attempts are logged to: logs/cookie_refresh.log"
echo ""
echo -e "${YELLOW}💡 Useful commands:${NC}"
echo ""
echo "View cron jobs:"
echo -e "  ${GREEN}crontab -l${NC}"
echo ""
echo "Check refresh logs:"
echo -e "  ${GREEN}tail -f logs/cookie_refresh.log${NC}"
echo ""
echo "Manual refresh:"
echo -e "  ${GREEN}./refresh_cookies_auto.sh${NC}"
echo ""
echo "Remove cron job:"
echo -e "  ${GREEN}crontab -e${NC} (then delete the line)"
echo ""

# Made with Bob
