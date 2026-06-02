"""
Initialize Solution Engine Database Tables

Run this script to create the Solution Engine tables directly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def init_solution_engine_tables():
    """Create Solution Engine tables in the database."""
    
    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Create blog_solutions table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS blog_solutions (
                id VARCHAR PRIMARY KEY,
                shopify_blog_id VARCHAR(50),
                title VARCHAR(300),
                handle VARCHAR(200),
                blog_handle VARCHAR(100),
                url VARCHAR(500),
                content_type VARCHAR(50),
                target_keywords JSON,
                primary_fault_code VARCHAR(20),
                related_fault_codes JSON,
                applicable_transmissions JSON,
                applicable_vehicles JSON,
                faq_schema JSON,
                howto_schema JSON,
                authority_signals JSON,
                monthly_clicks INTEGER DEFAULT 0,
                monthly_impressions INTEGER DEFAULT 0,
                avg_position REAL DEFAULT 0.0,
                avg_time_on_page INTEGER DEFAULT 0,
                conversion_rate REAL DEFAULT 0.0,
                content_summary TEXT,
                key_entities JSON,
                difficulty_level VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        
        # Create indexes for blog_solutions
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_blog_solutions_primary_fault_code 
            ON blog_solutions(primary_fault_code)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_blog_solutions_shopify_blog_id 
            ON blog_solutions(shopify_blog_id)
        """))
        
        # Create solution_paths table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS solution_paths (
                id VARCHAR PRIMARY KEY,
                query_pattern VARCHAR(200),
                query_intent VARCHAR(50),
                steps JSON,
                click_through_rate REAL DEFAULT 0.0,
                conversion_rate REAL DEFAULT 0.0,
                avg_revenue_per_path REAL DEFAULT 0.0,
                grok_optimized BOOLEAN DEFAULT 0,
                optimization_date TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_solution_paths_query_pattern 
            ON solution_paths(query_pattern)
        """))
        
        # Create product_recommendations table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS product_recommendations (
                id VARCHAR PRIMARY KEY,
                context_type VARCHAR(50),
                context_id VARCHAR(100),
                recommendations JSON,
                generated_by VARCHAR(50),
                generation_prompt TEXT,
                confidence_score REAL,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                purchases INTEGER DEFAULT 0,
                revenue_generated REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP
            )
        """))
        
        # Create query_product_affinity table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS query_product_affinity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_pattern VARCHAR(200),
                product_id VARCHAR,
                impression_count INTEGER DEFAULT 0,
                click_count INTEGER DEFAULT 0,
                purchase_count INTEGER DEFAULT 0,
                click_through_rate REAL DEFAULT 0.0,
                conversion_rate REAL DEFAULT 0.0,
                revenue_per_impression REAL DEFAULT 0.0,
                predicted_conversion_rate REAL DEFAULT 0.0,
                confidence REAL DEFAULT 0.0,
                last_updated TIMESTAMP,
                UNIQUE(query_pattern, product_id)
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_query_product_affinity_query_pattern 
            ON query_product_affinity(query_pattern)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_query_product_affinity_product_id 
            ON query_product_affinity(product_id)
        """))
        
        # Create smart_snippets table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS smart_snippets (
                id VARCHAR PRIMARY KEY,
                query VARCHAR(300),
                query_variations JSON,
                short_answer VARCHAR(300),
                detailed_answer TEXT,
                schema_type VARCHAR(50),
                schema_json JSON,
                related_products JSON,
                ai_citation_count INTEGER DEFAULT 0,
                position_0_count INTEGER DEFAULT 0,
                authority_quote VARCHAR(500),
                statistic_claims JSON,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_smart_snippets_query 
            ON smart_snippets(query)
        """))
        
        # Create blog_product_recommendations association table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS blog_product_recommendations (
                blog_id VARCHAR,
                product_id VARCHAR,
                recommendation_type VARCHAR(50),
                match_score REAL,
                conversion_rate REAL,
                FOREIGN KEY (blog_id) REFERENCES blog_solutions(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """))
        
        conn.commit()
        
        print("[OK] Solution Engine tables created successfully!")
        
        # Verify tables were created
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN (
                'blog_solutions', 'solution_paths', 'product_recommendations',
                'query_product_affinity', 'smart_snippets', 'blog_product_recommendations'
            )
        """))
        
        tables = [row[0] for row in result]
        print(f"\n[INFO] Tables created: {len(tables)}")
        for table in tables:
            print(f"  - {table}")

if __name__ == "__main__":
    init_solution_engine_tables()
