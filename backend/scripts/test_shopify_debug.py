# Test script to debug Shopify GraphQL
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from app.services.shopify_service import ShopifyService

shopify = ShopifyService()

# Test the query
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

print("Testing Shopify GraphQL query...")
orders = shopify._fetch_orders_with_utm(start_date, end_date)

print(f"\nFetched {len(orders)} orders")

# Check first few orders for LLM attribution
llm_orders = []
for order in orders:
    source = shopify._identify_llm_source(order)
    if source:
        llm_orders.append({
            'name': order.get('name'),
            'source': source,
            'date': order.get('createdAt'),
            'has_customer': 'customer' in order and order['customer'],
            'has_journey': 'customerJourneySummary' in order and order['customerJourneySummary'],
            'has_address': 'shippingAddress' in order and order['shippingAddress'],
            'has_line_items': 'lineItems' in order and order['lineItems'],
        })

print(f"\nFound {len(llm_orders)} LLM-attributed orders:")
for o in llm_orders[:5]:
    print(f"  - {o['name']}: {o['source']} | Customer: {o['has_customer']} | Journey: {o['has_journey']} | Address: {o['has_address']} | Items: {o['has_line_items']}")
