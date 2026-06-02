"""
Migration script to add product_type column to existing database.
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

if 'product_type' not in columns:
    print("Adding product_type column...")
    cursor.execute("ALTER TABLE products ADD COLUMN product_type TEXT")
    print("✅ Added product_type column")
else:
    print("⏭️ product_type column already exists")

conn.commit()
conn.close()

print("\n🎉 Migration complete! Restart your backend server.")
