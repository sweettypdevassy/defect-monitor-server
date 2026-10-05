#!/usr/bin/env python3
"""
Probe script v2 — focuses on /cognitive/external-data/ which returns 500
(meaning the path exists but the parameters are wrong).

Also tries to discover the exact API by fetching the JS bundle and searching
for the API URL pattern, and by trying the functional area list API.

Run on the VM:
    docker-compose exec defect-monitor python3 src/probe_api_url.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json
import logging
import urllib3
urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

COMPONENT = 'Batch'

# ─── Load saved cookies ───────────────────────────────────────────────────────
try:
    from cookie_storage import load_cookies
    raw_cookies = load_cookies()
    if not raw_cookies:
        logger.error("No saved cookies found. Authenticate first via the main app.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://libh-proxy1.fyre.ibm.com/cognitive/functionalAreaAnalysis.html',
        'X-Requested-With': 'XMLHttpRequest',
    })
    for c in raw_cookies:
        domain = c.get('domain', '').lstrip('.')
        session.cookies.set(c['name'], c['value'], domain=domain, path=c.get('path', '/'))
    logger.info(f"✅ Loaded {len(raw_cookies)} cookies into session")
except Exception as e:
    logger.error(f"Failed to load cookies: {e}")
    sys.exit(1)

BASE = 'https://libh-proxy1.fyre.ibm.com'

def probe(url, extra_headers=None):
    try:
        h = {}
        if extra_headers:
            h.update(extra_headers)
        resp = session.get(url, timeout=20, verify=False, headers=h)
        ct = resp.headers.get('content-type', '')
        status = resp.status_code
        body_preview = resp.text[:300].replace('\n', ' ')
        print(f"  [{status}] ct={ct[:50]}")
        print(f"  body: {body_preview}")
        if status == 200 and 'json' in ct.lower():
            try:
                data = resp.json()
                print(f"  JSON keys: {list(data.keys()) if isinstance(data, dict) else 'list['+str(len(data))+']'}")
                return data
            except Exception:
                pass
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


print(f"\n{'='*70}")
print("PHASE 1: Try /cognitive/external-data/ with many parameter variations")
print(f"{'='*70}\n")

# The 500 means path exists — try different parameter names and combinations
external_data_variants = [
    # Single param variants
    f"{BASE}/cognitive/external-data/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildBreakReport?fa={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildBreakReport?name={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildBreakReport?component={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildBreakReport?area={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildBreakReport?fas={COMPONENT}",
    # With tab param (matches the HTML page URL)
    f"{BASE}/cognitive/external-data/buildBreakReport?functionalArea={COMPONENT}&tab=Build+Break+Report",
    f"{BASE}/cognitive/external-data/buildBreakReport?functionalArea={COMPONENT}&tab=buildBreakReport",
    # Path-based component (REST style)
    f"{BASE}/cognitive/external-data/buildBreakReport/{COMPONENT}",
    f"{BASE}/cognitive/external-data/{COMPONENT}/buildBreakReport",
    f"{BASE}/cognitive/external-data/defects/{COMPONENT}",
    # Different report endpoint names
    f"{BASE}/cognitive/external-data/build-break-report?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildbreak-report?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/reports/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/report?type=buildBreakReport&functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/data?type=buildBreakReport&functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/data?report=buildBreakReport&functionalArea={COMPONENT}",
    # No param (base endpoint — may return schema or list)
    f"{BASE}/cognitive/external-data/buildBreakReport",
    f"{BASE}/cognitive/external-data/",
    f"{BASE}/cognitive/external-data",
]

for url in external_data_variants:
    print(f"→ {url}")
    result = probe(url)
    if result is not None:
        print(f"\n🎯 FOUND IT! {url}\n")
        break
    print()


print(f"\n{'='*70}")
print("PHASE 2: Fetch functional area list API (to understand URL structure)")
print(f"{'='*70}\n")

list_urls = [
    f"{BASE}/cognitive/external-data/functionalAreaList",
    f"{BASE}/cognitive/external-data/functionalAreas",
    f"{BASE}/cognitive/external-data/functionalArea",
    f"{BASE}/cognitive/external-data/components",
    f"{BASE}/cognitive/external-data/list",
    f"{BASE}/cognitive/external-data/areas",
]
for url in list_urls:
    print(f"→ {url}")
    result = probe(url)
    if result is not None:
        print(f"\n🎯 List API found! {url}\n")
        break
    print()


print(f"\n{'='*70}")
print("PHASE 3: Fetch the React JS bundle to find the API URL pattern")
print(f"{'='*70}\n")

# Get the HTML page first to find JS bundle URLs
try:
    html_resp = session.get(
        f"{BASE}/cognitive/functionalAreaAnalysis.html",
        timeout=20, verify=False,
        headers={'Accept': 'text/html'}
    )
    html = html_resp.text

    # Find all script src tags
    import re
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
    print(f"Found {len(scripts)} script tags in HTML")

    # Look for main/chunk JS bundles
    js_bundles = [s for s in scripts if s.endswith('.js') and ('main' in s or 'chunk' in s or 'bundle' in s or 'app' in s.lower())]
    if not js_bundles:
        js_bundles = [s for s in scripts if s.endswith('.js')]

    print(f"Checking {min(3, len(js_bundles))} JS bundles for API URL patterns...")

    for js_url in js_bundles[:3]:
        if not js_url.startswith('http'):
            js_url = BASE + ('/' if not js_url.startswith('/') else '') + js_url
        print(f"\n→ Fetching JS bundle: {js_url}")
        try:
            js_resp = session.get(js_url, timeout=30, verify=False, headers={'Accept': 'application/javascript'})
            js = js_resp.text

            # Search for API URL patterns
            api_patterns = re.findall(r'["\']([^"\']*(?:external.data|buildBreak|functionalArea|buildbreak|defects/build)[^"\']*)["\']', js, re.IGNORECASE)
            if api_patterns:
                print(f"  🎯 API URL patterns found in bundle:")
                for p in set(api_patterns):
                    print(f"     {p}")
            else:
                print(f"  (no API URL patterns found in this bundle)")
        except Exception as e:
            print(f"  ERROR fetching bundle: {e}")

except Exception as e:
    print(f"Could not fetch HTML page: {e}")


print(f"\n{'='*70}")
print("PHASE 4: Try with Accept: text/html (some APIs check Accept header)")
print(f"{'='*70}\n")

for url in [
    f"{BASE}/cognitive/external-data/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildBreakReport?fas={COMPONENT}",
]:
    print(f"→ {url}  [Accept: text/html]")
    probe(url, {'Accept': 'text/html,application/xhtml+xml,*/*'})
    print()

print(f"{'='*70}")
print("Done.")
print(f"{'='*70}")
