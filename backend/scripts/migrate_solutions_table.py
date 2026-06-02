"""
Database Migration: Add missing columns to solutions table

Run this with: python -m scripts.migrate_solutions_table
"""

import sqlite3
import os

# Determine the database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'rag_seo.db')

def migrate():
    """Add missing columns to solutions table."""
    print(f"Connecting to database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(solutions)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    print(f"Existing columns: {existing_columns}")
    
    # Columns to add with their types
    columns_to_add = {
        'title': 'VARCHAR(200)',
        'recommended_skus': 'TEXT',  # JSON stored as TEXT in SQLite
        'collection_url': 'VARCHAR(300)',
    }
    
    for column_name, column_type in columns_to_add.items():
        if column_name not in existing_columns:
            try:
                sql = f"ALTER TABLE solutions ADD COLUMN {column_name} {column_type}"
                print(f"Adding column: {sql}")
                cursor.execute(sql)
                print(f"✅ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Column {column_name} error: {e}")
        else:
            print(f"✓ Column {column_name} already exists")
    
    conn.commit()
    conn.close()
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    migrate()
