#!/usr/bin/env python3
"""
Automatic Cookie Extractor using Selenium
Opens Chrome with your profile, logs in automatically, extracts cookies
"""

import os
import sys
import yaml
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Color codes
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(message, color):
    print(f"{color}{message}{Colors.NC}")

def extract_cookies_with_selenium():
    """Extract cookies using Selenium with your Chrome profile"""
    
    print_colored("=" * 70, Colors.BLUE)
    print_colored("🍪 Automatic Cookie Extractor", Colors.BLUE)
    print_colored("=" * 70, Colors.BLUE)
    print()
    
    # Setup Chrome options
    chrome_options = Options()
    
    # Use your existing Chrome profile where 1Password is installed
    chrome_profile = os.path.expanduser("~/.config/google-chrome")
    chrome_options.add_argument(f"user-data-dir={chrome_profile}")
    
    # Use Default profile (or specify another profile like "Profile 1")
    chrome_options.add_argument("profile-directory=Default")
    
    # Other options
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--ignore-certificate-errors")
    
    # Don't use headless mode - we need to see 1Password
    # chrome_options.add_argument("--headless")
    
    print_colored("🚀 Starting Chrome with your profile...", Colors.BLUE)
    print_colored(f"📂 Profile: {chrome_profile}", Colors.BLUE)
    print()
    
    try:
        # Start Chrome
        driver = webdriver.Chrome(options=chrome_options)
        print_colored("✅ Chrome started!", Colors.GREEN)
        
        # Navigate to IBM site
        url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
        print_colored(f"🌐 Navigating to: {url}", Colors.BLUE)
        driver.get(url)
        
        # Wait for page to load
        time.sleep(5)
        
        # Check if we're on login page
        current_url = driver.current_url
        print_colored(f"📍 Current URL: {current_url}", Colors.BLUE)
        
        if 'login' in current_url.lower() or 'auth' in current_url.lower():
            print_colored("\n⚠️  Login page detected", Colors.YELLOW)
            print_colored("👉 1Password should automatically fill in credentials", Colors.YELLOW)
            print_colored("⏳ Waiting 30 seconds for automatic login...", Colors.BLUE)
            
            # Wait for automatic login (1Password should handle this)
            time.sleep(30)
            
            # Check if still on login page
            if 'login' in driver.current_url.lower():
                print_colored("\n⚠️  Still on login page", Colors.YELLOW)
                print_colored("👉 Please complete login manually in the browser", Colors.YELLOW)
                print_colored("⏳ Press Enter after you've logged in...", Colors.BLUE)
                input()
        else:
            print_colored("✅ Already logged in!", Colors.GREEN)
        
        # Wait a bit more for any redirects
        time.sleep(3)
        
        # Extract cookies
        print_colored("\n🍪 Extracting cookies...", Colors.BLUE)
        cookies = driver.get_cookies()
        
        if not cookies:
            print_colored("❌ No cookies found", Colors.RED)
            driver.quit()
            return None, None, None
        
        print_colored(f"✅ Found {len(cookies)} cookies", Colors.GREEN)
        
        # Convert to dictionary
        all_cookies = {}
        ltpa_token = None
        session_id = None
        
        for cookie in cookies:
            name = cookie['name']
            value = cookie['value']
            all_cookies[name] = value
            
            if name == 'LtpaToken2':
                ltpa_token = value
                print_colored(f"✅ Found LtpaToken2: {value[:50]}...", Colors.GREEN)
            elif name == 'mod_auth_openidc_session':
                session_id = value
                print_colored(f"✅ Found mod_auth_openidc_session: {value}", Colors.GREEN)
        
        # Keep browser open for a moment to verify
        print_colored("\n⏸️  Browser will stay open for 5 seconds...", Colors.YELLOW)
        time.sleep(5)
        
        # Close browser
        print_colored("🔒 Closing browser...", Colors.BLUE)
        driver.quit()
        
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
        print_colored(f"❌ Error: {e}", Colors.RED)
        import traceback
        print(traceback.format_exc())
        try:
            driver.quit()
        except:
            pass
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
        
        print_colored(f"📝 Storing {len(all_cookies)} cookies in config", Colors.BLUE)
        
        # Write back
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print_colored("✅ Config updated successfully!", Colors.GREEN)
        return True
        
    except Exception as e:
        print_colored(f"❌ Error updating config: {e}", Colors.RED)
        return False

def main():
    """Main function"""
    config_path = "config/config.yaml"
    
    if not os.path.exists(config_path):
        print_colored(f"❌ Config file not found: {config_path}", Colors.RED)
        sys.exit(1)
    
    # Extract cookies
    all_cookies, ltpa_token, session_id = extract_cookies_with_selenium()
    
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
    import subprocess
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
    main()

# Made with Bob
