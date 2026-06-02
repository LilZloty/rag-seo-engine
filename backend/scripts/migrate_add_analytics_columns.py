"""
Migration script to add GA4/GSC analytics columns to the products table.
Run this script to fix: sqlite3.OperationalError: no such column: products.ga4_sessions
"""
import sqlite3
import os

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "rag_seo.db")

# Columns to add with their SQL definitions
NEW_COLUMNS = [
    # GA4 Analytics Fields
    ("ga4_sessions", "INTEGER DEFAULT 0"),
    ("ga4_engagement_time", "REAL DEFAULT 0.0"),
    ("ga4_bounce_rate", "REAL DEFAULT 0.0"),
    ("ga4_revenue", "REAL DEFAULT 0.0"),
    # Search Console Fields  
    ("gsc_impressions", "INTEGER DEFAULT 0"),
    ("gsc_clicks", "INTEGER DEFAULT 0"),
    ("gsc_ctr", "REAL DEFAULT 0.0"),
    ("gsc_position", "REAL DEFAULT 0.0"),
    # Calculated Fields
    ("performance_score", "INTEGER DEFAULT 0"),
    ("opportunity_level", "TEXT DEFAULT 'low'"),
    # Timestamps
    ("last_analytics_sync", "TIMESTAMP"),
]


def get_existing_columns(cursor, table_name):
    """Get list of existing column names in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def migrate():
    """Add missing analytics columns to the products table."""
    print("Connecting to database...")
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        existing_columns = get_existing_columns(cursor, "products")
        print(f"Existing columns: {existing_columns}")
        
        added = 0
        for column_name, column_def in NEW_COLUMNS:
            if column_name not in existing_columns:
                sql = f"ALTER TABLE products ADD COLUMN {column_name} {column_def}"
                print(f"Adding column: {column_name}")
                cursor.execute(sql)
                added += 1
            else:
                print(f"Column already exists: {column_name}")
        
        conn.commit()
        print(f"\n✅ Migration complete! Added {added} new columns.")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
