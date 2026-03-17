#!/usr/bin/env python3
"""
Automatic Cookie Updater for config.yaml
Extracts LtpaToken2 and mod_auth_openidc_session from Chrome and updates config.yaml
"""

import sys
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Iterable, cast
import http.cookiejar

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

def extract_cookies_from_chrome(domain="libh-proxy1.fyre.ibm.com"):
    """
    Extract cookies from Chrome browser
    
    Args:
        domain: Domain to extract cookies from
        
    Returns:
        Tuple of (ltpa_token, session_id) or (None, None) if failed
    """
    try:
        import browser_cookie3
    except ImportError:
        print_colored("❌ browser-cookie3 not installed", Colors.RED)
        print_colored("Installing browser-cookie3...", Colors.YELLOW)
        os.system("pip3 install browser-cookie3")
        import browser_cookie3
    
    try:
        print_colored(f"🔍 Extracting cookies from Chrome for domain: {domain}", Colors.BLUE)
        
        # Force specific cookie file path - use absolute path to avoid ~ expansion issues
        from browser_cookie3 import Chrome
        import shutil
        import tempfile
        import glob
        
        # Try multiple possible locations
        possible_paths = [
            "/home/abhi/.config/google-chrome/Default/Cookies",
            os.path.expanduser("~/.config/google-chrome/Default/Cookies"),
            os.path.join(os.path.expanduser("~"), ".config/google-chrome/Default/Cookies"),
        ]
        
        cookie_file = None
        for path in possible_paths:
            if os.path.exists(path):
                cookie_file = path
                break
        
        if not cookie_file:
            print_colored("❌ Cookie file not found in default locations", Colors.RED)
            print_colored("💡 Searching for Chrome cookie files...", Colors.YELLOW)
            cookie_files = glob.glob(os.path.expanduser("~/.config/google-chrome/**/Cookies"), recursive=True)
            cookie_files += glob.glob("/home/*/.config/google-chrome/**/Cookies", recursive=True)
            print_colored(f"Found cookie files: {cookie_files}", Colors.YELLOW)
            if cookie_files:
                cookie_file = cookie_files[0]
                print_colored(f"✅ Using: {cookie_file}", Colors.GREEN)
            else:
                raise FileNotFoundError("No Chrome cookie files found. Please ensure Chrome is installed and has been run at least once.")
        
        print_colored(f"📂 Using cookie file: {cookie_file}", Colors.BLUE)
        print_colored(f"📋 File exists: {os.path.exists(cookie_file)}", Colors.GREEN)
        
        # Copy DB to temp to avoid lock issues - use safe method
        print_colored("📋 Copying cookie database to temp location...", Colors.BLUE)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp_cookie = tmp.name
        
        shutil.copy2(cookie_file, tmp_cookie)
        print_colored(f"✅ Copied to: {tmp_cookie}", Colors.GREEN)
        
        # Get cookies from Chrome using explicit path
        cj = Chrome(
            cookie_file=tmp_cookie,
            domain_name=domain
            keyring=False
        )
        cookies = list(cast(Iterable[http.cookiejar.Cookie], cj))
        
        # Clean up temp file
        try:
            os.remove(tmp_cookie)
        except:
            pass
        
        if not cookies:
            print_colored("⚠️  No cookies found in Chrome", Colors.YELLOW)
            print_colored("\n💡 Please ensure:", Colors.YELLOW)
            print("   1. Chrome is running")
            print("   2. You are logged in to: https://libh-proxy1.fyre.ibm.com/buildBreakReport/")
            print("   3. The page has fully loaded")
            print()
            print_colored("🔄 Would you like to retry after logging in? (y/n): ", Colors.YELLOW)
            
            try:
                response = input().strip().lower()
                if response == 'y':
                    print_colored("\n⏳ Waiting for you to login in Chrome...", Colors.BLUE)
                    print_colored("👉 After logging in, press Enter to retry...", Colors.YELLOW)
                    input()
                    
                    # Retry cookie extraction
                    print_colored("\n🔄 Retrying cookie extraction...", Colors.BLUE)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                        tmp_cookie_retry = tmp.name
                    shutil.copy2(cookie_file, tmp_cookie_retry)
                    
                    cj_retry = Chrome(cookie_file=tmp_cookie_retry, domain_name=domain)
                    cookies = list(cj_retry.load())
                    
                    try:
                        os.remove(tmp_cookie_retry)
                    except:
                        pass
                    
                    if not cookies:
                        print_colored("❌ Still no cookies found", Colors.RED)
                        return None, None
                    
                    print_colored(f"✅ Found {len(cookies)} cookies after retry", Colors.GREEN)
                else:
                    return None, None
            except (KeyboardInterrupt, EOFError):
                print()
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
            print_colored("\n⚠️  Missing required cookies", Colors.YELLOW)
            print_colored("💡 Cookies found but session likely expired or not logged in", Colors.YELLOW)
            print_colored("Please login to IBM site in Chrome and try again", Colors.YELLOW)
            return None, None
            
    except PermissionError as e:
        print_colored(f"❌ Permission denied: {e}", Colors.RED)
        print_colored("💡 Run as the same user that runs Chrome", Colors.YELLOW)
        return None, None
    except FileNotFoundError as e:
        print_colored(f"❌ Chrome cookie database not found: {e}", Colors.RED)
        print_colored("💡 Chrome may not be installed or never run", Colors.YELLOW)
        return None, None
    except Exception as e:
        print_colored(f"❌ Error extracting cookies: {e}", Colors.RED)
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

def main():
    """Main function"""
    print_colored("=" * 60, Colors.BLUE)
    print_colored("🍪 IBM Cookie Auto-Updater for config.yaml", Colors.BLUE)
    print_colored("=" * 60, Colors.BLUE)
    print()
    
    # Determine config path
    config_path = "config/config.yaml"
    
    if not os.path.exists(config_path):
        print_colored(f"❌ Config file not found: {config_path}", Colors.RED)
        print_colored("💡 Please create config.yaml from config.yaml.example", Colors.YELLOW)
        sys.exit(1)
    
    # Extract cookies from Chrome
    print_colored("Step 1: Extracting cookies from Chrome", Colors.BLUE)
    print_colored("-" * 60, Colors.BLUE)
    ltpa_token, session_id = extract_cookies_from_chrome()
    
    if not ltpa_token or not session_id:
        print_colored("\n❌ Failed to extract cookies from Chrome", Colors.RED)
        sys.exit(1)
    
    # Update config.yaml
    print_colored("\nStep 2: Updating config.yaml", Colors.BLUE)
    print_colored("-" * 60, Colors.BLUE)
    success = update_config_yaml(config_path, ltpa_token, session_id)
    
    if not success:
        print_colored("\n❌ Failed to update config.yaml", Colors.RED)
        sys.exit(1)
    
    # Success message
    print()
    print_colored("=" * 60, Colors.GREEN)
    print_colored("✅ Cookies updated successfully in config.yaml!", Colors.GREEN)
    print_colored("=" * 60, Colors.GREEN)
    print()
    print_colored("📝 Next steps:", Colors.YELLOW)
    print()
    print("1. Restart your application:")
    print_colored("   docker-compose restart", Colors.GREEN)
    print()
    print("2. Check logs for successful authentication:")
    print_colored("   docker-compose logs -f | grep -i auth", Colors.GREEN)
    print()
    print("3. Look for this message:")
    print("   ✅ Cookie-based authentication successful")
    print()
    print_colored("💡 Tip:", Colors.YELLOW)
    print("   - Cookies typically last 8-12 hours")
    print("   - Run this script again when they expire")
    print("   - You can automate this with a cron job")
    print()

if __name__ == "__main__":
    main()

# Made with Bob
