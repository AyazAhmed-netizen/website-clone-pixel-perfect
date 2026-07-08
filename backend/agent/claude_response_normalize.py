"""Normalize provider responses into Claude-like response blocks.

The agent loop expects:
- response.content: list of blocks
- blocks have .type == 'text' or 'tool_use'
- tool_use blocks have: id, name, input

ProviderLLMClient returns raw SDK responses for Anthropic and OpenAI-compatible
providers.

This file centralizes the mapping so the agent can remain stable.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def _has_anthropic_shape(resp: Any) -> bool:
    return hasattr(resp, "content") and isinstance(getattr(resp, "content"), list)


def _normalize_to_claude_blocks_anthropic(resp: Any) -> Any:
    # Anthropic SDK response already matches the agent's expected interface.
    return resp


def _normalize_to_claude_blocks_openai(resp: Any) -> Any:
    # OpenAI chat.completions response shape:
    # resp.choices[0].message.content
    # resp.choices[0].message.tool_calls (optional)

    try:
        choice = resp.choices[0]
        msg = choice.message

        blocks: List[Any] = []

        if getattr(msg, "content", None):
            blocks.append(_Block(type="text", text=msg.content))

        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            # tc.function.arguments is usually a JSON string
            try:
                input_data: Dict[str, Any] = json.loads(tc.function.arguments)
            except Exception:
                input_data = {}

            blocks.append(
                _Block(
                    type="tool_use",
                    id=tc.id,
                    name=tc.function.name,
                    input=input_data,
                )
            )

        return _Response(content=blocks, stop_reason=getattr(choice, "finish_reason", None))
    except Exception as e:
        raise RuntimeError(f"Failed to normalize OpenAI response: {e}")


class _Block:
    def __init__(self, type: str, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Response:
    def __init__(self, content: List[Any], stop_reason: Any = None):
        self.content = content
        self.stop_reason = stop_reason


def _normalize_to_claude_blocks(resp: Any) -> Any:
    if _has_anthropic_shape(resp):
        return _normalize_to_claude_blocks_anthropic(resp)

    # Otherwise assume OpenAI-compatible
    return _normalize_to_claude_blocks_openai(resp)

