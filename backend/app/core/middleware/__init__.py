"""
FastAPI middleware for RAG SEO Engine
Provides centralized error handling, request logging, and metrics
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.exceptions import (
    AppException,
    ContentGenerationError,
    LLMProviderError,
    ShopifySyncError,
    DatabaseError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import logger


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and timing to all requests"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Add request ID to state
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.4f}s"
            
            # Log request
            logger.info(
                f"{request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Unhandled exception: {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "exception_type": type(e).__name__,
                    "traceback": str(e),
                }
            )
            raise


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware to handle Example Store exceptions consistently"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
            
        except AppException as e:
            logger.warning(
                f"Application exception: {e.code} - {e.message}",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "code": e.code,
                    "status_code": e.status_code,
                    "details": e.details,
                }
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "details": e.details,
                    }
                }
            )
            
        except NotFoundError as e:
            logger.info(
                f"Resource not found: {e.message}",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "code": e.code,
                    "details": e.details,
                }
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "details": e.details,
                    }
                }
            )
            
        except ValueError as e:
            logger.warning(
                f"Validation error: {str(e)}",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "code": "VALIDATION_ERROR",
                    "details": {"field": None, "value": None},
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": str(e),
                        "details": {},
                    }
                }
            )
            
        except Exception as e:
            logger.exception(
                f"Unexpected error: {str(e)}",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "exception_type": type(e).__name__,
                }
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected error occurred",
                        "details": {},
                    }
                }
            )


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track basic metrics"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = 0
        self.error_count = 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        self.request_count += 1
        
        response = await call_next(request)
        
        if response.status_code >= 400:
            self.error_count += 1
        
        return response


def add_exception_handlers(app):
    """Add exception handlers to the FastAPI app"""
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            }
        )
    
    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            }
        )
    
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            }
        )


# Import status for HTTP codes
from fastapi import status
