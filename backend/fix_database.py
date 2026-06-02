"""
Fix database issues:
1. Set document_count to 0 where NULL
2. Delete corrupted documents from failed seed
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
if not os.path.exists(db_path):
    db_path = 'rag_seo.db'

print(f"Fixing database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fix 1: Update NULL document_count to 0
cursor.execute("UPDATE libraries SET document_count = 0 WHERE document_count IS NULL")
print(f"✓ Fixed {cursor.rowcount} libraries with NULL document_count")

# Fix 2: Delete all documents (they have corrupted JSON fields from seed script)
cursor.execute("DELETE FROM documents")
print(f"✓ Deleted {cursor.rowcount} corrupted documents")

# Fix 3: Delete all document_chunks
cursor.execute("DELETE FROM document_chunks")
print(f"✓ Deleted {cursor.rowcount} document chunks")

conn.commit()
conn.close()

print("\n✅ Database fixed! Restart your backend server.")
