"""
Schema.org Generator Service
============================

Generates structured data markup for AEO/GEO optimization.
Supports: FAQPage, HowTo, Product, BreadcrumbList, Article
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.aeo_models import FaultCode
from app.core.config import settings

logger = logging.getLogger("schema_generator")


class SchemaGenerator:
    """
    Generates Schema.org structured data for SEO.
    
    Creates markup that helps search engines and AI systems
    understand content structure and relationships.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.store_url
    
    async def generate_schema(
        self,
        content_type: str,
        fault_code: Optional[str] = None,
        blog_content: Optional[str] = None,
        product_ids: Optional[List[str]] = None
    ) -> Dict:
        """
        Generate Schema.org structured data.
        
        Args:
            content_type: faq, howto, product, breadcrumb, article
            fault_code: Optional fault code for context
            blog_content: Optional blog content for extraction
            product_ids: Optional list of product IDs
        """
        generators = {
            "faq": self._generate_faq_schema,
            "howto": self._generate_howto_schema,
            "product": self._generate_product_schema,
            "breadcrumb": self._generate_breadcrumb_schema,
            "article": self._generate_article_schema
        }
        
        if content_type not in generators:
            raise ValueError(f"Unknown content type: {content_type}")
        
        return await generators[content_type](fault_code, blog_content, product_ids)
    
    async def _generate_faq_schema(
        self,
        fault_code: Optional[str],
        blog_content: Optional[str],
        product_ids: Optional[List[str]]
    ) -> Dict:
        """Generate FAQPage schema."""
        fc = None
        if fault_code:
            fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        
        questions = []
        
        if fc:
            questions.extend([
                {
                    "@type": "Question",
                    "name": f"¿Qué significa el código {fc.code}?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": fc.description or f"El código {fc.code} indica {fc.name}."
                    }
                },
                {
                    "@type": "Question",
                    "name": f"¿Cuáles son los síntomas del código {fc.code}?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Los síntomas más comunes son: " + ", ".join((fc.symptoms_text or [])[:5]) + "."
                    }
                },
                {
                    "@type": "Question",
                    "name": f"¿Cómo se repara el código {fc.code}?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": f"La reparación depende de la causa. Las soluciones más comunes incluyen reemplazar: " + ", ".join((fc.common_causes or [])[:3]) + "."
                    }
                }
            ])
        
        # Add product-related FAQ if products provided
        if product_ids:
            products = self.db.query(Product).filter(Product.id.in_(product_ids)).all()
            if products:
                for product in products[:2]:
                    questions.append({
                        "@type": "Question",
                        "name": f"¿El {product.title} soluciona el código {fault_code or 'de falla'}?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": f"Sí, el {product.title} es compatible con transmisiones {product.transmission_code or 'múltiples'} y ha sido probado para resolver este tipo de código de falla."
                        }
                    })
        
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": questions
        }
        
        return {
            "schema_type": "FAQPage",
            "schema_json": schema,
            "html_script": f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
        }
    
    async def _generate_howto_schema(
        self,
        fault_code: Optional[str],
        blog_content: Optional[str],
        product_ids: Optional[List[str]]
    ) -> Dict:
        """Generate HowTo schema."""
        fc = None
        if fault_code:
            fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        
        steps = []
        products = []
        
        if product_ids:
            products = self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        
        # Build steps
        steps.append({
            "@type": "HowToStep",
            "position": 1,
            "name": "Identificar el código de falla",
            "text": f"Conecta un escáner OBDII al puerto del vehículo y verifica que el código presente sea {fc.code if fc else 'el correcto'}.",
            "url": f"{self.base_url}/blogs/news/{(fc.code if fc else 'diagnostico').lower()}#step1"
        })
        
        steps.append({
            "@type": "HowToStep",
            "position": 2,
            "name": "Verificar síntomas",
            "text": "Comprueba que los síntomas del vehículo coincidan con los descritos en la guía técnica.",
            "url": f"{self.base_url}/blogs/news/{(fc.code if fc else 'diagnostico').lower()}#step2"
        })
        
        if fc and fc.common_causes:
            steps.append({
                "@type": "HowToStep",
                "position": 3,
                "name": "Diagnosticar la causa raíz",
                "text": f"Revisa las causas más comunes: {', '.join(fc.common_causes[:2])}.",
                "url": f"{self.base_url}/blogs/news/{fc.code.lower()}#step3"
            })
        
        if products:
            steps.append({
                "@type": "HowToStep",
                "position": len(steps) + 1,
                "name": "Reemplazar las piezas defectuosas",
                "text": f"Instala el producto recomendado: {products[0].title}. Sigue las instrucciones del fabricante.",
                "url": f"{self.base_url}/products/{products[0].handle}" if products[0].handle else f"{self.base_url}/products"
            })
        
        schema = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": f"Cómo reparar el código {fc.code if fc else 'de falla de transmisión'}",
            "description": f"Guía paso a paso para diagnosticar y reparar el código de falla {fc.code if fc else ''} en transmisiones automáticas.",
            "totalTime": "PT2H",
            "estimatedCost": {
                "@type": "MonetaryAmount",
                "currency": "MXN",
                "value": str(products[0].price) if products else "2500"
            },
            "step": steps
        }
        
        if products:
            schema["supply"] = [
                {
                    "@type": "HowToSupply",
                    "name": p.title
                }
                for p in products[:3]
            ]
        
        return {
            "schema_type": "HowTo",
            "schema_json": schema,
            "html_script": f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
        }
    
    async def _generate_product_schema(
        self,
        fault_code: Optional[str],
        blog_content: Optional[str],
        product_ids: Optional[List[str]]
    ) -> Dict:
        """Generate Product schema."""
        if not product_ids:
            raise ValueError("Product IDs required for Product schema")
        
        products = self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        
        if len(products) == 1:
            # Single product
            p = products[0]
            schema = {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": p.title,
                "description": f"{p.title} - Refacción para transmisión {p.transmission_code or ''}",
                "sku": p.sku,
                "brand": {
                    "@type": "Brand",
                    "name": settings.STORE_NAME
                },
                "offers": {
                    "@type": "Offer",
                    "url": f"{self.base_url}/products/{p.handle}" if p.handle else f"{self.base_url}/products",
                    "priceCurrency": "MXN",
                    "price": str(p.price).replace(',', '') if p.price else "0",
                    "availability": "https://schema.org/InStock" if (p.inventory_quantity or 0) > 0 else "https://schema.org/OutOfStock",
                    "seller": {
                        "@type": "Organization",
                        "name": settings.STORE_NAME
                    }
                }
            }
            
            if fault_code:
                schema["category"] = f"Reparación de código {fault_code}"
        else:
            # Multiple products - use ItemList
            schema = {
                "@context": "https://schema.org",
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
                    for i, p in enumerate(products)
                ]
            }
        
        return {
            "schema_type": "Product",
            "schema_json": schema,
            "html_script": f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
        }
    
    async def _generate_breadcrumb_schema(
        self,
        fault_code: Optional[str],
        blog_content: Optional[str],
        product_ids: Optional[List[str]]
    ) -> Dict:
        """Generate BreadcrumbList schema."""
        items = [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Inicio",
                "item": self.base_url
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Blog",
                "item": f"{self.base_url}/blogs/news"
            }
        ]
        
        if fault_code:
            items.append({
                "@type": "ListItem",
                "position": 3,
                "name": f"Código {fault_code}",
                "item": f"{self.base_url}/blogs/news/{fault_code.lower()}"
            })
        
        schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": items
        }
        
        return {
            "schema_type": "BreadcrumbList",
            "schema_json": schema,
            "html_script": f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
        }
    
    async def _generate_article_schema(
        self,
        fault_code: Optional[str],
        blog_content: Optional[str],
        product_ids: Optional[List[str]]
    ) -> Dict:
        """Generate Article schema for blog posts."""
        fc = None
        if fault_code:
            fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        
        schema = {
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": f"Código {fc.code}: {fc.name}" if fc else "Guía de Reparación de Transmisión",
            "description": fc.description if fc else "Guía técnica para reparación de transmisiones automáticas.",
            "author": {
                "@type": "Organization",
                "name": settings.STORE_NAME,
                "url": self.base_url
            },
            "publisher": {
                "@type": "Organization",
                "name": settings.STORE_NAME,
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{self.base_url}/logo.png"
                }
            },
            "datePublished": datetime.utcnow().isoformat(),
            "dateModified": datetime.utcnow().isoformat(),
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": f"{self.base_url}/blogs/news/{(fc.code if fc else 'guia').lower()}"
            }
        }
        
        if fault_code:
            schema["about"] = {
                "@type": "Thing",
                "name": f"Código de falla {fault_code}",
                "description": fc.description if fc else None
            }
        
        return {
            "schema_type": "TechArticle",
            "schema_json": schema,
            "html_script": f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=2)}</script>'
        }
    
    def generate_complete_markup_set(
        self,
        fault_code: str,
        product_ids: List[str]
    ) -> Dict:
        """
        Generate a complete set of schemas for a fault code article.
        
        Returns all schemas needed for a comprehensive SEO setup.
        """
        import asyncio
        
        async def _generate_all():
            article = await self.generate_schema("article", fault_code, None, product_ids)
            faq = await self.generate_schema("faq", fault_code, None, product_ids)
            howto = await self.generate_schema("howto", fault_code, None, product_ids)
            breadcrumb = await self.generate_schema("breadcrumb", fault_code)
            product = await self.generate_schema("product", fault_code, None, product_ids)
            
            return {
                "article": article,
                "faq": faq,
                "howto": howto,
                "breadcrumb": breadcrumb,
                "product": product
            }
        
        return asyncio.run(_generate_all())


# Factory function
def get_schema_generator(db: Session) -> SchemaGenerator:
    """Get SchemaGenerator instance."""
    return SchemaGenerator(db)
