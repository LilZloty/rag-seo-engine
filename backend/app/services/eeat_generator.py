"""
E-E-A-T Authority Generator
============================

Generates E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)
content boxes for articles to boost credibility with both users and AI engines.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("eeat_generator")


@dataclass
class EEATBox:
    """E-E-A-T content box data."""
    title: str
    badge_text: str
    statistics: List[Dict[str, str]]
    expertise_proof: List[str]
    trust_signals: List[str]
    cta_text: str
    html_output: str


class EEATAuthorityGenerator:
    """
    Generates authority content boxes that build trust.
    
    Key elements:
    - Experience: Years in business, customers served
    - Expertise: Technical knowledge, certifications
    - Authoritativeness: Industry recognition, data-backed claims
    - Trustworthiness: Guarantees, reviews, transparency
    """
    
    # Company constants
    COMPANY_STATS = {
        "customers_served": "10,000+",
        "years_experience": "15+",
        "success_rate": "94%",
        "warranty_months": "12",
        "support_hours": "24/7",
        "products_count": "850+",
        "transmissions_covered": "120+",
        "mechanics_helped": "10,000+",
        "response_time": "< 2 horas"
    }
    
    EXPERTISE_SIGNALS = [
        "Especialistas certificados en transmisiones automáticas",
        "Diagnóstico técnico respaldado por datos reales",
        "Ingenieros con 15+ años de experiencia",
        "Centro de servicio autorizado",
        "Técnicos certificados ASE",
    ]
    
    TRUST_SIGNALS = [
        "Garantía de 12 meses en todos los productos",
        "Envío express a todo México (1-3 días)",
        "Devolución sin preguntas en 30 días",
        "Soporte técnico gratuito post-compra",
        "Piezas 100% compatibles garantizadas",
        "Precios sin intermediarios",
        "Más de 2,000 reseñas verificadas",
    ]
    
    def generate_authority_box(
        self,
        context: str = "general",
        fault_code: Optional[str] = None,
        transmission: Optional[str] = None
    ) -> EEATBox:
        """
        Generate an E-E-A-T authority box.
        
        Args:
            context: 'general', 'product', 'guide', 'comparison'
            fault_code: Optional fault code for specific context
            transmission: Optional transmission for specific context
        """
        # Customize based on context
        if context == "product":
            title = "Por qué comprar en Example Store"
            badge_text = "VENDEDOR CERTIFICADO"
            stats = [
                {"label": "Clientes satisfechos", "value": self.COMPANY_STATS["customers_served"]},
                {"label": "Tasa de éxito", "value": self.COMPANY_STATS["success_rate"]},
                {"label": "Garantía", "value": f"{self.COMPANY_STATS['warranty_months']} meses"},
                {"label": "Tiempo de respuesta", "value": self.COMPANY_STATS["response_time"]},
            ]
        elif context == "guide":
            title = "Guía técnica verificada"
            badge_text = "CONTENIDO EXPERTO"
            stats = [
                {"label": "Mecánicos ayudados", "value": self.COMPANY_STATS["mechanics_helped"]},
                {"label": "Años de experiencia", "value": self.COMPANY_STATS["years_experience"]},
                {"label": "Transmisiones cubiertas", "value": self.COMPANY_STATS["transmissions_covered"]},
                {"label": "Productos disponibles", "value": self.COMPANY_STATS["products_count"]},
            ]
        else:
            title = "Expertos en transmisiones automáticas"
            badge_text = "E-E-A-T VERIFIED"
            stats = [
                {"label": "Mecánicos ayudados", "value": self.COMPANY_STATS["mechanics_helped"]},
                {"label": "Años de experiencia", "value": self.COMPANY_STATS["years_experience"]},
                {"label": "Tasa de éxito", "value": self.COMPANY_STATS["success_rate"]},
                {"label": "Garantía real", "value": f"{self.COMPANY_STATS['warranty_months']} meses"},
            ]
        
        # Generate HTML
        html = self._generate_html(title, badge_text, stats, context)
        
        return EEATBox(
            title=title,
            badge_text=badge_text,
            statistics=stats,
            expertise_proof=self.EXPERTISE_SIGNALS[:3],
            trust_signals=self.TRUST_SIGNALS[:5],
            cta_text="¿Dudas? Contácta a nuestros expertos",
            html_output=html
        )
    
    def _generate_html(self, title: str, badge: str, stats: List[Dict], context: str) -> str:
        """Generate HTML for the authority box."""
        stats_html = "\n".join([
            f'''<div class="stat-item">
                <div class="stat-value">{stat["value"]}</div>
                <div class="stat-label">{stat["label"]}</div>
            </div>'''
            for stat in stats
        ])
        
        expertise_html = "\n".join([
            f'<li>✓ {signal}</li>'
            for signal in self.EXPERTISE_SIGNALS[:3]
        ])
        
        trust_html = "\n".join([
            f'<li>✓ {signal}</li>'
            for signal in self.TRUST_SIGNALS[:5]
        ])
        
        return f'''<div class="eeat-authority-box" itemscope itemtype="https://schema.org/Organization">
    <meta itemprop="name" content="Example Store" />
    <meta itemprop="url" content="https://example-store.com" />
    <meta itemprop="@id" content="https://example-store.com/#organization" />
    
    <div class="eeat-badge">{badge}</div>
    <h3 class="eeat-title">{title}</h3>
    
    <div class="eeat-stats-grid">
        {stats_html}
    </div>
    
    <div class="eeat-sections">
        <div class="eeat-expertise">
            <h4>Nuestra Experiencia</h4>
            <ul>{expertise_html}</ul>
        </div>
        
        <div class="eeat-trust">
            <h4>Confianza Garantizada</h4>
            <ul>{trust_html}</ul>
        </div>
    </div>
    
    <div class="eeat-cta">
        <p>📞 ¿Dudas? Habla con un experto: <strong>55-XXXX-XXXX</strong></p>
        <p class="eeat-hours">Horario: Lunes a Viernes 9:00 - 18:00</p>
    </div>
</div>'''
    
    def generate_product_specific_box(
        self,
        product_name: str,
        fault_code: Optional[str] = None,
        compatibility_rate: str = "98%",
        installation_time: str = "3-4 horas"
    ) -> EEATBox:
        """Generate product-specific authority box."""
        title = f"¿Por qué elegir {product_name}?"
        badge_text = "KIT VERIFICADO"
        
        stats = [
            {"label": "Compatibilidad", "value": compatibility_rate},
            {"label": "Tiempo instalación", "value": installation_time},
            {"label": "Garantía", "value": "12 meses"},
            {"label": "Soporte incluido", "value": "24/7"},
        ]
        
        return self.generate_authority_box("product")
    
    # Phase 3.3 — schema.org Organization entity for Example Store as the seller.
    # Emitted into product_schema_json @graph so AI engines (ChatGPT, Google AI
    # Shopping, Perplexity) can attribute trust signals to the seller alongside
    # the product. Only includes claims Theo explicitly approved on 2026-05-20:
    # areaServed, knowsAbout, customers_served, years_experience.
    # Excluded: warranty/success_rate/support_hours/response_time/products_count
    # (the last is stale — actual catalog is 5000+ SKUs, not 850+).
    ORG_NAME = "Example Store"
    ORG_URL = "https://example-store.com"
    ORG_ID = "https://example-store.com/#organization"
    ORG_AREA_SERVED = "Mexico"
    ORG_KNOWS_ABOUT = [
        "Transmisiones automáticas",
        "Refacciones de transmisión",
        "Kits de reparación de transmisión",
        "Solenoides de transmisión",
        "Convertidores de torque",
        "Embragues y discos de transmisión",
    ]

    def build_organization_entity(self) -> Dict[str, object]:
        """Schema.org Organization entity for the consolidated product_schema_json @graph.

        Single source of truth — both content_generator.generate_for_product
        and the /generate-schema endpoint call this so the entity stays
        identical across the two write paths.
        """
        return {
            "@type": "Organization",
            "@id": self.ORG_ID,
            "name": self.ORG_NAME,
            "url": self.ORG_URL,
            "areaServed": {
                "@type": "Country",
                "name": self.ORG_AREA_SERVED,
            },
            "knowsAbout": list(self.ORG_KNOWS_ABOUT),
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": "Customers Served",
                    "value": self.COMPANY_STATS["customers_served"],
                },
                {
                    "@type": "PropertyValue",
                    "name": "Years Experience",
                    "value": self.COMPANY_STATS["years_experience"],
                },
            ],
        }

    def generate_comparison_box(
        self,
        code_a: str,
        code_b: str
    ) -> str:
        """Generate authority box for comparison articles."""
        return f'''<div class="eeat-comparison-note">
    <p><strong>Nota de nuestros expertos:</strong> 
    Esta comparación entre {code_a} y {code_b} está basada en datos reales de 
    {self.COMPANY_STATS['mechanics_helped']} reparaciones realizadas por mecánicos mexicanos. 
    Nuestros ingenieros certificados verifican toda la información técnica.</p>
    
    <p class="eeat-data-date">Última actualización: {datetime.now().strftime("%B %Y")}</p>
</div>'''


# Singleton instance
_eeat_generator = None


def get_eeat_generator() -> EEATAuthorityGenerator:
    """Get E-E-A-T generator instance."""
    global _eeat_generator
    if _eeat_generator is None:
        _eeat_generator = EEATAuthorityGenerator()
    return _eeat_generator
