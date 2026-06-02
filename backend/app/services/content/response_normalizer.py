"""
Response Normalizer - Normalize LLM responses to consistent format

Handles field mapping, validation, and fallback generation.
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


@dataclass
class NormalizedContent:
    """Normalized content with all required fields"""
    h1_title: str
    description_html: str
    short_description: str
    meta_title: str
    meta_description: str
    url_handle: str
    alt_tags: List[str]
    technical_specs: List[str]
    installation_guide: str
    faq_items: List[Dict]
    compatible_vehicles: str
    resumen: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "h1_title": self.h1_title,
            "description_html": self.description_html,
            "short_description": self.short_description,
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "url_handle": self.url_handle,
            "alt_tags": self.alt_tags,
            "technical_specs": self.technical_specs,
            "installation_guide": self.installation_guide,
            "faq_items": self.faq_items,
            "compatible_vehicles": self.compatible_vehicles,
            "resumen": self.resumen,
        }


class ResponseNormalizer:
    """Normalize LLM responses to consistent field format"""
    
    # Field mappings from various LLM response formats
    FIELD_MAPPINGS = {
        'h1_title': ['h1_title', 'h1', 'titulo', 'title', 'titulo_seo', 'seo_title', 'product_title'],
        'description_html': ['description_html', 'hook_html', 'descripcion', 'description', 'body_html', 'content', 'html_content', 'product_description'],
        'alt_tags': ['alt_tags', 'alt_textos', 'image_alts', 'alts', 'alt_texts', 'alt_text', 'imagenes_alt'],
        'meta_title': ['meta_title', 'meta_titulo', 'seo_meta_title', 'titulo_meta'],
        'meta_description': ['meta_description', 'meta_descripcion', 'seo_meta_description', 'descripcion_meta'],
        'url_handle': ['url_handle', 'handle', 'slug', 'url_slug', 'seo_url'],
        'short_description': ['short_description', 'descripcion_corta', 'excerpt'],
        'compatible_vehicles': ['compatible_vehicles', 'vehiculos', 'vehiculos_compatibles', 'vehicles'],
        'technical_specs': ['technical_specs', 'specs', 'especificaciones', 'especificaciones_tecnicas'],
        'installation_guide': ['installation_guide', 'guia_instalacion', 'instalacion'],
        'faq_items': ['faq_items', 'faq', 'preguntas_frecuentes'],
        'resumen': ['resumen', 'ficha_tecnica', 'technical_summary', 'resumen_tecnico'],
    }
    
    def __init__(self, product_info: Optional[Dict] = None):
        self.product_info = product_info or {}
        self.product_name = self.product_info.get('title', '')
        self.sku = self.product_info.get('sku', '')
        self.vendor = self.product_info.get('vendor', 'TSS')
        self.images = self.product_info.get('image_filenames', [])
    
    def _slugify(self, text: str) -> str:
        """Create URL-safe slug from text"""
        text = text.lower()
        # Remove accents
        text = text.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
        # Keep only alphanumeric and spaces
        text = re.sub(r'[^a-z0-9\s-]', '', text)
        # Replace spaces with hyphens
        text = re.sub(r'\s+', '-', text.strip())
        # Remove multiple hyphens
        return re.sub(r'-+', '-', text)
    
    def _generate_seo_url_handle(self, source_text: str, product_name: str) -> str:
        """
        Generate SEO-optimized URL handle.
        
        Strategy:
        1. Extract key SEO terms from source (product type + transmission code + key modifiers)
        2. Create a descriptive, keyword-rich URL
        3. Keep it under 100 chars for SEO best practices
        """
        import re
        
        # Common product type keywords for transmission parts
        product_types = {
            'aceite': 'aceite-transmision',
            'filtro': 'filtro-transmision',
            'carter': 'carter-transmision',
            'cuerpo valvulas': 'cuerpo-valvulas',
            'cuerpo de valvulas': 'cuerpo-valvulas',
            'solenoide': 'solenoide',
            'sensor': 'sensor',
            'bomba': 'bomba-aceite',
            'convertidor': 'convertidor-torque',
            'banda': 'banda-transmision',
            'kit': 'kit-reparacion',
            'modulo': 'modulo-control',
        }
        
        text_lower = source_text.lower()
        
        # Find product type
        product_type_slug = None
        for keyword, slug in sorted(product_types.items(), key=lambda x: -len(x[0])):  # Longest first
            if keyword in text_lower:
                product_type_slug = slug
                break
        
        # Extract transmission code (e.g., ZF8HP70, 6L80, etc.)
        trans_code_match = re.search(
            r'(ZF\d+HP\d+|\d+[LR]\d{2}[EW]?|[A-Z]{2}\d{3}[A-Z]*|\d{3}RE)',
            product_name, re.IGNORECASE
        )
        trans_code = trans_code_match.group(0).upper() if trans_code_match else None
        
        # Extract brand/vendor if present
        brand = None
        brands = ['ZF', 'TSS', 'Dacco', 'Sonna', 'Allison', 'Bosch']
        for b in brands:
            if b.lower() in text_lower or b.lower() in product_name.lower():
                brand = b.lower()
                break
        
        # Build URL parts in priority order
        url_parts = []
        
        # 1. Product type (most important for SEO)
        if product_type_slug:
            url_parts.append(product_type_slug)
        
        # 2. Transmission code (very important for search)
        if trans_code:
            url_parts.append(trans_code.lower())
        
        # 3. Brand (if not already in product type)
        if brand and brand not in '-'.join(url_parts):
            url_parts.append(brand)
        
        # 4. If we still don't have enough, add key terms from product name
        if len('-'.join(url_parts)) < 30:
            # Extract key words from product name (remove common words)
            stop_words = {'de', 'la', 'el', 'en', 'y', 'o', 'para', 'con', 'sin', 'un', 'una', 'los', 'las', 'al', 'del'}
            name_words = [w for w in self._slugify(product_name).split('-') 
                         if w and w not in stop_words and len(w) > 2]
            # Add unique words not already in URL
            existing = '-'.join(url_parts)
            for word in name_words[:5]:  # Limit to first 5 significant words
                if word not in existing and len(existing + '-' + word) < 100:
                    url_parts.append(word)
                    existing = '-'.join(url_parts)
        
        # Join and clean up
        url_handle = '-'.join(url_parts)
        url_handle = re.sub(r'-+', '-', url_handle)  # Remove duplicate hyphens
        url_handle = url_handle.strip('-')[:100]  # Max 100 chars, no trailing hyphens
        
        # Fallback to simple slug if empty
        if not url_handle:
            url_handle = self._slugify(product_name)[:100]
        
        return url_handle
    
    def normalize(self, parsed_json: Dict) -> NormalizedContent:
        """Normalize LLM response to consistent format"""
        
        # Map common field names to our expected names
        normalized = {}
        
        for target_field, source_fields in self.FIELD_MAPPINGS.items():
            for source in source_fields:
                if source in parsed_json and parsed_json[source]:
                    normalized[target_field] = parsed_json[source]
                    break
        
        # Create base slug from product name
        product_slug = self._slugify(self.product_name)[:60]
        
        # Ensure required fields have values (H1: 60 char max for SEO consistency)
        if not normalized.get('h1_title'):
            normalized['h1_title'] = self.product_name[:60] if len(self.product_name) > 60 else self.product_name
            logger.debug(f"h1_title missing, using product name (60 chars max)")
        elif len(normalized['h1_title']) > 60:
            normalized['h1_title'] = normalized['h1_title'][:60]
            logger.debug(f"h1_title truncated to 60 chars")
        
        if not normalized.get('description_html'):
            normalized['description_html'] = self.product_info.get('description', '')
            logger.debug(f"description_html missing, using existing description")
        
        # Generate unique alt_tags with proper SEO-friendly filenames
        if not normalized.get('alt_tags') and self.images:
            alt_tags = []
            for i, img in enumerate(self.images[:10]):
                unique_filename = f"{product_slug}-vista-{i+1}.jpg"
                alt_text = f"{self.product_name} - {self.vendor} - Vista {i+1}"
                alt_tags.append(f"{unique_filename} | {alt_text}")
            normalized['alt_tags'] = alt_tags
            logger.debug(f"alt_tags missing, generated {len(alt_tags)} with unique filenames")
        
        # Fix alt_tags if they don't have proper format
        if normalized.get('alt_tags'):
            fixed_alt_tags = []
            for i, alt in enumerate(normalized['alt_tags']):
                if '|' in alt:
                    parts = alt.split('|')
                    filename = parts[0].strip()
                    alt_text = parts[1].strip() if len(parts) > 1 else f"{self.product_name} - Vista {i+1}"
                    if len(filename) < 10 or filename.count('-') < 2:
                        filename = f"{product_slug}-vista-{i+1}.jpg"
                    fixed_alt_tags.append(f"{filename} | {alt_text}")
                else:
                    fixed_alt_tags.append(f"{product_slug}-vista-{i+1}.jpg | {alt}")
            normalized['alt_tags'] = fixed_alt_tags
        
        # Generate SEO-optimized url_handle if missing
        if not normalized.get('url_handle'):
            # Try to use meta_title first (already SEO-optimized), then product name
            source_text = normalized.get('meta_title', self.product_name)
            normalized['url_handle'] = self._generate_seo_url_handle(source_text, self.product_name)
            logger.debug(f"url_handle missing, generated: {normalized['url_handle']}")
        
        # Generate meta_title if missing
        if not normalized.get('meta_title'):
            trans_match = re.search(
                r'(\d{1,2}[LR]\d{2}[EW]?|ZF\d+HP\d+|[A-Z]{2}\d{3}[A-Z]*)',
                self.product_name, re.IGNORECASE
            )
            trans_code = trans_match.group(0) if trans_match else ''
            if trans_code:
                normalized['meta_title'] = f"{self.product_name[:45]} {trans_code} | {settings.STORE_NAME}"[:70]
            else:
                normalized['meta_title'] = f"{self.product_name[:50]} | {settings.STORE_NAME}"[:70]
            logger.debug(f"meta_title missing, generated")
        
        # Generate meta_description if missing
        if not normalized.get('meta_description'):
            trans_match = re.search(
                r'(\d{1,2}[LR]\d{2}[EW]?|ZF\d+HP\d+|[A-Z]{2}\d{3}[A-Z]*)',
                self.product_name, re.IGNORECASE
            )
            trans_code = trans_match.group(0) if trans_match else 'transmisión automática'
            normalized['meta_description'] = f"{self.product_name[:80]} para {trans_code}. {self.vendor}. 1 año garantía, envío express México."[:160]
            logger.debug(f"meta_description missing, generated")
        
        if not normalized.get('short_description'):
            h1 = normalized.get('h1_title', self.product_name)
            normalized['short_description'] = f"{h1}. {self.vendor}. Garantía de 1 año. Envío express 1-2 días a todo México."[:160]
            logger.debug(f"short_description missing, generated")
        
        # Fallback for compatible_vehicles
        if not normalized.get('compatible_vehicles') and normalized.get('description_html'):
            vehicles_match = re.search(
                r'<h4>\s*Veh[ií]culos[^<]*</h4>(.*?)(?=<h|$)',
                normalized['description_html'], re.IGNORECASE | re.DOTALL
            )
            if vehicles_match:
                vehicles_html = vehicles_match.group(1)
                normalized['compatible_vehicles'] = re.sub(r'<[^>]+>', ' ', vehicles_html).strip()[:500]
        
        # Fallback resumen (ficha técnica) if not generated by LLM
        if not normalized.get('resumen'):
            normalized['resumen'] = self._generate_fallback_resumen()
            logger.debug(f"resumen missing, generated fallback ficha técnica")
        
        # Get h1_title with SEO-optimized fallback (60 chars max for consistency)
        h1_title = normalized.get('h1_title')
        if not h1_title:
            h1_title = self.product_name[:60] if len(self.product_name) > 60 else self.product_name
        
        return NormalizedContent(
            h1_title=h1_title,
            description_html=normalized.get('description_html', ''),
            short_description=normalized.get('short_description', '')[:160],
            meta_title=normalized.get('meta_title', '')[:70],
            meta_description=normalized.get('meta_description', '')[:160],
            url_handle=normalized.get('url_handle', product_slug[:100]),
            alt_tags=normalized.get('alt_tags', []),
            technical_specs=normalized.get('technical_specs', []),
            installation_guide=normalized.get('installation_guide', '<p>Instalación profesional requerida.</p>'),
            faq_items=normalized.get('faq_items', []),
            compatible_vehicles=normalized.get('compatible_vehicles', ''),
            resumen=normalized.get('resumen', '')
        )
    
    def get_fallback_content(self) -> NormalizedContent:
        """Generate fallback content when LLM fails"""
        import re
        
        product_slug = self._slugify(self.product_name)[:60]
        
        # Use product description if available and substantial
        existing_description = self.product_info.get('description', '') or self.product_info.get('body_html', '')
        if existing_description and len(existing_description) > 50:
            description_html = existing_description if existing_description.startswith('<') else f"<p>{existing_description}</p>"
        else:
            description_html = f"""<h2>¿Por qué elegir {self.product_name}?</h2>
<p>El <strong>{self.product_name}</strong> es la elección ideal para mantener tu transmisión automática en óptimas condiciones. En <strong>{settings.STORE_NAME}</strong> garantizamos calidad OEM y el mejor precio del mercado.</p>
<h3>Especificaciones</h3>
<ul>
<li><strong>Marca:</strong> {self.vendor}</li>
<li><strong>SKU:</strong> {self.sku}</li>
<li><strong>Garantía:</strong> 1 año</li>
</ul>
<p>✅ Envío express 1-2 días a todo México.<br>📞 Asesoría técnica especializada.</p>"""
        
        # Generate alt_tags
        alt_tags = []
        for i, img in enumerate(self.images[:10] if self.images else [self.sku]):
            img_name = img if isinstance(img, str) else str(img)
            alt_tags.append(f"{img_name} | {self.product_name} - {self.vendor} - Vista {i+1}")
        if not alt_tags:
            alt_tags = [f"{product_slug[:50]}-vista-1.jpg | {self.product_name} - {settings.STORE_NAME}"]
        
        # Generate SEO-optimized URL handle from product name
        url_handle = self._generate_seo_url_handle(self.product_name, self.product_name)
        
        return NormalizedContent(
            h1_title=self.product_name[:60] if len(self.product_name) > 60 else self.product_name,
            description_html=description_html,
            short_description=f"{self.product_name}. {self.vendor}. Garantía 1 año. Envío express México."[:160],
            meta_title=f"{self.product_name[:55]} | {settings.STORE_NAME}"[:70],
            meta_description=f"{self.product_name[:80]}. {self.vendor}. Garantía 1 año. Envío express 1-2 días México."[:160],
            url_handle=url_handle,
            alt_tags=alt_tags,
            technical_specs=[
                f"Marca: {self.vendor}",
                f"SKU: {self.sku}",
                "Garantía: 1 año",
                "Calidad OEM garantizada"
            ],
            installation_guide="<p>Instalación profesional recomendada. Consulte el manual de servicio del fabricante para procedimientos específicos.</p>",
            faq_items=[
                {"question": "¿Qué garantía tiene este producto?", "answer": "1 año de garantía contra defectos de fabricación."},
                {"question": "¿Cuánto tarda el envío?", "answer": "Envío express 1-2 días hábiles a todo México."}
            ],
            compatible_vehicles="Consultar compatibilidad en la descripción del producto.",
            resumen=self._generate_fallback_resumen()
        )

    def _generate_fallback_resumen(self) -> str:
        """Generate a fallback ficha técnica HTML table from product info"""
        product_type = self.product_info.get('product_type', 'Parte de Transmisión')
        rows = [
            ('SKU', self.sku or 'N/A'),
            ('Producto', self.product_name or 'N/A'),
            ('Marca', self.vendor or 'N/A'),
            ('Tipo', product_type or 'N/A'),
            ('Garantía', '1 año'),
        ]
        
        rows_html = ''
        for label, value in rows:
            rows_html += (
                f'<tr>'
                f'<td style="padding:10px;border:1px solid #ddd;"><strong>{label}</strong></td>'
                f'<td style="padding:10px;border:1px solid #ddd;">{value}</td>'
                f'</tr>\n'
            )
        
        return (
            f'<h4>Ficha Técnica</h4>\n'
            f'<div style="overflow-x:auto;">\n'
            f'<table style="width:100%;border-collapse:collapse;">\n'
            f'<tbody>\n'
            f'<tr style="background-color:#f2f2f2;">'
            f'<th style="padding:10px;text-align:left;border:1px solid #ddd;">Dato</th>'
            f'<th style="padding:10px;text-align:left;border:1px solid #ddd;">Especificación</th>'
            f'</tr>\n'
            f'{rows_html}'
            f'</tbody>\n'
            f'</table>\n'
            f'</div>'
        )


def normalize_response(
    parsed_json: Dict,
    product_info: Optional[Dict] = None
) -> NormalizedContent:
    """Convenience function to normalize LLM response"""
    normalizer = ResponseNormalizer(product_info)
    return normalizer.normalize(parsed_json)


def get_fallback_content(product_info: Optional[Dict] = None) -> Dict:
    """Convenience function to get fallback content"""
    normalizer = ResponseNormalizer(product_info)
    fallback = normalizer.get_fallback_content()
    return fallback.to_dict()
