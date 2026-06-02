import sys, os
import asyncio
sys.path.append(os.getcwd())
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    from app.services.content_generator import content_generator_service
    from app.db.session import SessionLocal
    from app.models.product import Product

    async def main():
        db = SessionLocal()
        # Find the high-traffic product
        product = db.query(Product).filter(Product.title.like('%Aceite Motorcraft Mercon ULV%')).first()
        if not product:
            print("Product not found")
            return
            
        print(f"Generating content for: {product.title}")
        print(f"Current Handle: {product.handle}")
        print(f"Impressions: {product.gsc_impressions}")
        print("-" * 50)
        
        # Run the generator
        try:
            result = await content_generator_service.generate_for_product(
                product_id=str(product.id),
                provider="xai",
                model_name="grok-4.3" # Current model matching env
            )
            
            print("\n----- GENERATION RESULT -----")
            print(f"Original Handle: {product.handle}")
            print(f"Final Handle:    {result.get('url_handle')}")
            print(f"Original Title:  {product.title}")
            print(f"Final Title:     {result.get('h1_title')}")
            
            if "_seo_warnings" in result:
                print("\n[SEO WARNINGS]")
                for w in result["_seo_warnings"]:
                    print(f" - {w}")
        except Exception as e:
            print(f"Generation failed: {e}")
            
    asyncio.run(main())
except Exception as e:
    print(f"Error setting up test: {e}")
