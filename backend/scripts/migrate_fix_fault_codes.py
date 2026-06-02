"""
Migration script to update 'fault_codes' table with new performance tracking columns.
Adds 'avg_position' to the existing table.
"""

import os
import sys
import sqlite3

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings

def migrate():
    print(f"🔄 Updating 'fault_codes' table in {settings.DATABASE_URL}...")
    
    # Extract path from sqlite:///./rag_seo.db
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(os.getcwd(), db_path[2:])
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if avg_position exists
        cursor.execute("PRAGMA table_info(fault_codes)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'avg_position' not in columns:
            print("➕ Adding 'avg_position' column to 'fault_codes'...")
            cursor.execute("ALTER TABLE fault_codes ADD COLUMN avg_position FLOAT DEFAULT 0.0")
            print("✅ Column 'avg_position' added successfully.")
        else:
            print("ℹ️ Column 'avg_position' already exists.")
            
        conn.commit()
        conn.close()
        print("🎉 Migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate()
