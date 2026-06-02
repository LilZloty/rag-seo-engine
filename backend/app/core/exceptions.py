"""
Custom exceptions for RAG SEO Engine
"""

from typing import Optional
from fastapi import HTTPException, status


class AppException(Exception):
    """Base exception for Example Store application errors"""
    
    def __init__(
        self,
        message: str,
        code: str = "APP_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class ContentGenerationError(AppException):
    """Raised when content generation fails"""
    
    def __init__(self, message: str, product_id: Optional[str] = None, **kwargs):
        self.product_id = product_id
        details = kwargs.pop("details", {})
        if product_id:
            details["product_id"] = product_id
        super().__init__(
            message=message,
            code="CONTENT_GENERATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )


class LLMProviderError(AppException):
    """Raised when LLM provider fails"""
    
    def __init__(self, message: str, provider: str = "unknown", model: str = "unknown", **kwargs):
        self.provider = provider
        self.model = model
        details = kwargs.pop("details", {})
        details.update({"provider": provider, "model": model})
        super().__init__(
            message=message,
            code="LLM_PROVIDER_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details
        )


class ShopifySyncError(AppException):
    """Raised when Shopify sync operations fail"""
    
    def __init__(self, message: str, operation: str = "sync", **kwargs):
        self.operation = operation
        details = kwargs.pop("details", {})
        details.update({"operation": operation})
        super().__init__(
            message=message,
            code="SHOPIFY_SYNC_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details
        )


class DatabaseError(AppException):
    """Raised when database operations fail"""
    
    def __init__(self, message: str, operation: str = "unknown", **kwargs):
        self.operation = operation
        details = kwargs.pop("details", {})
        details.update({"operation": operation})
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


class ValidationError(AppException):
    """Raised when validation fails"""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        if value:
            details["value"] = value
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class NotFoundError(AppException):
    """Raised when a resource is not found"""
    
    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        details = kwargs.pop("details", {})
        details.update({"resource_type": resource_type, "resource_id": resource_id})
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class RateLimitError(AppException):
    """Raised when API rate limit is exceeded"""
    
    def __init__(self, provider: str = "unknown", retry_after: int = 60, **kwargs):
        details = kwargs.pop("details", {})
        details.update({"provider": provider, "retry_after": retry_after})
        super().__init__(
            message=f"Rate limit exceeded for {provider}. Retry after {retry_after} seconds.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details
        )


class ConfigurationError(AppException):
    """Raised when there's a configuration issue"""
    
    def __init__(self, message: str, setting_name: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if setting_name:
            details["setting_name"] = setting_name
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )
