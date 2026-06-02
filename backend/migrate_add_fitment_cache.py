"""
Migration: Add cached_vehicle_fitments column to products table.
This enables fast loading of vehicle fitments without calling Shopify API.
"""
import sqlite3
import os

def migrate():
    # Find database file
    db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'cached_vehicle_fitments' in columns:
            print("✅ Column 'cached_vehicle_fitments' already exists")
            return True
        
        # Add the new column
        print("Adding 'cached_vehicle_fitments' column to products table...")
        cursor.execute("""
            ALTER TABLE products 
            ADD COLUMN cached_vehicle_fitments JSON
        """)
        
        conn.commit()
        print("✅ Migration complete: added cached_vehicle_fitments column")
        return True
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
