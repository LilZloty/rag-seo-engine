"""
SEO Intelligence Daily Scheduler
Run this script daily to collect SEO intelligence data automatically.

Usage:
    # Run once manually
    python -m app.scheduler
    
    # Or add to crontab (Linux/Mac):
    # 0 6 * * * cd /path/to/backend && python -m app.scheduler
    
    # Or add to Windows Task Scheduler:
    # Program: python
    # Arguments: -m app.scheduler
    # Start in: C:\path\to\backend
"""
import requests
import sys
from datetime import datetime

def run_collection():
    """Trigger the daily collection endpoint."""
    API_BASE = "http://localhost:8000/api/v1/seo-intelligence"
    
    print(f"[{datetime.now().isoformat()}] Starting daily collection...")
    
    try:
        response = requests.post(f"{API_BASE}/collect", timeout=300)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Collection successful:")
            print(f"   - Queries stored: {result.get('queries_stored', 0)}")
            print(f"   - Pages stored: {result.get('pages_stored', 0)}")
            print(f"   - Funnel days stored: {result.get('funnel_days_stored', 0)}")
            print(f"   - Alerts generated: {result.get('alerts_generated', 0)}")
            print(f"   - Harvested at: {result.get('harvested_at')}")
            return True
        else:
            print(f"❌ Collection failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Collection error: {e}")
        return False

if __name__ == "__main__":
    success = run_collection()
    sys.exit(0 if success else 1)
