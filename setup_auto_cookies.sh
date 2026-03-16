#!/bin/bash
# Setup Script for Automatic Cookie Updates
# Installs dependencies and configures automatic cookie refresh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔧 Auto Cookie Update Setup${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if running on macOS or Linux
OS="$(uname -s)"
echo -e "${BLUE}Detected OS: $OS${NC}"
echo ""

# Step 1: Install browser-cookie3
echo -e "${GREEN}Step 1: Installing dependencies...${NC}"
echo ""

if python3 -c "import browser_cookie3" 2>/dev/null; then
    echo -e "${GREEN}✅ browser-cookie3 already installed${NC}"
else
    echo -e "${YELLOW}Installing browser-cookie3...${NC}"
    pip3 install browser-cookie3
    echo -e "${GREEN}✅ browser-cookie3 installed${NC}"
fi

if python3 -c "import yaml" 2>/dev/null; then
    echo -e "${GREEN}✅ PyYAML already installed${NC}"
else
    echo -e "${YELLOW}Installing PyYAML...${NC}"
    pip3 install PyYAML
    echo -e "${GREEN}✅ PyYAML installed${NC}"
fi

echo ""

# Step 2: Make scripts executable
echo -e "${GREEN}Step 2: Making scripts executable...${NC}"
chmod +x auto_update_cookies.py
chmod +x refresh_cookies_auto.sh
echo -e "${GREEN}✅ Scripts are now executable${NC}"
echo ""

# Step 3: Create logs directory
echo -e "${GREEN}Step 3: Creating logs directory...${NC}"
mkdir -p logs
echo -e "${GREEN}✅ Logs directory created${NC}"
echo ""

# Step 4: Test cookie extraction
echo -e "${GREEN}Step 4: Testing cookie extraction...${NC}"
echo ""
echo -e "${YELLOW}⚠️  Please ensure:${NC}"
echo "   1. Chrome is running"
echo "   2. You are logged in to: https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
echo ""
read -p "Press Enter to test cookie extraction..."
echo ""

if python3 extract_cookies_simple.py; then
    echo ""
    echo -e "${GREEN}✅ Cookie extraction test successful!${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠️  Cookie extraction test failed${NC}"
    echo -e "${YELLOW}Please ensure Chrome is running and you're logged in${NC}"
fi

echo ""

# Step 5: Offer to set up cron job
echo -e "${GREEN}Step 5: Cron job setup (optional)${NC}"
echo ""
echo "Would you like to set up automatic cookie refresh?"
echo "This will refresh cookies every 2 hours."
echo ""
read -p "Set up cron job? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    CRON_CMD="0 */2 * * * cd $SCRIPT_DIR && ./refresh_cookies_auto.sh >> logs/cookie_refresh.log 2>&1"
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "refresh_cookies_auto.sh"; then
        echo -e "${YELLOW}⚠️  Cron job already exists${NC}"
        echo ""
        echo "Updating to 2-hour interval..."
        # Remove old cron job and add new one
        (crontab -l 2>/dev/null | grep -v "refresh_cookies_auto.sh"; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}✅ Cron job updated successfully!${NC}"
    else
        # Add cron job
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}✅ Cron job added successfully!${NC}"
    fi
    echo ""
    echo "Cron job will run every 2 hours:"
    echo "$CRON_CMD"
else
    echo -e "${YELLOW}Skipping cron job setup${NC}"
    echo ""
    echo "To set up manually later, add this to your crontab:"
    echo "  crontab -e"
    echo ""
    echo "Then add:"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo "  0 */2 * * * cd $SCRIPT_DIR && ./refresh_cookies_auto.sh >> logs/cookie_refresh.log 2>&1"
fi

echo ""

# Step 6: Summary
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo ""
echo "1. Ensure Chrome is running and logged in to IBM"
echo ""
echo "2. Run the cookie updater manually:"
echo -e "   ${GREEN}./auto_update_cookies.py${NC}"
echo ""
echo "3. Or use the wrapper script:"
echo -e "   ${GREEN}./refresh_cookies_auto.sh${NC}"
echo ""
echo "4. Check the guide for more details:"
echo -e "   ${GREEN}cat AUTO_COOKIE_UPDATE_GUIDE.md${NC}"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo "   - Cookies typically last 8-12 hours"
echo "   - The cron job will refresh them automatically"
echo "   - Check logs: tail -f logs/cookie_refresh.log"
echo ""

# Made with Bob
