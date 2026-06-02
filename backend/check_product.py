"""Quick script to check what data exists in DB for product 7708800024681"""
import sqlite3
import json

conn = sqlite3.connect('rag_seo.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

pid = '7708800024681'

print("=" * 80)
print(f"1. PRODUCTS TABLE - searching for shopify_id or id = {pid}")
print("=" * 80)
cur.execute("SELECT id, shopify_id, title, product_type, ga4_sessions, sold_30d, revenue_30d, gsc_impressions, gsc_clicks, gsc_ctr, gsc_position, description_length, image_count, needs_seo, opportunity_level, performance_score FROM products WHERE shopify_id = ? OR id = ?", (pid, pid))
rows = cur.fetchall()
if rows:
    for r in rows:
        for key in r.keys():
            print(f"  {key}: {r[key]}")
else:
    print("  NOT FOUND in products table")

print()
print("=" * 80)
print(f"2. PRODUCT VISIBILITY SNAPSHOTS - searching for product_id = {pid}")
print("=" * 80)
try:
    cur.execute("SELECT * FROM product_visibility_snapshots WHERE product_id = ? ORDER BY snapshot_date DESC LIMIT 3", (pid,))
    rows = cur.fetchall()
    if rows:
        for i, r in enumerate(rows):
            print(f"\n  --- Snapshot {i+1} ---")
            for key in r.keys():
                val = r[key]
                if isinstance(val, str) and len(val) > 200:
                    val = val[:200] + "..."
                print(f"  {key}: {val}")
    else:
        print("  NOT FOUND in product_visibility_snapshots")
except Exception as e:
    print(f"  Error: {e}")

# Also try with integer ID
print()
print("=" * 80)
print(f"3. Checking if product_id is stored as integer")
print("=" * 80)
try:
    cur.execute("SELECT * FROM product_visibility_snapshots WHERE product_id = ? ORDER BY snapshot_date DESC LIMIT 3", (int(pid),))
    rows = cur.fetchall()
    if rows:
        for i, r in enumerate(rows):
            print(f"\n  --- Snapshot {i+1} ---")
            for key in r.keys():
                val = r[key]
                if isinstance(val, str) and len(val) > 200:
                    val = val[:200] + "..."
                print(f"  {key}: {val}")
    else:
        print("  NOT FOUND with integer ID either")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 80)
print(f"4. AI ANALYSIS CACHE - searching for product_id = {pid}")
print("=" * 80)
try:
    cur.execute("SELECT id, product_id, seo_score, aeo_score, geo_score, is_stale, updated_at, ga4_sessions_snapshot, gsc_impressions_snapshot, sold_30d_snapshot FROM ai_analysis_cache WHERE product_id = ?", (pid,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            for key in r.keys():
                print(f"  {key}: {r[key]}")
    else:
        print("  NOT FOUND in ai_analysis_cache")
except Exception as e:
    print(f"  Error: {e}")

# Check what the actual internal product ID is
print()
print("=" * 80)
print(f"5. Finding internal product ID for shopify_id = {pid}")
print("=" * 80)
try:
    cur.execute("SELECT id, shopify_id, title FROM products WHERE shopify_id = ?", (pid,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            internal_id = r['id']
            print(f"  Internal ID: {internal_id}, Shopify ID: {r['shopify_id']}, Title: {r['title']}")
            # Now check visibility with internal ID
            cur.execute("SELECT * FROM product_visibility_snapshots WHERE product_id = ? ORDER BY snapshot_date DESC LIMIT 1", (internal_id,))
            vis_rows = cur.fetchall()
            if vis_rows:
                print(f"\n  --- Visibility Snapshot (using internal_id={internal_id}) ---")
                for key in vis_rows[0].keys():
                    val = vis_rows[0][key]
                    if isinstance(val, str) and len(val) > 300:
                        val = val[:300] + "..."
                    print(f"  {key}: {val}")
            else:
                print(f"  No visibility snapshots for internal_id={internal_id}")
    else:
        print(f"  No product found with shopify_id = {pid}")
except Exception as e:
    print(f"  Error: {e}")

conn.close()
print("\nDone.")
