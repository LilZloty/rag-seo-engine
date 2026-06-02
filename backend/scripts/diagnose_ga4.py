"""
Diagnostic script to check Google Analytics API connectivity
Run this to debug GA4 permission issues
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Metric,
    Dimension
)

def diagnose_ga4_connection():
    """Diagnose GA4 connection issues"""
    
    print("=" * 60)
    print("GOOGLE ANALYTICS 4 API DIAGNOSTIC")
    print("=" * 60)
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    # 1. Check credentials file
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    print(f"\n1. Credentials Path: {creds_path}")
    
    if not creds_path:
        print("   ❌ ERROR: GOOGLE_APPLICATION_CREDENTIALS not set in .env")
        return
    
    if not os.path.exists(creds_path):
        print(f"   ❌ ERROR: Credentials file not found at {creds_path}")
        return
    
    print("   ✅ Credentials file exists")
    
    # 2. Load credentials and check service account
    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        print(f"   ✅ Service Account: {credentials.service_account_email}")
    except Exception as e:
        print(f"   ❌ ERROR loading credentials: {e}")
        return
    
    # 3. Check Property ID
    property_id = os.getenv('GOOGLE_GA4_PROPERTY_ID')
    print(f"\n2. GA4 Property ID: {property_id}")
    
    if not property_id:
        print("   ❌ ERROR: GOOGLE_GA4_PROPERTY_ID not set in .env")
        print("   ℹ️  Get this from GA4 Admin > Property Settings")
        return
    
    # Clean property ID
    property_id = property_id.replace('properties/', '').strip()
    print(f"   ℹ️  Using Property ID: {property_id}")
    
    # 4. Try to connect and run a simple report
    print(f"\n3. Testing GA4 API Connection...")
    
    try:
        client = BetaAnalyticsDataClient(credentials=credentials)
        
        # Try to get a simple report
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
            limit=1
        )
        
        response = client.run_report(request)
        
        print("   ✅ SUCCESS! Connected to GA4 API")
        print(f"   📊 Sample data: {len(response.rows)} rows returned")
        
        # 5. Check for LLM traffic specifically
        print(f"\n4. Checking for LLM-related traffic...")
        
        # Check pageReferrer for LLM sources
        llm_request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="pageReferrer")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
            dimension_filter={
                "filter": {
                    "field_name": "pageReferrer",
                    "string_filter": {
                        "match_type": "CONTAINS",
                        "value": "openai"
                    }
                }
            },
            limit=10
        )
        
        llm_response = client.run_report(llm_request)
        print(f"   ℹ️  OpenAI referrer sessions: {sum(row.metric_values[0].value for row in llm_response.rows)}")
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        
        if "403" in str(e):
            print("\n" + "=" * 60)
            print("PERMISSION ERROR (403)")
            print("=" * 60)
            print("""
The service account doesn't have access to this GA4 property.

TO FIX:
1. Go to https://analytics.google.com/
2. Select your property
3. Click Admin (gear icon) → Property Access Management
4. Click + Add users
5. Add this email: {credentials.service_account_email}
6. Set role to "Viewer" or "Analyst"
7. Click Add

Wait 2-3 minutes for permissions to propagate, then try again.
            """)
        elif "404" in str(e):
            print("\n" + "=" * 60)
            print("PROPERTY NOT FOUND (404)")
            print("=" * 60)
            print(f"""
The Property ID {property_id} was not found.

TO FIX:
1. Verify the Property ID in GA4 Admin > Property Settings
2. Make sure you're using the numeric ID (e.g., "123456789")
3. NOT the full path (don't use "properties/123456789")
            """)

if __name__ == "__main__":
    # Load .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    diagnose_ga4_connection()
