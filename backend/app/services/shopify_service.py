import shopify
from app.core.config import settings
from app.services.redis_service import create_cache, TTLCache
import time
import json
from typing import Dict, Any, Optional, List

# Global cache instances (Redis-backed when USE_REDIS=true, in-memory fallback)
_product_cache = create_cache(default_ttl=300)   # 5 minutes for product details
_fitment_cache = create_cache(default_ttl=600)   # 10 minutes for fitments
_llm_sales_cache = create_cache(default_ttl=3600)  # 1 hour - sales data is stable

# Configurable LLM source patterns for sales attribution
# Keys are normalized source names, values are patterns to match in:
# - referrerUrl (e.g., chat.openai.com)
# - source (platform name)
# - utmParameters (utm_source, utm_medium, utm_campaign)
# - landingPage URLs with UTM params
# IMPORTANT: Be specific to avoid false positives (e.g., google.com != Gemini)
LLM_SOURCE_PATTERNS = {
    'chatgpt': ['chatgpt', 'chat.openai.com', 'openai.com'],
    'gemini': ['gemini.google', 'aistudio.google'],  # Specific Gemini URLs only
    'perplexity': ['perplexity.ai', 'perplexity'],
    'claude': ['claude.ai', 'anthropic.com'],
    'copilot': ['copilot.microsoft', 'bing.com/chat'],
    'grok': ['grok', 'x.com/i/grok'],
}

# UTM sources that indicate LLM traffic (more reliable than referrer matching)
LLM_UTM_SOURCES = {
    'chatgpt': ['chatgpt', 'openai', 'gpt'],
    'gemini': ['gemini', 'bard', 'google-ai'],
    'perplexity': ['perplexity', 'pplx'],
    'claude': ['claude', 'anthropic'],
    'copilot': ['copilot', 'bing-ai'],
    'grok': ['grok', 'xai'],
}




class ShopifyService:
    def __init__(self):
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization to avoid errors if Shopify credentials are not set"""
        if self._initialized:
            return True
        
        if not settings.SHOPIFY_ACCESS_TOKEN or not settings.SHOPIFY_STORE:
            print("⚠️ Shopify credentials not configured - sync will not work")
            return False
        
        try:
            # Use Session-based authentication for Admin API access tokens
            api_version = settings.SHOPIFY_API_VERSION
            shop_url = settings.SHOPIFY_STORE
            token = settings.SHOPIFY_ACCESS_TOKEN
            
            # Create and activate session
            session = shopify.Session(shop_url, api_version, token)
            shopify.ShopifyResource.activate_session(session)
            
            print(f"✅ Shopify connected to {shop_url}")
            self._initialized = True
            return True
        except Exception as e:
            print(f"⚠️ Failed to initialize Shopify: {e}")
            return False
    
    def get_all_products(self, limit=250, status='active'):
        """Fetch all products from Shopify. Default only fetches published (active) products."""
        if not self._ensure_initialized():
            return []
        
        products = []
        page_num = 1
        # Only fetch published products by default
        page = shopify.Product.find(limit=limit, status=status)
        
        while page:
            products.extend(page)
            print(f"📦 Fetched page {page_num}: {len(products)} products so far...")
            
            if page.has_next_page():
                page = page.next_page()
                page_num += 1
            else:
                break
        
        print(f"✅ Total products fetched: {len(products)}")
        return products
    
    def get_product_by_id(self, product_id):
        if not self._ensure_initialized():
            return None
        return shopify.Product.find(product_id)
    
    def get_product_by_handle(self, handle):
        if not self._ensure_initialized():
            return None
        try:
            return shopify.Product.find(handle=handle)
        except shopify.ResourceNotFound:
            return None
    
    def update_product(self, product_id, data):
        if not self._ensure_initialized():
            return None

        try:
            product = shopify.Product.find(product_id)
            if not product:
                print(f"Product {product_id} not found")
                return None

            # Capture old handle so we can guarantee the 301 redirect after save.
            # Shopify *should* auto-create the redirect on handle change, but we've
            # observed cases where the redirect is missing (drafts, productSet, race
            # conditions with apps), causing old URLs to 404 and bleed SEO equity.
            _old_handle = product.handle
            _new_handle = data.get('handle')

            # Basic fields
            if 'title' in data: product.title = data['title']
            if 'body_html' in data: product.body_html = data['body_html']
            if 'handle' in data: product.handle = data['handle']
            
            # Standard SEO metafields (Shopify handles these legacy fields specially)
            if 'metafields_global_title_tag' in data:
                product.add_metafield(shopify.Metafield({
                    'namespace': 'global',
                    'key': 'title_tag',
                    'value': data['metafields_global_title_tag'],
                    'type': 'single_line_text_field'
                }))
            if 'metafields_global_description_tag' in data:
                product.add_metafield(shopify.Metafield({
                    'namespace': 'global',
                    'key': 'description_tag',
                    'value': data['metafields_global_description_tag'],
                    'type': 'multi_line_text_field'
                }))
            
            # Custom metafields
            if 'metafields' in data:
                print(f"[Shopify] Processing {len(data['metafields'])} metafields")
                for full_key, value in data['metafields'].items():
                    if '.' in full_key:
                        namespace, key = full_key.split('.', 1)
                        
                        # Debug logging
                        print(f"[Shopify] Processing metafield: {full_key}")
                        print(f"[Shopify] Value type: {type(value)}, Value preview: {str(value)[:200] if value else 'EMPTY'}")
                        
                        # Determine type based on value
                        if isinstance(value, (list, dict)):
                            metafield_value = json.dumps(value)
                            metafield_type = 'json'
                        elif full_key == 'standard.product_description':
                            # Shopify Rich Text fields need a specific JSON structure
                            # Ensure value is a plain string, not already JSON
                            if isinstance(value, str):
                                # If value looks like JSON, extract the text content
                                if value.strip().startswith('{') or value.strip().startswith('['):
                                    try:
                                        parsed = json.loads(value)
                                        if isinstance(parsed, dict) and 'children' in parsed:
                                            # Already in rich text format, use as-is
                                            metafield_value = value
                                            metafield_type = 'rich_text_field'
                                        else:
                                            # Plain text that happens to look like JSON
                                            metafield_value = json.dumps({
                                                "type": "root",
                                                "children": [{"type": "paragraph", "children": [{"type": "text", "value": str(value)}]}]
                                            })
                                            metafield_type = 'rich_text_field'
                                    except json.JSONDecodeError:
                                        # Not valid JSON, treat as plain text
                                        metafield_value = json.dumps({
                                            "type": "root",
                                            "children": [{"type": "paragraph", "children": [{"type": "text", "value": str(value)}]}]
                                        })
                                        metafield_type = 'rich_text_field'
                                else:
                                    # Plain text
                                    metafield_value = json.dumps({
                                        "type": "root",
                                        "children": [{"type": "paragraph", "children": [{"type": "text", "value": str(value)}]}]
                                    })
                                    metafield_type = 'rich_text_field'
                            else:
                                metafield_value = json.dumps({
                                    "type": "root",
                                    "children": [{"type": "paragraph", "children": [{"type": "text", "value": str(value)}]}]
                                })
                                metafield_type = 'rich_text_field'
                        elif full_key == 'custom.product_schema_json':
                            # JSON-LD schema stored in Shopify metafield (JSON type)
                            if isinstance(value, str):
                                metafield_value = value
                            else:
                                metafield_value = json.dumps(value, ensure_ascii=False)
                            metafield_type = 'json'
                            print(f"[Shopify] product_schema_json: {len(metafield_value)} chars as {metafield_type}")
                        elif full_key == 'custom.custom_compatible_vehicles':
                            # Ensure value is a string and truncate if too long
                            str_value = str(value) if value else ''
                            # Shopify multi_line_text_field has a limit, truncate to be safe
                            if len(str_value) > 5000:
                                str_value = str_value[:4997] + '...'
                            metafield_value = str_value
                            metafield_type = 'multi_line_text_field'
                        elif full_key == 'custom.resumen':
                            # Technical summary (Ficha Técnica) table
                            metafield_value = str(value) if value else ''
                            metafield_type = 'multi_line_text_field'
                        else:
                            metafield_value = str(value) if value else ''
                            metafield_type = 'single_line_text_field'
                        
                        print(f"[Shopify] Adding metafield: {namespace}.{key} = {metafield_value[:100]}... (type: {metafield_type})")
                        
                        product.add_metafield(shopify.Metafield({
                            'namespace': namespace,
                            'key': key,
                            'value': metafield_value,
                            'type': metafield_type
                        }))

            # Image alt tags
            if 'image_alts' in data:
                # data['image_alts'] should be a dict of {image_id: new_alt}
                if hasattr(product, 'images'):
                    for img in product.images:
                        if str(img.id) in data['image_alts']:
                            img.alt = data['image_alts'][str(img.id)]
                        elif img.id in data['image_alts']:
                            img.alt = data['image_alts'][img.id]
            
            # Save and check for errors
            success = product.save()
            if not success:
                print(f"[Shopify] Failed to save product. Errors: {product.errors.full_messages()}")
                return None

            # Force-create the 301 redirect when the handle changed. Shopify is
            # supposed to do this automatically, but we've seen products end up
            # with the new handle and no redirect (likely drafts/apps interfering),
            # which causes the old URL to 404 and breaks Google Merchant Center
            # links + SEO equity. We attempt the create unconditionally and
            # swallow "duplicate" errors when Shopify already did it for us.
            if _new_handle and _old_handle and _new_handle != _old_handle:
                try:
                    redirect = shopify.Redirect()
                    redirect.path = f"/products/{_old_handle}"
                    redirect.target = f"/products/{_new_handle}"
                    if redirect.save():
                        print(f"[Shopify] 301 redirect created: /products/{_old_handle} → /products/{_new_handle}")
                    else:
                        msgs = redirect.errors.full_messages() if hasattr(redirect, "errors") else []
                        if any("taken" in m.lower() or "duplicate" in m.lower() for m in msgs):
                            print(f"[Shopify] 301 redirect already existed for /products/{_old_handle}")
                        else:
                            print(f"[Shopify] WARN — redirect save failed for /products/{_old_handle}: {msgs}")
                except Exception as redirect_err:
                    print(f"[Shopify] WARN — redirect create raised for /products/{_old_handle}: {redirect_err}")

            # Invalidate cache after successful update
            _product_cache.invalidate(f"product:{product_id}")
            print(f"[Shopify] Product {product_id} saved successfully (cache invalidated)")
            return product
        except Exception as e:
            print(f"Error updating product {product_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_product_images(self, product_id):
        if not self._ensure_initialized():
            return []
        
        product = shopify.Product.find(product_id)
        if product and hasattr(product, 'images'):
            return [{'id': img.id, 'src': img.src, 'alt': img.alt or '', 'filename': self._extract_filename(img.src)} 
                    for img in product.images]
        return []
    
    def convert_alt_tags_to_image_alts(self, product_id, alt_tags: list) -> dict:
        """
        Convert generated alt_tags array to image_alts dict for update_product.
        
        Args:
            product_id: Shopify product ID
            alt_tags: List of alt tags in format ["filename.jpg | Alt text", ...]
        
        Returns:
            Dict of {image_id: alt_text} that update_product expects
        """
        if not alt_tags:
            return {}
        
        # Get current product images
        images = self.get_product_images(product_id)
        if not images:
            print(f"[Shopify] No images found for product {product_id}")
            return {}
        
        image_alts = {}
        
        # Match alt_tags to images by position (1st alt_tag -> 1st image, etc.)
        for i, alt_tag in enumerate(alt_tags):
            if i >= len(images):
                break  # More alt_tags than images
            
            # Parse alt_tag format: "filename.jpg | Alt text description"
            if '|' in alt_tag:
                parts = alt_tag.split('|', 1)
                alt_text = parts[1].strip() if len(parts) > 1 else alt_tag.strip()
            else:
                alt_text = alt_tag.strip()
            
            image_id = str(images[i]['id'])
            image_alts[image_id] = alt_text
            print(f"[Shopify] Image {i+1} ({images[i]['filename'][:30]}...) -> Alt: {alt_text[:50]}...")
        
        print(f"[Shopify] Mapped {len(image_alts)} alt tags to image IDs")
        return image_alts
    
    def update_product_images_graphql(self, product_id, alt_tags: list) -> bool:
        """
        Update product image filenames and alt text using GraphQL mutations.
        Uses productImageUpdate for alt text and fileUpdate for filename renaming.

        Args:
            product_id: Shopify product ID
            alt_tags: List of alt tags in format ["new-filename.jpg | Alt text", ...]

        Returns:
            bool: True if some updates succeeded

        Gap #14: this used to GraphQL-update alt text + filename for every
        image on every save, even when the values hadn't changed. That
        burned quota on no-op writes and bumped Shopify's last_modified
        on the product whenever Grok regenerated content for a product
        whose images were already correct. Now we fetch each image's
        current altText + URL in the same media query and SKIP the alt
        mutation if the new text matches, and SKIP the file rename if the
        derived filename already matches the URL.
        """
        if not self._ensure_initialized():
            return False

        if not alt_tags:
            return True

        # Fetch MediaImage GIDs for renaming + current altText/url so we can
        # diff and skip no-op writes (Gap #14).
        media_nodes = []
        try:
            media_query = """
            query getProductMedia($id: ID!) {
              product(id: $id) {
                media(first: 20) {
                  edges {
                    node {
                      id
                      ... on MediaImage {
                        image {
                          url
                          altText
                        }
                      }
                    }
                  }
                }
              }
            }
            """
            media_result = self._graphql_request(media_query, {"id": f"gid://shopify/Product/{product_id}"})
            edges = media_result.get('data', {}).get('product', {}).get('media', {}).get('edges', [])
            media_nodes = [edge['node'] for edge in edges]
            print(f"[Shopify GraphQL] Found {len(media_nodes)} media nodes for product {product_id}")
        except Exception as e:
            print(f"[Shopify GraphQL] Failed to fetch media GIDs: {e}")

        success_count = 0
        alt_skipped = 0
        rename_skipped = 0

        for i, alt_tag in enumerate(alt_tags):
            if i >= len(media_nodes):
                break

            # Parse alt_tag format: "new-filename.jpg | Alt text description"
            if '|' in alt_tag:
                parts = alt_tag.split('|', 1)
                new_filename = parts[0].strip()
                alt_text = parts[1].strip() if len(parts) > 1 else ''
            else:
                new_filename = None
                alt_text = alt_tag.strip()

            media_node = media_nodes[i]
            current_image = media_node.get('image') or {}
            current_alt = (current_image.get('altText') or '').strip()
            image_url = current_image.get('url', '')

            # Extract image ID from media_node (GID format: gid://shopify/MediaImage/123)
            media_id = media_node.get('id', '')
            image_id = media_id.split('/')[-1] if media_id else str(i)

            # Extract filename from URL
            orig_filename = image_url.split('/')[-1].split('?')[0] if image_url else f"image_{i}.jpg"

            # 1. Update Alt Text (using ProductImage ID).
            # Gap #14: skip the GraphQL call entirely when the new alt is
            # identical to what's already on the image. No-op writes still
            # cost quota AND touch Shopify's product.updated_at, which can
            # silently break "stale cache" heuristics elsewhere.
            if alt_text == current_alt:
                alt_skipped += 1
                print(f"[Shopify GraphQL] Skipping alt update for image {i+1} — unchanged")
            else:
                try:
                    alt_mutation = """
                    mutation productImageUpdate($productId: ID!, $image: ImageInput!) {
                        productImageUpdate(productId: $productId, image: $image) {
                            image { id altText }
                            userErrors { field message }
                        }
                    }
                    """
                    alt_variables = {
                        "productId": f"gid://shopify/Product/{product_id}",
                        "image": {
                            "id": f"gid://shopify/ProductImage/{image_id}",
                            "altText": alt_text
                        }
                    }
                    self._graphql_request(alt_mutation, alt_variables)
                    print(f"[Shopify GraphQL] Updated alt text for image {i+1}")
                except Exception as e:
                    print(f"[Shopify GraphQL] Failed to update alt for image {i+1}: {e}")

            # 2. Update Filename (using MediaImage ID). Same Gap #14 short-
            # circuit: derive the final filename we WOULD push, compare to
            # what's already there, and only call fileUpdate when different.
            if new_filename:
                # Preserve original extension from URL
                ext = ""
                if '.' in orig_filename:
                    ext = "." + orig_filename.split('.')[-1]
                if not ext:
                    ext = ".jpg"  # Default extension

                # Clean new_filename (remove extension if provided, we'll re-add original)
                clean_name = new_filename
                if clean_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    clean_name = '.'.join(clean_name.split('.')[:-1])

                final_filename = clean_name + ext

                # Gap #14: skip the fileUpdate if the existing URL already
                # contains this exact filename. Shopify's URL is the only
                # client-visible filename signal we have, so URL match ==
                # filename match for our purposes.
                if final_filename == orig_filename:
                    rename_skipped += 1
                    print(f"[Shopify GraphQL] Skipping rename for image {i+1} — already named {final_filename}")
                    success_count += 1
                else:
                    try:
                        file_update_mutation = """
                        mutation fileUpdate($files: [FileUpdateInput!]!) {
                          fileUpdate(files: $files) {
                            files { id ... on MediaImage { image { url } } }
                            userErrors { field message }
                          }
                        }
                        """

                        file_variables = {
                          "files": [{
                            "id": media_id,
                            "filename": final_filename
                          }]
                        }

                        file_result = self._graphql_request(file_update_mutation, file_variables)
                        if file_result.get('data', {}).get('fileUpdate', {}).get('userErrors'):
                            print(f"[Shopify GraphQL] Filename error: {file_result['data']['fileUpdate']['userErrors']}")
                        else:
                            print(f"[Shopify GraphQL] Renamed image {i+1} to {final_filename}")
                            success_count += 1
                    except Exception as e:
                        print(f"[Shopify GraphQL] Failed to rename image {i+1}: {e}")
            else:
                success_count += 1 # Alt text was updated

        if alt_skipped or rename_skipped:
            print(f"[Shopify GraphQL] Gap #14: skipped {alt_skipped} no-op alt update(s) "
                  f"and {rename_skipped} no-op rename(s) — saved {alt_skipped + rename_skipped} "
                  f"GraphQL mutations.")
        return success_count > 0
    
    def get_product_full_details(self, shopify_id, bypass_cache: bool = False):
        """Get full product details including metafields for editing.
        
        Args:
            shopify_id: Shopify product ID
            bypass_cache: If True, skip cache and fetch fresh from Shopify
        """
        if not self._ensure_initialized():
            return None
        
        cache_key = f"product:{shopify_id}"
        
        # Check cache first (unless bypassing)
        if not bypass_cache:
            cached = _product_cache.get(cache_key)
            if cached:
                print(f"[Shopify] Cache HIT for product {shopify_id}")
                return cached
        
        print(f"[Shopify] Cache MISS - fetching product {shopify_id} from API...")
        
        try:
            product = shopify.Product.find(shopify_id)
            if not product:
                return None
            
            # Get product metafields for SEO data
            metafields = shopify.Metafield.find(resource='products', resource_id=shopify_id)
            
            # Parse metafields into a dict
            meta_dict = {}
            for mf in metafields:
                key = f"{mf.namespace}.{mf.key}"
                value = mf.value
                
                # Handle rich text fields - extract plain text from JSON structure
                if mf.type == 'rich_text_field' and isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, dict) and 'children' in parsed:
                            # Extract text from the rich text structure
                            texts = []
                            for child in parsed.get('children', []):
                                if child.get('type') == 'paragraph':
                                    for text_child in child.get('children', []):
                                        if text_child.get('type') == 'text':
                                            texts.append(text_child.get('value', ''))
                            value = ' '.join(texts)
                    except (json.JSONDecodeError, AttributeError):
                        pass  # Keep original value if parsing fails
                
                meta_dict[key] = value
            
            # Get images with alt tags
            images = []
            if hasattr(product, 'images'):
                for img in product.images:
                    images.append({
                        'id': img.id,
                        'src': img.src,
                        'alt': img.alt or '',
                        'filename': self._extract_filename(img.src)
                    })
            
            result = {
                'shopify_id': product.id,
                'title': product.title,
                'handle': product.handle,
                'body_html': product.body_html or '',
                'vendor': product.vendor,
                'product_type': product.product_type,
                'sku': product.variants[0].sku if product.variants else '',
                'price': str(product.variants[0].price) if product.variants else '',
                'images': images,
                'image_count': len(images),
                'tags': product.tags,
                'status': product.status,
                # SEO metafields
                'meta_title': meta_dict.get('global.title_tag', ''),
                'meta_description': meta_dict.get('global.description_tag', ''),
                'short_description': meta_dict.get('standard.product_description', ''),
                'compatible_vehicles': meta_dict.get('custom.custom_compatible_vehicles', ''),
                'resumen': meta_dict.get('custom.resumen', ''),
                'metafields': meta_dict,
                # Vehicle fitments from metaobjects
                'vehicle_fitments': self._get_vehicle_fitments_from_metafield(meta_dict.get('custom.vehiculo_fitment'))
            }
            
            # Store in cache
            _product_cache.set(cache_key, result)
            print(f"[Shopify] Cached product {shopify_id} (TTL: 5 min)")
            
            return result
        except Exception as e:
            print(f"Error fetching product {shopify_id}: {e}")
            return None
    
    def _extract_filename(self, url):
        if url:
            return url.split('/')[-1].split('?')[0]
        return ''
    
    def _get_vehicle_fitments_from_metafield(self, metafield_value):
        """Fetch vehicle fitment metaobjects from the metafield reference list"""
        if not metafield_value:
            return []
        
        try:
            import json
            # Parse the metafield value - it's a JSON array of metaobject GIDs
            metaobject_ids = json.loads(metafield_value)
            if not isinstance(metaobject_ids, list):
                metaobject_ids = [metaobject_ids]
            
            print(f"[Shopify] Fetching {len(metaobject_ids)} vehicle fitment metaobjects...")
            
            fitments = []
            for idx, gid in enumerate(metaobject_ids):
                # Use GraphQL to fetch each metaobject
                query = """
                query GetMetaobject($id: ID!) {
                    metaobject(id: $id) {
                        id
                        fields {
                            key
                            value
                        }
                    }
                }
                """
                
                result = self._graphql_request(query, {"id": gid})
                
                if 'errors' in result:
                    print(f"[Shopify] Error fetching metaobject: {result['errors']}")
                    continue
                
                metaobject = result.get('data', {}).get('metaobject')
                if not metaobject:
                    continue
                
                # Parse the fields into our fitment format
                fields = {}
                for field in metaobject.get('fields', []):
                    fields[field['key']] = field['value']
                
                # Parse JSON values (make and model are lists)
                def parse_json_field(val):
                    if val:
                        try:
                            return json.loads(val)
                        except:
                            return val
                    return val
                
                fitment = {
                    'id': idx + 1,
                    'make': parse_json_field(fields.get('make', [])),
                    'modelo': parse_json_field(fields.get('model', [])),
                    'year_start': int(fields.get('ano_inicial', 0)) if fields.get('ano_inicial') else None,
                    'year_end': int(fields.get('ano_final', 0)) if fields.get('ano_final') else None,
                    'transmission_type': fields.get('transmission_type', ''),
                    'transmission_model': fields.get('transmission_model', ''),
                    'engine': fields.get('engine', '')
                }
                fitments.append(fitment)
            
            print(f"[Shopify] Loaded {len(fitments)} vehicle fitments")
            return fitments
            
        except Exception as e:
            import traceback
            print(f"[Shopify] Error loading vehicle fitments: {e}")
            traceback.print_exc()
            return []
    
    def _graphql_request(self, query, variables=None):
        """Execute a GraphQL request to Shopify Admin API"""
        import requests
        
        url = f"https://{settings.SHOPIFY_STORE}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN
        }
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def create_vehicle_fitment_metaobject(self, fitment_data):
        """Create a vehicle fitment metaobject entry"""
        if not self._ensure_initialized():
            return None
        
        # Log incoming data for debugging
        print(f"[Shopify] Creating metaobject with data: {fitment_data}")
        
        # Build the fields for the metaobject
        # Based on the user's metaobject structure: Make, Modelo, Año Inicial, Año Final, Transmission Type, Transmission Model, Engine
        import json
        
        fields = []
        
        # Make (list of strings)
        make_value = fitment_data.get('make', [])
        if make_value:
            fields.append({"key": "make", "value": json.dumps(make_value) if isinstance(make_value, list) else json.dumps([make_value])})
        
        # Model (list of strings) - Shopify key is 'model', our frontend uses 'modelo'
        model_value = fitment_data.get('modelo', [])
        if model_value:
            fields.append({"key": "model", "value": json.dumps(model_value) if isinstance(model_value, list) else json.dumps([model_value])})
        
        # Year fields (integers)
        if fitment_data.get('year_start'):
            fields.append({"key": "ano_inicial", "value": str(fitment_data['year_start'])})
        if fitment_data.get('year_end'):
            fields.append({"key": "ano_final", "value": str(fitment_data['year_end'])})
        
        # Transmission model (string) - e.g. "09G", "68RFE"
        trans_model = fitment_data.get('transmission_model', '')
        if trans_model:
            fields.append({"key": "transmission_model", "value": trans_model})
        
        # Engine (string)
        engine = fitment_data.get('engine', '')
        if engine:
            fields.append({"key": "engine", "value": engine})
        
        print(f"[Shopify] Metaobject fields to create: {fields}")
        
        mutation = """
        mutation CreateMetaobject($metaobject: MetaobjectCreateInput!) {
            metaobjectCreate(metaobject: $metaobject) {
                metaobject {
                    id
                    handle
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "metaobject": {
                "type": "vehicle_fitment",
                "capabilities": {
                    "publishable": {
                        "status": "ACTIVE"
                    }
                },
                "fields": fields
            }
        }
        
        result = self._graphql_request(mutation, variables)
        print(f"[Shopify] Metaobject creation result: {result}")
        
        if 'data' in result and result['data']['metaobjectCreate']['metaobject']:
            return result['data']['metaobjectCreate']['metaobject']['id']
        
        if 'data' in result and result['data']['metaobjectCreate']['userErrors']:
            print(f"[Shopify] Metaobject errors: {result['data']['metaobjectCreate']['userErrors']}")
        
        return None
    
    def save_vehicle_fitments_to_metaobjects(self, product_shopify_id, fitments):
        """Save all vehicle fitments as metaobjects and link to product"""
        if not self._ensure_initialized():
            return False
        
        created_ids = []
        
        # Create metaobject entries for each fitment
        for fitment in fitments:
            metaobject_id = self.create_vehicle_fitment_metaobject(fitment)
            if metaobject_id:
                created_ids.append(metaobject_id)
        
        print(f"[Shopify] Created {len(created_ids)} metaobject entries")
        
        if not created_ids:
            return False
        
        # Link ALL metaobjects to the product via metafield
        # For a list of metaobject references, we pass a JSON array of GIDs
        import json
        
        mutation = """
        mutation UpdateProductMetafield($input: ProductInput!) {
            productUpdate(input: $input) {
                product {
                    id
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "id": f"gid://shopify/Product/{product_shopify_id}",
                "metafields": [
                    {
                        "namespace": "custom",
                        "key": "vehiculo_fitment",
                        "value": json.dumps(created_ids),  # All metaobject IDs as JSON array
                        "type": "list.metaobject_reference"
                    }
                ]
            }
        }
        
        result = self._graphql_request(mutation, variables)
        print(f"[Shopify] Product metafield update result: {result}")
        
        if 'data' in result and result['data']['productUpdate']['userErrors']:
            errors = result['data']['productUpdate']['userErrors']
            if errors:
                print(f"[Shopify] Product update errors: {errors}")
                return False
        
        # Invalidate cache after updating fitments
        _product_cache.invalidate(f"product:{product_shopify_id}")
        print(f"[Shopify] Successfully linked {len(created_ids)} fitments to product (cache invalidated)")
        return True

    def update_product_seo_metafields(self, product_id: str, metafields: dict) -> bool:
        """
        Write SEO metafields to a product so the theme's structured-data.liquid
        can read them into Product JSON-LD.

        Supported keys (all optional, only emit those provided):
        - oem_number: Manufacturer part number → schema.org/mpn
        - transmission_code: Primary transmission code → schema.org/additionalProperty (legacy single value)
        - transmission_codes: Full cross-reference list (Phase 1.2) → multiple schema.org/additionalProperty entries

        Returns True on success, False otherwise.
        """
        if not self._ensure_initialized():
            return False

        metafields_input = []
        if metafields.get('oem_number'):
            metafields_input.append({
                "namespace": "custom",
                "key": "oem_number",
                "value": str(metafields['oem_number']).strip(),
                "type": "single_line_text_field"
            })
        if metafields.get('transmission_code'):
            metafields_input.append({
                "namespace": "custom",
                "key": "transmission_code",
                "value": str(metafields['transmission_code']).strip().upper(),
                "type": "single_line_text_field"
            })
        # Phase 1.2 (May 20 2026): full cross-reference list. List-type metafield
        # with JSON-encoded string array per Shopify Admin API conventions.
        codes_list = metafields.get('transmission_codes')
        if codes_list and isinstance(codes_list, list):
            normalized = [str(c).strip().upper() for c in codes_list if c]
            if normalized:
                import json as _json
                metafields_input.append({
                    "namespace": "custom",
                    "key": "transmission_codes",
                    "value": _json.dumps(normalized),
                    "type": "list.single_line_text_field"
                })
        # Phase 2.1: AEO TL;DR summary — emitted by the theme as
        # schema.org/disambiguatingDescription in Product JSON-LD.
        tldr = metafields.get('product_tldr_summary')
        if tldr and isinstance(tldr, str):
            cleaned = tldr.strip()
            if cleaned:
                metafields_input.append({
                    "namespace": "custom",
                    "key": "product_tldr_summary",
                    "value": cleaned,
                    "type": "multi_line_text_field"
                })
        # Phase 2.5: rebuild_tier classified from vendor + product_type by
        # rebuild_tier.classify_rebuild_tier. Single Spanish tier label
        # ("Servicio", "Profesional", "OE Premium", etc.) emitted by the
        # theme as additionalProperty name="Rebuild Tier" — gives LLMs the
        # explicit repair-intent signal ChatGPT's framework names.
        tier = metafields.get('rebuild_tier')
        if tier and isinstance(tier, str):
            tier_clean = tier.strip()
            if tier_clean:
                metafields_input.append({
                    "namespace": "custom",
                    "key": "rebuild_tier",
                    "value": tier_clean,
                    "type": "single_line_text_field"
                })

        # Phase 2.4: FAQs generated alongside the TL;DR by
        # product_enrichment_service. Stored as JSON metafield; theme emits
        # as a standalone FAQPage <script> JSON-LD block.
        faqs = metafields.get('product_faqs')
        if faqs and isinstance(faqs, list):
            faq_list = []
            for f in faqs:
                if not isinstance(f, dict):
                    continue
                q = (f.get('q') or '').strip()
                a = (f.get('a') or '').strip()
                if q and a:
                    faq_list.append({'q': q, 'a': a})
            if faq_list:
                import json as _json
                metafields_input.append({
                    "namespace": "custom",
                    "key": "product_faqs",
                    "value": _json.dumps(faq_list, ensure_ascii=False),
                    "type": "json"
                })
        # Phase 2.3: OEM cross-reference list. extract_oem_references_from_html
        # already returns the full list; previously only [0] was stored as the
        # single oem_number (→ mpn). Multi-OEM is emitted as additionalProperty
        # entries by the theme. Keeps the legacy single oem_number write intact.
        oem_list = metafields.get('oem_numbers')
        if oem_list and isinstance(oem_list, list):
            cleaned = [str(o).strip() for o in oem_list if o and str(o).strip()]
            # Dedupe preserving order
            seen = set()
            unique_oems = []
            for o in cleaned:
                if o not in seen:
                    seen.add(o)
                    unique_oems.append(o)
            if unique_oems:
                import json as _json
                metafields_input.append({
                    "namespace": "custom",
                    "key": "oem_numbers",
                    "value": _json.dumps(unique_oems),
                    "type": "list.single_line_text_field"
                })

        # Phase 2.2: co-purchase / related products — Shopify list.product_reference
        # metafield. Theme emits each as schema.org/isRelatedTo. Accepts either
        # bare Shopify product IDs (numeric string or int) or full GIDs; we
        # normalize to GID format here.
        related = metafields.get('related_products')
        if related and isinstance(related, list):
            gids: list = []
            for r in related:
                if r is None:
                    continue
                if isinstance(r, str) and r.startswith('gid://shopify/Product/'):
                    gids.append(r)
                else:
                    bare = str(r).strip()
                    if bare.isdigit():
                        gids.append(f"gid://shopify/Product/{bare}")
            if gids:
                import json as _json
                metafields_input.append({
                    "namespace": "custom",
                    "key": "related_products",
                    "value": _json.dumps(gids),
                    "type": "list.product_reference"
                })

        if not metafields_input:
            return True

        mutation = """
        mutation UpdateProductSEOMetafields($input: ProductInput!) {
            productUpdate(input: $input) {
                product { id }
                userErrors { field message }
            }
        }
        """
        variables = {
            "input": {
                "id": f"gid://shopify/Product/{product_id}",
                "metafields": metafields_input
            }
        }
        result = self._graphql_request(mutation, variables)

        if 'errors' in result:
            print(f"[Shopify] SEO metafield GraphQL error: {result['errors']}")
            return False
        user_errors = result.get('data', {}).get('productUpdate', {}).get('userErrors', [])
        if user_errors:
            print(f"[Shopify] SEO metafield user errors: {user_errors}")
            return False

        _product_cache.invalidate(f"product:{product_id}")
        keys = [m['key'] for m in metafields_input]
        print(f"[Shopify] Updated SEO metafields {keys} for product {product_id}")
        return True

    def activate_draft_vehicle_fitments(self, batch_size=25):
        """Activate all DRAFT vehicle_fitment metaobjects. Returns count activated."""
        if not self._ensure_initialized():
            return {"error": "Shopify not initialized", "activated": 0}

        # Step 1: Fetch all draft vehicle_fitment metaobjects
        draft_ids = []
        cursor = None
        page = 0

        while True:
            page += 1
            after_clause = f', after: "{cursor}"' if cursor else ''
            query = f"""
            {{
                metaobjects(type: "vehicle_fitment", first: 250{after_clause}) {{
                    edges {{
                        node {{
                            id
                            capabilities {{
                                publishable {{
                                    status
                                }}
                            }}
                        }}
                        cursor
                    }}
                    pageInfo {{
                        hasNextPage
                    }}
                }}
            }}
            """
            result = self._graphql_request(query)

            if 'data' not in result or not result['data']['metaobjects']['edges']:
                break

            edges = result['data']['metaobjects']['edges']
            for edge in edges:
                status = edge['node']['capabilities']['publishable']['status']
                if status == 'DRAFT':
                    draft_ids.append(edge['node']['id'])
                cursor = edge['cursor']

            print(f"[Shopify] Page {page}: found {len(draft_ids)} draft fitments so far...")

            if not result['data']['metaobjects']['pageInfo']['hasNextPage']:
                break

        print(f"[Shopify] Total DRAFT vehicle_fitment entries: {len(draft_ids)}")

        if not draft_ids:
            return {"activated": 0, "message": "No draft entries found"}

        # Step 2: Activate in batches
        activated = 0
        errors = []

        for i in range(0, len(draft_ids), batch_size):
            batch = draft_ids[i:i + batch_size]
            for metaobject_id in batch:
                mutation = """
                mutation ActivateMetaobject($id: ID!, $metaobject: MetaobjectUpdateInput!) {
                    metaobjectUpdate(id: $id, metaobject: $metaobject) {
                        metaobject {
                            id
                            capabilities {
                                publishable {
                                    status
                                }
                            }
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """
                variables = {
                    "id": metaobject_id,
                    "metaobject": {
                        "capabilities": {
                            "publishable": {
                                "status": "ACTIVE"
                            }
                        }
                    }
                }
                result = self._graphql_request(mutation, variables)

                if 'data' in result and result['data']['metaobjectUpdate']['metaobject']:
                    activated += 1
                else:
                    user_errors = result.get('data', {}).get('metaobjectUpdate', {}).get('userErrors', [])
                    errors.append({"id": metaobject_id, "errors": user_errors})

            print(f"[Shopify] Activated {activated}/{len(draft_ids)} fitments...")
            time.sleep(0.5)  # Rate limit buffer

        result = {
            "total_draft": len(draft_ids),
            "activated": activated,
            "errors": errors[:10] if errors else []
        }
        print(f"[Shopify] Activation complete: {result}")
        return result

    def get_products_needing_seo(self):
        products = self.get_all_products()
        needs_seo = []
        
        for product in products:
            desc_length = len(product.body_html or '')
            has_structure = self._has_seo_structure(product.body_html)
            
            if desc_length < 200 or not has_structure:
                needs_seo.append({
                    'id': product.id,
                    'title': product.title,
                    'handle': product.handle,
                    'sku': product.variants[0].sku if product.variants else '',
                    'description_length': desc_length,
                    'needs_structure': not has_structure
                })
        
        return needs_seo
    
    def _has_seo_structure(self, html):
        """
        Smarter SEO structure detection using a scoring system.
        Returns True if the description is well-optimized (score >= 60).
        
        Scoring breakdown:
        - Length: 0-30 points (based on character count)
        - Headings (h1-h3): 0-20 points
        - Lists (ul/ol): 0-15 points
        - Links: 0-10 points
        - Paragraphs: 0-10 points
        - Bold/emphasis: 0-5 points
        - Tables: 0-10 points
        
        Total possible: 100 points
        Threshold for "optimized": 60 points
        """
        if not html:
            return False
        
        score = 0
        html_lower = html.lower()
        
        # Length scoring (0-30 points)
        length = len(html)
        if length >= 1500:
            score += 30
        elif length >= 1000:
            score += 25
        elif length >= 500:
            score += 20
        elif length >= 300:
            score += 15
        elif length >= 150:
            score += 10
        elif length >= 50:
            score += 5
        
        # Headings scoring (0-20 points)
        has_h1 = '<h1>' in html_lower or '<h1 ' in html_lower
        has_h2 = '<h2>' in html_lower or '<h2 ' in html_lower
        has_h3 = '<h3>' in html_lower or '<h3 ' in html_lower
        heading_count = sum([has_h1, has_h2, has_h3])
        score += min(heading_count * 7, 20)
        
        # Lists scoring (0-15 points)
        has_ul = '<ul>' in html_lower or '<ul ' in html_lower
        has_ol = '<ol>' in html_lower or '<ol ' in html_lower
        if has_ul or has_ol:
            # Count list items for bonus
            li_count = html_lower.count('<li>')
            if li_count >= 5:
                score += 15
            elif li_count >= 3:
                score += 12
            elif li_count >= 1:
                score += 8
        
        # Links scoring (0-10 points)
        link_count = html_lower.count('<a href')
        if link_count >= 3:
            score += 10
        elif link_count >= 1:
            score += 5
        
        # Paragraphs scoring (0-10 points)
        p_count = html_lower.count('<p>')
        if p_count >= 3:
            score += 10
        elif p_count >= 1:
            score += 5
        
        # Bold/emphasis scoring (0-5 points)
        has_bold = '<strong>' in html_lower or '<b>' in html_lower
        has_emphasis = '<em>' in html_lower or '<i>' in html_lower
        if has_bold:
            score += 3
        if has_emphasis:
            score += 2
        
        # Tables scoring (0-10 points) - indicates technical specs
        if '<table>' in html_lower or '<table ' in html_lower:
            score += 10
        
        # Return True if score meets threshold (well optimized)
        return score >= 60
    
    def get_seo_score(self, html):
        """
        Get the actual SEO score (0-100) for a product description.
        Useful for displaying in the UI.
        """
        if not html:
            return 0
        
        score = 0
        html_lower = html.lower()
        
        # Length scoring (0-30 points)
        length = len(html)
        if length >= 1500:
            score += 30
        elif length >= 1000:
            score += 25
        elif length >= 500:
            score += 20
        elif length >= 300:
            score += 15
        elif length >= 150:
            score += 10
        elif length >= 50:
            score += 5
        
        # Headings scoring (0-20 points)
        has_h1 = '<h1>' in html_lower or '<h1 ' in html_lower
        has_h2 = '<h2>' in html_lower or '<h2 ' in html_lower
        has_h3 = '<h3>' in html_lower or '<h3 ' in html_lower
        heading_count = sum([has_h1, has_h2, has_h3])
        score += min(heading_count * 7, 20)
        
        # Lists scoring (0-15 points)
        has_ul = '<ul>' in html_lower or '<ul ' in html_lower
        has_ol = '<ol>' in html_lower or '<ol ' in html_lower
        if has_ul or has_ol:
            li_count = html_lower.count('<li>')
            if li_count >= 5:
                score += 15
            elif li_count >= 3:
                score += 12
            elif li_count >= 1:
                score += 8
        
        # Links scoring (0-10 points)
        link_count = html_lower.count('<a href')
        if link_count >= 3:
            score += 10
        elif link_count >= 1:
            score += 5
        
        # Paragraphs scoring (0-10 points)
        p_count = html_lower.count('<p>')
        if p_count >= 3:
            score += 10
        elif p_count >= 1:
            score += 5
        
        # Bold/emphasis scoring (0-5 points)
        has_bold = '<strong>' in html_lower or '<b>' in html_lower
        has_emphasis = '<em>' in html_lower or '<i>' in html_lower
        if has_bold:
            score += 3
        if has_emphasis:
            score += 2
        
        # Tables scoring (0-10 points)
        if '<table>' in html_lower or '<table ' in html_lower:
            score += 10
        
        return min(score, 100)
    
    def get_single_product_sales(self, shopify_id: str) -> Dict[str, Any]:
        """
        Fetch sales data for a single product across 30d/90d/365d periods.
        Uses Shopify GraphQL with product_id filter for speed.
        Returns: {'30d': {total_sold, total_revenue}, '90d': {...}, '365d': {...}}
        """
        if not self._ensure_initialized():
            return {}

        from datetime import datetime, timedelta

        now = datetime.now()
        cutoffs = {
            '30d': (now - timedelta(days=30)).strftime('%Y-%m-%d'),
            '90d': (now - timedelta(days=90)).strftime('%Y-%m-%d'),
            '365d': (now - timedelta(days=365)).strftime('%Y-%m-%d'),
        }

        # Fetch orders from last 365d that contain this product
        # Shopify GraphQL doesn't support filtering orders by product_id directly,
        # so we fetch recent orders and filter client-side. We use a limited window.
        start_date = cutoffs['365d']
        result_periods = {k: {'total_sold': 0, 'total_revenue': 0.0} for k in cutoffs}
        cursor = None

        while True:
            after_clause = f', after: "{cursor}"' if cursor else ''
            query = f"""
            {{
                orders(first: 100, sortKey: CREATED_AT, query: "created_at:>={start_date}"{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            createdAt
                            lineItems(first: 50) {{
                                edges {{
                                    node {{
                                        quantity
                                        product {{ legacyResourceId }}
                                        variant {{ price }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{ hasNextPage }}
                }}
            }}
            """
            resp = self._graphql_request(query)
            if 'errors' in resp:
                break

            orders = resp.get('data', {}).get('orders', {}).get('edges', [])
            if not orders:
                break

            for edge in orders:
                cursor = edge['cursor']
                order = edge['node']
                order_date = order.get('createdAt', '')[:10]

                for li_edge in order.get('lineItems', {}).get('edges', []):
                    li = li_edge['node']
                    product = li.get('product')
                    if not product or product.get('legacyResourceId') != str(shopify_id):
                        continue

                    qty = li.get('quantity', 0)
                    variant = li.get('variant')
                    price = float(variant.get('price', 0) or 0) if variant else 0.0
                    revenue = qty * price

                    for period, cutoff_date in cutoffs.items():
                        if order_date >= cutoff_date:
                            result_periods[period]['total_sold'] += qty
                            result_periods[period]['total_revenue'] += revenue

            if not resp.get('data', {}).get('orders', {}).get('pageInfo', {}).get('hasNextPage'):
                break

        return result_periods

    def get_product_sales_data(self, days: int = 90):
        """Fetch orders from specified days and aggregate sales data per product"""
        if not self._ensure_initialized():
            return {}
        
        # Calculate start date
        from datetime import datetime, timedelta
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        print(f"[Shopify] Fetching product sales data from orders (since {start_date}, {days} days)...")
        
        # Use GraphQL to fetch orders with line items
        sales_data = {}  # product_id -> {total_sold, total_revenue}
        cursor = None
        page = 1
        
        while True:
            # Build cursor query with date filter
            after_clause = f', after: "{cursor}"' if cursor else ''
            
            query = f"""
            {{
                orders(first: 250, sortKey: CREATED_AT, query: "created_at:>={start_date}"{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            id
                            createdAt
                            lineItems(first: 50) {{
                                edges {{
                                    node {{
                                        quantity
                                        product {{
                                            id
                                            legacyResourceId
                                        }}
                                        variant {{
                                            price
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                    }}
                }}
            }}
            """
            
            result = self._graphql_request(query)
            
            if 'errors' in result:
                print(f"[Shopify] GraphQL error: {result['errors']}")
                break
            
            orders = result.get('data', {}).get('orders', {}).get('edges', [])
            
            if not orders:
                break
            
            print(f"[Shopify] Processing orders page {page}...")
            
            for order_edge in orders:
                cursor = order_edge['cursor']
                order = order_edge['node']
                
                for line_item_edge in order.get('lineItems', {}).get('edges', []):
                    line_item = line_item_edge['node']
                    product = line_item.get('product')
                    
                    if not product:
                        continue
                    
                    product_id = product.get('legacyResourceId')
                    if not product_id:
                        continue
                    
                    quantity = line_item.get('quantity', 0)
                    # Safely handle variant that might be None (deleted products)
                    variant = line_item.get('variant')
                    price = float(variant.get('price', 0) or 0) if variant else 0.0
                    revenue = quantity * price
                    
                    if product_id not in sales_data:
                        sales_data[product_id] = {'total_sold': 0, 'total_revenue': 0.0}
                    
                    sales_data[product_id]['total_sold'] += quantity
                    sales_data[product_id]['total_revenue'] += revenue
            
            # Check if there are more pages
            if not result.get('data', {}).get('orders', {}).get('pageInfo', {}).get('hasNextPage'):
                break
            
            page += 1
        
        print(f"[Shopify] Sales data retrieved for {len(sales_data)} products ({days} days)")
        return sales_data
    
    def get_product_sales_all_periods(self):
        """
        Fetch sales data for multiple time periods: 30d, 90d, 365d, and all-time.
        Returns dict with separate aggregations for each period.
        """
        if not self._ensure_initialized():
            return {}
        
        from datetime import datetime, timedelta
        
        # Define time periods
        periods = {
            '30d': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            '90d': (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
            '365d': (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
            'all_time': '2000-01-01'  # Far enough in the past
        }
        
        # Initialize data structure
        # product_id -> { '30d': {...}, '90d': {...}, '365d': {...}, 'all_time': {...} }
        sales_data = {}
        
        print("[Shopify] Fetching sales data for all time periods...")
        
        # Fetch all-time orders (we'll filter them into periods)
        cursor = None
        page = 1
        total_orders = 0
        
        while True:
            after_clause = f', after: "{cursor}"' if cursor else ''
            
            # Fetch orders from last year (covers all our periods)
            query = f"""
            {{
                orders(first: 250, sortKey: CREATED_AT, query: "created_at:>={periods['365d']}"{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            id
                            createdAt
                            lineItems(first: 50) {{
                                edges {{
                                    node {{
                                        quantity
                                        product {{
                                            id
                                            legacyResourceId
                                        }}
                                        variant {{
                                            price
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                    }}
                }}
            }}
            """
            
            result = self._graphql_request(query)
            
            if 'errors' in result:
                print(f"[Shopify] GraphQL error: {result['errors']}")
                break
            
            orders = result.get('data', {}).get('orders', {}).get('edges', [])
            
            if not orders:
                break
            
            print(f"[Shopify] Processing orders page {page}...")
            
            for order_edge in orders:
                cursor = order_edge['cursor']
                order = order_edge['node']
                order_date = order.get('createdAt', '')
                
                total_orders += 1
                
                for line_item_edge in order.get('lineItems', {}).get('edges', []):
                    line_item = line_item_edge['node']
                    product = line_item.get('product')
                    
                    if not product:
                        continue
                    
                    product_id = product.get('legacyResourceId')
                    if not product_id:
                        continue
                    
                    quantity = line_item.get('quantity', 0)
                    variant = line_item.get('variant')
                    price = float(variant.get('price', 0) or 0) if variant else 0.0
                    revenue = quantity * price
                    
                    # Initialize product data if needed
                    if product_id not in sales_data:
                        sales_data[product_id] = {
                            '30d': {'total_sold': 0, 'total_revenue': 0.0},
                            '90d': {'total_sold': 0, 'total_revenue': 0.0},
                            '365d': {'total_sold': 0, 'total_revenue': 0.0},
                            'all_time': {'total_sold': 0, 'total_revenue': 0.0},
                            'last_sold_at': None,  # ISO datetime string of most recent sale
                        }

                    # Track most recent sale date
                    prev_last = sales_data[product_id]['last_sold_at']
                    if order_date and (prev_last is None or order_date > prev_last):
                        sales_data[product_id]['last_sold_at'] = order_date

                    # Add to all_time
                    sales_data[product_id]['all_time']['total_sold'] += quantity
                    sales_data[product_id]['all_time']['total_revenue'] += revenue

                    # Add to 365d (we only fetched 365d orders)
                    sales_data[product_id]['365d']['total_sold'] += quantity
                    sales_data[product_id]['365d']['total_revenue'] += revenue

                    # Check if within 90d
                    if order_date >= periods['90d']:
                        sales_data[product_id]['90d']['total_sold'] += quantity
                        sales_data[product_id]['90d']['total_revenue'] += revenue

                    # Check if within 30d
                    if order_date >= periods['30d']:
                        sales_data[product_id]['30d']['total_sold'] += quantity
                        sales_data[product_id]['30d']['total_revenue'] += revenue
            
            # Check if there are more pages
            if not result.get('data', {}).get('orders', {}).get('pageInfo', {}).get('hasNextPage'):
                break
            
            page += 1
            
            # Safety limit
            if page > 100:
                print("[Shopify] Reached page limit, stopping...")
                break
        
        print(f"[Shopify] Processed {total_orders} orders, sales data for {len(sales_data)} products")
        print(f"[Shopify] Periods: 30d, 90d, 365d, all_time")

        return sales_data

    def fetch_orders_since(self, since_iso: Optional[str] = None, until_iso: Optional[str] = None):
        """
        Yields raw Shopify order line items, optionally filtered by updated_at window.

        Used by the incremental sync pipeline. Each yielded dict represents one line item
        with all the metadata needed to upsert into the order_line_items table.

        Args:
            since_iso: ISO 8601 timestamp. Only fetches orders with updated_at > since_iso.
                       Pass None for the initial backfill (gets all 365 days of orders).
            until_iso: ISO 8601 timestamp. Only fetches orders with updated_at < until_iso.
                       Used to chunk large backfills.

        Yields:
            dict with keys: line_item_id, order_id, order_name, shopify_product_id,
                shopify_variant_id, sku, title, quantity, current_quantity, unit_price,
                revenue, is_refunded, is_cancelled, cancelled_at, order_created_at,
                order_updated_at
        """
        if not self._ensure_initialized():
            return

        from datetime import datetime, timedelta

        # Build the GraphQL query filter string
        filters = []
        if since_iso:
            filters.append(f"updated_at:>'{since_iso}'")
        else:
            # No since: default to last 365 days for the backfill case
            cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            filters.append(f"updated_at:>={cutoff}")

        if until_iso:
            filters.append(f"updated_at:<'{until_iso}'")

        query_filter = " AND ".join(filters)
        print(f"[Shopify] fetch_orders_since: {query_filter}")

        cursor = None
        page = 0
        total_orders = 0
        total_line_items = 0

        while True:
            page += 1
            after_clause = f', after: "{cursor}"' if cursor else ''
            query = f"""
            {{
                orders(first: 100, sortKey: UPDATED_AT, query: "{query_filter}"{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            id
                            name
                            createdAt
                            updatedAt
                            cancelledAt
                            displayFinancialStatus
                            lineItems(first: 100) {{
                                edges {{
                                    node {{
                                        id
                                        sku
                                        title
                                        quantity
                                        currentQuantity
                                        product {{
                                            id
                                            legacyResourceId
                                        }}
                                        variant {{
                                            id
                                            price
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                    }}
                }}
            }}
            """

            result = self._graphql_request(query)
            if 'errors' in result:
                print(f"[Shopify] fetch_orders_since GraphQL error: {result['errors']}")
                break

            orders = result.get('data', {}).get('orders', {}).get('edges', [])
            if not orders:
                break

            for order_edge in orders:
                cursor = order_edge['cursor']
                order = order_edge['node']
                total_orders += 1

                order_id = order.get('id', '').split('/')[-1]  # gid://shopify/Order/123 -> 123
                order_name = order.get('name')
                order_created = order.get('createdAt')
                order_updated = order.get('updatedAt')
                cancelled_at = order.get('cancelledAt')
                is_cancelled = bool(cancelled_at)
                fin_status = (order.get('displayFinancialStatus') or '').upper()
                # REFUNDED / PARTIALLY_REFUNDED → at least some line items refunded.
                # We mark the whole-order is_refunded for now; granular per-line refund
                # tracking can come later via the refunds{} field.
                is_refunded = fin_status in ('REFUNDED', 'PARTIALLY_REFUNDED')

                for li_edge in order.get('lineItems', {}).get('edges', []):
                    li = li_edge['node']
                    product = li.get('product')
                    if not product:
                        continue
                    shopify_product_id = product.get('legacyResourceId')
                    if not shopify_product_id:
                        continue

                    variant = li.get('variant') or {}
                    line_item_id = (li.get('id') or '').split('/')[-1]
                    quantity = li.get('quantity') or 0
                    current_quantity = li.get('currentQuantity')
                    if current_quantity is None:
                        current_quantity = quantity
                    try:
                        unit_price = float(variant.get('price') or 0)
                    except (ValueError, TypeError):
                        unit_price = 0.0
                    revenue = current_quantity * unit_price

                    total_line_items += 1
                    yield {
                        'line_item_id': line_item_id,
                        'order_id': str(order_id),
                        'order_name': order_name,
                        'shopify_product_id': str(shopify_product_id),
                        'shopify_variant_id': (variant.get('id') or '').split('/')[-1] or None,
                        'sku': li.get('sku'),
                        'title': li.get('title'),
                        'quantity': quantity,
                        'current_quantity': current_quantity,
                        'unit_price': unit_price,
                        'revenue': revenue,
                        'is_refunded': is_refunded,
                        'is_cancelled': is_cancelled,
                        'cancelled_at': cancelled_at,
                        'order_created_at': order_created,
                        'order_updated_at': order_updated,
                    }

            if page % 10 == 0:
                print(f"[Shopify] fetch_orders_since page {page}: {total_orders} orders, {total_line_items} line items so far")

            if not result.get('data', {}).get('orders', {}).get('pageInfo', {}).get('hasNextPage'):
                break

            if page > 500:  # Safety: ~50,000 orders
                print(f"[Shopify] fetch_orders_since: page limit reached at {page}")
                break

        print(f"[Shopify] fetch_orders_since complete: {total_orders} orders, {total_line_items} line items across {page} pages")

    def get_co_purchase_data(self, days: int = 90) -> dict:
        """
        Analyze co-purchase patterns from Shopify orders.
        For each order with 2+ products, records which products are bought together.

        Returns:
            {
                product_id: {
                    "co_purchase_count": int,       # Orders where this product was bought with others
                    "solo_purchase_count": int,      # Orders where bought alone
                    "avg_cart_companions": float,     # Avg other products in same cart
                    "avg_cart_total": float,          # Avg total cart value when this product is in it
                    "companions": {companion_id: count, ...},  # How often each companion appears
                }
            }
        """
        if not self._ensure_initialized():
            return {}

        from datetime import datetime, timedelta
        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Collect all orders with their line items
        orders_items = []  # List of [{product_id, price, quantity}, ...]
        cursor = None
        page = 1

        while True:
            after_clause = f', after: "{cursor}"' if cursor else ''
            query = f"""
            {{
                orders(first: 250, sortKey: CREATED_AT, query: "created_at:>={since_date}"{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            lineItems(first: 50) {{
                                edges {{
                                    node {{
                                        quantity
                                        product {{
                                            legacyResourceId
                                        }}
                                        variant {{
                                            price
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                    pageInfo {{ hasNextPage }}
                }}
            }}
            """

            result = self._graphql_request(query)
            if 'errors' in result:
                print(f"[Shopify] Co-purchase GraphQL error: {result['errors']}")
                break

            edges = result.get('data', {}).get('orders', {}).get('edges', [])
            if not edges:
                break

            for order_edge in edges:
                cursor = order_edge['cursor']
                items = []
                for li_edge in order_edge['node'].get('lineItems', {}).get('edges', []):
                    li = li_edge['node']
                    product = li.get('product')
                    if not product:
                        continue
                    pid = product.get('legacyResourceId')
                    if not pid:
                        continue
                    variant = li.get('variant')
                    price = float(variant.get('price', 0) or 0) if variant else 0.0
                    qty = li.get('quantity', 0)
                    items.append({"product_id": str(pid), "price": price, "quantity": qty})

                if items:
                    orders_items.append(items)

            if not result.get('data', {}).get('orders', {}).get('pageInfo', {}).get('hasNextPage'):
                break
            page += 1
            if page > 100:
                break

        print(f"[Shopify] Co-purchase analysis: {len(orders_items)} orders in {days}d")

        # Analyze co-purchase patterns
        product_stats = {}

        for order_items in orders_items:
            product_ids = list(set(item["product_id"] for item in order_items))
            cart_total = sum(item["price"] * item["quantity"] for item in order_items)
            is_multi = len(product_ids) > 1

            for item in order_items:
                pid = item["product_id"]
                if pid not in product_stats:
                    product_stats[pid] = {
                        "co_purchase_count": 0,
                        "solo_purchase_count": 0,
                        "cart_totals": [],
                        "cart_companion_counts": [],
                        "companions": {},
                    }

                if is_multi:
                    product_stats[pid]["co_purchase_count"] += 1
                    product_stats[pid]["cart_companion_counts"].append(len(product_ids) - 1)
                    product_stats[pid]["cart_totals"].append(cart_total)

                    # Record companions
                    for other_id in product_ids:
                        if other_id != pid:
                            product_stats[pid]["companions"][other_id] = \
                                product_stats[pid]["companions"].get(other_id, 0) + 1
                else:
                    product_stats[pid]["solo_purchase_count"] += 1

        # Summarize
        result_data = {}
        for pid, stats in product_stats.items():
            avg_companions = (
                sum(stats["cart_companion_counts"]) / len(stats["cart_companion_counts"])
                if stats["cart_companion_counts"] else 0.0
            )
            avg_cart_total = (
                sum(stats["cart_totals"]) / len(stats["cart_totals"])
                if stats["cart_totals"] else 0.0
            )

            # Top 10 companions sorted by frequency
            sorted_companions = sorted(
                stats["companions"].items(), key=lambda x: x[1], reverse=True
            )[:10]

            result_data[pid] = {
                "co_purchase_count": stats["co_purchase_count"],
                "solo_purchase_count": stats["solo_purchase_count"],
                "avg_cart_companions": round(avg_companions, 2),
                "avg_cart_total": round(avg_cart_total, 2),
                "companions": dict(sorted_companions),
            }

        co_purchase_products = sum(1 for v in result_data.values() if v["co_purchase_count"] > 0)
        print(f"[Shopify] Co-purchase: {co_purchase_products} products appear in multi-item orders")

        return result_data

    # ============ LLM Sales Attribution Methods (Orders API) ============
    # Note: ShopifyQL was sunset in API version 2024-07
    # Using Orders API with landingPageUrl for LLM attribution

    
    def get_llm_attributed_sales(self, days: int = 365, compare: bool = True) -> dict:
        """
        Fetch sales attributed to LLM sources via UTM tracking.
        
        Uses GraphQL to query orders, then filters by landing page URL 
        or referrer containing LLM identifiers.
        
        Args:
            days: Number of days to look back (default 365)
            compare: Include comparison to previous period
            
        Returns:
            LLMSalesReport dict with summary, by_source breakdown, and comparison
        """
        cache_key = f"llm_sales:{days}:{compare}"
        cached = _llm_sales_cache.get(cache_key)
        if cached:
            print(f"[Shopify] LLM sales cache HIT")
            return cached
        
        print(f"[Shopify] Fetching LLM attributed sales for last {days} days...")
        
        from datetime import datetime, timedelta
        
        # Calculate date ranges
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        prev_start = start_date - timedelta(days=days)
        prev_end = start_date
        
        # Fetch current period orders
        current_orders = self._fetch_orders_with_utm(start_date, end_date)
        
        # Fetch previous period if comparison requested
        prev_orders = []
        if compare:
            prev_orders = self._fetch_orders_with_utm(prev_start, prev_end)
        
        # Aggregate sales by LLM source
        current_stats = self._aggregate_llm_sales(current_orders)
        prev_stats = self._aggregate_llm_sales(prev_orders) if compare else None
        
        # Build response
        result = {
            "summary": current_stats["summary"],
            "by_source": current_stats["by_source"],
            "comparison": self._calculate_llm_comparison(current_stats, prev_stats) if compare else None,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
        # Cache result
        _llm_sales_cache.set(cache_key, result)
        print(f"[Shopify] LLM sales cached - {current_stats['summary']['total_orders']} orders from LLM sources")
        return result
    
    def _fetch_orders_with_utm(self, start_date, end_date) -> list:
        """
        Fetch orders with landing page and customer data via GraphQL.
        """
        if not self._ensure_initialized():
            return []
        
        from datetime import datetime
        
        orders = []
        cursor = None
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        while True:
            after_clause = f', after: "{cursor}"' if cursor else ''
            
            query = f'''
            {{
                orders(first: 250, query: "created_at:>={start_str} created_at:<={end_str}"{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            id
                            name
                            createdAt
                            totalPriceSet {{ shopMoney {{ amount currencyCode }} }}
                            customer {{
                                id
                                firstName
                                lastName
                            }}
                            customerJourneySummary {{
                                firstVisit {{
                                    landingPage
                                    referrerUrl
                                    source
                                    utmParameters {{
                                        source
                                        medium
                                        campaign
                                        content
                                        term
                                    }}
                                }}
                                lastVisit {{
                                    landingPage
                                    referrerUrl
                                    source
                                }}
                            }}
                            shippingAddress {{
                                country
                                province
                                city
                            }}
                            billingAddress {{
                                country
                                province
                                city
                            }}
                            lineItems(first: 50) {{
                                edges {{
                                    node {{
                                        id
                                        quantity
                                        originalTotalSet {{ shopMoney {{ amount currencyCode }} }}
                                        product {{
                                            id
                                            title
                                            productType
                                        }}
                                    }}
                                }}
                            }}
                            note
                        }}
                    }}
                    pageInfo {{ hasNextPage }}
                }}
            }}
            '''


            
            result = self._graphql_request(query)
            
            if 'errors' in result:
                print(f"[Shopify] GraphQL error in LLM sales: {result['errors']}")
                break
            
            edges = result.get('data', {}).get('orders', {}).get('edges', [])
            if not edges:
                break
            
            for edge in edges:
                cursor = edge['cursor']
                orders.append(edge['node'])
            
            if not result.get('data', {}).get('orders', {}).get('pageInfo', {}).get('hasNextPage'):
                break
        
        print(f"[Shopify] Fetched {len(orders)} orders for period {start_str} to {end_str}")
        return orders
    
    def _identify_llm_source(self, order: dict) -> Optional[str]:
        """
        Identify which LLM source attributed this order.
        
        Uses customerJourneySummary.firstVisit for attribution:
        - referrerUrl: The actual referring page (e.g., chat.openai.com)
        - source: Platform name
        - utmParameters: UTM tracking data
        
        Returns normalized source name or None if not LLM-attributed.
        """
        # Extract attribution data from customerJourneySummary
        journey = order.get('customerJourneySummary') or {}
        first_visit = journey.get('firstVisit') or {}
        last_visit = journey.get('lastVisit') or {}
        
        # Collect referrer URLs (use strict domain matching)
        referrer_url = (first_visit.get('referrerUrl') or '').lower()
        last_referrer = (last_visit.get('referrerUrl') or '').lower()
        
        # UTM parameters (can use broader patterns)
        utm = first_visit.get('utmParameters') or {}
        utm_source = (utm.get('source') or '').lower()
        utm_medium = (utm.get('medium') or '').lower()
        utm_campaign = (utm.get('campaign') or '').lower()
        
        # Note field (legacy fallback)
        note = (order.get('note') or '').lower()
        
        # Landing page for UTM checking
        landing_page = (first_visit.get('landingPage') or '').lower()
        
        # PRIORITY 1: Check UTM source (most reliable)
        utm_combined = f"{utm_source} {utm_medium} {utm_campaign}"
        for source_name, patterns in LLM_UTM_SOURCES.items():
            for pattern in patterns:
                if pattern in utm_combined:
                    return source_name
        
        # PRIORITY 2: Check referrer URLs with strict patterns
        referrer_combined = f"{referrer_url} {last_referrer}"
        for source_name, patterns in LLM_SOURCE_PATTERNS.items():
            for pattern in patterns:
                if pattern in referrer_combined:
                    return source_name
        
        # PRIORITY 3: Check landing page UTM params (in URL)
        for source_name, patterns in LLM_UTM_SOURCES.items():
            for pattern in patterns:
                if f"utm_source={pattern}" in landing_page:
                    return source_name
        
        # PRIORITY 4: Check note field
        for source_name, patterns in LLM_UTM_SOURCES.items():
            for pattern in patterns:
                if pattern in note:
                    return source_name
        
        return None

    
    def _aggregate_llm_sales(self, orders: list) -> dict:
        """
        Aggregate orders into sales metrics grouped by LLM source.
        Enhanced version with detailed breakdowns.
        """
        from collections import defaultdict
        from datetime import datetime
        
        by_source = defaultdict(lambda: {
            'sales': 0.0,
            'orders': 0,
            'order_details': [],  # Individual order info
            'referrers': defaultdict(int),  # Track actual referrer URLs
        })
        
        # Monthly breakdown
        by_month = defaultdict(lambda: {'sales': 0.0, 'orders': 0})
        
        # All referrer URLs found (for debugging)
        all_referrers = defaultdict(int)
        
        for order in orders:
            # Extract attribution data
            journey = order.get('customerJourneySummary') or {}
            first_visit = journey.get('firstVisit') or {}
            
            referrer_url = first_visit.get('referrerUrl') or ''
            source_name = first_visit.get('source') or ''
            
            # Track all referrers
            if referrer_url:
                all_referrers[referrer_url] += 1
            
            source = self._identify_llm_source(order)
            if not source:
                continue
            
            # Extract monetary values
            total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0) or 0)
            currency = order.get('totalPriceSet', {}).get('shopMoney', {}).get('currencyCode', 'MXN')
            
            # Parse date for monthly breakdown
            created_at = order.get('createdAt', '')
            month_key = created_at[:7] if created_at else 'unknown'  # YYYY-MM
            
            # Aggregate by source
            by_source[source]['sales'] += total
            by_source[source]['orders'] += 1
            
            # Track referrer URL
            if referrer_url:
                by_source[source]['referrers'][referrer_url] += 1
            
            # Store order details (limited to prevent huge responses)
            if len(by_source[source]['order_details']) < 50:
                # Extract UTM parameters
                utm = first_visit.get('utmParameters') or {}
                last_visit = journey.get('lastVisit') or {}
                
                by_source[source]['order_details'].append({
                    'order_id': order.get('id', '').split('/')[-1],
                    'order_name': order.get('name', ''),
                    'amount': round(total, 2),
                    'currency': currency,
                    'created_at': created_at,  # Full timestamp
                    'date': created_at[:10] if created_at else '',
                    'time': created_at[11:19] if len(created_at) > 11 else '',
                    'attribution': {
                        'first_visit': {
                            'referrer_url': referrer_url,
                            'landing_page': first_visit.get('landingPage', ''),
                            'source': source_name,
                            'utm_source': utm.get('source', ''),
                            'utm_medium': utm.get('medium', ''),
                            'utm_campaign': utm.get('campaign', ''),
                        },
                        'last_visit': {
                            'referrer_url': last_visit.get('referrerUrl', ''),
                            'landing_page': last_visit.get('landingPage', ''),
                            'source': last_visit.get('source', ''),
                        }
                    },
                    'note': (order.get('note') or '')[:100],  # Order note (truncated)
                })

            
            # Monthly breakdown
            by_month[month_key]['sales'] += total
            by_month[month_key]['orders'] += 1
        
        # Calculate totals
        total_sales = sum(s['sales'] for s in by_source.values())
        total_orders = sum(s['orders'] for s in by_source.values())
        
        # Build by_source list with percentages and details
        sources_list = []
        for name, stats in sorted(by_source.items(), key=lambda x: x[1]['sales'], reverse=True):
            # Convert referrers dict to sorted list
            top_referrers = sorted(stats['referrers'].items(), key=lambda x: x[1], reverse=True)[:5]
            
            sources_list.append({
                'source': name,
                'sales': round(stats['sales'], 2),
                'orders': stats['orders'],
                'aov': round(stats['sales'] / stats['orders'], 2) if stats['orders'] > 0 else 0,
                'percent_of_total': round((stats['sales'] / total_sales * 100) if total_sales > 0 else 0, 1),
                'top_referrers': [{'url': url, 'count': count} for url, count in top_referrers],
                'orders_detail': stats['order_details'],  # All orders (up to 50)

            })
        
        # Build monthly trend
        monthly_trend = []
        for month, data in sorted(by_month.items()):
            monthly_trend.append({
                'month': month,
                'sales': round(data['sales'], 2),
                'orders': data['orders']
            })
        
        # Top referrers (non-LLM also, for context)
        top_all_referrers = sorted(all_referrers.items(), key=lambda x: x[1], reverse=True)[:20]
        
        return {
            "summary": {
                "total_sales": round(total_sales, 2),
                "total_orders": total_orders,
                "average_order_value": round(total_sales / total_orders, 2) if total_orders > 0 else 0,
                "sources_detected": len(by_source),
            },
            "by_source": sources_list,
            "monthly_trend": monthly_trend,
            "all_referrers_sample": [{'url': url, 'count': count} for url, count in top_all_referrers],
        }


    
    def _calculate_llm_comparison(self, current: dict, previous: dict) -> dict:
        """
        Calculate percentage changes between current and previous period.
        """
        if not previous:
            return {"sales_change_pct": 0, "orders_change_pct": 0, "aov_change_pct": 0}
        
        def pct_change(curr, prev):
            if prev == 0:
                return 100.0 if curr > 0 else 0.0
            return round((curr - prev) / prev * 100, 1)
        
        return {
            "sales_change_pct": pct_change(
                current["summary"]["total_sales"],
                previous["summary"]["total_sales"]
            ),
            "orders_change_pct": pct_change(
                current["summary"]["total_orders"],
                previous["summary"]["total_orders"]
            ),
            "aov_change_pct": pct_change(
                current["summary"]["average_order_value"],
                previous["summary"]["average_order_value"]
            ),
        }

    def get_llm_product_insights(self, days: int = 365) -> dict:
        """
        Analyze products from LLM-attributed orders to understand:
        1. Which products get referenced by LLMs
        2. What content attributes they have (why they succeed)
        3. Similar products that could be optimized
        """
        from collections import defaultdict
        from app.models.product import Product
        from app.models.aeo_models import ChunkApprovalStatus
        from sqlalchemy.orm import Session
        from app.db.session import SessionLocal
        
        # First, get LLM sales data
        llm_sales = self.get_llm_attributed_sales(days=days, compare=False)
        
        if not llm_sales or llm_sales.get("summary", {}).get("total_orders", 0) == 0:
            return {
                "status": "no_data",
                "message": "No LLM-attributed orders found",
                "products_from_llm": [],
                "optimization_opportunities": [],
                "success_patterns": {}
            }
        
        # Collect product IDs from LLM orders
        llm_product_ids = set()
        product_sources = defaultdict(list)  # product_id -> [sources]
        product_orders = defaultdict(lambda: {"count": 0, "revenue": 0})
        
        # Parse line items from orders to get product IDs
        orders = self._fetch_orders_with_products(days)
        print(f"[Product Intelligence] Fetched {len(orders)} total orders from Shopify")
        
        llm_order_count = 0
        for order in orders:
            source = self._identify_llm_source(order)
            if not source:
                continue
            
            llm_order_count += 1
            line_items = order.get('lineItems', {}).get('edges', [])
            print(f"[Product Intelligence] Order {order.get('name', 'N/A')} from {source} has {len(line_items)} line items")
            
            for edge in line_items:
                item = edge.get('node', {})
                product = item.get('product') or {}
                product_id = product.get('id', '')
                
                if product_id:
                    numeric_id = product_id.split('/')[-1]
                    llm_product_ids.add(numeric_id)
                    product_sources[numeric_id].append(source)
                    
                    quantity = int(item.get('quantity', 1))
                    price = float(item.get('originalTotalSet', {}).get('shopMoney', {}).get('amount', 0))
                    
                    product_orders[numeric_id]["count"] += quantity
                    product_orders[numeric_id]["revenue"] += price
                    print(f"[Product Intelligence]   -> Product ID: {numeric_id}, Qty: {quantity}, Price: {price}")
                else:
                    print(f"[Product Intelligence]   -> No product ID in line item: {item}")
        
        print(f"[Product Intelligence] Found {llm_order_count} LLM-attributed orders")
        
        if not llm_product_ids:
            return {
                "status": "no_products",
                "message": "Could not extract products from LLM orders",
                "products_from_llm": [],
                "optimization_opportunities": [],
                "success_patterns": {}
            }
        
        print(f"[Product Intelligence] Found {len(llm_product_ids)} unique products in LLM orders: {list(llm_product_ids)[:10]}...")
        
        # Query product details from database
        db = SessionLocal()
        try:
            # Get products that sold via LLMs
            llm_products = db.query(Product).filter(
                Product.shopify_id.in_(list(llm_product_ids))
            ).all()
            
            print(f"[Product Intelligence] Matched {len(llm_products)} products in local database out of {len(llm_product_ids)} from orders")
            
            # Find which product IDs weren't found in database
            found_ids = {str(p.shopify_id) for p in llm_products}
            missing_ids = llm_product_ids - found_ids
            if missing_ids:
                print(f"[Product Intelligence] {len(missing_ids)} products not in local database: {list(missing_ids)[:10]}...")
            
            # Get approved chunks (transmission codes)
            approved_chunks = {
                status.product_type 
                for status in db.query(ChunkApprovalStatus).filter(ChunkApprovalStatus.approved == True).all()
            }
            
            # Analyze content attributes of successful products
            products_from_llm = []
            total_desc_length = 0
            products_in_llms_txt = 0
            
            for prod in llm_products:
                shopify_id = str(prod.shopify_id)
                
                # Check if product is in an approved chunk (in llms.txt)
                in_llms_txt = prod.transmission_code in approved_chunks
                
                # Analyze content attributes
                desc_length = len(prod.current_description_html or "")
                total_desc_length += desc_length
                if in_llms_txt:
                    products_in_llms_txt += 1
                
                # Get sources for this product
                sources = list(set(product_sources.get(shopify_id, [])))
                order_data = product_orders.get(shopify_id, {"count": 0, "revenue": 0})
                
                products_from_llm.append({
                    "id": str(prod.id),
                    "shopify_id": shopify_id,
                    "title": prod.title,
                    "sku": prod.sku or "",
                    "handle": prod.handle,
                    "product_type": prod.product_type or "",
                    "orders_from_llm": order_data["count"],
                    "revenue_from_llm": round(order_data["revenue"], 2),
                    "sources": sources,
                    "content_attributes": {
                        "description_length": desc_length,
                        "has_aeo_chunks": in_llms_txt,
                        "chunk_count": 1 if in_llms_txt else 0,
                        "in_llms_txt": in_llms_txt,
                        "has_images": (prod.image_count or 0) > 0,
                        "image_count": prod.image_count or 0,
                    }
                })
            
            # Calculate success patterns
            total_products = len(products_from_llm)
            avg_desc_length = total_desc_length / total_products if total_products else 0
            llm_txt_rate = (products_in_llms_txt / total_products * 100) if total_products else 0
            
            success_patterns = {
                "avg_description_length": round(avg_desc_length),
                "products_with_aeo_chunks_pct": round(llm_txt_rate, 1),
                "total_products_referenced": total_products,
                "most_common_sources": self._get_top_sources(product_sources),
            }
            
            print(f"[Product Intelligence] Success patterns: {total_products} products, {products_in_llms_txt} in llms.txt, avg {round(avg_desc_length)} chars")
            
            # Find optimization opportunities
            all_top_sellers = db.query(Product).filter(
                Product.total_sold > 5
            ).order_by(Product.total_sold.desc()).limit(50).all()
            
            opportunities = []
            for prod in all_top_sellers:
                if str(prod.shopify_id) in llm_product_ids:
                    continue
                
                in_llms_txt = prod.transmission_code in approved_chunks
                desc_length = len(prod.current_description_html or "")
                
                issues = []
                if not in_llms_txt:
                    issues.append("Not in llms.txt")
                if desc_length < avg_desc_length * 0.5:
                    issues.append("Short description")
                if (prod.image_count or 0) == 0:
                    issues.append("No images")
                
                if issues:
                    opportunities.append({
                        "id": str(prod.id),
                        "shopify_id": str(prod.shopify_id),
                        "title": prod.title,
                        "sku": prod.sku or "",
                        "handle": prod.handle,
                        "product_type": prod.product_type or "",
                        "total_sold": prod.total_sold,
                        "total_revenue": round(prod.total_revenue or 0, 2),
                        "current_attributes": {
                            "description_length": desc_length,
                            "has_aeo_chunks": in_llms_txt,
                            "chunk_count": 1 if in_llms_txt else 0,
                            "in_llms_txt": in_llms_txt,
                            "has_images": (prod.image_count or 0) > 0,
                            "image_count": prod.image_count or 0,
                        },
                        "issues": issues,
                        "recommendation": self._generate_recommendation(issues),
                    })
            
            opportunities.sort(key=lambda x: x["total_revenue"], reverse=True)
            sorted_products = sorted(products_from_llm, key=lambda x: x["revenue_from_llm"], reverse=True)
            
            print(f"[Product Intelligence] Returning {len(sorted_products)} products from LLM, {len(opportunities[:20])} opportunities")
            
            message = None
            if missing_ids:
                message = f"{len(missing_ids)} products from LLM orders are not in the local database. Run 'Sync Products' to include them."
            
            return {
                "status": "success",
                "message": message,
                "products_from_llm": sorted_products,
                "optimization_opportunities": opportunities[:20],
                "success_patterns": success_patterns,
                "sync_needed": len(missing_ids) > 0,
                "missing_product_count": len(missing_ids),
            }
            
        finally:
            db.close()

    def get_visibility_sales_correlation(self, days: int = 30) -> dict:
        """
        Calculates correlation between AI visibility (mentions) and actual revenue.
        
        This bridges the gap between 'what LLMs say' and 'what customers buy'.
        """
        from datetime import datetime, timedelta
        from sqlalchemy import func, Integer, cast
        from app.db.session import SessionLocal
        from app.models.aeo_models import AIVisibilityResult, PromptPanelItem
        from app.models.product import Product
        from collections import defaultdict

        db = SessionLocal()
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # 1. Fetch Visibility Mentions by Topic
            # Join Visibility results with Prompt items to get the linked topic
            visibility_query = db.query(
                PromptPanelItem.linked_transmission,
                PromptPanelItem.linked_fault_code,
                func.count(AIVisibilityResult.id).label('checks'),
                func.sum(cast(AIVisibilityResult.brand_mentioned, Integer)).label('mentions'),
                func.sum(cast(AIVisibilityResult.url_cited, Integer)).label('citations'),
                func.sum(cast(AIVisibilityResult.competitor_mentioned, Integer)).label('competitor_mentions')
            ).join(
                AIVisibilityResult, PromptPanelItem.id == AIVisibilityResult.prompt_id
            ).filter(
                AIVisibilityResult.checked_at >= start_date
            ).group_by(
                PromptPanelItem.linked_transmission,
                PromptPanelItem.linked_fault_code
            ).all()

            topic_metrics = {}
            for res in visibility_query:
                # Use transmission code if available, otherwise fault code
                raw_topic = res.linked_transmission or res.linked_fault_code
                if not raw_topic:
                    continue
                
                # Normalize topic for matching
                topic = raw_topic.upper().strip()
                
                category = 'transmission' if res.linked_transmission else 'fault_code'
                topic_metrics[topic] = {
                    "topic": topic,
                    "category": category,
                    "mentions": int(res.mentions or 0),
                    "citations": int(res.citations or 0),
                    "competitor_mentions": int(res.competitor_mentions or 0),
                    "checks": int(res.checks or 0),
                    "orders": 0,
                    "revenue": 0.0,
                    "original_name": raw_topic
                }

            # 2. Fetch Sales by Topic (Transmission Code)
            # Fetch orders for the period and identify LLM sources
            orders = self._fetch_orders_with_products(days)
            topic_sales = defaultdict(lambda: {"orders": 0, "revenue": 0.0})

            # Pre-fetch product transmission codes to map efficiently
            # We map Shopify numeric ID to transmission_code
            product_mapping = {}
            all_products = db.query(Product.shopify_id, Product.transmission_code, Product.product_type).all()
            for p in all_products:
                # Store normalized transmission code
                t_code = p.transmission_code.upper().strip() if p.transmission_code else None
                p_type = p.product_type.upper().strip() if p.product_type else None
                product_mapping[str(p.shopify_id)] = (t_code, p_type)

            for order in orders:
                if not self._identify_llm_source(order):
                    continue
                
                line_items = order.get('lineItems', {}).get('edges', [])
                for edge in line_items:
                    item = edge.get('node', {})
                    product = item.get('product') or {}
                    sid_raw = product.get('id', '')
                    if not sid_raw: continue
                    
                    sid = sid_raw.split('/')[-1]
                    
                    if sid in product_mapping:
                        t_code, p_type = product_mapping[sid]
                        # Match sales to topic: prefer transmission code, then product type
                        topic = t_code or p_type
                        if topic:
                            topic_sales[topic]["orders"] += int(item.get('quantity', 1))
                            topic_sales[topic]["revenue"] += float(item.get('originalTotalSet', {}).get('shopMoney', {}).get('amount', 0))

            # 3. Merge Visibility and Sales
            final_topics = []
            total_mentions = 0
            total_revenue = 0.0

            # Add topics that have visibility data
            for topic, metrics in topic_metrics.items():
                sales = topic_sales.get(topic, {"orders": 0, "revenue": 0.0})
                metrics["orders"] = sales["orders"]
                metrics["revenue"] = round(sales["revenue"], 2)
                
                # Calculate Correlation
                mentions = metrics["mentions"]
                metrics["revenue_per_mention"] = round(metrics["revenue"] / mentions, 2) if mentions > 0 else 0
                metrics["visibility_score"] = round((mentions / metrics["checks"] * 100), 1) if metrics["checks"] > 0 else 0
                
                # Assign Status (using dynamic thresholds based on averages would be better, but fixed for now)
                # Star: High Revenue, High Visibility
                if metrics["revenue"] > 500 and metrics["visibility_score"] > 40:
                    metrics["status"] = "star"
                # Underperformer: High Visibility, Low Revenue (Content/Conversion Gap)
                elif metrics["revenue"] < 100 and metrics["visibility_score"] > 40:
                    metrics["status"] = "underperformer" 
                # Potential: Low Visibility, High Revenue (Visibility Gap)
                elif metrics["revenue"] > 300 and metrics["visibility_score"] < 20:
                    metrics["status"] = "potential"
                else:
                    metrics["status"] = "neutral"

                final_topics.append(metrics)
                total_mentions += mentions
                total_revenue += metrics["revenue"]

            # Add extra sales topics that were NOT in visibility tracker (to suggest new prompts)
            for topic, sales in topic_sales.items():
                if topic not in topic_metrics:
                    final_topics.append({
                        "topic": topic,
                        "category": "sales_only",
                        "mentions": 0,
                        "citations": 0,
                        "competitor_mentions": 0,
                        "checks": 0,
                        "orders": sales["orders"],
                        "revenue": round(sales["revenue"], 2),
                        "revenue_per_mention": 0,
                        "visibility_score": 0,
                        "status": "potential",
                        "original_name": topic
                    })
                    total_revenue += sales["revenue"]

            summary = {
                "total_mentions": total_mentions,
                "total_revenue": round(total_revenue, 2),
                "avg_revenue_per_mention": round(total_revenue / total_mentions, 2) if total_mentions > 0 else 0,
                "top_performing_topic": max(final_topics, key=lambda x: x["revenue"])["topic"] if final_topics else None,
                "most_cited_topic": max(final_topics, key=lambda x: x["citations"])["topic"] if any(t["citations"] > 0 for t in final_topics) else None,
            }

            return {
                "status": "success",
                "days": days,
                "summary": summary,
                "topics": sorted(final_topics, key=lambda x: x["revenue"], reverse=True)
            }

        finally:
            db.close()
    
    def _fetch_orders_with_products(self, days: int) -> list:
        """Fetch orders with line item product data."""
        self._ensure_initialized()
        
        from datetime import datetime, timedelta
        
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        
        query = """
        query($cursor: String) {
            orders(first: 100, after: $cursor, query: "created_at:>='%s'") {
                pageInfo { hasNextPage endCursor }
                edges {
                    node {
                        id
                        name
                        createdAt
                        totalPriceSet { shopMoney { amount } }
                        customerJourneySummary {
                            firstVisit {
                                referrerUrl
                                landingPage
                                source
                                utmParameters { source medium campaign }
                            }
                            lastVisit {
                                referrerUrl
                                source
                            }
                        }
                        note
                        lineItems(first: 50) {
                            edges {
                                node {
                                    quantity
                                    originalTotalSet { shopMoney { amount } }
                                    product { id title handle }
                                }
                            }
                        }
                    }
                }
            }
        }
        """ % start_date
        
        orders = []
        cursor = None
        max_pages = 100
        
        for _ in range(max_pages):
            result = self._graphql_request(query, {"cursor": cursor})
            
            # Fix: Access 'data' key properly like _fetch_all_orders does
            orders_data = result.get('data', {}).get('orders', {}) if result else {}
            edges = orders_data.get('edges', [])
            
            if not edges:
                break
            
            for edge in edges:
                orders.append(edge["node"])
            
            page_info = orders_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')
        
        return orders
    
    def _get_top_sources(self, product_sources: dict) -> list:
        """Get most common LLM sources across all products."""
        from collections import Counter
        
        all_sources = []
        for sources in product_sources.values():
            all_sources.extend(sources)
        
        counts = Counter(all_sources)
        return [{"source": s, "count": c} for s, c in counts.most_common(5)]
    
    def _generate_recommendation(self, issues: list) -> str:
        """Generate actionable recommendation based on issues."""
        if "Not in llms.txt" in issues:
            return "Add to llms.txt by creating AEO chunk with product details"
        elif "Short description" in issues:
            return "Expand product description with technical specs and use cases"
        elif "No images" in issues:
            return "Add high-quality product images"
        return "Review and optimize product content"

    # ============ Collection Methods for Collection Optimizer ============

    def get_collections(self) -> list:
        """
        Fetch all collections from Shopify.
        Returns list of collections with id, title, handle.
        """
        if not self._ensure_initialized():
            return []

        print("[Shopify] Fetching collections...")
        
        collections = []
        cursor = None
        page = 1
        
        while True:
            after_clause = f', after: "{cursor}"' if cursor else ''
            
            query = f"""
            {{
                collections(first: 50{after_clause}) {{
                    edges {{
                        cursor
                        node {{
                            id
                            title
                            handle
                            description
                            productsCount {{
                                count
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
            """
            
            result = self._graphql_request(query)
            
            if 'errors' in result:
                print(f"[Shopify] GraphQL error fetching collections: {result['errors']}")
                break
            
            edges = result.get('data', {}).get('collections', {}).get('edges', [])
            
            if not edges:
                break
            
            print(f"[Shopify] Processing collections page {page}...")
            
            for edge in edges:
                node = edge['node']
                collections.append({
                    'id': node['id'].replace('gid://shopify/Collection/', ''),
                    'title': node['title'],
                    'handle': node['handle'],
                    'description': node.get('description', ''),
                    'products_count': node.get('productsCount', {}).get('count', 0)
                })
            
            page_info = result.get('data', {}).get('collections', {}).get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')
            page += 1
        
        print(f"[Shopify] Fetched {len(collections)} collections")
        return collections

    def get_collection_revenue_attribution(self, days: int = 30) -> Dict[str, Dict]:
        """
        Attribute Shopify order revenue to collection landing pages.

        Fetches orders and filters those where the first-touch landing page
        was a /collections/{handle} URL. Returns a dict keyed by handle with
        attributed revenue, order count, and LLM-attributed subset.
        """
        from collections import defaultdict

        orders = self._fetch_orders_with_products(days)

        attribution: Dict[str, Dict] = defaultdict(lambda: {
            'attributed_revenue': 0.0,
            'attributed_orders': 0,
            'llm_revenue': 0.0,
            'llm_orders': 0,
        })

        for order in orders:
            journey = order.get('customerJourneySummary') or {}
            first_visit = journey.get('firstVisit') or {}
            landing_page = (first_visit.get('landingPage') or '').lower()

            if '/collections/' not in landing_page:
                continue

            try:
                handle = landing_page.split('/collections/')[-1].split('?')[0].rstrip('/').split('/')[0]
            except Exception:
                continue

            if not handle:
                continue

            amount = float(
                (order.get('totalPriceSet') or {})
                    .get('shopMoney', {})
                    .get('amount', 0) or 0
            )

            attribution[handle]['attributed_revenue'] += amount
            attribution[handle]['attributed_orders'] += 1

            if self._identify_llm_source(order):
                attribution[handle]['llm_revenue'] += amount
                attribution[handle]['llm_orders'] += 1

        return dict(attribution)

    def update_collection_metafields(self, collection_id: str, metafields: dict) -> bool:
        """
        Update collection metafields in Shopify.
        
        Args:
            collection_id: Shopify collection ID
            metafields: Dict with keys like 'collection_description', 'collection_faq', 'collection_schema'
        
        Returns:
            True if successful, False otherwise
        """
        if not self._ensure_initialized():
            return False
        
        print(f"[Shopify] Updating metafields for collection {collection_id}...")
        
        # Build metafields input
        metafields_input = []
        
        if 'collection_description' in metafields:
            metafields_input.append({
                "namespace": "custom",
                "key": "seo_description",
                "value": metafields['collection_description'],
                "type": "multi_line_text_field"
            })
        
        if 'collection_faq' in metafields:
            import json
            metafields_input.append({
                "namespace": "custom",
                "key": "seo_faq",
                "value": json.dumps(metafields['collection_faq']),
                "type": "json"
            })
        
        if 'collection_schema' in metafields:
            metafields_input.append({
                "namespace": "custom",
                "key": "seo_schema",
                "value": metafields['collection_schema'],
                "type": "multi_line_text_field"
            })
        
        if not metafields_input:
            print("[Shopify] No metafields to update")
            return True
        
        mutation = """
        mutation UpdateCollectionMetafields($input: CollectionInput!) {
            collectionUpdate(input: $input) {
                collection {
                    id
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "id": f"gid://shopify/Collection/{collection_id}",
                "metafields": metafields_input
            }
        }
        
        result = self._graphql_request(mutation, variables)
        
        if 'errors' in result:
            print(f"[Shopify] GraphQL error: {result['errors']}")
            return False
        
        user_errors = result.get('data', {}).get('collectionUpdate', {}).get('userErrors', [])
        if user_errors:
            print(f"[Shopify] User errors: {user_errors}")
            return False
        
        print(f"[Shopify] Successfully updated {len(metafields_input)} metafields for collection {collection_id}")
        return True
    
    def get_abandoned_checkouts(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch abandoned checkouts from Shopify.
        
        Returns list of abandoned carts with:
        - id: checkout ID
        - email: customer email
        - total: cart total
        - line_items: items in cart
        - created_at: when abandoned
        """
        if not self._ensure_initialized():
            return []
        
        try:
            from datetime import datetime, timedelta
            
            # Calculate date range
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Query abandoned checkouts
            # Note: This requires Shopify Plus or specific permissions
            # For now, return empty list but log the attempt
            print(f"[Shopify] Fetching abandoned checkouts since {since_date}...")
            
            # Abandoned checkouts API endpoint
            from app.core.config import settings
            shop_url = settings.SHOPIFY_STORE
            url = f"{shop_url}/admin/api/2024-01/checkouts.json?created_at_min={since_date}T00:00:00Z&status=open"
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                print(f"[Shopify] Error fetching abandoned checkouts: {response.status_code}")
                return []
            
            data = response.json()
            checkouts = data.get('checkouts', [])
            
            results = []
            for checkout in checkouts:
                results.append({
                    'id': checkout.get('id'),
                    'email': checkout.get('email'),
                    'total': float(checkout.get('total_price', 0)),
                    'line_items': [
                        {
                            'product_id': item.get('product_id'),
                            'variant_id': item.get('variant_id'),
                            'quantity': item.get('quantity'),
                            'price': float(item.get('price', 0))
                        }
                        for item in checkout.get('line_items', [])
                    ],
                    'created_at': checkout.get('created_at'),
                    'cart_token': checkout.get('cart_token')
                })
            
            print(f"[Shopify] Found {len(results)} abandoned checkouts")
            return results
            
        except Exception as e:
            print(f"[Shopify] Error fetching abandoned checkouts: {e}")
            return []

    def get_inventory_for_product(self, product_id: str) -> dict:
        """
        Fetch inventory levels for a product using Shopify GraphQL API.
        Returns total quantity across all locations and status.
        """
        try:
            query = """
            query GetProductInventory($id: ID!) {
                product(id: $id) {
                    id
                    variants(first: 50) {
                        edges {
                            node {
                                id
                                sku
                                inventoryQuantity
                                inventoryItem {
                                    id
                                    inventoryLevels(first: 10) {
                                        edges {
                                            node {
                                                quantities(names: ["available"]) {
                                                    name
                                                    quantity
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
            
            variables = {"id": f"gid://shopify/Product/{product_id}"}
            
            # Make GraphQL request
            import requests
            url = f"https://{settings.SHOPIFY_STORE}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
            headers = {
                "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                url,
                json={"query": query, "variables": variables},
                headers=headers
            )
            
            if response.status_code != 200:
                print(f"[Shopify] Error fetching inventory: HTTP {response.status_code}")
                return {"quantity": None, "status": None}
            
            data = response.json()
            
            if data.get("errors"):
                print(f"[Shopify] GraphQL errors: {data['errors']}")
                return {"quantity": None, "status": None}
            
            product_data = data.get("data", {}).get("product", {})
            variants = product_data.get("variants", {}).get("edges", [])
            
            # Get inventory - use FIRST variant only (main product)
            # Products often have multiple variants (sizes, colors), but we want the main one
            total_quantity = 0
            has_inventory = False
            
            if variants:
                # Get the first variant (usually the default/main one)
                first_variant = variants[0].get("node", {})
                variant_sku = first_variant.get("sku", "N/A")
                
                # Try quantities API first
                inventory_item = first_variant.get("inventoryItem", {})
                levels = inventory_item.get("inventoryLevels", {}).get("edges", [])
                
                for level_edge in levels:
                    level = level_edge.get("node", {})
                    quantities = level.get("quantities", [])
                    for q in quantities:
                        if q.get("name") == "available":
                            available_qty = q.get("quantity")
                            if available_qty is not None:
                                total_quantity = available_qty
                                has_inventory = True
                                break
                    if has_inventory:
                        break
                
                # Fall back to inventoryQuantity
                if not has_inventory:
                    quantity = first_variant.get("inventoryQuantity")
                    if quantity is not None:
                        total_quantity = quantity
                        has_inventory = True
                
                print(f"[Shopify] Product {product_id} (SKU: {variant_sku}) inventory: {total_quantity}")
                
                # Debug: show all variants
                if len(variants) > 1:
                    all_variants = []
                    for v in variants:
                        v_data = v.get("node", {})
                        v_sku = v_data.get("sku", "N/A")
                        v_qty = v_data.get("inventoryQuantity", "N/A")
                        all_variants.append(f"{v_sku}:{v_qty}")
                    print(f"[Shopify DEBUG] All {len(variants)} variants: {', '.join(all_variants)}")
            
            # Determine status
            if total_quantity == 0:
                status = "out_of_stock"
            elif total_quantity <= 5:
                status = "low_stock"
            else:
                status = "in_stock"
            
            return {
                "quantity": total_quantity if has_inventory else 0,
                "status": status
            }
            
        except Exception as e:
            print(f"[Shopify] Error fetching inventory for product {product_id}: {e}")
            import traceback
            traceback.print_exc()
            return {"quantity": None, "status": None}

    def get_inventory_bulk(self, product_ids: list = None) -> dict:
        """
        Fetch inventory for multiple products efficiently using GraphQL.
        Fetches one by one since bulk query with ids filter can be complex.
        """
        if not product_ids:
            return {}
        
        inventory_data = {}
        
        print(f"[Shopify] Fetching inventory for {len(product_ids)} products...")
        
        for product_id in product_ids:
            try:
                # Use the single product function for each
                inv = self.get_inventory_for_product(product_id)
                if inv.get("quantity") is not None:
                    inventory_data[product_id] = inv
            except Exception as e:
                print(f"[Shopify] Error fetching inventory for {product_id}: {e}")
                continue
        
        print(f"[Shopify] Fetched inventory for {len(inventory_data)} products")
        return inventory_data

    def _parse_inventory_from_product_data(self, product: dict) -> dict:
        """Helper to parse inventory data from product GraphQL response"""
        variants = product.get("variants", {}).get("edges", [])
        total_quantity = 0
        has_inventory = False
        
        for variant_edge in variants:
            variant = variant_edge.get("node", {})
            
            # Use inventoryQuantity if available
            quantity = variant.get("inventoryQuantity")
            if quantity is not None:
                total_quantity += quantity
                has_inventory = True
            
            # Also check inventoryLevels
            inventory_item = variant.get("inventoryItem", {})
            levels = inventory_item.get("inventoryLevels", {}).get("edges", [])
            
            for level_edge in levels:
                level = level_edge.get("node", {})
                available = level.get("available")
                if available is not None:
                    total_quantity += available
                    has_inventory = True
        
        # Determine status
        if total_quantity == 0:
            status = "out_of_stock"
        elif total_quantity <= 5:
            status = "low_stock"
        else:
            status = "in_stock"
        
        return {
            "quantity": total_quantity if has_inventory else 0,
            "status": status
        }


shopify_service = ShopifyService()

