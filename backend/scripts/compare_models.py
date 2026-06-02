import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.llm_service import LLMService
# from app.api.v1.endpoints.content import get_db
from sqlalchemy.orm import Session
from app.models.product import Product
from app.services.content_generator import ContentGeneratorService
from app.core.config import settings

async def compare_models(sku: str):
    print(f"\n🚀 Starting Comparison for SKU: {sku}")
    print("=" * 60)
    
    # Initialize services
    llm_service = LLMService()
    generator = ContentGeneratorService()
    
    # Mock some context or fetch from DB if available
    # For a simple test, we'll just pass empty context or 
    # try to fetch the product to get real info
    # from sqlalchemy import create_url
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    product = db.query(Product).filter(Product.sku == sku).first()
    if not product:
        print(f"❌ Product with SKU {sku} not found in DB.")
        return
    
    print(f"📦 Product Found: {product.title}")
    shopify_id = product.shopify_id
    
    results = {}
    providers = [
        ("grok", "grok-4-1-fast-reasoning"),
        ("anthropic", "claude-sonnet-4-5-20250929"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("mistral", "mistral-large-latest")
    ]
    
    for provider, model in providers:
        print(f"\n🤖 Calling {provider.upper()} ({model})...")
        try:
            # We'll use the generator service to get the full logic (RAG + Prompting)
            # Note: This assumes you have RAG data indexed. If not, it will use base product info.
            content = await generator.generate_for_product(shopify_id, provider=provider, model_name=model)
            results[provider] = content
            print(f"✅ {provider.upper()} success! (Length: {len(str(content))} chars)")
        except Exception as e:
            print(f"❌ {provider.upper()} failed: {e}")
    
    # Save results to a comparison file
    output_file = Path(f"comparison_{sku}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print(f"✨ Comparison complete! Results saved to: {output_file.absolute()}")
    print("=" * 60)
    
    # Print summary of H1 titles
    print("\nSummary of generated H1 Titles:")
    for p, data in results.items():
        print(f"- {p.upper()}: {data.get('h1_title', 'N/A')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/compare_models.py <SKU>")
        sys.exit(1)
    
    sku = sys.argv[1]
    asyncio.run(compare_models(sku))
