import sys, os
import asyncio
sys.path.append(os.getcwd())
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    from app.api.v1.endpoints.content_analyzer import diagnose_primary_issue, build_enriched_analysis_prompt
    
    # Test diagnose_primary_issue
    print("Testing diagnose_primary_issue...")
    benchmarks = {"avg_sessions": 150, "avg_ctr": 3.5, "avg_conversion_rate": 2.1}
    # Test High tier
    res1 = diagnose_primary_issue(sessions=500, impressions=1500, clicks=100, sold=15, position=3.5, benchmarks=benchmarks)
    print(f"High Performer: Tier={res1.get('performance_tier')} (Expected: HIGH)")
    # Test Established tier
    res2 = diagnose_primary_issue(sessions=50, impressions=500, clicks=10, sold=1, position=12.5, benchmarks=benchmarks)
    print(f"Established Performer: Tier={res2.get('performance_tier')} (Expected: ESTABLISHED)")

    print("\nSyntax check complete on content_analyzer.py!")
except Exception as e:
    import traceback
    print("Error during test:")
    traceback.print_exc()
