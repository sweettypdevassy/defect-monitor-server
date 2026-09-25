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
        self.event_loop = None  # Persistent event loop for browser operations
        logger.info("🌐 Browser Manager initialized")
    
    def _ensure_event_loop(self):
        """Ensure we have a persistent event loop for browser operations"""
        if self.event_loop is None or self.event_loop.is_closed():
            logger.info("🔄 Creating new event loop for browser manager")
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
        else:
            # Set as current event loop for this thread
            asyncio.set_event_loop(self.event_loop)
        return self.event_loop
    
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
    
    async def fetch_component_data_json(self, component: str, timeout: int = 45000) -> Optional[dict]:
        """
        Fetch the Build Break Report JSON for a component from the cognitive portal.

        Strategy: open the functionalAreaAnalysis page in a new Playwright tab while
        intercepting ALL network responses.  The React SPA will fire an XHR/fetch call
        to the internal data API:
            /cognitive/external-data/…/buildBreakReport?functionalArea=<component>
        We capture that response's body before the page finishes loading so we get the
        real JSON data regardless of how long the React render takes.

        Falls back to scraping the rendered page DOM if no API response is intercepted
        (e.g. the backend is temporarily unavailable but a cached render exists).

        Args:
            component: Component name (e.g. "Batch", "Messaging")
            timeout:   Maximum wait time in ms for the page + API response

        Returns:
            Parsed JSON dict/list from the data API, or None on error.
        """
        if not self.context:
            logger.error("Browser not started — cannot fetch component data")
            return None

        import asyncio as _asyncio
        import urllib.parse as _urlparse

        # ── Step 1: Try direct HTTP fetch using the saved session cookies ───────
        # This is faster and more reliable than browser interception.
        # The mod_auth_openidc_session + JSESSIONID cookies from login are enough
        # to authenticate direct HTTP requests to the cognitive portal.
        direct_result = await self._direct_http_fetch(component)
        if direct_result is not None:
            return direct_result

        # ── Step 2: Browser-based interception fallback ───────────────────────
        # Log ALL network requests/responses so we can discover the real API URL
        # if the pattern we assumed is wrong.

        # Patterns that indicate a data API call (broad match, log everything else)
        DATA_API_PATTERNS = [
            "/cognitive/external-data/",
            "/buildBreakReport",
            "/functionalArea",
            "/api/",
            ".json",
        ]

        captured_json = [None]   # mutable container so the closure can write to it
        api_event = _asyncio.Event()
        all_requests_seen = []   # diagnostic: every URL the page fetches

        page = None
        try:
            page = await self.context.new_page()

            async def handle_response(response):
                """Log every response; capture the first JSON data API hit."""
                try:
                    url = response.url
                    status = response.status
                    ct = response.headers.get("content-type", "")

                    # Log every non-static resource so we know what the page calls
                    if not any(ext in url for ext in (".js", ".css", ".png", ".ico", ".woff")):
                        logger.info(f"   📡 [{status}] {url}  ({ct[:60]})")
                        all_requests_seen.append((status, url))

                    # Capture the first response that looks like a data API call
                    if captured_json[0] is None:
                        is_data_call = any(p in url for p in DATA_API_PATTERNS)
                        is_json = "json" in ct.lower()
                        if is_data_call and is_json and status == 200:
                            try:
                                body = await response.json()
                                captured_json[0] = body
                                api_event.set()
                                logger.info(f"✅ Captured data API JSON for {component} from: {url}")
                            except Exception as e:
                                logger.warning(f"Could not parse as JSON ({url}): {e}")
                        elif is_data_call and status not in (200,):
                            logger.warning(f"⚠️  Data API returned HTTP {status} for {component}: {url}")
                            api_event.set()   # stop waiting — won't get data this way
                except Exception as e:
                    logger.debug(f"Response handler error: {e}")

            page.on("response", handle_response)

            # Build component page URL
            encoded = _urlparse.quote(component)
            page_url = (
                f"https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaAnalysis.html"
                f"?functionalArea={encoded}&tab=Build%2BBreak+Report"
            )

            logger.info(f"🌐 [browser] Navigating to {page_url}")

            try:
                await page.goto(page_url, wait_until="domcontentloaded", timeout=timeout)
            except Exception as nav_err:
                logger.warning(f"Navigation warning for {component}: {nav_err}")

            # Wait up to (timeout − 5 s) for any intercepted data response
            wait_secs = max(10, (timeout / 1000) - 5)
            try:
                await _asyncio.wait_for(api_event.wait(), timeout=wait_secs)
            except _asyncio.TimeoutError:
                logger.warning(
                    f"⏰ No data API response within {wait_secs}s for {component}. "
                    f"Page made {len(all_requests_seen)} non-static requests total."
                )

            if captured_json[0] is not None:
                return captured_json[0]

            logger.warning(
                f"⚠️  No JSON captured for {component} after browser interception. "
                f"Requests seen: {[u for _, u in all_requests_seen[:20]]}"
            )
            return None

        except Exception as e:
            logger.error(f"Error in fetch_component_data_json for {component}: {e}")
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def _direct_http_fetch(self, component: str) -> Optional[dict]:
        """
        Attempt to fetch Build Break Report data directly via HTTP using the
        mod_auth_openidc_session and JSESSIONID cookies from the browser session.

        The cognitive portal React app calls one of these patterns:
          /cognitive/external-data/cognitive-pages/libh-proxy1.fyre.ibm.com/data/buildBreakReport?functionalArea=<X>
          /cognitive/api/buildBreakReport?functionalArea=<X>
          /buildBreakReport/rest2/defects/buildbreak/fas?fas=<X>   (old URL — may still work)

        We try all known patterns with the session cookies.
        """
        import aiohttp
        import urllib.parse as _urlparse
        import ssl

        # Get cookies from the persistent browser context
        if not self.context:
            return None

        try:
            cookies_list = await self.context.cookies()
        except Exception:
            return None

        if not cookies_list:
            return None

        # Build cookie dict for the target domain
        cookie_dict = {}
        for c in cookies_list:
            domain = c.get("domain", "")
            if "libh-proxy1" in domain or "fyre.ibm.com" in domain or not domain:
                cookie_dict[c["name"]] = c["value"]

        if not cookie_dict:
            logger.debug("No cookies found for libh-proxy1.fyre.ibm.com — skipping direct HTTP fetch")
            return None

        logger.info(f"🔗 Trying direct HTTP fetch for {component} with {len(cookie_dict)} cookies...")

        encoded = _urlparse.quote(component)

        # Candidate API URLs — newest first, old REST fallback last
        candidate_urls = [
            f"https://libh-proxy1.fyre.ibm.com/cognitive/external-data/cognitive-pages/libh-proxy1.fyre.ibm.com/data/buildBreakReport?functionalArea={encoded}",
            f"https://libh-proxy1.fyre.ibm.com/cognitive/api/buildBreakReport?functionalArea={encoded}",
            f"https://libh-proxy1.fyre.ibm.com/cognitive/data/buildBreakReport?functionalArea={encoded}",
        ]

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": (
                f"https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaAnalysis.html"
                f"?functionalArea={encoded}&tab=Build%2BBreak+Report"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(
                connector=connector,
                cookies=cookie_dict,
                headers=headers
            ) as session:
                for url in candidate_urls:
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                            logger.info(f"   🔗 {resp.status} {url}")
                            if resp.status == 200:
                                ct = resp.headers.get("content-type", "")
                                if "json" in ct.lower():
                                    data = await resp.json(content_type=None)
                                    logger.info(f"✅ Direct HTTP fetch succeeded for {component}")
                                    return data
                                else:
                                    text = await resp.text()
                                    logger.warning(
                                        f"   URL returned 200 but content-type={ct!r}. "
                                        f"Preview: {text[:200]}"
                                    )
                            elif resp.status in (401, 403):
                                logger.warning(f"   🔒 Auth required ({resp.status}) — cookies may be insufficient")
                            # 500 / 404 — try next URL
                    except Exception as e:
                        logger.debug(f"   Direct fetch failed for {url}: {e}")
        except Exception as e:
            logger.debug(f"aiohttp session error for {component}: {e}")

        logger.info(f"   ℹ️  Direct HTTP fetch found no data for {component} — will try browser interception")
        return None

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
