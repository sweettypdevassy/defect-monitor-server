"""
Browser Cookie Authentication Module
Automatically extracts cookies from Chrome browser for IBM W3ID authentication
Solves the passkey/MFA authentication problem by reading cookies from logged-in Chrome
"""

import browser_cookie3
import requests
import logging
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class BrowserCookieAuthenticator:
    """Authenticates using cookies from Chrome browser"""
    
    def __init__(self, domain: str = "libh-proxy1.fyre.ibm.com"):
        """
        Initialize browser cookie authenticator
        
        Args:
            domain: Domain to extract cookies from
        """
        self.domain = domain
        self.session: Optional[requests.Session] = None
        self.last_refresh: Optional[datetime] = None
        
    def get_cookies_from_chrome(self) -> Dict[str, str]:
        """
        Extract cookies from Chrome browser
        
        Returns:
            Dictionary of cookie name-value pairs
        """
        try:
            logger.info(f"🔍 Extracting cookies from Chrome for domain: {self.domain}")
            
            # Get cookies from Chrome (automatically handles decryption)
            cj = browser_cookie3.chrome(domain_name=self.domain)
            
            # Convert to dictionary
            cookies = {}
            cookie_count = 0
            for cookie in cj:
                cookies[cookie.name] = cookie.value
                cookie_count += 1
                logger.debug(f"Found cookie: {cookie.name} (expires: {cookie.expires})")
            
            if cookie_count > 0:
                logger.info(f"✅ Extracted {cookie_count} cookies from Chrome")
                
                # Log important cookies (without values for security)
                important_cookies = ['LtpaToken2', 'JSESSIONID', 'PD-S-SESSION-ID', 
                                   'mod_auth_openidc_session', 'w3idSSO']
                found_important = [name for name in important_cookies if name in cookies]
                if found_important:
                    logger.info(f"📋 Found important cookies: {', '.join(found_important)}")
            else:
                logger.warning("⚠️ No cookies found in Chrome - is Chrome logged in?")
            
            return cookies
            
        except PermissionError as e:
            logger.error(f"❌ Permission denied accessing Chrome cookies: {e}")
            logger.error("💡 Tip: Ensure the script runs as the same user that runs Chrome")
            return {}
        except FileNotFoundError as e:
            logger.error(f"❌ Chrome cookie database not found: {e}")
            logger.error("💡 Tip: Ensure Chrome is installed and has been run at least once")
            return {}
        except Exception as e:
            logger.error(f"❌ Failed to extract cookies from Chrome: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return {}
    
    def create_authenticated_session(self) -> Optional[requests.Session]:
        """
        Create session with Chrome cookies
        
        Returns:
            Authenticated requests.Session or None if failed
        """
        try:
            # Get fresh cookies from Chrome
            cookies = self.get_cookies_from_chrome()
            
            if not cookies:
                logger.error("❌ No cookies found in Chrome - cannot authenticate")
                logger.error("💡 Please ensure:")
                logger.error("   1. Chrome is running with persistent profile")
                logger.error("   2. You are logged in to IBM system in Chrome")
                logger.error("   3. Chrome profile path is correct")
                return None
            
            # Create session
            session = requests.Session()
            
            # Set headers to mimic browser
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            })
            
            # Add cookies to session
            for name, value in cookies.items():
                session.cookies.set(name, value, domain=self.domain)
            
            logger.info(f"🔐 Created session with {len(cookies)} cookies")
            
            # Verify authentication
            if self._verify_session(session):
                self.session = session
                self.last_refresh = datetime.now()
                logger.info("✅ Browser cookie authentication successful")
                return session
            else:
                logger.error("❌ Browser cookie authentication failed - cookies may be expired")
                logger.error("💡 Try refreshing the IBM page in Chrome to renew cookies")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating authenticated session: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _verify_session(self, session: requests.Session, max_retries: int = 3) -> bool:
        """
        Verify session works by testing API call
        
        Args:
            session: Session to verify
            max_retries: Number of retry attempts
            
        Returns:
            True if session is valid, False otherwise
        """
        import time
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying verification (attempt {attempt + 1}/{max_retries}) in {wait_time}s...")
                    time.sleep(wait_time)
                
                # Test with actual API call
                test_url = f"https://{self.domain}/buildBreakReport/rest2/defects/buildbreak/fas"
                response = session.get(
                    test_url,
                    params={"fas": "Messaging"},  # Use a real component for testing
                    timeout=60,
                    verify=False,
                    headers={'Accept': 'application/json'}
                )
                
                # Check if redirected to login
                if "login" in response.url.lower():
                    logger.error("Session verification failed: redirected to login page")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                # Check for 401 Unauthorized
                if response.status_code == 401:
                    logger.error("Session verification failed: 401 Unauthorized")
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                # Check if we got valid response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, (list, dict)):
                            logger.info("✅ Session verified successfully")
                            return True
                    except ValueError:
                        logger.warning("Response is not valid JSON")
                        if attempt < max_retries - 1:
                            continue
                
                logger.warning(f"Unexpected response: status={response.status_code}, url={response.url}")
                if attempt < max_retries - 1:
                    continue
                return False
                
            except requests.exceptions.Timeout:
                logger.warning(f"Session verification timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
                return False
            except Exception as e:
                logger.error(f"Session verification error: {e}")
                if attempt < max_retries - 1:
                    continue
                return False
        
        return False
    
    def refresh_cookies(self) -> bool:
        """
        Refresh cookies from Chrome and update session
        
        Returns:
            True if refresh successful, False otherwise
        """
        logger.info("🔄 Refreshing cookies from Chrome...")
        new_session = self.create_authenticated_session()
        
        if new_session:
            self.session = new_session
            logger.info("✅ Cookies refreshed successfully")
            return True
        else:
            logger.error("❌ Failed to refresh cookies")
            return False
    
    def get_session_info(self) -> Dict:
        """
        Get information about current session
        
        Returns:
            Dictionary with session information
        """
        if not self.session or not self.last_refresh:
            return {
                "authenticated": False,
                "last_refresh": None,
                "cookie_count": 0,
                "source": "browser_cookies"
            }
        
        cookie_count = len(self.session.cookies)
        
        return {
            "authenticated": True,
            "last_refresh": self.last_refresh.isoformat(),
            "cookie_count": cookie_count,
            "source": "browser_cookies",
            "domain": self.domain
        }


# Made with Bob