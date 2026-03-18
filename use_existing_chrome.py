#!/usr/bin/env python3
"""
Cookie Extractor using your existing Chrome with Remote Debugging
This connects to your already-running Chrome instead of opening a new one
"""

import os
import sys
import yaml
import asyncio
import subprocess
import time
from datetime import datetime
from playwright.async_api import async_playwright

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

async def extract_cookies_from_running_chrome():
    """
    Extract cookies from your already-running Chrome browser
    """
    print_colored("=" * 70, Colors.BLUE)
    print_colored("🎭 Cookie Extractor - Using Your Running Chrome", Colors.BLUE)
    print_colored("=" * 70, Colors.BLUE)
    print()
    
    # Check if Chrome is running with remote debugging
    print_colored("🔍 Checking for Chrome with remote debugging...", Colors.BLUE)
    
    # Try to connect to Chrome on port 9222
    async with async_playwright() as p:
        try:
            # Connect to existing Chrome instance
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            print_colored("✅ Connected to your running Chrome!", Colors.GREEN)
            
            # Get all contexts (tabs)
            contexts = browser.contexts
            if not contexts:
                print_colored("❌ No browser contexts found", Colors.RED)
                return None, None, None
            
            # Use the first context
            context = contexts[0]
            pages = context.pages
            
            if not pages:
                print_colored("❌ No pages found", Colors.RED)
                return None, None, None
            
            # Use the first page or create new one
            page = pages[0]
            
            print_colored(f"📄 Using page: {page.url}", Colors.BLUE)
            
            # Navigate to IBM site if not already there
            current_url = page.url
            target_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
            
            if target_url not in current_url:
                print_colored(f"🌐 Navigating to: {target_url}", Colors.BLUE)
                await page.goto(target_url, wait_until='networkidle', timeout=60000)
            else:
                print_colored("✅ Already on IBM site", Colors.GREEN)
            
            # Wait a bit for any auth flows
            await asyncio.sleep(2)
            
            # Check if login is needed
            if 'login' in page.url.lower() or 'auth' in page.url.lower():
                print_colored("\n⚠️  Login required!", Colors.YELLOW)
                print_colored("👉 Please login in your Chrome browser", Colors.YELLOW)
                print_colored("   (Use 1Password passkey)", Colors.YELLOW)
                print_colored("\n⏳ Press Enter after you've logged in...", Colors.BLUE)
                input()
                await asyncio.sleep(2)
            
            # Extract cookies
            print_colored("\n🍪 Extracting cookies...", Colors.BLUE)
            cookies = await context.cookies()
            
            if not cookies:
                print_colored("❌ No cookies found", Colors.RED)
                return None, None, None
            
            print_colored(f"✅ Found {len(cookies)} cookies", Colors.GREEN)
            
            # Extract ALL cookies
            all_cookies = {}
            ltpa_token = None
            session_id = None
            
            for cookie in cookies:
                cookie_name = cookie['name']
                cookie_value = cookie['value']
                
                all_cookies[cookie_name] = cookie_value
                
                if cookie_name == 'LtpaToken2':
                    ltpa_token = cookie_value
                    print_colored(f"✅ Found LtpaToken2: {cookie_value[:50]}...", Colors.GREEN)
                elif cookie_name == 'mod_auth_openidc_session':
                    session_id = cookie_value
                    print_colored(f"✅ Found mod_auth_openidc_session: {cookie_value}", Colors.GREEN)
            
            if ltpa_token and session_id:
                print_colored(f"\n✅ Successfully extracted {len(all_cookies)} cookies!", Colors.GREEN)
                return all_cookies, ltpa_token, session_id
            else:
                if not ltpa_token:
                    print_colored("❌ LtpaToken2 not found", Colors.RED)
                if not session_id:
                    print_colored("❌ mod_auth_openidc_session not found", Colors.RED)
                return None, None, None
                
        except Exception as e:
            print_colored(f"❌ Error connecting to Chrome: {e}", Colors.RED)
            print()
            print_colored("💡 Chrome needs to be started with remote debugging enabled:", Colors.YELLOW)
            print_colored("   Close Chrome completely, then run:", Colors.YELLOW)
            print()
            print_colored("   google-chrome --remote-debugging-port=9222 &", Colors.GREEN)
            print()
            print_colored("   Then run this script again.", Colors.YELLOW)
            return None, None, None

def update_config_yaml(config_path, all_cookies, ltpa_token, session_id):
    """Update config.yaml with cookies"""
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
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update cookies
        if 'ibm' not in config:
            config['ibm'] = {}
        
        config['ibm']['auth_method'] = 'cookies'
        config['ibm']['cookies'] = all_cookies
        
        # Write back
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print_colored("✅ Config updated successfully!", Colors.GREEN)
        return True
        
    except Exception as e:
        print_colored(f"❌ Error updating config: {e}", Colors.RED)
        return False

async def main():
    """Main function"""
    config_path = "config/config.yaml"
    
    if not os.path.exists(config_path):
        print_colored(f"❌ Config file not found: {config_path}", Colors.RED)
        sys.exit(1)
    
    # Extract cookies
    all_cookies, ltpa_token, session_id = await extract_cookies_from_running_chrome()
    
    if not all_cookies or not ltpa_token or not session_id:
        print_colored("\n❌ Failed to extract cookies", Colors.RED)
        sys.exit(1)
    
    # Update config
    success = update_config_yaml(config_path, all_cookies, ltpa_token, session_id)
    
    if not success:
        print_colored("\n❌ Failed to update config.yaml", Colors.RED)
        sys.exit(1)
    
    # Restart Docker
    print_colored("\n🔄 Restarting Docker container...", Colors.BLUE)
    try:
        result = subprocess.run(
            ["docker-compose", "restart"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print_colored("✅ Docker container restarted successfully!", Colors.GREEN)
        else:
            print_colored("⚠️  Please restart Docker manually: docker-compose restart", Colors.YELLOW)
    except Exception as e:
        print_colored(f"⚠️  Could not restart Docker: {e}", Colors.YELLOW)
    
    print()
    print_colored("=" * 70, Colors.GREEN)
    print_colored("✅ Cookie extraction complete!", Colors.GREEN)
    print_colored("=" * 70, Colors.GREEN)

if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
