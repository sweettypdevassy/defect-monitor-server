#!/usr/bin/env python3
"""
One-time backfill: set closed_date / closed_state / real state for cached closed defects.

Reads rtc_cm:resolved + rtc_cm:state from RTC for every cached row that looks closed
(state contains canceled/closed/resolved or defect_workflow.state.s2) and has no closed_date.

Usage (on the VM, from the project root):
    python3 backfill_closed_dates.py            # dry run, prints what would change
    python3 backfill_closed_dates.py --apply    # write to data/defects.db

Needs only: requests, urllib3, pyyaml (no numpy / ML deps).
"""

import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, 'src')

import yaml
from ibm_auth import IBMAuthenticator
from rtc_states import closed_state_label

DB_PATH = 'data/defects.db'
APPLY = '--apply' in sys.argv

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

auth = IBMAuthenticator(
    username=config['ibm']['username'],
    password=config['ibm']['password'],
    auth_method='password'
)

# Make sure the new columns exist (same as DefectDatabase init)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
for column in ('closed_date', 'closed_state'):
    try:
        cur.execute(f"ALTER TABLE defect_descriptions ADD COLUMN {column} TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

cur.execute("""
    SELECT defect_id FROM defect_descriptions
    WHERE (closed_date IS NULL OR closed_date = '')
      AND (lower(state) LIKE '%cancel%' OR lower(state) LIKE '%closed%'
           OR lower(state) LIKE '%resolved%' OR lower(state) LIKE '%defect_workflow.state.s2%')
""")
ids = [r[0] for r in cur.fetchall()]
print(f"{len(ids)} cached closed defects without a closed_date")


def fetch(defect_id):
    try:
        session = auth.get_session()
        if not session:
            return defect_id, None
        url = f"https://wasrtc.hursley.ibm.com:9443/jazz/oslc/workitems/{defect_id}.json"
        resp = session.get(url, timeout=60, headers={'Accept': 'application/json'}, verify=False)
        if resp.status_code != 200:
            return defect_id, None
        data = resp.json()
        state_obj = data.get('rtc_cm:state', {})
        state = state_obj.get('rdf:resource', '') if isinstance(state_obj, dict) else ''
        return defect_id, {
            'state': state,
            'resolved': data.get('rtc_cm:resolved', '') or '',
            'modified': data.get('dc:modified', '') or '',
        }
    except Exception as e:
        print(f"  ! {defect_id}: {e}")
        return defect_id, None


updates, reopened, failed = [], [], []
with ThreadPoolExecutor(max_workers=8) as pool:
    for i, (defect_id, info) in enumerate(pool.map(fetch, ids), 1):
        if i % 50 == 0 or i == len(ids):
            print(f"  fetched {i}/{len(ids)}")
        if not info:
            failed.append(defect_id)
            continue
        label = closed_state_label(info['state'])
        if not label:
            reopened.append(defect_id)  # no longer closed in RTC (reopened)
            continue
        closed_date = info['resolved'] or info['modified']
        if closed_date:
            updates.append((closed_date, label, info['state'], defect_id))
        else:
            failed.append(defect_id)

print(f"\nTo update: {len(updates)} | reopened in RTC (left untouched): {len(reopened)} | failed: {len(failed)}")
by_label = {}
for _, label, _, _ in updates:
    by_label[label] = by_label.get(label, 0) + 1
print("By closed state:", by_label)

if reopened:
    print("Reopened IDs (first 20):", reopened[:20])

if APPLY:
    cur.executemany(
        "UPDATE defect_descriptions SET closed_date = ?, closed_state = ?, state = ? WHERE defect_id = ?",
        updates
    )
    conn.commit()
    print(f"Applied {len(updates)} updates to {DB_PATH}")
else:
    print("Dry run only. Re-run with --apply to write changes.")

conn.close()
