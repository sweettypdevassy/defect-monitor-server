#!/bin/bash
# Automated Cookie Extraction and Config Update Script
# Extracts cookies from Chrome and updates config.yaml automatically

set -e

echo "============================================"
echo "🍪 IBM Cookie Auto-Updater"
echo "============================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if config file exists
CONFIG_FILE="config/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Error: $CONFIG_FILE not found${NC}"
    exit 1
fi

# Check if browser-cookie3 is installed
if ! python3 -c "import browser_cookie3" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  browser-cookie3 not installed${NC}"
    echo "Installing..."
    pip3 install browser-cookie3
fi

echo -e "${GREEN}Step 1: Extracting cookies from Chrome...${NC}"
echo ""

# Extract cookies using Python
COOKIE_OUTPUT=$(python3 << 'PYEOF'
import browser_cookie3
import sys

try:
    # Get cookies
    cookies = list(browser_cookie3.chrome(domain_name='libh-proxy1.fyre.ibm.com'))
    
    if not cookies:
        print("ERROR:No cookies found")
        sys.exit(1)
    
    # Find required cookies
    ltpa_token = None
    session_id = None
    
    for cookie in cookies:
        if cookie.name == 'LtpaToken2':
            ltpa_token = cookie.value
        elif cookie.name == 'mod_auth_openidc_session':
            session_id = cookie.value
    
    if not ltpa_token or not session_id:
        print("ERROR:Missing required cookies")
        sys.exit(1)
    
    # Output in format: LTPA_TOKEN|SESSION_ID
    print(f"{ltpa_token}|{session_id}")
    
except Exception as e:
    print(f"ERROR:{e}")
    sys.exit(1)
PYEOF
)

# Check if extraction was successful
if [[ $COOKIE_OUTPUT == ERROR:* ]]; then
    ERROR_MSG="${COOKIE_OUTPUT#ERROR:}"
    echo -e "${RED}❌ Failed to extract cookies: $ERROR_MSG${NC}"
    echo ""
    echo -e "${YELLOW}💡 Please ensure:${NC}"
    echo "   1. Chrome is running"
    echo "   2. You are logged in to: https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
    echo "   3. The page has fully loaded"
    exit 1
fi

# Split the output
IFS='|' read -r LTPA_TOKEN SESSION_ID <<< "$COOKIE_OUTPUT"

echo -e "${GREEN}✅ Cookies extracted successfully${NC}"
echo "   - LtpaToken2: ${LTPA_TOKEN:0:50}..."
echo "   - mod_auth_openidc_session: $SESSION_ID"
echo ""

echo -e "${GREEN}Step 2: Backing up config file...${NC}"
BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
echo ""

echo -e "${GREEN}Step 3: Updating config.yaml...${NC}"

# Update config.yaml using Python
python3 << PYEOF
import yaml
import sys

config_file = "$CONFIG_FILE"

try:
    # Load config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Update cookies
    if 'ibm' not in config:
        config['ibm'] = {}
    
    config['ibm']['auth_method'] = 'cookies'
    
    if 'cookies' not in config['ibm']:
        config['ibm']['cookies'] = {}
    
    config['ibm']['cookies']['LtpaToken2'] = "$LTPA_TOKEN"
    config['ibm']['cookies']['mod_auth_openidc_session'] = "$SESSION_ID"
    
    # Write back
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print("✅ Config updated successfully")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}✅ Cookies updated successfully!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo -e "${YELLOW}📝 Next steps:${NC}"
    echo ""
    echo "1. Restart your application:"
    echo -e "   ${GREEN}docker-compose restart${NC}"
    echo ""
    echo "2. Check logs for successful authentication:"
    echo -e "   ${GREEN}docker-compose logs -f | grep -i auth${NC}"
    echo ""
    echo "3. Look for this message:"
    echo "   ✅ Cookie-based authentication successful"
    echo ""
    echo -e "${YELLOW}💡 Tip:${NC} Cookies typically last 8-12 hours"
    echo "   Run this script again when they expire"
    echo ""
else
    echo -e "${RED}❌ Failed to update config${NC}"
    echo "Restoring backup..."
    cp "$BACKUP_FILE" "$CONFIG_FILE"
    exit 1
fi

# Made with Bob