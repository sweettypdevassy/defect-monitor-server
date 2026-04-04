"""
IBM W3ID Authentication Module
Handles authentication with IBM systems and session management
"""

import requests
import urllib3
import logging
import threading
from datetime import datetime, timedelta
from cookie_monitor import get_cookie_monitor
from typing import Optional, Dict

# Disable SSL warnings for IBM self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class IBMAuthenticator:
    """Handles IBM W3ID authentication and session management"""
    
    # Class-level variables to keep browser alive
    _playwright_instance = None
    _browser_context = None
    _browser_page = None
    _browser_lock = threading.Lock()
    
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
        
        # Check if session has expired based on time
        elapsed = (datetime.now() - self.last_login).total_seconds()
        if elapsed > self.session_timeout:
            logger.info("Session expired based on timeout, needs re-authentication")
            return False
        
        # If session is less than 5 minutes old, assume it's valid (skip validation)
        if elapsed < 300:  # 5 minutes
            return True
        
        # For older sessions, test with a simple request
        try:
            test_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas"
            response = self.session.get(test_url, params={"component": "test"}, timeout=60, verify=False)
            
            # Check if we got redirected to login page
            if "login" in response.url.lower() or response.status_code == 401:
                logger.info("Session invalid (got 401 or redirect), needs re-authentication")
                return False
            
            return True
        except requests.exceptions.Timeout:
            # On timeout, assume session is still valid if not too old
            # This prevents unnecessary re-authentication when server is slow
            if elapsed < 600:  # Less than 10 minutes old
                logger.debug("Session validation timeout, but session is recent - assuming valid")
                return True
            else:
                logger.debug("Session validation timeout and session is old - will re-authenticate")
                return False
        except Exception as e:
            logger.debug(f"Session validation failed: {e}")
            # On other errors, assume valid if session is recent
            if elapsed < 600:
                logger.debug("Session validation error, but session is recent - assuming valid")
                return True
            return False
    
    def _authenticate_with_retry(self) -> bool:
        """Authenticate with retry logic"""
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
                if self._do_authenticate():
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
    
    def _do_authenticate(self) -> bool:
        """
        Authenticate with IBM Build Break Report using Playwright
        Since cookies expire in 10 minutes and W3ID uses JavaScript auth,
        we must use browser automation for every authentication
        Returns True if successful, False otherwise
        """
        try:
            logger.info(f"Authenticating with IBM Build Break Report using Playwright for user: {self.username}")
            
            # Use Playwright to login and get cookies
            cookies = self._playwright_login()
            
            if not cookies:
                logger.error("❌ Playwright login failed")
                return False
            
            # Create session with cookies from Playwright
            self.session = requests.Session()
            
            # Set headers
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            
            # Add cookies to session
            for cookie in cookies:
                self.session.cookies.set(
                    cookie['name'],
                    cookie['value'],
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/')
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
    
    def _playwright_login(self):
        """Use Playwright to login and extract cookies - KEEPS BROWSER ALIVE"""
        try:
            from playwright.sync_api import sync_playwright
            import re
            import os
            
            with self._browser_lock:
                # Check if browser is already running
                if self._browser_context and self._browser_page:
                    logger.info("♻️ Reusing existing browser session...")
                    try:
                        # Test if browser is still alive
                        self._browser_page.url
                        # Extract cookies from existing session
                        cookies = self._browser_context.cookies()
                        logger.info(f"✅ Extracted {len(cookies)} cookies from existing browser")
                        return cookies
                    except:
                        logger.warning("Existing browser session is dead, creating new one...")
                        self._browser_context = None
                        self._browser_page = None
                        self._playwright_instance = None
                
                # Launch new browser if needed
                if not self._playwright_instance:
                    logger.info("🌐 Launching persistent Playwright browser...")
                    
                    # Use persistent browser profile
                    user_data_dir = "/app/data/chrome_profile"
                    os.makedirs(user_data_dir, exist_ok=True)
                    
                    self._playwright_instance = sync_playwright().start()
                    
                    # Launch browser with persistent context (remembers login state)
                    self._browser_context = self._playwright_instance.chromium.launch_persistent_context(
                        user_data_dir,
                        headless=True,
                        ignore_https_errors=True,
                        args=['--disable-blink-features=AutomationControlled']
                    )
                    self._browser_page = self._browser_context.pages[0] if self._browser_context.pages else self._browser_context.new_page()
                
                context = self._browser_context
                page = self._browser_page
                
                try:
                    # Navigate to IBM page (will redirect to login if needed)
                    logger.info("📍 Navigating to Build Break Report to check session...")
                    page.goto("https://libh-proxy1.fyre.ibm.com/buildBreakReport/", wait_until="networkidle", timeout=30000)
                    
                    # Wait for page to load
                    page.wait_for_timeout(3000)
                    
                    current_url = page.url
                    logger.info(f"Current URL: {current_url}")
                    
                    # Check if we're ALREADY logged in (persistent profile worked!)
                    if "buildBreakReport" in current_url and "login" not in current_url.lower() and "auth" not in current_url.lower():
                        logger.info("✅ Already logged in! Persistent browser profile preserved the session")
                        logger.info("🎉 No 2FA needed - reusing trusted device session!")
                        # Extract cookies and return immediately
                        cookies = context.cookies()
                        logger.info(f"✅ Extracted {len(cookies)} cookies from existing session")
                        return cookies
                    
                    # Check if on login page (need to authenticate)
                    if "login" in current_url.lower() or "auth" in current_url.lower():
                        logger.info("🔑 Session expired or new device - need to authenticate...")
                        logger.info("🔑 On IBM login page...")
                        
                        # IMPORTANT: Click on "w3id Password" link first
                        logger.info("Step 1: Looking for 'w3id Password' link...")
                        try:
                            w3id_link = page.get_by_text("w3id Password")
                            w3id_link.wait_for(state="visible", timeout=10000)
                            w3id_link.click()
                            logger.info("✅ Clicked 'w3id Password' link")
                            
                            # Wait for login form to load
                            page.wait_for_load_state("networkidle")
                            page.wait_for_timeout(2000)
                        except Exception as e:
                            logger.warning(f"Could not find 'w3id Password' link: {e}")
                            logger.info("Continuing with direct login attempt...")
                        
                        # Step 2: Fill in email/username
                        logger.info("Step 2: Filling email/username...")
                        email_input = page.locator('input[type="email"], input[name="email"], input[id*="email"], input[name="username"]').first
                        email_input.wait_for(state="visible", timeout=10000)
                        email_input.fill(self.username)
                        logger.info("✅ Filled email field")
                        
                        # Step 3: Fill in password
                        logger.info("Step 3: Filling password...")
                        password_input = page.locator('input[type="password"], input[name="password"], input[id*="password"]').first
                        password_input.wait_for(state="visible", timeout=10000)
                        password_input.fill(self.password)
                        logger.info("✅ Filled password field")
                        
                        # Step 4: Click "Sign in" button
                        logger.info("Step 4: Clicking 'Sign in' button...")
                        try:
                            sign_in_button = page.get_by_role("button", name=re.compile("sign in", re.IGNORECASE))
                            sign_in_button.wait_for(state="visible", timeout=10000)
                            sign_in_button.click()
                            logger.info("✅ Clicked 'Sign in' button")
                        except Exception as e:
                            logger.warning(f"Could not find 'Sign in' button: {e}")
                            logger.info("Trying Enter key...")
                            page.keyboard.press('Enter')
                        
                        # Wait for navigation after login
                        logger.info("⏳ Waiting for login to complete...")
                        page.wait_for_timeout(5000)
                        page.wait_for_load_state("networkidle", timeout=30000)
                        
                        current_url = page.url
                        logger.info(f"After first login URL: {current_url}")
                        
                        # Check if we're on the 2FA/MFA selection page
                        if "authsvc" in current_url or "macotp" in current_url:
                            logger.info("🔐 On 2FA selection page, looking for 'Touch Approval' option...")
                            
                            # Take screenshot for debugging
                            try:
                                page.screenshot(path="/app/2fa_page.png")
                                logger.info("📸 Screenshot saved to /app/2fa_page.png")
                            except:
                                pass
                            
                            # Log page content for debugging
                            try:
                                page_text = page.inner_text('body')
                                logger.info(f"Page text preview: {page_text[:500]}")
                            except:
                                pass
                            
                            try:
                                # Look for "Touch Approval" option on the 2FA page
                                # Try multiple variations
                                selectors_to_try = [
                                    'text="Touch Approval"',
                                    'text="touch approval"',
                                    'text="Sweetty\'s S24 Ultra (Touch Approval)"',
                                    '[aria-label*="Touch Approval" i]',
                                    'button:has-text("Touch Approval")',
                                    'a:has-text("Touch Approval")',
                                    '.auth-method:has-text("Touch Approval")'
                                ]
                                
                                clicked = False
                                for selector in selectors_to_try:
                                    try:
                                        element = page.locator(selector).first
                                        if element.count() > 0:
                                            element.wait_for(state="visible", timeout=2000)
                                            element.click()
                                            logger.info(f"✅ Clicked 'Touch Approval' option using selector: {selector}")
                                            clicked = True
                                            break
                                    except:
                                        continue
                                
                                if not clicked:
                                    logger.warning("Could not find 'Touch Approval' option with any selector")
                                    raise Exception("Touch Approval option not found")
                                
                                # Wait for user to approve on phone
                                logger.info("📱 Waiting for approval on your phone...")
                                logger.info("⏳ Please approve the notification on Sweetty's S24 Ultra (60 seconds timeout)")
                                
                                # Wait for authentication to complete (longer timeout for phone approval)
                                try:
                                    page.wait_for_url("**/buildBreakReport**", timeout=60000)
                                    logger.info("✅ Successfully authenticated after phone approval!")
                                except Exception as e:
                                    logger.warning(f"Timeout waiting for phone approval: {e}")
                                    # Check if we're at least past the 2FA page
                                    current_url = page.url
                                    if "macotp" not in current_url:
                                        logger.info("✅ Moved past 2FA page, continuing...")
                                    else:
                                        raise Exception("Phone approval timeout or not completed")
                                
                            except Exception as e:
                                logger.warning(f"Could not complete 2FA with Touch Approval: {e}")
                        
                        # Check final URL
                        final_url = page.url
                        logger.info(f"Final URL: {final_url}")
                        
                        # If not at Build Break Report, try direct navigation
                        if "buildBreakReport" not in final_url:
                            logger.warning(f"⚠️  Not at Build Break Report, attempting direct navigation...")
                            page.goto("https://libh-proxy1.fyre.ibm.com/buildBreakReport/", wait_until="networkidle", timeout=30000)
                            logger.info(f"After direct navigation: {page.url}")
                    
                    # Extract cookies (DON'T close browser - keep it alive!)
                    cookies = context.cookies()
                    logger.info(f"✅ Extracted {len(cookies)} cookies")
                    logger.info("🔄 Keeping browser alive for future authentications...")
                    return cookies
                    
                except Exception as e:
                    logger.error(f"Error during Playwright login: {e}")
                    # Don't close browser on error - it might recover
                    return None
                    
        except ImportError:
            logger.error("❌ Playwright not installed")
            logger.error("Install with: pip install playwright && playwright install chromium")
            return None
        except Exception as e:
            logger.error(f"Error in Playwright login: {e}")
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
