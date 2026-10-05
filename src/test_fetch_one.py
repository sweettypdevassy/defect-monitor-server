#!/usr/bin/env python3
"""
Trigger a fetch through the RUNNING server's HTTP API so it uses
the live browser context (with service worker active).

Run: docker compose exec defect-monitor python3 src/test_fetch_one.py
"""
import sys, os, json, time
sys.path.insert(0, '/app/src')

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import requests
import urllib3
urllib3.disable_warnings()

BASE = 'http://localhost:5000'

print("\n" + "="*60)
print("METHOD 1: Trigger fetch via running server API")
print("="*60)

# Trigger a background fetch for Batch via the /fetch_component endpoint
try:
    r = requests.post(f'{BASE}/api/fetch_component',
                      json={'component': 'Batch'},
                      timeout=120)
    print(f"POST /api/fetch_component → [{r.status_code}]")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"POST /api/fetch_component → ERROR: {e}")

# Also try GET variant
try:
    r = requests.get(f'{BASE}/api/fetch_component?component=Batch', timeout=120)
    print(f"\nGET /api/fetch_component?component=Batch → [{r.status_code}]")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"GET → ERROR: {e}")

print("\n" + "="*60)
print("METHOD 2: Use the browser manager directly from INSIDE the container")
print("(shares the same process as gunicorn via import)")
print("="*60)

# Try to connect to the running gunicorn's browser manager via its socket
# The browser manager is a singleton — in gunicorn it's already started
# We need to use the SAME process. Let's check if we can call it via the app

try:
    # Check what API endpoints exist
    r = requests.get(f'{BASE}/health', timeout=5)
    print(f"Health: [{r.status_code}] {r.text[:100]}")
    
    # Try dashboard data which triggers a real fetch
    r = requests.get(f'{BASE}/api/dashboard_data?component=Batch&force_refresh=true', timeout=120)
    print(f"\nGET /api/dashboard_data?component=Batch → [{r.status_code}]")
    if r.status_code == 200:
        data = r.json()
        print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
        defects = data.get('defects', data.get('data', []))
        print(f"Defects count: {len(defects) if isinstance(defects, list) else '?'}")
        if defects and isinstance(defects, list):
            print(f"First defect: {defects[0]}")
    else:
        print(f"Body: {r.text[:300]}")
except Exception as e:
    print(f"ERROR: {e}")


print("\n" + "="*60)
print("METHOD 3: Check all available API routes on running server")
print("="*60)

try:
    endpoints = [
        '/api/components',
        '/api/defects?component=Batch',
        '/api/fetch?component=Batch',
        '/dashboard',
        '/api/trigger_fetch',
        '/api/refresh',
    ]
    for ep in endpoints:
        try:
            r = requests.get(f'{BASE}{ep}', timeout=10)
            print(f"  [{r.status_code}] {ep}  ct={r.headers.get('content-type','')[:40]}")
            if r.status_code == 200 and 'json' in r.headers.get('content-type',''):
                body = r.json()
                if isinstance(body, list) and len(body) > 0:
                    print(f"    → list[{len(body)}], first={str(body[0])[:100]}")
                elif isinstance(body, dict):
                    print(f"    → keys={list(body.keys())[:5]}")
        except Exception as e:
            print(f"  [ERR] {ep}: {e}")
except Exception as e:
    print(f"ERROR: {e}")


print("\n" + "="*60)
print("METHOD 4: Run the service worker fetch test from inside the")
print("          EXISTING browser context (attach to running gunicorn)")
print("="*60)

# The browser manager in gunicorn has context. We can't share it across
# processes. But we CAN use the /api/ endpoint to trigger and wait.
# Let's find the right trigger endpoint by checking app.py routes.

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "/app/src/app.py")
    # Just read the routes from the file without importing
    with open('/app/src/app.py') as f:
        app_content = f.read()
    import re
    routes = re.findall(r'@app\.route\(["\']([^"\']+)["\']', app_content)
    print(f"Available routes in app.py ({len(routes)}):")
    for r in routes:
        print(f"  {r}")
except Exception as e:
    print(f"ERROR reading routes: {e}")

print("\n" + "="*60 + "\nDone.\n" + "="*60)
