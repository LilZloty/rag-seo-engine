"""
In-memory metrics collector for request tracking.
Tracks request counts, latencies, error rates per endpoint, plus cache
hit/miss counters for the Redis-backed caches.
"""

import time
import uuid
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class MetricsCollector:
    """Collects request + cache metrics in memory."""

    def __init__(self):
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        # Cache hit/miss counters keyed by cache name (e.g. "cache", "llm_cache")
        self._cache_hits: Dict[str, int] = defaultdict(int)
        self._cache_misses: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def record(self, method: str, path: str, status_code: int, duration_ms: float):
        key = f"{method} {path}"
        self._request_counts[key] += 1
        if status_code >= 400:
            self._error_counts[key] += 1
        # Keep last 1000 latencies per endpoint
        latencies = self._latencies[key]
        latencies.append(duration_ms)
        if len(latencies) > 1000:
            self._latencies[key] = latencies[-1000:]

    def record_cache(self, cache_name: str, hit: bool) -> None:
        """Record a cache lookup outcome.

        cache_name should match the module-level cache instance name
        (e.g. 'cache', 'llm_cache', 'serp_cache', 'product_cache').
        """
        if hit:
            self._cache_hits[cache_name] += 1
        else:
            self._cache_misses[cache_name] += 1

    def get_summary(self) -> dict:
        total_requests = sum(self._request_counts.values())
        total_errors = sum(self._error_counts.values())
        uptime = time.time() - self._start_time

        # Top endpoints by request count
        top_endpoints = sorted(
            self._request_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Per-endpoint latency stats
        endpoint_stats = {}
        for key, latencies in self._latencies.items():
            if not latencies:
                continue
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            endpoint_stats[key] = {
                "count": self._request_counts[key],
                "errors": self._error_counts.get(key, 0),
                "avg_ms": round(sum(sorted_lat) / n, 1),
                "p50_ms": round(sorted_lat[n // 2], 1),
                "p95_ms": round(sorted_lat[int(n * 0.95)], 1) if n >= 20 else None,
                "max_ms": round(sorted_lat[-1], 1),
            }

        # Cache stats — hit rate per cache, plus totals
        cache_stats = {}
        cache_names = set(self._cache_hits) | set(self._cache_misses)
        for name in cache_names:
            hits = self._cache_hits.get(name, 0)
            misses = self._cache_misses.get(name, 0)
            total = hits + misses
            cache_stats[name] = {
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_rate_pct": round(hits / total * 100, 1) if total else None,
            }

        return {
            "uptime_seconds": round(uptime),
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": round(total_errors / max(total_requests, 1) * 100, 2),
            "top_endpoints": [{"endpoint": k, "count": v} for k, v in top_endpoints],
            "endpoint_stats": endpoint_stats,
            "cache_stats": cache_stats,
        }

    def get_prometheus(self) -> str:
        """Export metrics in Prometheus text exposition format.

        Emits request counts + p50/p95/max latency per endpoint and cache
        hit/miss counters. Endpoints are labeled by method + path; paths are
        surfaced as-is so high-cardinality dynamic paths (e.g. /products/{id})
        may create many series — fine for a small internal service.
        """
        lines: List[str] = []

        lines.append("# HELP app_uptime_seconds Process uptime in seconds.")
        lines.append("# TYPE app_uptime_seconds counter")
        lines.append(f"app_uptime_seconds {round(time.time() - self._start_time)}")

        lines.append("# HELP app_http_requests_total Total HTTP requests served.")
        lines.append("# TYPE app_http_requests_total counter")
        for key, count in self._request_counts.items():
            method, path = key.split(" ", 1)
            lines.append(
                f'app_http_requests_total{{method="{method}",path="{_escape(path)}"}} {count}'
            )

        lines.append("# HELP app_http_errors_total Total HTTP responses with status >= 400.")
        lines.append("# TYPE app_http_errors_total counter")
        for key, count in self._error_counts.items():
            method, path = key.split(" ", 1)
            lines.append(
                f'app_http_errors_total{{method="{method}",path="{_escape(path)}"}} {count}'
            )

        lines.append("# HELP app_http_latency_ms Per-endpoint latency percentiles in ms.")
        lines.append("# TYPE app_http_latency_ms gauge")
        for key, latencies in self._latencies.items():
            if not latencies:
                continue
            method, path = key.split(" ", 1)
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            p50 = sorted_lat[n // 2]
            p95 = sorted_lat[int(n * 0.95)] if n >= 20 else sorted_lat[-1]
            labels = f'method="{method}",path="{_escape(path)}"'
            lines.append(f'app_http_latency_ms{{{labels},quantile="0.5"}} {round(p50, 2)}')
            lines.append(f'app_http_latency_ms{{{labels},quantile="0.95"}} {round(p95, 2)}')
            lines.append(f'app_http_latency_ms{{{labels},quantile="1.0"}} {round(sorted_lat[-1], 2)}')

        lines.append("# HELP app_cache_hits_total Cache hits by cache name.")
        lines.append("# TYPE app_cache_hits_total counter")
        for name, count in self._cache_hits.items():
            lines.append(f'app_cache_hits_total{{cache="{name}"}} {count}')

        lines.append("# HELP app_cache_misses_total Cache misses by cache name.")
        lines.append("# TYPE app_cache_misses_total counter")
        for name, count in self._cache_misses.items():
            lines.append(f'app_cache_misses_total{{cache="{name}"}} {count}')

        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    """Escape a Prometheus label value per the text exposition format."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# Singleton
metrics = MetricsCollector()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records request metrics and injects a request ID.

    Emits an X-Request-ID response header and attaches the ID to
    request.state.request_id so downstream handlers and structured logs
    can correlate events for a single request.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Accept inbound X-Request-ID (e.g. from a load balancer) or mint one.
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        # Echo the ID back so the client can correlate.
        response.headers["X-Request-ID"] = request_id

        # Normalize path: collapse IDs to {id}
        path = request.url.path
        # Skip static/docs paths
        if not path.startswith(("/docs", "/openapi.json", "/redoc")):
            metrics.record(request.method, path, response.status_code, duration_ms)

        return response
