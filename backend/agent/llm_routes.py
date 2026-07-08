"""HTTP endpoints for listing providers/models, testing credentials, and applying config at runtime."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .llm_provider import (
    LLMConfig,
    LLMProviderEntry,
    LLMProviderType,
    fetch_models,
    multi_provider_manager,
    resolve_provider_from_env,
    test_credentials,
    uuid4,
)

router = APIRouter(prefix="/api/llm", tags=["llm"])

# ── Persistence file ───────────────────────────────────────────────────────────
_PERSISTENCE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "providers.json"
)


# ── Runtime state for multiple providers ──────────────────────────────────────
_providers: List[LLMProviderEntry] = []
_active_config: Optional[LLMConfig] = None


def _save_providers():
    """Save providers to disk as JSON."""
    data = []
    for entry in _providers:
        entry_dict = {
            "id": entry.id,
            "provider": entry.provider.value,
            "model": entry.model,
            "api_key": entry.api_key,
            "base_url": entry.base_url,
            "models": entry.models,
            "is_active": entry.is_active,
            "last_tested": entry.last_tested,
            "test_status": entry.test_status,
            "test_error": entry.test_error,
        }
        data.append(entry_dict)
    with open(_PERSISTENCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    logger.info(
        f"[llm_routes] Saved {len(_providers)} providers to {_PERSISTENCE_FILE}"
    )
    # Update the multi-provider manager
    multi_provider_manager.update_providers(_providers)


def _load_providers():
    """Load providers from disk if available."""
    global _providers, _active_config
    if os.path.exists(_PERSISTENCE_FILE):
        try:
            with open(_PERSISTENCE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded_providers = []
            active_entry = None
            for entry_dict in data:
                entry = LLMProviderEntry(
                    id=entry_dict["id"],
                    provider=LLMProviderType(entry_dict["provider"]),
                    model=entry_dict["model"],
                    api_key=entry_dict.get("api_key"),
                    base_url=entry_dict.get("base_url"),
                    models=entry_dict.get("models", []),
                    is_active=entry_dict.get("is_active", False),
                    last_tested=entry_dict.get("last_tested"),
                    test_status=entry_dict.get("test_status"),
                    test_error=entry_dict.get("test_error"),
                )
                loaded_providers.append(entry)
                if entry.is_active:
                    active_entry = entry
            _providers = loaded_providers
            if active_entry:
                _active_config = LLMConfig(
                    provider=active_entry.provider,
                    model=active_entry.model,
                    api_key=active_entry.api_key,
                    base_url=active_entry.base_url,
                )
            logger.info(
                f"[llm_routes] Loaded {len(_providers)} providers from {_PERSISTENCE_FILE}"
            )
            # Update the multi-provider manager with loaded providers
            multi_provider_manager.update_providers(_providers)
            return
        except Exception as e:
            logger.exception(f"[llm_routes] Failed to load providers: {e}")
    # Fallback to env vars if no saved file or failed to load
    _initialize_providers_from_env()


def get_active_config() -> LLMConfig:
    """Return the currently active LLM config (UI override > env vars)."""
    if _active_config is not None:
        return _active_config
    return resolve_provider_from_env()


def _initialize_providers_from_env():
    """Initialize providers list from environment variables on first use."""
    global _providers
    if not _providers:
        cfg = resolve_provider_from_env()
        if cfg.api_key:
            entry = LLMProviderEntry(
                id=str(uuid4()),
                provider=cfg.provider,
                model=cfg.model,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                models=[],
                is_active=True,
                last_tested=None,
                test_status=None,
                test_error=None,
            )
            _providers.append(entry)
            _active_config = cfg
            _save_providers()


# Initialize providers on first import
_load_providers()


# ── Request / Response models ─────────────────────────────────────────────────


class LLMTestRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class LLMApplyRequest(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class CreateProviderRequest(BaseModel):
    provider: str
    model: str
    api_key: str
    base_url: Optional[str] = None


class UpdateProviderRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/providers")
async def list_providers() -> Dict[str, Any]:
    """List all available provider types and saved provider entries."""

    # Convert entries to dict, masking API keys
    def entry_to_dict(entry: LLMProviderEntry) -> Dict[str, Any]:
        return {
            "id": entry.id,
            "provider": entry.provider.value,
            "model": entry.model,
            "base_url": entry.base_url or "",
            "models": entry.models or [],
            "is_active": entry.is_active,
            "last_tested": entry.last_tested,
            "test_status": entry.test_status,
            "test_error": entry.test_error,
            "has_api_key": bool(entry.api_key),
        }

    return {
        "provider_types": [p.value for p in LLMProviderType],
        "providers": [entry_to_dict(p) for p in _providers],
    }


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str) -> Dict[str, Any]:
    """Get a single provider entry."""
    entry = next((p for p in _providers if p.id == provider_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Provider not found")

    def entry_to_dict(e: LLMProviderEntry) -> Dict[str, Any]:
        return {
            "id": e.id,
            "provider": e.provider.value,
            "model": e.model,
            "base_url": e.base_url or "",
            "models": e.models or [],
            "is_active": e.is_active,
            "last_tested": e.last_tested,
            "test_status": e.test_status,
            "test_error": e.test_error,
            "has_api_key": bool(e.api_key),
        }

    return {"provider": entry_to_dict(entry)}


@router.post("/providers")
async def create_provider(req: CreateProviderRequest) -> Dict[str, Any]:
    """Create a new provider entry."""
    global _providers
    try:
        provider_type = LLMProviderType(req.provider)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Unknown provider type: {req.provider}"
        )

    entry = LLMProviderEntry(
        id=str(uuid4()),
        provider=provider_type,
        model=req.model,
        api_key=req.api_key,
        base_url=req.base_url,
        models=[],
        is_active=False,
        last_tested=None,
        test_status=None,
        test_error=None,
    )
    _providers.append(entry)
    _save_providers()

    def entry_to_dict(e: LLMProviderEntry) -> Dict[str, Any]:
        return {
            "id": e.id,
            "provider": e.provider.value,
            "model": e.model,
            "base_url": e.base_url or "",
            "models": e.models or [],
            "is_active": e.is_active,
            "last_tested": e.last_tested,
            "test_status": e.test_status,
            "test_error": e.test_error,
            "has_api_key": bool(e.api_key),
        }

    return {"success": True, "provider": entry_to_dict(entry)}


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str, req: UpdateProviderRequest
) -> Dict[str, Any]:
    """Update a provider entry."""
    entry = next((p for p in _providers if p.id == provider_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Provider not found")

    if req.provider:
        try:
            entry.provider = LLMProviderType(req.provider)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Unknown provider type: {req.provider}"
            )
    if req.model is not None:
        entry.model = req.model
    if req.api_key is not None:
        entry.api_key = req.api_key
    if req.base_url is not None:
        entry.base_url = req.base_url
    _save_providers()

    def entry_to_dict(e: LLMProviderEntry) -> Dict[str, Any]:
        return {
            "id": e.id,
            "provider": e.provider.value,
            "model": e.model,
            "base_url": e.base_url or "",
            "models": e.models or [],
            "is_active": e.is_active,
            "last_tested": e.last_tested,
            "test_status": e.test_status,
            "test_error": e.test_error,
            "has_api_key": bool(e.api_key),
        }

    return {"success": True, "provider": entry_to_dict(entry)}


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str) -> Dict[str, Any]:
    """Delete a provider entry."""
    global _providers
    entry = next((p for p in _providers if p.id == provider_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Provider not found")

    _providers = [p for p in _providers if p.id != provider_id]

    # If we deleted the active provider, clear active config
    if entry.is_active:
        global _active_config
        _active_config = None
        for p in _providers:
            p.is_active = False
    _save_providers()

    return {"success": True}


@router.post("/providers/{provider_id}/activate")
async def activate_provider(provider_id: str) -> Dict[str, Any]:
    """Activate a provider entry as the current config"""
    global _providers, _active_config
    entry = next((p for p in _providers if p.id == provider_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Provider not found")

    for p in _providers:
        p.is_active = False

    entry.is_active = True
    _active_config = LLMConfig(
        provider=entry.provider,
        model=entry.model,
        api_key=entry.api_key,
        base_url=entry.base_url,
    )

    # Also push into env vars so existing agent code that reads os.getenv() picks it up
    os.environ["LLM_PROVIDER"] = entry.provider.value
    os.environ["LLM_MODEL"] = entry.model
    if entry.api_key:
        os.environ["LLM_API_KEY"] = entry.api_key
    if entry.base_url:
        os.environ["LLM_BASE_URL"] = entry.base_url
    elif "LLM_BASE_URL" in os.environ:
        del os.environ["LLM_BASE_URL"]

    # Map to legacy env vars used by boxlite_agent.py
    if entry.provider in (
        LLMProviderType.ANTHROPIC,
        LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
    ):
        if entry.api_key:
            os.environ["ANTHROPIC_API_KEY"] = entry.api_key
        os.environ.pop("USE_CLAUDE_PROXY", None)
        os.environ.pop("CLAUDE_PROXY_API_KEY", None)
        os.environ.pop("CLAUDE_PROXY_BASE_URL", None)
    else:
        # OpenAI-compatible path used by boxlite_agent.py
        os.environ["USE_CLAUDE_PROXY"] = "true"
        if entry.api_key:
            os.environ["CLAUDE_PROXY_API_KEY"] = entry.api_key
        if entry.base_url:
            os.environ["CLAUDE_PROXY_BASE_URL"] = entry.base_url
        os.environ["CLAUDE_PROXY_MODEL"] = entry.model
        os.environ["CLAUDE_PROXY_MODEL_MAIN"] = entry.model

    # Refresh all active agents to use the new provider
    try:
        from boxlite.boxlite_agent import refresh_all_agents_providers

        refresh_all_agents_providers()
    except ImportError:
        pass
    _save_providers()

    def entry_to_dict(e: LLMProviderEntry) -> Dict[str, Any]:
        return {
            "id": e.id,
            "provider": e.provider.value,
            "model": e.model,
            "base_url": e.base_url or "",
            "models": e.models or [],
            "is_active": e.is_active,
            "last_tested": e.last_tested,
            "test_status": e.test_status,
            "test_error": e.test_error,
            "has_api_key": bool(e.api_key),
        }

    return {"success": True, "provider": entry_to_dict(entry)}


@router.post("/providers/{provider_id}/fetch-models")
async def fetch_provider_models(provider_id: str) -> Dict[str, Any]:
    """Fetch models for a provider entry."""
    entry = next((p for p in _providers if p.id == provider_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Provider not found")

    cfg = LLMConfig(
        provider=entry.provider,
        model=entry.model,
        api_key=entry.api_key,
        base_url=entry.base_url,
    )
    models = await fetch_models(cfg)
    entry.models = models
    _save_providers()

    def entry_to_dict(e: LLMProviderEntry) -> Dict[str, Any]:
        return {
            "id": e.id,
            "provider": e.provider.value,
            "model": e.model,
            "base_url": e.base_url or "",
            "models": e.models or [],
            "is_active": e.is_active,
            "last_tested": e.last_tested,
            "test_status": e.test_status,
            "test_error": e.test_error,
            "has_api_key": bool(e.api_key),
        }

    return {"success": True, "models": models, "provider": entry_to_dict(entry)}


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str) -> Dict[str, Any]:
    """Test a provider entry's credentials and connection."""
    entry = next((p for p in _providers if p.id == provider_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Provider not found")

    cfg = LLMConfig(
        provider=entry.provider,
        model=entry.model,
        api_key=entry.api_key,
        base_url=entry.base_url,
    )
    result = await test_credentials(cfg)

    entry.last_tested = datetime.now().isoformat()
    if result["success"]:
        entry.test_status = "ok"
        entry.test_error = None
    else:
        entry.test_status = "error"
        entry.test_error = str(result.get("error", "Unknown error"))
    _save_providers()

    def entry_to_dict(e: LLMProviderEntry) -> Dict[str, Any]:
        return {
            "id": e.id,
            "provider": e.provider.value,
            "model": e.model,
            "base_url": e.base_url or "",
            "models": e.models or [],
            "is_active": e.is_active,
            "last_tested": e.last_tested,
            "test_status": e.test_status,
            "test_error": e.test_error,
            "has_api_key": bool(e.api_key),
        }

    return {**result, "provider": entry_to_dict(entry)}


@router.get("/models")
async def list_models(provider: Optional[str] = None) -> Dict[str, Any]:
    curated: Dict[str, List[str]] = {
        "anthropic": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-20240229",
        ],
        "openai": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-3.5-turbo",
        ],
        "groq": [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
        "mistral": [
            "mistral-large-latest",
            "mistral-small-latest",
            "open-mixtral-8x7b",
        ],
        "azure_openai": ["gpt-4o-mini", "gpt-4o"],
        "custom_openai_compatible": [],
        "custom_anthropic_compatible": [],
    }

    try:
        provider_type = (
            LLMProviderType(provider) if provider else get_active_config().provider
        )
    except ValueError:
        provider_type = LLMProviderType.CUSTOM_OPENAI_COMPATIBLE

    return {
        "provider": provider_type.value,
        "models": curated.get(provider_type.value, []),
    }


@router.post("/test")
async def test_llm_credentials(req: LLMTestRequest) -> Dict[str, Any]:
    try:
        try:
            default_cfg = get_active_config()
        except Exception:
            default_cfg = None

        provider = (
            LLMProviderType(req.provider)
            if req.provider
            else (default_cfg.provider if default_cfg else LLMProviderType.ANTHROPIC)
        )
        model = req.model or (default_cfg.model if default_cfg else "")
        api_key = req.api_key or (default_cfg.api_key if default_cfg else None)
        base_url = req.base_url or (default_cfg.base_url if default_cfg else None)

        cfg = LLMConfig(
            provider=provider, model=model, api_key=api_key, base_url=base_url
        )

        if not cfg.api_key:
            raise HTTPException(status_code=400, detail="api_key is required")
        if (
            provider
            in {
                LLMProviderType.CUSTOM_OPENAI_COMPATIBLE,
                LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
            }
            and not cfg.base_url
        ):
            raise HTTPException(
                status_code=400, detail="base_url is required for custom providers"
            )

        return await test_credentials(cfg)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply")
async def apply_llm_config(req: LLMApplyRequest) -> Dict[str, Any]:
    """Apply a provider config at runtime — affects all subsequent agent calls."""
    global _active_config

    try:
        provider = LLMProviderType(req.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    if not req.api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    if (
        provider
        in {
            LLMProviderType.CUSTOM_OPENAI_COMPATIBLE,
            LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
        }
        and not req.base_url
    ):
        raise HTTPException(
            status_code=400, detail="base_url is required for custom providers"
        )

    _active_config = LLMConfig(
        provider=provider,
        model=req.model,
        api_key=req.api_key,
        base_url=req.base_url or None,
    )

    # Also push into env vars so existing agent code that reads os.getenv() picks it up
    os.environ["LLM_PROVIDER"] = provider.value
    os.environ["LLM_MODEL"] = req.model
    os.environ["LLM_API_KEY"] = req.api_key
    if req.base_url:
        os.environ["LLM_BASE_URL"] = req.base_url
    elif "LLM_BASE_URL" in os.environ:
        del os.environ["LLM_BASE_URL"]

    # Map to legacy env vars used by boxlite_agent.py
    if provider in {
        LLMProviderType.ANTHROPIC,
        LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
    }:
        os.environ["ANTHROPIC_API_KEY"] = req.api_key
        os.environ.pop("USE_CLAUDE_PROXY", None)
        os.environ.pop("CLAUDE_PROXY_API_KEY", None)
        os.environ.pop("CLAUDE_PROXY_BASE_URL", None)
    else:
        # OpenAI-compatible path used by boxlite_agent.py
        os.environ["USE_CLAUDE_PROXY"] = "true"
        os.environ["CLAUDE_PROXY_API_KEY"] = req.api_key
        os.environ["CLAUDE_PROXY_BASE_URL"] = req.base_url or ""
        os.environ["CLAUDE_PROXY_MODEL"] = req.model
        os.environ["CLAUDE_PROXY_MODEL_MAIN"] = req.model

    return {"success": True, "provider": provider.value, "model": req.model}
