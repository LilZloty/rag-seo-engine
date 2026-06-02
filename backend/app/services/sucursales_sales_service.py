"""
Sucursales Sales Service
========================

Fetches `TopProducts` (sales) and `Products/Details` (enrichment) feeds
from the 4 Example Store physical-store nodes (Sucursal 1-4),
joins each entry against Shopify Product, and exposes the result as a single
in-memory snapshot.

Phase 1: manual-refresh, no persistence — see /intelligence/sucursales.
Phase 2 (later): Postgres-backed snapshot + Celery beat.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.product import Product
from app.services.redis_service import cache

logger = logging.getLogger(__name__)

_SNAPSHOT_CACHE_KEY = "sucursales:snapshot"
_SNAPSHOT_TTL = 86400  # 24h — manual refresh is primary invalidation


@dataclass(frozen=True)
class SucursalNode:
    name: str
    host: str
    path: str = "/Apps/Admin/TopProducts"

    @property
    def url(self) -> str:
        return f"https://{self.host}{self.path}"


SUCURSALES: tuple[SucursalNode, ...] = (
    SucursalNode(name="Sucursal 1", host="m107.internal.example"),
    SucursalNode(name="Sucursal 2", host="m207.internal.example"),
    SucursalNode(name="Sucursal 3", host="m407.internal.example"),
    SucursalNode(name="Sucursal 4", host="m507.internal.example"),
)


def get_last_snapshot() -> dict[str, Any] | None:
    return cache.get(_SNAPSHOT_CACHE_KEY)


def _credentials_present() -> bool:
    return bool(settings.SUCURSAL_BASIC_USER and settings.SUCURSAL_BASIC_TOKEN)


async def _fetch_one(client: httpx.AsyncClient, node: SucursalNode) -> dict[str, Any]:
    """Fetch a single sucursal feed. Errors are caught and returned in-band."""
    started = time.monotonic()
    try:
        response = await client.get(
            node.url,
            auth=(settings.SUCURSAL_BASIC_USER, settings.SUCURSAL_BASIC_TOKEN),
            timeout=settings.SUCURSAL_FETCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            return _fail(node, started, "feed returned success=false")
        raw_items = payload.get("data") or []
        items: list[dict[str, Any]] = []
        for entry in raw_items:
            sku = (entry.get("itemName") or "").strip()
            if not sku:
                continue
            try:
                qty = int(entry.get("quantity") or 0)
            except (TypeError, ValueError):
                qty = 0
            # Forward-compatible: pass through any extra metadata the feed adds
            # later (title, marcas, transmisiones — pending enrichment).
            extras = {
                k: v
                for k, v in entry.items()
                if k not in ("itemName", "quantity")
            }
            items.append({"sku": sku, "quantity": qty, "feed_metadata": extras})

        return {
            "name": node.name,
            "host": node.host,
            "ok": True,
            "error": None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "items": items,
        }
    except httpx.HTTPStatusError as exc:
        return _fail(node, started, f"HTTP {exc.response.status_code}")
    except httpx.RequestError as exc:
        return _fail(node, started, f"request error: {exc.__class__.__name__}")
    except ValueError:
        return _fail(node, started, "invalid JSON response")
    except Exception as exc:
        logger.exception("Unexpected error fetching sucursal %s", node.name)
        return _fail(node, started, f"unexpected: {exc.__class__.__name__}")


def _fail(node: SucursalNode, started: float, message: str) -> dict[str, Any]:
    return {
        "name": node.name,
        "host": node.host,
        "ok": False,
        "error": message,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "items": [],
    }


async def _fetch_all() -> list[dict[str, Any]]:
    """Parallel fetch all 4 sucursales — one slow node never blocks the rest."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        return await asyncio.gather(
            *(_fetch_one(client, node) for node in SUCURSALES)
        )


# ---------------------------------------------------------------------------
# Products/Details enrichment (title, OEM, makers, transmissions)
# ---------------------------------------------------------------------------
# Endpoint is per-host but product details don't vary by sucursal, so we
# call ONE node. Same Basic auth. Batch limit: 50 items per request.

_DETAILS_PATH = "/Apps/Products/Details"
_DETAILS_CONCURRENCY = 5  # max concurrent batches against IIS


async def _fetch_details_batch(
    client: httpx.AsyncClient,
    node: SucursalNode,
    skus: list[str],
) -> dict[str, dict[str, Any]]:
    url = f"https://{node.host}{_DETAILS_PATH}"
    params = {
        "codeCountry": settings.SUCURSAL_COUNTRY_CODE,
        "items": ",".join(skus),
    }
    try:
        response = await client.get(
            url,
            params=params,
            auth=(settings.SUCURSAL_BASIC_USER, settings.SUCURSAL_BASIC_TOKEN),
            timeout=settings.SUCURSAL_FETCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            logger.warning("Details batch returned success=false on %s", node.host)
            return {}
        result: dict[str, dict[str, Any]] = {}
        for entry in payload.get("data") or []:
            sku = (entry.get("item") or "").strip()
            if not sku:
                continue
            result[sku] = {
                "title": entry.get("title"),
                "description": entry.get("description"),
                "oem": entry.get("OEM"),
                "makers": entry.get("makers"),
                "transmissions": entry.get("transmissions"),
                "vehicules": entry.get("vehicules"),
            }
        return result
    except Exception as exc:
        logger.warning("Details batch failed on %s: %s", node.host, exc)
        return {}


async def _fetch_all_details(skus: set[str]) -> dict[str, dict[str, Any]]:
    """Batch-fetch product details for all SKUs from one available node.

    Tries m107 (Sucursal 1) first; if an entire batch sequence fails, falls back
    to the next node. Uses a semaphore to limit concurrent requests.
    """
    if not skus:
        return {}
    sku_list = sorted(skus)
    batch_size = settings.SUCURSAL_DETAILS_BATCH_SIZE
    batches = [sku_list[i : i + batch_size] for i in range(0, len(sku_list), batch_size)]
    logger.info(
        "Fetching product details: %d unique SKUs in %d batches of %d",
        len(sku_list), len(batches), batch_size,
    )

    sem = asyncio.Semaphore(_DETAILS_CONCURRENCY)

    async def _run_batch(client: httpx.AsyncClient, node: SucursalNode, batch: list[str]):
        async with sem:
            return await _fetch_details_batch(client, node, batch)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for node in SUCURSALES:
            results = await asyncio.gather(
                *(_run_batch(client, node, b) for b in batches)
            )
            merged: dict[str, dict[str, Any]] = {}
            for r in results:
                merged.update(r)
            if merged:
                logger.info(
                    "Details enrichment: %d/%d SKUs resolved via %s",
                    len(merged), len(sku_list), node.host,
                )
                return merged
            logger.warning("Details: 0 results from %s — trying next node", node.host)

    logger.warning("Details enrichment: all nodes failed, proceeding without details")
    return {}


def _enrich_with_products(
    db: Session,
    sucursal_results: list[dict[str, Any]],
    details_by_sku: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Join each sucursal's items against Product.sku and internal Details.

    Returns (enriched_sucursales, unmatched_aggregate).
    """
    all_skus = {item["sku"] for s in sucursal_results for item in s["items"] if item["sku"]}
    products_by_sku: dict[str, Product] = {}
    if all_skus:
        rows = (
            db.query(Product)
            .filter(Product.sku.in_(all_skus))
            .all()
        )
        for row in rows:
            if row.sku:
                products_by_sku[row.sku] = row

    enriched: list[dict[str, Any]] = []
    unmatched_index: dict[str, dict[str, Any]] = {}

    for sucursal in sucursal_results:
        matched_count = 0
        unmatched_count = 0
        total_units = 0
        items_out: list[dict[str, Any]] = []

        for item in sucursal["items"]:
            sku = item["sku"]
            qty = item["quantity"]
            total_units += qty
            product = products_by_sku.get(sku)
            detail = details_by_sku.get(sku)

            base = {
                "sku": sku,
                "quantity": qty,
                "internal_details": detail,
                "feed_metadata": item.get("feed_metadata") or {},
            }
            if product:
                matched_count += 1
                base.update({
                    "matched": True,
                    "product": {
                        "id": product.id,
                        "shopify_id": product.shopify_id,
                        "title": product.title,
                        "handle": product.handle,
                        "vendor": product.vendor,
                        "transmission_code": product.transmission_code,
                        "product_type": product.product_type,
                    },
                })
            else:
                unmatched_count += 1
                base.update({"matched": False, "product": None})
                bucket = unmatched_index.setdefault(sku, {
                    "sku": sku,
                    "total_quantity": 0,
                    "by_sucursal": {},
                    "internal_details": detail,
                })
                bucket["total_quantity"] += qty
                bucket["by_sucursal"][sucursal["name"]] = (
                    bucket["by_sucursal"].get(sucursal["name"], 0) + qty
                )

            items_out.append(base)

        enriched.append({
            **sucursal,
            "items": items_out,
            "total_units": total_units,
            "item_count": len(items_out),
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
        })

    unmatched_aggregate = sorted(
        unmatched_index.values(),
        key=lambda x: x["total_quantity"],
        reverse=True,
    )
    return enriched, unmatched_aggregate


# ---------------------------------------------------------------------------
# Opportunity scoring — cross-signal analysis
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GSC query demand analysis
# ---------------------------------------------------------------------------

def _fetch_search_demand(
    transmission_codes: set[str],
    maker_names: set[str],
    trans_online: dict[str, dict[str, Any]],
    trans_store_qty: dict[str, int],
    maker_store_qty: dict[str, int],
) -> dict[str, Any]:
    """Pull GSC queries and match against transmission codes + brands.

    Returns demand signals grouped by transmission and maker, plus a
    unified `unmet_demand` list sorted by impressions.
    """
    try:
        from app.services.google_api_service import GoogleApiService
        gsc = GoogleApiService()
        queries = gsc.get_search_console_data(days=90)
    except Exception as exc:
        logger.warning("GSC fetch for demand analysis failed: %s", exc)
        return {
            "total_queries_analyzed": 0,
            "by_transmission": {},
            "by_maker": {},
            "unmet_demand": [],
        }

    if not queries:
        return {
            "total_queries_analyzed": 0,
            "by_transmission": {},
            "by_maker": {},
            "unmet_demand": [],
        }

    # Build regex patterns for word-boundary matching (min 3 chars to avoid noise)
    trans_patterns: list[tuple[re.Pattern, str]] = []
    for tc in transmission_codes:
        if len(tc) >= 3:
            trans_patterns.append((re.compile(rf"\b{re.escape(tc.lower())}\b"), tc))

    maker_patterns: list[tuple[re.Pattern, str]] = []
    for m in maker_names:
        if len(m) >= 3:
            maker_patterns.append((re.compile(rf"\b{re.escape(m.lower())}\b"), m))

    by_transmission: dict[str, dict[str, Any]] = {}
    by_maker: dict[str, dict[str, Any]] = {}

    for q in queries:
        qt = q["query"].lower()
        imp = q.get("impressions", 0)
        clk = q.get("clicks", 0)

        for pat, tc in trans_patterns:
            if pat.search(qt):
                bucket = by_transmission.setdefault(tc, {
                    "impressions": 0, "clicks": 0, "top_queries": [],
                })
                bucket["impressions"] += imp
                bucket["clicks"] += clk
                if len(bucket["top_queries"]) < 5:
                    bucket["top_queries"].append(q["query"])

        for pat, m in maker_patterns:
            if pat.search(qt):
                bucket = by_maker.setdefault(m, {
                    "impressions": 0, "clicks": 0, "top_queries": [],
                })
                bucket["impressions"] += imp
                bucket["clicks"] += clk
                if len(bucket["top_queries"]) < 5:
                    bucket["top_queries"].append(q["query"])

    # Build unified "unmet demand" list — gaps with search demand
    unmet: list[dict[str, Any]] = []

    for tc, demand in by_transmission.items():
        online = trans_online.get(tc, {})
        shopify_count = online.get("shopify_product_count", 0)
        if demand["impressions"] < 10:
            continue
        unmet.append({
            "type": "transmission",
            "code": tc,
            "impressions": demand["impressions"],
            "clicks": demand["clicks"],
            "top_queries": demand["top_queries"],
            "shopify_products": shopify_count,
            "in_store_qty": trans_store_qty.get(tc, 0),
            "gap": shopify_count == 0,
        })

    for m, demand in by_maker.items():
        if demand["impressions"] < 10:
            continue
        unmet.append({
            "type": "maker",
            "code": m,
            "impressions": demand["impressions"],
            "clicks": demand["clicks"],
            "top_queries": demand["top_queries"],
            "shopify_products": 0,
            "in_store_qty": maker_store_qty.get(m, 0),
            "gap": True,
        })

    unmet.sort(key=lambda x: x["impressions"], reverse=True)

    return {
        "total_queries_analyzed": len(queries),
        "by_transmission": by_transmission,
        "by_maker": by_maker,
        "unmet_demand": unmet,
    }


_NOISE_SKUS = {"TRANSPORTE", "DVI", "DCVT", "SERVICIO", "ENVIO", "FLETE"}

_MAKE_ALIASES: dict[str, str] = {
    "MERCEDES-BENZ": "MERCEDES",
    "VW": "VOLKSWAGEN",
    "CHEVY": "CHEVROLET",
}

# Curated aliases for transmissions the internal system names differently than Shopify.
# Only includes cases where parts are genuinely interchangeable.
_KNOWN_TRANS_ALIASES: dict[str, str] = {
    # Ford
    "AXODE": "AX4S", "AXOD": "AX4S", "ATX": "AX4S",
    "CD4E": "4F27E",
    "4R100": "E4OD",
    # GM
    "TH350C": "TH350",
    "TH250C": "TH250",
    # Chrysler / Dodge
    "A670": "A604", "A470": "A604", "A413": "A604",
    "44RH": "A500", "A999": "A500",
    "A904": "A500",
    # Toyota / Aisin
    "A340H": "A340E", "A340F": "A340E",
    "A341E": "A340E", "A343E": "A340E", "A343F": "A340E",
}


def _build_transmission_aliases(
    details_by_sku: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Build alias → canonical code map from Details otherCodes + suffix stripping.

    Example mappings produced:
      "4L60" → "TH700"  (via otherCodes)
      "TH700-R4" → "TH700"  (via suffix stripping)
    """
    alias_map: dict[str, str] = {}
    for detail in details_by_sku.values():
        for t in detail.get("transmissions") or []:
            name = t.get("name")
            if not name:
                continue
            for other in t.get("otherCodes") or []:
                if other and other != name:
                    alias_map[other] = name
            if "-" in name:
                base = name.rsplit("-", 1)[0]
                if base and base != name:
                    alias_map.setdefault(name, base)
    alias_map.update(_KNOWN_TRANS_ALIASES)
    return alias_map


def _resolve_transmission(
    code: str,
    alias_map: dict[str, str],
    trans_online: dict[str, dict[str, Any]],
) -> str | None:
    """Resolve a transmission code to one that exists in trans_online.

    Tries: exact → alias → suffix-stripped base.
    """
    if code in trans_online:
        return code
    mapped = alias_map.get(code)
    if mapped and mapped in trans_online:
        return mapped
    if "-" in code:
        base = code.rsplit("-", 1)[0]
        if base in trans_online:
            return base
    return None


def _compute_opportunities(
    db: Session,
    enriched_sucursales: list[dict[str, Any]],
    unmatched_aggregate: list[dict[str, Any]],
    details_by_sku: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Cross sucursal sales with GSC/GA4/Shopify data to find opportunities.

    Returns (opportunities, transmission_gaps).
    """
    # --- Step 1: aggregate per-SKU stats across all sucursales ---
    sku_agg: dict[str, dict[str, Any]] = {}
    for suc in enriched_sucursales:
        if not suc["ok"]:
            continue
        for item in suc["items"]:
            sku = item["sku"]
            agg = sku_agg.setdefault(sku, {
                "total_qty": 0,
                "sucursal_count": 0,
                "sucursales": [],
                "matched": item["matched"],
                "product": item.get("product"),
                "internal_details": item.get("internal_details"),
            })
            if item["quantity"] > 0:
                agg["total_qty"] += item["quantity"]
                if suc["name"] not in agg["sucursales"]:
                    agg["sucursales"].append(suc["name"])
                    agg["sucursal_count"] = len(agg["sucursales"])

    # --- Step 2: build transmission → online-demand map from Product DB ---
    from sqlalchemy import func as sa_func, text as sa_text

    trans_stats_rows = (
        db.query(
            Product.transmission_code,
            sa_func.sum(Product.gsc_impressions).label("impressions"),
            sa_func.sum(Product.gsc_clicks).label("clicks"),
            sa_func.count(Product.id).label("product_count"),
            sa_func.sum(Product.sold_90d).label("sold_90d"),
        )
        .filter(Product.transmission_code.isnot(None))
        .group_by(Product.transmission_code)
        .all()
    )
    trans_online: dict[str, dict[str, Any]] = {}
    for row in trans_stats_rows:
        trans_online[row.transmission_code] = {
            "gsc_impressions": row.impressions or 0,
            "gsc_clicks": row.clicks or 0,
            "shopify_product_count": row.product_count or 0,
            "shopify_sold_90d": row.sold_90d or 0,
        }

    # Also count products by secondary codes from transmission_codes JSON array.
    # Many products list multiple compatible codes (e.g. 4L60E + 4L65E + 4L70E).
    try:
        _multi_rows = db.execute(sa_text("""
            SELECT code,
                   count(DISTINCT p.id) AS cnt,
                   coalesce(sum(p.gsc_impressions), 0) AS imp,
                   coalesce(sum(p.gsc_clicks), 0) AS clk,
                   coalesce(sum(p.sold_90d), 0) AS sold
            FROM products p,
                 json_array_elements_text(p.transmission_codes) AS code
            WHERE p.transmission_codes IS NOT NULL
            GROUP BY code
        """)).fetchall()
        for mrow in _multi_rows:
            mcode, mcnt, mimp, mclk, msold = mrow
            if mcode not in trans_online:
                trans_online[mcode] = {
                    "gsc_impressions": mimp or 0,
                    "gsc_clicks": mclk or 0,
                    "shopify_product_count": mcnt or 0,
                    "shopify_sold_90d": msold or 0,
                }
            elif mcnt > trans_online[mcode]["shopify_product_count"]:
                trans_online[mcode]["shopify_product_count"] = mcnt
    except Exception as exc:
        logger.warning("Multi-code transmission query failed: %s", exc)

    # Build alias map from internal Details otherCodes
    alias_map = _build_transmission_aliases(details_by_sku)

    # Count how many SUCURSAL SKUs belong to each transmission
    trans_store_skus: dict[str, set[str]] = {}
    # Also count matched SKUs per transmission (these ARE on Shopify even if
    # their Product.transmission_code doesn't match — same logic as the
    # drill-down endpoint uses)
    trans_matched_skus: dict[str, set[str]] = {}
    for sku, agg in sku_agg.items():
        detail = agg.get("internal_details") or {}
        for t in detail.get("transmissions") or []:
            tcode = t.get("name")
            if tcode:
                trans_store_skus.setdefault(tcode, set()).add(sku)
                if agg["matched"]:
                    trans_matched_skus.setdefault(tcode, set()).add(sku)

    # Load matched products for SEO/conversion analysis
    matched_skus = [sku for sku, agg in sku_agg.items() if agg["matched"]]
    products_by_sku: dict[str, Product] = {}
    if matched_skus:
        for row in db.query(Product).filter(Product.sku.in_(matched_skus)).all():
            if row.sku:
                products_by_sku[row.sku] = row

    # --- Step 3: score opportunities ---
    opportunities: list[dict[str, Any]] = []

    for sku, agg in sku_agg.items():
        if sku.upper() in _NOISE_SKUS or agg["total_qty"] < 5:
            continue

        detail = agg.get("internal_details") or {}
        trans_codes = [t["name"] for t in (detail.get("transmissions") or []) if t.get("name")]
        best_trans_impressions = 0
        best_trans_code = None
        best_trans_shopify_count = 0
        for tc in trans_codes:
            resolved = _resolve_transmission(tc, alias_map, trans_online)
            ts = trans_online.get(resolved, {}) if resolved else {}
            if ts.get("gsc_impressions", 0) > best_trans_impressions:
                best_trans_impressions = ts["gsc_impressions"]
                best_trans_code = tc
                best_trans_shopify_count = ts.get("shopify_product_count", 0)

        if not agg["matched"]:
            # --- PUBLISH CANDIDATE ---
            if agg["total_qty"] < 10:
                continue
            reasons = []
            reasons.append(
                f"Sells {agg['total_qty']:,} units across {agg['sucursal_count']} "
                f"sucursal{'es' if agg['sucursal_count'] > 1 else ''} (90d)"
            )
            if best_trans_code and best_trans_impressions > 0:
                reasons.append(
                    f"Fits {best_trans_code} — existing products get "
                    f"{best_trans_impressions:,} GSC impressions from "
                    f"{best_trans_shopify_count} products on Shopify"
                )
            oem = detail.get("oem")
            if oem:
                reasons.append(f"OEM codes: {', '.join(oem[:5])}")
            makers = detail.get("makers")
            if makers:
                reasons.append(f"Compatible: {', '.join(makers[:6])}")
            if trans_codes and not best_trans_impressions:
                reasons.append(f"Transmissions: {', '.join(trans_codes[:4])}")

            score = (
                min(agg["total_qty"] / 100, 1.0) * 30
                + (agg["sucursal_count"] / 4) * 20
                + min(best_trans_impressions / 5000, 1.0) * 30
                + (len(trans_codes) > 0) * 10
                + (bool(oem)) * 10
            )

            opportunities.append({
                "sku": sku,
                "type": "publish_candidate",
                "score": round(min(score, 100)),
                "title": detail.get("title") or sku,
                "in_store_qty": agg["total_qty"],
                "cross_sucursal_count": agg["sucursal_count"],
                "reasons": reasons,
                "action": "Publish on Shopify",
                "internal_details": detail or None,
                "shopify_product": None,
                "signals": {
                    "best_transmission": best_trans_code,
                    "transmission_gsc_impressions": best_trans_impressions,
                    "transmission_shopify_products": best_trans_shopify_count,
                },
            })
        else:
            # --- MATCHED SKU: check for SEO blind spot or conversion gap ---
            product = products_by_sku.get(sku)
            if not product:
                continue

            shopify_sold = product.sold_90d or 0
            gsc_imp = product.gsc_impressions or 0
            ga4_sess = product.ga4_sessions or 0
            bounce = product.ga4_bounce_rate or 0
            seo_sc = product.seo_score or 0
            img_count = product.image_count or 0
            store_qty = agg["total_qty"]

            # SEO BLIND SPOT: sells in stores but invisible online
            if store_qty >= 20 and gsc_imp < 200 and shopify_sold < (store_qty * 0.1):
                reasons = []
                reasons.append(
                    f"Sells {store_qty:,} in stores but only {shopify_sold} online (90d)"
                )
                reasons.append(
                    f"Only {gsc_imp:,} GSC impressions — nearly invisible in search"
                )
                if seo_sc < 50:
                    reasons.append(f"SEO score: {seo_sc}/100 — needs optimization")
                if img_count < 2:
                    reasons.append(f"Only {img_count} product image{'s' if img_count != 1 else ''}")
                ratio = store_qty / max(shopify_sold, 1)
                score = (
                    min(ratio / 20, 1.0) * 35
                    + (1 - min(gsc_imp / 500, 1.0)) * 35
                    + (1 - seo_sc / 100) * 20
                    + min(store_qty / 100, 1.0) * 10
                )
                opportunities.append({
                    "sku": sku,
                    "type": "seo_blind_spot",
                    "score": round(min(score, 100)),
                    "title": product.title,
                    "in_store_qty": store_qty,
                    "cross_sucursal_count": agg["sucursal_count"],
                    "reasons": reasons,
                    "action": "Optimize SEO",
                    "internal_details": detail or None,
                    "shopify_product": {
                        "handle": product.handle,
                        "sold_90d": shopify_sold,
                        "gsc_impressions": gsc_imp,
                        "gsc_clicks": product.gsc_clicks or 0,
                        "seo_score": seo_sc,
                    },
                    "signals": {
                        "store_to_online_ratio": round(ratio, 1),
                        "best_transmission": product.transmission_code,
                    },
                })

            # CONVERSION GAP: gets traffic but doesn't convert
            elif ga4_sess >= 30 and shopify_sold < max(ga4_sess * 0.01, 1) and store_qty >= 15:
                conv_rate = shopify_sold / max(ga4_sess, 1)
                reasons = []
                reasons.append(
                    f"{ga4_sess:,} visits but only {shopify_sold} sales (90d) — "
                    f"{conv_rate:.1%} conversion"
                )
                reasons.append(
                    f"Sells {store_qty:,} in stores — demand is proven"
                )
                if bounce > 50:
                    reasons.append(f"Bounce rate: {bounce:.0f}%")
                if img_count < 2:
                    reasons.append(f"Only {img_count} product image{'s' if img_count != 1 else ''}")
                score = (
                    min(ga4_sess / 200, 1.0) * 25
                    + (1 - min(conv_rate / 0.02, 1.0)) * 35
                    + min(bounce / 80, 1.0) * 20
                    + min(store_qty / 100, 1.0) * 20
                )
                opportunities.append({
                    "sku": sku,
                    "type": "conversion_gap",
                    "score": round(min(score, 100)),
                    "title": product.title,
                    "in_store_qty": store_qty,
                    "cross_sucursal_count": agg["sucursal_count"],
                    "reasons": reasons,
                    "action": "Improve product page",
                    "internal_details": detail or None,
                    "shopify_product": {
                        "handle": product.handle,
                        "sold_90d": shopify_sold,
                        "ga4_sessions": ga4_sess,
                        "ga4_bounce_rate": round(bounce, 1),
                        "image_count": img_count,
                    },
                    "signals": {
                        "conversion_rate": round(conv_rate, 4),
                        "best_transmission": product.transmission_code,
                    },
                })

    opportunities.sort(key=lambda x: x["score"], reverse=True)

    # --- Step 4: transmission-level gaps (with alias resolution) ---
    transmission_gaps: list[dict[str, Any]] = []
    for tcode, store_skus in trans_store_skus.items():
        resolved = _resolve_transmission(tcode, alias_map, trans_online)
        online = trans_online.get(resolved, {}) if resolved else {}
        db_count = online.get("shopify_product_count", 0)
        matched_skus_for_code = trans_matched_skus.get(tcode, set())
        matched_count = len(matched_skus_for_code)
        shopify_count = max(db_count, matched_count)
        store_count = len(store_skus)
        if store_count < 3:
            continue
        coverage = shopify_count / max(store_count, 1)
        if coverage >= 0.8:
            continue
        store_total_qty = sum(sku_agg.get(s, {}).get("total_qty", 0) for s in store_skus)
        gsc_imp = online.get("gsc_impressions", 0)
        if not gsc_imp and matched_skus_for_code:
            for ms in matched_skus_for_code:
                p = products_by_sku.get(ms)
                if p:
                    gsc_imp += p.gsc_impressions or 0
        gap_score = round(
            min(store_total_qty / 500, 1.0) * 30
            + (1 - coverage) * 40
            + min(gsc_imp / 5000, 1.0) * 30
        )
        transmission_gaps.append({
            "transmission_code": tcode,
            "resolved_code": resolved,
            "in_store_skus": store_count,
            "shopify_products": shopify_count,
            "coverage": round(coverage, 2),
            "total_in_store_qty": store_total_qty,
            "gsc_impressions": gsc_imp,
            "gap_score": min(gap_score, 100),
        })
    transmission_gaps.sort(key=lambda x: x["gap_score"], reverse=True)

    return opportunities, transmission_gaps


async def refresh_snapshot(db: Session) -> dict[str, Any]:
    """Hit all 4 sucursales, enrich with Product join, store + return the snapshot."""
    if not _credentials_present():
        snapshot = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0,
            "error": "SUCURSAL_BASIC_USER / SUCURSAL_BASIC_TOKEN not configured in backend/.env",
            "sucursales": [],
            "unmatched_aggregate": [],
            "summary": {
                "total_units": 0,
                "matched_skus": 0,
                "unmatched_skus": 0,
                "sucursales_ok": 0,
                "sucursales_failed": len(SUCURSALES),
            },
        }
        return snapshot

    started = time.monotonic()

    # Step 1: fetch sales from all 4 sucursales in parallel
    raw_results = await _fetch_all()

    # Step 2: collect unique SKUs, then batch-fetch product details
    all_skus = {
        item["sku"]
        for s in raw_results
        for item in s["items"]
        if item["sku"]
    }
    details_by_sku = await _fetch_all_details(all_skus)

    # Step 3: join with Shopify Product DB + internal details
    enriched, unmatched_aggregate = _enrich_with_products(
        db, raw_results, details_by_sku
    )

    # Step 4: cross-signal opportunity analysis
    opportunities, transmission_gaps = _compute_opportunities(
        db, enriched, unmatched_aggregate, details_by_sku
    )

    # Step 5: GSC query demand analysis — find search demand by transmission + brand
    all_trans_codes: set[str] = set()
    all_makers: set[str] = set()
    trans_store_qty: dict[str, int] = {}
    maker_store_qty: dict[str, int] = {}
    for detail in details_by_sku.values():
        for t in detail.get("transmissions") or []:
            tname = t.get("name")
            if tname:
                all_trans_codes.add(tname)
        for m in detail.get("makers") or []:
            if m:
                all_makers.add(m)

    # Aggregate in-store qty per transmission and maker
    for suc in enriched:
        for item in suc.get("items", []):
            d = item.get("internal_details") or {}
            qty = item.get("quantity", 0)
            for t in d.get("transmissions") or []:
                tname = t.get("name")
                if tname:
                    trans_store_qty[tname] = trans_store_qty.get(tname, 0) + qty
            for m in d.get("makers") or []:
                if m:
                    maker_store_qty[m] = maker_store_qty.get(m, 0) + qty

    # Build trans_online for the GSC demand function (reuse from opportunities)
    from sqlalchemy import func as sa_func, text as sa_text
    _trans_rows = (
        db.query(
            Product.transmission_code,
            sa_func.count(Product.id).label("cnt"),
        )
        .filter(Product.transmission_code.isnot(None))
        .group_by(Product.transmission_code)
        .all()
    )
    _trans_product_counts = {r.transmission_code: r.cnt for r in _trans_rows}
    try:
        _multi_cnt = db.execute(sa_text("""
            SELECT code, count(DISTINCT p.id) AS cnt
            FROM products p, json_array_elements_text(p.transmission_codes) AS code
            WHERE p.transmission_codes IS NOT NULL
            GROUP BY code
        """)).fetchall()
        for mcode, mcnt in _multi_cnt:
            if mcnt > _trans_product_counts.get(mcode, 0):
                _trans_product_counts[mcode] = mcnt
    except Exception:
        pass

    # Count products per vehicle make (from cached_vehicle_fitments, not vendor).
    # Fitment entries store make as a JSON array: {"make": ["CHEVROLET"], ...}
    _fitment_rows = (
        db.query(Product.id, Product.cached_vehicle_fitments)
        .filter(Product.cached_vehicle_fitments.isnot(None))
        .all()
    )
    maker_product_counts: dict[str, int] = {}
    for _pid, _fitments in _fitment_rows:
        _seen: set[str] = set()
        for _f in (_fitments or []):
            _make_raw = _f.get("make") or []
            if isinstance(_make_raw, str):
                _make_raw = [_make_raw]
            for _m in _make_raw:
                _make = (str(_m) if _m else "").strip().upper()
                _make = _MAKE_ALIASES.get(_make, _make)
                if _make and _make != "UNIVERSAL" and _make not in _seen:
                    _seen.add(_make)
                    maker_product_counts[_make] = maker_product_counts.get(_make, 0) + 1

    # Bridge brands via transmission codes from internal details (primary source).
    # Only 3% of products have fitments — the trans-code bridge covers the full catalog.
    _brand_trans_sets: dict[str, set[str]] = {}
    for detail in details_by_sku.values():
        _dtrans = {t["name"] for t in (detail.get("transmissions") or []) if t.get("name")}
        for m in (detail.get("makers") or []):
            if m:
                _mk = _MAKE_ALIASES.get(m.upper(), m.upper())
                _brand_trans_sets.setdefault(_mk, set()).update(_dtrans)
    _all_bridge_trans: set[str] = set()
    for bt in _brand_trans_sets.values():
        _all_bridge_trans.update(bt)
    if _all_bridge_trans:
        _trans_to_pids: dict[str, set[str]] = {}
        _bridge_rows = (
            db.query(Product.id, Product.transmission_code)
            .filter(Product.transmission_code.in_(_all_bridge_trans))
            .all()
        )
        for _br_pid, _br_tc in _bridge_rows:
            _trans_to_pids.setdefault(_br_tc, set()).add(_br_pid)
        try:
            _multi_bridge = db.execute(sa_text("""
                SELECT p.id, code
                FROM products p, json_array_elements_text(p.transmission_codes) AS code
                WHERE p.transmission_codes IS NOT NULL
            """)).fetchall()
            for _mb_pid, _mb_tc in _multi_bridge:
                if _mb_tc in _all_bridge_trans:
                    _trans_to_pids.setdefault(_mb_tc, set()).add(_mb_pid)
        except Exception:
            pass
        for bk, bt in _brand_trans_sets.items():
            _pids: set[str] = set()
            for tc in bt:
                _pids.update(_trans_to_pids.get(tc, set()))
            if len(_pids) > maker_product_counts.get(bk, 0):
                maker_product_counts[bk] = len(_pids)

    # Re-derive trans_online quickly for the demand function
    _trans_online_for_demand = {
        tc: {"shopify_product_count": cnt}
        for tc, cnt in _trans_product_counts.items()
    }

    search_demand = _fetch_search_demand(
        all_trans_codes, all_makers,
        _trans_online_for_demand, trans_store_qty, maker_store_qty,
    )

    # Enrich maker entries with Shopify product count
    for entry in search_demand.get("unmet_demand", []):
        if entry["type"] == "maker":
            _norm = _MAKE_ALIASES.get(entry["code"].upper(), entry["code"].upper())
            entry["shopify_products"] = maker_product_counts.get(_norm, 0)
            entry["gap"] = entry["shopify_products"] == 0

    # Enrich transmission_gaps with GSC query impressions
    demand_by_trans = search_demand.get("by_transmission", {})
    for gap in transmission_gaps:
        td = demand_by_trans.get(gap["transmission_code"], {})
        gap["query_impressions"] = td.get("impressions", 0)
        gap["query_clicks"] = td.get("clicks", 0)
        gap["top_queries"] = td.get("top_queries", [])

    sucursales_ok = sum(1 for s in enriched if s["ok"])
    details_resolved = sum(1 for v in details_by_sku.values() if v)
    opp_by_type = {}
    for opp in opportunities:
        opp_by_type[opp["type"]] = opp_by_type.get(opp["type"], 0) + 1

    snapshot: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "error": None,
        "sucursales": enriched,
        "unmatched_aggregate": unmatched_aggregate,
        "opportunities": opportunities,
        "transmission_gaps": transmission_gaps,
        "search_demand": search_demand,
        "summary": {
            "total_units": sum(s["total_units"] for s in enriched),
            "matched_skus": sum(s["matched_count"] for s in enriched),
            "unmatched_skus": len(unmatched_aggregate),
            "sucursales_ok": sucursales_ok,
            "sucursales_failed": len(SUCURSALES) - sucursales_ok,
            "details_resolved": details_resolved,
            "details_total_skus": len(all_skus),
            "opportunities_count": len(opportunities),
            "opportunities_by_type": opp_by_type,
            "transmission_gaps_count": len(transmission_gaps),
            "search_demand_queries": search_demand.get("total_queries_analyzed", 0),
            "unmet_demand_count": len(search_demand.get("unmet_demand", [])),
        },
    }
    cache.set(_SNAPSHOT_CACHE_KEY, snapshot, ttl=_SNAPSHOT_TTL)
    return snapshot
