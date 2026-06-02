"""
Apply GA4 migration directly to SQLite database
Run this script to add GA4 columns to collection_optimizer table
"""

import sqlite3
import os

def apply_ga4_migration():
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
    
    print(f"Connecting to database...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(collection_optimizer)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    print(f"Existing columns: {len(existing_columns)}")
    
    # GA4 columns to add
    ga4_columns = [
        ('ga4_sessions', 'INTEGER DEFAULT 0'),
        ('ga4_bounce_rate', 'REAL DEFAULT 0.0'),
        ('ga4_avg_engagement_time', 'REAL DEFAULT 0.0'),
        ('ga4_conversions', 'INTEGER DEFAULT 0'),
        ('ga4_conversion_rate', 'REAL DEFAULT 0.0'),
        ('ga4_revenue', 'REAL DEFAULT 0.0'),
        ('ga4_ai_referral_sessions', 'INTEGER DEFAULT 0'),
        ('ga4_ai_referral_conversions', 'INTEGER DEFAULT 0'),
        ('baseline_ga4_sessions', 'INTEGER DEFAULT 0'),
        ('baseline_ga4_conversions', 'INTEGER DEFAULT 0'),
        ('baseline_ga4_revenue', 'REAL DEFAULT 0.0'),
        ('baseline_ga4_date', 'DATETIME'),
        ('last_ga4_sync', 'DATETIME'),
    ]
    
    added_count = 0
    
    for column_name, column_type in ga4_columns:
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE collection_optimizer ADD COLUMN {column_name} {column_type}")
                print(f"[OK] Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"[WARN] Could not add {column_name}: {e}")
        else:
            print(f"[SKIP] Column already exists: {column_name}")

    conn.commit()
    conn.close()

    print(f"\nMigration complete! Added {added_count} new columns.")
    print("\nNext steps:")
    print("1. Set GOOGLE_GA4_PROPERTY_ID in your .env file")
    print("2. Set GOOGLE_APPLICATION_CREDENTIALS in your .env file")
    print("3. Run: POST /api/v1/collection-optimizer/ga4/analyze-all")

if __name__ == "__main__":
    apply_ga4_migration()
