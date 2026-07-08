from __future__ import annotations

from typing import Any, Dict, List, Optional

# Backward-compatible wrapper for ProviderLLMClient.
# It exists so we can evolve response normalization independently.


async def create_chat_blocks(llm_client: Any, system_prompt: str, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], max_tokens: int):
    resp = await llm_client.create_chat(
        system_prompt=system_prompt,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
    )
    return resp

