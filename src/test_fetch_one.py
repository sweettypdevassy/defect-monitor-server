#!/usr/bin/env python3
"""
Test the fetch by calling the RUNNING server's refresh endpoint.
This uses the live gunicorn process where the browser context IS active.

Run: docker compose exec defect-monitor python3 src/test_fetch_one.py
"""
import sys, time, json
import requests, urllib3
urllib3.disable_warnings()

BASE = 'http://localhost:5000'
COMPONENT = 'Batch'

print(f"\n{'='*60}")
print(f"Triggering refresh for: {COMPONENT}")
print(f"{'='*60}\n")

# Step 1: Trigger async refresh
try:
    r = requests.post(f'{BASE}/api/refresh-component/{COMPONENT}', timeout=10)
    print(f"Trigger: [{r.status_code}] {r.text[:200]}")
    refresh_id = r.json().get('refresh_id', '') if r.status_code == 200 else ''
except Exception as e:
    print(f"Trigger error: {e}")
    refresh_id = ''

if refresh_id:
    print(f"\nWaiting for refresh {refresh_id} to complete...")
    for i in range(30):
        time.sleep(2)
        try:
            s = requests.get(f'{BASE}/api/refresh-status/{refresh_id}', timeout=5)
            if s.status_code == 200:
                status = s.json()
                print(f"  [{i*2}s] status={status.get('status','?')} progress={status.get('progress','?')}")
                if status.get('status') in ('completed', 'done', 'finished', 'error'):
                    print(f"  Final: {status}")
                    break
        except Exception as e:
            print(f"  [{i*2}s] status check error: {e}")
else:
    print("No refresh_id, waiting 30s for background fetch...")
    time.sleep(30)

# Step 2: Check results
print(f"\n{'='*60}")
print(f"Checking fetched defects for {COMPONENT}...")
print(f"{'='*60}\n")

try:
    r = requests.get(f'{BASE}/api/insights/{COMPONENT}', timeout=15)
    print(f"Insights [{r.status_code}]")
    if r.status_code == 200:
        data = r.json()
        defects = data.get('defects', data.get('allDefects', []))
        print(f"Defects: {len(defects)}")
        if defects:
            d = defects[0]
            print(f"First: id={d.get('id')} summary={d.get('summary','')[:60]} source={d.get('source','?')}")
    else:
        print(r.text[:300])
except Exception as e:
    print(f"Insights error: {e}")

# Also check all-components data
try:
    r = requests.get(f'{BASE}/api/all-components', timeout=15)
    if r.status_code == 200:
        data = r.json()
        comps = data if isinstance(data, list) else data.get('components', [])
        batch = next((c for c in comps if isinstance(c, dict) and 
                      COMPONENT.lower() in c.get('name','').lower()), None)
        if batch:
            print(f"\nAll-components data for {COMPONENT}:")
            print(f"  defects={batch.get('defect_count', batch.get('defects','?'))}")
            print(f"  last_updated={batch.get('last_updated','?')}")
        else:
            print(f"\nAll-components: {COMPONENT} not found. Keys sample: {str(comps[:2])[:200]}")
except Exception as e:
    print(f"All-components error: {e}")

# Check live logs for the browser/SW activity
print(f"\n{'='*60}")
print("Checking container logs for browser/SW fetch activity...")
print(f"{'='*60}\n")
import subprocess
result = subprocess.run(
    ['docker', 'compose', 'logs', '--tail=50', 'defect-monitor'],
    capture_output=True, text=True, cwd='/app'
)
lines = result.stdout.split('\n')
relevant = [l for l in lines if any(k in l for k in [
    'SW fetch', 'service worker', 'FOUND DATA', 'Browser/SW', 'fetch()',
    'Calling fetch', 'Navigating to', 'external-data', 'evaluate',
    COMPONENT, 'defects for'
])]
for l in relevant[-30:]:
    print(l)

print(f"\n{'='*60}\nDone.\n{'='*60}")
