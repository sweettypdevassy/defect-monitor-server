#!/usr/bin/env python3
"""
Test fetch and show the real gunicorn logs around the fetch.
Run: docker compose exec defect-monitor python3 src/test_fetch_one.py
"""
import sys, time, os
import requests, urllib3
urllib3.disable_warnings()

BASE = 'http://localhost:5000'
COMPONENT = 'Batch'

# ── Read current log tail BEFORE triggering ──────────────────────────────────
def read_log_tail(n=5):
    for log_path in ['/app/logs/app.log', '/app/logs/scheduler.log',
                     '/var/log/defect-monitor.log', '/tmp/app.log']:
        if os.path.exists(log_path):
            with open(log_path) as f:
                lines = f.readlines()
            return log_path, lines[-n:]
    return None, []

log_path, _ = read_log_tail(1)
print(f"Log file: {log_path}")

# Get log file size before trigger so we can show only NEW lines after
log_before = 0
if log_path:
    log_before = os.path.getsize(log_path)

# ── Trigger refresh ───────────────────────────────────────────────────────────
print(f"\n{'='*60}\nTriggering refresh for: {COMPONENT}\n{'='*60}")
try:
    r = requests.post(f'{BASE}/api/refresh-component/{COMPONENT}', timeout=10)
    data = r.json()
    refresh_id = data.get('refresh_id', '')
    print(f"Triggered: {refresh_id}")
except Exception as e:
    print(f"ERROR triggering: {e}")
    refresh_id = ''

# ── Wait for completion ───────────────────────────────────────────────────────
if refresh_id:
    for i in range(60):
        time.sleep(1)
        try:
            s = requests.get(f'{BASE}/api/refresh-status/{refresh_id}', timeout=5).json()
            if s.get('status') in ('completed', 'failed', 'error'):
                print(f"Done in {i+1}s: {s}")
                break
            if i % 5 == 0:
                print(f"  [{i}s] {s.get('status')} progress={s.get('progress')}")
        except Exception:
            pass

# ── Show new log lines ────────────────────────────────────────────────────────
print(f"\n{'='*60}\nNew log lines after refresh:\n{'='*60}")
if log_path:
    with open(log_path) as f:
        all_lines = f.readlines()
    # Show lines that appeared after we started (approximate by count)
    new_lines = all_lines[max(0, len(all_lines)-100):]
    for line in new_lines:
        line = line.rstrip()
        if any(k in line for k in [
            'Browser', 'browser', 'SW ', 'service', 'fetch', 'Fetch',
            'FOUND', 'cognitive', 'external', 'Batch', 'defect', 'Defect',
            'Navigating', 'evaluate', 'cookie', 'Cookie', 'session',
            'WARNING', 'ERROR', 'Could not', 'failed', 'API'
        ]):
            print(line)
else:
    print("No log file found — checking gunicorn stderr via /proc...")
    # Try reading from gunicorn process stdout/stderr
    try:
        import glob
        for f in glob.glob('/proc/*/fd/1') + glob.glob('/proc/*/fd/2'):
            try:
                with open(f) as fh:
                    content = fh.read(2000)
                if 'defect' in content.lower() or 'browser' in content.lower():
                    print(f"Found in {f}:\n{content[-500:]}")
                    break
            except Exception:
                pass
    except Exception as e:
        print(f"proc scan error: {e}")

# ── Check if gunicorn logs to journald ───────────────────────────────────────
print(f"\n{'='*60}\nChecking for log output in stdout capture...\n{'='*60}")
import subprocess
for cmd in [
    ['find', '/app/logs', '-name', '*.log', '-newer', '/tmp'],
    ['find', '/var/log', '-name', '*.log', '-newer', '/tmp'],
    ['ls', '-la', '/app/logs/'],
]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            print(f"$ {' '.join(cmd)}:\n{r.stdout[:500]}")
    except Exception:
        pass

# ── Final result check ────────────────────────────────────────────────────────
print(f"\n{'='*60}\nFinal result from database:\n{'='*60}")
try:
    r = requests.get(f'{BASE}/api/insights/{COMPONENT}', timeout=10)
    data = r.json()
    defects = data.get('defects', data.get('allDefects', data.get('build_break_defects', [])))
    print(f"Total defects in DB for {COMPONENT}: {len(defects)}")
    if defects:
        d = defects[0]
        print(f"Sample: id={d.get('id')} summary={str(d.get('summary',''))[:60]!r} source={d.get('source','?')}")
    
    # Also check raw DB
    import sqlite3
    db_path = '/app/data/defects.db'
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM defect_descriptions WHERE component=?", (COMPONENT,))
        count = cur.fetchone()[0]
        print(f"SQLite defect_descriptions rows for {COMPONENT}: {count}")
        cur.execute("SELECT id, summary, tags FROM defect_descriptions WHERE component=? LIMIT 3", (COMPONENT,))
        for row in cur.fetchall():
            print(f"  Row: id={row[0]} summary={str(row[1])[:50]!r} tags={row[2]}")
        conn.close()
except Exception as e:
    print(f"Error: {e}")

print(f"\n{'='*60}\nDone.\n{'='*60}")
