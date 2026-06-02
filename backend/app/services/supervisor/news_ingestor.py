"""
News ingestor: fetches curated RSS/Atom feeds, dedupes, summarizes, stores.

Designed to run from the FastAPI app (POST /supervisor/news/ingest) so it
can be triggered by an external cron or by the existing scheduler.py pattern.

No new dependencies — uses httpx (already in requirements) and xml.etree
from stdlib. Summarization goes through the existing AnthropicProvider.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Any
import xml.etree.ElementTree as ET

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.models.supervisor_models import NewsItem, SupervisorRun
from app.services.supervisor.sources import get_sources

logger = get_logger(__name__)

# Atom uses XML namespaces; RSS does not. We normalize at parse time.
ATOM_NS = "{http://www.w3.org/2005/Atom}"
# RDF/RSS 1.0 namespaces (Search Engine Roundtable's FeedBurner is RDF)
RDF_NS = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
RSS1_NS = "{http://purl.org/rss/1.0/}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"

# How many items per LLM summarization batch. Higher = cheaper but more
# context to keep coherent. 6 is a good balance for Claude Haiku.
BATCH_SIZE = 6

# Hard cap so a runaway feed doesn't bankrupt us.
MAX_NEW_ITEMS_PER_RUN = 60

# Per-source ingestion ceiling. Some feeds publish 50+/day; we don't need them all.
MAX_ITEMS_PER_SOURCE = 12

ALLOWED_TAGS = {"algo", "aeo", "geo", "tooling", "policy", "market", "other"}
ALLOWED_RELEVANCE = {"high", "medium", "low", "skip"}


# ────────────────────────────────────────────────────────────────────────────
# Feed parsing
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class ParsedItem:
    title: str
    url: str
    guid: Optional[str]
    raw_summary: Optional[str]
    published_at: Optional[datetime]


def _strip_html(text: str) -> str:
    """Lightweight HTML strip — feeds sometimes embed markup in <description>."""
    if not text:
        return ""
    # Remove tags, collapse whitespace
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", no_tags).strip()


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # RFC 2822 (RSS pubDate)
    try:
        dt = parsedate_to_datetime(value)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        pass
    # ISO 8601 (Atom updated/published)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _parse_rss(root: ET.Element) -> List[ParsedItem]:
    items: List[ParsedItem] = []
    channel = root.find("channel")
    if channel is None:
        return items
    for entry in channel.findall("item"):
        title = (entry.findtext("title") or "").strip()
        link = (entry.findtext("link") or "").strip()
        guid = entry.findtext("guid")
        raw = entry.findtext("description") or entry.findtext(f"{CONTENT_NS}encoded")
        published = _parse_date(entry.findtext("pubDate") or entry.findtext(f"{DC_NS}date"))
        if title and link:
            items.append(ParsedItem(
                title=title,
                url=link,
                guid=(guid or "").strip() or None,
                raw_summary=_strip_html(raw or "")[:2000] or None,
                published_at=published,
            ))
    return items


def _parse_rdf(root: ET.Element) -> List[ParsedItem]:
    """RSS 1.0 (RDF) — items are siblings of <channel>, not children of it.
    Used by FeedBurner-mirrored feeds like seroundtable."""
    items: List[ParsedItem] = []
    # RDF items use either the RSS 1.0 namespace or no namespace
    candidates = (
        root.findall(f"{RSS1_NS}item")
        or root.findall("item")
    )
    for entry in candidates:
        title = (entry.findtext(f"{RSS1_NS}title") or entry.findtext("title") or "").strip()
        link = (entry.findtext(f"{RSS1_NS}link") or entry.findtext("link") or "").strip()
        # rdf:about attribute is the canonical URL when <link> is missing
        if not link:
            link = (entry.get(f"{RDF_NS}about") or "").strip()
        raw = (
            entry.findtext(f"{RSS1_NS}description")
            or entry.findtext("description")
            or entry.findtext(f"{CONTENT_NS}encoded")
        )
        published = _parse_date(entry.findtext(f"{DC_NS}date"))
        if title and link:
            items.append(ParsedItem(
                title=title,
                url=link,
                guid=link,
                raw_summary=_strip_html(raw or "")[:2000] or None,
                published_at=published,
            ))
    return items


def _parse_atom(root: ET.Element) -> List[ParsedItem]:
    items: List[ParsedItem] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        # Atom <link href="..." rel="alternate"/> — pick the alternate or first
        link_el = None
        for el in entry.findall(f"{ATOM_NS}link"):
            if el.get("rel") in (None, "alternate"):
                link_el = el
                break
        link = (link_el.get("href") if link_el is not None else "").strip()
        guid = (entry.findtext(f"{ATOM_NS}id") or "").strip() or None
        raw = entry.findtext(f"{ATOM_NS}summary") or entry.findtext(f"{ATOM_NS}content")
        published = _parse_date(
            entry.findtext(f"{ATOM_NS}published")
            or entry.findtext(f"{ATOM_NS}updated")
        )
        if title and link:
            items.append(ParsedItem(
                title=title,
                url=link,
                guid=guid,
                raw_summary=_strip_html(raw or "")[:2000] or None,
                published_at=published,
            ))
    return items


def parse_feed(body: bytes) -> List[ParsedItem]:
    """Parse RSS / Atom / RDF (RSS 1.0) into normalized ParsedItems. Returns [] on parse error."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        logger.warning(f"Feed parse error: {e}")
        return []

    tag = root.tag
    # RDF / RSS 1.0 — root is rdf:RDF, items are siblings of channel
    if tag == f"{RDF_NS}RDF" or tag.endswith("}RDF") or tag == "RDF":
        rdf_items = _parse_rdf(root)
        if rdf_items:
            return rdf_items
        return _parse_rss(root)
    if tag.endswith("rss") or tag == "rss":
        return _parse_rss(root)
    if tag == f"{ATOM_NS}feed" or tag.endswith("feed"):
        return _parse_atom(root)
    return _parse_rss(root)


def parse_json_search_status(body: bytes) -> List[ParsedItem]:
    """Google Search Status incidents.json — algorithmic updates land here first.

    Each entry has external_desc (title), uri (path), begin/created/modified dates,
    affected_products, status_impact (e.g. 'ranking'), severity.
    """
    items: List[ParsedItem] = []
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"JSON status feed parse error: {e}")
        return items
    if not isinstance(data, list):
        return items

    base = "https://status.search.google.com"
    for entry in data:
        if not isinstance(entry, dict):
            continue
        title = (entry.get("external_desc") or "").strip()
        if not title:
            continue
        uri = entry.get("uri") or ""
        link = uri if uri.startswith("http") else f"{base}{uri}"
        # Build a compact summary from the structured fields the LLM can use
        affected = entry.get("affected_products") or []
        affected_names = [a.get("title") for a in affected if isinstance(a, dict) and a.get("title")]
        last_update = ""
        updates = entry.get("updates") or []
        if updates and isinstance(updates[0], dict):
            last_update = updates[0].get("text", "")
        raw_parts = []
        if entry.get("status_impact"):
            raw_parts.append(f"Impact: {entry['status_impact']}")
        if entry.get("severity"):
            raw_parts.append(f"Severity: {entry['severity']}")
        if affected_names:
            raw_parts.append("Affected: " + ", ".join(affected_names))
        if last_update:
            raw_parts.append(f"Latest update: {last_update}")
        raw = ". ".join(raw_parts)[:2000] or None

        published = _parse_date(entry.get("begin") or entry.get("created"))
        items.append(ParsedItem(
            title=title,
            url=link,
            guid=entry.get("id") or link,
            raw_summary=raw,
            published_at=published,
        ))
    return items


# ────────────────────────────────────────────────────────────────────────────
# Fetching
# ────────────────────────────────────────────────────────────────────────────

async def fetch_feed(source: Dict) -> List[ParsedItem]:
    """Fetch one feed; never raises — returns [] on any failure.

    Dispatches on source['kind']: 'rss' (RSS/Atom/RDF auto-detected) or
    'json_search_status' (Google Search Status incidents.json).
    """
    url = source["url"]
    kind = source.get("kind", "rss")
    # Some feeds (Google blog, Shopify changelog, FeedBurner) reject non-browser UAs.
    # Use a real Chrome UA — RSS endpoints respect it without quirks.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/rss+xml, application/atom+xml, application/json, "
            "application/xml, text/xml; q=0.9, */*; q=0.5"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"[news] {source['key']} HTTP {resp.status_code}")
                return []
            if kind == "json_search_status":
                items = parse_json_search_status(resp.content)
            else:
                items = parse_feed(resp.content)
            return items[:MAX_ITEMS_PER_SOURCE]
    except Exception as e:
        logger.warning(f"[news] {source['key']} fetch error: {e}")
        return []


# ────────────────────────────────────────────────────────────────────────────
# Summarization
# ────────────────────────────────────────────────────────────────────────────

SUMMARIZE_SYSTEM = """You are a triage assistant for Example Store, a Mexican transmission-parts retailer with 5,000 SKUs selling on Shopify, Mercado Libre, and B2B. Spanish-first content for the Mexico market. The site bets heavily on AEO/GEO (visibility in ChatGPT / Perplexity / Claude / Gemini) and on organic Google rankings for fault-code and transmission-part queries.

Your job: classify each news item by whether it would change Example Store's SEO/AEO/GEO playbook. Be RUTHLESS about skipping noise. The operator only has 2 minutes a day for this feed — every irrelevant item is a tax.

For each item, output JSON with:

- bullets: 2-4 short sentences. Output them in SPANISH so the operator can scan in his native language. Lead with what CHANGED and what it MEANS for a Mexican e-commerce SEO/AEO operator. No marketing fluff. No "read more on...". If the item is `skip`, return [] (empty array).

- tag: one of [algo, aeo, geo, tooling, policy, market, other]
  - algo  = Google/Bing ranking changes, core/spam/HCU updates, SERP feature shifts (AI Overviews, Preferred Sources, etc.)
  - aeo   = ChatGPT/Perplexity/Claude/Gemini changes affecting how brands get cited or displayed
  - geo   = location-based search, MX/LATAM regional behavior, multilingual/Spanish search
  - tooling = Shopify, GA4, GSC, Ahrefs, schema.org spec — platforms we operate
  - policy = Google Search Essentials, structured data spec, helpful content guidelines
  - market = Mexican e-commerce, Mercado Libre, Spanish-search trends, MX consumer behavior
  - other = anything else

- relevance: one of [high, medium, low, skip] — be HARSH:
  - high   = This changes what Example Store should do THIS WEEK. Examples: Google rolls out core update; AI Overviews expand to ES-MX; Shopify adds a metafield type that affects schema; Perplexity changes citation rules; Spanish-language query behavior shifts.
  - medium = Worth a heads-up. May influence quarterly strategy. Examples: Bing market share moves; new GA4 metric; AEO measurement methodology paper; Google adds a SERP feature that's not yet in MX.
  - low    = General SEO knowledge, no concrete action. Often educational pieces. Examples: "What blog posts should you write to be mentioned in ChatGPT" (good thinking, but not breaking news); broad industry studies.
  - skip   = ZERO operator value. Default to skip when in doubt. Examples below.

SKIP examples (be aggressive):
- LLM vendor product launches that don't affect citation behavior ("Introducing Advanced Account Security", "Where the goblins came from", "Our principles", "GPT-5.5 System Card", "Cybersecurity in the Intelligence Age", VC/partnership news, FedRAMP certifications, infra announcements, AWS partnerships)
- B2B SaaS marketing studies ("Reddit marketing for SaaS", "117 brands study")
- Paid ads features that don't relate to organic discovery (Google Ads Brand Lift, PMax updates UNLESS they affect organic SERP rendering)
- Tool tutorials and "how-to" listicles
- Conference recaps without concrete algo info
- Marketing automation, email, CRM news
- AI lab manifesto / governance / safety / ethics pieces
- Anniversary posts, hiring news, exec quotes, thought leadership essays
- Items already covered by another item in this same batch (de-dupe to one)

DO NOT skip:
- Anything about Google ranking behavior, even if covered as opinion
- AEO/GEO citation mechanics (how LLMs choose what to cite, retrieval changes)
- Shopify schema/structured-data/SEO-affecting features
- Spanish-language search or MX-specific signals (rare, weight them up)
- Core/spam/helpful-content updates regardless of severity claim

Hard rules:
- Bullets are SPANISH. Tag and relevance are English machine values.
- Do not invent details. If the title is all you have, write less but don't fabricate.
- If unsure between two relevances, pick the LOWER one. False highs train the operator to ignore the feed.
- Maximum 4 bullets even for `high`. The operator is reading dozens per week."""


def _build_summarize_user_prompt(batch: List[Dict[str, str]]) -> str:
    """One prompt summarizing N items in a single call."""
    today = datetime.now(timezone.utc).date().isoformat()
    lines = [
        f"Today is {today}. Items below may be from days, weeks, or months ago — use the published date to judge freshness.",
        "",
        "Summarize each item. Return a JSON object with one key \"items\" whose value is an array of N objects in the same order as the input, one per item.",
        "",
        "Date-aware rules:",
        "- Completed algorithmic updates (Google core/spam/HCU/Discover updates) that finished MORE THAN 30 DAYS AGO are historical, not actionable. Mark them `low` unless the operator is doing a retro analysis.",
        "- Multi-week ongoing rollouts (e.g. AI Overviews expansion, Search Live) stay `medium`/`high` even if announced earlier — they're still affecting SERPs.",
        "- Items older than 60 days that aren't ongoing are usually `skip`.",
        "",
        "Items:",
    ]
    for i, item in enumerate(batch):
        lines.append(f"--- Item {i} ---")
        lines.append(f"Source: {item['source_name']}")
        if item.get("published"):
            lines.append(f"Published: {item['published']}")
        lines.append(f"Title: {item['title']}")
        if item.get("raw"):
            lines.append(f"Summary: {item['raw']}")
        lines.append(f"URL: {item['url']}")
        lines.append("")
    lines.append("Return JSON only. Schema:")
    lines.append('{"items":[{"bullets":["...","..."],"tag":"algo","relevance":"high"}, ...]}')
    return "\n".join(lines)


async def _summarize_batch_via_grok(
    batch: List[Dict[str, str]],
    model: str,
    api_key: str,
) -> Optional[List[Dict[str, Any]]]:
    """Call X.AI Grok with a batched prompt. Returns parsed list or None on error.

    Uses the OpenAI-compatible chat/completions endpoint with response_format=json_object.
    Grok's JSON mode requires an object root, so the prompt asks for {"items": [...]} and
    we unwrap.
    """
    # Reasoning models can be slow; mirror the timeout policy in the existing GrokProvider.
    request_timeout = 300.0 if "4.20" in model or "4-20" in model else 120.0

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SUMMARIZE_SYSTEM},
            {"role": "user", "content": _build_summarize_user_prompt(batch)},
        ],
        "temperature": 0.2,
        "top_p": 0.95,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning(f"[news] summarize HTTP {resp.status_code}: {resp.text[:300]}")
                return None
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            # Defensive: strip code fences if a model wrapped output despite json_object mode.
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
            parsed = json.loads(text)
            # Unwrap {"items": [...]} — also accept a raw array if the model returns one.
            if isinstance(parsed, dict):
                items = parsed.get("items") or parsed.get("results") or parsed.get("data")
                if isinstance(items, list):
                    return items
                # Some models return {"0": {...}, "1": {...}}; reconstitute by index.
                indexed = sorted(
                    ((int(k), v) for k, v in parsed.items() if str(k).isdigit()),
                    key=lambda kv: kv[0],
                )
                if indexed and all(isinstance(v, dict) for _, v in indexed):
                    return [v for _, v in indexed]
                return None
            if isinstance(parsed, list):
                return parsed
            return None
    except Exception as e:
        logger.warning(f"[news] summarize error: {e}")
        return None


def _normalize_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    bullets = raw.get("bullets") or []
    if not isinstance(bullets, list):
        bullets = [str(bullets)]
    bullets = [str(b).strip() for b in bullets if str(b).strip()][:5]

    tag = str(raw.get("tag", "other")).lower().strip()
    if tag not in ALLOWED_TAGS:
        tag = "other"

    relevance = str(raw.get("relevance", "low")).lower().strip()
    if relevance not in ALLOWED_RELEVANCE:
        relevance = "low"

    return {"bullets": bullets, "tag": tag, "relevance": relevance}


# ────────────────────────────────────────────────────────────────────────────
# Persistence
# ────────────────────────────────────────────────────────────────────────────

def _existing_urls(db: Session, source_key: str, urls: List[str]) -> set:
    if not urls:
        return set()
    rows = db.execute(
        select(NewsItem.url).where(NewsItem.source == source_key, NewsItem.url.in_(urls))
    ).all()
    return {r[0] for r in rows}


# ────────────────────────────────────────────────────────────────────────────
# Public entrypoint
# ────────────────────────────────────────────────────────────────────────────

async def ingest_news(db: Session, summarize: bool = True) -> Dict[str, Any]:
    """
    Run the full ingestion pipeline:
    1. Fetch each source
    2. Dedup against what's already in the DB (by source + url)
    3. Insert raw rows immediately so we don't lose data if summarization fails
    4. Summarize new rows in batches and update them in place
    5. Return a summary of what happened

    Designed to be idempotent: rerunning produces zero new rows if no new
    items exist upstream.
    """
    summarize_model = settings.SUPERVISOR_SUMMARIZE_MODEL or settings.XAI_MODEL
    run = SupervisorRun(mode="news_ingest", status="running", model=summarize_model if summarize else None)
    db.add(run)
    db.commit()
    db.refresh(run)

    started = datetime.now(timezone.utc)
    sources = get_sources()
    per_source_added: Dict[str, int] = {}
    new_rows: List[NewsItem] = []
    fetch_errors: List[str] = []

    # Step 1+2: fetch all feeds in parallel, dedup, insert raw
    fetch_tasks = [fetch_feed(s) for s in sources]
    parsed_per_source = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    for src, parsed in zip(sources, parsed_per_source):
        if isinstance(parsed, Exception):
            fetch_errors.append(f"{src['key']}: {parsed}")
            per_source_added[src["key"]] = 0
            continue
        if not parsed:
            per_source_added[src["key"]] = 0
            continue

        urls = [p.url for p in parsed]
        existing = _existing_urls(db, src["key"], urls)
        added = 0
        for p in parsed:
            if p.url in existing:
                continue
            row = NewsItem(
                source=src["key"],
                source_kind="atom" if "atom" in src["url"] else "rss",
                guid=p.guid,
                url=p.url,
                title=p.title[:500],
                raw_summary=p.raw_summary,
                published_at=p.published_at,
            )
            db.add(row)
            new_rows.append(row)
            added += 1
            if len(new_rows) >= MAX_NEW_ITEMS_PER_RUN:
                break
        per_source_added[src["key"]] = added
        if len(new_rows) >= MAX_NEW_ITEMS_PER_RUN:
            break

    db.commit()
    for r in new_rows:
        db.refresh(r)

    # Step 3+4: summarize in batches
    summarized = 0
    if summarize and new_rows and settings.XAI_API_KEY:
        # Batch new_rows; map row -> source_name for the prompt
        source_name_by_key = {s["key"]: s["name"] for s in sources}
        for i in range(0, len(new_rows), BATCH_SIZE):
            batch_rows = new_rows[i:i + BATCH_SIZE]
            batch_payload = [
                {
                    "source_name": source_name_by_key.get(r.source, r.source),
                    "title": r.title,
                    "raw": r.raw_summary or "",
                    "url": r.url,
                    "published": r.published_at.date().isoformat() if r.published_at else None,
                }
                for r in batch_rows
            ]
            results = await _summarize_batch_via_grok(
                batch_payload,
                model=summarize_model,
                api_key=settings.XAI_API_KEY,
            )
            if not results or len(results) != len(batch_rows):
                # Partial success: leave rows un-summarized; next run can retry.
                logger.warning(f"[news] summarize batch returned {len(results) if results else 0}/{len(batch_rows)}")
                continue
            for row, raw_result in zip(batch_rows, results):
                norm = _normalize_summary(raw_result)
                row.summary_bullets = norm["bullets"]
                row.tag = norm["tag"]
                row.relevance = norm["relevance"]
                row.summarized_at = datetime.now(timezone.utc)
                row.summary_model = summarize_model
                summarized += 1
        db.commit()

    finished = datetime.now(timezone.utc)
    run.finished_at = finished
    run.status = "ok" if not fetch_errors or summarized > 0 or new_rows else "ok"
    run.summary = (
        f"Fetched {len(sources)} sources, added {len(new_rows)} new items, "
        f"summarized {summarized}. Errors: {len(fetch_errors)}."
    )
    run.artifacts = {
        "sources_count": len(sources),
        "new_items": len(new_rows),
        "summarized": summarized,
        "per_source_added": per_source_added,
        "fetch_errors": fetch_errors,
        "duration_seconds": (finished - started).total_seconds(),
    }
    db.commit()

    return {
        "run_id": run.id,
        "new_items": len(new_rows),
        "summarized": summarized,
        "per_source_added": per_source_added,
        "fetch_errors": fetch_errors,
        "duration_seconds": (finished - started).total_seconds(),
    }
