#!/bin/bash
# Start Chrome with remote debugging for cookie extraction

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🌐 Starting Chrome with Remote Debugging${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if Chrome is already running with remote debugging
if lsof -i :9222 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome is already running with remote debugging on port 9222${NC}"
    echo ""
    echo -e "${YELLOW}💡 You can now run:${NC}"
    echo -e "   ${GREEN}python3 use_existing_chrome.py${NC}"
    exit 0
fi

# Close any running Chrome instances
echo -e "${YELLOW}🔄 Closing any running Chrome instances...${NC}"
pkill -f chrome 2>/dev/null
sleep 2

# Start Chrome with remote debugging
echo -e "${BLUE}🚀 Starting Chrome with remote debugging...${NC}"
echo ""

# Use your existing Chrome profile
CHROME_PROFILE="$HOME/.config/google-chrome"

# Start Chrome
google-chrome \
    --remote-debugging-port=9222 \
    --user-data-dir="$CHROME_PROFILE" \
    "https://libh-proxy1.fyre.ibm.com/buildBreakReport/" \
    > /dev/null 2>&1 &

# Wait for Chrome to start
sleep 3

# Check if Chrome started successfully
if lsof -i :9222 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome started successfully with remote debugging!${NC}"
    echo ""
    echo -e "${YELLOW}📝 Next steps:${NC}"
    echo ""
    echo "1. Chrome window should be open with IBM site"
    echo "2. If not logged in, use 1Password to login"
    echo "3. Once logged in, run:"
    echo -e "   ${GREEN}python3 use_existing_chrome.py${NC}"
    echo ""
    echo -e "${YELLOW}💡 Keep this Chrome window open for automation to work${NC}"
else
    echo -e "${RED}❌ Failed to start Chrome with remote debugging${NC}"
    echo ""
    echo -e "${YELLOW}💡 Try manually:${NC}"
    echo "   google-chrome --remote-debugging-port=9222 &"
    exit 1
fi

# Made with Bob
