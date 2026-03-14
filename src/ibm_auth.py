"""
IBM W3ID Authentication Module
Handles authentication with IBM systems and session management
"""

import requests
import urllib3
import logging
from datetime import datetime, timedelta
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
        
        # Check if session has expired
        elapsed = (datetime.now() - self.last_login).total_seconds()
        if elapsed > self.session_timeout:
            logger.info("Session expired, needs re-authentication")
            return False
        
        # Test session with a simple request
        try:
            test_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas"
            response = self.session.get(test_url, params={"component": "test"}, timeout=10, verify=False)
            
            # Check if we got redirected to login page
            if "login" in response.url.lower() or response.status_code == 401:
                logger.info("Session invalid, needs re-authentication")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
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
        Authenticate with IBM W3ID using improved flow
        Returns True if successful, False otherwise
        """
        try:
            logger.info(f"Authenticating with IBM W3ID for user: {self.username}")
            
            # Create new session with persistent cookies
            self.session = requests.Session()
            
            # Set comprehensive headers to mimic browser
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            # Step 1: Access the protected resource to trigger SSO redirect
            logger.debug("Step 1: Accessing protected resource to trigger SSO")
            initial_response = self.session.get(
                "https://libh-proxy1.fyre.ibm.com/buildBreakReport/",
                timeout=30,
                allow_redirects=True,
                verify=False
            )
            
            # Step 2: Check if we're already authenticated (session might be cached)
            if "login" not in initial_response.url.lower():
                logger.debug("Already authenticated, verifying session")
                if self._verify_authentication():
                    self.last_login = datetime.now()
                    logger.info("✅ IBM authentication successful (cached session)")
                    return True
            
            # Step 3: Submit credentials to W3ID login
            logger.debug("Step 2: Submitting credentials to W3ID")
            
            # Prepare form data with all required fields
            auth_data = {
                'username': self.username,
                'password': self.password,
                'login-form-type': 'pwd',
            }
            
            # Post to W3ID login endpoint
            auth_response = self.session.post(
                "https://login.w3.ibm.com/oidc/endpoint/default/authorize",
                data=auth_data,
                timeout=30,
                allow_redirects=True,
                verify=False,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': 'https://login.w3.ibm.com/',
                }
            )
            
            # Step 4: Follow any additional redirects to complete SSO flow
            logger.debug("Step 3: Completing SSO flow")
            if auth_response.status_code in [200, 302, 303]:
                # Try to access the original resource again
                final_response = self.session.get(
                    "https://libh-proxy1.fyre.ibm.com/buildBreakReport/",
                    timeout=30,
                    allow_redirects=True,
                    verify=False
                )
                
                # Step 5: Verify authentication
                logger.debug("Step 4: Verifying authentication")
                if self._verify_authentication():
                    self.last_login = datetime.now()
                    logger.info("✅ IBM authentication successful")
                    return True
                else:
                    logger.error("❌ IBM authentication failed - verification failed")
                    logger.debug(f"Final URL: {final_response.url}")
                    logger.debug(f"Status: {final_response.status_code}")
                    return False
            else:
                logger.error(f"❌ IBM authentication failed - auth response status: {auth_response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ IBM authentication error: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _verify_authentication(self) -> bool:
        """Verify that authentication was successful by testing API"""
        try:
            if not self.session:
                logger.error("No session available for verification")
                return False
            
            # Test with actual API call using correct URL format
            test_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas?fas=Messaging"
            response = self.session.get(
                test_url,
                timeout=30,
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
                        logger.debug("Authentication verified with valid API response")
                        return True
                except ValueError:
                    logger.error("Response is not valid JSON")
                    return False
            
            logger.error(f"Authentication verification failed: status {response.status_code}")
            logger.debug(f"Response URL: {response.url}")
            return False
            
        except Exception as e:
            logger.error(f"Authentication verification error: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_session(self) -> Optional[requests.Session]:
        """
        Get authenticated session, re-authenticating if necessary
        Returns None if authentication fails
        """
        if not self.is_session_valid():
            logger.info("Session invalid or expired, re-authenticating...")
            if not self.authenticate():
                return None
        
        return self.session
    
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
        Matches Chrome extension flow with proper form submission
        """
        try:
            logger.info("🔐 Authenticating with Jazz/RTC...")
            
            if not self.session:
                logger.error("No active session - authenticate with Build Break Report first")
                return False
            
            if not self.username or not self.password:
                logger.error("No Jazz/RTC credentials configured")
                return False
            
            # Jazz/RTC authentication endpoint
            jazz_auth_url = "https://wasrtc.hursley.ibm.com:9443/jazz/authenticated/identity"
            
            # Step 1: Try to access Jazz/RTC (will redirect to login if needed)
            logger.info(f"Step 1: Accessing {jazz_auth_url}")
            initial_response = self.session.get(
                jazz_auth_url,
                timeout=30,
                verify=False,
                allow_redirects=True
            )
            
            # Check if already authenticated (got JSON)
            if initial_response.status_code == 200:
                content_type = initial_response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    try:
                        data = initial_response.json()
                        logger.info(f"✅ Jazz/RTC already authenticated as {data.get('userId', 'unknown')}")
                        return True
                    except:
                        pass
            
            # Step 2: Submit login credentials
            logger.info("Step 2: Submitting Jazz/RTC login credentials...")
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
            
            logger.info(f"Login response: status={login_response.status_code}, url={login_response.url}")
            
            # Step 3: Verify authentication
            logger.info("Step 3: Verifying Jazz/RTC authentication...")
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
                        logger.error(f"Response: {verify_response.text[:300]}")
            
            logger.error(f"Jazz/RTC authentication failed - Status: {verify_response.status_code}")
            logger.error(f"Content-Type: {verify_response.headers.get('content-type')}")
            logger.error(f"Response preview: {verify_response.text[:300]}")
            return False
            
            logger.warning("⚠️ Jazz/RTC authentication not possible - no credentials or session")
            return False
            
        except Exception as e:
            logger.error(f"Error authenticating with Jazz/RTC: {e}")
            return False
