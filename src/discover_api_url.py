#!/usr/bin/env python3
"""
One-shot script to discover the real backend API URL that the cognitive portal
React SPA calls when loading the Build Break Report for a component.

Run this ONCE on the VM (where the browser is already logged in):
    docker-compose exec defect-monitor python3 src/discover_api_url.py

It will:
1. Open a new Playwright page with --disable-features=ServiceWorker
2. Navigate to the Batch component Build Break Report page
3. Intercept ALL network requests (before any service worker can cache them)
4. Print every request URL so you can identify the data API endpoint

Once you see the API URL in the output, update defect_checker.py to use it directly.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright
from cookie_storage import load_cookies
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def discover():
    async with async_playwright() as pw:
        logger.info("🚀 Launching browser with ServiceWorker disabled...")
        context = await pw.chromium.launch_persistent_context(
            "/app/data/chrome_profile",
            headless=False,
            ignore_https_errors=True,
            args=[
                '--no-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--window-size=1920,1080',
                '--disable-features=ServiceWorker',
                '--disable-blink-features=AutomationControlled',
            ],
        )

        # Load saved cookies so we're already authenticated
        saved_cookies = load_cookies()
        if saved_cookies:
            await context.add_cookies(saved_cookies)
            logger.info(f"✅ Loaded {len(saved_cookies)} cookies")
        else:
            logger.warning("⚠️  No saved cookies — you may need to login first")

        page = await context.new_page()

        # Intercept ALL requests BEFORE navigation
        captured_requests = []

        async def on_request(request):
            url = request.url
            method = request.method
            # Skip static assets
            if not any(url.endswith(ext) for ext in ('.js', '.css', '.png', '.ico', '.woff', '.ttf', '.map', '.svg')):
                captured_requests.append((method, url))
                logger.info(f"   ➡️  REQUEST  [{method}] {url}")

        async def on_response(response):
            url = response.url
            status = response.status
            ct = response.headers.get('content-type', '')
            if not any(url.endswith(ext) for ext in ('.js', '.css', '.png', '.ico', '.woff', '.ttf', '.map', '.svg')):
                logger.info(f"   ⬅️  RESPONSE [{status}] {url}  ct={ct[:60]}")
                if status == 200 and 'json' in ct.lower():
                    try:
                        body = await response.json()
                        body_str = str(body)[:200]
                        if any(kw in body_str for kw in ['defect', 'Defect', 'RTC', 'untriaged', 'functional']):
                            logger.info(f"\n{'='*70}")
                            logger.info(f"🎯 FOUND DATA API URL: {url}")
                            logger.info(f"   Body preview: {body_str[:300]}")
                            logger.info(f"{'='*70}\n")
                    except Exception:
                        pass

        page.on('request', on_request)
        page.on('response', on_response)

        test_component = 'Batch'
        import urllib.parse
        encoded = urllib.parse.quote(test_component)
        page_url = (
            f"https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaAnalysis.html"
            f"?functionalArea={encoded}&tab=Build%2BBreak+Report"
        )

        logger.info(f"\n🌐 Navigating to: {page_url}\n")
        try:
            await page.goto(page_url, wait_until='domcontentloaded', timeout=30000)
        except Exception as e:
            logger.warning(f"Navigation warning: {e}")

        logger.info("⏳ Waiting 20s for React to load and make API calls...")
        await asyncio.sleep(20)

        logger.info(f"\n{'='*70}")
        logger.info("📋 ALL captured non-static requests:")
        for method, url in captured_requests:
            logger.info(f"   [{method}] {url}")
        logger.info(f"{'='*70}")

        # Also check current page DOM for any data
        try:
            dom_info = await page.evaluate("""
                () => ({
                    title: document.title,
                    url: window.location.href,
                    bodyText: document.body ? document.body.innerText.substring(0, 500) : '',
                    tableCount: document.querySelectorAll('table').length,
                    rowCount: document.querySelectorAll('tr').length,
                })
            """)
            logger.info(f"\n📄 Page state after 20s:")
            logger.info(f"   Title: {dom_info.get('title')}")
            logger.info(f"   URL:   {dom_info.get('url')}")
            logger.info(f"   Tables: {dom_info.get('tableCount')}, Rows: {dom_info.get('rowCount')}")
            logger.info(f"   Text:  {dom_info.get('bodyText','')[:300]}")
        except Exception as e:
            logger.error(f"DOM eval error: {e}")

        await context.close()
        logger.info("\n✅ Discovery complete. Check output above for the API URL.")


if __name__ == '__main__':
    asyncio.run(discover())
