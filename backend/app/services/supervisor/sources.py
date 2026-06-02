"""
Curated source list for the supervisor agent.

Keep this list short. Bias toward sources that publish *signals*, not noise.
Sources that produce zero useful items in 4 weeks should be removed during
the weekly tightening pass.

Each source has:
- key: short stable identifier, used in news_items.source
- url: feed URL
- name: human-readable
- kind: "rss" (also handles RDF/RSS 1.0 + Atom auto-detected) or "json_search_status"
- expected_tag: prior on what these items will be classified as (used as a hint
  for the LLM, not enforced)
- weight: 1-3 — used at retrieval time to bias high-signal feeds in summaries
"""
from typing import List, Dict


SOURCES: List[Dict] = [
    # --- Search algorithm + Google policy ---
    {
        "key": "search-engine-land",
        "url": "https://searchengineland.com/feed",
        "name": "Search Engine Land",
        "kind": "rss",
        "expected_tag": "algo",
        "weight": 3,
    },
    {
        "key": "search-engine-roundtable",
        # FeedBurner mirror — the direct /feed.xml returns 200 with empty body
        "url": "https://feeds.feedburner.com/seroundtable",
        "name": "Search Engine Roundtable",
        "kind": "rss",
        "expected_tag": "algo",
        "weight": 3,
    },
    {
        "key": "google-search-blog",
        # Replaces the old developers.google.com/search/blog feed (404'd Apr 2026)
        "url": "https://blog.google/products/search/rss/",
        "name": "Google Search Blog",
        "kind": "rss",
        "expected_tag": "policy",
        "weight": 3,
    },
    {
        "key": "google-search-status",
        # JSON feed — algo updates land here first (e.g. "March 2026 core update")
        "url": "https://status.search.google.com/incidents.json",
        "name": "Google Search Status",
        "kind": "json_search_status",
        "expected_tag": "algo",
        "weight": 3,
    },
    # --- AEO / GEO — AI surfaces ---
    {
        "key": "openai-news",
        "url": "https://openai.com/news/rss.xml",
        "name": "OpenAI News",
        "kind": "rss",
        "expected_tag": "aeo",
        "weight": 2,
    },
    # NOTE: Anthropic doesn't publish RSS as of Apr 2026. Their /news page is HTML-only.
    # Skipping for now; SEL + SE Roundtable cover the same announcements within 24h.
    # --- Tooling / commerce platform ---
    {
        "key": "shopify-changelog",
        "url": "https://changelog.shopify.com/feed",
        "name": "Shopify Changelog",
        "kind": "rss",
        "expected_tag": "tooling",
        "weight": 2,
    },
    # --- Mexico market signal (es-419) ---
    {
        "key": "google-blog-es419",
        "url": "https://blog.google/intl/es-419/rss/",
        "name": "Google Blog (es-419)",
        "kind": "rss",
        "expected_tag": "market",
        "weight": 1,
    },
]


def get_sources() -> List[Dict]:
    """Return the active source list. Function (not constant) so callers can
    monkeypatch in tests."""
    return SOURCES
