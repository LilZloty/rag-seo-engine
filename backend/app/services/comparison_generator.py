"""
Comparison Table Generator
==========================

Generates comparison tables for fault codes, products, and transmissions.
Targets "vs" and "versus" search queries.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("comparison_generator")


@dataclass
class ComparisonRow:
    """Single row in comparison table."""
    feature: str
    value_a: str
    value_b: str
    winner: Optional[str]  # 'a', 'b', or None for tie


class ComparisonTableGenerator:
    """
    Generates comparison tables for SEO.
    
    Targets:
    - "P0700 vs P0706"
    - "4L60E vs 6L80E"
    - "Kit A vs Kit B"
    """
    
    # Fault code comparison data
    FAULT_CODE_COMPARISONS = {
        ("P0700", "P0706"): {
            "severity": ("Moderada", "Alta", "b"),
            "symptom_principal": ("Luz check engine", "No cambia de marcha", "b"),
            "componente_afectado": ("Sistema general", "Sensor de rango", "b"),
            "costo_reparacion": ("$2,000 - $4,000", "$1,500 - $3,000", None),
            "urgencia": ("Reparar pronto", "Reparar inmediatamente", "b"),
            "transmisiones_comunes": ("Múltiples", "4L60E, 4L80E", None),
        },
        ("P0700", "P0715"): {
            "severity": ("Moderada", "Alta", "b"),
            "symptom_principal": ("Luz check engine", "Tirones al cambiar", "b"),
            "componente_afectado": ("Sistema general", "Sensor de entrada", "b"),
            "costo_reparacion": ("$2,000 - $4,000", "$1,800 - $3,500", None),
            "urgencia": ("Reparar pronto", "Reparar pronto", None),
            "transmisiones_comunes": ("Múltiples", "JF011E, RE0F10A", None),
        },
        ("P0706", "P0715"): {
            "severity": ("Alta", "Alta", None),
            "symptom_principal": ("No cambia", "Tirones", None),
            "componente_afectado": ("Sensor rango", "Sensor velocidad", None),
            "costo_reparacion": ("$1,500 - $3,000", "$1,800 - $3,500", None),
            "urgencia": ("Inmediata", "Pronto", "a"),
            "transmisiones_comunes": ("GM principalmente", "Nissan, Mitsubishi", None),
        }
    }
    
    def generate_fault_code_comparison(
        self,
        code_a: str,
        code_b: str
    ) -> Dict:
        """
        Generate comparison between two fault codes.
        
        Returns:
            Dict with table data and HTML
        """
        # Try both orderings
        comparison_data = self.FAULT_CODE_COMPARISONS.get((code_a, code_b))
        if not comparison_data:
            comparison_data = self.FAULT_CODE_COMPARISONS.get((code_b, code_a))
            # Swap values if we found reverse order
            if comparison_data:
                swapped_data = {}
                for feature, (val_a, val_b, winner) in comparison_data.items():
                    new_winner = "a" if winner == "b" else ("b" if winner == "a" else None)
                    swapped_data[feature] = (val_b, val_a, new_winner)
                comparison_data = swapped_data
        
        # Default comparison if no specific data
        if not comparison_data:
            comparison_data = self._generate_default_comparison(code_a, code_b)
        
        rows = []
        for feature, (val_a, val_b, winner) in comparison_data.items():
            rows.append(ComparisonRow(
                feature=self._format_feature_name(feature),
                value_a=val_a,
                value_b=val_b,
                winner=winner
            ))
        
        html = self._generate_comparison_html(code_a, code_b, rows)
        
        return {
            "code_a": code_a,
            "code_b": code_b,
            "rows": [
                {
                    "feature": row.feature,
                    "value_a": row.value_a,
                    "value_b": row.value_b,
                    "winner": row.winner
                }
                for row in rows
            ],
            "html": html
        }
    
    def _generate_default_comparison(self, code_a: str, code_b: str) -> Dict:
        """Generate default comparison when specific data not available."""
        return {
            "severity": ("Variable", "Variable", None),
            "tipo_problema": ("Requiere diagnóstico", "Requiere diagnóstico", None),
            "diagnostico": ("Escáner profesional", "Escáner profesional", None),
            "reparacion": ("Depende de causa", "Depende de causa", None),
            "costo_estimado": ("Variable", "Variable", None),
        }
    
    def _format_feature_name(self, feature: str) -> str:
        """Convert snake_case to readable Spanish."""
        translations = {
            "severity": "Severidad",
            "symptom_principal": "Síntoma principal",
            "componente_afectado": "Componente afectado",
            "costo_reparacion": "Costo de reparación",
            "urgencia": "Urgencia",
            "transmisiones_comunes": "Transmisiones comunes",
            "tipo_problema": "Tipo de problema",
            "diagnostico": "Diagnóstico",
            "reparacion": "Reparación",
            "costo_estimado": "Costo estimado",
        }
        return translations.get(feature, feature.replace("_", " ").title())
    
    def _generate_comparison_html(
        self,
        code_a: str,
        code_b: str,
        rows: List[ComparisonRow]
    ) -> str:
        """Generate HTML comparison table."""
        rows_html = "\n".join([
            f'''<tr class="{'winner-a' if row.winner == 'a' else 'winner-b' if row.winner == 'b' else ''}">
                <td class="feature">{row.feature}</td>
                <td class="value-a"{' style="background:#F7B50022"' if row.winner == 'a' else ''}>{row.value_a}{' ✓' if row.winner == 'a' else ''}</td>
                <td class="value-b"{' style="background:#F7B50022"' if row.winner == 'b' else ''}>{row.value_b}{' ✓' if row.winner == 'b' else ''}</td>
            </tr>'''
            for row in rows
        ])
        
        return f'''<div class="comparison-table-container">
    <h3>{code_a} vs {code_b}: Comparación</h3>
    <table class="comparison-table">
        <thead>
            <tr>
                <th>Característica</th>
                <th><a href="/blogs/news/{code_a.lower()}">{code_a}</a></th>
                <th><a href="/blogs/news/{code_b.lower()}">{code_b}</a></th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <p class="comparison-note">✓ = Opción recomendada según severidad/costo</p>
</div>'''
    
    def generate_product_comparison(
        self,
        product_a: Dict,
        product_b: Dict
    ) -> Dict:
        """Generate comparison between two products."""
        rows = [
            ComparisonRow("Precio", f"${product_a.get('price', 'N/A')}", f"${product_b.get('price', 'N/A')}", None),
            ComparisonRow("Compatibilidad", product_a.get('transmission', 'N/A'), product_b.get('transmission', 'N/A'), None),
            ComparisonRow("Tipo", "Kit completo" if "kit" in product_a.get('title', '').lower() else "Pieza individual",
                         "Kit completo" if "kit" in product_b.get('title', '').lower() else "Pieza individual", None),
            ComparisonRow("Garantía", "12 meses", "12 meses", None),
            ComparisonRow("Instalación", "3-4 horas", "3-4 horas", None),
        ]
        
        return {
            "product_a": product_a,
            "product_b": product_b,
            "rows": [{"feature": r.feature, "value_a": r.value_a, "value_b": r.value_b} for r in rows],
            "html": self._generate_product_comparison_html(product_a, product_b, rows)
        }
    
    def _generate_product_comparison_html(
        self,
        product_a: Dict,
        product_b: Dict,
        rows: List[ComparisonRow]
    ) -> str:
        """Generate HTML for product comparison."""
        rows_html = "\n".join([
            f'''<tr>
                <td>{row.feature}</td>
                <td>{row.value_a}</td>
                <td>{row.value_b}</td>
            </tr>'''
            for row in rows
        ])
        
        return f'''<div class="product-comparison">
    <h3>Comparación de Productos</h3>
    <table class="comparison-table">
        <thead>
            <tr>
                <th>Característica</th>
                <th>{product_a.get('title', 'Producto A')}</th>
                <th>{product_b.get('title', 'Producto B')}</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</div>'''
    
    def generate_related_codes_table(
        self,
        primary_code: str,
        related_codes: List[str]
    ) -> str:
        """
        Generate table of related fault codes.
        
        Used at end of articles to capture "códigos relacionados" searches.
        """
        if not related_codes:
            return ""
        
        rows_html = "\n".join([
            f'''<tr>
                <td><strong><a href="/blogs/news/{code.lower()}">{code}</a></strong></td>
                <td>Sistema relacionado</td>
                <td><a href="/blogs/news/{code.lower()}">Ver guía →</a></td>
            </tr>'''
            for code in related_codes[:5]
        ])
        
        return f'''<div class="related-codes-table">
    <h3>Códigos de falla relacionados con {primary_code}</h3>
    <p>Estos códigos suelen aparecer junto con {primary_code}. Te recomendamos verificarlos también:</p>
    <table class="codes-table">
        <thead>
            <tr>
                <th>Código</th>
                <th>Relación</th>
                <th>Guía</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</div>'''


# Singleton instance
_comparison_generator = None


def get_comparison_generator() -> ComparisonTableGenerator:
    """Get comparison generator instance."""
    global _comparison_generator
    if _comparison_generator is None:
        _comparison_generator = ComparisonTableGenerator()
    return _comparison_generator
