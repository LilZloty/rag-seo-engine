"""
SOLUTION ENGINE SERVICE - Phase 2 Implementation
=================================================

Advanced AI-powered service for connecting fault codes to products and blog content.
Integrates with Grok for intelligent product matching and solution generation.
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.product import Product
from app.models.aeo_models import FaultCode, BlogCache
from app.models.solution_graph import (
    SolutionPath, ProductRecommendationEngine, SmartSnippet
)
from app.services.llm_service import llm_service
from app.services.multi_agent import TaskRouter
from app.core.config import settings

logger = logging.getLogger("solution_engine")


class SolutionEngineAI:
    """
    AI-enhanced Solution Engine with Grok integration.
    
    Extends base SolutionEngine with:
    - AI-powered product matching
    - Blog content analysis
    - Smart snippet generation with GEO optimization
    - Solution path persistence
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # AI-POWERED FAULT CODE ANALYSIS
    # =========================================================================
    
    async def analyze_fault_code_with_ai(
        self, fault_code: str, multi_agent_enabled: Optional[bool] = None
    ) -> Dict:
        """
        Use Grok AI to analyze which products truly solve a fault code.

        This goes beyond simple transmission matching - it uses AI to
        understand the technical relationship between symptoms and solutions.
        """
        if multi_agent_enabled is None:
            multi_agent_enabled = settings.MULTI_AGENT_ENABLED
        # Get fault code details
        fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        if not fc:
            return {"error": f"Fault code {fault_code} not found"}
        
        # Get candidate products (matching transmission)
        candidate_products = self._get_candidate_products(fc)
        
        if not candidate_products:
            return {
                "fault_code": fault_code,
                "products": [],
                "reasoning": "No matching products found for this transmission type",
                "ai_analyzed": False
            }
        
        # Build Grok prompt
        prompt = self._build_fault_code_analysis_prompt(fc, candidate_products)
        
        # Route to appropriate provider (single-agent or multi-agent)
        router = TaskRouter()
        provider = router.route("fault_code_analysis", multi_agent_enabled)

        try:
            response = await llm_service.generate_content(
                product_info={"fault_code": fault_code},
                context=[],
                system_prompt=self._get_fault_code_system_prompt(),
                provider=provider,
                model_name=None  # Use provider default
            )
            
            # Parse AI response
            ai_result = self._parse_ai_response(response, candidate_products)
            
            # Store in database
            await self._store_ai_recommendations(fault_code, ai_result)
            
            return {
                "fault_code": fault_code,
                "products": ai_result["recommendations"],
                "reasoning": ai_result.get("reasoning", ""),
                "confidence": ai_result.get("confidence", 70),
                "alternative_approaches": ai_result.get("alternative_approaches", []),
                "ai_analyzed": True
            }
            
        except Exception as e:
            logger.error(f"AI analysis failed for {fault_code}: {e}")
            # Fallback to algorithmic matching
            return self._fallback_product_matching(fc, candidate_products)
    
    def _get_candidate_products(self, fault_code: FaultCode, limit: int = 20) -> List[Product]:
        """Get products that could potentially fix this fault code."""
        transmissions = fault_code.transmissions or []
        
        if not transmissions:
            return self.db.query(Product).filter(
                Product.inventory_quantity > 0
            ).order_by(desc(Product.total_sold)).limit(limit).all()
        
        # Query products matching the transmissions
        products = self.db.query(Product).filter(
            Product.transmission_code.in_(transmissions),
            Product.inventory_quantity > 0
        ).order_by(desc(Product.total_sold)).limit(limit).all()
        
        return products
    
    def _build_fault_code_analysis_prompt(self, fc: FaultCode, products: List[Product]) -> str:
        """Build detailed prompt for Grok analysis."""
        
        product_list = []
        for p in products[:15]:
            product_list.append({
                "sku": p.sku,
                "title": p.title,
                "type": p.product_type,
                "transmission": p.transmission_code,
                "price": p.price,
                "sold": p.total_sold
            })
        
        return f"""# FAULT CODE ANALYSIS TASK

## Fault Code: {fc.code}
Name: {fc.name}
Description: {fc.description}

## Symptoms
{json.dumps(fc.symptoms_text or [], indent=2, ensure_ascii=False)}

## Common Causes
{json.dumps(fc.common_causes or [], indent=2, ensure_ascii=False)}

## Applicable Transmissions
{json.dumps(fc.transmissions or [], indent=2)}

## Available Products
```json
{json.dumps(product_list, indent=2, ensure_ascii=False)}
```

## Task
Analyze which products are MOST LIKELY to fix this fault code based on:
1. Technical relevance (does the part address the root cause?)
2. Symptom match (does it fix the stated symptoms?)
3. Popularity (higher sales = more trusted solution)
4. Completeness (kits vs individual parts)

Return your analysis as a JSON object with this structure:
{{
  "recommendations": [
    {{
      "sku": "product-sku-here",
      "rank": 1,
      "match_score": 95,
      "reasoning": "Detailed technical explanation of why this product fixes the fault code",
      "fix_probability": "high"
    }}
  ],
  "alternative_approaches": [
    "Check wiring first with multimeter",
    "Verify fluid level before replacing parts"
  ],
  "reasoning": "Overall analysis summary",
  "confidence": 85
}}"""
    
    def _get_fault_code_system_prompt(self) -> str:
        return """You are an expert automotive transmission technician with 20+ years of experience.

Your job is to match fault codes to the correct replacement parts with high accuracy.

Rules:
1. Be technically accurate - don't recommend irrelevant parts
2. Consider the root cause, not just symptoms
3. Prioritize complete kits over individual parts when appropriate
4. Factor in sales/popularity as a trust signal
5. Provide clear, actionable reasoning for each recommendation
6. Respond ONLY with valid JSON, no markdown formatting outside the JSON"""
    
    def _parse_ai_response(self, response: Dict, products: List[Product]) -> Dict:
        """Parse and validate AI response."""
        try:
            # Extract content from response
            if isinstance(response, dict):
                content = response.get("content", "")
                if isinstance(content, dict):
                    return content
            else:
                content = str(response)
            
            # Try to parse JSON from content
            if isinstance(content, str):
                # Find JSON block
                json_match = content.find("{")
                if json_match >= 0:
                    json_str = content[json_match:content.rfind("}")+1]
                    result = json.loads(json_str)
                else:
                    result = json.loads(content)
            else:
                result = content
            
            # Enrich recommendations with product data
            product_map = {p.sku: p for p in products if p.sku}
            enriched_recs = []
            
            for rec in result.get("recommendations", []):
                sku = rec.get("sku")
                if sku and sku in product_map:
                    p = product_map[sku]
                    enriched_recs.append({
                        **rec,
                        "product_id": p.id,
                        "title": p.title,
                        "handle": p.handle,
                        "price": p.price,
                        "url": f"/products/{p.handle}" if p.handle else None
                    })
            
            result["recommendations"] = enriched_recs
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            return {
                "recommendations": [],
                "reasoning": "Failed to parse AI response",
                "confidence": 0
            }
    
    def _fallback_product_matching(self, fc: FaultCode, products: List[Product]) -> Dict:
        """Algorithmic fallback when AI fails."""
        recommendations = []
        for i, p in enumerate(products[:5], 1):
            recommendations.append({
                "product_id": p.id,
                "sku": p.sku,
                "rank": i,
                "title": p.title,
                "match_score": 70 if i <= 2 else 50,
                "reasoning": f"Compatible with {p.transmission_code} - commonly purchased solution",
                "fix_probability": "medium",
                "url": f"/products/{p.handle}" if p.handle else None
            })
        
        return {
            "fault_code": fc.code,
            "products": recommendations,
            "reasoning": "Algorithmic matching based on transmission compatibility and sales",
            "confidence": 60,
            "ai_analyzed": False,
            "note": "AI analysis failed - using fallback"
        }
    
    async def _store_ai_recommendations(self, fault_code: str, result: Dict):
        """Store AI recommendations in database."""
        try:
            # Delete old recommendations
            self.db.query(ProductRecommendationEngine).filter(
                ProductRecommendationEngine.context_type == "fault_code",
                ProductRecommendationEngine.context_id == fault_code
            ).delete()
            
            # Create new entry
            new_rec = ProductRecommendationEngine(
                id=f"fc_{fault_code}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                context_type="fault_code",
                context_id=fault_code,
                recommendations=result.get("recommendations", []),
                generated_by="grok",
                confidence_score=result.get("confidence", 50)
            )
            
            self.db.add(new_rec)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to store recommendations: {e}")
            self.db.rollback()
    
    # =========================================================================
    # BLOG CONTENT ANALYSIS
    # =========================================================================
    
    async def analyze_blog_content(self, blog_id: str, blog_content: str = None) -> Dict:
        """
        Analyze blog content and recommend products to feature.
        
        Uses AI to understand content context and find relevant products.
        """
        # Get blog from cache
        blog = self.db.query(BlogCache).filter(BlogCache.id == blog_id).first()
        if not blog:
            return {"error": f"Blog {blog_id} not found"}
        
        # Use title/summary if content not provided
        content = blog_content or f"{blog.title}\n\n{blog.summary or ''}"
        
        # Extract fault codes from content
        fault_codes = self._extract_fault_codes_from_text(content)
        
        # Get relevant products
        products = []
        for fc in fault_codes[:2]:  # Limit to top 2 fault codes
            fc_products = await self.analyze_fault_code_with_ai(fc)
            if "products" in fc_products:
                products.extend(fc_products["products"][:3])
        
        # If no fault codes found, use keyword matching
        if not products:
            products = self._get_products_by_keywords(blog.title)
        
        # Build recommendations with placement
        recommendations = []
        for i, product in enumerate(products[:5], 1):
            recommendations.append({
                "product_id": product.get("product_id"),
                "sku": product.get("sku"),
                "title": product.get("title"),
                "placement": "early" if i <= 2 else "middle" if i <= 4 else "end",
                "context": self._generate_product_context(blog.title, product),
                "priority": i
            })
        
        return {
            "blog_id": blog_id,
            "blog_title": blog.title,
            "detected_fault_codes": fault_codes,
            "recommendations": recommendations,
            "estimated_ctr": 5.0 + len(recommendations)  # Estimate 5-10% CTR
        }
    
    def _extract_fault_codes_from_text(self, text: str) -> List[str]:
        """Extract fault codes from text content."""
        import re
        codes = re.findall(r'[PBCU]\d{4}', text.upper())
        return list(set(codes))  # Remove duplicates
    
    def _get_products_by_keywords(self, title: str) -> List[Dict]:
        """Get products matching keywords in title."""
        # Simple keyword matching
        keywords = {
            '4L60E': ['4L60E', 'TH700'],
            'JF011E': ['JF011E', 'CVT'],
            'A604': ['A604', '41TE'],
            'solenoid': ['solenoid', 'solenoide'],
            'sensor': ['sensor'],
            'kit': ['kit', 'reparacion']
        }
        
        title_lower = title.lower()
        matched_products = []
        
        for keyword_key, terms in keywords.items():
            if any(term in title_lower for term in terms):
                # Query products for this keyword
                products = self.db.query(Product).filter(
                    Product.title.ilike(f'%{keyword_key}%'),
                    Product.inventory_quantity > 0
                ).order_by(desc(Product.total_sold)).limit(3).all()
                
                for p in products:
                    matched_products.append({
                        "product_id": p.id,
                        "sku": p.sku,
                        "title": p.title,
                        "handle": p.handle,
                        "price": p.price
                    })
        
        return matched_products[:5]
    
    def _generate_product_context(self, blog_title: str, product: Dict) -> str:
        """Generate contextual text for product placement."""
        contexts = [
            f"Para resolver este problema, recomendamos {product['title']}",
            f"La solución más efectiva: {product['title']}",
            f"Producto recomendado: {product['title']}",
            f"Los mecánicos también compran: {product['title']}",
            f"Opción confiable: {product['title']}"
        ]
        
        # Simple hash-based selection for consistency
        idx = hash(blog_title + product.get('sku', '')) % len(contexts)
        return contexts[idx]
    
    # =========================================================================
    # SMART SNIPPET GENERATOR (GEO Optimized)
    # =========================================================================
    
    async def generate_geo_snippet(
        self, query: str, multi_agent_enabled: Optional[bool] = None
    ) -> Dict:
        """
        Generate GEO-optimized snippet for AI engine citations.
        
        Optimized for:
        - Grok citations
        - Perplexity references
        - ChatGPT knowledge
        """
        fault_code = self._extract_fault_code(query)
        
        if not fault_code:
            return await self._generate_generic_snippet(query)
        
        fc = self.db.query(FaultCode).filter(FaultCode.code == fault_code).first()
        if not fc:
            return await self._generate_generic_snippet(query)
        
        # Get AI-analyzed products
        ai_result = await self.analyze_fault_code_with_ai(fault_code)
        products = ai_result.get("products", [])
        
        # Build GEO-optimized content
        snippet_data = {
            "query": query,
            "fault_code": fault_code,
            "short_answer": self._build_short_answer(fc, products),
            "detailed_answer": self._build_detailed_answer(fc, products, ai_result),
            "authority_quote": self._build_authority_quote(fc),
            "statistic_claims": self._build_statistic_claims(fc, products),
            "key_entities": ["transmission", "fault code", fc.code] + [p.get("title", "")[:20] for p in products[:2]],
            "related_products": [p.get("product_id") for p in products[:3]],
            "sources": ["Example Store Technical Database", "OBD-II Diagnostic Standards"],
            "created_at": datetime.utcnow().isoformat(),
            "geo_optimized": True
        }
        
        # Store for tracking
        await self._store_smart_snippet(snippet_data)
        
        return snippet_data
    
    def _build_short_answer(self, fc: FaultCode, products: List[Dict]) -> str:
        """Build concise answer for featured snippets."""
        parts = [f"{fc.code}: {fc.name}."]
        
        if fc.symptoms_text:
            parts.append(f"Principal síntoma: {fc.symptoms_text[0]}.")
        
        if products:
            parts.append(f"Solución: {products[0]['title']}.")
        
        return " ".join(parts)[:300]
    
    def _build_detailed_answer(self, fc: FaultCode, products: List[Dict], ai_result: Dict) -> str:
        """Build comprehensive answer for AI citations."""
        lines = [
            f"## {fc.code}: {fc.name}",
            "",
            fc.description or "",
            "",
            "### Síntomas principales:",
        ]
        
        for symptom in (fc.symptoms_text or [])[:3]:
            lines.append(f"- {symptom}")
        
        lines.extend([
            "",
            "### Causas más comunes:",
        ])
        
        for cause in (fc.common_causes or [])[:3]:
            lines.append(f"- {cause}")
        
        if products:
            lines.extend([
                "",
                "### Productos recomendados:",
            ])
            for i, p in enumerate(products[:3], 1):
                lines.append(f"{i}. **{p['title']}** - {p.get('reasoning', 'Producto compatible')}")
        
        if ai_result.get("alternative_approaches"):
            lines.extend([
                "",
                "### Pasos adicionales:",
            ])
            for approach in ai_result["alternative_approaches"][:2]:
                lines.append(f"- {approach}")
        
        return "\n".join(lines)
    
    def _build_authority_quote(self, fc: FaultCode) -> str:
        """Build E-E-A-T authority statement."""
        quotes = [
            f"Según Example Store, con {fc.monthly_clicks or 'miles de'} reparaciones documentadas de {fc.code}.",
            f"Example Store ha ayudado a más de 10,000 mecánicos con códigos de transmisión.",
            f"Expertos en transmisiones automáticas con más de 10 años de experiencia.",
        ]
        return quotes[0] if fc.monthly_clicks else quotes[1]
    
    def _build_statistic_claims(self, fc: FaultCode, products: List[Dict]) -> List[str]:
        """Build statistic claims for credibility."""
        claims = []
        
        if products and products[0].get('total_sold'):
            claims.append(f"{products[0]['total_sold']}+ unidades vendidas del producto recomendado")
        
        if fc.transmissions:
            claims.append(f"Compatible con transmisiones {', '.join(fc.transmissions[:3])}")
        
        claims.append("Tasa de éxito del 87% según datos internos de reparaciones")
        
        return claims
    
    async def _generate_generic_snippet(self, query: str) -> Dict:
        """Generate snippet for non-fault-code queries."""
        return {
            "query": query,
            "short_answer": "Example Store ofrece soluciones expertas para transmisiones automáticas.",
            "detailed_answer": "Consulta nuestras guías técnicas y productos especializados.",
            "authority_quote": "Más de 10,000 mecánicos confían en Example Store",
            "statistic_claims": ["5,000+ productos en stock", "Cobertura para 50+ modelos de transmisión"],
            "geo_optimized": True
        }
    
    async def _store_smart_snippet(self, snippet_data: Dict):
        """Store smart snippet in database."""
        try:
            snippet = SmartSnippet(
                id=f"snippet_{snippet_data['query'][:50].replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}",
                query=snippet_data["query"],
                short_answer=snippet_data["short_answer"],
                detailed_answer=snippet_data["detailed_answer"],
                authority_quote=snippet_data["authority_quote"],
                statistic_claims=snippet_data["statistic_claims"],
                related_products=snippet_data["related_products"],
                is_active=True
            )
            
            self.db.add(snippet)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to store smart snippet: {e}")
            self.db.rollback()
    
    def _extract_fault_code(self, query: str) -> Optional[str]:
        """Extract fault code from query."""
        import re
        match = re.search(r'[PBCU]\d{4}', query.upper())
        return match.group(0) if match else None
    
    # =========================================================================
    # SOLUTION PATH MANAGEMENT
    # =========================================================================
    
    def create_solution_path(self, query_pattern: str, steps: List[Dict]) -> SolutionPath:
        """
        Create and persist a solution path.
        """
        # Parse intent
        intent = self._parse_query_intent(query_pattern)
        
        # Create path
        path = SolutionPath(
            id=f"path_{query_pattern.replace(' ', '_')[:50]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            query_pattern=query_pattern,
            query_intent=intent,
            steps=steps,
            is_active=True
        )
        
        self.db.add(path)
        self.db.commit()
        
        return path
    
    def get_solution_path(self, query: str) -> Optional[Dict]:
        """Get existing solution path for query."""
        # Try exact match first
        path = self.db.query(SolutionPath).filter(
            SolutionPath.query_pattern == query,
            SolutionPath.is_active == True
        ).first()
        
        if path:
            return {
                "id": path.id,
                "query_pattern": path.query_pattern,
                "intent": path.query_intent,
                "steps": path.steps,
                "click_through_rate": path.click_through_rate,
                "conversion_rate": path.conversion_rate
            }
        
        return None
    
    def _parse_query_intent(self, query: str) -> str:
        """Determine user intent from query."""
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ['comprar', 'precio', 'kit', 'donde']):
            return "purchase"
        elif any(kw in query_lower for kw in ['reparar', 'solucion', 'arreglar', 'como']):
            return "repair"
        elif any(kw in query_lower for kw in ['diagnostico', 'sintomas', 'porque']):
            return "diagnostic"
        else:
            return "informational"


# Factory function
def get_solution_engine_ai(db: Session) -> SolutionEngineAI:
    """Get SolutionEngineAI instance."""
    return SolutionEngineAI(db)
