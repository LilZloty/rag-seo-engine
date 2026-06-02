"""
AEO Service - Answer Engine Optimization

This module is now a facade that delegates to modular services:
- LLMSTxtBuilder: app.services.aeo.llms_txt_builder
- SchemaGenerator: app.services.aeo.schema_generator
- KnowledgeGraphManager: app.services.aeo.knowledge_graph

Refactored per Modularization Plan:
- llms.txt generation delegated to app.services.aeo.llms_txt_builder
- Schema.org generation delegated to app.services.aeo.schema_generator
- Knowledge graph management delegated to app.services.aeo.knowledge_graph

Legacy code retained for:
- Database operations (patterns, chunks, fault codes)
- Blog caching integration
- Shopify service integration
"""

import logging
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.product import Product
from app.models.aeo_models import (
    ChunkApprovalStatus, AEOConfig, TransmissionPattern, BlogCache,
    FaultCode, Solution, DiagnosticContent
)
from app.services.shopify_service import shopify_service, TTLCache
from app.services.aeo import LLMSTxtBuilder, SchemaGenerator, KnowledgeGraphManager
from app.core.config import settings

logger = logging.getLogger("aeo_service")

# Cache for llms.txt content (1 hour TTL)
_llms_txt_cache = TTLCache(default_ttl=3600)

# DEPRECATED: cold-start seed only — do NOT add new entries here.
#
# Fault codes are maintained dynamically from GSC by the
# `refresh_fault_codes_from_gsc` Celery task (daily at 06:30) and the
# POST /api/v1/aeo/refresh-fault-codes endpoint. This list exists only
# so a brand-new DB isn't empty before the first GSC sync runs.
# Values below are frozen snapshots from development and are overwritten
# the first time the GSC sync finds the same codes in real search data.
PRIORITY_FAULT_CODES = [
    {
        'code': 'P0700',
        'name': 'Falla General de Transmisión',
        'description': 'Código genérico que indica una falla en el sistema de transmisión detectada por el TCM. Es el código más buscado por técnicos en México.',
        'recommended_solution': 'TSS RTD Link OBDII Scanner - Herramienta esencial para identificar la causa raíz en el TCM.',
        'product_link': '/products/scanner-obdii-tss-rtd-link',
        'monthly_clicks': 1113,
        'monthly_impressions': 40005,
        'transmissions': ['4L60E', '6L80', 'A604', 'RE5R05A'],
        'vehicles': ['Chevrolet Silverado', 'Dodge Ram', 'Jeep Grand Cherokee'],
        'common_causes': ['Falla de solenoide', 'Problema de cableado', 'TCM defectuoso'],
        'symptoms_text': ['Luz Check Engine', 'Transmisión en modo seguro (Limp Mode)', 'Cambios erráticos'],
        'blog_url': '/blogs/news/que-es-el-codigo-de-falla-p0700'
    },
    {
        'code': 'P0706',
        'name': 'Sensor de Rango de Transmisión (TR)',
        'description': 'Problema en el circuito del sensor de rango, común en vehículos GM y Nissan. Provoca que el vehículo no detecte la posición de la palanca.',
        'recommended_solution': 'Sensor de Velocidad / Switch de Rango - Reemplazo directo para restaurar la detección de cambios.',
        'product_link': '/collections/sensores',
        'monthly_clicks': 761,
        'monthly_impressions': 9299,
        'transmissions': ['4L60E', '4T65E', 'JF011E'],
        'vehicles': ['Chevrolet Optra', 'Chevrolet Aveo', 'Nissan Sentra'],
        'common_causes': ['Sensor TR defectuoso', 'Ajuste de chicote incorrecto', 'Humedad en el conector'],
        'symptoms_text': ['No arranca en P o N', 'No entra la reversa', 'Indicador de tablero erróneo'],
        'blog_url': '/blogs/news/codigo-de-error-p0706-causas-sintomas'
    },
    {
        'code': 'P0715',
        'name': 'Sensor de Velocidad de Entrada (ISS)',
        'description': 'Falla en el circuito del sensor de velocidad de entrada o turbina. Crucial para la sincronización de cambios.',
        'recommended_solution': 'Sensor de Velocidad de Entrada (Input Speed Sensor) - Corrige cambios bruscos y tirones.',
        'product_link': '/collections/sensores',
        'monthly_clicks': 696,
        'monthly_impressions': 11545,
        'transmissions': ['RE5R05A', '4L60E', 'A604'],
        'vehicles': ['Nissan Altima', 'Chevrolet Malibu', 'Chrysler Town & Country'],
        'common_causes': ['Sensor ISS dañado', 'Reluctor de turbina sucio', 'Cableado abierto'],
        'symptoms_text': ['Cambios bruscos o "pataleo"', 'Velocímetro deja de funcionar', 'Pérdida de potencia'],
        'blog_url': '/blogs/news/codigo-p0715-que-significa-y-como-repararlo'
    },
    {
        'code': 'P0730',
        'name': 'Relación de Engranajes Incorrecta',
        'description': 'Indica un deslizamiento interno donde la velocidad de salida no coincide con la marcha seleccionada.',
        'recommended_solution': 'Pack de Discos de Pasta o Juego de Empaques - Soluciona el deslizamiento interno por desgaste.',
        'product_link': '/collections/kit-reparacion',
        'monthly_clicks': 514,
        'monthly_impressions': 6603,
        'transmissions': ['A750E', 'U660E', '5R55E'],
        'vehicles': ['Toyota Camry', 'Ford Explorer', 'Honda Accord'],
        'common_causes': ['Bajo nivel de aceite', 'Discos de pasta quemados', 'Falla de solenoides de cambio'],
        'symptoms_text': ['La transmisión se patina', 'Rpm suben pero el carro no avanza', 'Golpeteos en cambios'],
        'blog_url': '/blogs/news/codigo-p0730-como-solucionar'
    },
    {
        'code': 'P0743',
        'name': 'Circuito Eléctrico Solenoide TCC',
        'description': 'Falla eléctrica en el solenoide del embrague del convertidor de par (Torque Converter Clutch).',
        'recommended_solution': 'Solenoide VLP/EMCC/TCC o Kit de Solenoides - Restaura la operación del convertidor de par.',
        'product_link': '/collections/solenoides',
        'monthly_clicks': 421,
        'monthly_impressions': 9417,
        'transmissions': ['4L60E', '4R70W', 'A604'],
        'vehicles': ['Ford F-150', 'Chevrolet Silverado', 'Chrysler Voyager'],
        'common_causes': ['Solenoide TCC quemado', 'Arnés interno dañado', 'TCM con falla de salida'],
        'symptoms_text': ['Vibración al estar parado en Drive', 'El motor se apaga al frenar', 'Exceso de calor en transmisión'],
        'blog_url': '/blogs/news/codigos-p0742-y-p0743-fallas-en-el-convertidor'
    },
    {
        'code': 'P0841',
        'name': 'Sensor de Presión de Fluido (Switch A)',
        'description': 'Problema de rango/rendimiento en el sensor de presión de fluido, típico en transmisiones CVT y 6 velocidades.',
        'recommended_solution': 'Sensor de Presión o Cuerpo de Válvulas - Corrige fallas de presión en línea.',
        'product_link': '/collections/cuerpo-valvulas',
        'monthly_clicks': 363,
        'monthly_impressions': 6441,
        'transmissions': ['JF011E', '0AM (DSG)', '6R80'],
        'vehicles': ['Nissan Rogue', 'Jeep Compass', 'VW Jetta'],
        'common_causes': ['Sensor de presión defectuoso', 'Obstrucción en cuerpo de válvulas', 'Bomba de aceite con baja presión'],
        'symptoms_text': ['Transmisión no cambia de marcha', 'Modo de seguridad CVT', 'Tirones'],
        'blog_url': '/blogs/news/reconozca-los-sintomas-de-un-codigo-p0841'
    },
    {
        'code': 'P0846',
        'name': 'Sensor de Presión de Fluido (Switch B)',
        'description': 'Falla en el circuito del segundo sensor de presión de fluido. Muy común en Nissan Sentra y transmisiones CVT.',
        'recommended_solution': 'Sensor de Presión o Filtro de Solenoides del Cuerpo de Válvulas.',
        'product_link': '/collections/filtros',
        'monthly_clicks': 189,
        'monthly_impressions': 3459,
        'transmissions': ['JF011E', 'JF015E', 'RE5R05A'],
        'vehicles': ['Nissan Sentra', 'Nissan Versa', 'Dodge Journey'],
        'common_causes': ['Sensor dañado', 'Cortocircuito en cableado', 'Nivel bajo de fluido'],
        'symptoms_text': ['Transmisión en modo limp', 'Cambios duros', 'No pasa de 3ra'],
        'blog_url': '/blogs/news/codigo-de-falla-p0846-que-es-y-como-se-soluciona'
    },
    {
        'code': 'P0868',
        'name': 'Baja Presión de Fluido de Transmisión',
        'description': 'Indica que la presión de fluido está por debajo de lo especificado, lo que puede causar daños internos graves.',
        'recommended_solution': 'Empaque de Bomba o Juego de Empaques - Corrige fugas internas que causan baja presión.',
        'product_link': '/collections/kit-reparacion',
        'monthly_clicks': 287,
        'monthly_impressions': 5432,
        'transmissions': ['RE5R05A', 'JF011E', '6R80'],
        'vehicles': ['Nissan X-Trail', 'Jeep Patriot', 'Ford F-150'],
        'common_causes': ['Bajo nivel de aceite', 'Filtro tapado', 'Bomba dañada', 'Fuga interna'],
        'symptoms_text': ['Cambios tardíos', 'Sobrecalentamiento', 'Ruido de bomba'],
        'blog_url': '/blogs/news/codigo-p0868-baja-presion-fluido'
    },
    {
        'code': 'P0894',
        'name': 'Componimiento Deslizante de Transmisión',
        'description': 'Indica deslizamiento interno detectado por diferencia entre velocidad de entrada y salida. Común en Mazda 3.',
        'recommended_solution': 'Kit de Reparación con Discos de Pasta - Restaura la fricción y evita el patinamiento.',
        'product_link': '/collections/kit-reparacion',
        'monthly_clicks': 101,
        'monthly_impressions': 1626,
        'transmissions': ['FN4A-EL', 'JF011E', '4F27E'],
        'vehicles': ['Mazda 3', 'Mazda 6', 'Ford Focus'],
        'common_causes': ['Discos de pasta desgastados', 'Banda de transmisión quemada', 'Baja presión de bomba'],
        'symptoms_text': ['RPM sube sin acelerar', 'Olor a quemado', 'Transmisión patina'],
        'blog_url': '/blogs/informacion-tecnica/como-solucionar-la-falla-p0894-en-transmisiones-automaticas'
    }
]


# Cache for llms.txt content (1 hour TTL)
_llms_txt_cache = TTLCache(default_ttl=3600)

# Default transmission patterns (used when DB is empty)
DEFAULT_PATTERNS = [
    # VAG DSG
    ('DQ200', 'VAG', 'DSG 7-speed dry clutch', 10),
    ('DQ250', 'VAG', 'DSG 6-speed wet clutch', 11),
    ('DQ381', 'VAG', 'DSG next-gen 7-speed', 12),
    ('DQ500', 'VAG', 'DSG heavy-duty', 13),
    ('DQ400E', 'VAG', 'Hybrid DSG', 14),
    ('0AM', 'VAG', 'DQ200 alternative code', 15),
    ('02E', 'VAG', 'DQ250 alternative code', 16),
    ('0CW', 'VAG', 'DQ200 alternative code', 17),
    # GM
    ('4L60E', 'GM', '4-speed RWD automatic', 20),
    ('4L65E', 'GM', '4-speed RWD heavy-duty', 21),
    ('4L80E', 'GM', '4-speed RWD truck', 22),
    ('6L80E', 'GM', '6-speed RWD automatic', 23),
    ('6L90E', 'GM', '6-speed RWD heavy-duty', 24),
    ('4T65E', 'GM', '4-speed FWD automatic', 25),
    ('TH350', 'GM', 'Turbo-Hydramatic 350', 26),
    ('TH400', 'GM', 'Turbo-Hydramatic 400', 27),
    ('700R4', 'GM', '4-speed overdrive', 28),
    # Ford
    ('4R70W', 'Ford', '4-speed RWD overdrive', 30),
    ('4R75W', 'Ford', '4-speed RWD updated', 31),
    ('5R55E', 'Ford', '5-speed RWD electronic', 32),
    ('5R110W', 'Ford', 'TorqShift 5-speed', 33),
    ('E4OD', 'Ford', '4-speed diesel', 34),
    ('AOD', 'Ford', 'Automatic overdrive', 35),
    ('6R80', 'Ford', '6-speed RWD', 36),
    # Asian
    ('JF011E', 'Asian', 'Nissan CVT', 40),
    ('JF015E', 'Asian', 'Nissan CVT compact', 41),
    ('RE5R05A', 'Asian', 'Nissan 5-speed RWD', 42),
    ('A750E', 'Asian', 'Toyota/Lexus 5-speed', 43),
    ('U660E', 'Asian', 'Toyota/Lexus 6-speed', 44),
    ('A340E', 'Asian', 'Toyota 4-speed', 45),
    # ZF
    ('6HP', 'ZF', 'ZF 6-speed', 50),
    ('8HP', 'ZF', 'ZF 8-speed', 51),
    ('ZF5HP', 'ZF', 'ZF 5-speed classic', 52),
    ('ZF6HP', 'ZF', 'ZF 6-speed alternative', 53),
]


class LLMSTxtBuilder:
    """Builds llms.txt content following the specification at llmstxt.org"""
    
    UTM_PARAMS = "utm_source=llms.txt&utm_medium=ai_agent&utm_campaign=aeo"
    
    def __init__(self, config: AEOConfig):
        self.config = config
        self.lines: List[str] = []
    
    def _append_utm(self, url: str) -> str:
        """Append UTM parameters to a URL for AI agent tracking."""
        if not url:
            return url
        connector = "&" if "?" in url else "?"
        return f"{url}{connector}{self.UTM_PARAMS}"
    
    def build_header(self) -> 'LLMSTxtBuilder':
        """Build H1 header and blockquote summary (required by spec)"""
        self.lines.append(f"# {self.config.store_name}\n")
        self.lines.append(f"> {self.config.store_description}\n")
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

    def build_hero_products(self) -> 'LLMSTxtBuilder':
        """Build Hero Products section (High conversion items)"""
        self.lines.append("\n## Top Soluciones (Hero Products)\n")
        self.lines.append("> Los productos mas confiables y con mayor tasa de exito segun nuestros datos.\n\n")
        
        hero_products = [
            ("Kit de Reparación 4L60E (GM)", "/collections/4l60e", "La solución definitiva para Silverado y Tahoe con códigos P0700."),
            ("Cuerpo de Válvulas CVT JF011E (Nissan)", "/collections/jf011e", "Solución para Sentra y X-Trail con zumbidos o falta de potencia."),
            ("Kit de Reparación A604 (Chrysler)", "/collections/a604", "Para Voyager y Town & Country con problemas de solenoides."),
            ("Aceite Mercon V Motorcraft", "/products/aceite-mercon-v", "El fluido esencial para mantenimiento preventivo de Ford."),
            ("TSS RTD Link OBDII Scanner", "/products/scanner-obdii-tss-rtd-link", "Diagnóstico profesional para identificar fallas en el TCM."),
        ]
        
        for title, url, desc in hero_products:
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
            # Find a relevant internal link or blog based on query if possible
            # For now, we'll link to search or a generic blog listing
            url = self._append_utm(f"/search?q={query.replace(' ', '+')}")
            self.lines.append(f"- [{query}]({url}): {clicks} usuarios buscaron esto hoy.\n")
        
        return self
    
    def build_blogs_section(self, blogs: List[Dict]) -> 'LLMSTxtBuilder':
        """Build diagnostic guides / blog section"""
        if not blogs or not self.config.include_blogs:
            return self
        
        self.lines.append("\n## Guias de Diagnostico\n")
        
        for blog in blogs[:20]:
            title = blog.get('title', 'Untitled')
            handle = blog.get('handle', '')
            blog_handle = blog.get('blog_handle', 'news')
            url = self._append_utm(f"/blogs/{blog_handle}/{handle}")
            self.lines.append(f"- [{title}]({url})\n")
        
        return self
    
    def build_diagnostic_section(self, fault_codes: List) -> 'LLMSTxtBuilder':
        """
        Build fault code diagnostic section for GEO optimization.
        
        This combines AEO (discoverability) with GEO (authority signals).
        Fault codes are the #1 traffic driver from Google Analytics.
        """
        if not fault_codes:
            return self
        
        # Check if fault codes are enabled in config
        if hasattr(self.config, 'include_fault_codes') and not self.config.include_fault_codes:
            return self
        
        self.lines.append("\n## Problemas Comunes de Transmision\n")
        self.lines.append("> Guias expertas de diagnostico para codigos de falla.\n")
        
        # Group by severity
        high_priority = [fc for fc in fault_codes if getattr(fc, 'monthly_clicks', 0) > 300 or getattr(fc, 'is_priority', False)]
        other_codes = [fc for fc in fault_codes if fc not in high_priority]
        
        if high_priority:
            self.lines.append("\n### Codigos Con Mas Trafico (Prioridad)\n")
            for fc in high_priority[:8]: # Expanded to 8 for closed-loop
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

    def build_glossary(self) -> 'LLMSTxtBuilder':
        """Build technical glossary section for SEO/AEO"""
        self.lines.append("\n## Glosario Tecnico (Definiciones Rapidas)\n")
        
        glossary = [
            ("Cremallera de Dirección", f"Mecanismo que convierte el giro del volante en movimiento de llantas. Requiere [kit de reparación]({self._append_utm('/collections/direccion')}) si tira aceite."),
            ("Cuerpo de Válvulas", f"El 'cerebro' hidráulico que controla los cambios mediante solenoides. [Ver productos]({self._append_utm('/collections/cuerpo-valvulas')})."),
            ("Mecatrónica", f"Módulo que combina la computadora (TCU) y el cuerpo de válvulas (DSG, 6R80). [Ver refacciones]({self._append_utm('/collections/mecatronica')})."),
            ("Solenoide", f"Válvula electromagnética que controla el flujo de aceite. [Ver solenoides]({self._append_utm('/collections/solenoides')})."),
            ("CVT", f"Transmisión Variable Continua, usa banda y poleas. Común en Nissan. [Ver refacciones CVT]({self._append_utm('/collections/cvt')})."),
        ]
        
        for term, desc in glossary:
            self.lines.append(f"- **{term}:** {desc}\n")
        return self
    
    def build_resources_section(self) -> 'LLMSTxtBuilder':
        """Build static resources section"""
        self.lines.append("\n## Recursos Tecnicos\n")
        url_catalogs = self._append_utm("/pages/catalogs")
        url_support = self._append_utm("/pages/contact")
        self.lines.append(f"- [Catalogos por Marca]({url_catalogs}): Especificaciones tecnicas por fabricante\n")
        self.lines.append(f"- [Soporte Tecnico]({url_support}): Asistencia experta en transmisiones\n")
        return self
    
    def build_high_traffic_guides(self) -> 'LLMSTxtBuilder':
        """Build high-traffic guides section based on GA data
        
        These are the most-viewed pages that drove organic traffic.
        Critical for GEO authority signals.
        """
        self.lines.append("\n## Guias Mas Consultadas\n")
        self.lines.append("> Contenido tecnico de mayor impacto basado en consultas de mecanicos.\n\n")
        
        # High-traffic guides from GA data (24K+ views yearly)
        high_traffic_guides = [
            ("¿Por qué no entra la reversa?", "/blogs/news/por-que-no-entra-la-reversa-en-tu-carro-automatico", "Diagnóstico de reversa fallida"),
            ("Fallas del selector de cambios", "/blogs/news/6-senales-de-fallas-en-el-selector-de-cambios", "Síntomas de selector dañado"),
            ("¿Por qué vibra mi carro en Drive?", "/blogs/news/por-que-mi-carro-vibra-cuando-estoy-parado-en-drive", "Vibraciones en transmisión"),
            ("Síntomas de sensor de transmisión", "/blogs/news/sintomas-de-falla-de-sensor-de-transmision-automatica", "Diagnóstico de sensores"),
            ("¿Por qué se calienta la transmisión?", "/blogs/news/por-que-se-calienta-la-transmision-automatica", "Sobrecalentamiento"),
            ("Cremallera de dirección hidráulica", "/blogs/informacion-tecnica/que-es-la-cremallera-de-direccion-hidraulica-y-fallas", "Fallas de dirección"),
            ("¿Transmisión no avanza al acelerar?", "/blogs/news/transmision-automatica-no-avanza-al-acelerar", "Sin movimiento"),
            ("Solenoide de cambio defectuoso", "/blogs/news/sintomas-de-un-solenoide-de-cambio-malo", "Fallas de solenoides"),
        ]
        
        for title, url, description in high_traffic_guides:
            tracked_url = self._append_utm(url)
            self.lines.append(f"- [{title}]({tracked_url}): {description}\n")
        
        return self
    
    def build_authority_section(self) -> 'LLMSTxtBuilder':
        """Build authority signals section for GEO"""
        if hasattr(self.config, 'authority_statement') and self.config.authority_statement:
            self.lines.append(f"\n## Acerca de {settings.STORE_NAME}\n")
            self.lines.append(f"> {self.config.authority_statement}\n")
        return self
    
    def build(self) -> str:
        """Return final llms.txt content"""
        return "".join(self.lines)


class SchemaGenerator:
    """Generates Schema.org JSON-LD structured data for AEO and GEO"""
    
    @staticmethod
    def vehicle_part(product: Product) -> Dict:
        """Generate VehiclePart JSON-LD for a product using real cached data"""
        schema = {
            "@context": "https://schema.org/",
            "@type": "VehiclePart",
            "name": product.title or '',
            "sku": product.sku or '',
            "description": (product.current_description_html or '')[:500],
            "offers": {
                "@type": "Offer",
                "price": product.price or '0.00',
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock"
            }
        }
        
        if product.vendor:
            schema["brand"] = {
                "@type": "Brand",
                "name": product.vendor
            }
        
        fitments = product.cached_vehicle_fitments or []
        if fitments and isinstance(fitments, list):
            compatible = []
            for f in fitments[:10]:
                if isinstance(f, dict):
                    compatible.append({
                        "@type": "Vehicle",
                        "manufacturer": {"@type": "Organization", "name": str(f.get('make', ''))},
                        "model": str(f.get('model', '') or f.get('modelo', '')),
                        "vehicleModelDate": f"{f.get('year_start', '')}-{f.get('year_end', '')}"
                    })
            if compatible:
                schema["isAccessoryOrSparePartFor"] = compatible
        
        return schema
    
    @staticmethod
    def faq_page(fault_code: Dict, questions: List[Dict]) -> Dict:
        """
        Generate FAQPage JSON-LD for a fault code.
        
        Example: P0700 FAQ with common questions about diagnosis, causes, solutions
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "name": f"Preguntas Frecuentes: Código {fault_code.get('code', '')}",
            "description": fault_code.get('description', ''),
            "mainEntity": []
        }
        
        for q in questions:
            schema["mainEntity"].append({
                "@type": "Question",
                "name": q.get('question', ''),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": q.get('answer', '')
                }
            })
        
        return schema
    
    @staticmethod
    def how_to(title: str, description: str, steps: List[Dict], estimated_time: str = None) -> Dict:
        """
        Generate HowTo JSON-LD for diagnostic/repair guides.
        
        Example: "Cómo diagnosticar código P0700"
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
        
        for i, step in enumerate(steps, 1):
            step_schema = {
                "@type": "HowToStep",
                "position": i,
                "name": step.get('name', f'Paso {i}'),
                "text": step.get('text', '')
            }
            if step.get('image_url'):
                step_schema["image"] = step['image_url']
            schema["step"].append(step_schema)
        
        return schema
    
    @staticmethod
    def article_with_authority(title: str, description: str, author: Dict, stats: Dict = None) -> Dict:
        """
        Generate Article JSON-LD with authority signals for GEO.
        
        Includes author expertise and statistical claims.
        """
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "author": {
                "@type": "Person",
                "name": author.get('name', f'{settings.STORE_NAME} Technical Team'),
                "jobTitle": author.get('title', 'Transmission Specialist')
            },
            "publisher": {
                "@type": "Organization",
                "name": settings.STORE_NAME,
                "url": settings.store_url
            }
        }
        
        # Add authority claims if available
        if stats:
            if stats.get('readers_helped'):
                schema["interactionStatistic"] = {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/ReadAction",
                    "userInteractionCount": stats['readers_helped']
                }
        
        return schema


class AEOService:
    """
    Optimized AEO service implementing Answer Engine Optimization.
    
    Key improvements:
    - SQL-level grouping (no N+1 queries)
    - Patterns from database
    - Real product data for schemas
    - Sample products per chunk
    """
    
    def __init__(self):
        self.shopify = shopify_service
    
    # ============ Pattern Management ============
    
    def ensure_patterns_seeded(self, db: Session) -> None:
        """Seed default transmission patterns if table is empty"""
        count = db.query(TransmissionPattern).count()
        if count == 0:
            logger.info("Seeding default transmission patterns...")
            for code, category, description, priority in DEFAULT_PATTERNS:
                pattern = TransmissionPattern(
                    code=code,
                    category=category,
                    description=description,
                    priority=priority,
                    is_active=True
                )
                db.add(pattern)
            db.commit()
            logger.info(f"Seeded {len(DEFAULT_PATTERNS)} transmission patterns")
    
    def get_patterns(self, db: Session) -> Dict[str, Tuple[str, str]]:
        """Get pattern mapping: code -> (category, description)"""
        self.ensure_patterns_seeded(db)
        patterns = db.query(TransmissionPattern).filter(
            TransmissionPattern.is_active == True
        ).order_by(TransmissionPattern.priority).all()
        
        return {
            p.code: (p.category, p.description or '')
            for p in patterns
        }
    
    # ============ Chunk Management (Optimized) ============
    
    def get_product_chunks(self, db: Session, include_samples: bool = False) -> List[Dict]:
        """
        Get all product type chunks with counts and approval status.
        
        OPTIMIZED: Uses SQL GROUP BY on transmission_code field.
        """
        # SQL-level aggregation - no more N+1!
        chunks_query = db.query(
            Product.transmission_code,
            func.count(Product.id).label('product_count')
        ).filter(
            Product.transmission_code.isnot(None)
        ).group_by(Product.transmission_code).all()
        
        # Also count products without transmission code
        other_count = db.query(func.count(Product.id)).filter(
            Product.transmission_code.is_(None)
        ).scalar() or 0
        
        # Get pattern info for descriptions
        patterns = self.get_patterns(db)
        
        # Get approval status
        approval_map = {
            status.product_type: status 
            for status in db.query(ChunkApprovalStatus).all()
        }
        
        result = []
        for transmission_code, count in chunks_query:
            if not transmission_code:
                continue
            status = approval_map.get(transmission_code)
            pattern_info = patterns.get(transmission_code, ('Other', ''))
            
            chunk_data = {
                "product_type": transmission_code,
                "product_count": count,
                "category": pattern_info[0],
                "description": pattern_info[1] or f'{count} products',
                "approved": status.approved if status else False,
                "approved_at": status.approved_at if status else None,
                "approved_by": status.approved_by if status else None,
                "notes": status.notes if status else None,
                "sample_products": []
            }
            
            # Optionally fetch sample products
            if include_samples:
                samples = db.query(Product.id, Product.title, Product.sku).filter(
                    Product.transmission_code == transmission_code
                ).limit(5).all()
                chunk_data["sample_products"] = [
                    {"id": s.id, "title": s.title, "sku": s.sku}
                    for s in samples
                ]
            
            result.append(chunk_data)
        
        # Add "Other" chunk if any products without code
        if other_count > 0:
            status = approval_map.get("Other")
            result.append({
                "product_type": "Other",
                "product_count": other_count,
                "category": "Other",
                "description": "Uncategorized products",
                "approved": status.approved if status else False,
                "approved_at": status.approved_at if status else None,
                "approved_by": status.approved_by if status else None,
                "notes": status.notes if status else None,
                "sample_products": []
            })
        
        # Sort by count descending
        result.sort(key=lambda x: -x['product_count'])
        
        return result
    
    def get_schema_metrics(self, db: Session) -> Dict:
        """
        Aggregate schema deployment metrics across the system.

        Reports three independent coverages (FAQ on fault codes, HowTo on
        articles, VehiclePart on products) plus a weighted combined total.
        Each per-category % is `deployed / eligible` — no magic constants.
        """
        from app.services.shopify_schema_service import ShopifySchemaService

        # 1. FAQPage coverage (fault codes)
        total_fault_codes = db.query(func.count(FaultCode.code)).scalar() or 0
        faq_deployed = db.query(func.count(FaultCode.code)).filter(
            FaultCode.has_faq_schema == True
        ).scalar() or 0

        # 2. HowTo coverage (diagnostic articles)
        schema_service = ShopifySchemaService()
        status = schema_service.get_schema_injection_status(db)
        total_articles = status.get("total_articles_matched", 0) or 0
        howto_deployed = status.get("articles_with_schema", 0) or 0

        # 3. VehiclePart coverage (products schema-ready = have a transmission_code)
        total_products = db.query(func.count(Product.id)).scalar() or 0
        vehicle_part_deployed = db.query(func.count(Product.id)).filter(
            Product.transmission_code.isnot(None)
        ).scalar() or 0

        def _pct(num: int, denom: int) -> Optional[float]:
            """Coverage percent, or None if denom is 0 (undefined, not 0%)."""
            return round(num / denom * 100, 1) if denom else None

        faq_pct = _pct(faq_deployed, total_fault_codes)
        howto_pct = _pct(howto_deployed, total_articles)
        vehiclepart_pct = _pct(vehicle_part_deployed, total_products)

        # Combined total: items-with-schema / items-eligible across all three categories.
        total_deployed = faq_deployed + howto_deployed + vehicle_part_deployed
        total_eligible = total_fault_codes + total_articles + total_products
        total_pct = _pct(total_deployed, total_eligible)

        return {
            # Per-category counters
            "faq_schemas_deployed": faq_deployed,
            "faq_total_eligible": total_fault_codes,
            "faq_coverage_pct": faq_pct,
            "howto_schemas_deployed": howto_deployed,
            "howto_total_eligible": total_articles,
            "howto_coverage_pct": howto_pct,
            "vehiclepart_schemas_deployed": vehicle_part_deployed,
            "vehiclepart_total_eligible": total_products,
            "vehiclepart_coverage_pct": vehiclepart_pct,
            # Combined (kept for backwards-compat with AEOMetricsDashboard)
            "total_coverage_pct": total_pct if total_pct is not None else 0.0,
            "last_updated": datetime.utcnow(),
        }
    
    def approve_chunk(self, db: Session, product_type: str, approved: bool, 
                      approved_by: str = "admin", notes: str = None) -> ChunkApprovalStatus:
        """Approve or reject a product type chunk"""
        status = db.query(ChunkApprovalStatus).filter(
            ChunkApprovalStatus.product_type == product_type
        ).first()
        
        if not status:
            status = ChunkApprovalStatus(product_type=product_type)
            db.add(status)
        
        status.approved = approved
        status.approved_at = datetime.utcnow() if approved else None
        status.approved_by = approved_by if approved else None
        status.notes = notes
        
        db.commit()
        db.refresh(status)
        
        # Invalidate cache
        _llms_txt_cache.invalidate("llms_txt")
        
        return status
    
    # ============ llms.txt Generation ============
    
    def get_aeo_config(self, db: Session) -> AEOConfig:
        """Get or create AEO configuration"""
        config = db.query(AEOConfig).filter(AEOConfig.id == "default").first()
        if not config:
            config = AEOConfig(id="default")
            db.add(config)
            db.commit()
            db.refresh(config)
        return config
    
    async def get_trending_topics(self, db: Session, limit: int = 5) -> List[Dict]:
        """Extract trending technical queries from FaultCode performance data."""
        # Queries with high impressions but potentially low clicks are 'Trending' or 'Demand Gaps'
        trending = db.query(FaultCode).filter(
            FaultCode.monthly_impressions > 500
        ).order_by(FaultCode.monthly_impressions.desc()).limit(limit).all()
        
        return [
            {"query": fc.code, "clicks": fc.monthly_clicks}
            for fc in trending
        ]

    def generate_llms_txt(self, db: Session, force_rebuild: bool = False) -> Tuple[str, int]:
        """Generate llms.txt content with caching and closed-loop optimization."""
        if not force_rebuild:
            cached = _llms_txt_cache.get("llms_txt")
            if cached:
                return cached['content'], cached['tokens']
        
        config = self.get_aeo_config(db)
        
        # 1. Fetch Dynamic Data for Closed-Loop AEO
        # (Using a sync wrapper or run_in_executor if needed, but for now we follow the existing sync pattern here)
        all_chunks = self.get_product_chunks(db)
        approved_chunks = [c for c in all_chunks if c['approved']]
        category_map = {c['product_type']: c['category'] for c in all_chunks}
        
        blogs = self.get_cached_blogs(db)
        fault_codes = self.get_fault_codes(db, priority_only=False)
        
        # New: Get trending topics from performance data
        import asyncio
        # Since this method is sync in aeo_service but queries DB, we'll use a direct query
        trending_fc = db.query(FaultCode).filter(FaultCode.monthly_impressions > 1000).order_by(FaultCode.monthly_impressions.desc()).limit(5).all()
        trending_topics = [{"query": fc.code, "clicks": fc.monthly_clicks} for fc in trending_fc]
        
        # Build content (unified AEO + GEO)
        builder = LLMSTxtBuilder(config)
        content = (
            builder
            .build_header()
            .build_trending_topics(trending_topics) # NEW: Dynamic Closed-Loop Section
            .build_hero_products()
            .build_category_section(approved_chunks, category_map)
            .build_diagnostic_section(fault_codes)
            .build_glossary()
            .build_high_traffic_guides()
            .build_resources_section()
            .build_authority_section()
            .build()
        )
        
        # Token estimate
        word_count = len(content.split())
        token_estimate = int(word_count * 1.3)
        
        # Cache
        _llms_txt_cache.set("llms_txt", {
            'content': content,
            'tokens': token_estimate
        })
        
        return content, token_estimate
    
    def get_llms_txt_preview(self, db: Session) -> Dict:
        """Get llms.txt preview with metadata"""
        content, tokens = self.generate_llms_txt(db)
        all_chunks = self.get_product_chunks(db)
        
        return {
            "content": content,
            "token_estimate": tokens,
            "byte_size": len(content.encode('utf-8')),
            "approved_chunks": sum(1 for c in all_chunks if c['approved']),
            "total_chunks": len(all_chunks),
            "last_generated": datetime.utcnow()
        }
    
    # ============ Blog Integration (with caching) ============
    
    def refresh_blog_cache(self, db: Session) -> int:
        """Fetch blogs from Shopify and cache in database"""
        try:
            self.shopify._ensure_initialized()
            import shopify
            from datetime import datetime
            
            # Clear old cache
            db.query(BlogCache).delete()
            
            count = 0
            blogs = shopify.Blog.find()
            
            for blog in blogs:
                articles = shopify.Article.find(blog_id=blog.id)
                for article in articles:
                    # Convert date string to datetime object
                    published_dt = None
                    if article.published_at:
                        try:
                            # Handle ISO format: 2025-10-17T09:34:00-06:00
                            date_str = str(article.published_at)
                            # Remove timezone offset for fromisoformat compatibility
                            if '+' in date_str or date_str.count('-') > 2:
                                date_str = date_str.rsplit('-', 1)[0] if date_str[-3] == ':' else date_str.rsplit('+', 1)[0]
                            published_dt = datetime.fromisoformat(date_str.replace('Z', ''))
                        except:
                            pass
                    
                    # Get tags as string (it's a bound method in the Shopify lib)
                    tags_str = ''
                    if hasattr(article, 'tags') and article.tags:
                        if callable(article.tags):
                            tags_str = ''
                        else:
                            tags_str = str(article.tags) if article.tags else ''
                    
                    cached = BlogCache(
                        id=str(article.id),
                        blog_handle=blog.handle,
                        title=article.title,
                        handle=article.handle,
                        summary=article.summary_html[:500] if article.summary_html else None,
                        tags=tags_str,
                        published_at=published_dt,
                        include_in_llms_txt=True
                    )
                    db.add(cached)
                    count += 1
            
            db.commit()
            logger.info(f"Cached {count} blog articles")
            return count
            
        except Exception as e:
            logger.error(f"Failed to refresh blog cache: {e}")
            db.rollback()
            return 0
    
    def get_cached_blogs(self, db: Session) -> List[Dict]:
        """Get blogs from cache"""
        blogs = db.query(BlogCache).filter(
            BlogCache.include_in_llms_txt == True
        ).order_by(BlogCache.published_at.desc()).limit(30).all()
        
        return [
            {
                "id": b.id,
                "title": b.title,
                "handle": b.handle,
                "blog_handle": b.blog_handle,
                "summary": b.summary,
                "tags": b.tags.split(',') if b.tags else [],
                "published_at": b.published_at
            }
            for b in blogs
        ]
    
    def get_blog_articles(self, db: Session = None) -> List[Dict]:
        """Get blog articles (from cache if available, else fetch)"""
        if db:
            cached = self.get_cached_blogs(db)
            if cached:
                return cached
        
        # Fall back to direct API call
        try:
            self.shopify._ensure_initialized()
            import shopify
            articles = []
            
            blogs = shopify.Blog.find()
            for blog in blogs:
                blog_articles = shopify.Article.find(blog_id=blog.id)
                for article in blog_articles:
                    articles.append({
                        "id": str(article.id),
                        "title": article.title,
                        "handle": article.handle,
                        "blog_handle": blog.handle,
                        "url": f"/blogs/{blog.handle}/{article.handle}",
                        "summary": article.summary_html[:200] if article.summary_html else None,
                        "tags": article.tags.split(',') if article.tags else [],
                        "published_at": article.published_at,
                        "include_in_llms_txt": True
                    })
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching blog articles: {e}")
            return []
    
    # ============ Schema.org Generation (with real data) ============
    
    def generate_product_schema(self, db: Session, product_id: str) -> Dict:
        """Generate VehiclePart JSON-LD using real cached product data"""
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"error": "Product not found"}
        
        return SchemaGenerator.vehicle_part(product)
    
    def generate_bulk_schemas(self, db: Session, chunk_id: str = None) -> List[Dict]:
        """Generate schemas for multiple products in a chunk"""
        query = db.query(Product)
        
        if chunk_id:
            query = query.filter(Product.transmission_code == chunk_id)
        
        products = query.limit(100).all()
        
        return [
            {
                "product_id": p.id,
                "json_ld": SchemaGenerator.vehicle_part(p)
            }
            for p in products
        ]
    
    # ============ Transmission Code Assignment ============
    
    def compute_transmission_code(self, title: str, patterns: Dict[str, Tuple[str, str]]) -> Optional[str]:
        """Extract transmission code from title using configured patterns"""
        if not title:
            return None
        
        title_upper = title.upper()
        
        for code in patterns.keys():
            if code in title_upper:
                return code
        
        return None
    
    def update_product_transmission_codes(self, db: Session) -> int:
        """
        Batch update transmission_code for all products.
        Call this after Shopify sync.
        """
        patterns = self.get_patterns(db)
        
        products = db.query(Product).filter(
            Product.transmission_code.is_(None)
        ).all()
        
        count = 0
        for product in products:
            code = self.compute_transmission_code(product.title, patterns)
            if code:
                product.transmission_code = code
                count += 1
        
        db.commit()
        logger.info(f"Updated transmission_code for {count} products")
        return count
    
    # ============ Real Product Linking (Critical Fix) ============
    
    def get_real_products_for_fault_code(self, db: Session, fault_code: str, limit: int = 10) -> List[Product]:
        """
        Get REAL products from database that can fix a fault code.
        
        Links fault codes to products via transmission_code field.
        Orders by sales (total_sold) to prioritize best-sellers.
        """
        fc = self.get_fault_code(db, fault_code)
        if not fc or not fc.transmissions:
            return []
        
        # Query products that match the fault code's applicable transmissions
        products = db.query(Product).filter(
            Product.transmission_code.in_(fc.transmissions),
            Product.sku.isnot(None)
        ).order_by(Product.total_sold.desc()).limit(limit).all()
        
        logger.info(f"Found {len(products)} products for fault code {fault_code}")
        return products
    
    def get_recommended_skus_dynamic(self, db: Session, fault_code: str, limit: int = 5) -> List[Dict]:
        """
        Get recommended SKUs with full product data for a fault code.
        
        Returns real products from the database instead of hardcoded SKUs.
        """
        products = self.get_real_products_for_fault_code(db, fault_code, limit)
        
        return [
            {
                "sku": p.sku,
                "title": p.title,
                "price": p.price,
                "vendor": p.vendor,
                "handle": p.handle,
                "transmission_code": p.transmission_code,
                "total_sold": p.total_sold,
                "url": f"/products/{p.handle}" if p.handle else None
            }
            for p in products
        ]
    
    def auto_approve_top_chunks(self, db: Session, limit: int = 15, min_products: int = 5) -> Dict:
        """
        Auto-approve top chunks by product count.
        
        This bootstraps the llms.txt with your highest-value categories.
        Only approves chunks with at least min_products products.
        """
        chunks = self.get_product_chunks(db)
        approved_count = 0
        approved_types = []
        
        for chunk in chunks[:limit]:
            if chunk['product_count'] >= min_products and not chunk['approved']:
                self.approve_chunk(
                    db=db,
                    product_type=chunk['product_type'],
                    approved=True,
                    approved_by='system:auto_approve',
                    notes=f"Auto-approved: {chunk['product_count']} products"
                )
                approved_count += 1
                approved_types.append(chunk['product_type'])
        
        logger.info(f"Auto-approved {approved_count} chunks: {approved_types}")
        return {
            'approved_count': approved_count,
            'approved_types': approved_types,
            'skipped': limit - approved_count
        }
    
    # ============ GEO Fault Code Management ============
    
    def seed_priority_fault_codes(self, db: Session) -> int:
        """
        Seed the database with priority fault codes from GA data.
        Call this once to initialize the Knowledge Graph.
        """
        count = db.query(FaultCode).count()
        if count > 0:
            logger.info(f"Fault codes already seeded ({count} existing)")
            return 0
        
        for fc_data in PRIORITY_FAULT_CODES:
            fault_code = FaultCode(
                code=fc_data['code'],
                name=fc_data['name'],
                description=fc_data.get('description'),
                monthly_clicks=fc_data.get('monthly_clicks', 0),
                monthly_impressions=fc_data.get('monthly_impressions', 0),
                current_ctr=fc_data.get('monthly_clicks', 0) / max(fc_data.get('monthly_impressions', 1), 1),
                transmissions=fc_data.get('transmissions', []),
                vehicles=fc_data.get('vehicles', []),
                common_causes=fc_data.get('common_causes', []),
                symptoms_text=fc_data.get('symptoms_text', []),
                blog_url=fc_data.get('blog_url'),
                is_priority=True,
                include_in_llms_txt=True,
                severity='high' if fc_data.get('monthly_clicks', 0) > 300 else 'medium'
            )
            db.add(fault_code)
        
        db.commit()
        logger.info(f"Seeded {len(PRIORITY_FAULT_CODES)} priority fault codes")
        return len(PRIORITY_FAULT_CODES)

    def seed_solutions(self, db: Session) -> int:
        """
        Seed initial solutions for priority fault codes.
        Maps fault codes to specific technical solutions and product SKUs.
        """
        count = db.query(Solution).count()
        if count > 0:
            return 0

        # Mapping Fault Codes to Solutions and SKUs
        SOLUTIONS = [
            {
                'fault_code': 'P0706',
                'title': 'Reemplazo de Sensor TRS (Rango)',
                'description': 'El sensor de rango de transmisión (TRS) es propenso a fallas por humedad o desgaste en modelos Optra y Aveo.',
                'recommended_skus': ['TRS-CHEV-OPT', '93742966', '24157551082'],
                'collection_handle': 'sensores-de-rango'
            },
            {
                'fault_code': 'P0715',
                'title': 'Cambio de Sensor ISS / Velocidad de Entrada',
                'description': 'Reemplazar el sensor de velocidad de entrada (ISS) para restaurar la sincronización de cambios.',
                'recommended_skus': ['ISS-NISS-RE5', '31935-1XF01', 'G4T00171'],
                'collection_handle': 'sensores-de-velocidad'
            },
            {
                'fault_code': 'P0743',
                'title': 'Sustitución de Solenoide TCC',
                'description': 'Un solenoide de TCC defectuoso impide el acoplamiento correcto del convertidor de par.',
                'recommended_skus': ['TCC-FORD-4R70', 'F7AZ-7G136-AA', '24212690'],
                'collection_handle': 'solenoides'
            },
            {
                'fault_code': 'P0841',
                'title': 'Kit de Sensores de Presión CVT',
                'description': 'En transmisiones JF011E, el fallo del sensor de presión de fluido es común y requiere reemplazo.',
                'recommended_skus': ['PS-JF011E-KIT', '28600-RG5-004'],
                'collection_handle': 'sensores-de-presion'
            },
            {
                'fault_code': 'P0730',
                'title': 'Kit de Afinación Mayor / Overhaul',
                'description': 'La relación de engranajes incorrecta suele indicar desgaste de embragues internos que requiere una reparación mayor.',
                'recommended_skus': ['MK-A750E-VAG', 'OK-4L60E-GM'],
                'collection_handle': 'kits-de-reparacion'
            }
        ]

        for sol_data in SOLUTIONS:
            fc = self.get_fault_code(db, sol_data['fault_code'])
            if fc:
                solution = Solution(
                    id=str(uuid.uuid4()),
                    fault_code_id=fc.code,
                    title=sol_data['title'],
                    description=sol_data['description'],
                    recommended_skus=sol_data['recommended_skus'],
                    collection_url=f"/collections/{sol_data['collection_handle']}"
                )
                db.add(solution)
        
        db.commit()
        return len(SOLUTIONS)

    def get_solutions(self, db: Session, fault_code: str = None) -> List[Solution]:
        """Get solutions, optionally filtered by fault code"""
        query = db.query(Solution)
        if fault_code:
            fc = self.get_fault_code(db, fault_code)
            if fc:
                query = query.filter(Solution.fault_code_id == fc.code)
        return query.all()
    
    def get_fault_codes(self, db: Session, priority_only: bool = False) -> List[FaultCode]:
        """Get all fault codes, optionally filtering to priority only"""
        query = db.query(FaultCode)
        if priority_only:
            query = query.filter(FaultCode.is_priority == True)
        return query.order_by(FaultCode.monthly_clicks.desc()).all()
    
    def get_fault_code(self, db: Session, code: str) -> Optional[FaultCode]:
        """Get a single fault code by code"""
        return db.query(FaultCode).filter(FaultCode.code == code).first()
    
    def create_fault_code(self, db: Session, data: Dict) -> FaultCode:
        """Create a new fault code"""
        fault_code = FaultCode(
            code=data['code'],
            name=data['name'],
            description=data.get('description'),
            severity=data.get('severity', 'medium'),
            monthly_clicks=data.get('monthly_clicks', 0),
            monthly_impressions=data.get('monthly_impressions', 0),
            transmissions=data.get('transmissions', []),
            vehicles=data.get('vehicles', []),
            common_causes=data.get('common_causes', []),
            symptoms_text=data.get('symptoms_text', []),
            blog_url=data.get('blog_url'),
            collection_url=data.get('collection_url'),
            is_priority=data.get('is_priority', False),
            include_in_llms_txt=data.get('include_in_llms_txt', True)
        )
        db.add(fault_code)
        db.commit()
        db.refresh(fault_code)
        return fault_code
    
    def generate_faq_schema(self, db: Session, fault_code: str) -> Dict:
        """
        Generate FAQPage JSON-LD for a fault code.
        Auto-generates questions from fault code data.
        """
        fc = self.get_fault_code(db, fault_code)
        if not fc:
            return {"error": "Fault code not found"}
        
        # Auto-generate FAQ from fault code data
        questions = [
            {
                "question": f"¿Qué significa el código {fc.code}?",
                "answer": fc.description or f"El código {fc.code} indica un problema en la transmisión automática."
            },
            {
                "question": f"¿Cuáles son las causas del código {fc.code}?",
                "answer": ", ".join(fc.common_causes or ['Falla de componente electrónico', 'Problema de cableado'])
            },
            {
                "question": f"¿Cuáles son los síntomas del código {fc.code}?",
                "answer": ", ".join(fc.symptoms_text or ['Luz check engine encendida', 'Cambios bruscos'])
            },
            {
                "question": f"¿En qué vehículos aparece el código {fc.code}?",
                "answer": f"Este código es común en: {', '.join(fc.vehicles or ['Vehículos con transmisión automática'])}"
            }
        ]
        
        fc_dict = {
            'code': fc.code,
            'name': fc.name,
            'description': fc.description
        }
        
        return SchemaGenerator.faq_page(fc_dict, questions)
    
    def generate_howto_schema(self, db: Session, fault_code: str) -> Dict:
        """
        Generate HowTo JSON-LD for diagnosing a fault code.
        """
        fc = self.get_fault_code(db, fault_code)
        if not fc:
            return {"error": "Fault code not found"}
        
        steps = [
            {"name": "Conectar escáner", "text": "Conecte un escáner OBD-II al puerto de diagnóstico del vehículo."},
            {"name": "Leer códigos", "text": f"Lea los códigos almacenados y busque {fc.code}."},
            {"name": "Verificar síntomas", "text": f"Confirme los síntomas: {', '.join(fc.symptoms_text or [])}"},
            {"name": "Inspeccionar causas", "text": f"Revise las causas comunes: {', '.join(fc.common_causes or [])}"},
            {"name": "Reparar o reemplazar", "text": "Realice la reparación o reemplazo del componente identificado."},
            {"name": "Borrar código", "text": "Borre el código y realice prueba de manejo para confirmar la reparación."}
        ]
        
        return SchemaGenerator.how_to(
            title=f"Cómo diagnosticar código {fc.code}",
            description=fc.description or f"Guía paso a paso para diagnosticar el código de falla {fc.code}",
            steps=steps,
            estimated_time="PT30M"
        )


# Singleton instance
aeo_service = AEOService()
