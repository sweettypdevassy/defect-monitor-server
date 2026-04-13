#!/usr/bin/env python3
"""
Script to backfill missing creation dates for defects in database
Fetches defects from IBM Build Break Report API and updates database
"""

import sqlite3
import requests
import urllib3
import re
from datetime import datetime
from pathlib import Path
import sys
import time

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def extract_creation_date_from_builds(reported_builds: str) -> str:
    """
    Extract creation date from the first build in reported_builds string.
    Example: "[Liberty z/OS Platform Build 20231208-1940, ...]" -> "2023-12-08"
    Example: "[No longer available was:2026-02-12 22:09 ...]" -> "2026-02-12"
    """
    if not reported_builds:
        return ''
    
    # First try to match YYYY-MM-DD format (with hyphens)
    match = re.search(r'(\d{4}-\d{2}-\d{2})', reported_builds)
    if match:
        date_str = match.group(1)
        try:
            # Validate it's a real date
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        except ValueError:
            pass
    
    # Fall back to YYYYMMDD format (8 consecutive digits)
    match = re.search(r'(\d{8})', reported_builds)
    if match:
        date_str = match.group(1)
        try:
            # Parse YYYYMMDD format
            dt = datetime.strptime(date_str, '%Y%m%d')
            # Return in ISO format
            return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        except ValueError:
            pass
    
    return ''

def get_defects_missing_creation_date(db_path: str):
    """Get list of defects missing creation_date"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT defect_id, component
        FROM defect_descriptions
        WHERE creation_date IS NULL OR creation_date = ''
        ORDER BY component, defect_id
    """)
    
    defects = cursor.fetchall()
    conn.close()
    
    return defects

def fetch_defect_from_api(defect_id: str, component: str, session: requests.Session) -> dict:
    """Fetch single defect from IBM Build Break Report API"""
    try:
        api_url = f"https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas?fas={component}"
        
        response = session.get(
            api_url,
            timeout=30,
            headers={
                'Accept': 'application/json',
                'Cache-Control': 'no-cache'
            },
            verify=False
        )
        
        if response.status_code != 200:
            print(f"  ❌ HTTP {response.status_code} for {component}")
            return None
        
        defects = response.json()
        
        # Find the specific defect
        for defect in defects:
            if str(defect.get('id')) == str(defect_id):
                return defect
        
        return None
        
    except Exception as e:
        print(f"  ❌ Error fetching defect {defect_id}: {e}")
        return None

def update_creation_date(db_path: str, defect_id: str, creation_date: str):
    """Update creation_date in database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE defect_descriptions
        SET creation_date = ?, updated_at = ?
        WHERE defect_id = ?
    """, (creation_date, datetime.now().isoformat(), defect_id))
    
    conn.commit()
    conn.close()

def backfill_creation_dates():
    """Main function to backfill missing creation dates"""
    
    db_path = "data/defects.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print("=" * 80)
    print("🔄 BACKFILLING MISSING CREATION DATES")
    print("=" * 80)
    
    # Get defects missing creation_date
    defects = get_defects_missing_creation_date(db_path)
    
    if not defects:
        print("\n✅ No defects missing creation_date!")
        return
    
    print(f"\n📋 Found {len(defects)} defects missing creation_date")
    print(f"   Components affected: {len(set(d[1] for d in defects))}")
    
    # Group by component
    by_component = {}
    for defect_id, component in defects:
        if component not in by_component:
            by_component[component] = []
        by_component[component].append(defect_id)
    
    print("\n📊 Breakdown by component:")
    for component, defect_ids in sorted(by_component.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  • {component}: {len(defect_ids)} defects")
    
    # Ask for confirmation
    print("\n" + "=" * 80)
    response = input("Do you want to proceed with backfilling? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Aborted")
        return
    
    # Create session with cookies from environment or config
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    })
    
    # Try to load cookies from session_cookies.json
    try:
        import json
        cookie_file = Path("data/session_cookies.json")
        if cookie_file.exists():
            with open(cookie_file, 'r') as f:
                cookies_data = json.load(f)
                cookies = cookies_data.get('cookies', [])
                for cookie in cookies:
                    session.cookies.set(cookie['name'], cookie['value'])
            print(f"\n✅ Loaded {len(cookies)} cookies from session_cookies.json")
        else:
            print("\n⚠️  No session cookies found - API calls may fail")
            print("   Make sure the server is authenticated")
    except Exception as e:
        print(f"\n⚠️  Could not load cookies: {e}")
    
    print("\n" + "=" * 80)
    print("🔄 Starting backfill process...")
    print("=" * 80)
    
    updated = 0
    failed = 0
    skipped = 0
    
    # Process by component to minimize API calls
    for component, defect_ids in by_component.items():
        print(f"\n📦 Processing {component} ({len(defect_ids)} defects)...")
        
        # Fetch all defects for this component once
        try:
            api_url = f"https://libh-proxy1.fyre.ibm.com/buildBreakReport/rest2/defects/buildbreak/fas?fas={component}"
            response = session.get(api_url, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"  ❌ Failed to fetch {component}: HTTP {response.status_code}")
                failed += len(defect_ids)
                continue
            
            all_defects = response.json()
            
            # Create lookup dict
            defect_lookup = {str(d.get('id')): d for d in all_defects}
            
            # Update each defect
            for defect_id in defect_ids:
                defect_data = defect_lookup.get(str(defect_id))
                
                if not defect_data:
                    print(f"  ⚠️  Defect {defect_id} not found in API response")
                    skipped += 1
                    continue
                
                reported_builds = defect_data.get('reported_builds', '')
                if reported_builds:
                    creation_date = extract_creation_date_from_builds(reported_builds)
                    if creation_date:
                        update_creation_date(db_path, defect_id, creation_date)
                        print(f"  ✅ Updated {defect_id}: {creation_date}")
                        updated += 1
                    else:
                        print(f"  ⚠️  Could not extract date from: {reported_builds[:50]}...")
                        skipped += 1
                else:
                    print(f"  ⚠️  No reported_builds for {defect_id}")
                    skipped += 1
            
            # Rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ❌ Error processing {component}: {e}")
            failed += len(defect_ids)
    
    print("\n" + "=" * 80)
    print("📊 BACKFILL SUMMARY")
    print("=" * 80)
    print(f"✅ Updated: {updated}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"📦 Total: {updated + skipped + failed}")
    
    if updated > 0:
        print(f"\n✅ Successfully backfilled {updated} creation dates!")
    
    print("=" * 80)

if __name__ == "__main__":
    backfill_creation_dates()

# Made with Bob
