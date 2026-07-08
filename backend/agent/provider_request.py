from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class LLMProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CUSTOM_OPENAI_COMPATIBLE = "custom_openai_compatible"
    CUSTOM_ANTHROPIC_COMPATIBLE = "custom_anthropic_compatible"


@dataclass
class ProviderRequest:
    """Provider override that can be sent per chat (if you wire it in the websocket)."""

    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
        }

