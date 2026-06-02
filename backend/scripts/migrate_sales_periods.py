"""
Migration script to add time-period sales columns to products table.
Run this to update existing database without losing data.
"""
import sqlite3
import os

# Path to your SQLite database - change this if needed
DB_PATH = 'rag_seo.db'

def migrate():
    print("Starting database migration...")
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found: {DB_PATH}")
        print("Please run this script from the backend directory")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(products)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    print(f"Existing columns: {len(existing_columns)}")
    
    # New columns to add
    new_columns = [
        ('sold_30d', 'INTEGER DEFAULT 0'),
        ('revenue_30d', 'REAL DEFAULT 0.0'),
        ('sold_90d', 'INTEGER DEFAULT 0'),
        ('revenue_90d', 'REAL DEFAULT 0.0'),
        ('sold_365d', 'INTEGER DEFAULT 0'),
        ('revenue_365d', 'REAL DEFAULT 0.0'),
        ('sold_all_time', 'INTEGER DEFAULT 0'),
        ('revenue_all_time', 'REAL DEFAULT 0.0'),
    ]
    
    added = 0
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name}")
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            added += 1
        else:
            print(f"Column already exists: {col_name}")
    
    conn.commit()
    conn.close()
    
    print("")
    print("Migration complete!")
    print(f"Added {added} new columns")
    print("")
    print("Next steps:")
    print("   1. Restart your backend server")
    print("   2. Run 'Sync Sales' to populate the new columns")
    print("   3. Refresh your dashboard")

if __name__ == "__main__":
    migrate()
