"""
IBM Jazz/RTC Authentication Module
Authenticates with wasrtc.hursley.ibm.com using plain username + password.
No browser, no 2FA, no cookies needed.
"""

import requests
import urllib3
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict

# Disable SSL warnings for IBM self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

JAZZ_BASE = "https://wasrtc.hursley.ibm.com:9443/jazz"


class IBMAuthenticator:
    """Authenticates with Jazz/RTC using username + password (j_security_check)."""

    def __init__(self, username: str, password: str,
                 session_timeout: int = 7200, max_retries: int = 3,
                 auth_method: str = "password", cookies: Optional[Dict] = None):
        self.username = username
        self.password = password
        self.session_timeout = session_timeout
        self.max_retries = max_retries
        self.session: Optional[requests.Session] = None
        self.last_login: Optional[datetime] = None
        self._auth_lock = threading.Lock()
        self._is_authenticating = False

    # ── Public API ──────────────────────────────────────────────────────────

    def authenticate(self) -> bool:
        """Authenticate with Jazz/RTC. Returns True on success."""
        return self.authenticate_jazz_rtc()

    def authenticate_jazz_rtc(self) -> bool:
        """
        Authenticate with Jazz/RTC via j_security_check (username + password).
        Thread-safe. Re-uses an existing valid session when possible.
        """
        with self._auth_lock:
            try:
                # Re-use session if it is still fresh (< session_timeout seconds old)
                if self.session and self.last_login:
                    age = (datetime.now() - self.last_login).total_seconds()
                    if age < self.session_timeout:
                        # Quick liveness check
                        try:
                            resp = self.session.get(
                                f"{JAZZ_BASE}/authenticated/identity",
                                timeout=10, verify=False, allow_redirects=False
                            )
                            if resp.status_code == 200 and "json" in resp.headers.get("content-type", "").lower():
                                logger.debug("♻️  Reusing existing Jazz/RTC session")
                                return True
                        except Exception:
                            pass  # fall through to re-authenticate

                logger.info("🔐 Authenticating with Jazz/RTC...")

                self.session = requests.Session()
                self.session.headers.update({
                    "User-Agent": "Mozilla/5.0 (compatible; defect-monitor/1.0)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                })

                # Step 1: POST credentials to j_security_check
                login_resp = self.session.post(
                    f"{JAZZ_BASE}/j_security_check",
                    data={"j_username": self.username, "j_password": self.password},
                    timeout=30,
                    verify=False,
                    allow_redirects=True,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": f"{JAZZ_BASE}/",
                    },
                )

                # Step 2: Verify by hitting the identity endpoint
                verify_resp = self.session.get(
                    f"{JAZZ_BASE}/authenticated/identity",
                    timeout=30,
                    verify=False,
                    allow_redirects=False,
                )

                if verify_resp.status_code == 200:
                    ct = verify_resp.headers.get("content-type", "")
                    if "json" in ct.lower():
                        try:
                            user_id = verify_resp.json().get("userId", "unknown")
                            logger.info(f"✅ Jazz/RTC authenticated as {user_id}")
                            self.last_login = datetime.now()
                            return True
                        except Exception as e:
                            logger.error(f"Failed to parse identity JSON: {e}")

                logger.error(f"Jazz/RTC authentication failed — HTTP {verify_resp.status_code}")
                return False

            except Exception as e:
                logger.error(f"Error authenticating with Jazz/RTC: {e}")
                return False

    def get_session(self) -> Optional[requests.Session]:
        """Return an authenticated session, re-authenticating if needed."""
        if self.authenticate_jazz_rtc():
            return self.session
        return None

    def refresh_session(self) -> bool:
        """Force a fresh authentication."""
        self.last_login = None  # invalidate so authenticate_jazz_rtc re-logs in
        return self.authenticate_jazz_rtc()

    def get_session_info(self) -> Dict:
        """Return basic info about the current session."""
        if not self.session or not self.last_login:
            return {"authenticated": False, "last_login": None}
        age = (datetime.now() - self.last_login).total_seconds()
        return {
            "authenticated": True,
            "last_login": self.last_login.isoformat(),
            "session_age": int(age),
            "expires_in": max(0, int(self.session_timeout - age)),
        }
