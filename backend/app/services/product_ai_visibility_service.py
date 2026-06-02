"""
Product AI Visibility Service (v2.0 Enhanced)

Provides product-level AI visibility tracking across LLM engines,
similar to SEMrush's AI Visibility feature but focused on individual products.

Key Features:
- Generate dynamic prompts based on product attributes (make/model/year fitments)
- Query multiple LLMs and detect product mentions
- Calculate visibility scores (0-100) with level classification
- Track historical trends and competitor mentions

V2.0 ENHANCEMENTS:
- GSC query-based prompt generation (use REAL user searches)
- Vehicle-specific prompts from cached_vehicle_fitments
- Response analysis for competitor insights
- Data-driven revenue impact calculations
- LLM response comparison analysis
"""

import asyncio
import re
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from collections import Counter

from app.core.logging import get_logger
from app.core.config import settings
from app.models.product import Product
from app.models.aeo_models import (
    ProductVisibilityResult,
    ProductVisibilitySnapshot,
)
from app.services.llm_providers import LLMProviderFactory, BaseLLMProvider

logger = get_logger(__name__)


# ============ Configuration ============

# Competitor brands to detect
COMPETITOR_BRANDS = [
    "transgo", "sonnax", "alto products", "alto",
    "raybestos", "transtec", "tss", "precision",
    "borg warner", "borgwarner", "zf", "luk",
    "valeo", "exedy", "aisin"
]

# Brand keywords (derived from the configured store profile)
BRAND_KEYWORDS = settings.store_brand_aliases

# Prompt templates for different query types (LEGACY - kept for backward compatibility)
PROMPT_TEMPLATES = {
    "fitment_query": """¿Cuál es el mejor {product_type} para {vehicle_info}? 
Busco opciones de calidad disponibles en México.""",
    
    "diagnostic_query": """Mi {vehicle_info} tiene problemas de transmisión, 
¿qué {product_type} me recomiendan para repararlo?""",
    
    "comparison_query": """Estoy buscando un {product_type} para {vehicle_info}.
¿Cuáles son las mejores marcas y dónde puedo comprarlo en México?""",
    
    "price_query": """¿Cuánto cuesta un {product_type} para {vehicle_info}?
¿Dónde puedo encontrar el mejor precio en México?""",
    
    "quality_query": """¿Cuál es el {product_type} de mejor calidad para {vehicle_info}?
Busco algo duradero y confiable.""",
}

# V2.0: Enhanced prompt templates by category
PROMPT_TEMPLATES_V2 = {
    "gsc_based": """{{gsc_query}}? ¿Dónde lo consigo en México y cuál marca es mejor?""",
    
    "vehicle_specific": """¿Cuál es el mejor {product_type} para {make} {model} {years}? 
¿Qué marca recomiendan en México?""",
    
    "fault_code": """Mi carro muestra el código de error {fault_code}. 
¿Qué {product_type} necesito para solucionarlo?""",
    
    "competitive": """¿Qué es mejor para {product_type}: {competitor} o Example Store? 
¿Cuál tiene mejor calidad y precio en México?""",
    
    "voice_search": """¿Cómo instalar {product_type} en {vehicle}?""",
    
    "buying_intent": """Quiero comprar {product_type} para mi {vehicle}. 
¿Cuál marca recomiendan y dónde lo compro en México?"""
}

# Common fault codes by transmission type
TRANSMISSION_FAULT_CODES = {
    "4L60E": ["P0700", "P0751", "P0753", "P0758", "P1870"],
    "4L80E": ["P0700", "P0751", "P0756", "P0785"],
    "6L80": ["P0700", "P0751", "P0776", "P0796", "P2714"],
    "6L90": ["P0700", "P0751", "P0776", "P2714"],
    "ZF8HP": ["P0868", "P0871", "P0730", "P0741"],
    "ZF9HP": ["P0868", "P0730", "P0741", "P17BF"],
    "DQ200": ["P0841", "P2711", "P0730"],
    "01M": ["P0730", "P0741", "P0748"],
    "09G": ["P0730", "P0741", "P2714"],
}


class ProductAIVisibilityService:
    """
    Service for checking product-level AI visibility across LLM engines.
    
    Inspired by SEMrush's AI Visibility feature, this service:
    - Generates contextual prompts based on product attributes
    - Queries LLMs to check if products are mentioned/recommended
    - Calculates visibility scores (0-100) like SEMrush's scoring
    - Tracks trends and competitor mentions over time
    """
    
    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
    
    def _get_provider(self, provider_name: str) -> BaseLLMProvider:
        """Get or create a provider instance."""
        if provider_name not in self._providers:
            self._providers[provider_name] = LLMProviderFactory.create(provider_name)
        return self._providers[provider_name]
    
    # ============ Prompt Generation ============
    
    def generate_product_prompts(
        self, 
        product: Product,
        db: Session,
        max_prompts: int = 5
    ) -> List[Dict[str, str]]:
        """
        Generate contextual prompts for a product based on its attributes.
        
        Uses product title, type, vehicle fitments, and SKU to create realistic
        search queries that users might ask AI assistants.
        
        Returns:
            List of dicts with 'prompt_text' and 'prompt_type' keys
        """
        prompts = []
        
        # Extract product info — USE TITLE for descriptive context, not just product_type
        product_type = product.product_type or "refacción de transmisión"
        title = product.title or ""
        sku = product.sku or ""
        
        # Build a descriptive product name from title (more specific than product_type)
        # e.g., "Pack Fe Discos Acero AW50-40LE" → "discos de acero para transmisión AW50-40LE"
        descriptive_name = self._build_descriptive_name(product)
        
        # Try to get vehicle fitment info
        vehicle_info = self._extract_vehicle_info(product, db)
        
        # Generate prompts for each template type
        for prompt_type_key, template in PROMPT_TEMPLATES.items():
            if len(prompts) >= max_prompts:
                break
            
            try:
                prompt_text = template.format(
                    product_type=descriptive_name,
                    vehicle_info=vehicle_info or "vehículos automáticos",
                    sku=sku
                )
                prompts.append({
                    "prompt_text": prompt_text,
                    "prompt_type": prompt_type_key
                })
            except Exception as e:
                logger.warning(f"Failed to generate prompt {prompt_type_key}: {e}")
        
        # Add SKU-specific prompt if available
        if sku and len(prompts) < max_prompts:
            prompts.append({
                "prompt_text": f"¿Dónde puedo comprar el kit {sku} en México?",
                "prompt_type": "sku_query"
            })
        
        # Add title-based prompt (the most specific query possible)
        if title and len(prompts) < max_prompts:
            prompts.append({
                "prompt_text": f"¿Es bueno el {title}? ¿Dónde lo consigo en México?",
                "prompt_type": "product_review"
            })
        
        return prompts
    
    def _build_descriptive_name(self, product: Product) -> str:
        """
        Build a descriptive product name from title for use in prompts.
        Avoids the generic product_type (e.g., 'PACK DE METALES') and instead
        creates a meaningful description like 'discos de acero para transmisión AW50-40LE'.
        """
        import re as _re
        
        title = str(product.title or "").strip()
        product_type = str(product.product_type or "").strip()
        transmission_code = str(product.transmission_code or "").strip()
        
        if not title:
            return product_type or "refacción de transmisión"
        
        # Extract transmission code from title if not set on product
        if not transmission_code:
            # Common transmission patterns
            trans_patterns = [
                r'\b(AW50-40LE|AW55-50SN|AW55-51SN|AF33|AF40)\b',
                r'\b(4L60E|4L65E|4L80E|4T65E|4T80E)\b',
                r'\b(6L80|6L90|6T40|6T70|6T75)\b',
                r'\b(ZF8HP|ZF9HP|ZF6HP|8HP\d+|9HP\d+)\b',
                r'\b(DQ200|DQ250|DQ381|DQ500|DSG7|DSG6)\b',
                r'\b(01M|09G|09D|09K|01J|0AW)\b',
                r'\b(JF\d+E?|RE\d+F?|A\d+[A-Z])\b',
                r'\b(CVT|[A-Z]{2,3}\d{2,3}[A-Z]*-?\d*[A-Z]*)\b',
            ]
            for pattern in trans_patterns:
                match = _re.search(pattern, title, _re.IGNORECASE)
                if match:
                    transmission_code = match.group(0)
                    break
        
        # Clean up title: remove brand prefixes like "Pack Fe", generic words
        clean_title = title.lower()
        # Remove common prefixes that don't add search value
        clean_title = _re.sub(r'^(pack\s+fe\s+|kit\s+de\s+|set\s+de\s+)', '', clean_title, flags=_re.IGNORECASE)
        
        # If title has a transmission code, build around it
        if transmission_code:
            return f"{clean_title.split(transmission_code.lower())[0].strip()} para transmisión {transmission_code}".strip()
        
        # Fallback: just use the cleaned title (better than raw product_type)
        return clean_title[:80] if clean_title else product_type or "refacción de transmisión"
    
    def _extract_vehicle_info(self, product: Product, db: Session) -> Optional[str]:
        """Extract vehicle fitment info from product for prompt generation."""
        # Try to get from metafields or related data
        if hasattr(product, 'compatible_vehicles') and product.compatible_vehicles:
            return product.compatible_vehicles[:100]  # Truncate if too long
        
        # Try cached_vehicle_fitments
        if hasattr(product, 'cached_vehicle_fitments') and product.cached_vehicle_fitments:
            fitments = product.cached_vehicle_fitments
            if isinstance(fitments, list) and len(fitments) > 0:
                first = fitments[0]
                if isinstance(first, dict):
                    make = first.get('make', first.get('marca', ''))
                    model = first.get('model', first.get('modelo', ''))
                    years = first.get('years', first.get('años', ''))
                    if isinstance(years, list) and years:
                        years = f"{years[0]}-{years[-1]}"
                    vehicle_str = f"{make} {model} {years}".strip()
                    if vehicle_str:
                        return vehicle_str
        
        # Try to extract from tags
        if hasattr(product, 'tags') and product.tags:
            # Look for make/model/year patterns
            tags = product.tags if isinstance(product.tags, str) else str(product.tags)
            if any(make in tags.lower() for make in ['chevrolet', 'ford', 'nissan', 'dodge', 'gm']):
                return tags[:100]
        
        # Fallback: DON'T return product_type (that causes "PACK DE METALES para PACK DE METALES")
        # Instead return None so the template uses "vehículos automáticos"
        return None
    
    # ============ V2.0: Enhanced Prompt Generation (Library-Integrated) ============
    
    def generate_product_prompts_v2(
        self, 
        product: Product,
        db: Session,
        max_prompts: int = 10,
        include_library_prompts: bool = True,
        include_gsc_queries: bool = True,
        include_vehicle_specific: bool = True,
        include_fault_codes: bool = True,
        include_competitive: bool = True
    ) -> List[Dict[str, Any]]:
        """
        V2.0: Generate contextual prompts using REAL data sources + Prompt Library.
        
        Data sources used (in priority order):
        1. Prompt Library (PromptPanelItem) - Curated prompts from your library
        2. GSC Queries - Actual search terms users use
        3. Vehicle Fitments - Specific make/model/year from product data
        4. Fault Codes - Based on transmission type
        5. Competitor Context - Based on past AI visibility results
        
        The library prompts are ENHANCED with product-specific context.
        
        Returns:
            List of dicts with 'prompt_text', 'prompt_type', and metadata
        """
        prompts = []
        
        # Extract basic product info
        product_type = str(product.product_type or "refacción de transmisión")
        title = str(product.title or "")
        sku = str(product.sku or "")
        transmission_code = str(product.transmission_code or "")
        
        # 1. PROMPT LIBRARY - Use existing curated prompts (highest priority!)
        if include_library_prompts:
            library_prompts = self._get_library_prompts_for_product(product, db, max_prompts=5)
            prompts.extend(library_prompts)
            logger.info(f"[V2 Prompts] Found {len(library_prompts)} prompts from library")
        
        # 2. GSC QUERY-BASED PROMPTS (real user intent)
        if include_gsc_queries and len(prompts) < max_prompts:
            gsc_prompts = self._generate_gsc_based_prompts(product, db, max_prompts=3)
            prompts.extend(gsc_prompts)
            logger.info(f"[V2 Prompts] Generated {len(gsc_prompts)} GSC-based prompts")
        
        # 3. VEHICLE-SPECIFIC PROMPTS (from cached_vehicle_fitments)
        if include_vehicle_specific and len(prompts) < max_prompts:
            vehicle_prompts = self._generate_vehicle_specific_prompts(product, max_prompts=3)
            prompts.extend(vehicle_prompts)
            logger.info(f"[V2 Prompts] Generated {len(vehicle_prompts)} vehicle-specific prompts")
        
        # 4. FAULT CODE PROMPTS (based on transmission type)
        if include_fault_codes and transmission_code and len(prompts) < max_prompts:
            fault_prompts = self._generate_fault_code_prompts(product, transmission_code)
            prompts.extend(fault_prompts)
            logger.info(f"[V2 Prompts] Generated {len(fault_prompts)} fault code prompts")
        
        # 5. COMPETITIVE PROMPTS (based on past competitor mentions)
        if include_competitive and len(prompts) < max_prompts:
            comp_prompts = self._generate_competitive_prompts(product, db)
            prompts.extend(comp_prompts)
            logger.info(f"[V2 Prompts] Generated {len(comp_prompts)} competitive prompts")
        
        # 6. FALLBACK: Legacy template prompts if we don't have enough
        if len(prompts) < 3:
            legacy_prompts = self.generate_product_prompts(product, db, max_prompts=3)
            for lp in legacy_prompts:
                if len(prompts) < max_prompts:
                    lp["prompt_type"] = f"legacy_{lp['prompt_type']}"
                    prompts.append(lp)
        
        # Deduplicate and limit
        seen_prompts = set()
        unique_prompts = []
        for p in prompts:
            prompt_key = p["prompt_text"][:100].lower()
            if prompt_key not in seen_prompts:
                seen_prompts.add(prompt_key)
                unique_prompts.append(p)
        
        return unique_prompts[:max_prompts]
    
    def _get_library_prompts_for_product(
        self,
        product: Product,
        db: Session,
        max_prompts: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get relevant prompts from PromptPanelItem library for this product.
        
        Matches prompts by:
        - Transmission code (linked_transmission)
        - Fault codes (linked_fault_code) 
        - Product type (category)
        - General prompts
        
        Enhances prompts with product-specific context.
        """
        from app.models.aeo_models import PromptPanelItem
        
        prompts = []
        transmission_code = str(product.transmission_code or "").upper()
        product_type = str(product.product_type or "")
        
        # Build query for relevant prompts
        query = db.query(PromptPanelItem).filter(
            PromptPanelItem.is_active == True
        )
        
        # Get prompts matching this product's transmission
        if transmission_code:
            transmission_prompts = query.filter(
                PromptPanelItem.linked_transmission == transmission_code
            ).order_by(PromptPanelItem.priority.desc()).limit(3).all()
            
            for p in transmission_prompts:
                prompts.append({
                    "prompt_text": self._enhance_prompt_with_product(p.prompt_text, product),
                    "prompt_type": f"library_{p.category or 'general'}",
                    "source": "prompt_library",
                    "library_prompt_id": p.id,
                    "original_prompt": p.prompt_text,
                    "priority": p.priority
                })
        
        # Get prompts by category matching product type
        if product_type and len(prompts) < max_prompts:
            # Map product types to categories
            category_map = {
                "Filtros": "product",
                "Aceites": "product", 
                "Partes Electricas": "fault_code",
                "Kits": "product",
                "Cuerpos de Valvulas": "product",
            }
            category = category_map.get(product_type, "general")
            
            category_prompts = query.filter(
                PromptPanelItem.category == category,
                PromptPanelItem.linked_transmission.is_(None)  # Don't duplicate
            ).order_by(PromptPanelItem.priority.desc()).limit(2).all()
            
            for p in category_prompts:
                if len(prompts) >= max_prompts:
                    break
                prompts.append({
                    "prompt_text": self._enhance_prompt_with_product(p.prompt_text, product),
                    "prompt_type": f"library_{p.category or 'general'}",
                    "source": "prompt_library",
                    "library_prompt_id": p.id,
                    "original_prompt": p.prompt_text,
                    "priority": p.priority
                })
        
        # Get general high-priority prompts
        if len(prompts) < max_prompts:
            general_prompts = query.filter(
                PromptPanelItem.category == "general",
                PromptPanelItem.priority >= 70  # High priority only
            ).order_by(PromptPanelItem.priority.desc()).limit(2).all()
            
            for p in general_prompts:
                if len(prompts) >= max_prompts:
                    break
                prompts.append({
                    "prompt_text": self._enhance_prompt_with_product(p.prompt_text, product),
                    "prompt_type": "library_general",
                    "source": "prompt_library",
                    "library_prompt_id": p.id,
                    "original_prompt": p.prompt_text,
                    "priority": p.priority
                })
        
        return prompts
    
    def _enhance_prompt_with_product(self, prompt_text: str, product: Product) -> str:
        """
        Enhance a library prompt with product-specific context.
        
        Replaces placeholders and adds vehicle/product context.
        """
        enhanced = prompt_text
        
        # Replace common placeholders
        replacements = {
            "{product_type}": str(product.product_type or "refacción"),
            "{transmission}": str(product.transmission_code or "transmisión automática"),
            "{sku}": str(product.sku or ""),
            "{title}": str(product.title or "producto"),
        }
        
        for placeholder, value in replacements.items():
            if placeholder in enhanced:
                enhanced = enhanced.replace(placeholder, value)
        
        # Add vehicle context if prompt doesn't already have specific vehicle
        if "{vehicle}" in enhanced:
            # Get a popular vehicle from fitments
            fitments = product.cached_vehicle_fitments or []
            if fitments and isinstance(fitments, list) and len(fitments) > 0:
                fit = fitments[0]
                if isinstance(fit, dict):
                    vehicle = f"{fit.get('make', '')} {fit.get('model', '')}".strip()
                    enhanced = enhanced.replace("{vehicle}", vehicle or "vehículos automáticos")
            else:
                enhanced = enhanced.replace("{vehicle}", "vehículos automáticos")
        
        return enhanced
    
    def _generate_gsc_based_prompts(
        self, 
        product: Product, 
        db: Session,
        max_prompts: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate prompts from ACTUAL Google Search Console queries.
        
        This is the highest-value prompt source because it reflects
        how users ACTUALLY search for your products.
        """
        prompts = []
        
        try:
            # Try to get GSC queries from ProductAnalyticsSnapshot
            from app.models.product import ProductAnalyticsSnapshot
            
            snapshot = db.query(ProductAnalyticsSnapshot).filter(
                ProductAnalyticsSnapshot.product_id == str(product.id)
            ).order_by(desc(ProductAnalyticsSnapshot.snapshot_date)).first()
            
            if snapshot and snapshot.gsc_top_queries:
                for query_data in snapshot.gsc_top_queries[:max_prompts]:
                    query_text = query_data.get('query', '') if isinstance(query_data, dict) else str(query_data)
                    if query_text and len(query_text) > 5:
                        prompts.append({
                            "prompt_text": f"{query_text}? ¿Dónde lo consigo en México y cuál marca es mejor?",
                            "prompt_type": "gsc_real_query",
                            "source": "gsc",
                            "source_impressions": query_data.get('impressions', 0) if isinstance(query_data, dict) else 0,
                            "source_position": query_data.get('position', 0) if isinstance(query_data, dict) else 0
                        })
            
            # If no snapshot queries, try to match by handle/title keywords
            if not prompts:
                # Get GSC data from Google API
                from app.services.google_api_service import GoogleApiService
                google_service = GoogleApiService()
                
                all_queries = google_service.get_search_console_data(days=30)
                
                # Match queries to this product
                product_keywords = self._extract_product_keywords(product)
                
                for query_data in all_queries:
                    query = query_data.get('query', '').lower()
                    
                    # Check relevance
                    relevance_score = sum(1 for kw in product_keywords if kw in query)
                    
                    if relevance_score >= 2 and query_data.get('impressions', 0) > 50:
                        prompts.append({
                            "prompt_text": f"{query_data['query']}? ¿Dónde comprarlo en México?",
                            "prompt_type": "gsc_matched_query",
                            "source": "gsc_matched",
                            "source_impressions": query_data.get('impressions', 0),
                            "source_position": query_data.get('position', 0),
                            "relevance_score": relevance_score
                        })
                        
                        if len(prompts) >= max_prompts:
                            break
        
        except Exception as e:
            logger.warning(f"[V2 Prompts] GSC query fetch failed: {e}")
        
        return prompts
    
    def _extract_product_keywords(self, product: Product) -> List[str]:
        """Extract searchable keywords from product data."""
        keywords = []
        
        # From title
        if product.title:
            title_words = str(product.title).lower().split()
            keywords.extend([w for w in title_words if len(w) > 3])
        
        # From product type
        if product.product_type:
            type_words = str(product.product_type).lower().split()
            keywords.extend([w for w in type_words if len(w) > 3])
        
        # From transmission code
        if product.transmission_code:
            keywords.append(str(product.transmission_code).lower())
        
        # From SKU
        if product.sku:
            keywords.append(str(product.sku).lower())
        
        return list(set(keywords))
    
    def _generate_vehicle_specific_prompts(
        self, 
        product: Product,
        max_prompts: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate prompts from cached_vehicle_fitments.
        
        Creates specific queries for popular vehicles that the product fits.
        """
        prompts = []
        product_type = str(product.product_type or "refacción de transmisión")
        
        fitments = product.cached_vehicle_fitments
        if not fitments or not isinstance(fitments, list):
            return prompts
        
        # Group by make to get popular makes
        make_counts = Counter()
        for fitment in fitments:
            if isinstance(fitment, dict):
                make = fitment.get('make', fitment.get('marca', ''))
                if make:
                    make_counts[make] += 1
        
        # Get top vehicles (prioritize diverse makes)
        used_makes = set()
        selected_fitments = []
        
        for fitment in fitments:
            if len(selected_fitments) >= max_prompts:
                break
            
            if isinstance(fitment, dict):
                make = fitment.get('make', fitment.get('marca', ''))
                model = fitment.get('model', fitment.get('modelo', ''))
                years = fitment.get('years', fitment.get('años', ''))
                
                # Prioritize diverse makes
                if make and make not in used_makes:
                    used_makes.add(make)
                    selected_fitments.append({
                        'make': make,
                        'model': model,
                        'years': years if isinstance(years, str) else f"{years[0]}-{years[-1]}" if isinstance(years, list) and years else ""
                    })
        
        # Generate prompts for selected vehicles
        for veh in selected_fitments:
            vehicle_str = f"{veh['make']} {veh['model']} {veh['years']}".strip()
            
            prompts.append({
                "prompt_text": f"¿Cuál es el mejor {product_type} para {vehicle_str}? ¿Qué marca recomiendan en México?",
                "prompt_type": "vehicle_specific",
                "source": "fitments",
                "vehicle": veh
            })
        
        return prompts
    
    def _generate_fault_code_prompts(
        self, 
        product: Product,
        transmission_code: str
    ) -> List[Dict[str, Any]]:
        """
        Generate diagnostic prompts based on transmission fault codes.
        """
        prompts = []
        product_type = str(product.product_type or "refacción de transmisión")
        
        # Get fault codes for this transmission
        fault_codes = TRANSMISSION_FAULT_CODES.get(transmission_code.upper(), [])
        
        if not fault_codes:
            return prompts
        
        # Generate prompts for top 2 fault codes
        for code in fault_codes[:2]:
            prompts.append({
                "prompt_text": f"Mi carro muestra el código {code}. ¿Qué {product_type} necesito para solucionarlo?",
                "prompt_type": "fault_code",
                "source": "fault_codes",
                "fault_code": code,
                "transmission": transmission_code
            })
        
        return prompts
    
    def _generate_competitive_prompts(
        self, 
        product: Product, 
        db: Session
    ) -> List[Dict[str, Any]]:
        """
        Generate competitive comparison prompts based on past AI mentions.
        
        If competitors were mentioned in previous checks, create prompts
        that directly compare your product vs those competitors.
        """
        prompts = []
        product_type = str(product.product_type or "refacción de transmisión")
        
        try:
            # Get recent results where competitors were mentioned
            recent_results = db.query(ProductVisibilityResult).filter(
                and_(
                    ProductVisibilityResult.product_id == product.id,
                    ProductVisibilityResult.competitors_mentioned.isnot(None)
                )
            ).order_by(desc(ProductVisibilityResult.checked_at)).limit(20).all()
            
            # Count competitor mentions
            competitor_counts = Counter()
            for result in recent_results:
                if result.competitors_mentioned:
                    for comp in result.competitors_mentioned:
                        competitor_counts[comp] += 1
            
            # Generate prompts for top competitors
            for competitor, count in competitor_counts.most_common(2):
                prompts.append({
                    "prompt_text": f"¿Qué es mejor para {product_type}: {competitor.title()} o {settings.STORE_NAME}? ¿Cuál tiene mejor calidad y precio en México?",
                    "prompt_type": "competitive",
                    "source": "competitor_history",
                    "competitor": competitor,
                    "past_mentions": count
                })
        
        except Exception as e:
            logger.warning(f"[V2 Prompts] Competitive prompt generation failed: {e}")
        
        return prompts
    
    # ============ V2.0: Response Analysis ============
    
    def analyze_competitor_response(
        self,
        response_text: str,
        competitors_mentioned: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze WHY competitors were mentioned in an LLM response.
        
        Extracts:
        - What was said about each competitor
        - Keywords/phrases that triggered the mention
        - Content gaps in your product
        """
        analysis = {
            "competitor_contexts": [],
            "common_phrases": [],
            "content_gaps": []
        }
        
        if not response_text or not competitors_mentioned:
            return analysis
        
        # Extract sentences containing each competitor
        sentences = re.split(r'[.!?]\s+', response_text)
        
        for competitor in competitors_mentioned:
            comp_sentences = [
                s for s in sentences 
                if competitor.lower() in s.lower()
            ]
            
            if comp_sentences:
                # Extract why they mentioned this competitor
                context = {
                    "competitor": competitor,
                    "mentions": len(comp_sentences),
                    "quotes": comp_sentences[:2],  # First 2 mentions
                    "keywords": self._extract_keywords_from_sentences(comp_sentences)
                }
                analysis["competitor_contexts"].append(context)
                
                # Identify phrases we should add
                for sentence in comp_sentences:
                    phrases = self._extract_valuable_phrases(sentence)
                    analysis["common_phrases"].extend(phrases)
        
        # Identify content gaps (what competitors have that we don't mention)
        analysis["content_gaps"] = self._identify_content_gaps(
            analysis["competitor_contexts"]
        )
        
        return analysis
    
    def _extract_keywords_from_sentences(self, sentences: List[str]) -> List[str]:
        """Extract important keywords from competitor mention sentences."""
        keywords = []
        
        # Quality/value keywords
        quality_patterns = [
            r'calidad\s+(\w+)',
            r'mejor\s+(\w+)',
            r'recomend\w*\s+(\w+)',
            r'(\w+)\s+precio',
            r'(\w+)\s+duradero',
            r'(\w+)\s+confiable'
        ]
        
        for sentence in sentences:
            for pattern in quality_patterns:
                matches = re.findall(pattern, sentence.lower())
                keywords.extend(matches)
        
        return list(set(keywords))
    
    def _extract_valuable_phrases(self, sentence: str) -> List[str]:
        """Extract phrases that add value (specs, features, benefits)."""
        phrases = []
        
        # Technical spec patterns
        spec_patterns = [
            r'\d+\s*(ml|litros?|psi|nm|°c|bar)',  # Measurements
            r'oem\s+\d+',  # OEM numbers
            r'compatible\s+con\s+\w+',  # Compatibility
            r'incluye\s+\w+',  # Inclusions
        ]
        
        for pattern in spec_patterns:
            matches = re.findall(pattern, sentence.lower())
            phrases.extend(matches)
        
        return phrases
    
    def _identify_content_gaps(self, competitor_contexts: List[Dict]) -> List[str]:
        """Identify content gaps based on competitor analysis."""
        gaps = []
        
        all_keywords = []
        for ctx in competitor_contexts:
            all_keywords.extend(ctx.get("keywords", []))
        
        keyword_counts = Counter(all_keywords)
        
        # Keywords mentioned multiple times are likely important
        for keyword, count in keyword_counts.most_common(5):
            if count >= 2:
                gaps.append(f"Consider adding content about: {keyword}")
        
        return gaps
    
    # ============ V2.0: Revenue Impact Calculator ============
    
    def calculate_revenue_opportunity(
        self,
        product: Product,
        current_visibility_score: float,
        target_visibility_score: float = 70.0
    ) -> Dict[str, Any]:
        """
        Calculate actual $ revenue opportunity from improving visibility.
        
        Uses real product data:
        - Current conversion rate
        - Average order value (price)
        - Current traffic (sessions)
        - Category benchmarks
        """
        sessions = product.ga4_sessions or 0
        sold_30d = product.sold_30d or 0
        price = float(product.price or 0)
        
        # Current conversion rate
        current_conversion = (sold_30d / sessions * 100) if sessions > 0 else 0
        
        # Estimate traffic increase from visibility improvement
        visibility_gap = target_visibility_score - current_visibility_score
        estimated_traffic_increase_pct = max(0, visibility_gap * 0.3)  # ~30% of visibility gap = traffic increase
        
        # Calculate potential
        additional_sessions = sessions * (estimated_traffic_increase_pct / 100)
        additional_sales = additional_sessions * (current_conversion / 100)
        additional_revenue = additional_sales * price
        
        return {
            "current_state": {
                "sessions": sessions,
                "conversion_rate": round(current_conversion, 2),
                "sold_30d": sold_30d,
                "revenue_30d": product.revenue_30d or 0,
                "visibility_score": current_visibility_score
            },
            "opportunity": {
                "target_visibility": target_visibility_score,
                "visibility_gap": round(visibility_gap, 1),
                "estimated_traffic_increase_pct": round(estimated_traffic_increase_pct, 1),
                "additional_sessions": round(additional_sessions, 0),
                "additional_sales": round(additional_sales, 1),
                "additional_monthly_revenue": round(additional_revenue, 2)
            },
            "confidence": "high" if sessions > 100 else "medium" if sessions > 20 else "low",
            "calculation_method": "data_driven_v2"
        }
    
    # ============ Visibility Checking ============
    
    async def check_product_visibility(
        self,
        db: Session,
        product_id: int,
        provider_names: List[str] = None,
        prompts: List[Dict[str, str]] = None
    ) -> List[ProductVisibilityResult]:
        """
        Check visibility for a single product across specified LLMs.
        
        Args:
            db: Database session
            product_id: ID of the product to check
            provider_names: LLMs to query (default: ["grok"])
            prompts: Custom prompts (optional, will auto-generate if not provided)
        
        Returns:
            List of ProductVisibilityResult records
        """
        if provider_names is None:
            provider_names = ["grok"]
        
        # Get the product
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # Generate prompts if not provided
        if prompts is None:
            prompts = self.generate_product_prompts(product, db)
        
        if not prompts:
            logger.warning(f"No prompts generated for product {product_id}")
            return []
        
        results = []
        
        for provider_name in provider_names:
            provider = self._get_provider(provider_name)
            
            for prompt_data in prompts:
                result = await self._check_single_prompt(
                    db=db,
                    product=product,
                    prompt_text=prompt_data["prompt_text"],
                    prompt_type=prompt_data["prompt_type"],
                    provider=provider,
                    provider_name=provider_name
                )
                results.append(result)
        
        db.commit()
        return results
    
    async def _check_single_prompt(
        self,
        db: Session,
        product: Product,
        prompt_text: str,
        prompt_type: str,
        provider: BaseLLMProvider,
        provider_name: str
    ) -> ProductVisibilityResult:
        """Execute a single visibility check for a product/prompt/provider combination."""
        
        system_prompt = """Eres un experto en refacciones automotrices en México.
Responde de forma detallada, mencionando marcas específicas, tiendas y URLs donde sea posible.
Enfócate en opciones disponibles en el mercado mexicano/latinoamericano."""

        start_time = time.time()
        error = None
        response_text = ""
        
        try:
            result = await provider.generate(
                system_prompt=system_prompt,
                user_prompt=prompt_text,
                json_mode=False,
                temperature=0.7
            )
            
            # Handle response format
            if isinstance(result, dict):
                response_text = str(result.get("content", result.get("response", str(result))))
            else:
                response_text = str(result)
                
        except Exception as e:
            error = str(e)
            logger.error(f"LLM query failed for product {product.id}: {e}")
        
        query_time_ms = int((time.time() - start_time) * 1000)
        
        # Parse the response for visibility signals
        visibility_data = self._parse_product_visibility(
            response_text=response_text,
            product=product
        )
        
        # Create result record
        visibility_result = ProductVisibilityResult(
            product_id=product.id,
            prompt_text=prompt_text,
            prompt_type=prompt_type,
            llm_provider=provider_name,
            llm_model=getattr(provider, 'model', None),
            response_text=response_text[:5000] if response_text else None,
            was_mentioned=visibility_data["was_mentioned"],
            position_in_response=visibility_data["position"],
            mention_context=visibility_data["context"],
            brand_mentioned=visibility_data["brand_mentioned"],
            brand_url_cited=visibility_data["url_cited"],
            competitors_mentioned=visibility_data["competitors"],
            sentiment=visibility_data["sentiment"],
            recommendation_strength=visibility_data["strength"],
            query_time_ms=query_time_ms,
            error=error
        )
        
        db.add(visibility_result)
        return visibility_result
    
    def _parse_product_visibility(
        self, 
        response_text: str,
        product: Product
    ) -> Dict[str, Any]:
        """
        Parse an LLM response for product-specific visibility signals.
        
        Detects:
        - Product mention (by title, SKU, or product type)
        - Brand mention (Example Store)
        - URL citations
        - Competitor mentions
        - Position in recommendations
        - Sentiment
        """
        if not response_text:
            return {
                "was_mentioned": False,
                "position": None,
                "context": "not_found",
                "brand_mentioned": False,
                "url_cited": False,
                "competitors": [],
                "sentiment": None,
                "strength": "none"
            }
        
        text_lower = response_text.lower()
        
        # Check for brand mentions
        brand_mentioned = any(kw.lower() in text_lower for kw in BRAND_KEYWORDS)
        
        # Check for URL citations
        url_pattern = re.compile(r'example-store\.com[^\s]*', re.IGNORECASE)
        url_cited = bool(url_pattern.search(response_text))
        
        # Check if product was specifically mentioned
        was_mentioned = False
        mention_indicators = []
        
        # Check by SKU
        if product.sku and product.sku.lower() in text_lower:
            was_mentioned = True
            mention_indicators.append("sku")
        
        # Check by title (partial match)
        if product.title:
            title_words = product.title.lower().split()[:3]  # First 3 words
            if all(word in text_lower for word in title_words if len(word) > 3):
                was_mentioned = True
                mention_indicators.append("title")
        
        # Check by brand mention with product type context
        if brand_mentioned and product.product_type:
            if product.product_type.lower() in text_lower:
                was_mentioned = True
                mention_indicators.append("brand+type")
        
        # Determine position in response (rough estimate)
        position = None
        if was_mentioned:
            # Find first occurrence and estimate position
            for idx, line in enumerate(response_text.split('\n')[:10], 1):
                if any(ind in line.lower() for ind in mention_indicators):
                    position = min(idx, 3)  # Cap at position 3
                    break
            if position is None:
                position = 3  # Mentioned but not prominently
        
        # Detect competitors
        competitors = [
            comp for comp in COMPETITOR_BRANDS 
            if comp.lower() in text_lower
        ]
        
        # Determine context
        if was_mentioned and position == 1:
            context = "recommended"
        elif was_mentioned:
            context = "mentioned"
        elif brand_mentioned:
            context = "brand_only"
        elif competitors:
            context = "competitors_only"
        else:
            context = "not_found"
        
        # Sentiment detection
        sentiment = self._detect_sentiment(response_text)
        
        # Recommendation strength
        if was_mentioned and position == 1:
            strength = "strong"
        elif was_mentioned:
            strength = "moderate"
        elif brand_mentioned:
            strength = "weak"
        else:
            strength = "none"
        
        return {
            "was_mentioned": was_mentioned,
            "position": position,
            "context": context,
            "brand_mentioned": brand_mentioned,
            "url_cited": url_cited,
            "competitors": competitors,
            "sentiment": sentiment,
            "strength": strength
        }
    
    def _detect_sentiment(self, text: str) -> str:
        """Basic sentiment detection for Spanish text."""
        text_lower = text.lower()
        
        positive = ["recomiendo", "excelente", "confiable", "bueno", "mejor", 
                   "calidad", "funciona", "efectivo", "duradero"]
        negative = ["no recomiendo", "malo", "problema", "evitar", "cuidado",
                   "defectuoso", "falla", "caro"]
        
        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)
        
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"
    
    # ============ Score Calculation ============
    
    def calculate_visibility_score(
        self,
        results: List[ProductVisibilityResult]
    ) -> Dict[str, Any]:
        """
        Calculate visibility score from check results.
        
        Score breakdown:
        - Mention rate: 40 points (% of prompts where product was mentioned)
        - Position bonus: 30 points (being mentioned first)
        - Brand citation: 20 points (example-store.com URL cited)
        - Low competitor share: 10 points (fewer competitor mentions)
        
        Returns:
            Dict with score (0-100), level (low/medium/high), and breakdown
        """
        if not results:
            return {
                "score": 0,
                "level": "low",
                "breakdown": {},
                "by_llm": {}
            }
        
        valid_results = [r for r in results if r.error is None]
        if not valid_results:
            return {"score": 0, "level": "low", "breakdown": {}, "by_llm": {}}
        
        total = len(valid_results)
        
        # Mention rate (40 points max)
        mentions = sum(1 for r in valid_results if r.was_mentioned)
        mention_rate = mentions / total
        mention_score = mention_rate * 40
        
        # Position bonus (30 points max - for being mentioned 1st)
        first_positions = sum(1 for r in valid_results if r.position_in_response == 1)
        position_rate = first_positions / total if total > 0 else 0
        position_score = position_rate * 30
        
        # Brand citation (20 points max)
        citations = sum(1 for r in valid_results if r.brand_url_cited)
        citation_rate = citations / total
        citation_score = citation_rate * 20
        
        # Competitor share (10 points max - lower is better)
        competitor_mentions = sum(
            1 for r in valid_results 
            if r.competitors_mentioned and len(r.competitors_mentioned) > 0
        )
        competitor_rate = competitor_mentions / total
        competitor_score = (1 - competitor_rate) * 10  # Invert - less competitors = more points
        
        # Total score
        total_score = mention_score + position_score + citation_score + competitor_score
        
        # Determine level
        if total_score >= 67:
            level = "high"
        elif total_score >= 34:
            level = "medium"
        else:
            level = "low"
        
        # Calculate per-LLM scores
        by_llm = {}
        for provider in set(r.llm_provider for r in valid_results):
            provider_results = [r for r in valid_results if r.llm_provider == provider]
            provider_mentions = sum(1 for r in provider_results if r.was_mentioned)
            by_llm[provider] = round((provider_mentions / len(provider_results)) * 100) if provider_results else 0
        
        return {
            "score": round(total_score, 1),
            "level": level,
            "breakdown": {
                "mention_score": round(mention_score, 1),
                "position_score": round(position_score, 1),
                "citation_score": round(citation_score, 1),
                "competitor_score": round(competitor_score, 1)
            },
            "by_llm": by_llm,
            "stats": {
                "total_checks": total,
                "mentions": mentions,
                "first_positions": first_positions,
                "url_citations": citations,
                "competitor_appearances": competitor_mentions
            }
        }
    
    # ============ Snapshot Management ============
    
    def create_product_snapshot(
        self,
        db: Session,
        product_id: int,
        target_date: Optional[date] = None
    ) -> Optional[ProductVisibilitySnapshot]:
        """
        Create or update a daily visibility snapshot for a product.
        
        Aggregates all check results from the target day into a single
        visibility score and metrics summary.
        """
        if target_date is None:
            target_date = date.today()
        
        # Get day boundaries
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())
        
        # Query results for the day
        results = db.query(ProductVisibilityResult).filter(
            and_(
                ProductVisibilityResult.product_id == product_id,
                ProductVisibilityResult.checked_at >= day_start,
                ProductVisibilityResult.checked_at <= day_end,
                ProductVisibilityResult.error.is_(None)
            )
        ).all()
        
        if not results:
            logger.info(f"No results to aggregate for product {product_id} on {target_date}")
            return None
        
        # Calculate scores
        score_data = self.calculate_visibility_score(results)
        
        # Calculate competitor data
        all_competitors = []
        for r in results:
            if r.competitors_mentioned:
                all_competitors.extend(r.competitors_mentioned)
        
        competitor_counts = {}
        for comp in all_competitors:
            competitor_counts[comp] = competitor_counts.get(comp, 0) + 1
        
        top_competitors = sorted(
            [{"name": k, "mentions": v} for k, v in competitor_counts.items()],
            key=lambda x: x["mentions"],
            reverse=True
        )[:5]
        
        competitor_share = len([r for r in results if r.competitors_mentioned]) / len(results) * 100
        
        # Get historical scores for change tracking
        score_7d_ago = self._get_historical_score(db, product_id, days_ago=7)
        score_30d_ago = self._get_historical_score(db, product_id, days_ago=30)
        
        current_score = score_data["score"]
        score_change_7d = current_score - score_7d_ago if score_7d_ago else None
        score_change_30d = current_score - score_30d_ago if score_30d_ago else None
        
        # Check for existing snapshot
        snapshot = db.query(ProductVisibilitySnapshot).filter(
            and_(
                ProductVisibilitySnapshot.product_id == product_id,
                func.date(ProductVisibilitySnapshot.snapshot_date) == target_date
            )
        ).first()
        
        if snapshot:
            # Update existing
            snapshot.visibility_score = current_score
            snapshot.visibility_level = score_data["level"]
            snapshot.scores_by_llm = score_data["by_llm"]
            snapshot.total_checks = score_data["stats"]["total_checks"]
            snapshot.mention_count = score_data["stats"]["mentions"]
            snapshot.first_position_count = score_data["stats"]["first_positions"]
            snapshot.url_citation_count = score_data["stats"]["url_citations"]
            snapshot.competitor_share = competitor_share
            snapshot.top_competitors = top_competitors
            snapshot.score_change_7d = score_change_7d
            snapshot.score_change_30d = score_change_30d
        else:
            # Create new
            snapshot = ProductVisibilitySnapshot(
                product_id=product_id,
                snapshot_date=day_start,
                visibility_score=current_score,
                visibility_level=score_data["level"],
                scores_by_llm=score_data["by_llm"],
                total_checks=score_data["stats"]["total_checks"],
                mention_count=score_data["stats"]["mentions"],
                first_position_count=score_data["stats"]["first_positions"],
                url_citation_count=score_data["stats"]["url_citations"],
                competitor_share=competitor_share,
                top_competitors=top_competitors,
                score_change_7d=score_change_7d,
                score_change_30d=score_change_30d
            )
            db.add(snapshot)
        
        db.commit()
        db.refresh(snapshot)
        
        logger.info(f"Created snapshot for product {product_id}: {current_score:.1f}/100 ({score_data['level']})")
        return snapshot
    
    def _get_historical_score(
        self, 
        db: Session, 
        product_id: int, 
        days_ago: int
    ) -> Optional[float]:
        """Get the visibility score from N days ago."""
        target_date = date.today() - timedelta(days=days_ago)
        
        snapshot = db.query(ProductVisibilitySnapshot).filter(
            and_(
                ProductVisibilitySnapshot.product_id == product_id,
                func.date(ProductVisibilitySnapshot.snapshot_date) == target_date
            )
        ).first()
        
        return snapshot.visibility_score if snapshot else None
    
    # ============ Trend Analysis ============
    
    def get_product_visibility_trend(
        self,
        db: Session,
        product_id: int,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get historical visibility trend for charting."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        snapshots = db.query(ProductVisibilitySnapshot).filter(
            and_(
                ProductVisibilitySnapshot.product_id == product_id,
                ProductVisibilitySnapshot.snapshot_date >= cutoff
            )
        ).order_by(ProductVisibilitySnapshot.snapshot_date.asc()).all()
        
        return [
            {
                "date": s.snapshot_date.strftime("%Y-%m-%d"),
                "score": s.visibility_score,
                "level": s.visibility_level,
                "by_llm": s.scores_by_llm or {},
                "mentions": s.mention_count,
                "first_positions": s.first_position_count,
                "competitor_share": s.competitor_share
            }
            for s in snapshots
        ]
    
    def get_multi_llm_comparison(
        self,
        db: Session,
        product_id: int,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get comparison of visibility across different LLM providers."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        results = db.query(ProductVisibilityResult).filter(
            and_(
                ProductVisibilityResult.product_id == product_id,
                ProductVisibilityResult.checked_at >= cutoff,
                ProductVisibilityResult.error.is_(None)
            )
        ).all()
        
        by_provider = {}
        for provider in set(r.llm_provider for r in results):
            provider_results = [r for r in results if r.llm_provider == provider]
            mentions = sum(1 for r in provider_results if r.was_mentioned)
            first_pos = sum(1 for r in provider_results if r.position_in_response == 1)
            citations = sum(1 for r in provider_results if r.brand_url_cited)
            
            total = len(provider_results)
            by_provider[provider] = {
                "total_checks": total,
                "mention_rate": round(mentions / total * 100, 1) if total else 0,
                "first_position_rate": round(first_pos / total * 100, 1) if total else 0,
                "citation_rate": round(citations / total * 100, 1) if total else 0,
                "last_checked": max(r.checked_at for r in provider_results).isoformat() if provider_results else None
            }
        
        return {
            "product_id": product_id,
            "period_days": days,
            "by_provider": by_provider
        }
    
    # ============ Position History Tracking ============
    
    def get_position_history(
        self,
        db: Session,
        product_id: int,
        days: int = 30,
        provider_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get position ranking history for a product over time.
        
        Tracks how the product's position in LLM recommendations has changed,
        similar to SEMrush's position tracking for organic search.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(ProductVisibilityResult).filter(
            and_(
                ProductVisibilityResult.product_id == product_id,
                ProductVisibilityResult.checked_at >= cutoff,
                ProductVisibilityResult.error.is_(None),
                ProductVisibilityResult.was_mentioned == True
            )
        )
        
        if provider_filter:
            query = query.filter(ProductVisibilityResult.llm_provider == provider_filter)
        
        results = query.order_by(ProductVisibilityResult.checked_at.asc()).all()
        
        # Group by date
        position_by_date = {}
        for r in results:
            date_key = r.checked_at.strftime("%Y-%m-%d")
            if date_key not in position_by_date:
                position_by_date[date_key] = []
            position_by_date[date_key].append(r.position_in_response or 3)
        
        # Calculate daily averages
        history = []
        for date_key, positions in sorted(position_by_date.items()):
            avg_position = sum(positions) / len(positions)
            first_count = sum(1 for p in positions if p == 1)
            history.append({
                "date": date_key,
                "avg_position": round(avg_position, 2),
                "checks": len(positions),
                "first_position_count": first_count,
                "first_position_rate": round(first_count / len(positions) * 100, 1)
            })
        
        # Calculate overall stats
        all_positions = [r.position_in_response or 3 for r in results]
        first_positions = sum(1 for p in all_positions if p == 1)
        
        return {
            "product_id": product_id,
            "period_days": days,
            "provider": provider_filter or "all",
            "total_mentions": len(results),
            "avg_position": round(sum(all_positions) / len(all_positions), 2) if all_positions else None,
            "first_position_rate": round(first_positions / len(all_positions) * 100, 1) if all_positions else 0,
            "position_improved": self._calculate_position_trend(history),
            "history": history
        }
    
    def _calculate_position_trend(self, history: List[Dict]) -> Optional[str]:
        """Determine if position is improving, declining, or stable."""
        if len(history) < 2:
            return None
        
        # Compare first and last week averages
        recent = history[-min(7, len(history)):]
        older = history[:min(7, len(history))]
        
        recent_avg = sum(h["avg_position"] for h in recent) / len(recent)
        older_avg = sum(h["avg_position"] for h in older) / len(older)
        
        # Lower position number is better
        if recent_avg < older_avg - 0.3:
            return "improving"
        elif recent_avg > older_avg + 0.3:
            return "declining"
        return "stable"
    
    # ============ Competitor Gap Analysis ============
    
    def get_competitor_gap_analysis(
        self,
        db: Session,
        product_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze competitor visibility gap.
        
        Shows which competitors are being mentioned more than your product
        and identifies opportunities where you should be visible but aren't.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        results = db.query(ProductVisibilityResult).filter(
            and_(
                ProductVisibilityResult.product_id == product_id,
                ProductVisibilityResult.checked_at >= cutoff,
                ProductVisibilityResult.error.is_(None)
            )
        ).all()
        
        if not results:
            return {"product_id": product_id, "competitors": [], "gaps": []}
        
        # Count competitor appearances
        competitor_data = {}
        total_checks = len(results)
        product_mentions = sum(1 for r in results if r.was_mentioned)
        
        for r in results:
            if r.competitors_mentioned:
                for comp in r.competitors_mentioned:
                    if comp not in competitor_data:
                        competitor_data[comp] = {
                            "mentions": 0,
                            "when_product_absent": 0,
                            "with_product": 0,
                            "providers": set()
                        }
                    competitor_data[comp]["mentions"] += 1
                    competitor_data[comp]["providers"].add(r.llm_provider)
                    
                    if r.was_mentioned:
                        competitor_data[comp]["with_product"] += 1
                    else:
                        competitor_data[comp]["when_product_absent"] += 1
        
        # Build competitor analysis
        competitors = []
        gaps = []
        
        for comp, data in sorted(competitor_data.items(), key=lambda x: x[1]["mentions"], reverse=True):
            visibility_rate = round(data["mentions"] / total_checks * 100, 1)
            product_visibility = round(product_mentions / total_checks * 100, 1)
            
            competitor_info = {
                "name": comp,
                "mentions": data["mentions"],
                "visibility_rate": visibility_rate,
                "gap_vs_product": round(visibility_rate - product_visibility, 1),
                "appears_when_product_absent": data["when_product_absent"],
                "providers": list(data["providers"])
            }
            competitors.append(competitor_info)
            
            # Identify gaps (where competitor beats product)
            if data["when_product_absent"] > product_mentions * 0.3:
                gaps.append({
                    "competitor": comp,
                    "opportunity": f"{comp} appears in {data['when_product_absent']} queries where your product doesn't",
                    "severity": "high" if data["when_product_absent"] > product_mentions else "medium",
                    "suggested_action": f"Optimize content to compete with {comp} in AI responses"
                })
        
        return {
            "product_id": product_id,
            "period_days": days,
            "total_checks": total_checks,
            "product_visibility_rate": round(product_mentions / total_checks * 100, 1) if total_checks else 0,
            "competitors": competitors[:10],  # Top 10
            "gaps": gaps[:5],  # Top 5 gaps
            "competitive_index": self._calculate_competitive_index(product_mentions, competitor_data, total_checks)
        }
    
    def _calculate_competitive_index(
        self, 
        product_mentions: int, 
        competitor_data: Dict, 
        total_checks: int
    ) -> float:
        """
        Calculate competitive position index (0-100).
        
        100 = Product always mentioned, no competitors
        0 = Product never mentioned, competitors dominate
        """
        if total_checks == 0:
            return 0
        
        product_rate = product_mentions / total_checks
        
        # Average competitor rate
        if competitor_data:
            avg_competitor_rate = sum(
                d["mentions"] / total_checks for d in competitor_data.values()
            ) / len(competitor_data)
        else:
            avg_competitor_rate = 0
        
        # Index: product rate vs average competitor
        if avg_competitor_rate == 0 and product_rate > 0:
            return 100
        elif product_rate == 0:
            return 0
        else:
            ratio = product_rate / (product_rate + avg_competitor_rate)
            return round(ratio * 100, 1)
    
    # ============ Platform-Specific Recommendations ============
    
    def get_optimization_recommendations(
        self,
        db: Session,
        product_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate platform-specific recommendations for improving visibility.
        
        Analyzes performance across providers and suggests optimizations
        tailored to each LLM's behavior patterns.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        results = db.query(ProductVisibilityResult).filter(
            and_(
                ProductVisibilityResult.product_id == product_id,
                ProductVisibilityResult.checked_at >= cutoff,
                ProductVisibilityResult.error.is_(None)
            )
        ).all()
        
        product = db.query(Product).filter(Product.id == product_id).first()
        
        recommendations = []
        provider_insights = {}
        
        # Analyze by provider
        for provider in set(r.llm_provider for r in results):
            provider_results = [r for r in results if r.llm_provider == provider]
            total = len(provider_results)
            mentions = sum(1 for r in provider_results if r.was_mentioned)
            citations = sum(1 for r in provider_results if r.brand_url_cited)
            first_pos = sum(1 for r in provider_results if r.position_in_response == 1)
            
            mention_rate = mentions / total * 100 if total else 0
            citation_rate = citations / total * 100 if total else 0
            
            provider_insights[provider] = {
                "mention_rate": round(mention_rate, 1),
                "citation_rate": round(citation_rate, 1),
                "first_position_rate": round(first_pos / total * 100, 1) if total else 0,
                "checks": total
            }
            
            # Generate provider-specific recommendations
            if mention_rate < 30:
                recommendations.append({
                    "provider": provider,
                    "priority": "high",
                    "issue": f"Low visibility on {provider.upper()} ({mention_rate:.0f}%)",
                    "action": self._get_provider_optimization(provider, "low_visibility"),
                    "impact": "Could increase product mentions in AI recommendations"
                })
            
            if citation_rate < 10 and mention_rate > 30:
                recommendations.append({
                    "provider": provider,
                    "priority": "medium", 
                    "issue": f"Product mentioned but URL rarely cited on {provider.upper()}",
                    "action": self._get_provider_optimization(provider, "low_citation"),
                    "impact": "Would drive direct traffic from AI referrals"
                })
            
            if first_pos / total * 100 < 20 if total else True:
                recommendations.append({
                    "provider": provider,
                    "priority": "medium",
                    "issue": f"Rarely first recommendation on {provider.upper()}",
                    "action": self._get_provider_optimization(provider, "low_position"),
                    "impact": "First position gets 3x more clicks"
                })
        
        # General content recommendations
        if product:
            content_recs = self._get_content_recommendations(product)
            recommendations.extend(content_recs)
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 2))
        
        return {
            "product_id": product_id,
            "period_days": days,
            "provider_insights": provider_insights,
            "recommendations": recommendations[:10],
            "overall_score": self._calculate_opportunity_score(provider_insights)
        }
    
    def _get_provider_optimization(self, provider: str, issue_type: str) -> str:
        """Get specific optimization advice for a provider and issue type."""
        optimizations = {
            "grok": {
                "low_visibility": "Ensure product appears in X/Twitter discussions and trending automotive topics. Grok prioritizes recent social content.",
                "low_citation": "Add structured product data with clear URLs. Grok cites sources from verified business accounts.",
                "low_position": "Include unique selling points and competitive advantages in product descriptions. Grok ranks by relevance to query."
            },
            "openai": {
                "low_visibility": "Optimize for semantic search - use natural language descriptions. GPT excels at understanding context from quality content.",
                "low_citation": "Ensure example-store.com has strong SEO presence. ChatGPT often cites authoritative e-commerce sources.",
                "low_position": "Add detailed specifications and comparisons. GPT prioritizes comprehensive, accurate information."
            },
            "perplexity": {
                "low_visibility": "Perplexity pulls from live search results. Ensure strong Google SEO and recent content updates.",
                "low_citation": "Perplexity cites sources directly. Focus on being indexed and having clear product URLs.",
                "low_position": "Create comparison content and FAQ pages. Perplexity loves structured answer-focused content."
            }
        }
        
        return optimizations.get(provider, {}).get(
            issue_type, 
            "Improve product content quality and ensure consistent brand presence across web."
        )
    
    def _get_content_recommendations(self, product: Product) -> List[Dict]:
        """Generate content-level recommendations for a product."""
        recs = []
        
        # Check description length
        desc_len = len(product.body_html or "") if hasattr(product, 'body_html') else 0
        if desc_len < 500:
            recs.append({
                "provider": "all",
                "priority": "high",
                "issue": "Product description too short",
                "action": "Expand description to 500+ words with detailed features, benefits, and use cases",
                "impact": "Longer descriptions provide more context for AI to recommend product"
            })
        
        # Check for structured data signals
        if not product.product_type or len(product.product_type) < 5:
            recs.append({
                "provider": "all",
                "priority": "medium",
                "issue": "Missing or vague product type",
                "action": "Add specific product category (e.g., 'Kit de Reconstrucción Transmisión Automática')",
                "impact": "Helps AI understand product context for relevant queries"
            })
        
        return recs
    
    def _calculate_opportunity_score(self, provider_insights: Dict) -> float:
        """Calculate overall optimization opportunity score (0-100)."""
        if not provider_insights:
            return 0
        
        # Higher score = more room for improvement
        total_opportunity = 0
        for provider, data in provider_insights.items():
            mention_gap = 100 - data["mention_rate"]
            citation_gap = 100 - data["citation_rate"]
            position_gap = 100 - data["first_position_rate"]
            
            # Weight: mention most important, then position, then citation
            total_opportunity += mention_gap * 0.5 + position_gap * 0.3 + citation_gap * 0.2
        
        avg_opportunity = total_opportunity / len(provider_insights)
        return round(avg_opportunity, 1)
    
    # ============ V2.0: Enhanced Recommendations with Data-Driven Insights ============
    
    def get_optimization_recommendations_v2(
        self,
        db: Session,
        product_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        V2.0: Generate ACTIONABLE, DATA-DRIVEN recommendations.
        
        Enhancements over V1:
        - Analyzes actual LLM responses to find WHY competitors were mentioned
        - Calculates real revenue opportunity using product conversion data
        - Provides specific content suggestions based on competitor context
        - Includes prompt effectiveness analysis
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Fetch results and product
        results = db.query(ProductVisibilityResult).filter(
            and_(
                ProductVisibilityResult.product_id == product_id,
                ProductVisibilityResult.checked_at >= cutoff,
                ProductVisibilityResult.error.is_(None)
            )
        ).order_by(desc(ProductVisibilityResult.checked_at)).all()
        
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            return {"error": "Product not found"}
        
        recommendations = []
        provider_insights = {}
        competitor_insights = []
        prompt_effectiveness = []
        
        # 1. PROVIDER ANALYSIS (enhanced with response analysis)
        for provider in set(r.llm_provider for r in results):
            provider_results = [r for r in results if r.llm_provider == provider]
            total = len(provider_results)
            mentions = sum(1 for r in provider_results if r.was_mentioned)
            citations = sum(1 for r in provider_results if r.brand_url_cited)
            first_pos = sum(1 for r in provider_results if r.position_in_response == 1)
            
            mention_rate = mentions / total * 100 if total else 0
            citation_rate = citations / total * 100 if total else 0
            first_pos_rate = first_pos / total * 100 if total else 0
            
            provider_insights[provider] = {
                "mention_rate": round(mention_rate, 1),
                "citation_rate": round(citation_rate, 1),
                "first_position_rate": round(first_pos_rate, 1),
                "checks": total
            }
            
            # ENHANCED: Analyze responses where competitors beat us
            competitor_wins = [
                r for r in provider_results 
                if not r.was_mentioned and r.competitors_mentioned
            ]
            
            for result in competitor_wins[:3]:  # Analyze top 3 competitor wins
                analysis = self.analyze_competitor_response(
                    result.response_text or "",
                    result.competitors_mentioned or []
                )
                
                if analysis["competitor_contexts"]:
                    competitor_insights.append({
                        "provider": provider,
                        "prompt": result.prompt_text,
                        "prompt_type": result.prompt_type,
                        "competitors": result.competitors_mentioned,
                        "analysis": analysis,
                        "recommendation": self._generate_competitor_beating_recommendation(
                            analysis, product, result.prompt_type or ""
                        )
                    })
        
        # 2. BUILD DATA-DRIVEN RECOMMENDATIONS
        
        # A) Competitor-based recommendations (most actionable)
        for insight in competitor_insights[:5]:
            if insight["recommendation"]:
                recommendations.append({
                    "provider": insight["provider"],
                    "priority": "high",
                    "issue": f"Competitor {insight['competitors'][0]} mentioned instead of you for '{insight['prompt_type']}' query",
                    "action": insight["recommendation"]["action"],
                    "content_to_add": insight["recommendation"].get("suggested_content"),
                    "competitor_said": insight["analysis"]["competitor_contexts"][0].get("quotes", [])[:1],
                    "impact": "Match competitor visibility for this query type"
                })
        
        # B) Provider-specific recommendations (enhanced with context)
        for provider, insights in provider_insights.items():
            if insights["mention_rate"] < 30:
                # Find what prompts failed on this provider
                failed_prompts = [
                    r.prompt_type for r in results 
                    if r.llm_provider == provider and not r.was_mentioned
                ]
                prompt_types = list(set(failed_prompts))[:3]
                
                recommendations.append({
                    "provider": provider,
                    "priority": "high",
                    "issue": f"Low visibility on {provider.upper()} ({insights['mention_rate']:.0f}%)",
                    "action": self._get_provider_optimization_v2(
                        provider, "low_visibility", product, prompt_types
                    ),
                    "failed_prompt_types": prompt_types,
                    "impact": f"Improve mention rate from {insights['mention_rate']:.0f}% toward 50%+"
                })
        
        # C) Prompt effectiveness analysis
        prompt_stats = {}
        for r in results:
            pt = r.prompt_type or "unknown"
            if pt not in prompt_stats:
                prompt_stats[pt] = {"total": 0, "mentions": 0, "first_pos": 0}
            prompt_stats[pt]["total"] += 1
            if r.was_mentioned:
                prompt_stats[pt]["mentions"] += 1
            if r.position_in_response == 1:
                prompt_stats[pt]["first_pos"] += 1
        
        for pt, stats in prompt_stats.items():
            mention_rate = (stats["mentions"] / stats["total"] * 100) if stats["total"] > 0 else 0
            prompt_effectiveness.append({
                "prompt_type": pt,
                "total_checks": stats["total"],
                "mention_rate": round(mention_rate, 1),
                "first_position_rate": round(stats["first_pos"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
                "effectiveness": "high" if mention_rate > 50 else "medium" if mention_rate > 20 else "low"
            })
        
        # D) Revenue opportunity calculation
        current_score = self._calculate_current_visibility_score(results)
        revenue_opportunity = self.calculate_revenue_opportunity(
            product, 
            current_score,
            target_visibility_score=70.0
        )
        
        # Sort recommendations by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 2))
        
        return {
            "product_id": product_id,
            "product_title": product.title,
            "period_days": days,
            "total_checks": len(results),
            "current_visibility_score": round(current_score, 1),
            "provider_insights": provider_insights,
            "recommendations": recommendations[:10],
            "competitor_insights": competitor_insights[:5],
            "prompt_effectiveness": sorted(
                prompt_effectiveness, 
                key=lambda x: x["mention_rate"], 
                reverse=True
            ),
            "revenue_opportunity": revenue_opportunity,
            "overall_opportunity_score": self._calculate_opportunity_score(provider_insights)
        }
    
    def _calculate_current_visibility_score(self, results: List[ProductVisibilityResult]) -> float:
        """Calculate current visibility score from results."""
        if not results:
            return 0
        
        valid_results = [r for r in results if r.error is None]
        if not valid_results:
            return 0
        
        total = len(valid_results)
        mentions = sum(1 for r in valid_results if r.was_mentioned)
        first_pos = sum(1 for r in valid_results if r.position_in_response == 1)
        citations = sum(1 for r in valid_results if r.brand_url_cited)
        
        # Simple weighted score
        mention_score = (mentions / total) * 40
        position_score = (first_pos / total) * 30
        citation_score = (citations / total) * 20
        
        return mention_score + position_score + citation_score + 10  # Base 10
    
    def _generate_competitor_beating_recommendation(
        self,
        analysis: Dict[str, Any],
        product: Product,
        prompt_type: str
    ) -> Optional[Dict[str, Any]]:
        """Generate specific recommendation to beat a competitor."""
        
        if not analysis.get("competitor_contexts"):
            return None
        
        top_competitor = analysis["competitor_contexts"][0]
        competitor_name = top_competitor.get("competitor", "competitor")
        keywords = top_competitor.get("keywords", [])
        quotes = top_competitor.get("quotes", [])
        
        # Generate actionable recommendation
        if keywords:
            keyword_str = ", ".join(keywords[:3])
            action = f"Add content emphasizing: {keyword_str}. {competitor_name.title()} was mentioned because of these terms."
        else:
            action = f"Analyze {competitor_name.title()}'s content and match their authority signals."
        
        # Generate suggested content if we have quotes
        suggested_content = None
        if quotes:
            suggested_content = f"Consider adding similar content: '{quotes[0][:100]}...'"
        
        return {
            "action": action,
            "suggested_content": suggested_content,
            "keywords_to_add": keywords[:5],
            "competitor": competitor_name
        }
    
    def _get_provider_optimization_v2(
        self, 
        provider: str, 
        issue_type: str, 
        product: Product,
        failed_prompt_types: List[str]
    ) -> str:
        """
        V2: Generate SPECIFIC optimization advice based on actual failed prompts.
        """
        product_type = str(product.product_type or "refacción")
        
        # Base recommendations by provider
        base_recommendations = {
            "grok": {
                "low_visibility": f"For {product_type}: Ensure product has recent X/Twitter mentions. Grok prioritizes fresh social signals.",
            },
            "openai": {
                "low_visibility": f"For {product_type}: Add detailed semantic descriptions. GPT needs rich context to recommend products.",
            },
            "perplexity": {
                "low_visibility": f"For {product_type}: Ensure strong Google indexing. Perplexity uses live search results.",
            }
        }
        
        # Enhance with failed prompt context
        prompt_context = ""
        if "vehicle_specific" in failed_prompt_types:
            prompt_context = " Focus on vehicle compatibility content - add clear make/model/year tables."
        elif "fault_code" in failed_prompt_types:
            prompt_context = " Add diagnostic code content - explain which fault codes this product addresses."
        elif "competitive" in failed_prompt_types:
            prompt_context = " Strengthen brand authority signals - add reviews, certifications, comparisons."
        elif "gsc_real_query" in failed_prompt_types or "gsc_matched_query" in failed_prompt_types:
            prompt_context = " Optimize for actual search queries - match user intent in descriptions."
        
        base = base_recommendations.get(provider, {}).get(
            issue_type, 
            f"Improve {product_type} content quality and visibility."
        )
        
        return base + prompt_context
    
    # ============ V2.0: LLM Response Comparison ============
    
    def get_llm_response_comparison(
        self,
        db: Session,
        product_id: int,
        prompt_text: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Compare how different LLMs responded to the same or similar prompts.
        
        Shows side-by-side analysis:
        - Which LLM mentioned your product
        - Which competitors each LLM mentioned
        - What each LLM said about competitors (to identify content gaps)
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(ProductVisibilityResult).filter(
            and_(
                ProductVisibilityResult.product_id == product_id,
                ProductVisibilityResult.checked_at >= cutoff,
                ProductVisibilityResult.error.is_(None)
            )
        )
        
        if prompt_text:
            query = query.filter(ProductVisibilityResult.prompt_text == prompt_text)
        
        results = query.order_by(desc(ProductVisibilityResult.checked_at)).all()
        
        if not results:
            return {"product_id": product_id, "comparisons": [], "summary": {}}
        
        # Group by prompt text
        prompts_compared = {}
        for r in results:
            prompt_key = r.prompt_text[:100] if r.prompt_text else "unknown"
            if prompt_key not in prompts_compared:
                prompts_compared[prompt_key] = {
                    "prompt": r.prompt_text,
                    "prompt_type": r.prompt_type,
                    "responses": {}
                }
            
            # Analyze this LLM's response
            analysis = self.analyze_competitor_response(
                r.response_text or "",
                r.competitors_mentioned or []
            )
            
            prompts_compared[prompt_key]["responses"][r.llm_provider] = {
                "mentioned_you": r.was_mentioned,
                "position": r.position_in_response,
                "brand_mentioned": r.brand_mentioned,
                "url_cited": r.brand_url_cited,
                "competitors": r.competitors_mentioned or [],
                "sentiment": r.sentiment,
                "competitor_analysis": analysis,
                "response_excerpt": (r.response_text or "")[:500] + "..." if r.response_text and len(r.response_text) > 500 else r.response_text
            }
        
        # Generate comparison summary
        comparisons = list(prompts_compared.values())
        
        # Overall summary
        provider_wins = Counter()
        provider_losses = Counter()
        
        for comp in comparisons:
            for provider, data in comp["responses"].items():
                if data["mentioned_you"]:
                    provider_wins[provider] += 1
                else:
                    provider_losses[provider] += 1
        
        summary = {
            "total_prompts_compared": len(comparisons),
            "provider_performance": {
                provider: {
                    "wins": provider_wins.get(provider, 0),
                    "losses": provider_losses.get(provider, 0),
                    "win_rate": round(
                        provider_wins.get(provider, 0) / 
                        (provider_wins.get(provider, 0) + provider_losses.get(provider, 0)) * 100, 1
                    ) if (provider_wins.get(provider, 0) + provider_losses.get(provider, 0)) > 0 else 0
                }
                for provider in set(list(provider_wins.keys()) + list(provider_losses.keys()))
            },
            "best_performing_llm": provider_wins.most_common(1)[0][0] if provider_wins else None,
            "worst_performing_llm": provider_losses.most_common(1)[0][0] if provider_losses else None
        }
        
        return {
            "product_id": product_id,
            "period_days": days,
            "comparisons": comparisons[:10],
            "summary": summary
        }


# Singleton instance
product_ai_visibility_service = ProductAIVisibilityService()
