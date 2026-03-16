"""
Cookie Monitor - Detects expired cookies and auto-refreshes
Monitors authentication failures and triggers automatic cookie refresh
"""

import logging
import subprocess
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CookieMonitor:
    """Monitors cookie validity and auto-refreshes when expired"""
    
    def __init__(self, refresh_script_path: str = "/app/refresh_cookies_auto.sh"):
        """
        Initialize cookie monitor
        
        Args:
            refresh_script_path: Path to cookie refresh script
        """
        import os
        # Try to find the script in common locations
        possible_paths = [
            refresh_script_path,
            "/app/refresh_cookies_auto.sh",
            "./refresh_cookies_auto.sh",
            os.path.join(os.getcwd(), "refresh_cookies_auto.sh")
        ]
        
        self.refresh_script_path = None
        for path in possible_paths:
            if os.path.exists(path):
                self.refresh_script_path = path
                break
        
        if not self.refresh_script_path:
            logger.warning(f"⚠️  Cookie refresh script not found in any of: {possible_paths}")
            self.refresh_script_path = refresh_script_path  # Use default anyway
        self.last_refresh: Optional[datetime] = None
        self.refresh_in_progress = False
        
    def detect_cookie_expiration(self, response) -> bool:
        """
        Detect if cookies have expired based on response
        
        Args:
            response: HTTP response object
            
        Returns:
            True if cookies appear to be expired
        """
        # Check for common signs of expired cookies
        if response.status_code == 401:
            logger.warning("🔴 401 Unauthorized - Cookies may be expired")
            return True
        
        if response.status_code == 403:
            logger.warning("🔴 403 Forbidden - Cookies may be expired")
            return True
        
        # Check if redirected to login page
        if "login" in response.url.lower():
            logger.warning("🔴 Redirected to login - Cookies expired")
            return True
        
        # Check for authentication error messages
        try:
            if response.text and any(keyword in response.text.lower() for keyword in 
                                    ['authentication', 'unauthorized', 'session expired', 'please log in']):
                logger.warning("🔴 Authentication error detected - Cookies expired")
                return True
        except:
            pass
        
        return False
    
    def refresh_cookies_now(self) -> bool:
        """
        Immediately refresh cookies by calling the host service
        
        Returns:
            True if refresh successful, False otherwise
        """
        if self.refresh_in_progress:
            logger.info("⏳ Cookie refresh already in progress, skipping...")
            return False
        
        try:
            self.refresh_in_progress = True
            logger.info("🔄 COOKIE EXPIRATION DETECTED - Refreshing cookies immediately...")
            
            import requests
            
            # Try to call the cookie refresh service on host
            service_urls = [
                "http://host.docker.internal:5002/refresh-cookies",  # Docker Desktop
                "http://172.17.0.1:5002/refresh-cookies",  # Linux Docker
                "http://localhost:5002/refresh-cookies",  # Direct host
            ]
            
            for url in service_urls:
                try:
                    logger.info(f"Trying cookie refresh service at {url}")
                    response = requests.post(url, timeout=30)
                    
                    if response.status_code == 200:
                        self.last_refresh = datetime.now()
                        logger.info("✅ Cookies refreshed successfully via service!")
                        logger.info(f"Last refresh: {self.last_refresh.isoformat()}")
                        return True
                    else:
                        logger.warning(f"Service returned status {response.status_code}")
                        continue
                        
                except requests.exceptions.ConnectionError:
                    logger.debug(f"Could not connect to {url}")
                    continue
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout calling {url}")
                    continue
                except Exception as e:
                    logger.debug(f"Error calling {url}: {e}")
                    continue
            
            # If service calls failed, log error
            logger.error("❌ Could not reach cookie refresh service on host")
            logger.error("💡 Make sure cookie_refresh_service.py is running on host:")
            logger.error("   python3 cookie_refresh_service.py")
            return False
                
        except Exception as e:
            logger.error(f"❌ Error refreshing cookies: {e}")
            return False
        finally:
            self.refresh_in_progress = False
    
    def handle_authentication_failure(self, response, max_retries: int = 3) -> Optional[object]:
        """
        Handle authentication failure by refreshing cookies and retrying
        
        Args:
            response: Failed HTTP response
            max_retries: Maximum number of retry attempts
            
        Returns:
            New response after refresh, or None if failed
        """
        if not self.detect_cookie_expiration(response):
            return None
        
        logger.warning("🔴 Authentication failure detected!")
        logger.info("🔄 Attempting automatic cookie refresh...")
        
        # Refresh cookies
        if self.refresh_cookies_now():
            logger.info("✅ Cookies refreshed - Ready to retry request")
            return True
        else:
            logger.error("❌ Failed to refresh cookies")
            return None
    
    def get_status(self) -> dict:
        """
        Get current status of cookie monitor
        
        Returns:
            Dictionary with status information
        """
        return {
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "refresh_in_progress": self.refresh_in_progress,
            "monitoring_active": True
        }


# Global cookie monitor instance
_cookie_monitor = None


def get_cookie_monitor() -> CookieMonitor:
    """Get or create global cookie monitor instance"""
    global _cookie_monitor
    if _cookie_monitor is None:
        _cookie_monitor = CookieMonitor()
    return _cookie_monitor


# Made with Bob