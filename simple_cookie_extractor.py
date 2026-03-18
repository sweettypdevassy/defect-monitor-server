#!/usr/bin/env python3
"""
Simple Cookie Extractor - Copies your Chrome profile then extracts cookies
This avoids profile locking issues
"""

import os
import sys
import yaml
import time
import shutil
import subprocess
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Color codes
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(message, color):
    print(f"{color}{message}{Colors.NC}")

def copy_chrome_profile():
    """Copy your Chrome profile to avoid locking issues"""
    source = os.path.expanduser("~/.config/google-chrome/Default")
    dest = os.path.expanduser("~/.chrome-cookie-profile")
    
    print_colored("📂 Copying Chrome profile...", Colors.BLUE)
    print_colored(f"   From: {source}", Colors.YELLOW)
    print_colored(f"   To: {dest}", Colors.YELLOW)
    
    # Remove old copy if exists
    if os.path.exists(dest):
        shutil.rmtree(dest)
    
    # Copy profile
    try:
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns('SingletonLock', 'SingletonSocket', 'SingletonCookie'))
        print_colored("✅ Profile copied successfully!", Colors.GREEN)
        return dest
    except Exception as e:
        print_colored(f"❌ Error copying profile: {e}", Colors.RED)
        return None

def extract_cookies():
    """Extract cookies using copied profile"""
    
    print_colored("\n" + "=" * 70, Colors.BLUE)
    print_colored("🍪 Simple Cookie Extractor", Colors.BLUE)
    print_colored("=" * 70, Colors.BLUE)
    print()
    
    # Copy profile first
    profile_dir = copy_chrome_profile()
    if not profile_dir:
        return None, None, None
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={profile_dir}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-extensions")  # Disable extensions for automation
    
    print_colored("\n🚀 Starting Chrome...", Colors.BLUE)
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print_colored("✅ Chrome started!", Colors.GREEN)
        
        # Navigate to IBM site
        url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/"
        print_colored(f"\n🌐 Navigating to: {url}", Colors.BLUE)
        driver.get(url)
        
        # Wait for page load
        time.sleep(5)
        
        current_url = driver.current_url
        print_colored(f"📍 Current URL: {current_url}", Colors.BLUE)
        
        # Check if login needed
        if 'login' in current_url.lower() or 'auth' in current_url.lower():
            print_colored("\n⚠️  Login required!", Colors.YELLOW)
            print_colored("👉 Please login in the browser window", Colors.YELLOW)
            print_colored("   (The browser has your saved credentials)", Colors.YELLOW)
            print_colored("\n⏳ Press Enter after you've logged in...", Colors.BLUE)
            input()
            time.sleep(2)
        else:
            print_colored("✅ Already logged in (using saved session)!", Colors.GREEN)
        
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
        
        # Close browser
        print_colored("\n🔒 Closing browser...", Colors.BLUE)
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
    all_cookies, ltpa_token, session_id = extract_cookies()
    
    if not all_cookies or not ltpa_token or not session_id:
        print_colored("\n❌ Failed to extract cookies", Colors.RED)
        print_colored("\n💡 Tips:", Colors.YELLOW)
        print("   1. Make sure you can access the IBM site in your regular Chrome")
        print("   2. The script copies your Chrome profile to avoid locking")
        print("   3. You may need to login once in the script's browser window")
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
    print()
    print_colored("📝 Next steps:", Colors.YELLOW)
    print("   1. Verify: cat config/config.yaml | grep -A 5 'cookies:'")
    print("   2. Check Docker: docker-compose logs | grep 'Authentication'")
    print("   3. Setup cron for automatic refresh")

if __name__ == "__main__":
    main()

# Made with Bob
