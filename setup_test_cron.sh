#!/bin/bash
# Test setup for 5-minute automatic cookie refresh
# Use this for testing, then switch to setup_2hour_cron.sh for production

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🧪 Setting up TEST 5-minute Cookie Refresh${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define cron command for 5-minute testing
CRON_CMD="*/3 * * * * cd $SCRIPT_DIR && ./refresh_cookies_auto.sh >> logs/cookie_refresh.log 2>&1"

echo -e "${YELLOW}⚠️  WARNING: This is for TESTING only!${NC}"
echo -e "${YELLOW}This will refresh cookies every 5 minutes${NC}"
echo ""
echo "Cron job to be added:"
echo -e "${YELLOW}$CRON_CMD${NC}"
echo ""
echo -e "${RED}Remember to switch to 2-hour interval for production!${NC}"
echo -e "${GREEN}Use: ./setup_2hour_cron.sh${NC}"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "refresh_cookies_auto.sh"; then
    echo -e "${YELLOW}⚠️  Existing cron job found${NC}"
    echo ""
    read -p "Replace with 5-minute test interval? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove old cron job and add new one
        (crontab -l 2>/dev/null | grep -v "refresh_cookies_auto.sh"; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}✅ Cron job updated to 5-minute test interval!${NC}"
    else
        echo -e "${YELLOW}Keeping existing cron job${NC}"
        exit 0
    fi
else
    read -p "Add 5-minute test cron job? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Add cron job
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}✅ Test cron job added successfully!${NC}"
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
echo -e "${GREEN}✅ Test Setup Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}📝 What happens now:${NC}"
echo ""
echo "1. Cookies will be refreshed automatically every 5 minutes"
echo "2. First refresh will occur within 5 minutes"
echo "3. All refresh attempts are logged to: logs/cookie_refresh.log"
echo ""
echo -e "${YELLOW}💡 Monitor the test:${NC}"
echo ""
echo "Watch logs in real-time:"
echo -e "  ${GREEN}tail -f logs/cookie_refresh.log${NC}"
echo ""
echo "Check config updates:"
echo -e "  ${GREEN}watch -n 10 'ls -lt config/config.yaml.backup.* | head -3'${NC}"
echo ""
echo "View current cookies:"
echo -e "  ${GREEN}grep -A 2 'cookies:' config/config.yaml${NC}"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Switch to production interval after testing!${NC}"
echo -e "${GREEN}Run: ./setup_2hour_cron.sh${NC}"
echo ""

# Made with Bob
