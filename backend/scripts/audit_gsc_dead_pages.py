"""
Audit dead pages in Google Search Console traffic.

Pulls the top GSC pages for April 2026 (where Google has shown example-store.com in
search results) and checks each URL's current status. Reports 404s sorted by
the impressions they would still capture from Google SERPs.

Run:
    docker exec rag-seo-backend sh -c "cd /app && PYTHONPATH=/app python /tmp/audit_gsc.py"
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

from app.db.session import engine as _engine
_engine.echo = False

import contextlib

import httpx


START_STR = "2026-04-01"
END_STR = "2026-04-30"
ROW_LIMIT = 200  # top N pages to audit


def fetch_top_pages(svc) -> list[dict[str, Any]]:
    from googleapiclient.discovery import build

    service = build("webmasters", "v3", credentials=svc.credentials)
    resp = service.searchanalytics().query(siteUrl=svc.site_url, body={
        "startDate": START_STR,
        "endDate": END_STR,
        "dimensions": ["page"],
        "rowLimit": ROW_LIMIT,
    }).execute()
    return [
        {
            "page": r["keys"][0],
            "clicks": int(r["clicks"]),
            "impressions": int(r["impressions"]),
            "position": round(float(r["position"]), 2),
        }
        for r in resp.get("rows", [])
    ]


def check_url(client: httpx.Client, url: str) -> dict[str, Any]:
    try:
        # Use GET with stream/HEAD-like behaviour. Some servers return wrong
        # codes on HEAD, GET is more reliable.
        r = client.get(url, follow_redirects=False)
        result = {"status": r.status_code, "redirect_to": None}
        if 300 <= r.status_code < 400:
            result["redirect_to"] = r.headers.get("location", "")
            # Follow once to get final status
            try:
                r2 = client.get(url, follow_redirects=True)
                result["final_status"] = r2.status_code
                result["final_url"] = str(r2.url)
            except Exception:
                result["final_status"] = None
        else:
            result["final_status"] = r.status_code
            result["final_url"] = url
        return result
    except Exception as e:
        return {"status": None, "error": str(e), "final_status": None}


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def main():
    with contextlib.redirect_stdout(sys.stderr):
        from app.services.google_api_service import GoogleApiService
        svc = GoogleApiService()
        if not svc.credentials or not svc.site_url:
            print("GSC not configured", file=sys.stderr)
            return 1
        print(f"⏳ Fetching top {ROW_LIMIT} GSC pages for April 2026...", file=sys.stderr)
        pages = fetch_top_pages(svc)
        print(f"   Got {len(pages)} pages", file=sys.stderr)

    if not pages:
        print("No GSC pages returned")
        return 0

    print(f"⏳ Checking HTTP status of {len(pages)} URLs...", file=sys.stderr)
    results: list[dict[str, Any]] = []
    with httpx.Client(
        timeout=15.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Example Store-Audit/1.0)"},
    ) as client:
        for i, p in enumerate(pages):
            chk = check_url(client, p["page"])
            results.append({**p, **chk})
            if (i + 1) % 25 == 0:
                print(f"   {i+1}/{len(pages)}", file=sys.stderr)

    # Bucket by final status
    buckets: dict[int | str, list[dict]] = {}
    for r in results:
        status = r.get("final_status") or r.get("status") or "ERROR"
        buckets.setdefault(status, []).append(r)

    # Output report
    print("# Audit pages mortes — GSC avril 2026")
    print()
    print(f"_Période : {START_STR} → {END_STR}_  ")
    print(f"_Pages analysées : {len(results)} (top {ROW_LIMIT} GSC par impressions)_")
    print()

    print("## Résumé par status")
    print()
    print("| Status | # Pages | Clics avril | Impressions avril |")
    print("|---|---:|---:|---:|")
    for status in sorted(buckets.keys(), key=lambda s: str(s)):
        rows = buckets[status]
        clicks = sum(r["clicks"] for r in rows)
        impr = sum(r["impressions"] for r in rows)
        label = str(status)
        if status == 200:
            label = "✅ 200 OK"
        elif status == 404:
            label = "❌ 404 Not Found"
        elif isinstance(status, int) and 500 <= status < 600:
            label = f"💥 {status} Server Error"
        elif isinstance(status, int) and 300 <= status < 400:
            label = f"↪️ {status} Redirect"
        print(f"| {label} | {fmt_int(len(rows))} | {fmt_int(clicks)} | {fmt_int(impr)} |")
    print()

    # Detailed list of dead pages (404, 5xx, errors)
    dead = []
    for status, rows in buckets.items():
        if status == 200:
            continue
        if isinstance(status, int) and 200 <= status < 400:
            continue
        dead.extend(rows)
    dead.sort(key=lambda r: r["impressions"], reverse=True)

    if dead:
        print("## Pages mortes (404 / 5xx / erreur)")
        print()
        print("_Triées par impressions GSC avril (= trafic perdu)._")
        print()
        print("| # | URL | Status | Clics avril | Impressions avril | Position moy. |")
        print("|---:|---|:---:|---:|---:|---:|")
        for i, r in enumerate(dead, 1):
            status = r.get("final_status") or r.get("status") or "ERROR"
            print(f"| {i} | `{r['page']}` | {status} | {fmt_int(r['clicks'])} | {fmt_int(r['impressions'])} | {r['position']} |")
    else:
        print("## ✅ Aucune page morte détectée parmi le top 200 GSC")
    print()

    # Redirects detected (for informational sanity check)
    redirects = [r for r in results if r.get("status") and 300 <= r["status"] < 400]
    if redirects:
        print(f"## Redirects 301/302 détectés ({len(redirects)})")
        print()
        print("_Pages que Google indexe encore avec leur ancienne URL — Google les reconsolidera._")
        print()
        print("| # | Ancien URL | → Cible | Status final | Clics | Impressions |")
        print("|---:|---|---|:---:|---:|---:|")
        for i, r in enumerate(redirects[:30], 1):
            tgt = r.get("redirect_to") or "?"
            print(f"| {i} | `{r['page']}` | `{tgt[:80]}` | {r.get('final_status')} | {fmt_int(r['clicks'])} | {fmt_int(r['impressions'])} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
