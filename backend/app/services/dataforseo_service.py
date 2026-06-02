"""
DataForSEO SERP Service

Fetches real Google SERP data for product keywords:
- Organic results (title, description, URL, position, domain)
- People Also Ask questions with answer snippets
- Featured snippet detection (paragraph/table/list)
- Related searches
- SERP features present

Caches results in CacheEntry with 48h TTL.
Target market: Mexico, Spanish language.
"""

import httpx
import base64
from typing import List, Dict, Optional, Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DataForSEOService:
    """Service for fetching real SERP data via DataForSEO API."""

    # Live endpoint: synchronous, $0.60/1000 calls. Good for user-facing latency.
    API_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"
    # Task endpoint: async, $0.06/1000 calls (10x cheaper). Used when
    # DATAFORSEO_USE_STANDARD=true in settings. Submit → poll ready list → fetch.
    TASK_POST_URL = "https://api.dataforseo.com/v3/serp/google/organic/task_post"
    TASK_READY_URL = "https://api.dataforseo.com/v3/serp/google/organic/tasks_ready"
    TASK_GET_URL = "https://api.dataforseo.com/v3/serp/google/organic/task_get/regular"

    # 90 days — transmission parts SERP landscape is glacial. Extending from 30d
    # to 90d cuts duplicate calls by ~3x with negligible freshness loss.
    CACHE_TTL_HOURS = 2160
    CACHE_KEY_PREFIX = "dataforseo_serp:"

    SPANISH_STOP_WORDS = {
        'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una',
        'para', 'con', 'por', 'en', 'y', 'o', 'a', 'al',
        'que', 'su', 'se', 'es', 'son', 'sin',
        '1l', '2l', '4l', 'qt', 'ml', 'litro', 'litros',
        'pza', 'pzas', 'pieza', 'piezas', 'kit'
    }

    SERPAPI_URL = "https://serpapi.com/search.json"

    def __init__(self):
        self.login = settings.DATAFORSEO_LOGIN
        self.password = settings.DATAFORSEO_PASSWORD
        self.serpapi_key = settings.SERPAPI_KEY
        self.provider = settings.SERP_PROVIDER

    def is_configured(self) -> bool:
        """True if credentials for the active provider are present."""
        if self.provider == "serpapi":
            return bool(self.serpapi_key)
        return bool(self.login and self.password)

    def _get_auth_header(self) -> str:
        """Build HTTP Basic Auth header value."""
        credentials = f"{self.login}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _build_cache_key(self, keyword: str) -> str:
        """Build cache key for a keyword. Lowercase + stripped for max cache hits."""
        return f"{self.CACHE_KEY_PREFIX}{keyword.lower().strip()}"

    async def fetch_serp(
        self,
        keyword: str,
        db,
        depth: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch SERP data for a single keyword.
        Checks CacheEntry first. On miss, calls DataForSEO API and caches result.
        """
        from app.models.aeo_models import CacheEntry

        cache_key = self._build_cache_key(keyword)

        # 1. Check cache
        cached = CacheEntry.get(db, cache_key)
        if cached is not None:
            logger.info(f"[DataForSEO] Cache HIT: {keyword[:60]}")
            cached['cached'] = True
            return cached

        # 2. If not configured, return empty
        if not self.is_configured():
            logger.warning(f"[SERP] Provider '{self.provider}' not configured — skipping fetch")
            return self._empty_result(keyword, error=f"{self.provider} credentials not configured")

        # 3a. Route to SerpAPI if active provider
        if self.provider == "serpapi":
            logger.info(f"[SerpAPI] Fetching SERP for: {keyword[:60]}")
            try:
                result = await self._fetch_serp_serpapi(keyword, depth)
                if not result.get("error"):
                    CacheEntry.set(db, cache_key, result, ttl_hours=self.CACHE_TTL_HOURS)
                    logger.info(
                        f"[SerpAPI] Cached '{keyword[:40]}' "
                        f"({len(result['organic'])} organic, "
                        f"{len(result['people_also_ask'])} PAA, "
                        f"{len(result['related_searches'])} related)"
                    )
                result['cached'] = False
                return result
            except Exception as e:
                logger.error(f"[SerpAPI] Unexpected error: {e}")
                return self._empty_result(keyword, error=str(e))

        # 3b. DataForSEO path — choose endpoint based on cost/latency tradeoff
        use_standard = getattr(settings, 'DATAFORSEO_USE_STANDARD', False)
        logger.info(
            f"[DataForSEO] Fetching SERP for: {keyword[:60]} "
            f"({'STANDARD/async' if use_standard else 'LIVE/sync'})"
        )
        try:
            payload = [{
                "keyword": keyword,
                "location_name": "Mexico",
                "language_name": "Spanish",
                "device": "desktop",
                "os": "windows",
                "depth": depth
            }]

            if use_standard:
                data = await self._fetch_serp_standard(payload)
            else:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(
                        self.API_URL,
                        headers={
                            "Authorization": self._get_auth_header(),
                            "Content-Type": "application/json"
                        },
                        json=payload
                    )
                if response.status_code != 200:
                    logger.error(f"[DataForSEO] API error {response.status_code}: {response.text[:200]}")
                    return self._empty_result(keyword, error=f"HTTP {response.status_code}")
                data = response.json()

            if not data:
                return self._empty_result(keyword, error="Empty API response")

            result = self._parse_response(data, keyword)

            # 4. Cache the result
            CacheEntry.set(db, cache_key, result, ttl_hours=self.CACHE_TTL_HOURS)
            logger.info(
                f"[DataForSEO] Cached SERP for '{keyword[:40]}' "
                f"({len(result['organic'])} organic, "
                f"{len(result['people_also_ask'])} PAA, "
                f"{len(result['related_searches'])} related)"
            )

            result['cached'] = False
            return result

        except httpx.TimeoutException:
            logger.error(f"[DataForSEO] Timeout fetching SERP for: {keyword[:60]}")
            return self._empty_result(keyword, error="Request timeout")
        except Exception as e:
            logger.error(f"[DataForSEO] Unexpected error: {e}")
            return self._empty_result(keyword, error=str(e))

    async def _fetch_serp_standard(self, payload: List[Dict]) -> Optional[Dict]:
        """Async/task-based SERP fetch. $0.06/1000 calls vs $0.60 for live.

        Flow: submit task → poll for completion → fetch result. Task priority
        defaults to 1 ('standard') which typically completes in 30-60 seconds.
        We cap polling at ~90s and fall back to None on timeout so the caller
        can degrade gracefully.
        """
        import asyncio

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": self._get_auth_header(),
                "Content-Type": "application/json",
            }

            # Step 1: post the task
            # priority=1 is the "standard" cheap tier; priority=2 is the faster
            # "priority" tier (~2x the price, still 5x cheaper than live)
            task_payload = [{**p, "priority": 1} for p in payload]
            post_resp = await client.post(self.TASK_POST_URL, headers=headers, json=task_payload)
            if post_resp.status_code != 200:
                logger.error(f"[DataForSEO] task_post HTTP {post_resp.status_code}: {post_resp.text[:200]}")
                return None
            post_data = post_resp.json()
            tasks = post_data.get('tasks') or []
            if not tasks or tasks[0].get('status_code') not in (20000, 20100):
                logger.error(f"[DataForSEO] task_post rejected: {post_data}")
                return None
            task_id = tasks[0].get('id')
            if not task_id:
                return None

            # Step 2: poll for completion (check every 5s, give up after 90s)
            get_url = f"{self.TASK_GET_URL}/{task_id}"
            for attempt in range(18):  # 18 * 5s = 90s cap
                await asyncio.sleep(5)
                get_resp = await client.get(get_url, headers=headers)
                if get_resp.status_code == 200:
                    result_data = get_resp.json()
                    task_entry = (result_data.get('tasks') or [{}])[0]
                    status = task_entry.get('status_code')
                    # 20000 = success; 40602 = task in queue; other 4xxxx codes = errors
                    if status == 20000 and task_entry.get('result'):
                        return result_data
                    if status and status >= 40000 and status != 40602:
                        logger.error(f"[DataForSEO] Task {task_id} failed: {task_entry.get('status_message')}")
                        return None
            logger.warning(f"[DataForSEO] Task {task_id} timed out after 90s — caller will get empty result")
            return None

    async def _fetch_serp_serpapi(self, keyword: str, depth: int = 10) -> Dict[str, Any]:
        """
        Fetch a SERP via SerpAPI (free tier: 100 searches/month).

        Returns the same shape as _parse_response() so downstream consumers
        can stay provider-agnostic. SerpAPI's free tier requires no card and
        no minimum top-up — the trade is the monthly cap.
        """
        params = {
            "api_key": self.serpapi_key,
            "engine": "google",
            "q": keyword,
            "google_domain": "google.com.mx",
            "gl": "mx",
            "hl": "es",
            "num": depth,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(self.SERPAPI_URL, params=params)
        if resp.status_code != 200:
            logger.error(f"[SerpAPI] HTTP {resp.status_code}: {resp.text[:200]}")
            return self._empty_result(keyword, error=f"HTTP {resp.status_code}")

        data = resp.json()
        if "error" in data:
            return self._empty_result(keyword, error=str(data["error"]))
        return self._adapt_serpapi_response(data, keyword)

    def _adapt_serpapi_response(self, data: Dict, keyword: str) -> Dict[str, Any]:
        """Map SerpAPI response → the DataForSEO-shape dict the rest of the code expects."""
        result = self._empty_result(keyword)
        features_seen = set()

        for org in (data.get("organic_results") or []):
            features_seen.add("organic")
            result["organic"].append({
                "position": org.get("position", 0),
                "title": org.get("title", ""),
                "description": org.get("snippet", ""),
                "url": org.get("link", ""),
                "domain": (org.get("displayed_link") or "").split("/")[0],
                "breadcrumb": org.get("displayed_link", ""),
                "is_featured_snippet": False,
            })

        # SerpAPI exposes PAA under "related_questions"
        for paa in (data.get("related_questions") or []):
            features_seen.add("people_also_ask")
            question = paa.get("question", "")
            snippet = paa.get("snippet") or ""
            if question:
                result["people_also_ask"].append({
                    "question": question,
                    "answer_snippet": snippet[:300],
                })

        # "answer_box" ≈ featured snippet
        ab = data.get("answer_box")
        if ab:
            features_seen.add("featured_snippet")
            result["featured_snippet"] = {
                "type": ab.get("type", "paragraph"),
                "title": ab.get("title", ""),
                "description": ab.get("snippet") or ab.get("answer", ""),
                "url": ab.get("link", ""),
                "domain": (ab.get("displayed_link") or "").split("/")[0],
            }

        # related_searches is a list of objects in SerpAPI — extract the query string
        for rs in (data.get("related_searches") or []):
            features_seen.add("related_searches")
            q = rs.get("query") if isinstance(rs, dict) else str(rs)
            if q:
                result["related_searches"].append(q)

        # Other SerpAPI feature blocks worth flagging
        for key in ("knowledge_graph", "local_results", "shopping_results",
                    "inline_videos", "ads", "top_stories"):
            if data.get(key):
                features_seen.add(key)

        result["serp_features"] = list(features_seen)
        return result

    def _parse_response(self, data: Dict, keyword: str) -> Dict[str, Any]:
        """
        Parse raw DataForSEO API response into structured result.

        Items have 'type' field: organic, people_also_ask, related_searches,
        featured_snippet, knowledge_graph, local_pack, etc.
        """
        result = self._empty_result(keyword)

        try:
            tasks = data.get('tasks', [])
            if not tasks:
                result['error'] = 'No tasks in response'
                return result

            task = tasks[0]
            if task.get('status_code') != 20000:
                result['error'] = task.get('status_message', 'Task failed')
                return result

            task_result = task.get('result', [])
            if not task_result:
                result['error'] = 'Empty task result'
                return result

            items = task_result[0].get('items', [])
            serp_features_seen = set()

            for item in items:
                item_type = item.get('type', '')
                serp_features_seen.add(item_type)

                if item_type == 'organic':
                    result['organic'].append({
                        'position': item.get('rank_absolute', item.get('rank_group', 0)),
                        'title': item.get('title', ''),
                        'description': item.get('description', ''),
                        'url': item.get('url', ''),
                        'domain': item.get('domain', ''),
                        'breadcrumb': item.get('breadcrumb', ''),
                        'is_featured_snippet': item.get('is_featured_snippet', False)
                    })

                elif item_type == 'people_also_ask':
                    sub_items = item.get('items', [])
                    for paa in sub_items:
                        question = paa.get('title', '')
                        expanded = paa.get('expanded_element', [])
                        answer_snippet = ''
                        if expanded and isinstance(expanded, list):
                            answer_snippet = expanded[0].get('description', '') if expanded else ''
                        if question:
                            result['people_also_ask'].append({
                                'question': question,
                                'answer_snippet': answer_snippet[:300]
                            })

                elif item_type == 'related_searches':
                    sub_items = item.get('items', [])
                    for rs in sub_items:
                        query = rs.get('title', '')
                        if query:
                            result['related_searches'].append(query)

                elif item_type == 'featured_snippet':
                    result['featured_snippet'] = {
                        'type': item.get('featured_snippet_type', 'paragraph'),
                        'title': item.get('title', ''),
                        'description': item.get('description', ''),
                        'url': item.get('url', ''),
                        'domain': item.get('domain', '')
                    }

            result['serp_features'] = list(serp_features_seen)

        except Exception as e:
            logger.error(f"[DataForSEO] Parse error: {e}")
            result['error'] = f"Parse error: {str(e)}"

        return result

    def _empty_result(self, keyword: str, error: Optional[str] = None) -> Dict[str, Any]:
        """Return empty result structure for graceful degradation."""
        return {
            'keyword': keyword,
            'organic': [],
            'people_also_ask': [],
            'related_searches': [],
            'featured_snippet': None,
            'serp_features': [],
            'cached': False,
            'error': error
        }

    async def get_serp_data_for_product(
        self,
        product_title: str,
        gsc_queries: List[Dict[str, Any]],
        db,
        max_keywords: int = 3
    ) -> Dict[str, Any]:
        """
        Main entry point: extract keywords from product data and fetch SERP.

        Keyword extraction priority:
        1. Top 2 GSC queries by impressions (real search demand)
        2. Product title cleaned to core phrase (fallback)
        3. Deduplicate and cap at max_keywords
        """
        keywords = self._extract_keywords(product_title, gsc_queries, max_keywords)
        logger.info(f"[DataForSEO] Fetching SERP for {len(keywords)} keywords: {keywords}")

        results = []
        for kw in keywords:
            r = await self.fetch_serp(kw, db)
            results.append(r)

        return self._aggregate_results(keywords, results)

    def _extract_keywords(
        self,
        product_title: str,
        gsc_queries: List[Dict[str, Any]],
        max_keywords: int
    ) -> List[str]:
        """
        Extract 2-3 search keywords from product data.

        Accepts a GSC query only if it shares at least one meaningful token
        with the product/collection title. Without this guard, GSC attribution
        noise can attach a high-impression query to an unrelated collection
        (e.g. "Empaques de Carter" → "cremallera de direccion"), making the
        whole SERP fetch useless.
        """
        keywords = []
        title_tokens = self._meaningful_tokens(product_title)

        sorted_queries = sorted(
            gsc_queries, key=lambda q: q.get('impressions', 0), reverse=True
        )
        for q in sorted_queries:
            query_text = q.get('query', '').strip().lower()
            if not query_text or query_text in keywords:
                continue
            # If we have title tokens, require overlap. If we don't (rare),
            # accept GSC queries as-is rather than fail closed.
            if title_tokens and not (self._meaningful_tokens(query_text) & title_tokens):
                continue
            keywords.append(query_text)
            if len(keywords) >= 2:
                break

        title_keyword = self._clean_title_to_keyword(product_title)
        if title_keyword and title_keyword not in keywords:
            keywords.append(title_keyword)

        return keywords[:max_keywords]

    def _meaningful_tokens(self, text: str) -> set:
        """Tokens ≥3 chars, lowercased, with Spanish stop words removed."""
        if not text:
            return set()
        return {
            t for t in text.lower().split()
            if len(t) >= 3 and t not in self.SPANISH_STOP_WORDS
        }

    def _clean_title_to_keyword(self, title: str) -> str:
        """
        Extract core searchable phrase from a product title.

        Examples:
          "Kit de Reparación 4L60E TransGo Shift Kit SK4L60E"
           -> "reparación 4l60e transgo shift"

          "Aceite ZF LifeguardFluid 8 1L para ZF8HP"
           -> "aceite zf lifeguardfluid 8"
        """
        tokens = title.lower().split()
        meaningful = [
            t for t in tokens
            if t not in self.SPANISH_STOP_WORDS or any(c.isdigit() for c in t)
        ]
        return ' '.join(meaningful[:4]).strip()

    def _aggregate_results(
        self,
        keywords: List[str],
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge SERP results from multiple keywords into one aggregate structure.
        Deduplicates organic by URL, PAA by question text, related by string.
        """
        seen_urls = {}
        seen_questions = set()
        seen_related = set()

        all_paa = []
        all_related = []
        all_featured = []
        all_features = set()
        errors = []

        for r in results:
            if r.get('error'):
                errors.append(r['error'])

            # Organic dedup by URL (keep lowest position)
            for org in r.get('organic', []):
                url = org.get('url', '')
                pos = org.get('position', 999)
                if url not in seen_urls or pos < seen_urls[url]['position']:
                    seen_urls[url] = org

            # PAA dedup by question
            for paa in r.get('people_also_ask', []):
                q_lower = paa.get('question', '').lower().strip()
                if q_lower and q_lower not in seen_questions:
                    seen_questions.add(q_lower)
                    all_paa.append(paa)

            # Related searches dedup
            for rs in r.get('related_searches', []):
                rs_lower = rs.lower().strip()
                if rs_lower and rs_lower not in seen_related:
                    seen_related.add(rs_lower)
                    all_related.append(rs)

            # Featured snippets
            fs = r.get('featured_snippet')
            if fs:
                all_featured.append({**fs, 'keyword': r.get('keyword', '')})

            all_features.update(r.get('serp_features', []))

        all_organic = sorted(seen_urls.values(), key=lambda x: x.get('position', 999))

        return {
            'keywords_searched': keywords,
            'results': results,
            'all_organic': all_organic,
            'all_paa': all_paa,
            'all_related': all_related,
            'featured_snippets': all_featured,
            'serp_features_detected': list(all_features),
            'errors': errors,
            'total_organic': len(all_organic),
            'total_paa': len(all_paa)
        }

    def format_for_prompt(self, serp_data: Dict[str, Any]) -> str:
        """
        Format aggregated SERP data into a prompt section for Grok.
        Returns fallback string if no data available.
        """
        if not serp_data or (
            not serp_data.get('all_organic') and
            not serp_data.get('all_paa') and
            not serp_data.get('featured_snippets')
        ):
            return "No SERP data available (DataForSEO not configured or no results)."

        sections = []
        keywords = serp_data.get('keywords_searched', [])
        sections.append(f"**Keywords analyzed:** {', '.join(keywords)}")

        # Featured Snippets
        featured = serp_data.get('featured_snippets', [])
        if featured:
            sections.append("\n### Featured Snippet (Position 0):")
            for fs in featured:
                sections.append(
                    f"- **Type:** {fs.get('type', 'paragraph')} | "
                    f"**Domain:** {fs.get('domain', 'N/A')} | "
                    f"**Keyword:** '{fs.get('keyword', '')}'"
                )
                if fs.get('description'):
                    sections.append(f"  *\"{fs['description'][:200]}\"*")

        # Organic Top 10
        organic = serp_data.get('all_organic', [])[:10]
        if organic:
            sections.append("\n### Real Organic Rankings (Mexico, Google):")
            sections.append("| Pos | Domain | Title | Description |")
            sections.append("|-----|--------|-------|-------------|")
            for r in organic:
                title = r.get('title', 'N/A')[:45]
                desc = r.get('description', '')[:80]
                sections.append(
                    f"| {r.get('position', '?')} | "
                    f"{r.get('domain', 'N/A')[:25]} | "
                    f"{title} | "
                    f"{desc} |"
                )

        # People Also Ask
        paa = serp_data.get('all_paa', [])
        if paa:
            sections.append("\n### People Also Ask (Real Google Questions):")
            sections.append(
                "(Use these as your FAQ questions — they are REAL user questions, "
                "not invented)"
            )
            for i, item in enumerate(paa[:8], 1):
                q = item.get('question', '')
                a = item.get('answer_snippet', '')
                sections.append(f"{i}. **{q}**")
                if a:
                    sections.append(f"   *Answer preview: {a[:150]}*")

        # Related Searches
        related = serp_data.get('all_related', [])
        if related:
            sections.append("\n### Related Searches (Keyword Expansion Opportunities):")
            sections.append(', '.join(f'"{rs}"' for rs in related[:10]))

        # SERP Features detected
        features = serp_data.get('serp_features_detected', [])
        meaningful = [f for f in features if f in (
            'featured_snippet', 'people_also_ask', 'knowledge_graph',
            'local_pack', 'shopping_results', 'video_results'
        )]
        if meaningful:
            sections.append(f"\n**SERP Features Present:** {', '.join(meaningful)}")

        return "\n".join(sections)

    async def fetch_keyword_volumes(
        self,
        keywords: List[str],
        db
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch monthly search volumes for a list of keywords via DataForSEO Keywords Data API.
        
        Returns dict mapping keyword -> {volume, competition, cpc, trend}
        Caches results for 7 days.
        """
        from app.models.aeo_models import CacheEntry

        if not keywords:
            return {}

        if not self.is_configured():
            logger.warning("[DataForSEO] Not configured - skipping keyword volumes")
            return {}

        # SerpAPI's free tier has no keyword-volume endpoint. Skip silently
        # — callers already handle empty volume data (fall back to first
        # keyword for primary_keyword selection).
        if self.provider == "serpapi":
            return {}

        results = {}
        uncached_keywords = []

        # 1. Check cache for each keyword
        for kw in keywords:
            kw_clean = kw.lower().strip()
            cache_key = f"kw_volume:{kw_clean}"
            cached = CacheEntry.get(db, cache_key)
            if cached is not None:
                results[kw_clean] = cached
            else:
                uncached_keywords.append(kw_clean)

        if not uncached_keywords:
            logger.info(f"[DataForSEO] All {len(keywords)} keyword volumes from cache")
            return results

        # 2. Batch API call for uncached keywords
        logger.info(f"[DataForSEO] Fetching volumes for {len(uncached_keywords)} keywords")
        try:
            VOLUME_API_URL = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"

            payload = [{
                "keywords": uncached_keywords[:100],  # API limit
                "location_code": 2484,  # Mexico
                "language_code": "es",
            }]

            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    VOLUME_API_URL,
                    headers={
                        "Authorization": self._get_auth_header(),
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

            if response.status_code != 200:
                logger.error(f"[DataForSEO] Volume API error {response.status_code}")
                return results

            data = response.json()
            tasks = data.get('tasks', [])
            if not tasks:
                return results

            task = tasks[0]
            task_result = task.get('result', [])
            if not task_result:
                return results

            # Parse results
            for item in task_result:
                kw = (item.get('keyword', '') or '').lower().strip()
                if not kw:
                    continue

                volume_data = {
                    'volume': item.get('search_volume', 0) or 0,
                    'competition': item.get('competition', 'UNKNOWN'),
                    'competition_index': item.get('competition_index', 0),
                    'cpc': item.get('cpc', 0) or 0,
                    'monthly_searches': item.get('monthly_searches', []),
                }

                results[kw] = volume_data

                # Cache for 7 days
                cache_key = f"kw_volume:{kw}"
                CacheEntry.set(db, cache_key, volume_data, ttl_hours=168)

            logger.info(
                f"[DataForSEO] Got volumes for {len(task_result)} keywords, "
                f"total cached: {len(results)}"
            )

        except httpx.TimeoutException:
            logger.error("[DataForSEO] Timeout fetching keyword volumes")
        except Exception as e:
            logger.error(f"[DataForSEO] Volume error: {e}")

        return results


def format_volumes_for_gsc_table(
    gsc_queries: List[Dict[str, Any]],
    volumes: Dict[str, Dict[str, Any]]
) -> str:
    """
    Format GSC queries table enhanced with real search volumes.
    Replaces the basic GSC query table with volume-enriched data.
    """
    if not gsc_queries:
        return "No GSC query data available."

    lines = []
    lines.append("| Query | Impressions | Clicks | CTR | Position | Monthly Volume | Competition |")
    lines.append("|-------|-------------|--------|-----|----------|----------------|-------------|")

    for q in gsc_queries[:10]:
        query = q.get('query', '')
        impressions = q.get('impressions', 0)
        clicks = q.get('clicks', 0)
        ctr = q.get('ctr', 0)
        position = q.get('position', 0)

        # Get volume data
        vol_data = volumes.get(query.lower().strip(), {})
        volume = vol_data.get('volume', '—')
        competition = vol_data.get('competition', '—')

        lines.append(
            f"| {query[:40]} | {impressions} | {clicks} | {ctr:.1f}% | "
            f"{position:.1f} | {volume} | {competition} |"
        )

    return "\n".join(lines)


# Singleton instance
dataforseo_service = DataForSEOService()

