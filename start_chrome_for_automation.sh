#!/bin/bash
# Start Chrome with remote debugging for cookie automation

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🌐 Starting Chrome for Cookie Automation${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if Chrome is already running with remote debugging
if lsof -i :9222 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome is already running with remote debugging on port 9222${NC}"
    echo ""
    echo -e "${YELLOW}💡 You can now run:${NC}"
    echo -e "   ${GREEN}./auto_refresh_and_update_cookies.py${NC}"
    exit 0
fi

# Determine Chrome path based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    USER_DATA_DIR="$HOME/Library/Application Support/Google/Chrome"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CHROME_PATH="google-chrome"
    USER_DATA_DIR="$HOME/.config/google-chrome"
else
    echo -e "${RED}❌ Unsupported OS${NC}"
    exit 1
fi

echo -e "${BLUE}Starting Chrome with remote debugging...${NC}"
echo ""
echo -e "${YELLOW}Chrome will open with:${NC}"
echo "  - Remote debugging on port 9222"
echo "  - Your existing profile and cookies"
echo "  - IBM page: https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
echo ""

# Start Chrome with remote debugging
if [[ "$OSTYPE" == "darwin"* ]]; then
    "$CHROME_PATH" \
        --remote-debugging-port=9222 \
        --user-data-dir="$USER_DATA_DIR" \
        "https://libh-proxy1.fyre.ibm.com/buildBreakReport/" \
        > /dev/null 2>&1 &
else
    $CHROME_PATH \
        --remote-debugging-port=9222 \
        --user-data-dir="$USER_DATA_DIR" \
        "https://libh-proxy1.fyre.ibm.com/buildBreakReport/" \
        > /dev/null 2>&1 &
fi

# Wait for Chrome to start
sleep 3

# Check if Chrome started successfully
if lsof -i :9222 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Chrome started successfully!${NC}"
    echo ""
    echo -e "${YELLOW}📝 Next steps:${NC}"
    echo ""
    echo "1. Log in to IBM in the Chrome window that just opened"
    echo ""
    echo "2. Once logged in, run the auto-refresh script:"
    echo -e "   ${GREEN}./auto_refresh_and_update_cookies.py${NC}"
    echo ""
    echo "3. Or set up automatic refresh:"
    echo -e "   ${GREEN}./setup_2hour_cron.sh${NC}"
    echo ""
    echo -e "${YELLOW}💡 Keep this Chrome window open for automation to work${NC}"
else
    echo -e "${RED}❌ Failed to start Chrome${NC}"
    exit 1
fi

# Made with Bob
