import sys, os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.product import Product, ProductAnalyticsSnapshot

db = SessionLocal()
product = db.query(Product).filter(Product.title.like('%Aceite Motorcraft Mercon ULV%')).first()
if product:
    print(f"Product: {product.title}")
    print(f"Current DB Impressions: {product.gsc_impressions}")
    snaps = db.query(ProductAnalyticsSnapshot).filter(ProductAnalyticsSnapshot.product_id == product.id).order_by(ProductAnalyticsSnapshot.snapshot_date.desc()).all()
    print("\nSnapshots History:")
    for s in snaps:
        print(f"[{s.snapshot_date.strftime('%Y-%m-%d')}]: Imp={s.gsc_impressions}, Pos={s.gsc_position}, Sess={s.ga4_sessions}, SEO={s.seo_score}")
else:
    print("Product not found")
