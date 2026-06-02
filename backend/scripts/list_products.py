import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.product import Product
from app.core.config import settings

def list_products():
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    products = db.query(Product).limit(10).all()
    
    print("\n📋 Sample Products in DB:")
    print("=" * 60)
    print(f"{'SKU':<15} | {'Title'}")
    print("-" * 60)
    for p in products:
        print(f"{p.sku:<15} | {p.title[:45]}")
    print("=" * 60)
    print("\nPick a SKU from above to run the comparison script.")

if __name__ == "__main__":
    list_products()
