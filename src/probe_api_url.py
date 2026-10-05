#!/usr/bin/env python3
"""
Probe v4: 
- Fix JS bundle URL (missing slash)
- Grep bundle for ALL URL strings to find the real API endpoint
- Try the JSESSIONID-based Java backend directly
- Check if backend service is on a different port

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
print("PHASE 1: Fetch JS bundle and grep ALL URL patterns")
print("="*70)

try:
    html_r = s.get(f"{BASE}/cognitive/functionalAreaAnalysis.html", timeout=15, verify=False,
                   headers={'Accept': 'text/html'})
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html_r.text)
    print(f"Script tags: {scripts}")

    for raw_path in scripts:
        if 'vendor' in raw_path:
            continue
        # Fix: ensure there's a / between BASE and path
        if raw_path.startswith('/'):
            js_url = BASE + raw_path
        else:
            js_url = BASE + '/' + raw_path
        print(f"\nFetching: {js_url}")
        js_r = s.get(js_url, timeout=60, verify=False)
        js = js_r.text
        print(f"Size: {len(js):,} bytes")

        # Find ALL path-like strings (anything starting with / that has letters)
        all_paths = set()
        for pattern in [
            r'"(/[\w\-/\.?=&%+#]{4,150})"',
            r"'(/[\w\-/\.?=&%+#]{4,150})'",
        ]:
            all_paths.update(re.findall(pattern, js))

        # Filter to interesting ones
        keywords = ['external', 'data', 'api', 'defect', 'build', 'report',
                    'functional', 'area', 'cognitive', 'backend', 'service',
                    'proxy', 'rest', 'json', 'result', 'analysis']
        interesting = sorted(p for p in all_paths if any(k in p.lower() for k in keywords))

        print(f"\nAll interesting path strings ({len(interesting)}):")
        for p in interesting:
            print(f"   {p}")

        # Also show ALL paths starting with /cognitive
        cognitive_paths = sorted(p for p in all_paths if '/cognitive' in p.lower() or 'external' in p.lower())
        if cognitive_paths:
            print(f"\n/cognitive/ paths specifically:")
            for p in cognitive_paths:
                print(f"   {p}")

        # Template literals
        tmpls = re.findall(r'`([^`]*\$\{[^`]*)[`]', js)
        url_tmpls = [t for t in tmpls if '/' in t and any(k in t.lower() for k in keywords)]
        if url_tmpls:
            print(f"\nTemplate URL patterns:")
            for t in url_tmpls[:30]:
                print(f"   {t}")

except Exception as e:
    print(f"Error: {e}")
    import traceback; traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 2: The JSESSIONID exists — try the Java backend directly")
print("="*70)
# JSESSIONID suggests a Java app server (WebSphere/Liberty) behind the proxy.
# The old URL /buildBreakReport/rest2/... was served by a Java app.
# The JSESSIONID cookie domain is libh-proxy1.fyre.ibm.com — same proxy.
# Try hitting the old Java backend path WITH the new JSESSIONID cookie.
jsession = next((c for c in raw_cookies if c['name'] == 'JSESSIONID'), None)
if jsession:
    print(f"JSESSIONID value: {jsession['value'][:20]}...")
    java_candidates = [
        f"{BASE}/buildBreakReport/rest2/defects/buildbreak/fas?fas={COMPONENT}",
        f"{BASE}/buildBreakReport/rest2/defects/buildbreak/fas?functionalArea={COMPONENT}",
        f"{BASE}/buildBreakReport/api/buildBreakReport?functionalArea={COMPONENT}",
        f"{BASE}/buildBreakReport/api/defects?functionalArea={COMPONENT}",
    ]
    for url in java_candidates:
        try:
            r = s.get(url, timeout=15, verify=False)
            ct = r.headers.get('content-type','')
            print(f"  [{r.status_code}] {url}")
            print(f"   ct={ct}  body={r.text[:200].replace(chr(10),' ')!r}")
            if r.status_code == 200 and 'json' in ct.lower():
                print(f"   🎯 JSON DATA: {r.text[:400]}")
        except Exception as e:
            print(f"  ERROR {url}: {e}")
else:
    print("No JSESSIONID cookie found.")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 3: Check what the /cognitive/version/ response reveals about backend")
print("="*70)
r = s.get(f"{BASE}/cognitive/version/", timeout=10, verify=False)
print(f"version/ response: {r.json()}")
# image: 202609.15 means Sept 2026 build — relatively new


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 4: Try the /cognitive/external-data/ as a POST (some APIs require POST)")
print("="*70)
post_payloads = [
    {"functionalArea": COMPONENT},
    {"fas": COMPONENT},
    {"functionalArea": COMPONENT, "tab": "Build Break Report"},
    {"component": COMPONENT},
]
for payload in post_payloads:
    try:
        r = s.post(f"{BASE}/cognitive/external-data/buildBreakReport",
                   json=payload, timeout=15, verify=False,
                   headers={'Content-Type': 'application/json'})
        ct = r.headers.get('content-type','')
        print(f"  POST {payload} → [{r.status_code}] ct={ct} body={r.text[:200]!r}")
    except Exception as e:
        print(f"  POST {payload} → ERROR: {e}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 5: Try fetching /cognitive/functionalAreaList.html data API")
print("        (the list page must also have a backend data call)")
print("="*70)
list_page = s.get(f"{BASE}/cognitive/functionalAreaList.html", timeout=15, verify=False,
                  headers={'Accept': 'text/html'})
list_scripts = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', list_page.text)
print(f"functionalAreaList.html scripts: {list_scripts}")

# The functionalAreaList page loads a different bundle — grep that one too
for raw_path in list_scripts:
    if 'vendor' in raw_path:
        continue
    js_url = BASE + ('/' if not raw_path.startswith('/') else '') + raw_path
    print(f"\nFetching list bundle: {js_url}")
    try:
        js_r = s.get(js_url, timeout=60, verify=False)
        js = js_r.text
        print(f"Size: {len(js):,} bytes")
        # Find ALL path strings
        all_paths = set()
        for pattern in [r'"(/[\w\-/\.?=&%+#]{4,150})"', r"'(/[\w\-/\.?=&%+#]{4,150})'"]:
            all_paths.update(re.findall(pattern, js))
        keywords = ['external', 'data', 'api', 'defect', 'build', 'report', 'functional', 'area']
        interesting = sorted(p for p in all_paths if any(k in p.lower() for k in keywords))
        print(f"Interesting paths ({len(interesting)}):")
        for p in interesting:
            print(f"   {p}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*70 + "\nDone.\n" + "="*70)
