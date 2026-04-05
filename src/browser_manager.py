"""
Browser Manager - Keeps a persistent Playwright browser session alive
Uses async API to work with APScheduler's asyncio event loop
"""

import asyncio
import logging
from typing import Optional, List, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages a persistent Playwright browser session"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.playwright = None
        self.browser = None
        self.context = None
        self.username = None
        self.password = None
        logger.info("🌐 Browser Manager initialized")
    
    async def start(self, username: str, password: str, user_data_dir: str = "/app/data/chrome_profile"):
        """Start the persistent browser session"""
        if self.context:
            # Browser already running
            logger.info("♻️ Browser session already running")
            return True
        
        try:
            import os
            os.makedirs(user_data_dir, exist_ok=True)
            
            logger.info("🚀 Starting persistent browser session...")
            self.username = username
            self.password = password
            
            # Start Playwright
            self.playwright = await async_playwright().start()
            
            # Launch persistent browser context
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                ignore_https_errors=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            logger.info("✅ Persistent browser session started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False
    
    async def get_cookies(self) -> Optional[List[Dict]]:
        """Get cookies from the current browser session"""
        if not self.context:
            logger.error("Browser not started")
            return None
        
        try:
            cookies = await self.context.cookies()
            return cookies
        except Exception as e:
            logger.error(f"Failed to get cookies: {e}")
            return None
    
    async def login_if_needed(self) -> bool:
        """Check if logged in, if not perform login with 2FA"""
        if not self.context:
            logger.error("Browser not started")
            return False
        
        try:
            # Open new page (tab) in existing browser session
            page = await self.context.new_page()
            
            try:
                logger.info("📍 Checking login status...")
                await page.goto("https://libh-proxy1.fyre.ibm.com/buildBreakReport/", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                
                current_url = page.url
                logger.info(f"Current URL: {current_url}")
                
                # Check if already logged in
                if "buildBreakReport" in current_url and "login" not in current_url.lower():
                    logger.info("✅ Already logged in! Session is valid")
                    await page.close()
                    return True
                
                # Need to login
                logger.info("🔑 Session expired - performing login...")
                return await self._perform_login(page)
                
            finally:
                # Always close the page (tab) but keep browser alive
                try:
                    await page.close()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in login_if_needed: {e}")
            return False
    
    async def _perform_login(self, page: Page) -> bool:
        """Perform login with username/password and 2FA"""
        try:
            import re
            
            # Click w3id Password link
            try:
                w3id_link = page.get_by_text("w3id Password")
                await w3id_link.wait_for(state="visible", timeout=10000)
                await w3id_link.click()
                logger.info("✅ Clicked 'w3id Password' link")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)
            except:
                logger.info("Continuing with direct login...")
            
            # Fill email
            email_input = page.locator('input[type="email"], input[name="email"], input[id*="email"], input[name="username"]').first
            await email_input.wait_for(state="visible", timeout=10000)
            await email_input.fill(self.username)
            logger.info("✅ Filled email")
            
            # Fill password
            password_input = page.locator('input[type="password"], input[name="password"], input[id*="password"]').first
            await password_input.wait_for(state="visible", timeout=10000)
            await password_input.fill(self.password)
            logger.info("✅ Filled password")
            
            # Click Sign in
            try:
                sign_in_button = page.get_by_role("button", name=re.compile("sign in", re.IGNORECASE))
                await sign_in_button.wait_for(state="visible", timeout=10000)
                await sign_in_button.click()
                logger.info("✅ Clicked Sign in")
            except:
                await page.keyboard.press('Enter')
            
            # Wait for login
            await page.wait_for_timeout(5000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            current_url = page.url
            
            # Handle 2FA if needed
            if "authsvc" in current_url or "macotp" in current_url:
                logger.info("🔐 2FA required - looking for Touch Approval...")
                
                # Click Touch Approval
                selectors = [
                    'text="Touch Approval"',
                    'text="Sweetty\'s S24 Ultra (Touch Approval)"',
                ]
                
                for selector in selectors:
                    try:
                        element = page.locator(selector).first
                        if await element.count() > 0:
                            await element.click()
                            logger.info("✅ Clicked Touch Approval")
                            break
                    except:
                        continue
                
                # Wait for phone approval
                logger.info("📱 Waiting for phone approval (60 seconds)...")
                try:
                    await page.wait_for_url("**/buildBreakReport**", timeout=60000)
                    logger.info("✅ Successfully authenticated!")
                    return True
                except:
                    logger.warning("Timeout waiting for approval")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    async def stop(self):
        """Stop the browser session"""
        if self.context:
            await self.context.close()
            self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        logger.info("🛑 Browser session stopped")


# Global instance
_browser_manager = None

def get_browser_manager() -> BrowserManager:
    """Get the global browser manager instance"""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager

# Made with Bob
