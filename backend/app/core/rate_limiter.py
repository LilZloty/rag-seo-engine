"""
Rate limiting configuration using slowapi.
Limits are applied per-IP to prevent abuse of expensive endpoints.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": exc.detail,
        },
    )


# Rate limit constants — use these as decorators on endpoints
RATE_CONTENT_GEN = "5/minute"      # Content generation (LLM calls)
RATE_SYNC = "10/minute"            # Data sync endpoints (Shopify, GA4)
RATE_ANALYSIS = "3/minute"         # Analysis endpoints (DataForSEO, SEO scores)
RATE_GENERAL = "60/minute"         # General read endpoints
