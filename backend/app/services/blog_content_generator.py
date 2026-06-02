"""
Blog Content Generator Service
==============================

Generates AEO-optimized blog articles for fault codes with embedded products.
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.product import Product
from app.models.aeo_models import FaultCode
from app.models.solution_graph import BlogSolution
from app.services.llm_service import llm_service
from app.services.eeat_generator import get_eeat_generator
from app.services.comparison_generator import get_comparison_generator

logger = logging.getLogger("blog_generator")


class BlogContentGenerator:
    """
    Generates complete AEO-optimized blog articles for fault codes.
    
    Features:
    - SEO-optimized titles and meta descriptions
    - Structured content with proper headings
    - Embedded product recommendations
    - Schema.org FAQ and HowTo generation
    - Keyword optimization
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def generate_fault_code_article(
        self,
        fault_code: str,
        include_products: bool = True,
        word_count: int = 1000,
        tone: str = "professional",
        include_eeat: bool = True,
        include_comparison_tables: bool = True
    ) -> Dict:
        """
        Generate complete blog article for a fault code with SEO enhancements.
        
        Features:
        - E-E-A-T Authority Box (trust signals)
        - Comparison Tables (vs other fault codes)
        - Schema.org markup
        
        Returns structured content ready for publishing.
        """
        # Get fault code data
        fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        if not fc:
            raise ValueError(f"Fault code {fault_code} not found")
        
        # Get matching products
        products = []
        if include_products:
            products = self._get_products_for_fault_code(fc)
        
        # Generate content sections
        sections = await self._generate_sections(fc, products, word_count, tone)
        
        # Generate title and meta
        title = self._generate_title(fc)
        meta_description = self._generate_meta_description(fc, products)
        
        # Initialize enhanced content
        enhanced_content = {
            "eeat_box": None,
            "comparison_tables": None,
            "related_codes_table": None
        }
        
        # 1. E-E-A-T Authority Box (trust signals)
        if include_eeat:
            eeat_gen = get_eeat_generator()
            eeat_box = eeat_gen.generate_authority_box(
                context="guide",
                fault_code=fc.code,
                transmission=fc.transmissions[0] if fc.transmissions else None
            )
            enhanced_content["eeat_box"] = {
                "html": eeat_box.html_output,
                "statistics": eeat_box.statistics,
                "trust_signals": eeat_box.trust_signals
            }
        
        # 2. Comparison Tables (vs other fault codes)
        if include_comparison_tables:
            comp_gen = get_comparison_generator()
            
            # Generate related fault codes comparison
            related_codes = ["P0706", "P0715", "P0730"]
            if fc.code in related_codes:
                related_codes.remove(fc.code)
            
            if related_codes:
                comparison = comp_gen.generate_fault_code_comparison(
                    fc.code, related_codes[0]
                )
                enhanced_content["comparison_tables"] = {
                    "vs_code": related_codes[0],
                    "html": comparison["html"],
                    "rows": comparison["rows"]
                }
            
            # Generate related codes table
            related_table_html = comp_gen.generate_related_codes_table(
                fc.code, related_codes[:3]
            )
            enhanced_content["related_codes_table"] = related_table_html
        
        # Generate Schema.org data
        faq_schema = self._generate_faq_schema(fc, products)
        howto_schema = self._generate_howto_schema(fc, products)
        
        # Calculate read time
        total_words = sum(len(section['content'].split()) for section in sections)
        read_time = max(1, total_words // 200)
        
        # Generate target keywords
        target_keywords = self._generate_keywords(fc)
        
        return {
            "fault_code": fault_code,
            "title": title,
            "meta_description": meta_description,
            "sections": sections,
            "product_recommendations": [
                {
                    "product_id": p.id,
                    "sku": p.sku,
                    "title": p.title,
                    "handle": p.handle,
                    "price": p.price,
                    "is_kit": self._is_kit_product(p),
                    "position": i + 1
                }
                for i, p in enumerate(products[:5])
            ],
            "faq_schema": faq_schema,
            "howto_schema": howto_schema,
            "estimated_read_time": read_time,
            "target_keywords": target_keywords,
            "transmissions": fc.transmissions or [],
            "monthly_clicks": fc.monthly_clicks or 0,
            "enhanced_content": enhanced_content
        }
    
    def _get_products_for_fault_code(self, fc: FaultCode) -> List[Product]:
        """Get products matching a fault code, prioritizing kits."""
        transmissions = fc.transmissions or []
        
        if not transmissions:
            return []
        
        # Get all matching products
        products = self.db.query(Product).filter(
            Product.transmission_code.in_(transmissions),
            Product.inventory_quantity > 0
        ).order_by(desc(Product.total_sold)).all()
        
        # Sort: kits first, then by sales
        def sort_key(p):
            is_kit = self._is_kit_product(p)
            return (-int(is_kit), -(p.total_sold or 0))
        
        return sorted(products, key=sort_key)
    
    def _is_kit_product(self, product: Product) -> bool:
        """Check if a product is a kit/repair kit."""
        kit_keywords = ['kit', 'reparación', 'reparacion', 'kit de reparación', 
                       'kit completo', 'kit de solenoides', 'rebuild kit']
        title_lower = (product.title or '').lower()
        return any(kw in title_lower for kw in kit_keywords)
    
    async def _generate_sections(
        self,
        fc: FaultCode,
        products: List[Product],
        word_count: int,
        tone: str
    ) -> List[Dict]:
        """Generate article sections using AI."""
        
        # Build prompt for Grok
        prompt = self._build_content_prompt(fc, products, word_count, tone)
        
        try:
            response = await llm_service.generate_content(
                product_info={"fault_code": fc.code},
                context=[],
                system_prompt=self._get_content_system_prompt(tone),
                provider="grok",
                model_name="grok-4.3"
            )
            
            # Parse response
            content = self._parse_content_response(response, fc, products)
            return content
            
        except Exception as e:
            logger.error(f"AI content generation failed for {fc.code}: {e}")
            # Fallback to template
            return self._generate_template_sections(fc, products)
    
    def _build_content_prompt(
        self,
        fc: FaultCode,
        products: List[Product],
        word_count: int,
        tone: str
    ) -> str:
        """Build prompt for content generation."""
        
        product_list = []
        for p in products[:5]:
            product_list.append({
                "title": p.title,
                "type": p.product_type,
                "price": p.price,
                "is_kit": self._is_kit_product(p)
            })
        
        return f"""Generate a comprehensive blog article about fault code {fc.code}.

FAULT CODE INFORMATION:
- Code: {fc.code}
- Name: {fc.name}
- Description: {fc.description}
- Symptoms: {json.dumps(fc.symptoms_text or [], ensure_ascii=False)}
- Common Causes: {json.dumps(fc.common_causes or [], ensure_ascii=False)}
- Affected Transmissions: {json.dumps(fc.transmissions or [], ensure_ascii=False)}

RECOMMENDED PRODUCTS:
```json
{json.dumps(product_list, indent=2, ensure_ascii=False)}
```

REQUIREMENTS:
1. Target word count: {word_count} words
2. Tone: {tone} (professional, friendly, or technical)
3. Structure with clear H2 headings
4. Include product recommendations naturally integrated
5. Write in Spanish (Mexico) for Mexican mechanics
6. Focus on practical solutions, not just theory

OUTPUT FORMAT (JSON):
{{
  "sections": [
    {{
      "heading": "H2 heading text",
      "content": "Section content in HTML/markdown",
      "type": "intro|symptoms|causes|solution|products|cta"
    }}
  ]
}}"""
    
    def _get_content_system_prompt(self, tone: str) -> str:
        """Get system prompt for content generation."""
        tone_instructions = {
            "professional": "Use professional, authoritative language suitable for mechanics.",
            "friendly": "Use approachable, helpful language that builds trust.",
            "technical": "Use detailed technical language for experienced mechanics."
        }
        
        return f"""You are an expert automotive transmission technician and SEO content writer.

Your task is to write blog articles that:
1. Answer mechanic's questions completely
2. Rank well in Google (SEO optimized)
3. Drive product sales naturally
4. Are cited by AI engines like Grok and Perplexity

{tone_instructions.get(tone, tone_instructions['professional'])}

Writing guidelines:
- Start with a strong hook that addresses the pain point
- Use the fault code name naturally in the first paragraph
- Include specific symptoms mechanics will recognize
- Explain causes in order of likelihood
- Recommend products as solutions, not just options
- End with a clear call-to-action
- Use Mexican Spanish terminology (mecanico, transmision, refacciones)

Respond ONLY with valid JSON matching the requested format."""
    
    def _parse_content_response(self, response: Dict, fc: FaultCode, products: List[Product]) -> List[Dict]:
        """Parse AI content response."""
        try:
            if isinstance(response, dict):
                content = response.get("content", response)
            else:
                content = str(response)
            
            # Extract JSON
            if isinstance(content, str):
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start >= 0:
                    data = json.loads(content[json_start:json_end])
                else:
                    data = json.loads(content)
            else:
                data = content
            
            sections = data.get("sections", [])
            
            # Ensure proper structure
            for section in sections:
                if "type" not in section:
                    section["type"] = "content"
            
            return sections
            
        except Exception as e:
            logger.error(f"Failed to parse content response: {e}")
            return self._generate_template_sections(fc, products)
    
    def _generate_template_sections(self, fc: FaultCode, products: List[Product]) -> List[Dict]:
        """Generate fallback template sections."""
        sections = []
        
        # Intro
        sections.append({
            "heading": f"¿Qué es el Código {fc.code}?",
            "content": f"""<p>El código de falla <strong>{fc.code}</strong> - {fc.name} - es uno de los problemas más comunes que enfrentan los mecánicos mexicanos. {fc.description or ''}</p>

<p>Si estás viendo este código en tu escáner OBDII, es importante entender qué lo causa y cómo solucionarlo correctamente. En este artículo te explicamos todo lo que necesitas saber.</p>""",
            "type": "intro"
        })
        
        # Symptoms
        symptoms_list = "".join([f"<li>{s}</li>" for s in (fc.symptoms_text or [])[:5]])
        sections.append({
            "heading": f"Síntomas del Código {fc.code}",
            "content": f"""<p>Cuando aparece el código {fc.code}, es común observar los siguientes síntomas:</p>

<ul>
{symptoms_list}
</ul>

<p>Si reconoces varios de estos síntomas en el vehículo que estás reparando, es muy probable que el problema sea este código de falla.</p>""",
            "type": "symptoms"
        })
        
        # Causes
        causes_list = "".join([f"<li>{c}</li>" for c in (fc.common_causes or [])[:5]])
        sections.append({
            "heading": "Causas Más Comunes",
            "content": f"""<p>El código {fc.code} puede tener varias causas. Estas son las más frecuentes:</p>

<ul>
{causes_list}
</ul>

<p>La mayoría de las veces, el problema se resuelve reemplazando la pieza defectuosa con una refacción de calidad.</p>""",
            "type": "causes"
        })
        
        # Products (if available)
        if products:
            kit_products = [p for p in products if self._is_kit_product(p)][:2]
            other_products = [p for p in products if not self._is_kit_product(p)][:3]
            
            product_html = "<div class='product-recommendations'>"
            
            for p in kit_products + other_products:
                product_html += f"""
<div class='product-card'>
    <h4>{p.title}</h4>
    <p class='price'>${p.price}</p>
    <p>{p.product_type or 'Refacción de transmisión'}</p>
    <a href='/products/{p.handle}' class='btn'>Ver Producto</a>
</div>"""
            
            product_html += "</div>"
            
            sections.append({
                "heading": f"Productos Recomendados para Solucionar {fc.code}",
                "content": f"""<p>En Example Store tenemos los productos específicos para resolver el código {fc.code}. Estas son nuestras recomendaciones basadas en la experiencia de miles de mecánicos:</p>

{product_html}

<p>Estos productos son compatibles con las transmisiones {', '.join((fc.transmissions or [])[:3])}.</p>""",
                "type": "products"
            })
        
        # CTA
        sections.append({
            "heading": "¿Necesitas Ayuda?",
            "content": f"""<p>Si tienes dudas sobre qué producto necesitas para resolver el código {fc.code}, nuestro equipo de expertos está listo para ayudarte.</p>

<p><strong>Contáctanos:</strong></p>
<ul>
<li>WhatsApp: +52 55 XXXX XXXX</li>
<li>Email: soporte@example-store.com</li>
<li>Teléfono: +52 55 XXXX XXXX</li>
</ul>

<p>En Example Store hemos ayudado a más de 10,000 mecánicos en México. ¡Confía en los expertos!</p>""",
            "type": "cta"
        })
        
        return sections
    
    def _generate_title(self, fc: FaultCode) -> str:
        """Generate SEO-optimized title."""
        transmissions = fc.transmissions or []
        transmission_str = transmissions[0] if transmissions else "Transmisión"
        
        titles = [
            f"Código {fc.code}: {fc.name} - Guía de Diagnóstico y Solución [{transmission_str}]",
            f"{fc.code} {transmission_str}: Causas, Síntomas y Cómo Repararlo",
            f"Código de Falla {fc.code} - Todo lo que Necesitas Saber | Example Store"
        ]
        
        # Pick based on traffic
        if fc.monthly_clicks and fc.monthly_clicks > 500:
            return titles[0]  # Most descriptive for high traffic
        return titles[1]
    
    def _generate_meta_description(self, fc: FaultCode, products: List[Product]) -> str:
        """Generate meta description."""
        kit_count = sum(1 for p in products if self._is_kit_product(p))
        
        desc = f"Código {fc.code} - {fc.name}. "
        desc += f"Descubre las causas, síntomas y soluciones. "
        
        if kit_count > 0:
            desc += f"Kits de reparación disponibles. "
        
        desc += "Envío a todo México. Expertos en transmisiones automáticas."
        
        return desc[:160]  # Keep under 160 chars
    
    def _generate_faq_schema(self, fc: FaultCode, products: List[Product]) -> Dict:
        """Generate FAQPage Schema.org markup."""
        questions = [
            {
                "question": f"¿Qué significa el código {fc.code}?",
                "answer": fc.description or f"El código {fc.code} indica {fc.name}."
            },
            {
                "question": f"¿Cuáles son los síntomas del código {fc.code}?",
                "answer": "Los síntomas más comunes son: " + ", ".join((fc.symptoms_text or [])[:3]) + "."
            },
            {
                "question": f"¿Cómo se repara el código {fc.code}?",
                "answer": "La reparación depende de la causa. Las soluciones más comunes incluyen: " + ", ".join((fc.common_causes or [])[:2]) + "."
            }
        ]
        
        if products:
            questions.append({
                "question": f"¿Qué producto necesito para el código {fc.code}?",
                "answer": f"Para resolver el código {fc.code} recomendamos: {products[0].title}. Este producto es compatible con transmisiones {', '.join((fc.transmissions or [])[:2])}."
            })
        
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": q["answer"]
                    }
                }
                for q in questions
            ]
        }
    
    def _generate_howto_schema(self, fc: FaultCode, products: List[Product]) -> Dict:
        """Generate HowTo Schema.org markup."""
        steps = [
            {
                "@type": "HowToStep",
                "position": 1,
                "name": "Identificar el código de falla",
                "text": f"Conecta el escáner OBDII y confirma que el código presente es {fc.code}.",
                "url": f"https://example-store.com/blogs/news/{fc.code.lower()}#step1"
            },
            {
                "@type": "HowToStep",
                "position": 2,
                "name": "Verificar síntomas",
                "text": "Revisa que los síntomas coincidan con los descritos en la guía técnica.",
                "url": f"https://example-store.com/blogs/news/{fc.code.lower()}#step2"
            },
            {
                "@type": "HowToStep",
                "position": 3,
                "name": "Diagnosticar la causa",
                "text": f"Las causas más comunes de {fc.code} son: " + ", ".join((fc.common_causes or [])[:2]) + ".",
                "url": f"https://example-store.com/blogs/news/{fc.code.lower()}#step3"
            }
        ]
        
        if products:
            steps.append({
                "@type": "HowToStep",
                "position": 4,
                "name": "Reemplazar las piezas defectuosas",
                "text": f"Instala el producto recomendado: {products[0].title}.",
                "url": f"https://example-store.com/blogs/news/{fc.code.lower()}#step4"
            })
        
        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": f"Cómo reparar el código {fc.code}",
            "description": f"Guía paso a paso para diagnosticar y reparar el código de falla {fc.code} - {fc.name}",
            "totalTime": "PT2H",
            "estimatedCost": {
                "@type": "MonetaryAmount",
                "currency": "MXN",
                "value": products[0].price if products else "2000"
            },
            "step": steps
        }
    
    def _generate_keywords(self, fc: FaultCode) -> List[str]:
        """Generate target keywords."""
        keywords = [
            fc.code,
            f"codigo {fc.code}",
            f"código {fc.code}",
            f"{fc.code} solucion",
            f"{fc.code} reparar"
        ]
        
        for transmission in (fc.transmissions or [])[:2]:
            keywords.append(f"{fc.code} {transmission}")
        
        return keywords
    



# Factory function
def get_blog_generator(db: Session) -> BlogContentGenerator:
    """Get BlogContentGenerator instance."""
    return BlogContentGenerator(db)
