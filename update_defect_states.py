#!/usr/bin/env python3
"""
Update defect states and tags in the database
"""
import sqlite3
import sys
import json
from datetime import datetime

def update_defect_tags(db_path, defect_id, tags):
    """Update a defect's tags in the database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current tags
        cursor.execute("SELECT tags FROM defect_descriptions WHERE defect_id = ?", (defect_id,))
        result = cursor.fetchone()
        
        if not result:
            print(f"❌ Defect {defect_id} not found in database")
            conn.close()
            return False
        
        old_tags = result[0]
        tags_json = json.dumps(tags)
        print(f"📝 Defect {defect_id}: tags {old_tags} → {tags_json}")
        
        # Update tags
        cursor.execute("""
            UPDATE defect_descriptions
            SET tags = ?, updated_at = ?
            WHERE defect_id = ?
        """, (tags_json, datetime.now().isoformat(), defect_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Updated defect {defect_id} tags to {tags_json}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating defect {defect_id} tags: {e}")
        return False

def update_defect_state(db_path, defect_id, new_state):
    """Update a defect's state in the database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current state
        cursor.execute("SELECT state FROM defect_descriptions WHERE defect_id = ?", (defect_id,))
        result = cursor.fetchone()
        
        if not result:
            print(f"❌ Defect {defect_id} not found in database")
            conn.close()
            return False
        
        old_state = result[0]
        print(f"📝 Defect {defect_id}: {old_state} → {new_state}")
        
        # Update state
        cursor.execute("""
            UPDATE defect_descriptions 
            SET state = ?, updated_at = ? 
            WHERE defect_id = ?
        """, (new_state, datetime.now().isoformat(), defect_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Updated defect {defect_id} state to {new_state}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating defect {defect_id}: {e}")
        return False

def main():
    db_path = "data/defects.db"
    
    print("🔄 Updating defect states and tags...")
    print()
    
    # Update defects from Canceled to Open
    update_defect_state(db_path, "308744", "Open")
    update_defect_state(db_path, "308600", "Open")
    
    print()
    
    # Add infrastructure tag to defect #309377
    update_defect_tags(db_path, "309377", ["infrastructure"])
    
    print()
    print("✅ Done! Restart the Docker container:")
    print("   docker compose restart")
    print()
    print("Or rebuild and restart:")
    print("   docker compose up -d --build")

if __name__ == "__main__":
    main()

# Made with Bob
