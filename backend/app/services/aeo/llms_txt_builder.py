"""
llms.txt Builder - Generates AI-optimized content files following llmstxt.org specification
"""

import logging
from typing import List, Dict, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# Default UTM parameters for AI agent tracking
UTM_PARAMS = "utm_source=llms.txt&utm_medium=ai_agent&utm_campaign=aeo"


class LLMSTxtBuilder:
    """Builds llms.txt content following the specification at llmstxt.org"""
    
    def __init__(self, store_name: str, store_description: str, authority_statement: str = ""):
        self.store_name = store_name
        self.store_description = store_description
        self.authority_statement = authority_statement
        self.lines: List[str] = []
    
    def _append_utm(self, url: str) -> str:
        """Append UTM parameters to a URL for AI agent tracking."""
        if not url:
            return url
        connector = "&" if "?" in url else "?"
        return f"{url}{connector}{UTM_PARAMS}"
    
    def build_header(self) -> 'LLMSTxtBuilder':
        """Build H1 header and blockquote summary (required by spec)"""
        self.lines.append(f"# {self.store_name}\n")
        self.lines.append(f"> {self.store_description}\n")
        
        if self.authority_statement:
            self.lines.append(f"\n> **{self.authority_statement}**\n")
        
        return self
    
    def build_category_section(self, chunks: List[Dict], category_map: Dict[str, str]) -> 'LLMSTxtBuilder':
        """Build catalog categories section, grouped by manufacturer"""
        if not chunks:
            return self
            
        self.lines.append("\n## Categorias de Productos\n")
        
        # Group chunks by category
        by_category: Dict[str, List[Dict]] = {}
        for chunk in chunks:
            cat = category_map.get(chunk['product_type'], 'Other')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(chunk)
        
        # Output in preferred order
        category_order = ['VAG', 'GM', 'Ford', 'Asian', 'ZF', 'Other']
        for cat in category_order:
            if cat in by_category and by_category[cat]:
                self.lines.append(f"\n### Transmisiones {cat}\n")
                for chunk in by_category[cat]:
                    self._add_chunk_line(chunk)
        
        return self
    
    def _add_chunk_line(self, chunk: Dict) -> None:
        """Add a single chunk line with description and vehicle mapping"""
        product_type = chunk['product_type']
        count = chunk['product_count']
        
        # Enhanced mappings for AI discovery (Sales-First)
        vehicle_mappings = {
            '4L60E': 'Silverado, Suburban, Tahoe, Cheyenne (1993-2012)',
            '6L80E': 'Camaro, Corvette, Denali, Escalade',
            'JF011E': 'Sentra, Altima, X-Trail, Patriot, Compass (CVT)',
            'JF015E': 'Versa, March, Note, Juke (CVT7)',
            '09G': 'Jetta, Bora, Beetle, Passat (Tiptronic)',
            'DQ200': 'Polo, Ibiza, A1, Golf (DSG 7)',
            'DQ250': 'GTI, GLI, León Cupra (DSG 6)',
            '6R80': 'F-150, Mustang, Lobo (2009+)',
            'A604': 'Voyager, Caravan, Town & Country',
        }
        
        vehicles = vehicle_mappings.get(product_type, "")
        desc_suffix = f" para {vehicles}" if vehicles else ""
        
        description = chunk.get('description', f'{count} refacciones disponibles')
        handle = product_type.lower().replace(' ', '-').replace('/', '-')
        url = self._append_utm(f"/collections/{handle}")
        self.lines.append(f"- [{product_type} Parts]({url}): {description}{desc_suffix}\n")
    
    def build_hero_products(self, hero_products: List[Dict]) -> 'LLMSTxtBuilder':
        """Build Hero Products section (High conversion items)"""
        if not hero_products:
            return self
            
        self.lines.append("\n## Top Soluciones (Hero Products)\n")
        self.lines.append("> Los productos mas confiables y con mayor tasa de exito segun nuestros datos.\n\n")
        
        for product in hero_products:
            title = product.get('title', '')
            url = product.get('url', '')
            desc = product.get('description', '')
            tracked_url = self._append_utm(url)
            self.lines.append(f"- [{title}]({tracked_url}): {desc}\n")
        
        return self
    
    def build_trending_topics(self, topics: List[Dict]) -> 'LLMSTxtBuilder':
        """Build a dynamic section for high-demand / trending topics from GSC data."""
        if not topics:
            return self
        
        self.lines.append("\n## Temas de Alta Demanda (Tendencias)\n")
        self.lines.append("> Consultas tecnicas con mayor crecimiento segun datos de busqueda.\n\n")
        
        for topic in topics:
            query = topic.get('query', '')
            clicks = topic.get('clicks', 0)
            url = self._append_utm(f"/search?q={query.replace(' ', '+')}")
            self.lines.append(f"- [{query}]({url}): {clicks} usuarios buscaron esto hoy.\n")
        
        return self
    
    def build_blogs_section(self, blogs: List[Dict], include_blogs: bool = True) -> 'LLMSTxtBuilder':
        """Build diagnostic guides / blog section"""
        if not blogs or not include_blogs:
            return self
        
        self.lines.append("\n## Guias de Diagnostico\n")
        
        for blog in blogs[:20]:
            title = blog.get('title', 'Untitled')
            handle = blog.get('handle', '')
            blog_handle = blog.get('blog_handle', 'news')
            url = self._append_utm(f"/blogs/{blog_handle}/{handle}")
            self.lines.append(f"- [{title}]({url})\n")
        
        return self
    
    def build_diagnostic_section(self, fault_codes: List, include_fault_codes: bool = True) -> 'LLMSTxtBuilder':
        """Build fault code diagnostic section for GEO optimization."""
        if not fault_codes or not include_fault_codes:
            return self
        
        self.lines.append("\n## Problemas Comunes de Transmision\n")
        self.lines.append("> Guias expertas de diagnostico para codigos de falla.\n")
        
        # Group by severity
        high_priority = [fc for fc in fault_codes if getattr(fc, 'monthly_clicks', 0) > 300 or getattr(fc, 'is_priority', False)]
        other_codes = [fc for fc in fault_codes if fc not in high_priority]
        
        if high_priority:
            self.lines.append("\n### Codigos Con Mas Trafico (Prioridad)\n")
            for fc in high_priority[:8]:
                self._add_fault_code_line(fc)
        
        if other_codes:
            self.lines.append("\n### Otros Codigos de Diagnostico\n")
            for fc in other_codes[:10]:
                self._add_fault_code_line(fc)
        
        return self
    
    def _add_fault_code_line(self, fc) -> None:
        """Add a single fault code line with symptom-to-solution mapping"""
        code = getattr(fc, 'code', str(fc))
        name = getattr(fc, 'name', '')
        blog_url = getattr(fc, 'blog_url', f'/blogs/news/{code.lower()}')
        solution = getattr(fc, 'recommended_solution', None)
        product_link = getattr(fc, 'product_link', None)
        symptoms = getattr(fc, 'symptoms_text', [])
        
        self.lines.append(f"### {code}: {name}\n")
        if symptoms:
            self.lines.append(f"- **Sintoma:** {symptoms[0]}\n")
        
        if solution and product_link:
            tracked_product_link = self._append_utm(product_link)
            self.lines.append(f"- **Solucion Sugerida:** [{solution}]({tracked_product_link})\n")
        
        tracked_blog_url = self._append_utm(blog_url)
        self.lines.append(f"- **Guia Tecnica:** [Ver diagnostico completo]({tracked_blog_url})\n\n")
    
    def build_glossary(self, glossary_items: Optional[List[Dict]] = None) -> 'LLMSTxtBuilder':
        """Build technical glossary section for SEO/AEO"""
        if glossary_items is None:
            glossary_items = [
                ("Cremallera de Dirección", "Mecanismo que convierte el giro del volante en movimiento."),
                ("Cuerpo de Válvulas", "El 'cerebro' hidráulico que controla los cambios mediante solenoides."),
                ("Mecatrónica", "Módulo que combina la computadora (TCU) y el cuerpo de válvulas."),
                ("Solenoide", "Válvula electromagnética que controla el flujo de aceite."),
                ("CVT", "Transmisión Variable Continua, usa banda y poleas."),
            ]
        
        self.lines.append("\n## Glosario Tecnico (Definiciones Rapidas)\n")
        
        for term, desc in glossary_items:
            self.lines.append(f"- **{term}:** {desc}\n")
        
        return self
    
    def build_resources_section(self, catalog_url: str = "/pages/catalogs", support_url: str = "/pages/contact") -> 'LLMSTxtBuilder':
        """Build static resources section"""
        self.lines.append("\n## Recursos Tecnicos\n")
        url_catalogs = self._append_utm(catalog_url)
        url_support = self._append_utm(support_url)
        self.lines.append(f"- [Catalogos por Marca]({url_catalogs}): Especificaciones tecnicas por fabricante\n")
        self.lines.append(f"- [Soporte Tecnico]({url_support}): Asistencia experta en transmisiones\n")
        return self
    
    def build_high_traffic_guides(self, guides: Optional[List[Dict]] = None) -> 'LLMSTxtBuilder':
        """Build high-traffic guides section based on GA data"""
        if guides is None:
            guides = [
                ("¿Por qué no entra la reversa?", "/blogs/news/por-que-no-entra-la-reversa", "Diagnóstico de reversa fallida"),
                ("Fallas del selector de cambios", "/blogs/news/6-senales-de-fallas-en-el-selector", "Síntomas de selector dañado"),
                ("¿Por qué vibra mi carro en Drive?", "/blogs/news/por-que-mi-carro-vibra-en-drive", "Vibraciones en transmisión"),
            ]
        
        self.lines.append("\n## Guias Mas Consultadas\n")
        self.lines.append("> Contenido tecnico de mayor impacto basado en consultas de mecanicos.\n\n")
        
        for title, url, description in guides:
            tracked_url = self._append_utm(url)
            self.lines.append(f"- [{title}]({tracked_url}): {description}\n")
        
        return self
    
    def build(self) -> str:
        """Return final llms.txt content"""
        return "".join(self.lines)
    
    def export(self) -> Dict:
        """Export complete llms.txt with metadata"""
        content = self.build()
        return {
            "content": content,
            "word_count": len(content.split()),
            "line_count": len(content.split('\n')),
            "byte_size": len(content.encode('utf-8')),
        }


# Factory function for easy instantiation
def create_llms_txt_builder(
    store_name: str,
    store_description: str,
    authority_statement: str = ""
) -> LLMSTxtBuilder:
    """Create a new LLMSTxtBuilder with the given configuration."""
    return LLMSTxtBuilder(
        store_name=store_name,
        store_description=store_description,
        authority_statement=authority_statement
    )
