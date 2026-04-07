#!/usr/bin/env python3
"""
Clear Database and ML Model - Start Fresh
Removes all cached data and trained model for testing from scratch
"""

import os
import sqlite3
import shutil
from pathlib import Path

def clear_database():
    """Clear all data from the database"""
    db_path = "data/defects.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📊 Found {len(tables)} tables in database")
        
        # Clear each table
        for table in tables:
            table_name = table[0]
            if table_name != 'sqlite_sequence':  # Skip internal table
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"   🗑️  Clearing {table_name}: {count} rows")
                cursor.execute(f"DELETE FROM {table_name}")
        
        conn.commit()
        conn.close()
        
        print("✅ Database cleared successfully!")
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")

def clear_ml_model():
    """Remove trained ML model"""
    model_path = "data/tag_model.pkl"
    
    if os.path.exists(model_path):
        try:
            os.remove(model_path)
            print(f"✅ Removed ML model: {model_path}")
        except Exception as e:
            print(f"❌ Error removing model: {e}")
    else:
        print(f"ℹ️  ML model not found: {model_path}")

def clear_model_backups():
    """Remove model backup files"""
    backup_dir = "data/model_backups"
    
    if os.path.exists(backup_dir):
        try:
            backups = list(Path(backup_dir).glob("*.pkl"))
            if backups:
                print(f"🗑️  Found {len(backups)} model backups")
                for backup in backups:
                    os.remove(backup)
                    print(f"   ✓ Removed {backup.name}")
                print("✅ Model backups cleared!")
            else:
                print("ℹ️  No model backups found")
        except Exception as e:
            print(f"❌ Error clearing backups: {e}")
    else:
        print("ℹ️  Backup directory not found")

def main():
    print("=" * 60)
    print("🧹 CLEARING DATABASE AND ML MODEL")
    print("=" * 60)
    print()
    
    # Confirm action
    response = input("⚠️  This will delete ALL cached data and trained model. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Cancelled")
        return
    
    print()
    print("🗑️  Clearing database...")
    clear_database()
    
    print()
    print("🗑️  Clearing ML model...")
    clear_ml_model()
    
    print()
    print("🗑️  Clearing model backups...")
    clear_model_backups()
    
    print()
    print("=" * 60)
    print("✅ CLEANUP COMPLETE - Ready for fresh training!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Restart the server: docker-compose restart")
    print("2. Trigger training or wait for scheduled time")
    print("3. System will fetch and train from scratch")

if __name__ == "__main__":
    main()

# Made with Bob
