#!/usr/bin/env python3
"""
Script to check defect data in database
Shows statistics about defects with creation_date, description, and other fields
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

def check_defect_data():
    """Check defect data statistics in database"""
    
    db_path = "data/defects.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print("=" * 80)
    print("📊 DEFECT DATA STATISTICS")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if defect_descriptions table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='defect_descriptions'
    """)
    
    if not cursor.fetchone():
        print("❌ defect_descriptions table not found")
        conn.close()
        return
    
    # Total defects in cache
    cursor.execute("SELECT COUNT(*) FROM defect_descriptions")
    total_defects = cursor.fetchone()[0]
    print(f"\n📦 Total defects in cache: {total_defects}")
    
    # Defects with creation_date
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE creation_date IS NOT NULL AND creation_date != ''
    """)
    with_creation_date = cursor.fetchone()[0]
    print(f"📅 Defects with creation_date: {with_creation_date} ({with_creation_date/total_defects*100:.1f}%)")
    
    # Defects with description
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE description IS NOT NULL AND LENGTH(description) > 10
    """)
    with_description = cursor.fetchone()[0]
    print(f"📝 Defects with description: {with_description} ({with_description/total_defects*100:.1f}%)")
    
    # Defects with summary
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE summary IS NOT NULL AND summary != ''
    """)
    with_summary = cursor.fetchone()[0]
    print(f"📋 Defects with summary: {with_summary} ({with_summary/total_defects*100:.1f}%)")
    
    # Defects with component
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE component IS NOT NULL AND component != ''
    """)
    with_component = cursor.fetchone()[0]
    print(f"🏷️  Defects with component: {with_component} ({with_component/total_defects*100:.1f}%)")
    
    # Defects with functional_area
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE functional_area IS NOT NULL AND functional_area != ''
    """)
    with_functional_area = cursor.fetchone()[0]
    print(f"🎯 Defects with functional_area: {with_functional_area} ({with_functional_area/total_defects*100:.1f}%)")
    
    # Defects with tags
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE tags IS NOT NULL AND tags != '[]' AND tags != ''
    """)
    with_tags = cursor.fetchone()[0]
    print(f"🏷️  Defects with tags: {with_tags} ({with_tags/total_defects*100:.1f}%)")
    
    # Defects with number_builds
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE number_builds > 0
    """)
    with_builds = cursor.fetchone()[0]
    print(f"🔢 Defects with build count: {with_builds} ({with_builds/total_defects*100:.1f}%)")
    
    # Complete defects (all fields populated)
    cursor.execute("""
        SELECT COUNT(*) FROM defect_descriptions 
        WHERE creation_date IS NOT NULL AND creation_date != ''
        AND description IS NOT NULL AND LENGTH(description) > 10
        AND summary IS NOT NULL AND summary != ''
        AND component IS NOT NULL AND component != ''
    """)
    complete_defects = cursor.fetchone()[0]
    print(f"✅ Complete defects (all key fields): {complete_defects} ({complete_defects/total_defects*100:.1f}%)")
    
    print("\n" + "=" * 80)
    print("📊 BREAKDOWN BY COMPONENT")
    print("=" * 80)
    
    # Top components by defect count
    cursor.execute("""
        SELECT component, COUNT(*) as count
        FROM defect_descriptions
        WHERE component IS NOT NULL AND component != ''
        GROUP BY component
        ORDER BY count DESC
        LIMIT 10
    """)
    
    print("\nTop 10 components by defect count:")
    for component, count in cursor.fetchall():
        print(f"  • {component}: {count} defects")
    
    print("\n" + "=" * 80)
    print("📊 SAMPLE DEFECTS")
    print("=" * 80)
    
    # Sample defects with all fields
    cursor.execute("""
        SELECT defect_id, summary, component, creation_date, number_builds
        FROM defect_descriptions
        WHERE creation_date IS NOT NULL AND creation_date != ''
        AND description IS NOT NULL AND LENGTH(description) > 10
        ORDER BY RANDOM()
        LIMIT 5
    """)
    
    print("\nSample complete defects:")
    for defect_id, summary, component, creation_date, number_builds in cursor.fetchall():
        summary_short = summary[:60] + "..." if len(summary) > 60 else summary
        print(f"\n  ID: {defect_id}")
        print(f"  Summary: {summary_short}")
        print(f"  Component: {component}")
        print(f"  Created: {creation_date}")
        print(f"  Builds: {number_builds}")
    
    # Sample defects missing data
    print("\n" + "=" * 80)
    print("⚠️  SAMPLE DEFECTS MISSING DATA")
    print("=" * 80)
    
    cursor.execute("""
        SELECT defect_id, summary, component, creation_date, 
               CASE WHEN description IS NULL OR LENGTH(description) <= 10 THEN 'NO' ELSE 'YES' END as has_desc
        FROM defect_descriptions
        WHERE creation_date IS NULL OR creation_date = ''
        OR description IS NULL OR LENGTH(description) <= 10
        ORDER BY RANDOM()
        LIMIT 5
    """)
    
    print("\nSample defects with missing data:")
    for defect_id, summary, component, creation_date, has_desc in cursor.fetchall():
        summary_short = summary[:60] + "..." if summary and len(summary) > 60 else (summary or "N/A")
        print(f"\n  ID: {defect_id}")
        print(f"  Summary: {summary_short}")
        print(f"  Component: {component or 'N/A'}")
        print(f"  Created: {creation_date or 'MISSING'}")
        print(f"  Has Description: {has_desc}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)

if __name__ == "__main__":
    check_defect_data()

# Made with Bob
