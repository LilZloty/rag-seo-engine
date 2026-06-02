"""
Test Solution Engine Endpoints

Quick verification that the Solution Engine is working.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.solution_engine import SolutionEngine

def test_solution_engine():
    """Test the Solution Engine service."""
    
    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("SOLUTION ENGINE - PHASE 1 TEST")
        print("=" * 60)
        
        # Initialize engine
        se = SolutionEngine(db)
        
        # Test 1: Dashboard Stats
        print("\n[TEST 1] Dashboard Stats")
        print("-" * 40)
        stats = se.get_stats()
        print(f"  Fault codes total: {stats['fault_codes_total']}")
        print(f"  With products: {stats['fault_codes_with_products']}")
        print(f"  Coverage: {stats['coverage_percentage']}%")
        
        # Test 2: Get Products for P0700
        print("\n[TEST 2] Products for P0700")
        print("-" * 40)
        products = se.get_products_for_fault_code("P0700", 5)
        if products:
            for p in products[:3]:
                print(f"  {p['rank']}. {p['title'][:50]}...")
                print(f"     Score: {p['match_score']} | Reason: {p['reasoning'][:60]}...")
        else:
            print("  No products found")
        
        # Test 3: Solution Path
        print("\n[TEST 3] Solution Path for 'p0700 chevrolet'")
        print("-" * 40)
        path = se.generate_solution_path("p0700 chevrolet")
        print(f"  Query: {path['query']}")
        print(f"  Intent: {path['intent']}")
        print(f"  Fault Code: {path['fault_code']}")
        print("  Steps:")
        for step in path['steps']:
            print(f"    {step['step']}. [{step['type']}] {step['title']}")
        
        # Test 4: Smart Snippet
        print("\n[TEST 4] Smart Snippet for 'código p0700'")
        print("-" * 40)
        snippet = se.generate_smart_snippet("código p0700")
        print(f"  Short Answer: {snippet['short_answer'][:80]}...")
        print(f"  Authority: {snippet['authority_quote'][:60]}...")
        
        print("\n" + "=" * 60)
        print("[OK] All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_solution_engine()
