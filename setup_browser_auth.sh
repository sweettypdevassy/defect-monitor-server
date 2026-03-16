#!/bin/bash
# Setup Script for Browser Cookie Authentication
# This script helps set up Chrome with persistent profile for automatic cookie extraction

set -e

echo "============================================"
echo "Browser Cookie Authentication Setup"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${RED}❌ This script is designed for Linux systems${NC}"
    echo "For other systems, please follow the manual setup in PASSKEY_SOLUTION_BROWSER_COOKIES.md"
    exit 1
fi

echo -e "${BLUE}Step 1: Checking Chrome installation${NC}"
if command -v google-chrome &> /dev/null; then
    echo -e "${GREEN}✅ Chrome is installed${NC}"
    google-chrome --version
else
    echo -e "${YELLOW}⚠️  Chrome not found. Installing...${NC}"
    
    # Download and install Chrome
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb
    sudo dpkg -i /tmp/chrome.deb || sudo apt-get install -f -y
    rm /tmp/chrome.deb
    
    echo -e "${GREEN}✅ Chrome installed successfully${NC}"
fi

echo ""
echo -e "${BLUE}Step 2: Creating Chrome profile directory${NC}"
CHROME_PROFILE_DIR="$HOME/chrome-profile"
if [ -d "$CHROME_PROFILE_DIR" ]; then
    echo -e "${YELLOW}⚠️  Profile directory already exists: $CHROME_PROFILE_DIR${NC}"
else
    mkdir -p "$CHROME_PROFILE_DIR"
    echo -e "${GREEN}✅ Created profile directory: $CHROME_PROFILE_DIR${NC}"
fi

echo ""
echo -e "${BLUE}Step 3: Installing Python dependencies${NC}"
pip install browser-cookie3>=0.19.1
echo -e "${GREEN}✅ browser-cookie3 installed${NC}"

echo ""
echo -e "${BLUE}Step 4: Creating systemd service (optional)${NC}"
read -p "Do you want to create a systemd service to keep Chrome running? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/chrome-keepalive.service"
    
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Chrome Browser Keep-Alive for Cookie Authentication
After=network.target

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:99
ExecStart=/usr/bin/google-chrome --user-data-dir=$CHROME_PROFILE_DIR --no-first-run --no-default-browser-check --disable-gpu --headless=new
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable chrome-keepalive
    
    echo -e "${GREEN}✅ Systemd service created${NC}"
    echo -e "${YELLOW}Note: Service will start in headless mode. For initial login, start Chrome manually.${NC}"
fi

echo ""
echo -e "${BLUE}Step 5: Testing cookie extraction${NC}"
python3 << 'PYEOF'
try:
    import browser_cookie3
    print("✅ browser-cookie3 import successful")
    
    # Try to get cookies (will be empty if Chrome not logged in yet)
    cookies = list(browser_cookie3.chrome(domain_name='libh-proxy1.fyre.ibm.com'))
    print(f"📊 Found {len(cookies)} cookies for IBM domain")
    
    if len(cookies) == 0:
        print("⚠️  No cookies found yet - you need to login to IBM in Chrome first")
    else:
        print("✅ Cookies found! Authentication should work.")
        
except ImportError as e:
    print(f"❌ Failed to import browser-cookie3: {e}")
except Exception as e:
    print(f"⚠️  Error testing cookies: {e}")
PYEOF

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Start Chrome with persistent profile:"
echo -e "   ${BLUE}google-chrome --user-data-dir=$CHROME_PROFILE_DIR${NC}"
echo ""
echo "2. In Chrome:"
echo "   - Install 1Password extension (if using passkeys)"
echo "   - Navigate to: https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
echo "   - Complete passkey/MFA authentication"
echo "   - Verify you can see the page content"
echo ""
echo "3. Update config/config.yaml:"
echo "   - Set auth_method: \"browser_cookies\""
echo "   - Set use_browser_cookies: true"
echo ""
echo "4. Restart the defect monitor:"
echo -e "   ${BLUE}docker-compose restart${NC}"
echo ""
echo "5. Check logs for successful authentication:"
echo -e "   ${BLUE}docker-compose logs -f | grep -i 'browser\\|cookie\\|auth'${NC}"
echo ""
echo -e "${YELLOW}Troubleshooting:${NC}"
echo "- If cookies not found: Ensure Chrome is running with the correct profile"
echo "- If permission denied: Run script as the same user that runs Chrome"
echo "- For more help: See PASSKEY_SOLUTION_BROWSER_COOKIES.md"
echo ""

# Made with Bob