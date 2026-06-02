"""
April 2026 monthly dashboard export.

Aggregates GA4 + GSC + Shopify + per-product snapshot data for the month of
April 2026, filters out non-MX traffic (China / wider Asia / US bot countries),
and emits a markdown report on stdout.

Run:
    docker exec rag-seo-backend python -m scripts.april_2026_dashboard_export
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

# Silence SQLAlchemy echo logs that pollute the markdown output even in DEBUG mode.
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from sqlalchemy import func

from app.db.session import SessionLocal, engine as _engine
from app.models.product import Product, ProductAnalyticsSnapshot
from app.services.google_api_service import GoogleApiService
from app.services.shopify_service import ShopifyService

# After the engine is built (which may set echo=True and reset the logger level
# to INFO), force SQL logging back off so the markdown output stays clean.
_engine.echo = False
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

START = datetime(2026, 4, 1)
END = datetime(2026, 5, 1)
START_STR = "2026-04-01"
END_STR = "2026-04-30"

MX_ALIASES = {"Mexico", "México", "MX"}
EXCLUDED_BOT_COUNTRIES = {
    "China", "Hong Kong", "Taiwan", "Japan", "South Korea", "India",
    "Singapore", "Vietnam", "Thailand", "Indonesia", "Malaysia", "Philippines",
    "United States", "Russia", "(not set)",
}

# TikTok / Pangle ad-network signatures. These domains commonly leak through
# as `referral` instead of `paid_social` because campaigns aren't UTM-tagged.
TIKTOK_PATTERNS = [
    "pangleglobal.com", "pangle.io", "byteadsv2.com",
    "tiktok.com", "tiktok-ads.com", "ads.tiktok.com",
    "vm.tiktok.com", "m.tiktok.com",
]
META_PATTERNS = [
    "facebook.com", "fb.com", "instagram.com", "l.facebook.com",
    "lm.facebook.com", "m.facebook.com", "l.instagram.com",
]
AI_PATTERNS = [
    "chatgpt", "openai", "perplexity", "claude.ai",
    "copilot.microsoft.com", "you.com", "phind",
]


def classify_channel(source: str, medium: str = "", referrer: str = "") -> str:
    """Map a (source, medium, referrer) triple to a unified channel name."""
    s = (source or "").lower()
    m = (medium or "").lower()
    r = (referrer or "").lower()
    blob = f"{s} {r}"

    if any(p in blob for p in TIKTOK_PATTERNS):
        return "TikTok Ads (untagged)"
    if any(p in blob for p in AI_PATTERNS):
        return "AI Referral"
    if any(p in blob for p in META_PATTERNS) or s in {"facebook", "instagram"}:
        return "Meta (FB/IG)"
    if "google" in s and m in {"cpc", "paid", "ppc", "paidsearch"}:
        return "Google Ads"
    if "google" in s:
        return "Google Organic"
    if "bing" in s:
        return "Bing"
    if "yahoo" in s:
        return "Yahoo"
    if s in {"direct", "(direct)", ""} and m in {"(none)", "", "none"}:
        return "Direct"
    if "shop.app" in s or "shop.app" in r:
        return "Shop App"
    if m == "email" or "email" in s or "shopify_email" in s or "judgeme" in s:
        return "Email"
    if "respond" in s:
        return "Respond.io"
    if m == "referral":
        return f"Referral ({s[:40]})"
    return f"Other ({s[:40]} / {m[:20]})"


def fmt_int(n: float | int) -> str:
    return f"{int(n):,}".replace(",", " ")


def fmt_money(n: float) -> str:
    # Shopify shopMoney + GA4 totalRevenue are both in MXN for this store.
    return f"{n:,.2f} MXN".replace(",", " ")


def fmt_pct(n: float, decimals: int = 1) -> str:
    return f"{n:.{decimals}f}%"


def section(title: str) -> None:
    print()
    print(f"## {title}")
    print()


def subsection(title: str) -> None:
    print()
    print(f"### {title}")
    print()


# ---------------------------------------------------------------------------
# 1. Per-product snapshot aggregation (April 30 closing state)
# ---------------------------------------------------------------------------

def snapshot_aggregates(db) -> dict[str, Any]:
    apr30_start = datetime(2026, 4, 30)
    apr30_end = datetime(2026, 5, 1)

    snaps = (
        db.query(ProductAnalyticsSnapshot)
        .filter(
            ProductAnalyticsSnapshot.snapshot_date >= apr30_start,
            ProductAnalyticsSnapshot.snapshot_date < apr30_end,
        )
        .all()
    )

    total_sold_30d = sum(s.sold_30d or 0 for s in snaps)
    total_revenue_30d = sum(float(s.revenue_30d or 0) for s in snaps)
    total_ga4_sessions = sum(s.ga4_sessions or 0 for s in snaps)
    total_ga4_revenue = sum(float(s.ga4_revenue or 0) for s in snaps)
    total_gsc_impressions = sum(s.gsc_impressions or 0 for s in snaps)
    total_gsc_clicks = sum(s.gsc_clicks or 0 for s in snaps)

    # Weighted-by-impressions average position
    weighted_pos_num = sum(
        (s.gsc_position or 0) * (s.gsc_impressions or 0) for s in snaps
    )
    weighted_pos = (
        weighted_pos_num / total_gsc_impressions if total_gsc_impressions else 0
    )

    avg_seo_score = (
        sum(s.seo_score or 0 for s in snaps) / len(snaps) if snaps else 0
    )

    # Position buckets (top 3 / 4-10 / 11-20 / 21-50 / 51+)
    buckets = {"top3": 0, "top10": 0, "top20": 0, "top50": 0, "beyond": 0, "no_rank": 0}
    for s in snaps:
        p = s.gsc_position or 0
        if p == 0:
            buckets["no_rank"] += 1
        elif p <= 3:
            buckets["top3"] += 1
        elif p <= 10:
            buckets["top10"] += 1
        elif p <= 20:
            buckets["top20"] += 1
        elif p <= 50:
            buckets["top50"] += 1
        else:
            buckets["beyond"] += 1

    return {
        "snap_count": len(snaps),
        "total_sold_30d": total_sold_30d,
        "total_revenue_30d": total_revenue_30d,
        "ga4_sessions": total_ga4_sessions,
        "ga4_revenue": total_ga4_revenue,
        "gsc_impressions": total_gsc_impressions,
        "gsc_clicks": total_gsc_clicks,
        "weighted_position": weighted_pos,
        "avg_seo_score": avg_seo_score,
        "position_buckets": buckets,
        "snaps": snaps,
    }


def top_products(snaps, db, by: str, limit: int = 30) -> list[dict[str, Any]]:
    product_map = {
        p.id: p for p in db.query(Product).filter(
            Product.id.in_([s.product_id for s in snaps])
        ).all()
    }

    def keyfn(s):
        if by == "sales":
            return float(s.revenue_30d or 0)
        if by == "units":
            return s.sold_30d or 0
        if by == "impressions":
            return s.gsc_impressions or 0
        if by == "clicks":
            return s.gsc_clicks or 0
        if by == "ga4_sessions":
            return s.ga4_sessions or 0
        return 0

    sorted_snaps = sorted(snaps, key=keyfn, reverse=True)[:limit]
    rows = []
    for s in sorted_snaps:
        p = product_map.get(s.product_id)
        if not p:
            continue
        rows.append({
            "title": (p.title or "")[:80],
            "handle": p.handle,
            "sold_30d": s.sold_30d or 0,
            "revenue_30d": float(s.revenue_30d or 0),
            "gsc_impressions": s.gsc_impressions or 0,
            "gsc_clicks": s.gsc_clicks or 0,
            "gsc_position": float(s.gsc_position or 0),
            "ga4_sessions": s.ga4_sessions or 0,
            "seo_score": s.seo_score or 0,
            "price": float(p.price or 0),
        })
    return rows


def position_movers(db, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    """Compare April 30 vs March 27 snapshots to find biggest position gains/losses.

    March 27 is the closest pre-April reference we have.
    """
    march = datetime(2026, 3, 27)
    march_end = datetime(2026, 3, 28)
    april = datetime(2026, 4, 30)
    april_end = datetime(2026, 5, 1)

    march_snaps = {
        s.product_id: s for s in db.query(ProductAnalyticsSnapshot).filter(
            ProductAnalyticsSnapshot.snapshot_date >= march,
            ProductAnalyticsSnapshot.snapshot_date < march_end,
        ).all()
    }
    april_snaps = {
        s.product_id: s for s in db.query(ProductAnalyticsSnapshot).filter(
            ProductAnalyticsSnapshot.snapshot_date >= april,
            ProductAnalyticsSnapshot.snapshot_date < april_end,
        ).all()
    }

    deltas = []
    common_ids = set(march_snaps.keys()) & set(april_snaps.keys())
    products_in_play = {
        p.id: p for p in db.query(Product).filter(Product.id.in_(common_ids)).all()
    }

    for pid in common_ids:
        m = march_snaps[pid]
        a = april_snaps[pid]
        if not m.gsc_position or not a.gsc_position:
            continue
        # Need meaningful exposure
        if (a.gsc_impressions or 0) < 50:
            continue
        delta = float(m.gsc_position) - float(a.gsc_position)  # positive = improvement
        prod = products_in_play.get(pid)
        if not prod:
            continue
        deltas.append({
            "title": (prod.title or "")[:70],
            "handle": prod.handle,
            "march_pos": float(m.gsc_position),
            "april_pos": float(a.gsc_position),
            "delta": delta,
            "april_impr": a.gsc_impressions or 0,
            "april_clicks": a.gsc_clicks or 0,
        })

    gainers = sorted(deltas, key=lambda d: d["delta"], reverse=True)[:limit]
    losers = sorted(deltas, key=lambda d: d["delta"])[:limit]
    return {"gainers": gainers, "losers": losers, "compared": len(deltas)}


# ---------------------------------------------------------------------------
# 2. Live GA4 (April 1 → April 30, country-filtered)
# ---------------------------------------------------------------------------

def ga4_april(svc: GoogleApiService) -> dict[str, Any]:
    if not svc.credentials or not svc.property_id:
        return {"error": "GA4 not configured"}

    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest, OrderBy,
    )

    client = BetaAnalyticsDataClient(credentials=svc.credentials)
    prop = f"properties/{svc.property_id}"
    dr = [DateRange(start_date=START_STR, end_date=END_STR)]

    out: dict[str, Any] = {}

    # Totals (no filter)
    resp = client.run_report(RunReportRequest(
        property=prop,
        metrics=[
            Metric(name="sessions"),
            Metric(name="activeUsers"),
            Metric(name="screenPageViews"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="conversions"),
            Metric(name="totalRevenue"),
        ],
        date_ranges=dr,
    ))
    if resp.rows:
        r = resp.rows[0]
        out["totals_all"] = {
            "sessions": int(r.metric_values[0].value),
            "users": int(r.metric_values[1].value),
            "pageviews": int(r.metric_values[2].value),
            "bounce_rate": round(float(r.metric_values[3].value) * 100, 1),
            "avg_duration_sec": round(float(r.metric_values[4].value), 1),
            "conversions": int(float(r.metric_values[5].value)),
            "revenue": round(float(r.metric_values[6].value), 2),
        }

    # By country
    resp = client.run_report(RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="country")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="activeUsers"),
            Metric(name="bounceRate"),
            Metric(name="conversions"),
        ],
        date_ranges=dr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=25,
    ))
    out["by_country"] = [
        {
            "country": row.dimension_values[0].value,
            "sessions": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
            "bounce_rate": round(float(row.metric_values[2].value) * 100, 1),
            "conversions": int(float(row.metric_values[3].value)),
        }
        for row in resp.rows
    ]

    # MX-only totals
    mx_sessions = sum(c["sessions"] for c in out["by_country"] if c["country"] in MX_ALIASES)
    mx_users = sum(c["users"] for c in out["by_country"] if c["country"] in MX_ALIASES)
    mx_conv = sum(c["conversions"] for c in out["by_country"] if c["country"] in MX_ALIASES)
    bot_sessions = sum(
        c["sessions"] for c in out["by_country"]
        if c["country"] in EXCLUDED_BOT_COUNTRIES
    )
    out["mx_totals"] = {
        "sessions": mx_sessions, "users": mx_users, "conversions": mx_conv,
    }
    out["bot_sessions_filtered"] = bot_sessions

    # By channel
    resp = client.run_report(RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="conversions"),
            Metric(name="totalRevenue"),
        ],
        date_ranges=dr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    ))
    out["by_channel"] = [
        {
            "channel": row.dimension_values[0].value,
            "sessions": int(row.metric_values[0].value),
            "conversions": int(float(row.metric_values[1].value)),
            "revenue": round(float(row.metric_values[2].value), 2),
        }
        for row in resp.rows
    ]

    # Top 25 source/medium
    resp = client.run_report(RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="conversions"),
            Metric(name="totalRevenue"),
        ],
        date_ranges=dr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=25,
    ))
    out["by_source_medium"] = [
        {
            "source": row.dimension_values[0].value,
            "medium": row.dimension_values[1].value,
            "sessions": int(row.metric_values[0].value),
            "conversions": int(float(row.metric_values[1].value)),
            "revenue": round(float(row.metric_values[2].value), 2),
        }
        for row in resp.rows
    ]

    # Top 30 landing pages (MX-filtered would require dimension+filter — simpler:
    # report all then user can read country breakdown for context)
    resp = client.run_report(RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="activeUsers"),
            Metric(name="bounceRate"),
            Metric(name="conversions"),
        ],
        date_ranges=dr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=30,
    ))
    out["top_pages"] = [
        {
            "path": row.dimension_values[0].value,
            "sessions": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
            "bounce_rate": round(float(row.metric_values[2].value) * 100, 1),
            "conversions": int(float(row.metric_values[3].value)),
        }
        for row in resp.rows
    ]

    # Conversions broken down by event_name — reveals what GA4 counts as
    # "conversion" (purchase vs add_to_cart vs view_item etc.)
    resp = client.run_report(RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount"), Metric(name="conversions"), Metric(name="totalRevenue")],
        date_ranges=dr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="eventCount"), desc=True)],
        limit=30,
    ))
    out["events_by_name"] = [
        {
            "event": row.dimension_values[0].value,
            "count": int(row.metric_values[0].value),
            "conversions": int(float(row.metric_values[1].value)),
            "revenue": round(float(row.metric_values[2].value), 2),
        }
        for row in resp.rows
    ]

    # TikTok / Pangle detection — aggregate across the source/medium list
    tiktok = {"sessions": 0, "conversions": 0, "revenue": 0.0, "entries": []}
    for s in out.get("by_source_medium", []):
        blob = f"{s['source']}".lower()
        if any(p in blob for p in TIKTOK_PATTERNS):
            tiktok["sessions"] += s["sessions"]
            tiktok["conversions"] += s["conversions"]
            tiktok["revenue"] += s["revenue"]
            tiktok["entries"].append(s)
    out["tiktok_detected"] = tiktok

    return out


# ---------------------------------------------------------------------------
# 3. Live Search Console (April 1 → April 30)
# ---------------------------------------------------------------------------

def gsc_april(svc: GoogleApiService) -> dict[str, Any]:
    if not svc.credentials or not svc.site_url:
        return {"error": "GSC not configured"}

    from googleapiclient.discovery import build
    service = build("webmasters", "v3", credentials=svc.credentials)

    out: dict[str, Any] = {}

    # Totals
    resp = service.searchanalytics().query(siteUrl=svc.site_url, body={
        "startDate": START_STR,
        "endDate": END_STR,
    }).execute()
    if "rows" in resp and resp["rows"]:
        r = resp["rows"][0]
        out["totals"] = {
            "clicks": int(r["clicks"]),
            "impressions": int(r["impressions"]),
            "ctr": round(float(r["ctr"]) * 100, 2),
            "position": round(float(r["position"]), 2),
        }
    else:
        out["totals"] = {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}

    # Top queries
    resp = service.searchanalytics().query(siteUrl=svc.site_url, body={
        "startDate": START_STR,
        "endDate": END_STR,
        "dimensions": ["query"],
        "rowLimit": 50,
    }).execute()
    out["top_queries"] = [
        {
            "query": row["keys"][0],
            "clicks": int(row["clicks"]),
            "impressions": int(row["impressions"]),
            "ctr": round(float(row["ctr"]) * 100, 2),
            "position": round(float(row["position"]), 2),
        }
        for row in resp.get("rows", [])
    ]

    # Top pages
    resp = service.searchanalytics().query(siteUrl=svc.site_url, body={
        "startDate": START_STR,
        "endDate": END_STR,
        "dimensions": ["page"],
        "rowLimit": 50,
    }).execute()
    out["top_pages"] = [
        {
            "page": row["keys"][0],
            "clicks": int(row["clicks"]),
            "impressions": int(row["impressions"]),
            "ctr": round(float(row["ctr"]) * 100, 2),
            "position": round(float(row["position"]), 2),
        }
        for row in resp.get("rows", [])
    ]

    # Country breakdown for SEO traffic
    resp = service.searchanalytics().query(siteUrl=svc.site_url, body={
        "startDate": START_STR,
        "endDate": END_STR,
        "dimensions": ["country"],
        "rowLimit": 25,
    }).execute()
    out["by_country"] = [
        {
            "country": row["keys"][0].upper(),
            "clicks": int(row["clicks"]),
            "impressions": int(row["impressions"]),
            "ctr": round(float(row["ctr"]) * 100, 2),
            "position": round(float(row["position"]), 2),
        }
        for row in resp.get("rows", [])
    ]

    return out


# ---------------------------------------------------------------------------
# 4. Live Shopify orders (April 1 → April 30, country-filtered)
# ---------------------------------------------------------------------------

def shopify_april(svc: ShopifyService) -> dict[str, Any]:
    if not svc._ensure_initialized():
        return {"error": "Shopify not configured"}

    orders = svc._fetch_orders_with_utm(START, datetime(2026, 4, 30, 23, 59, 59))

    out: dict[str, Any] = {
        "raw_count": len(orders),
        "by_country": defaultdict(lambda: {"orders": 0, "revenue": 0.0}),
        "by_source": defaultdict(lambda: {"orders": 0, "revenue": 0.0}),
        "by_channel": defaultdict(lambda: {"orders": 0, "revenue": 0.0}),
        "top_products": defaultdict(lambda: {"qty": 0, "revenue": 0.0, "title": ""}),
        "by_day": defaultdict(lambda: {"orders": 0, "revenue": 0.0}),
        "ai_referral_orders": [],
    }

    mx_orders = 0
    mx_revenue = 0.0
    bot_orders = 0
    total_revenue = 0.0

    for o in orders:
        try:
            total = float(o.get("totalPriceSet", {}).get("shopMoney", {}).get("amount", 0))
        except Exception:
            total = 0.0
        ship = (o.get("shippingAddress") or {}).get("country") or (o.get("billingAddress") or {}).get("country") or "Unknown"
        out["by_country"][ship]["orders"] += 1
        out["by_country"][ship]["revenue"] += total

        total_revenue += total

        if ship in MX_ALIASES:
            mx_orders += 1
            mx_revenue += total
        elif ship in EXCLUDED_BOT_COUNTRIES:
            bot_orders += 1

        # Source
        journey = o.get("customerJourneySummary") or {}
        first = journey.get("firstVisit") or {}
        source = (first.get("source") or "direct").lower()
        out["by_source"][source]["orders"] += 1
        out["by_source"][source]["revenue"] += total

        ref_url = (first.get("referrerUrl") or "").lower()
        # Unified channel attribution
        channel = classify_channel(source, "", ref_url)
        out["by_channel"][channel]["orders"] += 1
        out["by_channel"][channel]["revenue"] += total

        if any(p in ref_url for p in AI_PATTERNS) or any(p in source for p in AI_PATTERNS):
            out["ai_referral_orders"].append({
                "id": o.get("name"),
                "source": source,
                "referrer": ref_url[:100],
                "total": total,
                "country": ship,
            })

        # Date bucket
        try:
            dt = datetime.fromisoformat(o["createdAt"].replace("Z", "+00:00")).date()
            out["by_day"][dt.isoformat()]["orders"] += 1
            out["by_day"][dt.isoformat()]["revenue"] += total
        except Exception:
            pass

        # Line items / products
        for ie in (o.get("lineItems") or {}).get("edges", []):
            n = ie.get("node", {})
            qty = n.get("quantity") or 0
            try:
                line_total = float(n.get("originalTotalSet", {}).get("shopMoney", {}).get("amount", 0))
            except Exception:
                line_total = 0
            prod = n.get("product") or {}
            pid = prod.get("id") or "unknown"
            out["top_products"][pid]["qty"] += qty
            out["top_products"][pid]["revenue"] += line_total
            out["top_products"][pid]["title"] = (prod.get("title") or "")[:80]

    out["total_orders"] = len(orders)
    out["total_revenue"] = round(total_revenue, 2)
    out["mx_orders"] = mx_orders
    out["mx_revenue"] = round(mx_revenue, 2)
    out["mx_share_orders_pct"] = round(mx_orders / max(len(orders), 1) * 100, 1)
    out["mx_share_revenue_pct"] = round(mx_revenue / max(total_revenue, 1) * 100, 1)
    out["bot_orders_filtered"] = bot_orders

    out["by_country"] = sorted(
        ({"country": k, **v} for k, v in out["by_country"].items()),
        key=lambda r: r["revenue"],
        reverse=True,
    )
    out["by_source"] = sorted(
        ({"source": k, **v} for k, v in out["by_source"].items()),
        key=lambda r: r["revenue"],
        reverse=True,
    )[:25]
    out["by_channel"] = sorted(
        ({"channel": k, **v} for k, v in out["by_channel"].items()),
        key=lambda r: r["revenue"],
        reverse=True,
    )
    out["top_products"] = sorted(
        ({"id": k, **v} for k, v in out["top_products"].items()),
        key=lambda r: r["revenue"],
        reverse=True,
    )[:30]
    out["by_day"] = sorted(
        ({"date": k, **v} for k, v in out["by_day"].items()),
        key=lambda r: r["date"],
    )

    return out


# ---------------------------------------------------------------------------
# 4b. Unified channel attribution — cross-reference GA4 + Shopify
# ---------------------------------------------------------------------------

def unified_attribution(ga4: dict, shop: dict) -> list[dict[str, Any]]:
    """Build a per-channel ROI table combining GA4 traffic with Shopify orders.

    Maps every GA4 source/medium row and every Shopify by_channel row into the
    same canonical channel name (via classify_channel), then merges them so each
    row shows: GA4 sessions, GA4 conversions (event-level), GA4 revenue
    (attribution-decayed), Shopify real orders, Shopify real revenue.
    """
    channels: dict[str, dict[str, float]] = defaultdict(lambda: {
        "ga4_sessions": 0,
        "ga4_conversions": 0,
        "ga4_revenue": 0.0,
        "shop_orders": 0,
        "shop_revenue": 0.0,
    })

    # GA4 side — collapse all source/medium rows into channels
    for s in ga4.get("by_source_medium", []):
        ch = classify_channel(s["source"], s["medium"])
        channels[ch]["ga4_sessions"] += s["sessions"]
        channels[ch]["ga4_conversions"] += s["conversions"]
        channels[ch]["ga4_revenue"] += s["revenue"]

    # Shopify side — already pre-classified in shopify_april()
    for s in shop.get("by_channel", []):
        ch = s["channel"]
        channels[ch]["shop_orders"] += s["orders"]
        channels[ch]["shop_revenue"] += s["revenue"]

    rows = []
    for ch, vals in channels.items():
        sess = vals["ga4_sessions"]
        rows.append({
            "channel": ch,
            "ga4_sessions": int(sess),
            "ga4_conversions": int(vals["ga4_conversions"]),
            "ga4_revenue": round(vals["ga4_revenue"], 2),
            "shop_orders": int(vals["shop_orders"]),
            "shop_revenue": round(vals["shop_revenue"], 2),
            "real_cvr_pct": round(vals["shop_orders"] / sess * 100, 2) if sess else 0,
            "rev_per_session": round(vals["shop_revenue"] / sess, 2) if sess else 0,
        })
    rows.sort(key=lambda r: r["shop_revenue"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 5. Render markdown report
# ---------------------------------------------------------------------------

def render(snap: dict, ga4: dict, gsc: dict, shop: dict, db) -> None:
    print(f"# Example Store — Tableau de bord avril 2026")
    print()
    print(f"_Période: {START_STR} → {END_STR}_  ")
    print(f"_Généré: {datetime.now().isoformat(timespec='seconds')}_  ")
    print(f"_Filtrage bots: pays exclus = {', '.join(sorted(EXCLUDED_BOT_COUNTRIES))}_")

    # ----- TOP-LINE -----
    section("1. Résumé exécutif")
    print("| Métrique | Valeur |")
    print("|---|---|")
    if "totals_all" in ga4:
        t = ga4["totals_all"]
        print(f"| Sessions GA4 (toutes origines) | {fmt_int(t['sessions'])} |")
        print(f"| Sessions GA4 — Mexique uniquement | {fmt_int(ga4['mx_totals']['sessions'])} |")
        print(f"| Sessions filtrées (CN/US/Asie/etc.) | {fmt_int(ga4['bot_sessions_filtered'])} |")
        print(f"| Utilisateurs actifs (toutes origines) | {fmt_int(t['users'])} |")
        print(f"| Pages vues | {fmt_int(t['pageviews'])} |")
        print(f"| Taux de rebond moyen | {fmt_pct(t['bounce_rate'])} |")
        print(f"| Durée moyenne session | {t['avg_duration_sec']}s |")
        print(f"| Conversions GA4 | {fmt_int(t['conversions'])} |")
        print(f"| Revenu GA4 | {fmt_money(t['revenue'])} |")

    if "total_orders" in shop:
        print(f"| Commandes Shopify (total) | {fmt_int(shop['total_orders'])} |")
        print(f"| Commandes Shopify — MX | {fmt_int(shop['mx_orders'])} ({fmt_pct(shop['mx_share_orders_pct'])}) |")
        print(f"| Revenu Shopify (total) | {fmt_money(shop['total_revenue'])} |")
        print(f"| Revenu Shopify — MX | {fmt_money(shop['mx_revenue'])} ({fmt_pct(shop['mx_share_revenue_pct'])}) |")
        print(f"| Commandes pays exclus (bots) | {fmt_int(shop['bot_orders_filtered'])} |")

    if "totals" in gsc:
        t = gsc["totals"]
        print(f"| Impressions Search Console | {fmt_int(t['impressions'])} |")
        print(f"| Clics Search Console | {fmt_int(t['clicks'])} |")
        print(f"| CTR moyen Search Console (global) | {fmt_pct(t['ctr'], 2)} |")
        print(f"| Position moyenne Search Console | {t['position']} |")

        # MX-pure GSC metrics — strip USA + Spain + Canada + France etc.
        # to reflect real Mexican market performance.
        countries = gsc.get("by_country", [])
        mx_row = next((c for c in countries if c["country"] in {"MEX", "MX"}), None)
        non_market = {"USA", "ESP", "CAN", "FRA", "CUW"}  # markets where Example Store doesn't ship
        non_market_clicks = sum(c["clicks"] for c in countries if c["country"] in non_market)
        non_market_impr = sum(c["impressions"] for c in countries if c["country"] in non_market)
        ex_clicks = max(t["clicks"] - non_market_clicks, 0)
        ex_impr = max(t["impressions"] - non_market_impr, 0)
        ex_ctr = (ex_clicks / ex_impr * 100) if ex_impr else 0
        if mx_row:
            print(f"| **CTR MX-pure (Mexique uniquement)** | **{fmt_pct(mx_row['ctr'], 2)}** ({fmt_int(mx_row['clicks'])} clics / {fmt_int(mx_row['impressions'])} impr.) |")
        print(f"| **CTR sans marchés non-livrés** (excl. USA, ES, CA, FR) | **{fmt_pct(ex_ctr, 2)}** ({fmt_int(ex_clicks)} clics / {fmt_int(ex_impr)} impr.) |")

    if "snap_count" in snap:
        print(f"| Produits avec snapshot avril | {fmt_int(snap['snap_count'])} |")
        print(f"| Score SEO moyen produits | {snap['avg_seo_score']:.1f} |")

    # ----- GA4 -----
    section("2. GA4 — Trafic site (avril)")

    subsection("2.1 Par pays (top 25)")
    print("| Pays | Sessions | Utilisateurs | Rebond | Conversions | Filtré ? |")
    print("|---|---:|---:|---:|---:|:---:|")
    for c in ga4.get("by_country", []):
        bot = "🤖 OUI" if c["country"] in EXCLUDED_BOT_COUNTRIES else ""
        if c["country"] in MX_ALIASES:
            bot = "✅ MX"
        print(f"| {c['country']} | {fmt_int(c['sessions'])} | {fmt_int(c['users'])} | {fmt_pct(c['bounce_rate'])} | {fmt_int(c['conversions'])} | {bot} |")

    subsection("2.2 Par canal")
    print("| Canal | Sessions | Conversions | Revenu |")
    print("|---|---:|---:|---:|")
    for c in ga4.get("by_channel", []):
        print(f"| {c['channel']} | {fmt_int(c['sessions'])} | {fmt_int(c['conversions'])} | {fmt_money(c['revenue'])} |")

    subsection("2.3 Top 25 source / medium")
    print("| Source | Medium | Sessions | Conversions | Revenu |")
    print("|---|---|---:|---:|---:|")
    for s in ga4.get("by_source_medium", []):
        print(f"| {s['source']} | {s['medium']} | {fmt_int(s['sessions'])} | {fmt_int(s['conversions'])} | {fmt_money(s['revenue'])} |")

    subsection("2.4 Top 30 pages d'atterrissage")
    print("| Page | Sessions | Utilisateurs | Rebond | Conversions |")
    print("|---|---:|---:|---:|---:|")
    for p in ga4.get("top_pages", []):
        print(f"| `{p['path']}` | {fmt_int(p['sessions'])} | {fmt_int(p['users'])} | {fmt_pct(p['bounce_rate'])} | {fmt_int(p['conversions'])} |")

    subsection("2.5 Conversions GA4 par event_name")
    print("_GA4 compte une « conversion » dès qu'un event marqué comme conversion se déclenche. Cette table montre quels events gonflent le compteur (purchase = vraie vente, add_to_cart / view_item = micro-conversions)._\n")
    print("| Event | # Événements | Conversions | Revenu GA4 |")
    print("|---|---:|---:|---:|")
    for e in ga4.get("events_by_name", []):
        print(f"| `{e['event']}` | {fmt_int(e['count'])} | {fmt_int(e['conversions'])} | {fmt_money(e['revenue'])} |")

    tk = ga4.get("tiktok_detected") or {}
    if tk.get("sessions"):
        subsection("2.6 Trafic TikTok / Pangle (mal taggé en « Referral »)")
        print("_Sources détectées comme TikTok Ads via les domaines pangleglobal, byteadsv2, tiktok.com, etc. À ajouter `utm_source=tiktok&utm_medium=cpc` aux campagnes pour que GA4 les classe correctement._\n")
        print(f"**Total TikTok détecté** : {fmt_int(tk['sessions'])} sessions · {fmt_int(tk['conversions'])} conversions · {fmt_money(tk['revenue'])} revenu GA4\n")
        print("| Source détectée | Medium GA4 | Sessions | Conversions GA4 | Revenu GA4 |")
        print("|---|---|---:|---:|---:|")
        for e in tk.get("entries", []):
            print(f"| {e['source']} | {e['medium']} | {fmt_int(e['sessions'])} | {fmt_int(e['conversions'])} | {fmt_money(e['revenue'])} |")

    # ----- SHOPIFY -----
    section("3. Shopify — Ventes (avril)")

    subsection("3.1 Ventes par pays")
    print("| Pays | Commandes | Revenu | Filtré ? |")
    print("|---|---:|---:|:---:|")
    for c in shop.get("by_country", []):
        bot = "🤖 OUI" if c["country"] in EXCLUDED_BOT_COUNTRIES else ""
        if c["country"] in MX_ALIASES:
            bot = "✅ MX"
        print(f"| {c['country']} | {fmt_int(c['orders'])} | {fmt_money(c['revenue'])} | {bot} |")

    subsection("3.2 Ventes par source d'acquisition (top 25)")
    print("| Source | Commandes | Revenu |")
    print("|---|---:|---:|")
    for s in shop.get("by_source", []):
        print(f"| {s['source']} | {fmt_int(s['orders'])} | {fmt_money(s['revenue'])} |")

    subsection("3.3 Ventes par jour d'avril")
    print("| Date | Commandes | Revenu |")
    print("|---|---:|---:|")
    for d in shop.get("by_day", []):
        print(f"| {d['date']} | {fmt_int(d['orders'])} | {fmt_money(d['revenue'])} |")

    subsection("3.4 Top 30 produits vendus")
    print("| # | Produit | Qté | Revenu |")
    print("|---:|---|---:|---:|")
    for i, p in enumerate(shop.get("top_products", []), 1):
        print(f"| {i} | {p['title']} | {fmt_int(p['qty'])} | {fmt_money(p['revenue'])} |")

    if shop.get("ai_referral_orders"):
        subsection("3.5 Commandes attribuées à l'IA (ChatGPT, Perplexity, Claude…)")
        print("| Commande | Source | Référent | Pays | Total |")
        print("|---|---|---|---|---:|")
        for o in shop["ai_referral_orders"]:
            print(f"| {o['id']} | {o['source']} | `{o['referrer']}` | {o['country']} | {fmt_money(o['total'])} |")

    # ----- GSC / SEO -----
    section("4. Search Console — SEO (avril)")

    subsection("4.1 Pays — clics et impressions SEO")
    print("| Pays | Clics | Impressions | CTR | Position moy. |")
    print("|---|---:|---:|---:|---:|")
    for c in gsc.get("by_country", []):
        print(f"| {c['country']} | {fmt_int(c['clicks'])} | {fmt_int(c['impressions'])} | {fmt_pct(c['ctr'], 2)} | {c['position']} |")

    subsection("4.2 Top 50 requêtes")
    print("| # | Requête | Clics | Impressions | CTR | Position |")
    print("|---:|---|---:|---:|---:|---:|")
    for i, q in enumerate(gsc.get("top_queries", []), 1):
        print(f"| {i} | {q['query']} | {fmt_int(q['clicks'])} | {fmt_int(q['impressions'])} | {fmt_pct(q['ctr'], 2)} | {q['position']} |")

    subsection("4.3 Top 50 pages SEO")
    print("| # | Page | Clics | Impressions | CTR | Position |")
    print("|---:|---|---:|---:|---:|---:|")
    for i, p in enumerate(gsc.get("top_pages", []), 1):
        print(f"| {i} | `{p['page']}` | {fmt_int(p['clicks'])} | {fmt_int(p['impressions'])} | {fmt_pct(p['ctr'], 2)} | {p['position']} |")

    # ----- PRODUCT-LEVEL SEO -----
    section("5. SEO produits — état au 30 avril 2026")

    if "position_buckets" in snap:
        b = snap["position_buckets"]
        subsection("5.1 Distribution des positions Google (4 657 produits)")
        print("| Tranche position | # produits |")
        print("|---|---:|")
        print(f"| Top 1-3 (page 1 haut) | {fmt_int(b['top3'])} |")
        print(f"| Top 4-10 (page 1) | {fmt_int(b['top10'])} |")
        print(f"| Top 11-20 (page 2) | {fmt_int(b['top20'])} |")
        print(f"| Top 21-50 (pages 3-5) | {fmt_int(b['top50'])} |")
        print(f"| Au-delà de 50 | {fmt_int(b['beyond'])} |")
        print(f"| Sans position GSC | {fmt_int(b['no_rank'])} |")

    subsection("5.2 Top 30 produits par revenu (avril)")
    rows = top_products(snap["snaps"], db, by="sales", limit=30)
    print("| # | Produit | Vendus | Revenu | Sessions | Impressions | Pos. moy. | Score SEO |")
    print("|---:|---|---:|---:|---:|---:|---:|---:|")
    for i, r in enumerate(rows, 1):
        print(f"| {i} | {r['title']} | {fmt_int(r['sold_30d'])} | {fmt_money(r['revenue_30d'])} | {fmt_int(r['ga4_sessions'])} | {fmt_int(r['gsc_impressions'])} | {r['gsc_position']:.1f} | {r['seo_score']} |")

    subsection("5.3 Top 30 produits par impressions GSC (avril)")
    rows = top_products(snap["snaps"], db, by="impressions", limit=30)
    print("| # | Produit | Impressions | Clics | CTR | Pos. moy. | Vendus | Revenu |")
    print("|---:|---|---:|---:|---:|---:|---:|---:|")
    for i, r in enumerate(rows, 1):
        ctr = (r["gsc_clicks"] / r["gsc_impressions"] * 100) if r["gsc_impressions"] else 0
        print(f"| {i} | {r['title']} | {fmt_int(r['gsc_impressions'])} | {fmt_int(r['gsc_clicks'])} | {fmt_pct(ctr, 2)} | {r['gsc_position']:.1f} | {fmt_int(r['sold_30d'])} | {fmt_money(r['revenue_30d'])} |")

    subsection("5.4 Top 30 produits par sessions GA4")
    rows = top_products(snap["snaps"], db, by="ga4_sessions", limit=30)
    print("| # | Produit | Sessions | Vendus | Revenu | Pos. SEO |")
    print("|---:|---|---:|---:|---:|---:|")
    for i, r in enumerate(rows, 1):
        print(f"| {i} | {r['title']} | {fmt_int(r['ga4_sessions'])} | {fmt_int(r['sold_30d'])} | {fmt_money(r['revenue_30d'])} | {r['gsc_position']:.1f} |")

    # Position movers
    movers = position_movers(db, limit=20)
    if movers["compared"]:
        subsection(f"5.5 Plus gros gains de position (vs 27 mars, {movers['compared']} produits comparés)")
        print("| # | Produit | Pos. mars | Pos. avril | Δ | Impr. avril | Clics avril |")
        print("|---:|---|---:|---:|---:|---:|---:|")
        for i, m in enumerate(movers["gainers"], 1):
            print(f"| {i} | {m['title']} | {m['march_pos']:.1f} | {m['april_pos']:.1f} | +{m['delta']:.1f} | {fmt_int(m['april_impr'])} | {fmt_int(m['april_clicks'])} |")

        subsection("5.6 Plus grosses chutes de position")
        print("| # | Produit | Pos. mars | Pos. avril | Δ | Impr. avril | Clics avril |")
        print("|---:|---|---:|---:|---:|---:|---:|")
        for i, m in enumerate(movers["losers"], 1):
            print(f"| {i} | {m['title']} | {m['march_pos']:.1f} | {m['april_pos']:.1f} | {m['delta']:.1f} | {fmt_int(m['april_impr'])} | {fmt_int(m['april_clicks'])} |")

    # ----- UNIFIED CHANNEL ATTRIBUTION -----
    section("6. ROI réel par canal — GA4 sessions × commandes Shopify")
    print("_Cette table croise les sessions/conversions GA4 (qui contiennent des micro-conversions, des bots résiduels, et du trafic d'attribution dégradée) avec les commandes Shopify réelles (= revenu encaissé). Le `CVR réel` = orders Shopify ÷ sessions GA4. Le `Rev/session` = revenu Shopify réel ÷ sessions._\n")
    rows = unified_attribution(ga4, shop)
    print("| Canal | Sessions GA4 | Conv. GA4 | Revenu GA4 | Commandes Shopify | Revenu Shopify | CVR réel | Rev/session |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        if r["ga4_sessions"] == 0 and r["shop_orders"] == 0:
            continue
        print(
            f"| {r['channel']} | {fmt_int(r['ga4_sessions'])} | {fmt_int(r['ga4_conversions'])} | "
            f"{fmt_money(r['ga4_revenue'])} | {fmt_int(r['shop_orders'])} | {fmt_money(r['shop_revenue'])} | "
            f"{fmt_pct(r['real_cvr_pct'], 2)} | {fmt_money(r['rev_per_session'])} |"
        )

    # ----- NOTES -----
    section("Notes méthodologiques")
    print("- **Période**: 1–30 avril 2026 inclus.")
    print("- **GA4**: dates explicites via API. Le filtre bot natif de GA4 reste actif. Les pays exclus (CN, HK, TW, JP, KR, IN, SG, VN, TH, ID, MY, PH, US, RU) sont marqués 🤖 — Example Store ne livre qu'au Mexique.")
    print("- **Shopify**: commandes filtrées sur `created_at` avril 2026, pays via shippingAddress (fallback billingAddress).")
    print("- **Search Console**: pas de filtre pays au niveau requête/page (limite API), mais breakdown pays disponible en 4.1.")
    print("- **Snapshots produits**: `sold_30d` au 30 avril = ventes des 30 jours glissants ≈ avril complet. Comparaison position mars→avril basée sur snapshot du 27 mars (référence la plus proche disponible).")
    print("- **Position GSC moyenne pondérée**: pondérée par impressions, plus fidèle qu'une moyenne simple.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import contextlib

    db = SessionLocal()
    try:
        # Send all init / fetch stdout (service banner prints, etc.) to stderr
        # so the final stdout stays pure markdown.
        with contextlib.redirect_stdout(sys.stderr):
            print("⏳ Aggregating snapshots...", file=sys.stderr)
            snap = snapshot_aggregates(db)

            print("⏳ Fetching GA4 (April)...", file=sys.stderr)
            gsvc = GoogleApiService()
            try:
                ga4 = ga4_april(gsvc)
            except Exception as e:
                print(f"GA4 error: {e}", file=sys.stderr)
                ga4 = {"error": str(e)}

            print("⏳ Fetching Search Console (April)...", file=sys.stderr)
            try:
                gsc = gsc_april(gsvc)
            except Exception as e:
                print(f"GSC error: {e}", file=sys.stderr)
                gsc = {"error": str(e)}

            print("⏳ Fetching Shopify orders (April)...", file=sys.stderr)
            ssvc = ShopifyService()
            try:
                shop = shopify_april(ssvc)
            except Exception as e:
                print(f"Shopify error: {e}", file=sys.stderr)
                shop = {"error": str(e)}

        print("✓ Rendering report...", file=sys.stderr)
        # render() itself only does pure DB reads — sqlalchemy logging is
        # suppressed at module top — so its stdout is pure markdown.
        render(snap, ga4, gsc, shop, db)
    finally:
        db.close()
