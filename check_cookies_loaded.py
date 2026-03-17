#!/usr/bin/env python3
"""
Check what cookies are actually being loaded from config.yaml
"""

import yaml
from pathlib import Path

def check_cookies():
    """Check cookies in config.yaml"""
    config_path = Path("config/config.yaml")
    
    print("=" * 70)
    print("🔍 Checking cookies in config.yaml")
    print("=" * 70)
    print()
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    print(f"✅ Config file found: {config_path}")
    print()
    
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Get cookies
    ibm_config = config.get('ibm', {})
    auth_method = ibm_config.get('auth_method', 'password')
    cookies = ibm_config.get('cookies', {})
    
    print(f"Auth method: {auth_method}")
    print(f"Number of cookies: {len(cookies)}")
    print()
    
    if cookies:
        print("📋 Cookies found:")
        print("-" * 70)
        for name, value in cookies.items():
            # Show first 50 chars of value
            display_value = value[:50] + "..." if len(value) > 50 else value
            print(f"  {name}: {display_value}")
        print()
        
        # Check for required cookies
        required = ['LtpaToken2', 'mod_auth_openidc_session']
        print("✅ Required cookies:")
        for req in required:
            if req in cookies:
                print(f"  ✓ {req}")
            else:
                print(f"  ✗ {req} - MISSING!")
        print()
        
        # Check for OpenID Connect cookies
        oidc_cookies = [name for name in cookies.keys() if 'mod_auth_openidc' in name]
        print(f"🔐 OpenID Connect cookies: {len(oidc_cookies)}")
        for name in oidc_cookies:
            print(f"  • {name}")
        print()
        
        # Check for other auth cookies
        other_cookies = [name for name in cookies.keys() 
                        if name not in required and 'mod_auth_openidc' not in name]
        print(f"🍪 Other cookies: {len(other_cookies)}")
        for name in other_cookies:
            print(f"  • {name}")
    else:
        print("❌ No cookies found in config!")
    
    print()
    print("=" * 70)

if __name__ == "__main__":
    check_cookies()

# Made with Bob
