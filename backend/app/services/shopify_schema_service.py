"""
Shopify Schema Injection Service

Automatically injects FAQPage and HowTo JSON-LD schemas into Shopify blog articles
based on fault code matching.

Usage:
    1. Run seed_priority_fault_codes() to initialize Knowledge Graph
    2. Call inject_schemas_to_articles() to update Shopify articles
"""

import re
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.aeo_models import FaultCode
from app.services.aeo_service import aeo_service, SchemaGenerator
from app.services.shopify_service import shopify_service

logger = logging.getLogger("shopify_schema_service")


class ShopifySchemaService:
    """
    Service to inject JSON-LD schemas into Shopify blog articles.
    
    This enables GEO optimization by adding structured data that AI engines
    can parse and cite.
    """
    
    def __init__(self):
        self.shopify = shopify_service
        
    def find_fault_code_articles(self, db: Session) -> List[Dict]:
        """
        Find all blog articles that mention fault codes.
        Returns list of articles with matched fault codes.
        """
        try:
            self.shopify._ensure_initialized()
            import shopify
            
            # Get all fault codes from database
            fault_codes = db.query(FaultCode).all()
            code_patterns = {fc.code.upper(): fc for fc in fault_codes}
            
            matched_articles = []
            blogs = shopify.Blog.find()
            
            for blog in blogs:
                articles = shopify.Article.find(blog_id=blog.id)
                for article in articles:
                    # Check if article title or content contains any fault code
                    title = (article.title or '').upper()
                    body = (article.body_html or '').upper()
                    
                    for code, fc in code_patterns.items():
                        if code in title or code in body:
                            matched_articles.append({
                                'article_id': article.id,
                                'blog_id': blog.id,
                                'blog_handle': blog.handle,
                                'title': article.title,
                                'handle': article.handle,
                                'fault_code': fc.code,
                                'fault_code_name': fc.name,
                                'has_schema': self._has_schema(article),
                                'url': f"/blogs/{blog.handle}/{article.handle}"
                            })
                            break  # One fault code per article
            
            return matched_articles
            
        except Exception as e:
            logger.error(f"Error finding fault code articles: {e}")
            return []
    
    def _has_schema(self, article) -> bool:
        """Check if article already has JSON-LD schema (HTML or Metafield)"""
        # Check body_html
        body_html = article.body_html or ''
        if 'application/ld+json' in body_html or '@type' in body_html:
            return True
            
        # Check metafields (Namespace: geo, Key: structured_data)
        try:
            metafields = article.metafields()
            for mf in metafields:
                if mf.namespace == 'geo' and mf.key == 'structured_data':
                    return True
        except:
            pass
            
        return False
    
    def generate_article_schema(self, db: Session, fault_code: str, article_url: str) -> str:
        """
        Generate complete schema block for an article.
        Includes FAQPage and optional HowTo schemas.
        """
        # Get FAQ schema
        faq_schema = aeo_service.generate_faq_schema(db, fault_code)
        if "error" in faq_schema:
            return ""
        
        # Get HowTo schema
        howto_schema = aeo_service.generate_howto_schema(db, fault_code)
        
        # Combine into single script block
        schemas = [faq_schema]
        if "error" not in howto_schema:
            schemas.append(howto_schema)
        
        # Build HTML block (used for both injection methods)
        schema_html = '\n<!-- GEO: Auto-generated structured data by Example Store AEO System -->\n'
        for schema in schemas:
            schema_html += f'<script type="application/ld+json">\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n</script>\n'
        schema_html += '<!-- /GEO -->\n'
        
        return schema_html
    
    def inject_schema_to_article(
        self, 
        db: Session, 
        article_id: int, 
        blog_id: int,
        fault_code: str,
        method: str = "metafield",  # "metafield" or "html"
        dry_run: bool = True
    ) -> Dict:
        """
        Inject FAQPage schema into a specific Shopify article.
        
        Args:
            db: Database session
            article_id: Shopify article ID
            blog_id: Shopify blog ID
            fault_code: Fault code to generate schema for
            method: "metafield" (safe) or "html" (legacy injection)
            dry_run: If True, don't actually update (preview only)
            
        Returns:
            Dict with status and preview
        """
        try:
            self.shopify._ensure_initialized()
            import shopify
            
            # Fetch the article
            article = shopify.Article.find(article_id, blog_id=blog_id)
            if not article:
                return {"error": "Article not found", "success": False}
            
            # Check if already has schema
            if self._has_schema(article):
                return {
                    "success": False,
                    "message": "Article already has JSON-LD schema",
                    "article_id": article_id,
                    "skip": True
                }
            
            # Generate schema
            schema_html = self.generate_article_schema(db, fault_code, f"/blogs/news/{article.handle}")
            if not schema_html:
                return {"error": "Could not generate schema", "success": False}
            
            if dry_run:
                return {
                    "success": True,
                    "dry_run": True,
                    "article_id": article_id,
                    "article_title": article.title,
                    "fault_code": fault_code,
                    "method": method,
                    "schema_preview": schema_html[:500] + "..." if len(schema_html) > 500 else schema_html,
                    "message": f"Preview only using {method} method - set dry_run=False to apply"
                }
            
            if method == "metafield":
                # Inject via Metafield (Safe Architectural approach)
                # Namespace: geo, Key: structured_data
                metafield = shopify.Metafield({
                    'owner_id': article.id,
                    'owner_resource': 'article',
                    'namespace': 'geo',
                    'key': 'structured_data',
                    'value': schema_html,
                    'type': 'multi_line_text_field'
                })
                metafield.save()
            else:
                # Legacy HTML Injection (ADR-5 Recommends against this for production)
                new_body = (article.body_html or '') + schema_html
                article.body_html = new_body
                article.save()
            
            # Update fault code record in our DB
            fc = db.query(FaultCode).filter(FaultCode.code == fault_code).first()
            if fc:
                fc.has_faq_schema = True
                db.commit()
            
            return {
                "success": True,
                "article_id": article_id,
                "article_title": article.title,
                "fault_code": fault_code,
                "method": method,
                "message": f"Schema injected successfully via {method}"
            }
            
        except Exception as e:
            logger.error(f"Error injecting schema: {e}")
            return {"error": str(e), "success": False}
    
    def inject_schemas_to_all_articles(
        self, 
        db: Session, 
        method: str = "metafield",
        dry_run: bool = True,
        limit: int = None
    ) -> Dict:
        """
        Inject schemas to all matching fault code articles.
        
        Args:
            db: Database session
            dry_run: If True, preview only (default)
            limit: Max articles to process (None = all)
            
        Returns:
            Summary of operations
        """
        articles = self.find_fault_code_articles(db)
        
        if limit:
            articles = articles[:limit]
        
        results = {
            "total_found": len(articles),
            "processed": 0,
            "success": 0,
            "skipped": 0,
            "errors": 0,
            "dry_run": dry_run,
            "articles": []
        }
        
        for article in articles:
            if article.get('has_schema'):
                results["skipped"] += 1
                results["articles"].append({
                    "title": article['title'],
                    "status": "skipped",
                    "reason": "Already has schema"
                })
                continue
            
            result = self.inject_schema_to_article(
                db=db,
                article_id=article['article_id'],
                blog_id=article['blog_id'],
                fault_code=article['fault_code'],
                method=method,
                dry_run=dry_run
            )
            
            results["processed"] += 1
            
            if result.get('success'):
                results["success"] += 1
                results["articles"].append({
                    "title": article['title'],
                    "fault_code": article['fault_code'],
                    "status": "success" if not dry_run else "preview",
                    "url": article['url']
                })
            elif result.get('skip'):
                results["skipped"] += 1
            else:
                results["errors"] += 1
                results["articles"].append({
                    "title": article['title'],
                    "status": "error",
                    "error": result.get('error')
                })
        
        return results
    
    def get_schema_injection_status(self, db: Session) -> Dict:
        """
        Get current status of schema injection across all fault code articles.
        """
        articles = self.find_fault_code_articles(db)
        
        # Count statuses
        with_schema = sum(1 for a in articles if a.get('has_schema'))
        without_schema = len(articles) - with_schema
        
        # Get fault codes with schema flag
        fault_codes = db.query(FaultCode).all()
        fc_with_schema = sum(1 for fc in fault_codes if fc.has_faq_schema)
        
        return {
            "total_articles_matched": len(articles),
            "articles_with_schema": with_schema,
            "articles_without_schema": without_schema,
            "fault_codes_total": len(fault_codes),
            "fault_codes_with_schema": fc_with_schema,
            "articles": articles
        }


# Singleton instance
shopify_schema_service = ShopifySchemaService()
