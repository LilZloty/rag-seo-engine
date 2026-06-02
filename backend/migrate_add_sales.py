"""
Quick migration script to add total_sold and total_revenue columns to existing database.
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

# Check if columns already exist
cursor.execute("PRAGMA table_info(products)")
columns = [col[1] for col in cursor.fetchall()]

if 'total_sold' not in columns:
    print("Adding total_sold column...")
    cursor.execute("ALTER TABLE products ADD COLUMN total_sold INTEGER DEFAULT 0")
    print("✅ Added total_sold column")
else:
    print("⏭️ total_sold column already exists")

if 'total_revenue' not in columns:
    print("Adding total_revenue column...")
    cursor.execute("ALTER TABLE products ADD COLUMN total_revenue REAL DEFAULT 0.0")
    print("✅ Added total_revenue column")
else:
    print("⏭️ total_revenue column already exists")

conn.commit()
conn.close()

print("\n🎉 Migration complete! Restart your backend server.")
