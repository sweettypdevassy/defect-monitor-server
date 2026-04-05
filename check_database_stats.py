#!/usr/bin/env python3
"""
Database Statistics Checker
Check defect counts, descriptions, tags, and training data
"""

import sqlite3
import json
from datetime import datetime

def check_database_stats():
    """Check and display comprehensive database statistics"""
    
    db_path = 'data/defects.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("DATABASE STATISTICS")
        print("=" * 70)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. Total defects
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions')
        total = cursor.fetchone()[0]
        print(f"📊 Total defects in database: {total}")
        print()
        
        # 2. Descriptions
        print("📝 DESCRIPTION STATISTICS:")
        print("-" * 70)
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE description IS NOT NULL')
        not_null = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE LENGTH(description) > 0')
        has_content = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE LENGTH(description) > 100')
        substantial = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE LENGTH(description) > 1000')
        detailed = cursor.fetchone()[0]
        
        print(f"  Descriptions NOT NULL: {not_null} ({not_null*100//total if total > 0 else 0}%)")
        print(f"  Descriptions with content (length > 0): {has_content} ({has_content*100//total if total > 0 else 0}%)")
        print(f"  Substantial descriptions (> 100 chars): {substantial} ({substantial*100//total if total > 0 else 0}%)")
        print(f"  Detailed descriptions (> 1000 chars): {detailed} ({detailed*100//total if total > 0 else 0}%)")
        print()
        
        # 3. Tags and Training Data
        print("🏷️  TAG STATISTICS (for ML training):")
        print("-" * 70)
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE tags IS NOT NULL AND tags != ""')
        with_tags = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE tags = "[]"')
        empty_tags = cursor.fetchone()[0]
        
        print(f"  Defects with tags: {with_tags} ({with_tags*100//total if total > 0 else 0}%)")
        print(f"  Defects with empty tags []: {empty_tags} ({empty_tags*100//total if total > 0 else 0}%)")
        print()
        
        # 4. Training data by tag type
        print("🎓 TRAINING DATA BY TAG TYPE:")
        print("-" * 70)
        
        # Count defects with each primary tag
        cursor.execute('SELECT tags FROM defect_descriptions WHERE tags IS NOT NULL AND tags != ""')
        all_tags = cursor.fetchall()
        
        test_bug_count = 0
        product_bug_count = 0
        infrastructure_count = 0
        triaging_count = 0
        other_count = 0
        
        for (tags_str,) in all_tags:
            try:
                tags_list = json.loads(tags_str) if tags_str else []
                if 'test_bug' in tags_list:
                    test_bug_count += 1
                elif 'product_bug' in tags_list:
                    product_bug_count += 1
                elif 'infrastructure' in tags_list:
                    infrastructure_count += 1
                elif 'triaging' in tags_list:
                    triaging_count += 1
                elif len(tags_list) == 0:
                    pass  # Already counted as empty_tags
                else:
                    other_count += 1
            except:
                pass
        
        triaged_total = test_bug_count + product_bug_count + infrastructure_count
        
        print(f"  test_bug: {test_bug_count} defects")
        print(f"  product_bug: {product_bug_count} defects")
        print(f"  infrastructure: {infrastructure_count} defects")
        print(f"  ─────────────────────────────")
        print(f"  TOTAL TRIAGED (for ML): {triaged_total} defects")
        print()
        print(f"  triaging (not yet triaged): {triaging_count} defects")
        print(f"  other tags: {other_count} defects")
        print()
        
        # 5. Sample defects with descriptions
        print("📄 SAMPLE DEFECTS WITH DESCRIPTIONS:")
        print("-" * 70)
        
        cursor.execute('''
            SELECT defect_id, component, LENGTH(description) as desc_len, tags 
            FROM defect_descriptions 
            WHERE LENGTH(description) > 100 
            ORDER BY desc_len DESC 
            LIMIT 5
        ''')
        samples = cursor.fetchall()
        
        if samples:
            for defect_id, component, desc_len, tags in samples:
                try:
                    tags_list = json.loads(tags) if tags else []
                    primary_tag = tags_list[0] if tags_list else "no_tag"
                except:
                    primary_tag = "unknown"
                print(f"  ID {defect_id} | {component} | {desc_len} chars | Tag: {primary_tag}")
        else:
            print("  No defects with descriptions found yet")
        print()
        
        # 6. Recent activity
        print("📅 RECENT ACTIVITY:")
        print("-" * 70)
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE updated_at >= datetime("now", "-1 day")')
        updated_today = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM defect_descriptions WHERE updated_at >= datetime("now", "-7 days")')
        updated_week = cursor.fetchone()[0]
        
        print(f"  Updated in last 24 hours: {updated_today}")
        print(f"  Updated in last 7 days: {updated_week}")
        print()
        
        # 7. Summary
        print("=" * 70)
        print("SUMMARY:")
        print("=" * 70)
        print(f"✅ Total defects: {total}")
        print(f"✅ Defects with descriptions: {has_content} ({has_content*100//total if total > 0 else 0}%)")
        print(f"✅ Triaged defects for ML training: {triaged_total}")
        print(f"⏳ Untriaged defects: {empty_tags + triaging_count}")
        print("=" * 70)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_database_stats()

# Made with Bob
