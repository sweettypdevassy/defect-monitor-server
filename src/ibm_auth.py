"""
IBM W3ID Authentication Module
Handles authentication with IBM systems and session management
"""

import requests
import urllib3
import logging
import threading
import asyncio
from datetime import datetime, timedelta
from cookie_monitor import get_cookie_monitor
from browser_manager import get_browser_manager
from typing import Optional, Dict

# Disable SSL warnings for IBM self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class IBMAuthenticator:
    """Handles IBM W3ID authentication and session management"""
    
    def __init__(self, username: str, password: str, session_timeout: int = 7200, max_retries: int = 3,
                 auth_method: str = "password", cookies: Optional[Dict[str, str]] = None):
        self.username = username
        self.password = password
        self.session_timeout = session_timeout
        self.max_retries = max_retries
        self.auth_method = auth_method  # "password" or "cookies"
        self.cookies = cookies or {}
        self.session: Optional[requests.Session] = None
        self.last_login: Optional[datetime] = None
        self.login_url = "https://login.w3.ibm.com/login"
        
        # Thread lock to prevent concurrent authentication attempts
        self._auth_lock = threading.Lock()
        self._is_authenticating = False
        
        # If using cookies, initialize session immediately
        if self.auth_method == "cookies" and self.cookies:
            self._init_session_with_cookies()
        
    def _init_session_with_cookies(self):
        """Initialize session with provided cookies"""
        try:
            self.session = requests.Session()
            
            # Set headers
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            
            # Add cookies to session
            for name, value in self.cookies.items():
                self.session.cookies.set(name, value)
            
            self.last_login = datetime.now()
            logger.info(f"✅ Session initialized with {len(self.cookies)} cookies")
            
        except Exception as e:
            logger.error(f"Error initializing session with cookies: {e}")
    
    def is_session_valid(self) -> bool:
        """Check if current session is still valid"""
        if not self.session or not self.last_login:
            return False
        
        # If session is less than 5 minutes old, assume it's valid (skip validation)
        elapsed = (datetime.now() - self.last_login).total_seconds()
        if elapsed < 300:  # 5 minutes
            return True
        
        # For older sessions, test with a simple request (don't rely on timeout)
        try:
            test_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas"
            response = self.session.get(test_url, params={"component": "test"}, timeout=60, verify=False)
            
            # Check if we got redirected to login page
            if "login" in response.url.lower() or response.status_code == 401:
                logger.info("Session invalid (got 401 or redirect), needs re-authentication")
                return False
            
            return True
        except requests.exceptions.Timeout:
            # On timeout, assume session is still valid
            # This prevents unnecessary re-authentication when server is slow
            logger.debug("Session validation timeout - assuming valid (persistent browser maintains session)")
            return True
        except Exception as e:
            logger.debug(f"Session validation failed: {e}")
            # On other errors, assume valid if session is recent
            if elapsed < 600:
                logger.debug("Session validation error, but session is recent - assuming valid")
                return True
            return False
    
    def _authenticate_with_retry(self, force_refresh: bool = False) -> bool:
        """Authenticate with retry logic
        
        Args:
            force_refresh: If True, force page refresh on first attempt
        """
        import time
        
        # If using cookies, just verify they work
        if self.auth_method == "cookies":
            logger.info("Using cookie-based authentication")
            if self._verify_authentication():
                logger.info("✅ Cookie-based authentication successful")
                return True
            else:
                logger.error("❌ Cookie-based authentication failed - cookies may be expired")
                logger.warning("🔄 Attempting automatic cookie refresh...")
                
                # Try to refresh cookies automatically
                cookie_monitor = get_cookie_monitor()
                if cookie_monitor.refresh_cookies_now():
                    logger.info("✅ Cookies refreshed successfully - reloading configuration...")
                    # Reload config to get new cookies
                    try:
                        import yaml
                        with open('config/config.yaml', 'r') as f:
                            config = yaml.safe_load(f)
                        self.cookies = config.get('ibm', {}).get('cookies', {})
                        self._init_session_with_cookies()
                        
                        # Verify new cookies work
                        if self._verify_authentication():
                            logger.info("✅ Authentication successful with refreshed cookies!")
                            return True
                        else:
                            logger.error("❌ Refreshed cookies still don't work")
                            return False
                    except Exception as e:
                        logger.error(f"❌ Error reloading config after cookie refresh: {e}")
                        return False
                else:
                    logger.error("❌ Failed to refresh cookies automatically")
                    return False
        
        # Password-based authentication with retry
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Authentication attempt {attempt}/{self.max_retries}")
                # Force refresh on first attempt if requested, or on retry attempts
                should_refresh = force_refresh or (attempt > 1)
                if self._do_authenticate(force_refresh=should_refresh):
                    return True
                
                if attempt < self.max_retries:
                    wait_time = attempt * 2  # Exponential backoff: 2s, 4s, 6s
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Authentication attempt {attempt} failed: {e}")
                if attempt < self.max_retries:
                    wait_time = attempt * 2
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        logger.error(f"All {self.max_retries} authentication attempts failed")
        return False
    
    def authenticate(self) -> bool:
        """
        Authenticate with IBM W3ID (public method with retry)
        Returns True if successful, False otherwise
        """
        return self._authenticate_with_retry()
    
    def _do_authenticate(self, force_refresh: bool = False) -> bool:
        """
        Authenticate with IBM Build Break Report using Playwright
        Since cookies expire in 10 minutes and W3ID uses JavaScript auth,
        we must use browser automation for every authentication
        
        Args:
            force_refresh: If True, force page refresh to get fresh cookies
            
        Returns True if successful, False otherwise
        """
        try:
            logger.info(f"Authenticating with IBM Build Break Report using Playwright for user: {self.username}")
            
            # Use Playwright to login and get cookies (with optional force refresh)
            cookies = self._playwright_login(force_refresh=force_refresh)
            
            if not cookies:
                logger.error("❌ Playwright login failed")
                return False
            
            # Create session with cookies from Playwright
            self.session = requests.Session()
            
            # Set headers to match browser
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            })
            
            # Add cookies to session with proper domain handling
            for cookie in cookies:
                # Handle domain - remove leading dot if present
                domain = cookie.get('domain', '')
                if domain.startswith('.'):
                    domain = domain[1:]
                
                self.session.cookies.set(
                    cookie['name'],
                    cookie['value'],
                    domain=domain,
                    path=cookie.get('path', '/'),
                    secure=cookie.get('secure', False),
                    rest={'HttpOnly': cookie.get('httpOnly', False)}
                )
            
            logger.info(f"✅ Added {len(cookies)} cookies to session")
            
            # Verify authentication
            if self._verify_authentication():
                self.last_login = datetime.now()
                logger.info("✅ IBM Build Break Report authentication successful")
                return True
            else:
                logger.error("❌ Authentication verification failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ IBM authentication error: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _playwright_login(self, force_refresh: bool = False):
        """Use async browser manager to login and extract cookies
        
        Args:
            force_refresh: If True, force page refresh to get fresh cookies
        """
        try:
            # Get browser manager and use its persistent event loop
            browser_manager = get_browser_manager()
            loop = browser_manager._ensure_event_loop()
            
            # Run async login using the browser manager's event loop
            result = loop.run_until_complete(self._async_playwright_login(force_refresh=force_refresh))
            return result
            
        except Exception as e:
            logger.error(f"Error in Playwright login: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None
    
    async def _async_playwright_login(self, force_refresh: bool = False):
        """Async method to use browser manager
        
        Args:
            force_refresh: If True, force page refresh to get fresh cookies
        """
        try:
            browser_manager = get_browser_manager()
            
            # Start browser if not already started
            await browser_manager.start(self.username, self.password)
            
            # Login if needed with optional force refresh
            success = await browser_manager.login_if_needed(force_refresh=force_refresh)
            
            if not success:
                logger.error("❌ Browser login failed")
                return None
            
            # Get cookies from browser
            cookies = await browser_manager.get_cookies()
            
            if cookies:
                logger.info(f"✅ Extracted {len(cookies)} cookies from persistent browser")
                return cookies
            else:
                logger.error("❌ Failed to extract cookies")
                return None
                
        except Exception as e:
            logger.error(f"Error in async Playwright login: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _verify_authentication(self, max_retries: int = 3) -> bool:
        """Verify that authentication was successful by testing API with retry logic"""
        import time
        
        for attempt in range(max_retries):
            try:
                if not self.session:
                    logger.error("No session available for verification")
                    return False
                
                if attempt > 0:
                    wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s
                    logger.info(f"Retrying authentication verification (attempt {attempt + 1}/{max_retries}) in {wait_time}s...")
                    time.sleep(wait_time)
                
                # Test with actual API call using correct URL format
                test_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas?fas=Messaging"
                response = self.session.get(
                    test_url,
                    timeout=60,  # Increased to 60 seconds for slow server
                    headers={'Accept': 'application/json'},
                    verify=False  # Disable SSL verification for IBM self-signed certs
                )
                
                # Check if we're redirected to login (authentication failed)
                if "login" in response.url.lower():
                    logger.error("Authentication verification failed: redirected to login")
                    return False
                
                # Check if we got valid JSON response (not login redirect)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Verify it's actual defect data, not error page
                        if isinstance(data, list) or isinstance(data, dict):
                            logger.info("✅ Cookie-based authentication successful")
                            return True
                    except ValueError:
                        logger.error("Response is not valid JSON")
                        if attempt < max_retries - 1:
                            continue
                        return False
                
                logger.error(f"Authentication verification failed: status {response.status_code}")
                logger.debug(f"Response URL: {response.url}")
                if attempt < max_retries - 1:
                    continue
                return False
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"Authentication verification timeout (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    continue
                logger.error("❌ Cookie-based authentication failed - server timeout after all retries")
                return False
            except Exception as e:
                logger.error(f"Authentication verification error: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
                if attempt < max_retries - 1:
                    continue
                return False
        
        return False
    
    def get_session(self) -> Optional[requests.Session]:
        """
        Get authenticated session, re-authenticating if necessary (thread-safe)
        Returns None if authentication fails
        """
        # Check if session is valid without lock (fast path)
        if self.is_session_valid():
            return self.session
        
        # Need to authenticate - acquire lock to prevent concurrent auth attempts
        with self._auth_lock:
            # Double-check after acquiring lock (another thread might have authenticated)
            if self.is_session_valid():
                return self.session
            
            # Check if another thread is currently authenticating
            if self._is_authenticating:
                logger.debug("Another thread is authenticating, waiting...")
                return self.session  # Return current session, will retry if needed
            
            self._is_authenticating = True
            try:
                logger.info("Session invalid or expired, re-authenticating...")
                if not self.authenticate():
                    return None
                return self.session
            finally:
                self._is_authenticating = False
    
    def refresh_session(self) -> bool:
        """Force refresh the session"""
        logger.info("Forcing session refresh")
        return self.authenticate()
    
    def get_session_info(self) -> Dict:
        """Get information about current session"""
        if not self.session or not self.last_login:
            return {
                "authenticated": False,
                "last_login": None,
                "session_age": None,
                "expires_in": None
            }
        
        session_age = (datetime.now() - self.last_login).total_seconds()
        expires_in = self.session_timeout - session_age
        
        return {
            "authenticated": True,
            "last_login": self.last_login.isoformat(),
            "session_age": int(session_age),
            "expires_in": int(expires_in) if expires_in > 0 else 0,
            "is_valid": self.is_session_valid()
        }

# Made with Bob

    def authenticate_jazz_rtc(self) -> bool:
        """
        Authenticate with Jazz/RTC system using username/password
        Uses lock to prevent concurrent authentication attempts
        """
        # Use lock to prevent multiple threads from authenticating simultaneously
        with self._auth_lock:
            try:
                if not self.session:
                    logger.debug("No session exists, creating new session")
                    self.session = requests.Session()
                    self.session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                    })
                
                if not self.username or not self.password:
                    logger.error("No Jazz/RTC credentials configured")
                    return False
                
                # Jazz/RTC authentication endpoint
                jazz_auth_url = "https://wasrtc.hursley.ibm.com:9443/jazz/authenticated/identity"
                
                # Step 1: Check if already authenticated (silent check)
                try:
                    initial_response = self.session.get(
                        jazz_auth_url,
                        timeout=10,
                        verify=False,
                        allow_redirects=True
                    )
                    
                    # Check if already authenticated (got JSON)
                    if initial_response.status_code == 200:
                        content_type = initial_response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            try:
                                data = initial_response.json()
                                # Already authenticated - return silently
                                return True
                            except:
                                pass
                except:
                    pass
                
                # Need to authenticate
                logger.info("🔐 Authenticating with Jazz/RTC...")
                
                # Step 2: Submit login credentials
                login_url = "https://wasrtc.hursley.ibm.com:9443/jazz/j_security_check"
                
                login_data = {
                    'j_username': self.username,
                    'j_password': self.password
                }
                
                login_response = self.session.post(
                    login_url,
                    data=login_data,
                    timeout=30,
                    verify=False,
                    allow_redirects=True,
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Referer': 'https://wasrtc.hursley.ibm.com:9443/jazz/'
                    }
                )
                
                # Step 3: Verify authentication
                verify_response = self.session.get(
                    jazz_auth_url,
                    timeout=30,
                    verify=False,
                    allow_redirects=False
                )
                
                if verify_response.status_code == 200:
                    content_type = verify_response.headers.get('content-type', '')
                    # Jazz/RTC returns 'text/json' instead of 'application/json'
                    if 'json' in content_type.lower():
                        try:
                            data = verify_response.json()
                            user_id = data.get('userId', 'unknown')
                            logger.info(f"✅ Jazz/RTC authenticated successfully as {user_id}")
                            return True
                        except Exception as e:
                            logger.error(f"Failed to parse JSON: {e}")
                
                logger.error(f"Jazz/RTC authentication failed - Status: {verify_response.status_code}")
                return False
                
            except Exception as e:
                logger.error(f"Error authenticating with Jazz/RTC: {e}")
                return False
