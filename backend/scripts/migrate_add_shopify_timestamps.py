"""
Migration script to add Shopify timestamp fields to products table (SQLite compatible)
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    """Add Shopify timestamp columns to products table"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Get existing columns using SQLite PRAGMA
        result = conn.execute(text("PRAGMA table_info(products)"))
        existing_columns = [row[1] for row in result]  # row[1] is column name
        
        print(f"Existing columns: {existing_columns}")
        
        # Add shopify_created_at column if not exists
        if 'shopify_created_at' not in existing_columns:
            print("Adding shopify_created_at column...")
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN shopify_created_at TIMESTAMP DEFAULT NULL
            """))
            conn.commit()
            print("✓ shopify_created_at column added")
        else:
            print("- shopify_created_at column already exists")
        
        # Add shopify_updated_at column if not exists
        if 'shopify_updated_at' not in existing_columns:
            print("Adding shopify_updated_at column...")
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN shopify_updated_at TIMESTAMP DEFAULT NULL
            """))
            conn.commit()
            print("✓ shopify_updated_at column added")
        else:
            print("- shopify_updated_at column already exists")
        
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Run the backend server")
        print("2. Click '🛒 Sync Shopify' button to sync products with Shopify timestamps")
        print("   OR call POST /api/v1/products/sync-shopify")

if __name__ == "__main__":
    migrate()
