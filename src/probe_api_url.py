#!/usr/bin/env python3
"""
Probe v5: 
- Follow the redirect for JS bundles to get real bundle URL
- Check what the 271-byte response actually is
- Try fetching the page with follow_redirects to get real JS
- Check if there's a separate data service host

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

def make_session(allow_redirects=True):
    s = requests.Session()
    s.max_redirects = 10
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Referer': f'{BASE}/cognitive/functionalAreaAnalysis.html?functionalArea={COMPONENT}&tab=Build%2BBreak+Report',
    })
    for c in raw_cookies:
        s.cookies.set(c['name'], c['value'], domain=c.get('domain','').lstrip('.'), path=c.get('path','/'))
    return s

s = make_session()

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 1: What IS that 271-byte JS bundle response?")
print("="*70)

# The bundle served 271 bytes - let's see what it actually contains
bundle_url = f"{BASE}/functionalAreaAnalysis.d06857684759d207a9f4.js"
r = s.get(bundle_url, timeout=15, verify=False, allow_redirects=False)
print(f"Bundle (no redirect): [{r.status_code}] headers={dict(r.headers)}")
print(f"Body: {r.text!r}")

r2 = s.get(bundle_url, timeout=15, verify=False, allow_redirects=True)
print(f"\nBundle (follow redirect): [{r2.status_code}] url={r2.url}")
print(f"Content-Length: {r2.headers.get('content-length','?')}")
print(f"Content-Type: {r2.headers.get('content-type','?')}")
print(f"Body preview: {r2.text[:500]!r}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 2: Fetch the HTML page with full redirect following + check all links")
print("="*70)

r = s.get(f"{BASE}/cognitive/functionalAreaAnalysis.html", timeout=15, verify=False)
print(f"HTML page: [{r.status_code}] final_url={r.url}")
print(f"HTML length: {len(r.text)}")

# Find ALL asset references (scripts, links with href containing .js)
all_scripts = re.findall(r'src=["\']([^"\']+)["\']', r.text)
all_links   = re.findall(r'href=["\']([^"\']+)["\']', r.text)
print(f"\nAll src= references: {all_scripts}")
print(f"All href= references: {all_links}")
print(f"\nFull HTML:\n{r.text[:2000]}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 3: Try the bundle URL with /cognitive/ prefix")
print("="*70)

# Maybe bundles live under /cognitive/ not at root
for prefix in ['/cognitive/', '/cognitive/static/', '/static/', '/assets/']:
    url = f"{BASE}{prefix}functionalAreaAnalysis.d06857684759d207a9f4.js"
    r = s.get(url, timeout=10, verify=False)
    ct = r.headers.get('content-type','')
    print(f"  [{r.status_code}] {url}  ct={ct}  len={len(r.text)}")
    if r.status_code == 200 and len(r.text) > 10000:
        print(f"  🎯 GOT REAL BUNDLE! Grepping...")
        js = r.text
        all_paths = set()
        for pat in [r'"(/[\w\-/\.?=&%+#]{4,150})"', r"'(/[\w\-/\.?=&%+#]{4,150})'"]:
            all_paths.update(re.findall(pat, js))
        keywords = ['external', 'data', 'api', 'defect', 'build', 'report', 'functional', 'area']
        for p in sorted(p for p in all_paths if any(k in p.lower() for k in keywords)):
            print(f"    {p}")
        break


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 4: The /cognitive/external-data/ backend is nginx 500.")
print("         Check nginx error via OPTIONS / HEAD to get more info")
print("="*70)

url = f"{BASE}/cognitive/external-data/buildBreakReport?functionalArea={COMPONENT}"
for method in ['HEAD', 'OPTIONS']:
    try:
        r = s.request(method, url, timeout=10, verify=False)
        print(f"{method} [{r.status_code}] headers={dict(r.headers)}")
    except Exception as e:
        print(f"{method} ERROR: {e}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 5: Check what /cognitive/external-data/ looks like from INSIDE")
print("         the docker network (direct to backend, bypassing nginx)")
print("="*70)

# The nginx reverse proxy may be forwarding to an internal service.
# Try common internal service hostnames/ports
import socket
try:
    # Try to resolve common backend hostnames
    for host in ['cognitive-data', 'cognitive-backend', 'backend', 'data-service', 
                 'libh-cognitive', 'cognitive', 'localhost']:
        for port in [8080, 8443, 3000, 3001, 4000, 9090]:
            try:
                sock = socket.create_connection((host, port), timeout=1)
                sock.close()
                print(f"  ✅ REACHABLE: {host}:{port}")
                # Try HTTP
                test_r = requests.get(
                    f"http://{host}:{port}/buildBreakReport?functionalArea={COMPONENT}",
                    timeout=3, verify=False
                )
                print(f"     HTTP response: [{test_r.status_code}] ct={test_r.headers.get('content-type','')}")
                if 'json' in test_r.headers.get('content-type','').lower():
                    print(f"     🎯 JSON DATA: {test_r.text[:300]}")
            except (socket.timeout, ConnectionRefusedError, socket.gaierror):
                pass
            except Exception as e:
                if 'REACHABLE' in str(e):
                    pass
except Exception as e:
    print(f"Socket scan error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("PHASE 6: Read full JS bundle via wget (handles redirect chain differently)")
print("="*70)

import subprocess
result = subprocess.run(
    ['wget', '-q', '-O', '/tmp/bundle.js', '--no-check-certificate',
     '--header', f'Cookie: mod_auth_openidc_session={next(c["value"] for c in raw_cookies if c["name"]=="mod_auth_openidc_session")}',
     f'{BASE}/functionalAreaAnalysis.d06857684759d207a9f4.js'],
    capture_output=True, text=True, timeout=30
)
print(f"wget stdout: {result.stdout}")
print(f"wget stderr: {result.stderr}")
try:
    with open('/tmp/bundle.js') as f:
        content = f.read()
    print(f"Downloaded: {len(content)} bytes")
    if len(content) > 1000:
        # Grep for paths
        all_paths = set()
        for pat in [r'"(/[\w\-/\.?=&%+#]{4,150})"', r"'(/[\w\-/\.?=&%+#]{4,150})'"]:
            all_paths.update(re.findall(pat, content))
        keywords = ['external', 'data', 'api', 'defect', 'build', 'report', 'functional', 'area']
        interesting = sorted(p for p in all_paths if any(k in p.lower() for k in keywords))
        print(f"Interesting paths from wget bundle: {interesting}")
        # Also show raw around 'external'
        idx = content.find('external')
        if idx >= 0:
            print(f"Context around 'external': {content[max(0,idx-100):idx+200]!r}")
    else:
        print(f"Content: {content!r}")
except Exception as e:
    print(f"Read error: {e}")

print("\n" + "="*70 + "\nDone.\n" + "="*70)
