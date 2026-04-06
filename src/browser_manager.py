"""
Browser Manager - Keeps a persistent Playwright browser session alive
Uses async API to work with APScheduler's asyncio event loop
"""

import asyncio
import logging
from typing import Optional, List, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from cookie_storage import save_cookies, load_cookies

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
            
            # Try to load saved cookies from JSON file
            saved_cookies = load_cookies()
            if saved_cookies:
                try:
                    # Add cookies to context BEFORE navigating
                    await self.context.add_cookies(saved_cookies)
                    logger.info(f"✅ Loaded {len(saved_cookies)} cookies from storage into browser context")
                except Exception as e:
                    logger.warning(f"Failed to load cookies into context: {e}")
            
            # Navigate to buildBreakReport to activate the cookies
            # Persistent context creates a page automatically, use it
            pages = self.context.pages
            if pages:
                page = pages[0]
                logger.info("📄 Using existing page, navigating to buildBreakReport...")
            else:
                logger.info("📄 Creating new page and navigating to buildBreakReport...")
                page = await self.context.new_page()
            
            try:
                await page.goto("https://libh-proxy1.fyre.ibm.com/buildBreakReport/",
                               wait_until="domcontentloaded",
                               timeout=30000)
                logger.info("✅ Initial navigation complete")
            except Exception as e:
                logger.warning(f"Initial navigation failed (will retry in login_if_needed): {e}")
            
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
    
    async def _verify_page_responding(self, page: Page) -> bool:
        """Verify that buildBreakReport page is responding by running a test query"""
        try:
            logger.info("🔍 Verifying page is responding by running test query...")
            
            # Wait for the page to be fully loaded
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Check if we can find key elements on the page
            # Look for the query input field or table
            selectors_to_check = [
                'input[type="text"]',  # Query input
                'table',  # Results table
                'form',  # Query form
            ]
            
            for selector in selectors_to_check:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        logger.info(f"✅ Found element: {selector} - page is responding!")
                        return True
                except:
                    continue
            
            # If no elements found, try to interact with the page
            logger.info("🔄 Trying to interact with page to verify it's responding...")
            try:
                # Get page title
                title = await page.title()
                if title and len(title) > 0:
                    logger.info(f"✅ Page title: '{title}' - page is responding!")
                    return True
            except:
                pass
            
            logger.warning("⚠️ Could not verify page is responding")
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Error verifying page: {e}")
            return False
    
    async def login_if_needed(self) -> bool:
        """Check if logged in, if not perform login with 2FA"""
        if not self.context:
            logger.error("Browser not started")
            return False
        
        try:
            # Check if we already have an open page
            pages = self.context.pages
            if pages:
                page = pages[0]
                current_url = page.url
                
                # If already on buildBreakReport, verify it's responding
                if "buildBreakReport" in current_url and "login" not in current_url.lower():
                    logger.info("✅ Already on buildBreakReport! Verifying page is responding...")
                    if await self._verify_page_responding(page):
                        logger.info("✅ Page verified - using existing session")
                        return True
                    else:
                        logger.warning("⚠️ Page not responding - will refresh")
                        await page.reload(wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(2000)
                        if await self._verify_page_responding(page):
                            logger.info("✅ Page responding after refresh!")
                            return True
                        logger.warning("⚠️ Page still not responding - will re-login")
                
                # If on about:blank or other page, navigate to check session
                logger.info(f"📍 Current page: {current_url}, checking if session is still valid...")
                try:
                    await page.goto("https://libh-proxy1.fyre.ibm.com/buildBreakReport/",
                                   wait_until="domcontentloaded",
                                   timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    current_url = page.url
                    if "buildBreakReport" in current_url and "login" not in current_url.lower():
                        logger.info("✅ Landed on buildBreakReport! Verifying page is responding...")
                        if await self._verify_page_responding(page):
                            logger.info("✅ Session is still valid and page is responding!")
                            # Save cookies for future use
                            new_cookies = await self.context.cookies()
                            save_cookies(new_cookies)
                            return True
                        else:
                            logger.warning("⚠️ Page not responding - will try refresh")
                    
                    # Session expired or page not responding - try refreshing page to get new cookies
                    logger.info("🔄 Refreshing page to get new cookies...")
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    current_url = page.url
                    if "buildBreakReport" in current_url and "login" not in current_url.lower():
                        logger.info("✅ Landed on buildBreakReport after refresh! Verifying...")
                        if await self._verify_page_responding(page):
                            logger.info("✅ Session refreshed successfully and page is responding!")
                            # Save the new cookies
                            new_cookies = await self.context.cookies()
                            save_cookies(new_cookies)
                            return True
                        else:
                            logger.warning("⚠️ Page still not responding after refresh")
                    
                    # Still need to login
                    logger.info("🔑 Refresh didn't work - performing login...")
                    return await self._perform_login(page)
                except Exception as e:
                    logger.warning(f"Error navigating: {e}")
                    return await self._perform_login(page)
            else:
                # No pages - create page and navigate
                logger.info("📄 Creating new page...")
                page = await self.context.new_page()
                
                try:
                    await page.goto("https://libh-proxy1.fyre.ibm.com/buildBreakReport/",
                                   wait_until="domcontentloaded",
                                   timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    current_url = page.url
                    if "buildBreakReport" in current_url and "login" not in current_url.lower():
                        logger.info("✅ Landed on buildBreakReport! Verifying page is responding...")
                        if await self._verify_page_responding(page):
                            logger.info("✅ Session is still valid and page is responding!")
                            # Save cookies
                            new_cookies = await self.context.cookies()
                            save_cookies(new_cookies)
                            return True
                        else:
                            logger.warning("⚠️ Page not responding - will try login")
                    
                    # Need to login
                    logger.info("🔑 Session expired - performing login...")
                    return await self._perform_login(page)
                except Exception as e:
                    logger.error(f"Error during navigation: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error in login_if_needed: {e}")
            return False
    
    async def _perform_login(self, page: Page) -> bool:
        """Perform login with username/password and 2FA (with retry logic)"""
        import re
        import time
        
        max_attempts = 2  # Try twice: initial attempt + 1 retry
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔐 Login attempt {attempt}/{max_attempts}")
                
                # Navigate to Build Break Report page (will redirect to login)
                logger.info("🌐 Navigating to buildBreakReport...")
                await page.goto("https://libh-proxy1.fyre.ibm.com/buildBreakReport/", wait_until="networkidle", timeout=30000)
                logger.info("✅ Loaded page")
                
                # Click w3id Password link
                try:
                    w3id_link = page.get_by_text("w3id Password")
                    await w3id_link.wait_for(state="visible", timeout=10000)
                    await w3id_link.click()
                    logger.info("✅ Clicked 'w3id Password' link")
                    await page.wait_for_load_state("networkidle", timeout=30000)
                except Exception as e:
                    logger.warning(f"Could not click w3id Password link: {e}")
                
                # Fill email
                email_input = page.locator('input[type="email"], input[name="email"], input[id*="email"]').first
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
                    logger.info("✅ Pressed Enter to sign in")
                
                # Wait for response
                await page.wait_for_timeout(10000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                
                current_url = page.url
                logger.info(f"📍 After sign in: {current_url}")
                
                # Check if login was successful (reached buildBreakReport or similar)
                if "buildBreakReport" in current_url or "libh-proxy" in current_url:
                    logger.info("✅ Login successful - no 2FA required!")
                    return True
                
                # Check if 2FA is required
                if "authsvc" in current_url or "macotp" in current_url:
                    logger.info("🔐 2FA required - looking for Touch Approval...")
                    
                    # Wait for 2FA page to load
                    await page.wait_for_timeout(3000)
                    
                    # Click Touch Approval
                    selectors = [
                        'text="Touch Approval"',
                        'text="Sweetty\'s S24 Ultra (Touch Approval)"',
                        'button:has-text("Touch Approval")',
                    ]
                    
                    clicked = False
                    for selector in selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.count() > 0:
                                await element.click()
                                logger.info("✅ Clicked Touch Approval")
                                clicked = True
                                break
                        except:
                            continue
                    
                    if not clicked:
                        logger.error("❌ Could not find Touch Approval button")
                        if attempt < max_attempts:
                            logger.info("🔄 Refreshing page and retrying...")
                            await page.reload()
                            continue
                        return False
                    
                    # Wait for phone approval (2 minutes)
                    logger.info("📱 Waiting for phone approval (120 seconds)...")
                    try:
                        await page.wait_for_url("**/buildBreakReport**", timeout=120000)
                        logger.info("✅ Successfully authenticated with 2FA!")
                        
                        # Wait a bit for cookies to be set
                        await page.wait_for_timeout(3000)
                        
                        # Get and save cookies
                        all_cookies = await self.context.cookies()
                        logger.info(f"📊 Total cookies after login: {len(all_cookies)}")
                        
                        # Check for important session cookies
                        session_cookies = [c for c in all_cookies if c.get('name') in ['LtpaToken2', 'JSESSIONID', 'mod_auth_openidc_session']]
                        
                        logger.info(f"📊 Total cookies after login: {len(all_cookies)}")
                        if session_cookies:
                            logger.info(f"✅ Found {len(session_cookies)} important session cookies:")
                            for cookie in session_cookies:
                                logger.info(f"   - {cookie.get('name')} (domain: {cookie.get('domain')})")
                        
                        # Save ALL cookies to file for persistence
                        logger.info(f"💾 Saving all {len(all_cookies)} cookies for future use...")
                        save_cookies(all_cookies)
                        
                        return True
                    except:
                        logger.warning("⏰ Timeout waiting for 2FA approval")
                        if attempt < max_attempts:
                            logger.info("🔄 Refreshing page and retrying...")
                            await page.reload()
                            continue
                        return False
                
                # If we're still on login page, login might have failed
                if "login" in current_url.lower():
                    logger.warning("⚠️ Still on login page - login may have failed")
                    if attempt < max_attempts:
                        logger.info("🔄 Refreshing page and retrying...")
                        await page.reload()
                        await page.wait_for_timeout(2000)
                        continue
                    return False
                
                # Unexpected state
                logger.warning(f"⚠️ Unexpected URL: {current_url}")
                if attempt < max_attempts:
                    logger.info("🔄 Refreshing page and retrying...")
                    await page.reload()
                    continue
                return False
                
            except Exception as e:
                logger.error(f"❌ Login attempt {attempt} failed: {e}")
                if attempt < max_attempts:
                    logger.info("🔄 Retrying...")
                    try:
                        await page.reload()
                    except:
                        pass
                    continue
                return False
        
        logger.error("❌ All login attempts failed")
        return False
    
    async def stop(self):
        """Stop the browser session - DISABLED to keep session alive across restarts"""
        # DO NOT close the browser - we want to keep the session alive!
        # The persistent browser context will maintain cookies and session state
        logger.info("⚠️ Browser stop() called but ignored - keeping session alive")
        # if self.context:
        #     await self.context.close()
        #     self.context = None
        # if self.playwright:
        #     await self.playwright.stop()
        #     self.playwright = None
        # logger.info("🛑 Browser session stopped")


# Global instance
_browser_manager = None

def get_browser_manager() -> BrowserManager:
    """Get the global browser manager instance"""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager

# Made with Bob
