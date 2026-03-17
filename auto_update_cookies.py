#!/usr/bin/env python3
"""
Automatic Cookie Updater for config.yaml
Extracts LtpaToken2 and mod_auth_openidc_session from Chrome and updates config.yaml
Uses direct SQLite access to bypass browser-cookie3 keyring issues
"""

import sys
import os
import yaml
import sqlite3
import shutil
import tempfile
import glob
from datetime import datetime
from pathlib import Path

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
    Extract cookies from Chrome browser using direct SQLite access
    This bypasses browser-cookie3 issues with keyring/DBus
    
    Args:
        domain: Domain to extract cookies from
        
    Returns:
        Tuple of (ltpa_token, session_id) or (None, None) if failed
    """
    try:
        print_colored(f"🔍 Extracting cookies from Chrome for domain: {domain}", Colors.BLUE)
        
        # Try multiple possible cookie file locations
        possible_paths = [
            "/home/abhi/.config/google-chrome/Default/Cookies",
            os.path.expanduser("~/.config/google-chrome/Default/Cookies"),
            os.path.join(os.path.expanduser("~"), ".config/google-chrome/Default/Cookies"),
        ]
        
        cookie_file = None
        for path in possible_paths:
            if os.path.exists(path):
                cookie_file = path
                print_colored(f"📂 Found cookie file: {cookie_file}", Colors.GREEN)
                break
        
        if not cookie_file:
            print_colored("❌ Cookie file not found in default locations", Colors.RED)
            print_colored("💡 Searching for Chrome cookie files...", Colors.YELLOW)
            cookie_files = glob.glob(os.path.expanduser("~/.config/google-chrome/**/Cookies"), recursive=True)
            cookie_files += glob.glob("/home/*/.config/google-chrome/**/Cookies", recursive=True)
            if cookie_files:
                cookie_file = cookie_files[0]
                print_colored(f"✅ Using: {cookie_file}", Colors.GREEN)
            else:
                print_colored("❌ No Chrome cookie files found", Colors.RED)
                print_colored("💡 Please ensure Chrome is installed and has been run at least once", Colors.YELLOW)
                return None, None
        
        # Copy DB to temp to avoid lock issues
        print_colored("📋 Copying cookie database to temp location...", Colors.BLUE)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp_cookie = tmp.name
        
        shutil.copy2(cookie_file, tmp_cookie)
        print_colored(f"✅ Copied to: {tmp_cookie}", Colors.GREEN)
        
        # Read cookies directly from SQLite database
        print_colored("🔍 Reading cookies from database...", Colors.BLUE)
        conn = sqlite3.connect(tmp_cookie)
        cursor = conn.cursor()
        
        # Query for cookies matching the domain
        query = """
        SELECT name, value, encrypted_value
        FROM cookies 
        WHERE host_key LIKE ?
        """
        
        cursor.execute(query, (f"%{domain}%",))
        rows = cursor.fetchall()
        
        conn.close()
        
        # Clean up temp file
        try:
            os.remove(tmp_cookie)
        except:
            pass
        
        if not rows:
            print_colored("⚠️  No cookies found in Chrome for this domain", Colors.YELLOW)
            print_colored("\n💡 Please ensure:", Colors.YELLOW)
            print("   1. Chrome is running")
            print("   2. You are logged in to: https://libh-proxy1.fyre.ibm.com/buildBreakReport/")
            print("   3. The page has fully loaded")
            return None, None
        
        print_colored(f"✅ Found {len(rows)} cookies in database", Colors.GREEN)
        
        # Find required cookies
        ltpa_token = None
        session_id = None
        
        for name, value, encrypted_value in rows:
            # Use value if available, otherwise note that it's encrypted
            cookie_value = value if value else None
            
            if name == 'LtpaToken2':
                if cookie_value:
                    ltpa_token = cookie_value
                    print_colored(f"✅ Found LtpaToken2: {ltpa_token[:50]}...", Colors.GREEN)
                elif encrypted_value:
                    print_colored("⚠️  LtpaToken2 found but is encrypted", Colors.YELLOW)
                    print_colored("💡 This means Chrome is using encrypted storage", Colors.YELLOW)
                    
            elif name == 'mod_auth_openidc_session':
                if cookie_value:
                    session_id = cookie_value
                    print_colored(f"✅ Found mod_auth_openidc_session: {session_id}", Colors.GREEN)
                elif encrypted_value:
                    print_colored("⚠️  mod_auth_openidc_session found but is encrypted", Colors.YELLOW)
        
        if not ltpa_token:
            print_colored("❌ LtpaToken2 not found or is encrypted", Colors.RED)
        if not session_id:
            print_colored("❌ mod_auth_openidc_session not found or is encrypted", Colors.RED)
        
        if ltpa_token and session_id:
            return ltpa_token, session_id
        else:
            print_colored("\n⚠️  Missing required cookies or cookies are encrypted", Colors.YELLOW)
            print_colored("💡 Possible reasons:", Colors.YELLOW)
            print("   1. Not logged in to IBM site")
            print("   2. Session expired")
            print("   3. Chrome is using encrypted cookie storage (v80+)")
            print()
            print_colored("🔧 Workaround: Extract cookies from your Mac and transfer config.yaml", Colors.YELLOW)
            return None, None
            
    except sqlite3.Error as e:
        print_colored(f"❌ SQLite error: {e}", Colors.RED)
        print_colored("💡 Cookie database may be corrupted or locked", Colors.YELLOW)
        return None, None
    except PermissionError as e:
        print_colored(f"❌ Permission denied: {e}", Colors.RED)
        print_colored("💡 Run as the same user that runs Chrome", Colors.YELLOW)
        return None, None
    except FileNotFoundError as e:
        print_colored(f"❌ File not found: {e}", Colors.RED)
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
