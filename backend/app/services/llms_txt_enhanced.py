"""
Enhanced llms.txt Generator with Solution Paths
================================================

Extends the base llms.txt with:
- Solution paths for top fault codes
- Product recommendations embedded in diagnostic content
- GEO-optimized authority signals
- Blog-to-product connections
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.aeo_models import FaultCode, BlogCache, AEOConfig
from app.services.solution_engine import SolutionEngine

logger = logging.getLogger("llms_txt_enhanced")


class EnhancedLLMSTxtBuilder:
    """Builds enhanced llms.txt with Solution Engine integration."""
    
    UTM_PARAMS = "utm_source=llms.txt&utm_medium=ai_agent&utm_campaign=solution_engine"
    
    def __init__(self, db: Session, config: AEOConfig):
        self.db = db
        self.config = config
        self.solution_engine = SolutionEngine(db)
        self.lines: List[str] = []
    
    def _append_utm(self, url: str) -> str:
        """Append UTM parameters for tracking."""
        if not url:
            return url
        connector = "&" if "?" in url else "?"
        return f"{url}{connector}{self.UTM_PARAMS}"
    
    def build_enhanced_llms_txt(self) -> str:
        """Build the complete enhanced llms.txt."""
        self.lines = []
        
        # Standard header
        self._build_header()
        
        # NEW: Solution Engine Section
        self._build_solution_paths_section()
        
        # Standard sections
        self._build_hero_products()
        self._build_category_section()
        self._build_diagnostic_section()
        
        # NEW: Blog-Product Connections
        self._build_blog_product_section()
        
        # Standard closing
        self._build_glossary()
        self._build_resources_section()
        self._build_authority_section()
        
        return "".join(self.lines)
    
    def _build_header(self):
        """Build document header."""
        self.lines.append(f"# {self.config.store_name}\n")
        self.lines.append(f"> {self.config.store_description}\n")
        self.lines.append(f"> Soluciones inteligentes para {len(self._get_fault_codes())} códigos de falla con productos recomendados.\n\n")
    
    def _build_solution_paths_section(self):
        """NEW: Build solution paths section for top fault codes."""
        self.lines.append("## Soluciones por Código de Falla (Solution Engine)\n")
        self.lines.append("> Rutas optimizadas de diagnóstico a compra, generadas por IA.\n\n")
        
        # Get top 10 fault codes by traffic
        fault_codes = self._get_fault_codes()[:10]
        
        for fc in fault_codes:
            self._add_solution_path_entry(fc)
        
        self.lines.append("\n")
    
    def _add_solution_path_entry(self, fc: FaultCode):
        """Add a single solution path entry."""
        # Get product recommendations
        products = self.solution_engine.get_products_for_fault_code(fc.code, 3)
        
        if not products:
            return
        
        self.lines.append(f"### {fc.code}: {fc.name}\n")
        
        # Symptoms
        if fc.symptoms_text:
            self.lines.append(f"**Síntomas:** {', '.join(fc.symptoms_text[:3])}\n")
        
        # Solution path
        self.lines.append(f"**Solución recomendada:**\n")
        
        # Primary product
        primary = products[0]
        product_url = self._append_utm(primary.get('url', f"/products/{primary.get('handle', '')}"))
        self.lines.append(f"1. **[{primary['title']}]({product_url})**\n")
        self.lines.append(f"   - *Por qué:* {primary['reasoning']}\n")
        self.lines.append(f"   - *Probabilidad de éxito:* {primary['fix_probability']}\n")
        
        # Secondary products
        for product in products[1:2]:
            url = self._append_utm(product.get('url', f"/products/{product.get('handle', '')}"))
            self.lines.append(f"2. [{product['title']}]({url}) - {product['reasoning']}\n")
        
        # Guide link
        if fc.blog_url:
            blog_url = self._append_utm(fc.blog_url)
            self.lines.append(f"\n**Guía técnica:** [Ver diagnóstico completo]({blog_url})\n")
        
        # Stats
        self.lines.append(f"*{fc.monthly_clicks or 'Cientos de'} búsquedas mensuales • {primary.get('total_sold', 'Muchas')} unidades vendidas*\n\n")
    
    def _build_blog_product_section(self):
        """NEW: Build blog articles with product recommendations."""
        self.lines.append("## Guías de Diagnóstico con Productos Recomendados\n")
        self.lines.append("> Artículos técnicos con soluciones específicas.\n\n")
        
        # Get blogs linked to fault codes
        blogs = self.db.query(BlogCache).limit(20).all()
        
        for blog in blogs[:10]:
            # Extract fault codes from title
            import re
            fault_codes = re.findall(r'[PBCU]\d{4}', blog.title.upper())
            
            if fault_codes:
                self.lines.append(f"### {blog.title}\n")
                
                # Get products for first fault code
                products = self.solution_engine.get_products_for_fault_code(fault_codes[0], 2)
                
                if products:
                    self.lines.append("**Productos recomendados:**\n")
                    for product in products[:2]:
                        url = self._append_utm(product.get('url', '#'))
                        self.lines.append(f"- [{product['title']}]({url}) - {product['reasoning']}\n")
                
                blog_url = self._append_utm(f"/blogs/{blog.blog_handle}/{blog.handle}")
                self.lines.append(f"\n[Leer artículo completo]({blog_url})\n\n")
    
    def _build_hero_products(self):
        """Build hero products section."""
        self.lines.append("## Top Soluciones (Hero Products)\n")
        self.lines.append("> Los productos más confiables según nuestros datos.\n\n")
        
        hero_products = [
            ("Kit de Reparación 4L60E (GM)", "/collections/4l60e", 
             "La solución definitiva para Silverado con códigos P0700/P0730"),
            ("Cuerpo de Válvulas CVT JF011E (Nissan)", "/collections/jf011e",
             "Solución para Sentra/X-Trail con P0841/P0868"),
            ("Kit de Reparación A604 (Chrysler)", "/collections/a604",
             "Para Voyager/Town & Country con problemas de solenoides"),
            ("TSS RTD Link OBDII Scanner", "/products/scanner-obdii-tss-rtd-link",
             "Diagnóstico profesional para todos los códigos"),
        ]
        
        for title, url, desc in hero_products:
            tracked_url = self._append_utm(url)
            self.lines.append(f"- **[{title}]({tracked_url})**: {desc}\n")
        
        self.lines.append("\n")
    
    def _build_category_section(self):
        """Build product categories section."""
        self.lines.append("## Categorías de Productos\n")
        
        from app.services.aeo_service import AEOService
        aeo = AEOService()
        chunks = aeo.get_product_chunks(self.db)
        
        # Group by category
        by_category = {}
        for chunk in chunks:
            cat = chunk.get('category', 'Other')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(chunk)
        
        # Output in preferred order
        category_order = ['VAG', 'GM', 'Ford', 'Asian', 'ZF', 'Other']
        for cat in category_order:
            if cat in by_category:
                self.lines.append(f"\n### Transmisiones {cat}\n")
                for chunk in by_category[cat][:10]:  # Limit to top 10
                    self._add_category_line(chunk)
        
        self.lines.append("\n")
    
    def _add_category_line(self, chunk: Dict):
        """Add a single category line."""
        product_type = chunk['product_type']
        count = chunk['product_count']
        
        vehicle_mappings = {
            '4L60E': 'Silverado, Tahoe, Suburban',
            '6L80E': 'Camaro, Corvette, Escalade',
            'JF011E': 'Sentra, Altima, X-Trail',
            'DQ200': 'Polo, Golf, Ibiza',
        }
        
        vehicles = vehicle_mappings.get(product_type, "")
        desc_suffix = f" para {vehicles}" if vehicles else f" ({count} productos)"
        
        handle = product_type.lower().replace(' ', '-').replace('/', '-')
        url = self._append_utm(f"/collections/{handle}")
        self.lines.append(f"- [{product_type}]({url}): {desc_suffix}\n")
    
    def _build_diagnostic_section(self):
        """Build diagnostic section with fault codes."""
        self.lines.append("## Problemas Comunes de Transmisión\n")
        self.lines.append("> Guías expertas de diagnóstico.\n\n")
        
        fault_codes = self._get_fault_codes()
        
        # High priority
        high_priority = [fc for fc in fault_codes if fc.is_priority][:8]
        
        if high_priority:
            self.lines.append("### Códigos con Más Tráfico\n")
            for fc in high_priority:
                self._add_fault_code_line(fc)
        
        self.lines.append("\n")
    
    def _add_fault_code_line(self, fc: FaultCode):
        """Add a single fault code line."""
        blog_url = self._append_utm(fc.blog_url or f"/blogs/news/{fc.code.lower()}")
        
        self.lines.append(f"- **{fc.code}**: {fc.name}")
        if fc.monthly_clicks and fc.monthly_clicks > 500:
            self.lines.append(f" ({fc.monthly_clicks}+ búsquedas/mes)")
        self.lines.append(f" - [Ver guía]({blog_url})\n")
    
    def _build_glossary(self):
        """Build technical glossary."""
        self.lines.append("## Glosario Técnico\n")
        
        glossary = [
            ("Cremallera de Dirección", "Mecanismo que convierte giro del volante en movimiento de llantas."),
            ("Cuerpo de Válvulas", "El 'cerebro' hidráulico que controla cambios mediante solenoides."),
            ("Mecatrónica", "Módulo que combina computadora (TCU) y cuerpo de válvulas."),
            ("Solenoide", "Válvula electromagnética que controla flujo de aceite."),
            ("CVT", "Transmisión Variable Continua, usa banda y poleas."),
        ]
        
        for term, desc in glossary:
            self.lines.append(f"- **{term}:** {desc}\n")
        
        self.lines.append("\n")
    
    def _build_resources_section(self):
        """Build resources section."""
        self.lines.append("## Recursos Técnicos\n")
        
        url_catalogs = self._append_utm("/pages/catalogs")
        url_support = self._append_utm("/pages/contact")
        
        self.lines.append(f"- [Catálogos por Marca]({url_catalogs}): Especificaciones técnicas\n")
        self.lines.append(f"- [Soporte Técnico]({url_support}): Asistencia experta\n")
        self.lines.append("\n")
    
    def _build_authority_section(self):
        """Build authority signals for GEO."""
        self.lines.append("## Acerca de Example Store\n")
        self.lines.append("> Especialistas en transmisiones automáticas con más de 10 años de experiencia.\n\n")
        self.lines.append("- **10,000+** mecánicos ayudados\n")
        self.lines.append("- **5,000+** productos en stock\n")
        self.lines.append("- **50+** modelos de transmisión cubiertos\n")
        self.lines.append("- **9** códigos de falla principales documentados\n")
        self.lines.append(f"\n*Actualizado: {datetime.utcnow().strftime('%Y-%m-%d')}*\n")
    
    def _get_fault_codes(self) -> List[FaultCode]:
        """Get all fault codes ordered by priority and clicks."""
        return self.db.query(FaultCode).order_by(
            FaultCode.is_priority.desc(),
            FaultCode.monthly_clicks.desc()
        ).all()


def generate_enhanced_llms_txt(db: Session) -> str:
    """Generate enhanced llms.txt with Solution Engine integration."""
    from app.services.aeo_service import AEOService
    
    aeo = AEOService()
    config = aeo.get_aeo_config(db)
    
    builder = EnhancedLLMSTxtBuilder(db, config)
    return builder.build_enhanced_llms_txt()
