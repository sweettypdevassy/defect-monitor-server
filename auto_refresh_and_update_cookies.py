#!/usr/bin/env python3
"""
Automatic Cookie Refresh with Browser Automation
Automatically refreshes IBM page in Chrome and extracts fresh cookies
"""

import sys
import os
import yaml
import time
from datetime import datetime

# Color codes for terminal output
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(message, color):
    """Print colored message to terminal"""
    print(f"{color}{message}{Colors.NC}")

def refresh_ibm_page_in_chrome():
    """
    Refresh IBM page in Chrome using Selenium to get fresh cookies
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        print_colored("❌ Selenium not installed", Colors.RED)
        print_colored("Installing selenium...", Colors.YELLOW)
        os.system("pip3 install selenium")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    
    try:
        print_colored("🌐 Connecting to existing Chrome session...", Colors.BLUE)
        
        # Chrome options to connect to existing session
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        
        # Connect to Chrome
        driver = webdriver.Chrome(options=chrome_options)
        
        print_colored(f"✅ Connected to Chrome", Colors.GREEN)
        print_colored(f"Current URL: {driver.current_url}", Colors.BLUE)
        
        # Navigate to IBM page if not already there
        ibm_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
        
        if "libh-proxy1.fyre.ibm.com" not in driver.current_url:
            print_colored(f"🔄 Navigating to {ibm_url}", Colors.BLUE)
            driver.get(ibm_url)
            time.sleep(3)
        else:
            print_colored("🔄 Refreshing current IBM page...", Colors.BLUE)
            driver.refresh()
            time.sleep(3)
        
        print_colored("✅ Page refreshed successfully", Colors.GREEN)
        
        # Wait for page to load
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            print_colored("✅ Page fully loaded", Colors.GREEN)
        except:
            print_colored("⚠️  Page load timeout, continuing anyway", Colors.YELLOW)
        
        # Don't close the driver - keep Chrome running
        print_colored("✅ Chrome session maintained", Colors.GREEN)
        
        return True
        
    except Exception as e:
        print_colored(f"❌ Error refreshing page: {e}", Colors.RED)
        print_colored("\n💡 Make sure Chrome is running with remote debugging:", Colors.YELLOW)
        print_colored("   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile", Colors.YELLOW)
        return False

def extract_cookies_from_chrome(domain="libh-proxy1.fyre.ibm.com"):
    """Extract cookies from Chrome browser"""
    try:
        import browser_cookie3
    except ImportError:
        print_colored("❌ browser-cookie3 not installed", Colors.RED)
        print_colored("Installing browser-cookie3...", Colors.YELLOW)
        os.system("pip3 install browser-cookie3")
        import browser_cookie3
    
    try:
        print_colored(f"🔍 Extracting cookies from Chrome for domain: {domain}", Colors.BLUE)
        
        # Get cookies from Chrome
        cj = browser_cookie3.chrome(domain_name=domain)
        cookies = list(cj)
        
        if not cookies:
            print_colored("⚠️  No cookies found in Chrome", Colors.YELLOW)
            return None, None
        
        print_colored(f"✅ Found {len(cookies)} cookies in Chrome", Colors.GREEN)
        
        # Find required cookies
        ltpa_token = None
        session_id = None
        
        for cookie in cookies:
            if cookie.name == 'LtpaToken2':
                ltpa_token = cookie.value
                if ltpa_token:
                    print_colored(f"✅ Found LtpaToken2: {ltpa_token[:50]}...", Colors.GREEN)
            elif cookie.name == 'mod_auth_openidc_session':
                session_id = cookie.value
                if session_id:
                    print_colored(f"✅ Found mod_auth_openidc_session: {session_id}", Colors.GREEN)
        
        if not ltpa_token:
            print_colored("❌ LtpaToken2 not found", Colors.RED)
        if not session_id:
            print_colored("❌ mod_auth_openidc_session not found", Colors.RED)
        
        if ltpa_token and session_id:
            return ltpa_token, session_id
        else:
            return None, None
            
    except Exception as e:
        print_colored(f"❌ Error extracting cookies: {e}", Colors.RED)
        return None, None

def update_config_yaml(config_path, ltpa_token, session_id):
    """Update config.yaml with new cookies"""
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
        
        # Restore backup if it exists
        if backup_path and os.path.exists(backup_path):
            print_colored("🔄 Restoring backup...", Colors.YELLOW)
            with open(backup_path, 'r') as f:
                content = f.read()
            with open(config_path, 'w') as f:
                f.write(content)
            print_colored("✅ Backup restored", Colors.GREEN)
        
        return False

def main():
    """Main function"""
    print_colored("=" * 60, Colors.BLUE)
    print_colored("🔄 Auto-Refresh IBM Page & Update Cookies", Colors.BLUE)
    print_colored("=" * 60, Colors.BLUE)
    print()
    
    # Determine config path
    config_path = "config/config.yaml"
    
    if not os.path.exists(config_path):
        print_colored(f"❌ Config file not found: {config_path}", Colors.RED)
        sys.exit(1)
    
    # Step 1: Refresh IBM page in Chrome
    print_colored("Step 1: Refreshing IBM page in Chrome", Colors.BLUE)
    print_colored("-" * 60, Colors.BLUE)
    
    if not refresh_ibm_page_in_chrome():
        print_colored("\n⚠️  Could not refresh page automatically", Colors.YELLOW)
        print_colored("Continuing with cookie extraction...", Colors.YELLOW)
    
    # Wait a bit for cookies to be set
    print_colored("\n⏳ Waiting 2 seconds for cookies to be set...", Colors.BLUE)
    time.sleep(2)
    
    # Step 2: Extract cookies from Chrome
    print_colored("\nStep 2: Extracting cookies from Chrome", Colors.BLUE)
    print_colored("-" * 60, Colors.BLUE)
    ltpa_token, session_id = extract_cookies_from_chrome()
    
    if not ltpa_token or not session_id:
        print_colored("\n❌ Failed to extract cookies from Chrome", Colors.RED)
        sys.exit(1)
    
    # Step 3: Update config.yaml
    print_colored("\nStep 3: Updating config.yaml", Colors.BLUE)
    print_colored("-" * 60, Colors.BLUE)
    success = update_config_yaml(config_path, ltpa_token, session_id)
    
    if not success:
        print_colored("\n❌ Failed to update config.yaml", Colors.RED)
        sys.exit(1)
    
    # Success message
    print()
    print_colored("=" * 60, Colors.GREEN)
    print_colored("✅ Page refreshed and cookies updated!", Colors.GREEN)
    print_colored("=" * 60, Colors.GREEN)
    print()

if __name__ == "__main__":
    main()

# Made with Bob
