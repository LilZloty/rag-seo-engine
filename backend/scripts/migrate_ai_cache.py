"""
Migration script to add AI analysis cache table.
Run this to create the table for storing Grok analysis results.
"""
import sqlite3
import os

# Path to your SQLite database - change this if needed
DB_PATH = 'rag_seo.db'

def migrate():
    print("Starting AI Analysis Cache migration...")
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found: {DB_PATH}")
        print("Please run this script from the backend directory")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_analysis_cache'")
    if cursor.fetchone():
        print("ai_analysis_cache table already exists")
    else:
        print("Creating ai_analysis_cache table...")
        cursor.execute("""
            CREATE TABLE ai_analysis_cache (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                seo_score INTEGER DEFAULT 0,
                aeo_score INTEGER DEFAULT 0,
                geo_score INTEGER DEFAULT 0,
                seo_analysis JSON DEFAULT '{}',
                aeo_analysis JSON DEFAULT '{}',
                geo_analysis JSON DEFAULT '{}',
                recommendations JSON DEFAULT '[]',
                priority_actions JSON DEFAULT '[]',
                expected_impact JSON DEFAULT '{}',
                ga4_sessions_snapshot INTEGER DEFAULT 0,
                gsc_impressions_snapshot INTEGER DEFAULT 0,
                sold_30d_snapshot INTEGER DEFAULT 0,
                seo_score_snapshot INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_stale BOOLEAN DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)
        
        # Create index on product_id
        cursor.execute("CREATE INDEX idx_ai_analysis_product_id ON ai_analysis_cache (product_id)")
        print("Table created successfully")
    
    conn.commit()
    conn.close()
    
    print("")
    print("Migration complete!")
    print("")
    print("Next steps:")
    print("   1. Restart your backend server")
    print("   2. Run Grok analysis - it will now cache results automatically")
    print("   3. Cached results are valid for 24 hours")

if __name__ == "__main__":
    migrate()
