#!/usr/bin/env python3
"""
Probe v6: The JS bundle reveals the API base path is /data/
The full URL is likely: /cognitive/data/buildBreakReport?functionalArea=Batch

Also grep the full bundle for all strings near '/data/' to find exact endpoint names.

Run: docker compose exec defect-monitor python3 src/probe_api_url.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests, urllib3
urllib3.disable_warnings()

BASE = 'https://libh-proxy1.fyre.ibm.com'
COMPONENT = 'Batch'

try:
    from cookie_storage import load_cookies
    raw_cookies = load_cookies()
    if not raw_cookies:
        print("No saved cookies."); sys.exit(1)
except Exception as e:
    print(f"Cookie load error: {e}"); sys.exit(1)

def make_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'{BASE}/cognitive/functionalAreaAnalysis.html?functionalArea={COMPONENT}&tab=Build%2BBreak+Report',
        'X-Requested-With': 'XMLHttpRequest',
    })
    for c in raw_cookies:
        s.cookies.set(c['name'], c['value'], domain=c.get('domain','').lstrip('.'), path=c.get('path','/'))
    return s

s = make_session()

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 1: Download the real bundle and extract all strings near '/data/'")
print("="*70)

bundle_url = f"{BASE}/cognitive/functionalAreaAnalysis.d06857684759d207a9f4.js"
js_r = s.get(bundle_url, timeout=60, verify=False)
js = js_r.text
print(f"Bundle size: {len(js):,} bytes")

# Find every occurrence of '/data' in the bundle and show 200 chars of context
print("\nAll occurrences of '/data' in bundle (with context):")
for m in re.finditer(r'.{0,150}/data.{0,150}', js):
    snippet = m.group().replace('\n', ' ')
    # Only show if it looks URL-like (has quotes around the path)
    if any(q in snippet for q in ['"', "'"]):
        print(f"  ...{snippet}...")

# Extract all string literals containing 'data'
data_strings = set()
for pat in [r'"([^"]*data[^"]*)"', r"'([^']*data[^']*)'"]:
    for m in re.findall(pat, js, re.IGNORECASE):
        if '/' in m and 3 < len(m) < 200:
            data_strings.add(m)

print(f"\nAll string literals containing 'data' with a slash ({len(data_strings)}):")
for ds in sorted(data_strings):
    print(f"  {ds!r}")

# Also extract ALL string literals that look like paths (start with /)
all_paths = set()
for pat in [r'"(/[^"]{3,120})"', r"'(/[^']{3,120})'"]:
    all_paths.update(re.findall(pat, js))
print(f"\nAll path-like strings in bundle ({len(all_paths)}):")
for p in sorted(all_paths):
    print(f"  {p!r}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 2: Try all /cognitive/data/ endpoint variations")
print("="*70)

data_candidates = [
    # Direct /data/ under /cognitive/
    f"{BASE}/cognitive/data/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/data/buildBreakReport?fas={COMPONENT}",
    f"{BASE}/cognitive/data/buildBreakReport/{COMPONENT}",
    f"{BASE}/cognitive/data/defects?functionalArea={COMPONENT}&type=buildBreak",
    f"{BASE}/cognitive/data/defects/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/data/functionalAreaAnalysis?functionalArea={COMPONENT}&tab=Build+Break+Report",
    f"{BASE}/cognitive/data/functionalAreaAnalysis?functionalArea={COMPONENT}",
    f"{BASE}/cognitive/data/functionalAreaList",
    f"{BASE}/cognitive/data/",
    f"{BASE}/cognitive/data",
    # Also try without /cognitive/ prefix
    f"{BASE}/data/buildBreakReport?functionalArea={COMPONENT}",
    f"{BASE}/data/buildBreakReport?fas={COMPONENT}",
    f"{BASE}/data/functionalAreaList",
]

for url in data_candidates:
    try:
        r = s.get(url, timeout=15, verify=False)
        ct = r.headers.get('content-type', '')
        status = r.status_code
        body = r.text[:300].replace('\n', ' ')
        if status == 200 and 'json' in ct.lower():
            try:
                data = r.json()
                data_str = str(data)
                print(f"\n🎯 [{status}] JSON FOUND: {url}")
                print(f"   keys={list(data.keys()) if isinstance(data, dict) else 'list['+str(len(data))+']'}")
                print(f"   preview: {data_str[:400]}")
            except Exception:
                print(f"  [{status}] {url}  ct={ct}  body={body[:150]!r}")
        elif status == 200:
            print(f"  [{status}] HTML {url}  len={len(r.text)}")
        elif status == 404:
            print(f"  [404] {url}")
        elif status == 500:
            print(f"  [500] {url}  (nginx backend error)")
        else:
            print(f"  [{status}] {url}  ct={ct}  body={body[:80]!r}")
    except Exception as e:
        print(f"  ERROR {url}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 3: Full bundle text search — find ALL API call patterns")
print("         (fetch(, axios., XMLHttpRequest, .get(, .post()")
print("="*70)

# Find all fetch( calls and what URL they use
fetch_calls = re.findall(r'fetch\(([^)]{3,200})\)', js)
print(f"\nfetch() calls ({len(fetch_calls)}):")
for f in fetch_calls[:30]:
    print(f"  fetch({f})")

# Find axios calls
axios_calls = re.findall(r'axios\.\w+\(([^)]{3,200})\)', js)
if axios_calls:
    print(f"\naxios calls ({len(axios_calls)}):")
    for a in axios_calls[:20]:
        print(f"  axios.x({a})")

# Find .get( / .post( on a client object
client_calls = re.findall(r'\.(get|post|put|delete)\(["\']([^"\']{3,150})["\']', js)
if client_calls:
    print(f"\nclient.get/post calls ({len(client_calls)}):")
    for method, path in client_calls[:30]:
        print(f"  .{method}('{path}')")

print("\n" + "="*70 + "\nDone.\n" + "="*70)
