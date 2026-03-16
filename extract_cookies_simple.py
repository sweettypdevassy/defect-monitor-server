#!/usr/bin/env python3
"""
Simple cookie extraction script for debugging
"""
import sys

print("🔍 Checking browser-cookie3 installation...")
try:
    import browser_cookie3
    print("✅ browser-cookie3 is installed")
except ImportError as e:
    print(f"❌ browser-cookie3 not installed: {e}")
    print("Install with: pip3 install browser-cookie3")
    sys.exit(1)

print("\n🔍 Attempting to extract cookies from Chrome...")
try:
    domain = "libh-proxy1.fyre.ibm.com"
    print(f"Domain: {domain}")
    
    # Try to get cookies
    cj = browser_cookie3.chrome(domain_name=domain)
    cookies = list(cj)
    
    print(f"\n📊 Found {len(cookies)} total cookies")
    
    if len(cookies) == 0:
        print("\n⚠️  No cookies found!")
        print("\nPossible reasons:")
        print("1. Chrome is not running on this system")
        print("2. Chrome profile path is incorrect")
        print("3. Not logged into IBM site in Chrome")
        print("4. Chrome is running as a different user")
        print("\n💡 Try running Chrome with:")
        print("   google-chrome --user-data-dir=$HOME/chrome-profile")
        sys.exit(1)
    
    # Display all cookies
    print("\n📋 All cookies found:")
    for cookie in cookies:
        print(f"   - {cookie.name}")
    
    # Look for important cookies
    print("\n🔍 Looking for authentication cookies...")
    ltpa_token = None
    session_id = None
    
    for cookie in cookies:
        if cookie.name == 'LtpaToken2':
            ltpa_token = cookie.value
            if ltpa_token:
                print(f"✅ Found LtpaToken2: {ltpa_token[:50]}...")
        elif cookie.name == 'mod_auth_openidc_session':
            session_id = cookie.value
            if session_id:
                print(f"✅ Found mod_auth_openidc_session: {session_id}")
    
    if not ltpa_token:
        print("❌ LtpaToken2 not found")
    if not session_id:
        print("❌ mod_auth_openidc_session not found")
    
    if ltpa_token and session_id:
        print("\n✅ All required cookies found!")
        print("\n📝 Add these to config/config.yaml:")
        print(f"\nLtpaToken2: \"{ltpa_token}\"")
        print(f"mod_auth_openidc_session: \"{session_id}\"")
    else:
        print("\n⚠️  Missing required cookies")
        print("Please ensure you're logged into IBM site in Chrome")
        
except PermissionError as e:
    print(f"\n❌ Permission denied: {e}")
    print("💡 Run as the same user that runs Chrome")
    sys.exit(1)
except FileNotFoundError as e:
    print(f"\n❌ Chrome cookie database not found: {e}")
    print("💡 Chrome may not be installed or never run")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)

# Made with Bob
