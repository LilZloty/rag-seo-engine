"""
Solution Engine Batch Processing
=================================

Batch operations for Phase 2:
1. AI analysis of all fault codes
2. Solution path generation for top queries
3. Smart snippet creation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.solution_engine_ai import SolutionEngineAI
from app.services.llms_txt_enhanced import generate_enhanced_llms_txt
from app.models.aeo_models import FaultCode

def init_db_session():
    """Initialize database session."""
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

async def batch_analyze_fault_codes():
    """Run AI analysis on all fault codes."""
    print("=" * 70)
    print("BATCH: AI Analysis of Fault Codes")
    print("=" * 70)
    
    db = init_db_session()
    
    try:
        se = SolutionEngineAI(db)
        
        # Get all fault codes
        fault_codes = db.query(FaultCode).all()
        
        print(f"\nFound {len(fault_codes)} fault codes to analyze\n")
        
        results = []
        for i, fc in enumerate(fault_codes, 1):
            print(f"[{i}/{len(fault_codes)}] Analyzing {fc.code}...", end=" ")
            
            try:
                result = await se.analyze_fault_code_with_ai(fc.code)
                
                if "error" in result:
                    print(f"ERROR: {result['error']}")
                    results.append({"code": fc.code, "status": "error", "error": result['error']})
                else:
                    product_count = len(result.get("products", []))
                    ai_analyzed = result.get("ai_analyzed", False)
                    print(f"OK ({product_count} products, AI={ai_analyzed})")
                    results.append({
                        "code": fc.code,
                        "status": "success",
                        "products": product_count,
                        "ai_analyzed": ai_analyzed,
                        "confidence": result.get("confidence", 0)
                    })
                
            except Exception as e:
                print(f"FAILED: {e}")
                results.append({"code": fc.code, "status": "failed", "error": str(e)})
        
        # Summary
        successful = sum(1 for r in results if r["status"] == "success")
        ai_analyzed_count = sum(1 for r in results if r.get("ai_analyzed"))
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total: {len(results)}")
        print(f"Successful: {successful}")
        print(f"AI Analyzed: {ai_analyzed_count}")
        print(f"Failed: {len(results) - successful}")
        
    finally:
        db.close()

async def generate_solution_paths():
    """Generate solution paths for top search queries."""
    print("\n" + "=" * 70)
    print("BATCH: Generate Solution Paths")
    print("=" * 70)
    
    db = init_db_session()
    
    try:
        se = SolutionEngineAI(db)
        
        # Top queries from Search Console data
        top_queries = [
            "p0700",
            "p0706",
            "p0715",
            "p0730",
            "p0743",
            "p0841",
            "p0868",
            "p0700 chevrolet",
            "p0706 nissan",
            "codigo p0700 que significa",
            "p0700 chrysler",
            "p0730 chevy"
        ]
        
        print(f"\nGenerating paths for {len(top_queries)} queries...\n")
        
        for query in top_queries:
            print(f"Creating path: '{query}'...", end=" ")
            
            try:
                # Generate steps
                path_data = se.solution_engine.generate_solution_path(query)
                
                # Persist path
                se.create_solution_path(
                    query_pattern=query,
                    steps=path_data["steps"]
                )
                
                print(f"OK ({len(path_data['steps'])} steps)")
                
            except Exception as e:
                print(f"FAILED: {e}")
        
        print("\n[OK] Solution paths created")
        
    finally:
        db.close()

async def generate_smart_snippets():
    """Generate smart snippets for top queries."""
    print("\n" + "=" * 70)
    print("BATCH: Generate Smart Snippets")
    print("=" * 70)
    
    db = init_db_session()
    
    try:
        se = SolutionEngineAI(db)
        
        # Queries to generate snippets for
        queries = [
            "codigo p0700",
            "que es p0700",
            "p0700 solucion",
            "p0706 nissan",
            "p0715 ford",
            "p0730 toyota",
            "p0743 chrysler",
            "p0841 mazda"
        ]
        
        print(f"\nGenerating snippets for {len(queries)} queries...\n")
        
        for query in queries:
            print(f"Snippet: '{query}'...", end=" ")
            
            try:
                snippet = await se.generate_geo_snippet(query)
                
                if snippet.get("geo_optimized"):
                    print(f"OK (GEO optimized)")
                else:
                    print(f"OK")
                    
            except Exception as e:
                print(f"FAILED: {e}")
        
        print("\n[OK] Smart snippets created")
        
    finally:
        db.close()

def generate_enhanced_llms_txt_file():
    """Generate and save enhanced llms.txt."""
    print("\n" + "=" * 70)
    print("BATCH: Generate Enhanced llms.txt")
    print("=" * 70)
    
    db = init_db_session()
    
    try:
        print("\nGenerating enhanced llms.txt with Solution Engine...")
        
        content = generate_enhanced_llms_txt(db)
        
        # Save to file
        output_path = "llms_enhanced.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n[OK] Saved to {output_path}")
        print(f"Size: {len(content)} bytes")
        print(f"Lines: {len(content.split(chr(10)))}")
        
        # Preview
        print("\n--- PREVIEW (first 500 chars) ---")
        print(content[:500])
        print("...")
        
    finally:
        db.close()

async def run_all():
    """Run all batch operations."""
    print("\n" + "=" * 70)
    print("SOLUTION ENGINE - PHASE 2 BATCH OPERATIONS")
    print("=" * 70)
    
    # 1. AI Analysis
    await batch_analyze_fault_codes()
    
    # 2. Solution Paths
    await generate_solution_paths()
    
    # 3. Smart Snippets
    await generate_smart_snippets()
    
    # 4. Enhanced llms.txt
    generate_enhanced_llms_txt_file()
    
    print("\n" + "=" * 70)
    print("ALL BATCH OPERATIONS COMPLETED")
    print("=" * 70)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "fault-codes":
            asyncio.run(batch_analyze_fault_codes())
        elif command == "paths":
            asyncio.run(generate_solution_paths())
        elif command == "snippets":
            asyncio.run(generate_smart_snippets())
        elif command == "llms":
            generate_enhanced_llms_txt_file()
        else:
            print(f"Unknown command: {command}")
            print("Available: fault-codes, paths, snippets, llms, all")
    else:
        # Run all
        asyncio.run(run_all())
