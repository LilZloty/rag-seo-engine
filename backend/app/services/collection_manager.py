"""
Collection Manager Service
==========================

Manages Shopify collections for fault codes.
Creates collections, manages products, and optimizes SEO.
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.product import Product
from app.models.aeo_models import FaultCode
from app.core.config import settings

logger = logging.getLogger("collection_manager")


class CollectionManager:
    """
    Manages Shopify collections for fault codes.
    
    Features:
    - Auto-create collections per fault code
    - Populate with matching products
    - Generate SEO-optimized descriptions
    - Track collection performance
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.store_url
    
    async def create_fault_code_collection(self, fault_code: str) -> Dict:
        """
        Create a Shopify collection for a fault code.
        
        Collection naming:
        - Title: "Kits [Fault Code] - [Transmission Names]"
        - Handle: kits-[fault-code]-[transmission]
        
        Returns collection data ready for Shopify API.
        """
        # Get fault code data
        fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        if not fc:
            raise ValueError(f"Fault code {fault_code} not found")
        
        # Get matching products
        products = self._get_products_for_fault_code(fc)
        
        if not products:
            return {
                "fault_code": fault_code,
                "status": "no_products",
                "message": f"No products found for {fault_code}",
                "collection_data": None
            }
        
        # Generate collection data
        collection_data = self._build_collection_data(fc, products)
        
        return {
            "fault_code": fault_code,
            "status": "ready",
            "message": f"Collection ready for {fault_code} with {len(products)} products",
            "collection_data": collection_data,
            "products": [
                {
                    "id": p.id,
                    "sku": p.sku,
                    "title": p.title,
                    "handle": p.handle,
                    "price": p.price,
                    "is_kit": self._is_kit_product(p)
                }
                for p in products[:10]
            ]
        }
    
    async def get_collection_data(self, fault_code: str) -> Dict:
        """
        Get complete collection data for a fault code.
        
        Returns SEO data, product list, and metadata.
        """
        fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        if not fc:
            raise ValueError(f"Fault code {fault_code} not found")
        
        products = self._get_products_for_fault_code(fc)
        
        # Categorize products
        kits = [p for p in products if self._is_kit_product(p)]
        parts = [p for p in products if not self._is_kit_product(p)]
        
        # Get top transmissions
        transmissions = fc.transmissions or []
        
        return {
            "fault_code": fault_code,
            "fault_code_name": fc.name,
            "title": self._generate_collection_title(fc),
            "handle": self._generate_collection_handle(fc),
            "description": self._generate_collection_description(fc, products),
            "meta_title": self._generate_meta_title(fc),
            "meta_description": self._generate_meta_description(fc, products),
            "seo_keywords": self._generate_seo_keywords(fc),
            "transmissions": transmissions,
            "product_counts": {
                "total": len(products),
                "kits": len(kits),
                "parts": len(parts)
            },
            "top_products": [
                {
                    "id": p.id,
                    "title": p.title,
                    "sku": p.sku,
                    "price": p.price,
                    "handle": p.handle,
                    "type": "kit" if self._is_kit_product(p) else "part",
                    "transmission_code": p.transmission_code
                }
                for p in products[:8]
            ],
            "schema_markup": self._generate_collection_schema(fc, products),
            "monthly_traffic_potential": fc.monthly_clicks or 0,
            "estimated_revenue_potential": self._estimate_revenue_potential(fc, products)
        }
    
    def _get_products_for_fault_code(self, fc: FaultCode) -> List[Product]:
        """Get products matching a fault code."""
        transmissions = fc.transmissions or []
        
        if not transmissions:
            return []
        
        return self.db.query(Product).filter(
            Product.transmission_code.in_(transmissions),
            Product.inventory_quantity > 0
        ).order_by(desc(Product.total_sold)).all()
    
    def _is_kit_product(self, product: Product) -> bool:
        """Check if product is a kit."""
        kit_keywords = ['kit', 'reparación', 'reparacion', 'kit de reparación',
                       'kit completo', 'kit de solenoides', 'rebuild kit']
        title_lower = (product.title or '').lower()
        return any(kw in title_lower for kw in kit_keywords)
    
    def _build_collection_data(self, fc: FaultCode, products: List[Product]) -> Dict:
        """Build complete collection data for Shopify."""
        transmissions = fc.transmissions or []
        
        return {
            "title": self._generate_collection_title(fc),
            "handle": self._generate_collection_handle(fc),
            "description": self._generate_collection_description(fc, products),
            "collection_type": "smart",  # Smart collection based on conditions
            "conditions": [
                {
                    "column": "tag",
                    "relation": "equals",
                    "condition": f"fault-code:{fc.code.lower()}"
                }
            ],
            "metafields": {
                "fault_code": fc.code,
                "transmissions": json.dumps(transmissions),
                "monthly_clicks": str(fc.monthly_clicks or 0),
                "target_keywords": json.dumps(self._generate_seo_keywords(fc))
            },
            "seo": {
                "title": self._generate_meta_title(fc),
                "description": self._generate_meta_description(fc, products)
            },
            "sort_order": "best-selling",
            "template_suffix": "fault-code-collection"
        }
    
    def _generate_collection_title(self, fc: FaultCode) -> str:
        """Generate collection title."""
        transmissions = fc.transmissions or []
        
        if transmissions:
            trans_str = transmissions[0]
            if len(transmissions) > 1:
                trans_str = f"{transmissions[0]} y más"
            return f"Kits {fc.code} - {fc.name} [{trans_str}]"
        
        return f"Kits {fc.code} - {fc.name}"
    
    def _generate_collection_handle(self, fc: FaultCode) -> str:
        """Generate URL-friendly handle."""
        transmissions = fc.transmissions or []
        
        if transmissions:
            trans_suffix = transmissions[0].lower().replace(' ', '-')
            return f"kits-{fc.code.lower()}-{trans_suffix}"
        
        return f"kits-{fc.code.lower()}"
    
    def _generate_collection_description(self, fc: FaultCode, products: List[Product]) -> str:
        """Generate HTML collection description."""
        transmissions = fc.transmissions or []
        trans_str = ', '.join(transmissions[:3]) if transmissions else 'múltiples modelos'
        
        kit_count = sum(1 for p in products if self._is_kit_product(p))
        
        html = f"""<div class="fault-code-collection-description">
    <h2>Kits y Refacciones para el Código {fc.code}</h2>
    
    <p>Encuentra los mejores productos para resolver el código de falla <strong>{fc.code}</strong> 
    - {fc.name}. Esta colección incluye kits de reparación y refacciones compatibles con 
    transmisiones <strong>{trans_str}</strong>.</p>
    
    <h3>¿Qué incluye esta colección?</h3>
    <ul>
        <li><strong>{kit_count} Kits de reparación</strong> completos</li>
        <li><strong>{len(products) - kit_count} Refacciones individuales</strong></li>
        <li>Productos compatibles con {trans_str}</li>
        <li>Envío a todo México</li>
    </ul>
    
    <h3>Síntomas del código {fc.code}</h3>
    <ul>
"""
        
        for symptom in (fc.symptoms_text or [])[:5]:
            html += f"        <li>{symptom}</li>\n"
        
        html += """    </ul>
    
    <p><strong>¿Necesitas ayuda?</strong> Nuestros técnicos expertos pueden asesorarte 
    para elegir el producto correcto. Contáctanos por WhatsApp o teléfono.</p>
    
    <div class="authority-badge">
        <p>✓ Más de 10,000 mecánicos ayudados<br>
        ✓ Garantía en todos los productos<br>
        ✓ Envío express disponible</p>
    </div>
</div>"""
        
        return html
    
    def _generate_meta_title(self, fc: FaultCode) -> str:
        """Generate SEO meta title."""
        transmissions = fc.transmissions or []
        if transmissions:
            return f"Kits {fc.code} {transmissions[0]} | Refacciones {fc.name} - {settings.STORE_NAME}"
        return f"Kits {fc.code} | Refacciones y Soluciones - {settings.STORE_NAME}"
    
    def _generate_meta_description(self, fc: FaultCode, products: List[Product]) -> str:
        """Generate SEO meta description."""
        kit_count = sum(1 for p in products if self._is_kit_product(p))
        
        desc = f"Kits y refacciones para código {fc.code} ({fc.name}). "
        if kit_count > 0:
            desc += f"{kit_count} kits de reparación disponibles. "
        desc += "Compatible con " + ', '.join((fc.transmissions or [])[:2]) + ". "
        desc += "Envío a todo México. Expertos en transmisiones."
        
        return desc[:160]
    
    def _generate_seo_keywords(self, fc: FaultCode) -> List[str]:
        """Generate SEO keywords."""
        keywords = [
            fc.code,
            f"kits {fc.code}",
            f"codigo {fc.code}",
            f"reparar {fc.code}",
            f"solucion {fc.code}",
            fc.name.lower()
        ]
        
        for transmission in (fc.transmissions or [])[:2]:
            keywords.append(f"{fc.code} {transmission}")
            keywords.append(f"kits {transmission}")
        
        return keywords
    
    def _generate_collection_schema(self, fc: FaultCode, products: List[Product]) -> Dict:
        """Generate CollectionPage schema."""
        return {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": self._generate_collection_title(fc),
            "description": f"Kits y refacciones para código {fc.code}",
            "url": f"{self.base_url}/collections/{self._generate_collection_handle(fc)}",
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {
                        "@type": "Product",
                        "position": i + 1,
                        "name": p.title,
                        "sku": p.sku,
                        "offers": {
                            "@type": "Offer",
                            "priceCurrency": "MXN",
                            "price": str(p.price).replace(',', '') if p.price else "0",
                            "availability": "https://schema.org/InStock" if (p.inventory_quantity or 0) > 0 else "https://schema.org/OutOfStock"
                        }
                    }
                    for i, p in enumerate(products[:10])
                ]
            },
            "about": {
                "@type": "Thing",
                "name": f"Código de falla {fc.code}",
                "description": fc.description
            }
        }
    
    def _estimate_revenue_potential(self, fc: FaultCode, products: List[Product]) -> float:
        """Estimate monthly revenue potential."""
        if not products or not fc.monthly_clicks:
            return 0.0
        
        # Conservative estimates
        ctr = 0.03  # 3% click-through rate from search
        conversion_rate = 0.02  # 2% conversion
        avg_order_value = sum(
            float(p.price.replace(',', '')) if p.price else 0
            for p in products[:3]
        ) / 3 if products else 0
        
        monthly_visitors = (fc.monthly_clicks or 0) * ctr
        monthly_sales = monthly_visitors * conversion_rate
        
        return round(monthly_sales * avg_order_value, 2)
    
    async def get_high_priority_collections(self, min_monthly_clicks: int = 300) -> List[Dict]:
        """
        Get list of fault codes that should have collections created.
        
        Prioritized by search volume and product availability.
        """
        fault_codes = self.db.query(FaultCode).filter(
            FaultCode.monthly_clicks >= min_monthly_clicks
        ).order_by(FaultCode.monthly_clicks.desc()).all()
        
        results = []
        for fc in fault_codes:
            products = self._get_products_for_fault_code(fc)
            if products:
                results.append({
                    "fault_code": fc.code,
                    "name": fc.name,
                    "monthly_clicks": fc.monthly_clicks,
                    "products_available": len(products),
                    "kits_available": sum(1 for p in products if self._is_kit_product(p)),
                    "revenue_potential": self._estimate_revenue_potential(fc, products),
                    "priority_score": (fc.monthly_clicks or 0) * len(products)
                })
        
        # Sort by priority score
        results.sort(key=lambda x: x["priority_score"], reverse=True)
        
        return results


# Factory function
def get_collection_manager(db: Session) -> CollectionManager:
    """Get CollectionManager instance."""
    return CollectionManager(db)
