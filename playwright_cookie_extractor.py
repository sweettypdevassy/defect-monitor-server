#!/usr/bin/env python3
"""
Playwright-based Cookie Extractor for IBM Site
Handles passkey authentication and extracts cookies automatically
"""

import os
import sys
import yaml
import asyncio
import subprocess
import time
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
        Tuple of (all_cookies_dict, ltpa_token, session_id) or (None, None, None) if failed
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
                    return None, None, None
                
                print_colored(f"✅ Found {len(cookies)} cookies", Colors.GREEN)
                
                # Extract ALL cookies (we need all OpenID Connect cookies)
                all_cookies = {}
                ltpa_token = None
                session_id = None
                
                for cookie in cookies:
                    cookie_name = cookie['name']
                    cookie_value = cookie['value']
                    
                    # Store all cookies
                    all_cookies[cookie_name] = cookie_value
                    
                    # Track specific important cookies
                    if cookie_name == 'LtpaToken2':
                        ltpa_token = cookie_value
                        print_colored(f"✅ Found LtpaToken2: {cookie_value[:50]}...", Colors.GREEN)
                    elif cookie_name == 'mod_auth_openidc_session':
                        session_id = cookie_value
                        print_colored(f"✅ Found mod_auth_openidc_session: {cookie_value}", Colors.GREEN)
                    elif cookie_name.startswith('mod_auth_openidc'):
                        print_colored(f"✅ Found {cookie_name}: {cookie_value[:50]}...", Colors.GREEN)
                    elif cookie_name.startswith('__tk'):
                        print_colored(f"✅ Found {cookie_name}: {cookie_value[:50]}...", Colors.GREEN)
                
                if ltpa_token and session_id:
                    print_colored(f"\n✅ Successfully extracted {len(all_cookies)} cookies!", Colors.GREEN)
                    print_colored("\n🔍 All extracted cookies:", Colors.BLUE)
                    for name, value in all_cookies.items():
                        display_value = value[:50] + "..." if len(value) > 50 else value
                        print_colored(f"   {name}: {display_value}", Colors.YELLOW)
                    print()
                    
                    # Check if running in interactive mode (has a terminal)
                    import sys
                    if sys.stdin.isatty() and not headless_mode:
                        print_colored("⏸️  Browser window will stay open for verification", Colors.YELLOW)
                        print_colored("👉 Check the cookies in browser DevTools (F12 → Application → Cookies)", Colors.YELLOW)
                        print_colored("👉 Press Enter when you've verified the cookies match...", Colors.GREEN)
                        input()
                    else:
                        print_colored("✅ Running in non-interactive mode (cron/headless), skipping verification", Colors.BLUE)
                        # Wait a bit for any final cookie updates
                        await asyncio.sleep(2)
                    
                    # Close browser after verification
                    await context.close()
                    return all_cookies, ltpa_token, session_id
                else:
                    if not ltpa_token:
                        print_colored("❌ LtpaToken2 not found", Colors.RED)
                    if not session_id:
                        print_colored("❌ mod_auth_openidc_session not found", Colors.RED)
                    
                    # Close browser
                    await context.close()
                    return None, None, None
                    
            except PlaywrightTimeout:
                print_colored("❌ Timeout waiting for page to load", Colors.RED)
                await context.close()
                return None, None, None
                
        except Exception as e:
            print_colored(f"❌ Error: {e}", Colors.RED)
            import traceback
            print(traceback.format_exc())
            return None, None, None

def update_config_yaml(config_path, all_cookies, ltpa_token, session_id):
    """
    Update config.yaml with ALL cookies
    
    Args:
        config_path: Path to config.yaml file
        all_cookies: Dictionary of all cookies
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
        
        # Store ALL cookies (not just LtpaToken2 and session)
        config['ibm']['cookies'] = all_cookies
        
        print_colored(f"📝 Storing {len(all_cookies)} cookies in config", Colors.BLUE)
        
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
    
    all_cookies, ltpa_token, session_id = await extract_cookies_with_playwright()
    
    if not all_cookies or not ltpa_token or not session_id:
        print_colored("\n❌ Failed to extract cookies", Colors.RED)
        print_colored("\n💡 Tips:", Colors.YELLOW)
        print("   1. Make sure you completed the login in the browser")
        print("   2. Check that you can access the site manually")
        print("   3. Try running the script again")
        sys.exit(1)
    
    # Update config.yaml
    print_colored("\nStep 2: Updating config.yaml with ALL cookies", Colors.BLUE)
    print_colored("-" * 70, Colors.BLUE)
    success = update_config_yaml(config_path, all_cookies, ltpa_token, session_id)
    
    if not success:
        print_colored("\n❌ Failed to update config.yaml", Colors.RED)
        sys.exit(1)
    
    # Success message
    print()
    print_colored("=" * 70, Colors.GREEN)
    print_colored("✅ Cookies extracted and updated successfully!", Colors.GREEN)
    print_colored("=" * 70, Colors.GREEN)
    print()
    
    # Automatically restart Docker to apply new cookies
    print_colored("🔄 Restarting Docker container to apply new cookies...", Colors.BLUE)
    print()
    
    try:
        result = subprocess.run(
            ["docker-compose", "restart"],
            cwd=os.path.dirname(config_path),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print_colored("✅ Docker container restarted successfully!", Colors.GREEN)
            print()
            print_colored("⏳ Waiting for application to start...", Colors.BLUE)
            import time
            time.sleep(5)
            
            # Check authentication status
            print_colored("📊 Checking authentication status...", Colors.BLUE)
            log_result = subprocess.run(
                ["docker-compose", "logs", "--tail=20"],
                cwd=os.path.dirname(config_path),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if "Session initialized" in log_result.stdout:
                print_colored("✅ Authentication successful!", Colors.GREEN)
            else:
                print_colored("⚠️  Check logs for authentication status", Colors.YELLOW)
            
            print()
            print_colored("=" * 70, Colors.GREEN)
            print_colored("✅ Cookie refresh and restart complete!", Colors.GREEN)
            print_colored("=" * 70, Colors.GREEN)
        else:
            print_colored("⚠️  Docker restart failed, please restart manually:", Colors.YELLOW)
            print_colored("   docker-compose restart", Colors.YELLOW)
            print()
            print_colored(f"Error: {result.stderr}", Colors.RED)
    
    except subprocess.TimeoutExpired:
        print_colored("⚠️  Docker restart timed out, please check manually", Colors.YELLOW)
    except FileNotFoundError:
        print_colored("⚠️  docker-compose not found, please restart manually:", Colors.YELLOW)
        print_colored("   docker-compose restart", Colors.YELLOW)
    except Exception as e:
        print_colored(f"⚠️  Could not restart Docker automatically: {e}", Colors.YELLOW)
        print_colored("   Please restart manually: docker-compose restart", Colors.YELLOW)
    
    print()
    print_colored("📝 Monitoring:", Colors.YELLOW)
    print("   docker-compose logs -f | grep -i auth")
    print()

if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob