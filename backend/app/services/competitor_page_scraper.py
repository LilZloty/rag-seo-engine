"""
Competitor Page Scraper Service

Fetches top competitor pages from SERP organic results and extracts
structured content signals for comparison:
- FAQ count and questions
- Spec table detection
- Video embeds
- Word count
- Schema.org markup
- Content sections (H2/H3 structure)

Cached 48h to minimize requests.
"""

import re
import httpx
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from app.core.logging import get_logger

logger = get_logger(__name__)

# Domains to skip (your own store, search engines, etc.)
SKIP_DOMAINS = {
    'example-store.com', 'www.example-store.com',
    'google.com', 'google.com.mx',
    'youtube.com', 'facebook.com', 'instagram.com',
    'mercadolibre.com.mx', 'mercadolibre.com',
    'amazon.com.mx', 'amazon.com',
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class CompetitorPageScraper:
    """Scrape and analyze top competitor pages from SERP results."""

    CACHE_TTL_HOURS = 168  # 7 days — competitor content is relatively stable
    CACHE_KEY_PREFIX = "competitor_page:"

    async def analyze_competitor_pages(
        self,
        serp_data: Dict[str, Any],
        db,
        max_pages: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Main entry: take SERP organic results, fetch top competitor pages,
        extract structured content signals.
        
        Returns list of CompetitorPageAnalysis dicts.
        """
        organic = serp_data.get('all_organic', [])
        if not organic:
            logger.info("[CompetitorScraper] No organic results to analyze")
            return []

        # Filter out own domain and marketplaces
        candidates = []
        for result in organic:
            domain = result.get('domain', '').lower()
            if domain and domain not in SKIP_DOMAINS and not any(
                skip in domain for skip in SKIP_DOMAINS
            ):
                candidates.append(result)

        if not candidates:
            logger.info("[CompetitorScraper] No competitor URLs after filtering")
            return []

        # Take top N
        targets = candidates[:max_pages]
        logger.info(f"[CompetitorScraper] Analyzing {len(targets)} competitor pages")

        analyses = []
        for target in targets:
            url = target.get('url', '')
            if not url:
                continue

            analysis = await self._analyze_single_page(url, target, db)
            if analysis:
                analyses.append(analysis)

        logger.info(f"[CompetitorScraper] Completed {len(analyses)}/{len(targets)} page analyses")
        return analyses

    async def _analyze_single_page(
        self,
        url: str,
        serp_info: Dict[str, Any],
        db
    ) -> Optional[Dict[str, Any]]:
        """Fetch and analyze a single competitor page. Uses cache."""
        from app.models.aeo_models import CacheEntry
        import hashlib

        cache_key = f"{self.CACHE_KEY_PREFIX}{hashlib.md5(url.encode()).hexdigest()}"

        # Check cache
        cached = CacheEntry.get(db, cache_key)
        if cached is not None:
            logger.info(f"[CompetitorScraper] Cache HIT: {url[:60]}")
            cached['cached'] = True
            return cached

        # Fetch page — try Crawl4AI first (handles JS-rendered pages), fall back to httpx
        html = await self._fetch_html(url)
        if not html:
            return None

        analysis = self._extract_content_signals(html, url, serp_info)

        # Cache result
        CacheEntry.set(db, cache_key, analysis, ttl_hours=self.CACHE_TTL_HOURS)
        analysis['cached'] = False
        return analysis

    async def _fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch raw HTML from a URL.
        Uses Crawl4AI (handles JS rendering + stealth) with httpx fallback.
        """
        # --- Crawl4AI (primary) ---
        try:
            from crawl4ai import AsyncWebCrawler

            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(url=url)

            if result.success and result.html and len(result.html) >= 500:
                logger.info(f"[CompetitorScraper] Crawl4AI OK: {url[:60]}")
                return result.html

            logger.warning(f"[CompetitorScraper] Crawl4AI returned empty page for {url[:60]}, falling back")

        except ImportError:
            pass  # crawl4ai not installed — use fallback below
        except Exception as e:
            logger.warning(f"[CompetitorScraper] Crawl4AI error for {url[:60]}: {e}")

        # --- httpx fallback (static pages only) ---
        try:
            import random
            ua = random.choice(USER_AGENTS)

            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                verify=False
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": ua,
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
                    }
                )

            if response.status_code != 200:
                logger.warning(f"[CompetitorScraper] HTTP {response.status_code} for {url[:60]}")
                return None

            html = response.text
            if len(html) < 500:
                logger.warning(f"[CompetitorScraper] Too short response for {url[:60]}")
                return None

            return html

        except httpx.TimeoutException:
            logger.warning(f"[CompetitorScraper] Timeout: {url[:60]}")
            return None
        except Exception as e:
            logger.warning(f"[CompetitorScraper] Error fetching {url[:60]}: {e}")
            return None

    def _extract_content_signals(
        self,
        html: str,
        url: str,
        serp_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract structured content signals from HTML."""
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script/style
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        text = soup.get_text(separator=' ', strip=True)
        word_count = len(text.split())

        # FAQ detection
        faq_questions = self._extract_faqs(soup)

        # Spec tables
        tables = soup.find_all('table')
        spec_tables = []
        for table in tables:
            rows = table.find_all('tr')
            if 2 <= len(rows) <= 50:
                headers = [th.get_text(strip=True) for th in table.find_all('th')]
                spec_tables.append({
                    'rows': len(rows),
                    'headers': headers[:5]
                })

        # Video embeds
        videos = []
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if 'youtube' in src or 'vimeo' in src or 'wistia' in src:
                videos.append(src[:100])
        video_tags = soup.find_all('video')
        videos.extend([v.get('src', '')[:100] for v in video_tags if v.get('src')])

        # Heading structure
        headings = {}
        for level in ['h1', 'h2', 'h3']:
            h_tags = soup.find_all(level)
            headings[level] = [h.get_text(strip=True)[:80] for h in h_tags]

        # Schema.org / JSON-LD
        schema_types = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string or '{}')
                if isinstance(data, dict):
                    schema_types.append(data.get('@type', 'unknown'))
                elif isinstance(data, list):
                    schema_types.extend(
                        item.get('@type', 'unknown') for item in data if isinstance(item, dict)
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        # Images
        images = soup.find_all('img')
        image_count = len([img for img in images if img.get('src') and not img.get('src', '').endswith('.svg')])

        return {
            'url': url,
            'domain': serp_info.get('domain', ''),
            'serp_position': serp_info.get('position', 0),
            'serp_title': serp_info.get('title', ''),
            'word_count': word_count,
            'faq_count': len(faq_questions),
            'faq_questions': faq_questions[:8],
            'spec_tables': spec_tables[:3],
            'video_count': len(videos),
            'videos': videos[:3],
            'h2_sections': headings.get('h2', [])[:10],
            'h3_sections': headings.get('h3', [])[:10],
            'image_count': image_count,
            'schema_types': schema_types,
            'has_comparison_table': any(
                any(kw in ' '.join(t.get('headers', [])).lower() 
                    for kw in ['comparar', 'vs', 'modelo', 'especificación', 'compatib'])
                for t in spec_tables
            ),
        }

    def _extract_faqs(self, soup: BeautifulSoup) -> List[str]:
        """Extract FAQ questions from various HTML patterns."""
        questions = []

        # Pattern 1: FAQ Schema.org
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string or '{}')
                if isinstance(data, dict) and data.get('@type') == 'FAQPage':
                    for entity in data.get('mainEntity', []):
                        q = entity.get('name', '')
                        if q:
                            questions.append(q)
            except (json.JSONDecodeError, TypeError):
                pass

        # Pattern 2: accordion/details elements
        details = soup.find_all('details')
        for d in details:
            summary = d.find('summary')
            if summary:
                q = summary.get_text(strip=True)
                if q and '?' in q or len(q) > 10:
                    questions.append(q)

        # Pattern 3: Common FAQ class names
        faq_selectors = [
            {'class_': re.compile(r'faq', re.I)},
            {'class_': re.compile(r'accordion', re.I)},
            {'class_': re.compile(r'question', re.I)},
        ]
        for selector in faq_selectors:
            for el in soup.find_all(['div', 'dt', 'h3', 'h4', 'button'], **selector):
                text = el.get_text(strip=True)
                if text and len(text) > 10 and text not in questions:
                    questions.append(text)

        # Pattern 4: Question marks in headings
        for h in soup.find_all(['h2', 'h3', 'h4']):
            text = h.get_text(strip=True)
            if '¿' in text or '?' in text:
                if text not in questions:
                    questions.append(text)

        return questions[:15]


def format_competitor_pages_for_prompt(analyses: List[Dict[str, Any]]) -> str:
    """Format competitor page analyses into a prompt section for Grok."""
    if not analyses:
        return "No competitor page data available (pages could not be fetched or no competitors in SERP)."

    lines = []
    lines.append(f"Analyzed {len(analyses)} top competitor product pages:\n")

    for i, page in enumerate(analyses, 1):
        domain = page.get('domain', 'unknown')
        pos = page.get('serp_position', '?')
        word_count = page.get('word_count', 0)
        faq_count = page.get('faq_count', 0)
        video_count = page.get('video_count', 0)
        image_count = page.get('image_count', 0)
        tables = page.get('spec_tables', [])
        schema = page.get('schema_types', [])

        lines.append(f"### Competitor {i}: {domain} (SERP Position #{pos})")
        lines.append(f"- **Word count:** {word_count:,}")
        lines.append(f"- **FAQ questions:** {faq_count}")
        if page.get('faq_questions'):
            for q in page['faq_questions'][:5]:
                lines.append(f"  - \"{q[:100]}\"")
        lines.append(f"- **Spec tables:** {len(tables)}")
        if tables:
            for t in tables[:2]:
                lines.append(f"  - {t.get('rows', 0)} rows, headers: {', '.join(t.get('headers', [])[:4])}")
        lines.append(f"- **Videos:** {video_count}")
        lines.append(f"- **Images:** {image_count}")
        if page.get('has_comparison_table'):
            lines.append(f"- **⚠️ Has comparison table** (you should add one too)")
        if schema:
            lines.append(f"- **Schema.org:** {', '.join(schema[:5])}")

        # Content structure
        h2s = page.get('h2_sections', [])
        if h2s:
            lines.append(f"- **Content sections (H2):** {', '.join(h2s[:6])}")

        lines.append("")

    # Summary comparison
    if len(analyses) >= 2:
        avg_words = sum(p.get('word_count', 0) for p in analyses) // len(analyses)
        avg_faqs = sum(p.get('faq_count', 0) for p in analyses) // len(analyses)
        lines.append(f"**Competitor Average:** {avg_words:,} words, {avg_faqs} FAQ questions")
        lines.append("(Compare these numbers against YOUR product's content above)")

    return "\n".join(lines)


# Singleton instance
competitor_scraper = CompetitorPageScraper()
