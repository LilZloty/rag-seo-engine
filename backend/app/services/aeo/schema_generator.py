"""
Schema.org JSON-LD Generator for AEO and GEO optimization

Generates structured data for:
- VehiclePart: Product schema with vehicle compatibility
- FAQPage: Frequently asked questions with answers
- HowTo: Step-by-step repair guides
- Article: Blog posts with author information
"""

from typing import List, Dict, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class SchemaGenerator:
    """Generates Schema.org JSON-LD structured data for AEO and GEO"""
    
    @staticmethod
    def vehicle_part(
        name: str,
        sku: str,
        description: str,
        price: str = "0.00",
        currency: str = "USD",
        vendor: Optional[str] = None,
        vehicle_fitments: Optional[List[Dict]] = None,
        url: Optional[str] = None,
        image_url: Optional[str] = None,
        availability: str = "https://schema.org/InStock"
    ) -> Dict:
        """
        Generate a partial VehiclePart JSON-LD for ADMIN PREVIEW ONLY.

        ⚠️ NOT THE SCHEMA EMITTED TO GOOGLE. The runtime Product schema is built
        in `Empire V8/snippets/structured-data.liquid` and includes fields this
        function does not (mpn, gtin, additionalProperty, shippingDetails,
        manufacturer, dateModified, multi-image, etc.). For the source of truth,
        view a product page and inspect the JSON-LD in HTML, or run Google's
        Rich Results Test on the live URL.

        This function is kept because `aeo_service.generate_product_schema()`
        and the `/aeo/.../schema` endpoint use it for the admin schema-preview
        UI. Do not infer that what you see here is what Google sees.
        """
        schema = {
            "@context": "https://schema.org/",
            "@type": "VehiclePart",
            "name": name,
            "sku": sku,
            "description": description[:500] if description else "",
            "offers": {
                "@type": "Offer",
                "price": price,
                "priceCurrency": currency,
                "availability": availability
            }
        }
        
        if vendor:
            schema["brand"] = {
                "@type": "Brand",
                "name": vendor
            }
        
        if url:
            schema["url"] = url
        
        if image_url:
            schema["image"] = image_url
        
        # Add vehicle compatibility
        if vehicle_fitments and isinstance(vehicle_fitments, list):
            compatible = []
            for f in vehicle_fitments[:10]:  # Limit to 10 for schema size
                if isinstance(f, dict):
                    vehicle = {
                        "@type": "Vehicle",
                        "manufacturer": {"@type": "Organization", "name": str(f.get('make', ''))},
                    }
                    if f.get('model'):
                        vehicle["model"] = str(f['model'])
                    if f.get('year_start') or f.get('year_end'):
                        year_range = f"{f.get('year_start', '')}-{f.get('year_end', '')}"
                        vehicle["vehicleModelDate"] = year_range
                    compatible.append(vehicle)
            
            if compatible:
                schema["isAccessoryOrSparePartFor"] = compatible
        
        return schema
    
    @staticmethod
    def faq_page(
        title: str,
        description: str,
        questions: List[Dict],
        url: Optional[str] = None
    ) -> Dict:
        """
        Generate FAQPage JSON-LD schema.
        
        Args:
            title: Page title (e.g., "Código P0700: Preguntas Frecuentes")
            description: Brief description of the FAQ topic
            questions: List of {question, answer} dicts
            url: Canonical URL of the FAQ page
        
        Returns:
            Dict containing the FAQPage JSON-LD
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "name": title,
            "description": description,
            "mainEntity": []
        }
        
        if url:
            schema["url"] = url
        
        for q in questions:
            if q.get('question') and q.get('answer'):
                schema["mainEntity"].append({
                    "@type": "Question",
                    "name": q['question'],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": q['answer']
                    }
                })
        
        return schema
    
    @staticmethod
    def how_to(
        title: str,
        description: str,
        steps: List[Dict],
        estimated_time: Optional[str] = None,
        image_url: Optional[str] = None,
        url: Optional[str] = None,
        author_name: str = "Example Store Technical Team",
        author_title: str = "Transmission Specialist"
    ) -> Dict:
        """
        Generate HowTo JSON-LD schema for repair guides.
        
        Args:
            title: Guide title
            description: Brief description
            steps: List of {name, text, image_url} dicts
            estimated_time: ISO 8601 duration (e.g., "PT30M")
            image_url: Hero image URL
            url: Guide URL
            author_name: Author name
            author_title: Author job title
        
        Returns:
            Dict containing the HowTo JSON-LD
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": title,
            "description": description,
            "step": []
        }
        
        if estimated_time:
            schema["totalTime"] = estimated_time
        
        if url:
            schema["url"] = url
        
        if image_url:
            schema["image"] = image_url
        
        if author_name or author_title:
            schema["author"] = {
                "@type": "Person",
                "name": author_name,
                "jobTitle": author_title
            }
        
        for i, step in enumerate(steps, 1):
            step_schema = {
                "@type": "HowToStep",
                "position": i,
                "name": step.get('name', f'Paso {i}'),
                "text": step.get('text', '')
            }
            if step.get('image_url'):
                step_schema["image"] = step['image_url']
            if step.get('url'):
                step_schema["url"] = step['url']
            schema["step"].append(step_schema)
        
        return schema
    
    @staticmethod
    def article(
        title: str,
        description: str,
        author_name: str = "Equipo Técnico Example Store",
        author_title: str = "Transmission Specialist",
        publisher_name: str = "Example Store",
        publisher_url: str = "https://example-store.com",
        published_date: Optional[str] = None,
        modified_date: Optional[str] = None,
        image_url: Optional[str] = None,
        url: Optional[str] = None,
        readers_helped: Optional[int] = None
    ) -> Dict:
        """
        Generate Article JSON-LD with authority signals for GEO.
        
        Args:
            title: Article headline
            description: Article description/summary
            author_name: Author name
            author_title: Author job title
            publisher_name: Publisher organization name
            publisher_url: Publisher website URL
            published_date: ISO date string
            modified_date: ISO date string
            image_url: Featured image URL
            url: Article URL
            readers_helped: Number of readers helped (for authority signals)
        
        Returns:
            Dict containing the Article JSON-LD
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "author": {
                "@type": "Person",
                "name": author_name,
                "jobTitle": author_title
            },
            "publisher": {
                "@type": "Organization",
                "name": publisher_name,
                "url": publisher_url
            }
        }
        
        if published_date:
            schema["datePublished"] = published_date
        
        if modified_date:
            schema["dateModified"] = modified_date
        
        if image_url:
            schema["image"] = image_url
        
        if url:
            schema["url"] = url
        
        # Add authority claim if available
        if readers_helped:
            schema["interactionStatistic"] = {
                "@type": "InteractionCounter",
                "interactionType": "https://schema.org/ReadAction",
                "userInteractionCount": readers_helped
            }
        
        return schema
    
    @staticmethod
    def breadcrumb_list(items: List[Dict]) -> Dict:
        """
        Generate BreadcrumbList JSON-LD for navigation.
        
        Args:
            items: List of {name, url} dicts representing breadcrumb items
        
        Returns:
            Dict containing the BreadcrumbList JSON-LD
        """
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "name": item['name'],
                    "item": item['url']
                }
                for i, item in enumerate(items)
                if item.get('name') and item.get('url')
            ]
        }
    
    @staticmethod
    def organization(
        name: str,
        url: str,
        logo_url: Optional[str] = None,
        contact_point: Optional[Dict] = None
    ) -> Dict:
        """
        Generate Organization JSON-LD.
        
        Args:
            name: Organization name
            url: Organization website URL
            logo_url: Logo image URL
            contact_point: {telephone, contactType, email} dict
        
        Returns:
            Dict containing the Organization JSON-LD
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": name,
            "url": url
        }
        
        if logo_url:
            schema["logo"] = logo_url
        
        if contact_point:
            schema["contactPoint"] = {
                "@type": "ContactPoint",
                **contact_point
            }
        
        return schema
    
    @staticmethod
    def local_business(
        name: str,
        address: Dict,
        geo: Dict,
        url: str,
        telephone: str,
        opening_hours: List[str] = None,
        price_range: str = "$$"
    ) -> Dict:
        """
        Generate LocalBusiness JSON-LD for physical locations.
        
        Args:
            name: Business name
            address: {streetAddress, addressLocality, addressRegion, postalCode, addressCountry}
            geo: {latitude, longitude}
            url: Business URL
            telephone: Phone number
            opening_hours: List of opening hour strings
            price_range: Price range ($, $$, $$$)
        
        Returns:
            Dict containing the LocalBusiness JSON-LD
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "AutomotiveBusiness",
            "name": name,
            "address": {
                "@type": "PostalAddress",
                **address
            },
            "geo": {
                "@type": "GeoCoordinates",
                **geo
            },
            "url": url,
            "telephone": telephone,
            "priceRange": price_range
        }
        
        if opening_hours:
            schema["openingHours"] = opening_hours
        
        return schema


def generate_combined_product_schema(
    product_data: Dict,
    faq_questions: Optional[List[Dict]] = None,
    install_steps: Optional[List[Dict]] = None,
    vehicle_fitments: Optional[List[Dict]] = None,
    install_total_time: Optional[str] = None,
) -> Dict:
    """
    Generate additional JSON-LD @graph for a product page.

    IMPORTANT: This generates ONLY supplemental schemas. The theme's
    structured-data.liquid handles: Product (with reviews, vehicle compatibility),
    BreadcrumbList, WebSite, and LocalBusiness.

    Generated schemas:
    - FAQPage (if FAQ questions exist)
    - HowTo (if installation guide exists)

    Designed to be stored in Shopify metafield: custom.product_schema_json
    
    Args:
        product_data: Dict with keys: title, sku, description, price, vendor, 
                      handle, product_type, image_url, oem_references
        faq_questions: List of {question, answer} dicts
        install_steps: List of {name, text} dicts for installation guide
        vehicle_fitments: List of vehicle fitment dicts
    """
    import re
    
    graph = []
    
    title = product_data.get('title', '')
    sku = product_data.get('sku', '')
    description = product_data.get('description', '')
    price = str(product_data.get('price', '0.00'))
    vendor = product_data.get('vendor', '')
    handle = product_data.get('handle', '')
    product_type = product_data.get('product_type', '')
    image_url = product_data.get('image_url', '')
    oem_refs = product_data.get('oem_references', [])
    
    base_url = "https://www.example-store.com"
    product_url = f"{base_url}/products/{handle}" if handle else ""
    product_id = f"{base_url}/products/{handle}#product" if handle else ""
    
    # --- [REMOVED] Product/VehiclePart Schema ---
    # Shopify theme's structured-data.liquid now handles:
    # Product (name, description, sku, mpn, brand, offers, reviews, isAccessoryOrSparePartFor)
    # BreadcrumbList (all page types)
    # We only generate what the theme CANNOT provide: FAQPage, HowTo

    # --- [REMOVED Phase 2.9 — dedupe] FAQPage Schema ---
    # FAQs are now written to the dedicated `custom.product_faqs` metafield
    # (Phase 2.4) by the calling endpoint. The theme's structured-data.liquid
    # emits FAQPage as a standalone <script> block from that metafield, so
    # keeping FAQPage in this @graph would emit duplicate FAQPage on the
    # product page. We accept faq_questions in the signature for backwards
    # compatibility (so existing callers don't break) but don't embed them
    # in the @graph anymore.
    _ = faq_questions  # intentionally unused — see comment above

    # --- 3. HowTo Schema (Installation Guide) ---
    if install_steps and len(install_steps) > 0:
        steps = []
        for i, step in enumerate(install_steps, 1):
            steps.append({
                "@type": "HowToStep",
                "position": i,
                "name": step.get('name', f'Paso {i}'),
                "text": step.get('text', '')
            })
        
        if steps:
            howto_schema = {
                "@type": "HowTo",
                "name": f"Instalacion de {title}",
                "description": f"Guia de instalacion para {title} en transmisiones automaticas",
                "step": steps,
                "author": {
                    "@type": "Organization",
                    "name": "Example Store",
                    "url": base_url
                }
            }
            if install_total_time:
                howto_schema["totalTime"] = install_total_time
            if product_url:
                howto_schema["url"] = product_url
            graph.append(howto_schema)
    
    # --- [REMOVED] BreadcrumbList ---
    # Theme's structured-data.liquid already generates BreadcrumbList for all page types

    # --- Build final @graph ---
    return {
        "@context": "https://schema.org",
        "@graph": graph
    }


# Utility function for easy schema generation
def generate_product_schema(
    name: str,
    sku: str,
    description: str,
    **kwargs
) -> Dict:
    """Convenience function to generate VehiclePart schema."""
    return SchemaGenerator.vehicle_part(
        name=name,
        sku=sku,
        description=description,
        **kwargs
    )


def extract_faq_from_html(html: str) -> List[Dict]:
    """Extract FAQ question/answer pairs from product HTML description."""
    import re
    questions = []
    
    faq_match = re.search(
        r'<h3[^>]*>\s*Preguntas\s+Frecuentes\s*</h3>(.*?)(?=<h[23]|$)',
        html, re.IGNORECASE | re.DOTALL
    )
    if not faq_match:
        return questions
    
    faq_section = faq_match.group(1)
    
    # Pattern: <strong>Question?</strong> Answer text
    pairs = re.findall(
        r'<strong>\s*([^<]*\?)\s*</strong>\s*(.*?)(?=<li>|</ul>|</li>|$)',
        faq_section, re.DOTALL
    )
    
    for question, answer in pairs:
        answer_clean = re.sub(r'<[^>]+>', '', answer).strip()
        question_clean = question.strip()
        if question_clean and answer_clean:
            questions.append({
                'question': question_clean,
                'answer': answer_clean
            })
    
    return questions


def extract_install_steps_from_html(html: str) -> List[Dict]:
    """Extract installation guide steps from product HTML description."""
    import re
    steps = []

    # Capture the full install-guide block from <h3> to the next <h2/h3> or end.
    # Wider net than before — accepts either a paragraph or list as content.
    block_match = re.search(
        r'<h3[^>]*>\s*Gu.{1,5}a\s+de\s+Instalaci.{1,3}n\s*</h3>(.*?)(?=<h[23]|$)',
        html, re.IGNORECASE | re.DOTALL
    )
    if not block_match:
        return steps

    block = block_match.group(1)

    # Preferred path: ordered or unordered list — each <li> is a discrete step.
    # Mechanic-authored guides upgraded to lists hit this branch and get clean,
    # numbered HowToStep entries instead of period-split fragments.
    list_items = re.findall(r'<li[^>]*>(.*?)</li>', block, re.IGNORECASE | re.DOTALL)
    if list_items:
        for i, raw in enumerate(list_items, 1):
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = re.sub(r'\s+', ' ', text).strip().rstrip('.')
            if len(text) > 10:
                steps.append({'name': f'Paso {i}', 'text': text})
        return steps

    # Fallback: single paragraph — split on sentence delimiters.
    # Used when the guide is still prose; works but produces rougher steps.
    para_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.IGNORECASE | re.DOTALL)
    if not para_match:
        return steps

    guide_text = re.sub(r'<[^>]+>', '', para_match.group(1)).strip()
    raw_steps = re.split(r'(?:\.\s+|\d+\.\s+|;\s+)', guide_text)
    for i, step_text in enumerate(raw_steps, 1):
        step_text = step_text.strip().rstrip('.')
        if len(step_text) > 10:
            steps.append({'name': f'Paso {i}', 'text': step_text})

    return steps


def extract_install_total_time_from_html(html: str) -> Optional[str]:
    """Pull a rough installation duration ("aproximadamente 45 minutos") and
    convert to ISO 8601 (PT45M). Returns None if no duration is mentioned —
    HowTo schema accepts an absent totalTime gracefully."""
    import re
    block_match = re.search(
        r'<h3[^>]*>\s*Gu.{1,5}a\s+de\s+Instalaci.{1,3}n\s*</h3>(.*?)(?=<h[23]|$)',
        html, re.IGNORECASE | re.DOTALL
    )
    if not block_match:
        return None
    text = re.sub(r'<[^>]+>', ' ', block_match.group(1))

    h_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hora|hr|h)\b', text, re.IGNORECASE)
    if h_match:
        hours = float(h_match.group(1))
        whole = int(hours)
        mins = int(round((hours - whole) * 60))
        if mins:
            return f"PT{whole}H{mins}M"
        return f"PT{whole}H"

    m_match = re.search(r'(\d+)\s*(?:minuto|min)\b', text, re.IGNORECASE)
    if m_match:
        return f"PT{int(m_match.group(1))}M"

    return None


def extract_oem_references_from_html(html: str) -> List[str]:
    """Extract OEM reference numbers from product HTML."""
    import re
    oem_match = re.search(
        r'OEM\s*(?:Referencia)?[^:]*:\s*</strong>\s*(.*?)(?:</li>|<br)',
        html, re.IGNORECASE | re.DOTALL
    )
    if oem_match:
        refs_text = re.sub(r'<[^>]+>', '', oem_match.group(1)).strip()
        return [r.strip() for r in refs_text.split(',') if r.strip()]
    return []


def generate_schema_from_product_page(
    product_data: Dict,
    description_html: str,
    vehicle_fitments: Optional[List[Dict]] = None
) -> Dict:
    """
    High-level function: Generate complete JSON-LD schema from a product page.
    
    Auto-extracts FAQ, install steps, and OEM references from the HTML description.
    
    Args:
        product_data: Dict with title, sku, price, vendor, handle, product_type, image_url
        description_html: Full HTML description of the product
        vehicle_fitments: Optional list of vehicle fitment dicts
    
    Returns:
        Complete @graph JSON-LD ready to store in custom.product_schema metafield
    """
    faq = extract_faq_from_html(description_html)
    steps = extract_install_steps_from_html(description_html)
    total_time = extract_install_total_time_from_html(description_html)
    oem_refs = extract_oem_references_from_html(description_html)

    # Strip HTML tags for clean description
    import re
    clean_desc = re.sub(r'<[^>]+>', ' ', description_html)
    clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()[:500]

    product_data_enriched = {
        **product_data,
        'description': clean_desc,
        'oem_references': oem_refs
    }

    schema = generate_combined_product_schema(
        product_data=product_data_enriched,
        faq_questions=faq,
        install_steps=steps,
        vehicle_fitments=vehicle_fitments,
        install_total_time=total_time
    )

    return schema


def generate_faq_schema(
    title: str,
    description: str,
    questions: List[Dict],
    **kwargs
) -> Dict:
    """Convenience function to generate FAQPage schema."""
    return SchemaGenerator.faq_page(
        title=title,
        description=description,
        questions=questions,
        **kwargs
    )


def generate_howto_schema(
    title: str,
    description: str,
    steps: List[Dict],
    **kwargs
) -> Dict:
    """Convenience function to generate HowTo schema."""
    return SchemaGenerator.how_to(
        title=title,
        description=description,
        steps=steps,
        **kwargs
    )
