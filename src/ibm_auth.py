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
    
    def __init__(self, username: str, password: str, session_timeout: int = 7200):
        self.username = username
        self.password = password
        self.session_timeout = session_timeout
        self.session: Optional[requests.Session] = None
        self.last_login: Optional[datetime] = None
        self.login_url = "https://login.w3.ibm.com/login"
        
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
            test_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/api/defects"
            response = self.session.get(test_url, params={"component": "test"}, timeout=10)
            
            # Check if we got redirected to login page
            if "login" in response.url.lower() or response.status_code == 401:
                logger.info("Session invalid, needs re-authentication")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return False
    
    def authenticate(self) -> bool:
        """
        Authenticate with IBM W3ID
        Returns True if successful, False otherwise
        """
        try:
            logger.info(f"Authenticating with IBM W3ID for user: {self.username}")
            
            # Create new session
            self.session = requests.Session()
            
            # Set headers to mimic browser
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            
            # Step 1: Get login page to establish session
            logger.debug("Step 1: Getting login page")
            login_page = self.session.get(
                "https://libh-proxy1.fyre.ibm.com/buildBreakReport/",
                timeout=30,
                allow_redirects=True,
                verify=False  # Disable SSL verification for IBM self-signed certs
            )
            
            # Step 2: Submit credentials
            logger.debug("Step 2: Submitting credentials")
            auth_data = {
                'username': self.username,
                'password': self.password,
            }
            
            auth_response = self.session.post(
                self.login_url,
                data=auth_data,
                timeout=30,
                allow_redirects=True,
                verify=False  # Disable SSL verification for IBM self-signed certs
            )
            
            # Step 3: Verify authentication
            logger.debug("Step 3: Verifying authentication")
            if self._verify_authentication():
                self.last_login = datetime.now()
                logger.info("✅ IBM authentication successful")
                return True
            else:
                logger.error("❌ IBM authentication failed - verification failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ IBM authentication error: {e}")
            return False
    
    def _verify_authentication(self) -> bool:
        """Verify that authentication was successful by testing API"""
        try:
            # Test with actual API call using correct URL format
            test_url = "https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas?fas=Messaging"
            response = self.session.get(
                test_url,
                timeout=30,
                headers={'Accept': 'application/json'},
                verify=False  # Disable SSL verification for IBM self-signed certs
            )
            
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
            return False
            
        except Exception as e:
            logger.error(f"Authentication verification error: {e}")
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
