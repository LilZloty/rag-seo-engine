"""
SOLUTION ENGINE SERVICE - Phase 1 Implementation
=================================================

Core service for connecting fault codes to products and blog content.
Simplified for Phase 1 - focuses on fault code analysis and product matching.
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.core.config import settings

from app.models.product import Product
from app.models.aeo_models import FaultCode

logger = logging.getLogger("solution_engine")


class SolutionEngine:
    """
    AI-powered engine that connects search queries to solutions.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # FAULT CODE → PRODUCT ANALYSIS
    # =========================================================================
    
    def get_products_for_fault_code(self, fault_code: str, limit: int = 10) -> List[Dict]:
        """
        Get products that can fix a specific fault code.
        
        Uses transmission matching and keyword analysis.
        """
        # Get fault code details
        fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        if not fc:
            return []
        
        # Get matching products
        products = self._get_candidate_products(fc, limit)
        
        # Enrich with match reasoning
        enriched = []
        for i, product in enumerate(products, 1):
            match_reason = self._generate_match_reason(fc, product)
            
            enriched.append({
                "rank": i,
                "product_id": product.id,
                "sku": product.sku,
                "title": product.title,
                "handle": product.handle,
                "price": product.price,
                "transmission_code": product.transmission_code,
                "product_type": product.product_type,
                "total_sold": product.total_sold,
                "url": f"/products/{product.handle}" if product.handle else None,
                "match_score": match_reason["score"],
                "reasoning": match_reason["reason"],
                "fix_probability": match_reason["probability"]
            })
        
        return enriched
    
    def _get_candidate_products(self, fault_code: FaultCode, limit: int = 10) -> List[Product]:
        """Get products relevant to a fault code."""
        transmissions = fault_code.transmissions or []
        
        if not transmissions:
            # If no transmission data, return best sellers
            return self.db.query(Product).filter(
                Product.inventory_quantity > 0
            ).order_by(desc(Product.total_sold)).limit(limit).all()
        
        # Query products matching the transmissions
        products = self.db.query(Product).filter(
            Product.transmission_code.in_(transmissions),
            Product.inventory_quantity > 0
        ).order_by(desc(Product.total_sold)).limit(limit).all()
        
        return products
    
    def _generate_match_reason(self, fc: FaultCode, product: Product) -> Dict:
        """Generate reasoning for why this product matches the fault code."""
        
        score = 50  # Base score
        reasons = []
        probability = "medium"
        
        # Check transmission match
        if fc.transmissions and product.transmission_code in fc.transmissions:
            score += 25
            reasons.append(f"Compatible with {product.transmission_code}")
        
        # Check sales volume (social proof)
        if product.total_sold and product.total_sold > 100:
            score += 10
            reasons.append(f"Popular choice ({product.total_sold} sold)")
        
        # Check common causes match
        causes = fc.common_causes or []
        cause_product_mapping = {
            'solenoid': ['Solenoides', 'Partes Electrizas', 'Kits de Reparación'],
            'sensor': ['Sensores', 'Partes Electrizas'],
            'pressure': ['Cuerpo de Válvulas', 'Filtros'],
            'cableado': ['Partes Electrizas'],
            'TCM': ['Partes Electrizas', 'Mecatrónicas']
        }
        
        for cause in causes:
            cause_lower = cause.lower()
            for key, product_types in cause_product_mapping.items():
                if key in cause_lower and product.product_type in product_types:
                    score += 15
                    reasons.append(f"Addresses: {cause}")
                    probability = "high"
                    break
        
        # Cap score at 100
        score = min(score, 100)
        
        if score >= 80:
            probability = "high"
        elif score >= 60:
            probability = "medium"
        else:
            probability = "low"
        
        return {
            "score": score,
            "reason": "; ".join(reasons) if reasons else f"Compatible transmission: {product.transmission_code}",
            "probability": probability
        }
    
    # =========================================================================
    # SOLUTION PATH GENERATOR
    # =========================================================================
    
    def generate_solution_path(self, query: str) -> Dict:
        """
        Generate a solution path for a search query.
        
        Returns step-by-step journey from query to purchase.
        """
        # Parse query
        fault_code = self._extract_fault_code(query)
        intent = self._parse_query_intent(query)
        
        # Get fault code info
        fc_info = None
        if fault_code:
            fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
            if fc:
                fc_info = {
                    "code": fc.code,
                    "name": fc.name,
                    "description": fc.description,
                    "symptoms": fc.symptoms_text,
                    "causes": fc.common_causes
                }
        
        # Get product recommendations
        products = self.get_products_for_fault_code(fault_code, 3) if fault_code else []
        
        # Build steps based on intent
        steps = self._build_steps(intent, fc_info, products, query)
        
        return {
            "query": query,
            "fault_code": fault_code,
            "intent": intent,
            "steps": steps,
            "products": products[:3],
            "created_at": datetime.utcnow().isoformat()
        }
    
    def _extract_fault_code(self, query: str) -> Optional[str]:
        """Extract fault code from query string."""
        import re
        match = re.search(r'[PBCU]\d{4}', query.upper())
        return match.group(0) if match else None
    
    def _parse_query_intent(self, query: str) -> str:
        """Determine user intent from query."""
        query_lower = query.lower()
        
        informational_keywords = ['que es', 'significa', 'codigo', 'significado', 'definicion']
        diagnostic_keywords = ['diagnostico', 'sintomas', 'porque', 'falla', 'problema']
        repair_keywords = ['reparar', 'solucion', 'arreglar', 'como', 'fix']
        purchase_keywords = ['comprar', 'precio', 'kit', 'donde', 'venta']
        
        if any(kw in query_lower for kw in purchase_keywords):
            return "purchase"
        elif any(kw in query_lower for kw in repair_keywords):
            return "repair"
        elif any(kw in query_lower for kw in diagnostic_keywords):
            return "diagnostic"
        elif any(kw in query_lower for kw in informational_keywords):
            return "informational"
        else:
            return "diagnostic"  # Default
    
    def _build_steps(self, intent: str, fc_info: Optional[Dict], products: List[Dict], query: str) -> List[Dict]:
        """Build solution steps based on intent."""
        steps = []
        
        if intent == "informational":
            steps = [
                {"step": 1, "type": "info", "title": "Understanding the Code", "content": fc_info["description"] if fc_info else "Learn what this code means"},
                {"step": 2, "type": "learn", "title": "Common Symptoms", "content": ", ".join(fc_info["symptoms"][:3]) if fc_info and fc_info["symptoms"] else "Learn the symptoms"},
                {"step": 3, "type": "blog", "title": "Read Full Guide", "content": f"Detailed guide for {fc_info['code']}" if fc_info else "Read diagnostic guide"}
            ]
        
        elif intent == "diagnostic":
            steps = [
                {"step": 1, "type": "identify", "title": "Identify the Problem", "content": fc_info["description"] if fc_info else "Identify symptoms"},
                {"step": 2, "type": "diagnose", "title": "Diagnose Cause", "content": f"Common causes: {', '.join(fc_info['causes'][:2])}" if fc_info and fc_info["causes"] else "Check common causes"},
                {"step": 3, "type": "tool", "title": "Use Diagnostic Tool", "content": "Use OBDII scanner to confirm"},
                {"step": 4, "type": "solution", "title": "Recommended Solution", "content": products[0]["reasoning"] if products else "Contact support"}
            ]
        
        elif intent == "repair":
            steps = [
                {"step": 1, "type": "blog", "title": "Repair Guide", "content": f"Step-by-step guide for {fc_info['code']}" if fc_info else "Repair guide"},
                {"step": 2, "type": "parts", "title": "Parts You'll Need", "content": f"{products[0]['title']}" if products else "See recommended parts"},
                {"step": 3, "type": "purchase", "title": "Order Parts", "content": "Order now to fix your transmission"},
                {"step": 4, "type": "support", "title": "Technical Support", "content": "Contact our experts if you need help"}
            ]
        
        elif intent == "purchase":
            steps = [
                {"step": 1, "type": "products", "title": "Recommended Products", "content": "Best products for your needs"},
                {"step": 2, "type": "compare", "title": "Compare Options", "content": "See all compatible parts"},
                {"step": 3, "type": "purchase", "title": "Buy Now", "content": "Add to cart and checkout"}
            ]
        
        return steps
    
    # =========================================================================
    # SMART SNIPPET GENERATOR (Basic Version)
    # =========================================================================
    
    def generate_smart_snippet(self, query: str) -> Dict:
        """
        Generate an optimized answer for a search query.
        
        Basic version - creates structured answers from fault code data.
        """
        fault_code = self._extract_fault_code(query)
        
        if not fault_code:
            return {
                "query": query,
                "short_answer": "Learn more about this topic on our site.",
                "detailed_answer": "We have comprehensive guides to help you.",
                "authority_quote": f"{settings.STORE_NAME} - Especialistas en Transmisiones"
            }
        
        fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        
        if not fc:
            return {
                "query": query,
                "short_answer": f"{fault_code} is a transmission fault code.",
                "detailed_answer": f"Learn more about {fault_code} and how to fix it.",
                "authority_quote": f"{settings.STORE_NAME} - Más de 10,000 mecánicos ayudados"
            }
        
        # Get products
        products = self.get_products_for_fault_code(fault_code, 2)
        
        # Build snippet
        short_answer = f"{fc.code}: {fc.name}. "
        if fc.symptoms_text:
            short_answer += f"Síntomas: {fc.symptoms_text[0]}. "
        if products:
            short_answer += f"Solución: {products[0]['title']}."
        
        detailed_answer = f"""
{fc.code} - {fc.name}

{fc.description}

Síntomas comunes:
{chr(10).join(['- ' + s for s in (fc.symptoms_text or [])[:3]])}

Causas más frecuentes:
{chr(10).join(['- ' + c for c in (fc.common_causes or [])[:3]])}

Productos recomendados:
{chr(10).join(['- ' + p['title'] + ' (' + p['reasoning'] + ')' for p in products[:2]])}
""".strip()
        
        return {
            "query": query,
            "fault_code": fault_code,
            "short_answer": short_answer[:300],
            "detailed_answer": detailed_answer,
            "authority_quote": f"{settings.STORE_NAME} - {fc.monthly_clicks or 0}+ búsquedas mensuales sobre este código. Expertos en transmisiones.",
            "statistic_claims": [
                f"{products[0]['total_sold']}+ unidades vendidas" if products and products[0]['total_sold'] else "Producto recomendado por expertos",
                f"Compatible con {', '.join(fc.transmissions or [])}" if fc.transmissions else ""
            ],
            "related_products": [p["product_id"] for p in products[:2]],
            "created_at": datetime.utcnow().isoformat()
        }
    
    # =========================================================================
    # DASHBOARD STATS
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """Get Solution Engine statistics."""
        
        # Count fault codes with products
        fault_codes = self.db.query(FaultCode).all()
        
        fc_with_products = 0
        total_products_matched = 0
        
        for fc in fault_codes:
            products = self.get_products_for_fault_code(fc.code, 1)
            if products:
                fc_with_products += 1
            total_products_matched += len(self.get_products_for_fault_code(fc.code, 100))
        
        return {
            "fault_codes_total": len(fault_codes),
            "fault_codes_with_products": fc_with_products,
            "coverage_percentage": round((fc_with_products / len(fault_codes) * 100), 1) if fault_codes else 0,
            "total_product_matches": total_products_matched,
            "top_fault_codes": [
                {
                    "code": fc.code,
                    "clicks": fc.monthly_clicks or 0,
                    "products_available": len(self.get_products_for_fault_code(fc.code, 10))
                }
                for fc in sorted(fault_codes, key=lambda x: x.monthly_clicks or 0, reverse=True)[:5]
            ]
        }


# Factory function
def get_solution_engine(db: Session) -> SolutionEngine:
    """Get SolutionEngine instance."""
    return SolutionEngine(db)
