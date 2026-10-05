#!/usr/bin/env python3
"""
Deep diagnostic: 
1. Show all saved cookies and their domains
2. Try /cognitive/external-data/ with different cookie subsets
3. Check Apache error log hints via response headers
4. Try POST instead of GET
5. Read the full 500 response body (Apache hides it with padding comment)
6. Try fetching the functionalAreaList.html page data API

Run on the VM:
    docker-compose exec defect-monitor python3 src/probe_api_url.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json
import re
import logging
import urllib3
urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

BASE = 'https://libh-proxy1.fyre.ibm.com'
COMPONENT = 'Batch'

# ─── Load saved cookies ───────────────────────────────────────────────────────
try:
    from cookie_storage import load_cookies
    raw_cookies = load_cookies()
    if not raw_cookies:
        logger.error("No saved cookies. Authenticate first.")
        sys.exit(1)
    logger.info(f"Loaded {len(raw_cookies)} raw cookies")
except Exception as e:
    logger.error(f"Failed to load cookies: {e}")
    sys.exit(1)

print(f"\n{'='*70}")
print("PHASE 1: List all saved cookies and their domains")
print(f"{'='*70}")
for c in raw_cookies:
    print(f"  name={c.get('name'):45s} domain={c.get('domain',''):40s} path={c.get('path','/')}")

def make_session(cookie_filter=None):
    """Build a requests session with all or a subset of cookies."""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'{BASE}/cognitive/functionalAreaAnalysis.html?functionalArea={COMPONENT}&tab=Build%2BBreak+Report',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': BASE,
    })
    for c in raw_cookies:
        if cookie_filter and c.get('name') not in cookie_filter:
            continue
        domain = c.get('domain', '').lstrip('.')
        s.cookies.set(c['name'], c['value'], domain=domain, path=c.get('path', '/'))
    return s

def probe(session, url, method='GET', extra_headers=None, data=None):
    try:
        h = extra_headers or {}
        if method == 'GET':
            r = session.get(url, timeout=20, verify=False, headers=h)
        else:
            r = session.post(url, timeout=20, verify=False, headers=h, data=data or {})
        ct = r.headers.get('content-type', '')
        status = r.status_code
        # Show ALL response headers for 500s
        if status >= 500:
            print(f"  [{status}] ct={ct}")
            print(f"  Response headers: {dict(r.headers)}")
            print(f"  Full body ({len(r.text)} bytes): {r.text[:800]}")
        elif status == 200 and 'json' in ct.lower():
            try:
                body = r.json()
                print(f"  [200 JSON] keys={list(body.keys()) if isinstance(body,dict) else 'list['+str(len(body))+']'}")
                print(f"  preview: {str(body)[:400]}")
                return body
            except Exception:
                print(f"  [200] ct={ct} body={r.text[:200]}")
        else:
            print(f"  [{status}] ct={ct} body={r.text[:150].replace(chr(10),' ')!r}")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


print(f"\n{'='*70}")
print("PHASE 2: Full 500 response body + all response headers")
print(f"{'='*70}\n")

s = make_session()
test_url = f"{BASE}/cognitive/external-data/buildBreakReport?functionalArea={COMPONENT}"
print(f"→ GET {test_url}")
probe(s, test_url)


print(f"\n{'='*70}")
print("PHASE 3: Try with only the OIDC session cookie (mod_auth_openidc_session)")
print(f"{'='*70}\n")

oidc_names = [c['name'] for c in raw_cookies if 'openidc' in c.get('name','').lower() or 'oidc' in c.get('name','').lower() or 'session' in c.get('name','').lower()]
print(f"OIDC/session cookie names: {oidc_names}")
if oidc_names:
    s2 = make_session(cookie_filter=oidc_names)
    print(f"→ GET {test_url}  [only oidc cookies]")
    probe(s2, test_url)


print(f"\n{'='*70}")
print("PHASE 4: Try the functionalAreaList data API (simpler endpoint)")
print(f"{'='*70}\n")

s = make_session()
list_candidates = [
    f"{BASE}/cognitive/external-data/functionalAreaList",
    f"{BASE}/cognitive/external-data/navigation",
    f"{BASE}/cognitive/navigation.json",
    f"{BASE}/cognitive/version/",
    f"{BASE}/cognitive/whoami/",
    f"{BASE}/cognitive/proxy_links.json",
]
for url in list_candidates:
    print(f"→ {url}")
    result = probe(s, url)
    if result is not None:
        print(f"  🎯 DATA FOUND at: {url}")
    print()


print(f"\n{'='*70}")
print("PHASE 5: Grep the full JS bundle for ALL URL strings")
print(f"{'='*70}\n")

s = make_session()
try:
    html_r = s.get(f"{BASE}/cognitive/functionalAreaAnalysis.html", timeout=15, verify=False, headers={'Accept':'text/html'})
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html_r.text)
    print(f"Script tags found: {scripts}")

    # Fetch the component-specific bundle (not vendor)
    app_bundle = next((s for s in scripts if 'vendor' not in s), scripts[0] if scripts else None)
    if app_bundle:
        js_url = app_bundle if app_bundle.startswith('http') else BASE + app_bundle
        print(f"\nFetching app bundle: {js_url}")
        js_r = make_session().get(js_url, timeout=60, verify=False)
        js = js_r.text
        print(f"Bundle size: {len(js):,} bytes")

        # Extract ALL string literals that contain a slash (URL-like)
        # Look for patterns like "external-data", "/cognitive/", "buildBreak" etc.
        hits = set()
        for pattern in [
            r'"(/[^"]{5,120})"',          # "/path/..."
            r"'(/[^']{5,120})'",           # '/path/...'
            r'`(/[^`]{5,120})`',           # `/path/...`
            r'"(https?://[^"]{10,200})"',  # full URLs
        ]:
            for m in re.findall(pattern, js):
                if any(kw in m for kw in ['external', 'buildBreak', 'defect', 'cognitive', 'functional', 'report', 'api/', '/data']):
                    hits.add(m)

        if hits:
            print(f"\n🎯 Interesting URL patterns found in bundle ({len(hits)}):")
            for h in sorted(hits):
                print(f"   {h}")
        else:
            print("No interesting URL patterns found in bundle.")

        # Also look for template literals with variable parts
        tmpl_hits = re.findall(r'["`]([^"`]*\$\{[^}`]+\}[^"`]*)["`]', js)
        url_tmpls = [t for t in tmpl_hits if '/' in t and len(t) > 5]
        if url_tmpls:
            print(f"\n🎯 Template string URL patterns ({len(url_tmpls[:20])}):")
            for t in url_tmpls[:20]:
                print(f"   {t}")

except Exception as e:
    print(f"Error in Phase 5: {e}")
    import traceback
    traceback.print_exc()


print(f"\n{'='*70}")
print("PHASE 6: Check if there is a different cookie name needed (whoami check)")
print(f"{'='*70}\n")

s = make_session()
# The browser network log showed whoami/ returning 200 — check what cookies it needs
whoami_url = f"{BASE}/cognitive/whoami/"
print(f"→ GET {whoami_url}")
result = probe(s, whoami_url)
if result:
    print(f"  whoami data: {result}")

# Also check navigation.json which was 200 in the browser
nav_url = f"{BASE}/cognitive/navigation.json"
print(f"\n→ GET {nav_url}")
result = probe(s, nav_url)
if result:
    print(f"  nav data (first 3 keys): { {k:v for k,v in list(result.items())[:3]} }")

print(f"\n{'='*70}")
print("Done.")
print(f"{'='*70}")
