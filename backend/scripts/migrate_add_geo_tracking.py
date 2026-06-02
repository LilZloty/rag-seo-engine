"""
Migration script to add GEO/AEO tracking tables.
Creates 'geo_metrics' and 'perplexity_citations' tables.
"""

import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import engine, Base
from app.models.aeo_models import GEOMetric, PerplexityCitation

def migrate():
    print("🔄 Starting GEO Tracking Migration...")
    
    # Create tables defined in models that don't exist yet
    try:
        GEOMetric.__table__.create(engine, checkfirst=True)
        print("✅ Table 'geo_metrics' created or already exists.")
        
        PerplexityCitation.__table__.create(engine, checkfirst=True)
        print("✅ Table 'perplexity_citations' created or already exists.")
        
        print("🎉 Migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate()
