"""
AI Visibility Service

Service for checking brand visibility across AI/LLM engines.
Replicates Semrush's AI Visibility tool functionality.

Key features:
- Query LLMs with prompts to check brand mentions
- Parse responses for Example Store citations and competitor mentions
- Aggregate daily visibility metrics
- Track share of voice vs competitors
"""

import asyncio
import re
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.logging import get_logger
from app.core.config import settings
from app.models.aeo_models import (
    PromptPanelItem,
    AIVisibilityResult,
    VisibilitySnapshot,
    FaultCode
)
from app.services.llm_providers import LLMProviderFactory, BaseLLMProvider

logger = get_logger(__name__)


# Brand and competitor detection keywords
BRAND_KEYWORDS = [
    "example-store", "example store", "example-store",
    "example-store.com", "www.example-store.com",
    "example store mexico", "example-store méxico"
]

COMPETITOR_KEYWORDS = [
    "transgo", "sonnax", "alto products", "alto",
    "raybestos", "transtec", "tss", "precision",
    "borg warner", "borgwarner", "zf", "luk",
    "valeo", "exedy", "aisin"
]

# URL patterns to detect
BRAND_URL_PATTERN = re.compile(r'example-store\.com[^\s]*', re.IGNORECASE)


class AIVisibilityService:
    """
    Service for AI visibility tracking across LLM engines.
    
    Inspired by Semrush's AI Visibility feature, this tracks:
    - Brand mentions (Example Store mentioned in response)
    - URL citations (example-store.com URLs included)
    - Product mentions (specific product names)
    - Competitor presence (share of voice)
    """
    
    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
    
    def _get_provider(self, provider_name: str) -> BaseLLMProvider:
        """Get or create a provider instance."""
        if provider_name not in self._providers:
            self._providers[provider_name] = LLMProviderFactory.create(provider_name)
        return self._providers[provider_name]
    
    # ============ Prompt Management ============
    
    def get_prompts(
        self, 
        db: Session, 
        active_only: bool = True,
        category: Optional[str] = None
    ) -> List[PromptPanelItem]:
        """Get prompts from the panel."""
        query = db.query(PromptPanelItem)
        
        if active_only:
            query = query.filter(PromptPanelItem.is_active == True)
        
        if category:
            query = query.filter(PromptPanelItem.category == category)
        
        return query.order_by(PromptPanelItem.priority.desc()).all()
    
    def add_prompt(
        self,
        db: Session,
        prompt_text: str,
        category: str = "general",
        priority: int = 50,
        linked_fault_code: Optional[str] = None,
        linked_transmission: Optional[str] = None,
        source: str = "manual"
    ) -> PromptPanelItem:
        """Add a new prompt to the panel."""
        prompt = PromptPanelItem(
            prompt_text=prompt_text,
            category=category,
            priority=priority,
            linked_fault_code=linked_fault_code,
            linked_transmission=linked_transmission,
            source=source,
            is_active=True
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        
        logger.info(f"Added prompt: {prompt_text[:50]}...", extra={"prompt_id": prompt.id})
        return prompt
    
    def remove_prompt(self, db: Session, prompt_id: int) -> bool:
        """Remove a prompt from the panel (soft delete by deactivation)."""
        prompt = db.query(PromptPanelItem).filter(PromptPanelItem.id == prompt_id).first()
        if prompt:
            prompt.is_active = False
            db.commit()
            return True
        return False
    
    # ============ Visibility Checking ============
    
    async def check_visibility_single(
        self,
        db: Session,
        prompt_id: int,
        provider_name: str = "grok"
    ) -> AIVisibilityResult:
        """
        Check visibility for a single prompt using specified LLM.
        
        Returns the result with parsed brand/competitor mentions.
        """
        prompt = db.query(PromptPanelItem).filter(PromptPanelItem.id == prompt_id).first()
        if not prompt:
            raise ValueError(f"Prompt {prompt_id} not found")
        
        provider = self._get_provider(provider_name)
        
        # Build the query - we want natural responses, not structured JSON
        system_prompt = """You are a helpful automotive transmission expert assistant. 
Answer questions naturally and thoroughly, providing specific product recommendations, 
brand names, and website URLs where applicable. Focus on the Mexican/Latin American market."""
        
        start_time = time.time()
        error = None
        response_text = ""
        
        try:
            # Make the LLM call.
            # TEMPERATURE=0: visibility tracking needs reproducibility, not
            # creativity. At temp=0.7 the same prompt gave different mention
            # rates across runs, so week-over-week trends were noise. At
            # temp=0 the output is near-deterministic, so a score delta now
            # reflects changed ground truth (content / AI knowledge cutoff /
            # competitor activity) rather than sampling variance.
            result = await provider.generate(
                system_prompt=system_prompt,
                user_prompt=prompt.prompt_text,
                json_mode=False,
                temperature=0
            )
            
            # The result might be parsed JSON or raw text, handle both
            if isinstance(result, dict):
                response_text = str(result.get("content", result.get("response", str(result))))
            else:
                response_text = str(result)
                
        except Exception as e:
            error = str(e)
            logger.error(f"LLM query failed for prompt {prompt_id}: {e}")
        
        query_time_ms = int((time.time() - start_time) * 1000)
        
        # Parse the response for visibility signals
        visibility_data = self._parse_visibility_response(response_text)
        
        # Create result record
        visibility_result = AIVisibilityResult(
            prompt_id=prompt_id,
            llm_provider=provider_name,
            llm_model=getattr(provider, 'model', None),
            response_text=response_text[:5000] if response_text else None,  # Truncate long responses
            brand_mentioned=visibility_data["brand_mentioned"],
            url_cited=visibility_data["url_cited"],
            product_mentioned=visibility_data["product_mentioned"],
            competitor_mentioned=visibility_data["competitor_mentioned"],
            mentioned_brands=visibility_data["mentioned_brands"],
            mentioned_urls=visibility_data["mentioned_urls"],
            mentioned_products=visibility_data["mentioned_products"],
            sentiment=visibility_data.get("sentiment"),
            query_time_ms=query_time_ms,
            error=error
        )
        
        db.add(visibility_result)
        
        # Update prompt check count
        prompt.check_count = (prompt.check_count or 0) + 1
        prompt.last_checked = datetime.utcnow()
        
        db.commit()
        db.refresh(visibility_result)
        
        return visibility_result
    
    async def batch_check_visibility(
        self,
        db: Session,
        prompt_ids: Optional[List[int]] = None,
        provider_names: List[str] = None,
        limit: int = 20,
        max_concurrent: int = 3,
        timeout_per_check: int = 60
    ) -> Dict:
        """
        Run visibility checks on multiple prompts in parallel.

        Args:
            prompt_ids: Specific prompts to check (None = active prompts)
            provider_names: LLMs to use (default: ["grok"])
            limit: Max prompts to check per run
            max_concurrent: Max concurrent LLM calls (default: 3)
            timeout_per_check: Timeout per check in seconds (default: 60)

        Returns:
            Summary of results
        """
        if provider_names is None:
            provider_names = ["grok"]  # Default to Grok

        # Get prompts to check
        if prompt_ids:
            prompts = db.query(PromptPanelItem).filter(
                PromptPanelItem.id.in_(prompt_ids),
                PromptPanelItem.is_active == True
            ).all()
        else:
            prompts = self.get_prompts(db, active_only=True)[:limit]

        results = []
        errors = []

        # Create semaphore to limit concurrent LLM calls
        semaphore = asyncio.Semaphore(max_concurrent)

        async def check_with_timeout(prompt, provider_name: str):
            """Run a single check with timeout and semaphore control."""
            async with semaphore:
                try:
                    # Use asyncio.wait_for to add timeout
                    result = await asyncio.wait_for(
                        self.check_visibility_single(db, prompt.id, provider_name),
                        timeout=timeout_per_check
                    )
                    return {
                        "success": True,
                        "prompt_id": prompt.id,
                        "prompt_text": prompt.prompt_text[:100],
                        "provider": provider_name,
                        "brand_mentioned": result.brand_mentioned,
                        "url_cited": result.url_cited,
                        "competitor_mentioned": result.competitor_mentioned
                    }
                except asyncio.TimeoutError:
                    logger.warning(f"Visibility check timeout for prompt {prompt.id} with {provider_name}")
                    return {
                        "success": False,
                        "prompt_id": prompt.id,
                        "provider": provider_name,
                        "error": f"Timeout after {timeout_per_check}s"
                    }
                except Exception as e:
                    logger.error(f"Visibility check failed for prompt {prompt.id}: {e}")
                    return {
                        "success": False,
                        "prompt_id": prompt.id,
                        "provider": provider_name,
                        "error": str(e)
                    }

        # Build list of all check tasks
        tasks = []
        for prompt in prompts:
            for provider_name in provider_names:
                tasks.append(check_with_timeout(prompt, provider_name))

        # Run all checks in parallel with concurrency limit
        if tasks:
            logger.info(f"Starting {len(tasks)} visibility checks with max {max_concurrent} concurrent...")
            start_time = time.time()

            all_results = await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = time.time() - start_time
            logger.info(f"Batch visibility check completed in {elapsed:.1f}s")

            # Process results
            for result in all_results:
                if isinstance(result, Exception):
                    errors.append({"error": str(result)})
                elif result.get("success"):
                    results.append({
                        "prompt_id": result["prompt_id"],
                        "prompt_text": result["prompt_text"],
                        "provider": result["provider"],
                        "brand_mentioned": result["brand_mentioned"],
                        "url_cited": result["url_cited"],
                        "competitor_mentioned": result["competitor_mentioned"]
                    })
                else:
                    errors.append({
                        "prompt_id": result.get("prompt_id"),
                        "provider": result.get("provider"),
                        "error": result.get("error", "Unknown error")
                    })

        # Calculate summary metrics
        total_checks = len(results)
        brand_mentions = sum(1 for r in results if r["brand_mentioned"])
        url_citations = sum(1 for r in results if r["url_cited"])
        competitor_mentions = sum(1 for r in results if r["competitor_mentioned"])

        return {
            "total_prompts": len(prompts),
            "total_checks": total_checks,
            "providers_used": provider_names,
            "elapsed_time_seconds": elapsed if tasks else 0,
            "metrics": {
                "brand_mention_rate": brand_mentions / total_checks if total_checks > 0 else 0,
                "url_citation_rate": url_citations / total_checks if total_checks > 0 else 0,
                "competitor_mention_rate": competitor_mentions / total_checks if total_checks > 0 else 0,
            },
            "results": results,
            "errors": errors
        }
    
    def _parse_visibility_response(self, response_text: str) -> Dict:
        """
        Parse an LLM response for visibility signals.
        
        Detects:
        - Brand mentions (Example Store)
        - URL citations (example-store.com)
        - Product names (from known catalog)
        - Competitor mentions
        """
        if not response_text:
            return {
                "brand_mentioned": False,
                "url_cited": False,
                "product_mentioned": False,
                "competitor_mentioned": False,
                "mentioned_brands": [],
                "mentioned_urls": [],
                "mentioned_products": [],
                "sentiment": None
            }
        
        text_lower = response_text.lower()
        
        # Check for brand mentions
        brand_mentioned = any(kw.lower() in text_lower for kw in BRAND_KEYWORDS)
        
        # Find cited URLs
        mentioned_urls = BRAND_URL_PATTERN.findall(response_text)
        url_cited = len(mentioned_urls) > 0
        
        # Check for competitor mentions
        mentioned_brands = []
        competitor_mentioned = False
        for competitor in COMPETITOR_KEYWORDS:
            if competitor.lower() in text_lower:
                mentioned_brands.append(competitor)
                competitor_mentioned = True
        
        # Add Example Store to mentioned brands if found
        if brand_mentioned:
            mentioned_brands.insert(0, "Example Store")
        
        # Product detection (basic - could be enhanced with actual catalog)
        product_keywords = [
            "kit de reparación", "kit de embrague", "solenoides",
            "cuerpo de válvulas", "body valve", "clutch pack",
            "steel plates", "friction plates"
        ]
        product_mentioned = any(pk in text_lower for pk in product_keywords)
        mentioned_products = [pk for pk in product_keywords if pk in text_lower]
        
        # Basic sentiment detection
        sentiment = self._detect_sentiment(response_text)
        
        return {
            "brand_mentioned": brand_mentioned,
            "url_cited": url_cited,
            "product_mentioned": product_mentioned,
            "competitor_mentioned": competitor_mentioned,
            "mentioned_brands": mentioned_brands,
            "mentioned_urls": list(set(mentioned_urls)),  # Deduplicate
            "mentioned_products": mentioned_products[:5],  # Limit
            "sentiment": sentiment
        }
    
    def _detect_sentiment(self, text: str) -> str:
        """Basic sentiment detection."""
        text_lower = text.lower()
        
        positive_words = ["recomiendo", "excelente", "confiable", "bueno", "mejor", "calidad"]
        negative_words = ["no recomiendo", "malo", "problema", "evitar", "cuidado", "advertencia"]
        
        positive_count = sum(1 for w in positive_words if w in text_lower)
        negative_count = sum(1 for w in negative_words if w in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"
    
    # ============ Results & Analytics ============
    
    def get_recent_results(
        self,
        db: Session,
        days: int = 7,
        limit: int = 100
    ) -> List[AIVisibilityResult]:
        """Get recent visibility check results."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        return db.query(AIVisibilityResult).filter(
            AIVisibilityResult.checked_at >= cutoff
        ).order_by(
            AIVisibilityResult.checked_at.desc()
        ).limit(limit).all()
    
    def get_results_by_prompt(
        self,
        db: Session,
        prompt_id: int,
        limit: int = 50
    ) -> List[AIVisibilityResult]:
        """Get results for a specific prompt."""
        return db.query(AIVisibilityResult).filter(
            AIVisibilityResult.prompt_id == prompt_id
        ).order_by(
            AIVisibilityResult.checked_at.desc()
        ).limit(limit).all()
    
    # ============ Snapshots & Aggregation ============
    
    def create_daily_snapshot(self, db: Session, target_date: Optional[date] = None) -> VisibilitySnapshot:
        """
        Create or update daily visibility snapshot.
        
        Aggregates all results from the target day into a single metrics summary.
        """
        if target_date is None:
            target_date = date.today()
        
        # Get day boundaries
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = datetime.combine(target_date, datetime.max.time())
        
        # Query results for the day
        results = db.query(AIVisibilityResult).filter(
            AIVisibilityResult.checked_at >= day_start,
            AIVisibilityResult.checked_at <= day_end,
            AIVisibilityResult.error.is_(None)  # Exclude errors
        ).all()
        
        if not results:
            logger.info(f"No results to aggregate for {target_date}")
            return None
        
        # Calculate metrics
        total_checks = len(results)
        brand_mentions = sum(1 for r in results if r.brand_mentioned)
        url_citations = sum(1 for r in results if r.url_cited)
        product_mentions = sum(1 for r in results if r.product_mentioned)
        competitor_mentions = sum(1 for r in results if r.competitor_mentioned)
        
        # Visibility score: % of prompts where Example Store was mentioned
        visibility_score = (brand_mentions / total_checks * 100) if total_checks > 0 else 0
        
        # Citation score: % with URL citations
        citation_score = (url_citations / total_checks * 100) if total_checks > 0 else 0
        
        # Share of voice: brand mentions / (brand + competitor mentions)
        total_mentions = brand_mentions + competitor_mentions
        share_of_voice = (brand_mentions / total_mentions * 100) if total_mentions > 0 else 0

        # Per-competitor breakdown: count how often each *named* competitor
        # appears across the day's results. "mentioned_brands" contains
        # Example Store as first entry when detected — exclude it here so only
        # true competitors populate the breakdown. Lowercased for stable
        # aggregation (response text casing varies).
        competitor_breakdown: Dict[str, int] = {}
        for result in results:
            for brand in (result.mentioned_brands or []):
                key = (brand or "").lower().strip()
                if not key or key == "example-store":
                    continue
                competitor_breakdown[key] = competitor_breakdown.get(key, 0) + 1
        # Sort descending so consumers can trust the dict ordering on Python 3.7+
        competitor_breakdown = dict(
            sorted(competitor_breakdown.items(), key=lambda kv: kv[1], reverse=True)
        )

        # Breakdown by LLM provider
        metrics_by_llm = {}
        for result in results:
            provider = result.llm_provider
            if provider not in metrics_by_llm:
                metrics_by_llm[provider] = {"checks": 0, "mentions": 0, "citations": 0}
            metrics_by_llm[provider]["checks"] += 1
            if result.brand_mentioned:
                metrics_by_llm[provider]["mentions"] += 1
            if result.url_cited:
                metrics_by_llm[provider]["citations"] += 1
        
        # Find top performing prompts
        prompt_performance = {}
        for result in results:
            pid = result.prompt_id
            if pid not in prompt_performance:
                prompt_performance[pid] = {"mentions": 0, "citations": 0}
            if result.brand_mentioned:
                prompt_performance[pid]["mentions"] += 1
            if result.url_cited:
                prompt_performance[pid]["citations"] += 1
        
        top_prompts = sorted(
            [{"prompt_id": k, **v} for k, v in prompt_performance.items()],
            key=lambda x: x["mentions"],
            reverse=True
        )[:10]
        
        # Check for existing snapshot
        snapshot = db.query(VisibilitySnapshot).filter(
            func.date(VisibilitySnapshot.snapshot_date) == target_date
        ).first()
        
        if snapshot:
            # Update existing
            snapshot.total_prompts_checked = total_checks
            snapshot.brand_mentions = brand_mentions
            snapshot.url_citations = url_citations
            snapshot.product_mentions = product_mentions
            snapshot.competitor_mentions = competitor_mentions
            snapshot.visibility_score = visibility_score
            snapshot.citation_score = citation_score
            snapshot.share_of_voice = share_of_voice
            snapshot.competitor_breakdown = competitor_breakdown
            snapshot.metrics_by_llm = metrics_by_llm
            snapshot.top_prompts = top_prompts
        else:
            # Create new
            snapshot = VisibilitySnapshot(
                snapshot_date=day_start,
                total_prompts_checked=total_checks,
                brand_mentions=brand_mentions,
                url_citations=url_citations,
                product_mentions=product_mentions,
                competitor_mentions=competitor_mentions,
                visibility_score=visibility_score,
                citation_score=citation_score,
                share_of_voice=share_of_voice,
                competitor_breakdown=competitor_breakdown,
                metrics_by_llm=metrics_by_llm,
                top_prompts=top_prompts
            )
            db.add(snapshot)
        
        db.commit()
        db.refresh(snapshot)
        
        logger.info(f"Created snapshot for {target_date}: visibility={visibility_score:.1f}%")
        return snapshot
    
    def get_snapshots(
        self,
        db: Session,
        days: int = 30
    ) -> List[VisibilitySnapshot]:
        """Get historical snapshots for trend analysis."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        return db.query(VisibilitySnapshot).filter(
            VisibilitySnapshot.snapshot_date >= cutoff
        ).order_by(
            VisibilitySnapshot.snapshot_date.desc()
        ).all()
    
    def get_dashboard_data(self, db: Session) -> Dict:
        """
        Get aggregated data for the visibility dashboard.
        
        Returns current scores, trends, and top-level metrics.
        """
        # Get latest snapshot
        latest_snapshot = db.query(VisibilitySnapshot).order_by(
            VisibilitySnapshot.snapshot_date.desc()
        ).first()
        
        # Get 7-day average
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_snapshots = db.query(VisibilitySnapshot).filter(
            VisibilitySnapshot.snapshot_date >= week_ago
        ).all()
        
        week_avg_visibility = 0
        week_avg_share = 0
        if recent_snapshots:
            week_avg_visibility = sum(s.visibility_score for s in recent_snapshots) / len(recent_snapshots)
            week_avg_share = sum(s.share_of_voice for s in recent_snapshots) / len(recent_snapshots)
        
        # Get prompt stats
        total_prompts = db.query(PromptPanelItem).filter(
            PromptPanelItem.is_active == True
        ).count()
        
        total_results = db.query(AIVisibilityResult).count()
        
        return {
            "current": {
                "visibility_score": latest_snapshot.visibility_score if latest_snapshot else 0,
                "citation_score": latest_snapshot.citation_score if latest_snapshot else 0,
                "share_of_voice": latest_snapshot.share_of_voice if latest_snapshot else 0,
                "last_updated": latest_snapshot.snapshot_date if latest_snapshot else None
            },
            "trends": {
                "week_avg_visibility": round(week_avg_visibility, 1),
                "week_avg_share": round(week_avg_share, 1),
            },
            "totals": {
                "active_prompts": total_prompts,
                "total_checks": total_results,
            },
            "by_llm": latest_snapshot.metrics_by_llm if latest_snapshot else {},
            "top_prompts": latest_snapshot.top_prompts if latest_snapshot else []
        }


# Singleton instance
ai_visibility_service = AIVisibilityService()
