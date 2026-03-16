#!/usr/bin/env python3
"""
Test script for browser cookie authentication
Verifies that cookies can be extracted from Chrome and used for authentication
"""

import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_browser_cookie_import():
    """Test if browser-cookie3 can be imported"""
    try:
        import browser_cookie3
        logger.info("✅ browser-cookie3 imported successfully")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import browser-cookie3: {e}")
        logger.error("💡 Install with: pip install browser-cookie3")
        return False

def test_cookie_extraction():
    """Test extracting cookies from Chrome"""
    try:
        import browser_cookie3
        
        domain = "libh-proxy1.fyre.ibm.com"
        logger.info(f"🔍 Extracting cookies from Chrome for domain: {domain}")
        
        # Get cookies
        cj = browser_cookie3.chrome(domain_name=domain)
        cookies = list(cj)
        
        if not cookies:
            logger.warning("⚠️  No cookies found in Chrome")
            logger.warning("💡 Please ensure:")
            logger.warning("   1. Chrome is running")
            logger.warning("   2. You are logged in to IBM system in Chrome")
            logger.warning("   3. Chrome profile path is correct")
            return False
        
        logger.info(f"✅ Found {len(cookies)} cookies")
        
        # Check for important cookies
        cookie_names = [c.name for c in cookies]
        important_cookies = ['LtpaToken2', 'JSESSIONID', 'PD-S-SESSION-ID', 
                           'mod_auth_openidc_session']
        
        found_important = [name for name in important_cookies if name in cookie_names]
        if found_important:
            logger.info(f"📋 Found important cookies: {', '.join(found_important)}")
        else:
            logger.warning("⚠️  No important authentication cookies found")
            logger.warning(f"Available cookies: {', '.join(cookie_names[:5])}...")
        
        # Display cookie details (without values for security)
        logger.info("\n📊 Cookie Details:")
        for cookie in cookies[:10]:  # Show first 10
            logger.info(f"   - {cookie.name}: expires={cookie.expires}, secure={cookie.secure}")
        
        if len(cookies) > 10:
            logger.info(f"   ... and {len(cookies) - 10} more cookies")
        
        return True
        
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {e}")
        logger.error("💡 Ensure script runs as same user that runs Chrome")
        return False
    except FileNotFoundError as e:
        logger.error(f"❌ Chrome cookie database not found: {e}")
        logger.error("💡 Ensure Chrome is installed and has been run at least once")
        return False
    except Exception as e:
        logger.error(f"❌ Error extracting cookies: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

def test_authentication():
    """Test authentication using browser cookies"""
    try:
        from src.browser_cookie_auth import BrowserCookieAuthenticator
        
        logger.info("\n🔐 Testing authentication with browser cookies...")
        
        # Create authenticator
        auth = BrowserCookieAuthenticator(domain="libh-proxy1.fyre.ibm.com")
        
        # Create session
        session = auth.create_authenticated_session()
        
        if session:
            logger.info("✅ Authentication successful!")
            
            # Get session info
            info = auth.get_session_info()
            logger.info(f"📊 Session Info:")
            logger.info(f"   - Authenticated: {info['authenticated']}")
            logger.info(f"   - Cookie count: {info['cookie_count']}")
            logger.info(f"   - Source: {info['source']}")
            logger.info(f"   - Domain: {info['domain']}")
            
            return True
        else:
            logger.error("❌ Authentication failed")
            return False
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("💡 Ensure src/browser_cookie_auth.py exists")
        return False
    except Exception as e:
        logger.error(f"❌ Authentication test failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

def main():
    """Run all tests"""
    logger.info("🧪 Browser Cookie Authentication Test")
    logger.info("=" * 50)
    
    tests = [
        ("Import Test", test_browser_cookie_import),
        ("Cookie Extraction Test", test_cookie_extraction),
        ("Authentication Test", test_authentication),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} ERROR: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 Test Summary:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Browser cookie authentication is ready.")
        logger.info("\n💡 Next steps:")
        logger.info("   1. Update config/config.yaml with auth_method: 'browser_cookies'")
        logger.info("   2. Restart the defect monitor: docker-compose restart")
        logger.info("   3. Check logs: docker-compose logs -f")
        return 0
    else:
        logger.error("❌ Some tests failed. Please fix issues before proceeding.")
        logger.error("\n💡 Common solutions:")
        logger.error("   - Ensure Chrome is running with persistent profile")
        logger.error("   - Login to IBM system in Chrome")
        logger.error("   - Install missing dependencies: pip install browser-cookie3")
        return 1

if __name__ == "__main__":
    sys.exit(main())

# Made with Bob