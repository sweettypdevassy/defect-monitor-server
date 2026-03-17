#!/usr/bin/env python3
"""
Playwright-based Cookie Extractor for IBM Site
Handles passkey authentication and extracts cookies automatically
"""

import os
import sys
import yaml
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Color codes for terminal output
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(message, color):
    """Print colored message to terminal"""
    print(f"{color}{message}{Colors.NC}")

async def extract_cookies_with_playwright(url="https://libh-proxy1.fyre.ibm.com/buildBreakReport/"):
    """
    Extract cookies using Playwright with persistent browser context
    This handles passkey authentication automatically
    
    Args:
        url: URL to navigate to
        
    Returns:
        Tuple of (ltpa_token, session_id) or (None, None) if failed
    """
    user_data_dir = os.path.expanduser("~/.playwright-chrome-profile")
    
    print_colored("🚀 Starting Playwright browser...", Colors.BLUE)
    print_colored(f"📂 Using profile: {user_data_dir}", Colors.BLUE)
    
    async with async_playwright() as p:
        try:
            # Check if DISPLAY is set (GUI available)
            display = os.environ.get('DISPLAY')
            
            if display:
                print_colored(f"✅ Display found: {display}", Colors.GREEN)
                headless_mode = False
            else:
                print_colored("⚠️  No display found, using headless mode", Colors.YELLOW)
                print_colored("💡 For first-time setup, you may need to set DISPLAY or use xvfb", Colors.YELLOW)
                headless_mode = True
            
            # Launch browser with persistent context (saves login state)
            context = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=headless_mode,
                ignore_https_errors=True,  # Ignore SSL certificate errors
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--ignore-certificate-errors',
                ],
                channel='chrome'  # Use system Chrome
            )
            
            print_colored("✅ Browser launched", Colors.GREEN)
            
            # Create new page
            page = await context.new_page()
            
            print_colored(f"🌐 Navigating to: {url}", Colors.BLUE)
            
            try:
                # Navigate to the site
                await page.goto(url, wait_until='networkidle', timeout=60000)
                print_colored("✅ Page loaded", Colors.GREEN)
                
                # Wait a bit for any redirects or auth flows
                await asyncio.sleep(3)
                
                # Check if we're on the login page
                current_url = page.url
                if 'login' in current_url.lower() or 'auth' in current_url.lower():
                    print_colored("\n⚠️  Login required!", Colors.YELLOW)
                    print_colored("👉 Please complete the login in the browser window", Colors.YELLOW)
                    print_colored("   (Use 1Password passkey authentication)", Colors.YELLOW)
                    print_colored("\n⏳ Waiting for you to login...", Colors.BLUE)
                    print_colored("   Press Enter after you've logged in successfully", Colors.YELLOW)
                    input()
                    
                    # Wait for navigation after login
                    await asyncio.sleep(2)
                    print_colored("✅ Login detected", Colors.GREEN)
                
                # Get cookies from the browser context
                print_colored("\n🍪 Extracting cookies...", Colors.BLUE)
                cookies = await context.cookies()
                
                if not cookies:
                    print_colored("❌ No cookies found", Colors.RED)
                    await context.close()
                    return None, None
                
                print_colored(f"✅ Found {len(cookies)} cookies", Colors.GREEN)
                
                # Find required cookies
                ltpa_token = None
                session_id = None
                
                for cookie in cookies:
                    if cookie['name'] == 'LtpaToken2':
                        ltpa_token = cookie['value']
                        print_colored(f"✅ Found LtpaToken2: {ltpa_token[:50]}...", Colors.GREEN)
                    elif cookie['name'] == 'mod_auth_openidc_session':
                        session_id = cookie['value']
                        print_colored(f"✅ Found mod_auth_openidc_session: {session_id}", Colors.GREEN)
                
                if ltpa_token and session_id:
                    print_colored("\n✅ Successfully extracted both required cookies!", Colors.GREEN)
                    print_colored("\n🔍 Extracted cookies:", Colors.BLUE)
                    print_colored(f"   LtpaToken2: {ltpa_token[:80]}...", Colors.YELLOW)
                    print_colored(f"   mod_auth_openidc_session: {session_id}", Colors.YELLOW)
                    print()
                    print_colored("⏸️  Browser window will stay open for verification", Colors.YELLOW)
                    print_colored("👉 Check the cookies in browser DevTools (F12 → Application → Cookies)", Colors.YELLOW)
                    print_colored("👉 Press Enter when you've verified the cookies match...", Colors.GREEN)
                    input()
                    
                    # Close browser after verification
                    await context.close()
                    return ltpa_token, session_id
                else:
                    if not ltpa_token:
                        print_colored("❌ LtpaToken2 not found", Colors.RED)
                    if not session_id:
                        print_colored("❌ mod_auth_openidc_session not found", Colors.RED)
                    
                    # Close browser
                    await context.close()
                    return None, None
                    
            except PlaywrightTimeout:
                print_colored("❌ Timeout waiting for page to load", Colors.RED)
                await context.close()
                return None, None
                
        except Exception as e:
            print_colored(f"❌ Error: {e}", Colors.RED)
            import traceback
            print(traceback.format_exc())
            return None, None

def update_config_yaml(config_path, ltpa_token, session_id):
    """
    Update config.yaml with new cookies
    
    Args:
        config_path: Path to config.yaml file
        ltpa_token: LtpaToken2 value
        session_id: mod_auth_openidc_session value
        
    Returns:
        True if successful, False otherwise
    """
    backup_path = None
    try:
        # Create backup
        backup_path = f"{config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print_colored(f"\n📦 Creating backup: {backup_path}", Colors.BLUE)
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
            with open(backup_path, 'w') as f:
                f.write(content)
            print_colored("✅ Backup created", Colors.GREEN)
        
        # Load config
        print_colored(f"\n📝 Loading config from: {config_path}", Colors.BLUE)
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update cookies
        if 'ibm' not in config:
            config['ibm'] = {}
        
        # Set auth method to cookies
        config['ibm']['auth_method'] = 'cookies'
        
        if 'cookies' not in config['ibm']:
            config['ibm']['cookies'] = {}
        
        config['ibm']['cookies']['LtpaToken2'] = ltpa_token
        config['ibm']['cookies']['mod_auth_openidc_session'] = session_id
        
        # Write back to file
        print_colored(f"💾 Writing updated config to: {config_path}", Colors.BLUE)
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print_colored("✅ Config updated successfully!", Colors.GREEN)
        return True
        
    except Exception as e:
        print_colored(f"❌ Error updating config: {e}", Colors.RED)
        import traceback
        print(traceback.format_exc())
        
        # Restore backup if it exists
        if backup_path and os.path.exists(backup_path):
            print_colored("🔄 Restoring backup...", Colors.YELLOW)
            with open(backup_path, 'r') as f:
                content = f.read()
            with open(config_path, 'w') as f:
                f.write(content)
            print_colored("✅ Backup restored", Colors.GREEN)
        
        return False

async def main():
    """Main function"""
    print_colored("=" * 70, Colors.BLUE)
    print_colored("🎭 Playwright Cookie Extractor for IBM Site", Colors.BLUE)
    print_colored("=" * 70, Colors.BLUE)
    print()
    
    # Determine config path
    config_path = "config/config.yaml"
    
    if not os.path.exists(config_path):
        print_colored(f"❌ Config file not found: {config_path}", Colors.RED)
        print_colored("💡 Please create config.yaml from config.yaml.example", Colors.YELLOW)
        sys.exit(1)
    
    # Extract cookies using Playwright
    print_colored("Step 1: Extracting cookies with Playwright", Colors.BLUE)
    print_colored("-" * 70, Colors.BLUE)
    print()
    
    ltpa_token, session_id = await extract_cookies_with_playwright()
    
    if not ltpa_token or not session_id:
        print_colored("\n❌ Failed to extract cookies", Colors.RED)
        print_colored("\n💡 Tips:", Colors.YELLOW)
        print("   1. Make sure you completed the login in the browser")
        print("   2. Check that you can access the site manually")
        print("   3. Try running the script again")
        sys.exit(1)
    
    # Update config.yaml
    print_colored("\nStep 2: Updating config.yaml", Colors.BLUE)
    print_colored("-" * 70, Colors.BLUE)
    success = update_config_yaml(config_path, ltpa_token, session_id)
    
    if not success:
        print_colored("\n❌ Failed to update config.yaml", Colors.RED)
        sys.exit(1)
    
    # Success message
    print()
    print_colored("=" * 70, Colors.GREEN)
    print_colored("✅ Cookies extracted and updated successfully!", Colors.GREEN)
    print_colored("=" * 70, Colors.GREEN)
    print()
    print_colored("📝 Next steps:", Colors.YELLOW)
    print()
    print("1. Restart your application:")
    print_colored("   docker-compose restart", Colors.GREEN)
    print()
    print("2. Check logs for successful authentication:")
    print_colored("   docker-compose logs -f | grep -i auth", Colors.GREEN)
    print()
    print("3. Set up automated refresh (cron):")
    print_colored("   */30 * * * * cd ~/defect-monitor-server && python3 playwright_cookie_extractor.py >> logs/cookie_refresh.log 2>&1", Colors.GREEN)
    print()
    print_colored("💡 Note:", Colors.YELLOW)
    print("   - First run requires manual login (passkey)")
    print("   - Subsequent runs use saved browser session")
    print("   - Cookies refresh automatically every 30 minutes")
    print()

if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob