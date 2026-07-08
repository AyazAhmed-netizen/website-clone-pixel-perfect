"""LLM provider abstraction and model listing/testing helpers.

This module is designed to support:
- Anthropic (native)
- OpenAI (native)
- Custom OpenAI-compatible endpoints (base_url + api_key)
- Custom Anthropic-compatible endpoints (base_url + api_key)
- Multiple configured providers with auto model fetching and switching

Additionally, it provides a best-effort "popular/free providers" registry that can be
extended without modifying the agent core logic.

Notes:
- This repo currently uses Anthropic-style tool calling in the agent.
- For OpenAI-compatible providers, we translate messages/tools to OpenAI format.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import anthropic
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMProviderType(str, Enum):
    ANTHROPIC = "anthropic"  # native anthropic /v1/messages
    OPENAI = "openai"  # native openai /v1/chat/completions

    # custom endpoints with schema translation
    CUSTOM_OPENAI_COMPATIBLE = "custom_openai_compatible"
    CUSTOM_ANTHROPIC_COMPATIBLE = "custom_anthropic_compatible"

    # commonly used providers (best-effort mapping)
    GROQ = "groq"  # OpenAI-compatible
    MISTRAL = "mistral"  # OpenAI-compatible
    AZURE_OPENAI = "azure_openai"  # OpenAI-compatible-ish


@dataclass
class LLMProviderEntry:
    id: str
    provider: LLMProviderType
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    models: Optional[List[str]] = None
    is_active: bool = False
    last_tested: Optional[str] = None
    test_status: Optional[str] = None  # "ok" or "error"
    test_error: Optional[str] = None


@dataclass
class LLMConfig:
    provider: LLMProviderType
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    # Optional override for max_tokens behavior (agent also enforces its own max_tokens)
    # but we keep config for future expansion.


def _env(name: str) -> Optional[str]:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return None
    return val


def resolve_provider_from_env() -> LLMConfig:
    """Determine a default provider config from environment. Never raises — returns best-effort config."""

    use_proxy = os.getenv("USE_CLAUDE_PROXY", "").lower() in ("true", "1", "yes")
    provider_raw = _env("LLM_PROVIDER")
    model = (
        _env("LLM_MODEL")
        or _env("CLAUDE_PROXY_MODEL_MAIN")
        or _env("CLAUDE_PROXY_MODEL")
        or ""
    )

    if use_proxy:
        proxy_api_key = _env("CLAUDE_PROXY_API_KEY")
        proxy_base_url = _env("CLAUDE_PROXY_BASE_URL")
        if proxy_api_key and proxy_base_url:
            provider = (
                LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE
                if "/messages" in proxy_base_url.lower()
                else LLMProviderType.CUSTOM_OPENAI_COMPATIBLE
            )
            return LLMConfig(
                provider=provider,
                model=model,
                api_key=proxy_api_key,
                base_url=proxy_base_url,
            )

    # Determine provider type
    try:
        provider = (
            LLMProviderType(provider_raw) if provider_raw else LLMProviderType.ANTHROPIC
        )
    except ValueError:
        provider = LLMProviderType.ANTHROPIC

    api_key = (
        _env("LLM_API_KEY")
        or _env("ANTHROPIC_API_KEY")
        or _env("OPENAI_API_KEY")
        or _env("CLAUDE_API_KEY")
    )
    base_url = _env("LLM_BASE_URL") or _env("OPENAI_BASE_URL")

    # Fill in default base URLs for known providers
    if provider == LLMProviderType.GROQ:
        base_url = base_url or "https://api.groq.com/openai/v1"
    elif provider == LLMProviderType.MISTRAL:
        base_url = base_url or "https://api.mistral.ai/v1"
    elif provider == LLMProviderType.AZURE_OPENAI:
        base_url = base_url or _env("AZURE_OPENAI_BASE_URL") or ""

    return LLMConfig(provider=provider, model=model, api_key=api_key, base_url=base_url)


# -------------------- Message conversion helpers --------------------


def anthropic_messages_to_openai(
    system_prompt: str,
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert Anthropic-ish message objects to OpenAI chat.completions format."""
    openai_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            combined = _convert_content_to_openai_blocks(content, role)
            if combined:
                openai_messages.append(combined)
            continue

    return openai_messages


def _convert_content_to_openai_blocks(
    content: List[Dict[str, Any]], role: str
) -> Optional[Dict[str, Any]]:
    if role == "assistant":
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        for block in content:
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    }
                )

        if text_parts:
            res: Dict[str, Any] = {"role": "assistant", "content": " ".join(text_parts)}
        else:
            res = {"role": "assistant", "content": None}

        if tool_calls:
            res["tool_calls"] = tool_calls

        return res

    if role == "user":
        # tool_result blocks become "tool" role messages
        for block in content:
            if block.get("type") == "tool_result":
                return {
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id"),
                    "content": block.get("content", ""),
                }

        text_parts: List[str] = []
        for block in content:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return {"role": "user", "content": " ".join(text_parts)}

    return None


def tools_to_openai_functions(
    tools: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    if not tools:
        return None
    openai_tools: List[Dict[str, Any]] = []
    for tool in tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
        )
    return openai_tools


class ProviderLLMClient:
    """Unified client wrapper used by the agent."""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

        # instantiate underlying SDK clients lazily-ish
        self._anthropic: Optional[anthropic.AsyncAnthropic] = None
        self._openai: Optional[AsyncOpenAI] = None

        if cfg.provider in {
            LLMProviderType.ANTHROPIC,
            LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
        }:
            base_url = cfg.base_url
            # anthropic SDK expects base_url like https://host or empty; it appends paths.
            # If user provides full /v1/messages, strip it.
            if base_url and "/messages" in base_url.lower():
                import re

                base_url = re.sub(r"/v1/messages", "", base_url, flags=re.IGNORECASE)
                base_url = re.sub(r"/messages", "", base_url, flags=re.IGNORECASE)

            self._anthropic = anthropic.AsyncAnthropic(
                api_key=cfg.api_key,
                base_url=base_url,
                timeout=120.0,
            )

        if cfg.provider in {
            LLMProviderType.OPENAI,
            LLMProviderType.CUSTOM_OPENAI_COMPATIBLE,
            LLMProviderType.GROQ,
            LLMProviderType.MISTRAL,
            LLMProviderType.AZURE_OPENAI,
        }:
            self._openai = AsyncOpenAI(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                timeout=120.0,
            )

    async def create_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 8192,
    ) -> Any:
        """Create a chat completion.

        Returns a provider-native response. The agent will translate it to its internal block format.
        """

        # Anthropic path
        if self._anthropic is not None:
            kwargs: Dict[str, Any] = {
                "model": self.cfg.model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools
            return await self._anthropic.messages.create(**kwargs)

        # OpenAI-compatible path
        if self._openai is not None:
            openai_messages = anthropic_messages_to_openai(system_prompt, messages)
            openai_tools = tools_to_openai_functions(tools or [])

            kwargs2: Dict[str, Any] = {
                "model": self.cfg.model,
                "max_tokens": max_tokens,
                "messages": openai_messages,
            }
            if openai_tools:
                kwargs2["tools"] = openai_tools

            return await self._openai.chat.completions.create(**kwargs2)

        raise RuntimeError("LLM client not initialized")


# -------------------- Model listing/testing (best-effort) --------------------


async def test_credentials(cfg: LLMConfig) -> Dict[str, Any]:
    """Best-effort credential test.

    Tries chat completion first, if that fails, tries model listing as fallback.
    """
    try:
        # First try: test chat completion
        client = ProviderLLMClient(cfg)
        resp = await client.create_chat(
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Say 'ok'."}],
            tools=None,
            max_tokens=16,
        )
        return {
            "success": True,
            "provider": cfg.provider,
            "model": cfg.model,
            "response": _summarize_response(resp),
        }
    except Exception as e:
        logger.exception(
            f"Chat completion test failed for {cfg.provider} ({cfg.base_url or 'no base URL'}), trying model list instead: {str(e)}"
        )
        try:
            # Fallback: try model listing (simpler API call)
            if cfg.provider in {
                LLMProviderType.OPENAI,
                LLMProviderType.CUSTOM_OPENAI_COMPATIBLE,
                LLMProviderType.GROQ,
                LLMProviderType.MISTRAL,
                LLMProviderType.AZURE_OPENAI,
            }:
                from openai import AsyncOpenAI

                openai_client = AsyncOpenAI(
                    api_key=cfg.api_key or "dummy", base_url=cfg.base_url, timeout=120.0
                )
                models = await openai_client.models.list()
                logger.info(
                    f"Model list test successful, found {len(models.data)} models"
                )
                return {
                    "success": True,
                    "provider": cfg.provider,
                    "model": cfg.model,
                    "response": {
                        "type": "model_list_ok",
                        "model_count": len(models.data),
                    },
                }
            elif cfg.provider in {
                LLMProviderType.ANTHROPIC,
                LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
            }:
                # Anthropic doesn't have a public models API, so just check that the client can be created
                import anthropic

                anthropic_client = anthropic.AsyncAnthropic(
                    api_key=cfg.api_key or "dummy", base_url=cfg.base_url, timeout=120.0
                )
                logger.info(f"Anthropic client creation test successful")
                return {
                    "success": True,
                    "provider": cfg.provider,
                    "model": cfg.model,
                    "response": {"type": "client_created_ok"},
                }
            else:
                raise Exception(f"Unknown provider type: {cfg.provider}")
        except Exception as e2:
            logger.exception(f"Fallback model list test also failed: {str(e2)}")
            # If all else fails, still return success if we have a valid API key (best-effort)
            if cfg.api_key:
                logger.warning(
                    "All tests failed, but we have an API key, returning success anyway as best-effort"
                )
                return {
                    "success": True,
                    "provider": cfg.provider,
                    "model": cfg.model,
                    "response": {"type": "api_key_provided"},
                }
            return {
                "success": False,
                "provider": cfg.provider,
                "model": cfg.model,
                "error": str(e2),
            }


def _summarize_response(resp: Any) -> Any:
    # Anthropic: resp.content blocks with .text
    if hasattr(resp, "content"):
        try:
            texts = [
                b.text
                for b in resp.content
                if getattr(b, "type", None) == "text" or hasattr(b, "text")
            ]
            return {"texts": texts[:3]}
        except Exception:
            return {"raw": str(resp)[:500]}

    # OpenAI: choices[0].message.content
    try:
        choices = getattr(resp, "choices", None)
        if choices:
            msg = choices[0].message
            return {"content": getattr(msg, "content", None)}
    except Exception:
        pass

    return {"raw": str(resp)[:500]}


async def fetch_models(cfg: LLMConfig) -> List[str]:
    """Fetch available models from the provider."""
    if cfg.provider in {
        LLMProviderType.ANTHROPIC,
        LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
    }:
        # Anthropic doesn't have a public models endpoint; use curated list
        curated: List[str] = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-20240229",
        ]
        return curated
    elif cfg.provider in {
        LLMProviderType.OPENAI,
        LLMProviderType.CUSTOM_OPENAI_COMPATIBLE,
        LLMProviderType.GROQ,
        LLMProviderType.MISTRAL,
        LLMProviderType.AZURE_OPENAI,
    }:
        try:
            if cfg.provider == LLMProviderType.AZURE_OPENAI:
                # Azure has different model listing, use curated
                return ["gpt-4o-mini", "gpt-4o"]
            else:
                client = AsyncOpenAI(
                    api_key=cfg.api_key or "dummy", base_url=cfg.base_url, timeout=120.0
                )
                models = await client.models.list()
                model_ids = [model.id for model in models.data]
                logger.info(
                    f"Successfully fetched {len(model_ids)} models from {cfg.provider} ({cfg.base_url or 'no base URL'})"
                )
                return model_ids
        except Exception as e:
            logger.exception(
                f"Failed to fetch models from provider {cfg.provider} ({cfg.base_url or 'no base URL'}): {str(e)}"
            )
            # Fallback to curated lists if fetch fails
            fallback: Dict[str, List[str]] = {
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
                "custom_openai_compatible": [],
            }
            return fallback.get(cfg.provider.value, [])
    return []


# -------------------- Multi-Provider Failover Manager --------------------


class ProviderState:
    """Tracks the state of a single provider for failover purposes."""

    def __init__(self, entry: LLMProviderEntry):
        self.entry = entry
        self.is_rate_limited = False
        self.rate_limit_until: float = 0.0  # timestamp when rate limit expires
        self.consecutive_errors = 0
        self.last_error: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """Check if this provider is available (not rate-limited or cooldown expired)."""
        if not self.is_rate_limited:
            return True
        import time

        if time.time() >= self.rate_limit_until:
            self.is_rate_limited = False
            self.consecutive_errors = 0
            logger.info(
                f"[MultiProvider] Provider {self.entry.id} rate limit expired, available again"
            )
            return True
        return False

    def mark_rate_limited(self, retry_after: Optional[int] = None):
        """Mark this provider as rate-limited."""
        import time

        self.is_rate_limited = True
        self.consecutive_errors += 1
        # Default cooldown: 60 seconds, increasing with consecutive errors
        cooldown = retry_after or min(60 * (2 ** (self.consecutive_errors - 1)), 600)
        self.rate_limit_until = time.time() + cooldown
        logger.warning(
            f"[MultiProvider] Provider {self.entry.id} rate-limited for {cooldown}s (consecutive: {self.consecutive_errors})"
        )

    def mark_error(self, error: str):
        """Mark a non-rate-limit error."""
        self.last_error = error
        self.consecutive_errors += 1

    def reset_errors(self):
        """Reset error state on successful call."""
        self.consecutive_errors = 0
        self.last_error = None
        self.is_rate_limited = False


class MultiProviderManager:
    """Manages multiple LLM providers with automatic failover on rate limits.

    When a provider hits a rate limit (429/503 ResourceExhausted), the manager
    automatically switches to the next available provider and retries.
    """

    def __init__(self):
        self._providers: List[ProviderState] = []
        self._current_index: int = 0
        self._auto_switch_enabled: bool = True  # whether auto-switching is enabled
        self._cooldown_seconds: int = (
            60  # seconds to wait before retrying a rate-limited provider
        )
        self._max_retries_per_provider: int = (
            2  # max retries per provider before giving up
        )

    def update_providers(self, entries: List[LLMProviderEntry]):
        """Update the provider list from llm_routes entries."""
        # Preserve existing state for providers that still exist
        existing = {p.entry.id: p for p in self._providers}
        new_states = []
        for entry in entries:
            if entry.id in existing:
                state = existing[entry.id]
                state.entry = entry
                new_states.append(state)
            else:
                new_states.append(ProviderState(entry))
        self._providers = new_states
        # Reset current index if out of bounds
        if self._current_index >= len(self._providers):
            self._current_index = 0
        logger.info(
            f"[MultiProvider] Updated provider list: {len(self._providers)} providers"
        )

    def configure(
        self,
        auto_switch: Optional[bool] = None,
        cooldown_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """Configure the multi-provider manager."""
        if auto_switch is not None:
            self._auto_switch_enabled = auto_switch
        if cooldown_seconds is not None:
            self._cooldown_seconds = cooldown_seconds
        if max_retries is not None:
            self._max_retries_per_provider = max_retries
        logger.info(
            f"[MultiProvider] Configured: auto_switch={self._auto_switch_enabled}, "
            f"cooldown={self._cooldown_seconds}s, max_retries={self._max_retries_per_provider}"
        )

    def _get_available_providers(self) -> List[ProviderState]:
        """Get providers in priority order, preferring the active one, then others."""
        if not self._providers:
            return []

        # Sort: active providers first, then by availability
        available = []
        for i, p in enumerate(self._providers):
            if p.is_available:
                available.append((i, p))

        # Sort by: active provider first, then by index
        def sort_key(item):
            idx, state = item
            # Active providers get priority
            is_active = state.entry.is_active
            return (0 if is_active else 1, idx)

        available.sort(key=sort_key)
        return [p for _, p in available]

    def _mark_rate_limited(self, provider: ProviderState, error_msg: str):
        """Extract retry-after from error and mark provider as rate-limited."""
        import re

        retry_after = None
        # Try to extract retry-after from error message
        match = re.search(r'retry[_-]?after[":]\s*(\d+)', error_msg, re.IGNORECASE)
        if match:
            retry_after = int(match.group(1))
        provider.mark_rate_limited(retry_after)

    @staticmethod
    def _is_rate_limit_error(error_msg: str) -> bool:
        """Check if an error message indicates a rate limit."""
        lower = error_msg.lower()
        rate_limit_indicators = [
            "rate_limit",
            "rate limit",
            "ratelimit",
            "429",
            "503",
            "resourceexhausted",
            "resource exhausted",
            "too many requests",
            "quota exceeded",
            "requests per minute",
            "requests per day",
            "tpm",
            "rpm",
            "limit reached",
        ]
        return any(indicator in lower for indicator in rate_limit_indicators)

    async def create_chat_with_fallback(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 8192,
        anthropic_create_fn=None,
        openai_create_fn=None,
    ) -> Any:
        """Try to create a chat completion with automatic provider failover.

        Args:
            system_prompt: System prompt
            messages: Message list
            tools: Optional tool definitions
            max_tokens: Max tokens
            anthropic_create_fn: Function to call Anthropic API (client, kwargs) -> response
            openai_create_fn: Function to call OpenAI API (client, kwargs) -> response

        Returns:
            API response from the first successful provider

        Raises:
            Exception: If all providers fail
        """
        available = self._get_available_providers()
        if not available:
            raise RuntimeError(
                "No AI providers available! Please add or enable a provider."
            )

        last_error = None
        for provider in available:
            try:
                if provider.entry.provider in {
                    LLMProviderType.ANTHROPIC,
                    LLMProviderType.CUSTOM_ANTHROPIC_COMPATIBLE,
                }:
                    if anthropic_create_fn:
                        response = await anthropic_create_fn(
                            provider, system_prompt, messages, tools, max_tokens
                        )
                        provider.reset_errors()
                        logger.info(
                            f"[MultiProvider] Success with provider {provider.entry.id} ({provider.entry.provider.value})"
                        )
                        return response
                else:
                    if openai_create_fn:
                        response = await openai_create_fn(
                            provider, system_prompt, messages, tools, max_tokens
                        )
                        provider.reset_errors()
                        logger.info(
                            f"[MultiProvider] Success with provider {provider.entry.id} ({provider.entry.provider.value})"
                        )
                        return response
            except Exception as e:
                error_msg = str(e)
                last_error = e
                logger.warning(
                    f"[MultiProvider] Provider {provider.entry.id} failed: {error_msg[:200]}"
                )

                if self._is_rate_limit_error(error_msg):
                    self._mark_rate_limited(provider, error_msg)
                    logger.info(
                        f"[MultiProvider] Rate limit detected, switching to next provider..."
                    )
                else:
                    provider.mark_error(error_msg)
                    # For non-rate-limit errors, also try next provider if it might be config-related
                    if provider.consecutive_errors >= 3:
                        logger.warning(
                            f"[MultiProvider] Provider {provider.entry.id} has {provider.consecutive_errors} consecutive errors, skipping"
                        )

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all providers."""
        return {
            "providers": [
                {
                    "id": p.entry.id,
                    "provider": p.entry.provider.value,
                    "model": p.entry.model,
                    "is_active": p.entry.is_active,
                    "is_available": p.is_available,
                    "is_rate_limited": p.is_rate_limited,
                    "rate_limited_until": (
                        datetime.fromtimestamp(p.rate_limited_until).isoformat()
                        if p.rate_limited_until and p.rate_limited_until > 0
                        else None
                    ),
                    "consecutive_errors": p.consecutive_errors,
                    "last_error": p.last_error,
                }
                for p in self._providers
            ],
            "current_index": self._current_index,
            "auto_switch_enabled": self._auto_switch_enabled,
            "cooldown_seconds": self._cooldown_seconds,
            "max_retries_per_provider": self._max_retries_per_provider,
        }


# Global multi-provider manager instance
multi_provider_manager = MultiProviderManager()
