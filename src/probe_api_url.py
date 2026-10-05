#!/usr/bin/env python3
"""
Probe script to find the correct backend API URL for the new cognitive portal.

The old API was: GET /buildBreakReport/rest2/defects/buildbreak/fas?fas=Batch
The new portal is at: /cognitive/functionalAreaAnalysis.html

This script tries multiple candidate URL patterns using the saved session cookies.

Run on the VM:
    docker-compose exec defect-monitor python3 src/probe_api_url.py

You must be authenticated first (cookies must be saved in /app/data/cookies.json).
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
ENCODED_COMPONENT = 'Batch'

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
    })
    for c in raw_cookies:
        domain = c.get('domain', '').lstrip('.')
        session.cookies.set(c['name'], c['value'], domain=domain, path=c.get('path', '/'))
    logger.info(f"✅ Loaded {len(raw_cookies)} cookies into session")
except Exception as e:
    logger.error(f"Failed to load cookies: {e}")
    sys.exit(1)

# ─── Candidate API URL patterns ──────────────────────────────────────────────
BASE = 'https://libh-proxy1.fyre.ibm.com'
candidates = [
    # Old URL (still there?)
    f"{BASE}/buildBreakReport/rest2/defects/buildbreak/fas?fas={COMPONENT}",
    # New cognitive external-data patterns
    f"{BASE}/cognitive/external-data/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildBreakReport?fas={COMPONENT}",
    f"{BASE}/cognitive/external-data/defects/buildbreak/fas?fas={COMPONENT}",
    f"{BASE}/cognitive/external-data/defects/buildbreak?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildbreak?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/buildbreak?fas={COMPONENT}",
    f"{BASE}/cognitive/api/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/api/defects/buildbreak?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/api/defects?functionalArea={COMPONENT}&type=buildbreak",
    f"{BASE}/cognitive/rest/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/rest2/defects/buildbreak/fas?fas={COMPONENT}",
    f"{BASE}/cognitive/rest/defects/buildbreak/fas?fas={COMPONENT}",
    f"{BASE}/cognitive/data/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/backend/buildBreakReport?functionalArea={COMPONENT}",
    # Tab-specific endpoints
    f"{BASE}/cognitive/external-data/tab/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/external-data/functionalArea/buildBreakReport?functionalArea={COMPONENT}",
]

print(f"\n{'='*70}")
print(f"Probing {len(candidates)} candidate API URLs for component: {COMPONENT}")
print(f"{'='*70}\n")

for url in candidates:
    try:
        resp = session.get(url, timeout=15, verify=False)
        ct = resp.headers.get('content-type', '')
        status = resp.status_code
        
        if status == 200 and 'json' in ct.lower():
            try:
                data = resp.json()
                data_str = str(data)
                if any(kw in data_str for kw in ['defect', 'Defect', 'RTC', 'untriaged', 'summary']):
                    print(f"🎯 MATCH FOUND!")
                    print(f"   URL:    {url}")
                    print(f"   Status: {status}")
                    print(f"   CT:     {ct}")
                    print(f"   Data:   {data_str[:400]}")
                    print()
                else:
                    print(f"✅ 200 JSON (no defect keywords): {url}")
                    print(f"   Data preview: {data_str[:200]}")
                    print()
            except Exception:
                print(f"✅ 200 non-parseable JSON: {url}  ct={ct}")
        elif status == 200:
            text = resp.text[:200]
            print(f"✅ 200 non-JSON: {url}  ct={ct}  text={text[:100]!r}")
        elif status == 302 or status == 301:
            loc = resp.headers.get('location', '')
            if 'login' in loc.lower():
                print(f"🔐 {status} redirect to login: {url}")
            else:
                print(f"↪️  {status} redirect → {loc[:80]}: {url}")
        elif status == 404:
            print(f"❌ 404: {url}")
        elif status == 401 or status == 403:
            print(f"🔒 {status} auth required: {url}")
        else:
            print(f"⚠️  {status}: {url}  ct={ct}  body={resp.text[:80]!r}")
    except requests.exceptions.Timeout:
        print(f"⏱️  TIMEOUT: {url}")
    except Exception as e:
        print(f"💥 ERROR: {url}  → {e}")

print(f"\n{'='*70}")
print("Probe complete.")
print(f"{'='*70}")
