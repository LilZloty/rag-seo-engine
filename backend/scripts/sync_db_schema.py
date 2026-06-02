"""
Final Migration script to synchronize SQLite schema with SQLAlchemy models.
Handles 'products', 'fault_codes', and 'solutions' tables.
"""

import os
import sys
import sqlite3

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings

def sync_table(cursor, table_name, expected_columns):
    print(f"🧐 Auditing table: {table_name}...")
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {info[1]: info[2] for info in cursor.fetchall()}
        
        if not existing_columns:
            print(f"⚠️ Table '{table_name}' does not exist yet. It will be created by the app on next restart if models are imported.")
            return

        for col_name, col_type in expected_columns.items():
            if col_name not in existing_columns:
                print(f"➕ Adding missing column '{col_name}' ({col_type}) to '{table_name}'...")
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Column '{col_name}' added.")
                except Exception as e:
                    print(f"⚠️ Failed to add '{col_name}': {e}")
            else:
                pass
    except Exception as e:
        print(f"❌ Error auditing {table_name}: {e}")

def migrate():
    print(f"🔄 Starting definitive schema sync for {settings.DATABASE_URL}...")
    
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(os.getcwd(), db_path[2:])
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Expected columns for fault_codes
        fault_codes_cols = {
            'avg_position': 'FLOAT DEFAULT 0.0',
            'monthly_clicks': 'INTEGER DEFAULT 0',
            'monthly_impressions': 'INTEGER DEFAULT 0',
            'current_ctr': 'FLOAT DEFAULT 0.0',
            'query_type': 'VARCHAR(50) DEFAULT "direct_fault"',
            'is_priority': 'BOOLEAN DEFAULT 0',
            'include_in_llms_txt': 'BOOLEAN DEFAULT 1',
            'has_faq_schema': 'BOOLEAN DEFAULT 0',
            'transmissions': 'JSON',
            'vehicles': 'JSON',
            'common_causes': 'JSON',
            'symptoms_text': 'JSON',
            'blog_url': 'VARCHAR(300)',
            'collection_url': 'VARCHAR(300)'
        }
        
        # Expected columns for products
        products_cols = {
            'transmission_code': 'VARCHAR(30)',
            'vendor': 'VARCHAR(100)',
            'price': 'VARCHAR(20)',
            'total_sold': 'INTEGER DEFAULT 0',
            'total_revenue': 'FLOAT DEFAULT 0.0'
        }
        
        # Expected columns for solutions
        solutions_cols = {
            'title': 'VARCHAR(200)',
            'recommended_skus': 'JSON',
            'collection_url': 'VARCHAR(300)'
        }
        
        sync_table(cursor, 'fault_codes', fault_codes_cols)
        sync_table(cursor, 'products', products_cols)
        sync_table(cursor, 'solutions', solutions_cols)
        
        conn.commit()
        conn.close()
        print("\n🎉 Synchronization complete! Your database is now perfectly in sync with the models.")
        print("💡 Please restart your uvicorn server to pick up the model changes.")
    except Exception as e:
        print(f"❌ Synchronization failed: {e}")

if __name__ == "__main__":
    migrate()
