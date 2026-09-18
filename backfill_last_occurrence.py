"""
One-time backfill: extract last_occurrence_date from reported_builds in the
all_components_snapshots JSON and write it into defect_descriptions.
Run once on the VM: python3 backfill_last_occurrence.py
"""
import sqlite3
import json
import re
from datetime import datetime

DB_PATH = "data/defects.db"

def extract_last_occurrence(reported_builds: str) -> str:
    if not reported_builds:
        return ''
    candidates = []
    for m in re.findall(r'\b(\d{8})\b', reported_builds):
        try:
            candidates.append(datetime.strptime(m, '%Y%m%d'))
        except ValueError:
            pass
    for m in re.findall(r'(\d{4}-\d{2}-\d{2})', reported_builds):
        try:
            candidates.append(datetime.strptime(m, '%Y-%m-%d'))
        except ValueError:
            pass
    if candidates:
        return max(candidates).strftime('%Y-%m-%d')
    return ''

conn = sqlite3.connect(DB_PATH)

# Step 1: get the list of distinct components and their latest created_at
print("Fetching component list...", flush=True)
comp_rows = conn.execute("""
    SELECT component, MAX(created_at) as latest
    FROM all_components_snapshots
    GROUP BY component
""").fetchall()
print(f"Found {len(comp_rows)} components to scan", flush=True)

updates = {}  # defect_id -> last_occurrence_date

# Step 2: fetch each component's latest snapshot individually
for i, (component, latest_at) in enumerate(comp_rows, 1):
    print(f"  [{i}/{len(comp_rows)}] {component}...", flush=True)
    row = conn.execute(
        "SELECT data FROM all_components_snapshots WHERE component = ? AND created_at = ?",
        (component, latest_at)
    ).fetchone()
    if not row:
        continue
    try:
        data = json.loads(row[0])
    except Exception:
        continue
    defects = data.get('all_defects', data.get('defects', []))
    for d in defects:
        defect_id = str(d.get('id', ''))
        if not defect_id:
            continue
        reported_builds = d.get('reported_builds', '')
        if reported_builds:
            last_occ = extract_last_occurrence(reported_builds)
            if last_occ:
                if defect_id not in updates or last_occ > updates[defect_id]:
                    updates[defect_id] = last_occ

print(f"\nFound {len(updates)} defects with last_occurrence_date to backfill", flush=True)

# Step 3: write updates
updated = 0
write_cur = conn.cursor()
for defect_id, last_occ in updates.items():
    write_cur.execute(
        "UPDATE defect_descriptions SET last_occurrence_date = ? WHERE defect_id = ? AND (last_occurrence_date IS NULL OR last_occurrence_date = '')",
        (last_occ, defect_id)
    )
    if write_cur.rowcount > 0:
        updated += 1

conn.commit()
conn.close()
print(f"Backfilled {updated} rows in defect_descriptions")

# Verify
conn2 = sqlite3.connect(DB_PATH)
row = conn2.execute("SELECT defect_id, creation_date, last_occurrence_date FROM defect_descriptions WHERE defect_id='300248'").fetchone()
if row:
    print(f"Defect 300248: creation={row[1]}, last_occurrence={row[2]}")
else:
    print("Defect 300248 not found in defect_descriptions")

# Show summary
total = conn2.execute("SELECT COUNT(*) FROM defect_descriptions").fetchone()[0]
with_occ = conn2.execute("SELECT COUNT(*) FROM defect_descriptions WHERE last_occurrence_date != '' AND last_occurrence_date IS NOT NULL").fetchone()[0]
print(f"Total defect_descriptions: {total}, with last_occurrence_date: {with_occ}")
conn2.close()
