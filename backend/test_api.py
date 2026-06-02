import requests
import json

# Test the product intelligence endpoint
url = "http://127.0.0.1:8000/api/v1/aeo/product-intelligence?days=365"

try:
    print(f"Testing {url}...")
    response = requests.get(url, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"\n✅ Valid JSON response")
            print(f"Status: {data.get('status', 'N/A')}")
            print(f"Products count: {len(data.get('products_from_llm', []))}")
            print(f"Opportunities count: {len(data.get('optimization_opportunities', []))}")
            print(f"Success patterns: {data.get('success_patterns')}")
            
            if data.get('products_from_llm'):
                print(f"\nFirst product:")
                print(json.dumps(data['products_from_llm'][0], indent=2))
        except json.JSONDecodeError as e:
            print(f"\n❌ Invalid JSON: {e}")
            print(f"Raw response (first 500 chars): {response.text[:500]}")
    else:
        print(f"\n❌ Error response: {response.text[:500]}")
        
except requests.exceptions.ConnectionError as e:
    print(f"❌ Connection error: {e}")
    print("Make sure the backend server is running on http://127.0.0.1:8000")
except Exception as e:
    print(f"❌ Error: {e}")
