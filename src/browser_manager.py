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
        self.event_loop = None      # Persistent event loop — runs in _loop_thread
        self._loop_thread = None    # Dedicated background thread for the event loop
        self._fetch_page = None     # Dedicated page kept alive on the portal for component fetches
        logger.info("🌐 Browser Manager initialized")
        self._start_background_loop()

    def _start_background_loop(self):
        """
        Start a dedicated background thread that runs the asyncio event loop
        continuously.  All Playwright operations are submitted to this loop via
        run_coroutine_threadsafe() so the Playwright context never crosses loop
        boundaries.
        """
        import threading

        if self._loop_thread is not None and self._loop_thread.is_alive():
            return  # Already running

        self.event_loop = asyncio.new_event_loop()

        def _run_loop():
            asyncio.set_event_loop(self.event_loop)
            logger.info("🔄 Browser event loop thread started")
            self.event_loop.run_forever()
            logger.info("🔄 Browser event loop thread stopped")

        self._loop_thread = threading.Thread(target=_run_loop, name="browser-loop", daemon=True)
        self._loop_thread.start()
        logger.info("✅ Browser background event loop running")

    def _ensure_event_loop(self):
        """Return the persistent running event loop (start it if needed)."""
        if self.event_loop is None or self.event_loop.is_closed() or not self._loop_thread.is_alive():
            logger.info("🔄 Restarting browser background event loop...")
            self._start_background_loop()
        return self.event_loop

    def _run_async(self, coro, timeout: float = 120):
        """
        Submit a coroutine to the persistent browser event loop and block the
        calling thread until it completes.  Safe to call from any thread.
        """
        import concurrent.futures
        loop = self._ensure_event_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"Browser operation timed out after {timeout}s")
    
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
            # Use headless=False with virtual display args so the React app's JS
            # executes fully — some apps detect headless mode and skip rendering.
            # --no-sandbox / --disable-gpu are standard for Docker/VM environments.
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                ignore_https_errors=True,
                args=[
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--window-size=1920,1080',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--allow-running-insecure-content',
                ]
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
            
            # Navigate to cognitive functional area list to activate the cookies
            # Persistent context creates a page automatically, use it
            pages = self.context.pages
            if pages:
                page = pages[0]
                logger.info("📄 Using existing page, navigating to functionalAreaList...")
            else:
                logger.info("📄 Creating new page and navigating to functionalAreaList...")
                page = await self.context.new_page()
            
            try:
                await page.goto("https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaList.html",
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
        """Verify that the cognitive functional area page is responding"""
        try:
            logger.info("🔍 Verifying page is responding...")
            
            # Wait for the page to be fully loaded
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Check if we can find key elements on the new cognitive page
            selectors_to_check = [
                'a[href*="functionalAreaAnalysis"]',  # Component links
                'table',  # Results table
                '.functional-area',  # FA items
                'h1',  # Page heading
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
    
    async def login_if_needed(self, force_refresh: bool = False) -> bool:
        """Check if logged in, if not perform login with 2FA
        
        Args:
            force_refresh: If True, force a page refresh to get fresh cookies
        """
        if not self.context:
            logger.error("Browser not started")
            return False
        
        try:
            # Check if we already have an open page
            pages = self.context.pages
            if pages:
                page = pages[0]
                current_url = page.url
                
                # Check if we're on a login page
                if "login" in current_url.lower() or "authsvc" in current_url.lower():
                    logger.warning("🔐 Detected login page - session expired, performing login...")
                    return await self._perform_login(page)
                
                # If already on the cognitive portal, verify it's responding
                if "cognitive" in current_url and "libh-proxy" in current_url:
                    logger.info("✅ Already on cognitive portal! Verifying page is responding...")
                    
                    # If force_refresh is True, always refresh the page to get fresh cookies
                    if force_refresh:
                        logger.info("🔄 Force refreshing page to get fresh cookies...")
                        await page.reload(wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(2000)
                        
                        # Check if refresh redirected us to login
                        current_url = page.url
                        if "login" in current_url.lower() or "authsvc" in current_url.lower():
                            logger.warning("🔐 Refresh redirected to login - session expired, performing login...")
                            return await self._perform_login(page)
                    
                    if await self._verify_page_responding(page):
                        logger.info("✅ Page verified - using existing session")
                        return True
                    else:
                        logger.warning("⚠️ Page not responding - will refresh")
                        await page.reload(wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(2000)
                        
                        # Check if refresh redirected us to login
                        current_url = page.url
                        if "login" in current_url.lower() or "authsvc" in current_url.lower():
                            logger.warning("🔐 Refresh redirected to login - session expired, performing login...")
                            return await self._perform_login(page)
                        
                        if await self._verify_page_responding(page):
                            logger.info("✅ Page responding after refresh!")
                            return True
                        logger.warning("⚠️ Page still not responding - will re-login")
                
                # If on about:blank or other page, navigate to check session
                logger.info(f"📍 Current page: {current_url}, checking if session is still valid...")
                try:
                    await page.goto("https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaList.html",
                                   wait_until="domcontentloaded",
                                   timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    current_url = page.url
                    
                    # Check if redirected to login
                    if "login" in current_url.lower() or "authsvc" in current_url.lower():
                        logger.warning("🔐 Redirected to login page - session expired, performing login...")
                        return await self._perform_login(page)
                    
                    if "cognitive" in current_url and "libh-proxy" in current_url:
                        logger.info("✅ Landed on cognitive portal! Verifying page is responding...")
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
                    
                    # Check if refresh redirected to login
                    if "login" in current_url.lower() or "authsvc" in current_url.lower():
                        logger.warning("🔐 Refresh redirected to login - session expired, performing login...")
                        return await self._perform_login(page)
                    
                    if "cognitive" in current_url and "libh-proxy" in current_url:
                        logger.info("✅ Landed on cognitive portal after refresh! Verifying...")
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
                    await page.goto("https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaList.html",
                                   wait_until="domcontentloaded",
                                   timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    current_url = page.url
                    if "cognitive" in current_url and "libh-proxy" in current_url and "login" not in current_url.lower():
                        logger.info("✅ Landed on cognitive portal! Verifying page is responding...")
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
                
                # Navigate to cognitive functional area list page (will redirect to login)
                logger.info("🌐 Navigating to cognitive functional area list...")
                await page.goto("https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaList.html", wait_until="networkidle", timeout=30000)
                logger.info("✅ Loaded page")
                
                # Wait a bit for page to stabilize
                await page.wait_for_timeout(2000)
                
                current_url = page.url
                logger.info(f"📍 Current URL after navigation: {current_url}")
                
                # Click w3id Password link (if present)
                # This link may not appear if we're already past the authentication method selection
                try:
                    # Check if the w3id Password link exists
                    w3id_link = page.get_by_text("w3id Password")
                    link_count = await w3id_link.count()
                    
                    if link_count > 0:
                        logger.info("🔍 Found 'w3id Password' link, clicking...")
                        await w3id_link.wait_for(state="visible", timeout=20000)
                        await w3id_link.click()
                        logger.info("✅ Clicked 'w3id Password' link")
                        await page.wait_for_load_state("networkidle", timeout=30000)
                        await page.wait_for_timeout(2000)
                    else:
                        logger.info("ℹ️ 'w3id Password' link not found - may already be on login page")
                except Exception as e:
                    logger.warning(f"Could not click w3id Password link (continuing anyway): {e}")
                    # Continue anyway - we might already be on the login page
                
                # Wait for login form to appear
                await page.wait_for_timeout(2000)
                
                # Fill email - try multiple selectors
                logger.info("🔍 Looking for email input field...")
                email_selectors = [
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[id*="email"]',
                    'input[placeholder*="email" i]',
                    'input[aria-label*="email" i]'
                ]
                
                email_filled = False
                for selector in email_selectors:
                    try:
                        email_input = page.locator(selector).first
                        if await email_input.count() > 0:
                            await email_input.wait_for(state="visible", timeout=15000)
                            await email_input.fill(self.username)
                            logger.info(f"✅ Filled email using selector: {selector}")
                            email_filled = True
                            break
                    except:
                        continue
                
                if not email_filled:
                    logger.error("❌ Could not find email input field")
                    if attempt < max_attempts:
                        logger.info("🔄 Retrying...")
                        continue
                    return False
                
                # Fill password - try multiple selectors
                logger.info("🔍 Looking for password input field...")
                password_selectors = [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[id*="password"]',
                    'input[placeholder*="password" i]',
                    'input[aria-label*="password" i]'
                ]
                
                password_filled = False
                for selector in password_selectors:
                    try:
                        password_input = page.locator(selector).first
                        if await password_input.count() > 0:
                            await password_input.wait_for(state="visible", timeout=15000)
                            await password_input.fill(self.password)
                            logger.info(f"✅ Filled password using selector: {selector}")
                            password_filled = True
                            break
                    except:
                        continue
                
                if not password_filled:
                    logger.error("❌ Could not find password input field")
                    if attempt < max_attempts:
                        logger.info("🔄 Retrying...")
                        continue
                    return False
                
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
                
                # Check if login was successful (reached cognitive portal or similar)
                if ("cognitive" in current_url and "libh-proxy" in current_url) or ("libh-proxy" in current_url and "login" not in current_url.lower()):
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
                        # Wait for redirect to land on libh-proxy1 (cognitive portal)
                        await page.wait_for_url("**/cognitive/**", timeout=120000)
                        logger.info("✅ Successfully authenticated with 2FA!")

                        # CRITICAL: Wait for full networkidle so ALL SSO redirect cookies
                        # (.ibm.com, .w3.ibm.com, w3_uid, pageviewContext etc.) are set.
                        # These are required for the backend data API to return 200.
                        logger.info("⏳ Waiting for full SSO cookie chain to settle...")
                        try:
                            await page.wait_for_load_state("networkidle", timeout=20000)
                        except Exception:
                            pass
                        await page.wait_for_timeout(3000)

                        # Collect cookies BEFORE any additional navigation
                        all_cookies = await self.context.cookies()
                        logger.info(f"📊 Cookies after 2FA: {len(all_cookies)}")

                        # Now navigate to a real component page to activate the backend session
                        # This causes the server to bind our mod_auth_openidc_session to the
                        # data API backend, fixing the 500 error on subsequent API calls.
                        logger.info("🔄 Activating backend data session...")
                        try:
                            await page.goto(
                                "https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaAnalysis.html"
                                "?functionalArea=Messaging&tab=Build%2BBreak+Report",
                                wait_until="networkidle",
                                timeout=30000
                            )
                            await page.wait_for_timeout(8000)
                            logger.info(f"📍 Activation page: {page.url}")
                        except Exception as e:
                            logger.warning(f"Backend activation warning (continuing): {e}")

                        # Collect final cookie set — includes any new cookies from activation
                        all_cookies = await self.context.cookies()
                        logger.info(f"📊 Total cookies after full login: {len(all_cookies)}")

                        # Log all cookies for diagnostics
                        for cookie in all_cookies:
                            logger.info(f"   🍪 {cookie.get('name'):40s} domain={cookie.get('domain')}")

                        # Save ALL cookies
                        logger.info(f"💾 Saving all {len(all_cookies)} cookies for future use...")
                        save_cookies(all_cookies)

                        # Create the dedicated fetch page NOW — while we're already on the
                        # cognitive portal. This page stays alive and is reused for all
                        # component fetches, so React never cold-starts.
                        await self._ensure_fetch_page()

                        return True
                    except:
                        logger.warning("⏰ Timeout waiting for 2FA approval")
                        if attempt < max_attempts:
                            logger.info("🔄 2FA timeout - clearing session and retrying...")
                            logger.info("   This will trigger a NEW 2FA request on your phone")
                            # Clear cookies to force fresh login
                            try:
                                await self.context.clear_cookies()
                                logger.info("🗑️  Cleared browser cookies to reset session")
                            except Exception as e:
                                logger.warning(f"Could not clear cookies: {e}")
                            # Small delay before retry
                            await page.wait_for_timeout(2000)
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
                
                # Take screenshot on failure for debugging
                try:
                    screenshot_path = f"/app/logs/login_failure_attempt_{attempt}.png"
                    await page.screenshot(path=screenshot_path)
                    logger.info(f"📸 Screenshot saved to {screenshot_path}")
                except Exception as screenshot_error:
                    logger.warning(f"Could not save screenshot: {screenshot_error}")
                
                if attempt < max_attempts:
                    logger.info("🔄 Retrying...")
                    try:
                        await page.reload()
                        await page.wait_for_timeout(2000)
                    except:
                        pass
                    continue
                return False
        
        logger.error("❌ All login attempts failed")
        return False
    
    async def force_fresh_login(self) -> bool:
        """
        Force a fresh login with 2FA to get brand new cookies
        This resets the session expiration timer
        """
        try:
            logger.info("🔄 Forcing fresh login to reset session...")
            
            if not self.context:
                logger.error("❌ Browser context not initialized")
                return False
            
            # Get the page
            pages = self.context.pages
            if pages:
                page = pages[0]
            else:
                page = await self.context.new_page()
            
            # Clear existing cookies to force fresh login
            logger.info("🗑️  Clearing existing cookies...")
            await self.context.clear_cookies()
            
            # Perform fresh login with 2FA
            logger.info("🔐 Performing fresh login with 2FA...")
            success = await self._perform_login(page)
            
            if success:
                logger.info("✅ Fresh login successful - session reset with new cookies")
                return True
            else:
                logger.error("❌ Fresh login failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error during fresh login: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _ensure_fetch_page(self) -> Optional["Page"]:
        """
        Return the dedicated fetch page, creating/recovering it if needed.
        This page stays alive on the cognitive portal between component fetches
        so React never cold-starts and always has its full session state.
        """
        # Check if existing fetch page is still alive and on the portal
        if self._fetch_page is not None:
            try:
                url = self._fetch_page.url
                if "libh-proxy1" in url and not self._fetch_page.is_closed():
                    return self._fetch_page
            except Exception:
                pass
            # Page crashed or closed — reset it
            logger.info("🔄 Fetch page needs recovery — creating new one")
            self._fetch_page = None

        if not self.context:
            return None

        try:
            # Create a new page and navigate to the portal list page
            # (not a component page, so it loads fast and React mounts cleanly)
            logger.info("📄 Creating dedicated fetch page on cognitive portal...")
            self._fetch_page = await self.context.new_page()
            await self._fetch_page.goto(
                "https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaList.html",
                wait_until="domcontentloaded",
                timeout=20000
            )
            # Wait briefly for React to mount on the list page
            await self._fetch_page.wait_for_timeout(3000)
            logger.info(f"✅ Fetch page ready at: {self._fetch_page.url}")
            return self._fetch_page
        except Exception as e:
            logger.error(f"Failed to create fetch page: {e}")
            self._fetch_page = None
            return None

    async def fetch_component_data_json(self, component: str, timeout: int = 45000) -> Optional[dict]:
        """
        Fetch the Build Break Report data for a component from the cognitive portal.

        Uses a dedicated long-lived fetch page (_fetch_page) that stays on the
        cognitive portal between fetches. Navigating this page to each component
        URL is a React SPA route-change (fast, reuses Redux state) — not a cold start.

        URL: https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaAnalysis.html
               ?functionalArea=<component>&tab=Build%2BBreak+Report
        """
        if not self.context:
            logger.error("Browser not started — cannot fetch component data")
            return None

        import asyncio as _asyncio
        import urllib.parse as _urlparse

        encoded = _urlparse.quote(component)
        page_url = (
            f"https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaAnalysis.html"
            f"?functionalArea={encoded}&tab=Build%2BBreak+Report"
        )

        # Get (or recover) the dedicated fetch page
        page = await self._ensure_fetch_page()
        if page is None:
            logger.error("Cannot get fetch page — aborting")
            return None

        captured_json = [None]

        async def handle_response(response):
            """Capture any JSON data API response (future-proof fast path)."""
            try:
                url = response.url
                status = response.status
                ct = response.headers.get("content-type", "")
                if not any(url.endswith(ext) for ext in (".js", ".css", ".png", ".ico", ".woff", ".ttf", ".map")):
                    logger.info(f"   📡 [{status}] {url}  ({ct[:50]})")
                if captured_json[0] is None and status == 200 and "json" in ct.lower():
                    if any(kw in url.lower() for kw in ["buildbreak", "defect", "untriaged"]):
                        try:
                            captured_json[0] = await response.json()
                            logger.info(f"✅ Intercepted JSON for {component}: {url}")
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            logger.info(f"🌐 Navigating to {page_url}")
            try:
                await page.goto(page_url, wait_until="domcontentloaded", timeout=timeout)
            except Exception as nav_err:
                logger.warning(f"Navigation warning for {component}: {nav_err}")
                # If page crashed, clear it so _ensure_fetch_page recreates on next call
                if "crash" in str(nav_err).lower():
                    self._fetch_page = None
                    return None

            # ── Poll for React content (up to 30s) ───────────────────────────
            content_appeared = False
            logger.info(f"   ⏳ Waiting for React to render...")
            for _ in range(30):
                await _asyncio.sleep(1)
                if captured_json[0] is not None:
                    content_appeared = True
                    break
                for sel in ("table tr td", "h2", "h3", "h4",
                            "[class*='defect']", "[class*='Defect']",
                            "[class*='report']", "[class*='Report']",
                            "main", "#root > *"):
                    try:
                        if await page.locator(sel).count() > 0:
                            logger.info(f"   ✅ Content appeared: {sel!r}")
                            content_appeared = True
                            break
                    except Exception:
                        continue
                if content_appeared:
                    break

            if not content_appeared:
                logger.warning(f"   ⚠️  No content after 30s for {component}")

            await _asyncio.sleep(2)

            if captured_json[0] is not None:
                return captured_json[0]

            # ── Scrape the rendered DOM ───────────────────────────────────────
            logger.info(f"🔍 Scraping DOM for {component}...")
            try:
                dom_data = await page.evaluate("""
                    () => {
                        const sections = [];
                        const allTableRows = [];

                        document.querySelectorAll('h1,h2,h3,h4,h5').forEach(h => {
                            const sec = { heading: h.textContent.trim(), rows: [] };
                            let el = h.nextElementSibling;
                            while (el && !['H1','H2','H3','H4','H5'].includes(el.tagName)) {
                                el.querySelectorAll('tr').forEach(row => {
                                    const cells = Array.from(row.querySelectorAll('td,th'))
                                                       .map(c => c.textContent.trim());
                                    if (cells.length > 0) sec.rows.push(cells);
                                });
                                el = el.nextElementSibling;
                            }
                            if (sec.rows.length > 0) sections.push(sec);
                        });

                        document.querySelectorAll('table tr').forEach(row => {
                            const cells = Array.from(row.querySelectorAll('td,th'))
                                               .map(c => c.textContent.trim());
                            if (cells.length > 1) allTableRows.push(cells);
                        });

                        const root = document.getElementById('root') || document.body;
                        return {
                            pageTitle: document.title,
                            sections,
                            allTableRows,
                            rawText: document.body ? document.body.innerText.substring(0, 4000) : '',
                            rootHTML: root ? root.innerHTML.substring(0, 3000) : '',
                            bodyChildCount: document.body ? document.body.children.length : 0
                        };
                    }
                """)
            except Exception as eval_err:
                logger.error(f"DOM evaluate error for {component}: {eval_err}")
                if "crash" in str(eval_err).lower() or "Target closed" in str(eval_err):
                    self._fetch_page = None
                return None

            logger.info(
                f"   📄 DOM: title='{dom_data.get('pageTitle')}', "
                f"bodyChildren={dom_data.get('bodyChildCount')}, "
                f"sections={len(dom_data.get('sections', []))}, "
                f"tableRows={len(dom_data.get('allTableRows', []))}"
            )

            raw_text = dom_data.get('rawText', '').strip()
            if raw_text:
                logger.info(f"   📝 Page text:\n{raw_text[:1200]}")
            else:
                logger.warning(f"   ⚠️  Page body is EMPTY")
                logger.info(f"   🔍 Root HTML: {dom_data.get('rootHTML', '')[:600]}")

            all_rows = dom_data.get('allTableRows', [])
            sections = dom_data.get('sections', [])

            if all_rows or sections:
                return {
                    "_dom_scraped": True,
                    "sections": sections,
                    "allTableRows": all_rows,
                    "pageTitle": dom_data.get('pageTitle', ''),
                    "component": component
                }

            logger.warning(f"   ⚠️  No defect table data in DOM for {component}")
            return None

        except Exception as e:
            logger.error(f"Error in fetch_component_data_json for {component}: {e}")
            if "crash" in str(e).lower() or "Target closed" in str(e):
                self._fetch_page = None
            return None
        finally:
            try:
                page.remove_listener("response", handle_response)
            except Exception:
                pass

    async def fetch_rendered_html(self, url: str, wait_for_selector: str = None, timeout: int = 30000) -> Optional[str]:
        """
        Navigate to a URL using the authenticated Playwright browser and return
        the fully-rendered HTML after JavaScript execution.
        This is needed for React SPAs that load data dynamically.

        NOTE: This is kept as a fallback.  The primary data-fetch path now uses
        fetch_component_data_json() which intercepts the XHR data API call directly.

        Args:
            url: The page URL to fetch
            wait_for_selector: CSS selector to wait for before returning HTML
            timeout: Navigation timeout in ms

        Returns:
            Rendered HTML string, or None on error
        """
        if not self.context:
            logger.error("Browser not started — cannot fetch rendered HTML")
            return None

        page = None
        try:
            # Use a new page to avoid disrupting the main session page
            page = await self.context.new_page()

            # Navigate and wait for JS to execute
            await page.goto(url, wait_until="networkidle", timeout=timeout)

            # Wait for specific selector if provided
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=15000)
                except Exception:
                    pass  # Continue even if selector not found
            else:
                # Default: wait for any table row or RTC link to appear
                try:
                    await page.wait_for_selector('tr td a, [class*="defect"], [class*="row"]', timeout=15000)
                except Exception:
                    # No defects found — page may be empty, still return HTML
                    await page.wait_for_timeout(3000)

            html = await page.content()
            return html

        except Exception as e:
            logger.error(f"Error fetching rendered HTML for {url}: {e}")
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

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
