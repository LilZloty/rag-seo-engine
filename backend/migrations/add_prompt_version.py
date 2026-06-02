"""
Migration script to add version column to prompt_templates table.
Run this script once to update existing databases.
"""
import sqlite3
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base_dir, 'rag_seo.db')

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(prompt_templates)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'version' not in columns:
        print("📝 Adding 'version' column to prompt_templates...")
        cursor.execute("ALTER TABLE prompt_templates ADD COLUMN version INTEGER DEFAULT 1")
        conn.commit()
        print("✅ Migration complete!")
    else:
        print("ℹ️ Column 'version' already exists, skipping migration.")
    
    conn.close()

if __name__ == "__main__":
    migrate()
