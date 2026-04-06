"""
Cookie Storage Module
Saves and loads session cookies to/from a JSON file for persistence across container restarts
"""

import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

COOKIE_FILE = "/app/data/session_cookies.json"

def save_cookies(cookies: List[Dict]) -> bool:
    """Save ALL cookies to JSON file"""
    try:
        if not cookies:
            logger.warning("No cookies to save")
            return False
        
        # Save ALL cookies, not just session cookies
        # Add timestamp
        data = {
            'timestamp': datetime.now().isoformat(),
            'cookies': cookies
        }
        
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        with open(COOKIE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"✅ Saved {len(cookies)} cookies to {COOKIE_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save cookies: {e}")
        return False

def load_cookies() -> Optional[List[Dict]]:
    """Load cookies from JSON file"""
    try:
        if not os.path.exists(COOKIE_FILE):
            logger.info("No saved cookies file found")
            return None
        
        with open(COOKIE_FILE, 'r') as f:
            data = json.load(f)
        
        cookies = data.get('cookies', [])
        timestamp = data.get('timestamp')
        
        if cookies:
            logger.info(f"✅ Loaded {len(cookies)} session cookies from {COOKIE_FILE}")
            logger.info(f"   Saved at: {timestamp}")
            return cookies
        else:
            logger.warning("No cookies in saved file")
            return None
            
    except Exception as e:
        logger.error(f"Failed to load cookies: {e}")
        return None

def clear_cookies() -> bool:
    """Clear saved cookies file"""
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
            logger.info(f"✅ Cleared saved cookies from {COOKIE_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear cookies: {e}")
        return False

# Made with Bob
