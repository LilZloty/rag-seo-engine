
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.db.session import SessionLocal
    from app.models.product import Product
    from app.services.shopify_service import shopify_service
    
    print("Testing Shopify Product Intelligence logic...")
    
    # We don't necessarily need to run the full shopify_service.get_llm_product_insights() 
    # because it makes GraphQL calls. We just want to make sure the attribute access is gone.
    
    db = SessionLocal()
    try:
        # Fetch one product to test manual calculation logic (matching what's in the service now)
        product = db.query(Product).first()
        if product:
            print(f"Product found: {product.title}")
            desc_length = len(product.current_description_html or "")
            print(f"Calculated description length: {desc_length}")
            print("SUCCESS: Manual calculation works.")
        else:
            print("No products in database to test with.")
            
    finally:
        db.close()

except Exception as e:
    print(f"FAILED with error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
