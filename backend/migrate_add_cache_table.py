"""
Migration script to add cache_entries table for persistent caching.
Run this once to update the database schema.
"""
import sqlite3
import os

# Find the database file
db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
if not os.path.exists(db_path):
    db_path = 'rag_seo.db'

print(f"Looking for database at: {db_path}")

if not os.path.exists(db_path):
    print("❌ Database file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if table already exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cache_entries'")
if cursor.fetchone():
    print("⏭️ cache_entries table already exists")
else:
    print("Creating cache_entries table...")
    cursor.execute("""
        CREATE TABLE cache_entries (
            cache_key VARCHAR(255) PRIMARY KEY,
            cache_value TEXT NOT NULL,
            cached_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME
        )
    """)
    print("✅ Created cache_entries table")

conn.commit()
conn.close()

print("\n🎉 Migration complete! The cache will now persist across restarts.")
