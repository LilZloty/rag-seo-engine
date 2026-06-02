"""
Migration script to add inventory fields to products table (SQLite compatible)
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

def migrate():
    """Add inventory columns to products table"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Get existing columns using SQLite PRAGMA
        result = conn.execute(text("PRAGMA table_info(products)"))
        existing_columns = [row[1] for row in result]  # row[1] is column name
        
        print(f"Existing columns: {existing_columns}")
        
        # Add inventory_quantity column if not exists
        if 'inventory_quantity' not in existing_columns:
            print("Adding inventory_quantity column...")
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN inventory_quantity INTEGER DEFAULT NULL
            """))
            conn.commit()
            print("✓ inventory_quantity column added")
        else:
            print("- inventory_quantity column already exists")
        
        # Add inventory_status column if not exists
        if 'inventory_status' not in existing_columns:
            print("Adding inventory_status column...")
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN inventory_status VARCHAR(20) DEFAULT NULL
            """))
            conn.commit()
            print("✓ inventory_status column added")
        else:
            print("- inventory_status column already exists")
        
        # Add last_inventory_sync column if not exists
        if 'last_inventory_sync' not in existing_columns:
            print("Adding last_inventory_sync column...")
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN last_inventory_sync TIMESTAMP DEFAULT NULL
            """))
            conn.commit()
            print("✓ last_inventory_sync column added")
        else:
            print("- last_inventory_sync column already exists")
        
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Run the backend server")
        print("2. Click the '📦 Sync Inventory' button in the dashboard")
        print("   OR call POST /api/v1/products/sync-inventory")

if __name__ == "__main__":
    migrate()
