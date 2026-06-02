"""
Settings API endpoints for application configuration.

Provides endpoints for:
- Listing available LLM providers
- Getting/setting active LLM provider
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from typing import Optional
from pydantic import BaseModel

router = APIRouter()


class LLMProviderInfo(BaseModel):
    """Information about an LLM provider."""
    name: str
    display_name: str
    model: str
    factory_provider: str  # Backend provider class name for LLMProviderFactory
    configured: bool
    active: bool


class SetProviderRequest(BaseModel):
    """Request to set active LLM provider."""
    provider: str


# Available LLM providers with their configuration
# factory_provider maps UI entries to the backend provider class (LLMProviderFactory name)
LLM_PROVIDERS = {
    "grok": {
        "display_name": "Grok 4.3 (X.AI)",
        "model_setting": "XAI_MODEL",
        "api_key_setting": "XAI_API_KEY",
        "default_model": "grok-4.3",
        "factory_provider": "grok",
    },
    "anthropic": {
        "display_name": "Claude (Anthropic)",
        "model_setting": "ANTHROPIC_MODEL",
        "api_key_setting": "ANTHROPIC_API_KEY",
        "default_model": "claude-opus-4-5",
        "factory_provider": "anthropic",
    },
    "kimi": {
        "display_name": "Kimi (Moonshot)",
        "model_setting": "KIMI_MODEL",
        "api_key_setting": "KIMI_API_KEY",
        "default_model": "kimi-k2.5",
        "factory_provider": "kimi",
    },
    "mistral": {
        "display_name": "Mistral AI",
        "model_setting": "MISTRAL_MODEL",
        "api_key_setting": "MISTRAL_API_KEY",
        "default_model": "mistral-large-latest",
        "factory_provider": "mistral",
    },
    "minimax": {
        "display_name": "MiniMax",
        "model_setting": "MINIMAX_MODEL",
        "api_key_setting": "MINIMAX_API_KEY",
        "default_model": "MiniMax-M2.1",
        "factory_provider": "minimax",
    },
    "ollama": {
        "display_name": "Ollama (Local)",
        "model_setting": "OLLAMA_MODEL",
        "api_key_setting": None,  # No API key needed
        "default_model": "llama3",
        "factory_provider": "ollama",
    }
}


def _get_active_provider(db: Session) -> str:
    """Get the active LLM provider from database or fall back to .env."""
    from app.models.aeo_models import CacheEntry
    
    cached = CacheEntry.get(db, "app_settings:llm_provider")
    if cached:
        return cached.get("provider", settings.LLM_PROVIDER.lower())
    return settings.LLM_PROVIDER.lower()


def _set_active_provider(db: Session, provider: str):
    """Set the active LLM provider in database."""
    from app.models.aeo_models import CacheEntry
    
    CacheEntry.set(db, "app_settings:llm_provider", {"provider": provider}, ttl_hours=0)


@router.get("/llm-providers")
async def list_llm_providers(db: Session = Depends(get_db)):
    """
    List all available LLM providers with their configuration status.
    
    Returns a list of providers with:
    - name: Internal provider name
    - display_name: Human-readable name
    - model: Currently configured model
    - configured: Whether API key is set
    - active: Whether this is the currently selected provider
    """
    active_provider = _get_active_provider(db)
    
    providers = []
    for name, info in LLM_PROVIDERS.items():
        # Check if API key is configured
        api_key_attr = info["api_key_setting"]
        if api_key_attr:
            configured = bool(getattr(settings, api_key_attr, None))
        else:
            configured = True  # Ollama doesn't need API key
        
        # Get current model
        model_attr = info["model_setting"]
        current_model = getattr(settings, model_attr, None) if model_attr else None
        
        providers.append(LLMProviderInfo(
            name=name,
            display_name=info["display_name"],
            model=current_model or info["default_model"],
            factory_provider=info.get("factory_provider", name),
            configured=configured,
            active=(name == active_provider)
        ))
    
    # Sort: active first, then configured, then alphabetical
    providers.sort(key=lambda p: (not p.active, not p.configured, p.display_name))
    
    return {
        "providers": [p.model_dump() for p in providers],
        "active": active_provider
    }


@router.post("/llm-provider")
async def set_llm_provider(request: SetProviderRequest, db: Session = Depends(get_db)):
    """
    Set the active LLM provider.
    
    This persists across server restarts (stored in SQLite).
    """
    provider = request.provider.lower()
    
    if provider not in LLM_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider}. Available: {list(LLM_PROVIDERS.keys())}"
        )
    
    # Check if provider is configured
    info = LLM_PROVIDERS[provider]
    api_key_attr = info["api_key_setting"]
    if api_key_attr and not getattr(settings, api_key_attr, None):
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider} is not configured. Please add {api_key_attr} to .env"
        )
    
    _set_active_provider(db, provider)
    
    return {
        "status": "success",
        "message": f"Active LLM provider set to {provider}",
        "provider": provider,
        "display_name": info["display_name"]
    }


@router.get("/llm-provider")
async def get_llm_provider(db: Session = Depends(get_db)):
    """Get the currently active LLM provider."""
    provider = _get_active_provider(db)
    info = LLM_PROVIDERS.get(provider, {})
    
    model_setting = info.get("model_setting")
    current_model = getattr(settings, model_setting, None) if model_setting else None

    return {
        "provider": provider,
        "display_name": info.get("display_name", provider),
        "model": current_model or info.get("default_model", "unknown"),
        "factory_provider": info.get("factory_provider", provider),
    }
