"""
SDK Memory Manager

Three-tier memory system for Claude Agent SDK.

Architecture:
1. Long-Term Memory - CLAUDE.md content injected to system_prompt
2. Mid-Term Memory - AU2 8-segment compression
3. Short-Term Memory - Current session messages
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

from .memory.long_term import LongTermMemory
from .core.compressor import AU2Algorithm
from .core.constants import (
    CompressionConfig,
    ExecutionContext,
    estimate_token_count,
    COMPRESSION_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ============================================
# Configuration
# ============================================

@dataclass
class MemoryConfig:
    """Memory system configuration"""
    max_context_tokens: int = 200000  # Claude context limit
    compression_threshold: float = COMPRESSION_THRESHOLD  # 0.92
    keep_recent_messages: int = 10  # Don't compress recent messages
    enable_long_term: bool = True
    enable_compression: bool = True


# ============================================
# Message Types
# ============================================

@dataclass
class MemoryMessage:
    """Message in memory"""
    role: str  # user, assistant, system, tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = estimate_token_count(self.content)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format"""
        return {
            "role": self.role,
            "content": self.content,
        }


# ============================================
# SDK Memory Manager
# ============================================

class SDKMemoryManager:
    """
    Claude Agent SDK Memory Manager

    Integrates three-tier memory:
    1. Long-Term - CLAUDE.md content injected to system_prompt
    2. Mid-Term - AU2 8-segment compression when threshold reached
    3. Short-Term - Current session messages
    """

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        project_root: Optional[Path] = None,
    ):
        """
        Initialize memory manager

        Args:
            config: Memory configuration
            project_root: Project root for CLAUDE.md
        """
        self.config = config or MemoryConfig()
        self.project_root = project_root

        # Long-term memory (CLAUDE.md)
        self.long_term: Optional[LongTermMemory] = None
        if self.config.enable_long_term and project_root:
            self.long_term = LongTermMemory(project_root=project_root)
            self.long_term.load()

        # AU2 compressor (Mid-term)
        self.au2 = AU2Algorithm(CompressionConfig())

        # Short-term memory (messages)
        self._messages: List[MemoryMessage] = []
        self._total_tokens: int = 0

        # Compression history
        self._compression_count: int = 0
        self._tokens_saved: int = 0

        logger.info(
            f"SDKMemoryManager initialized: "
            f"long_term={'enabled' if self.long_term else 'disabled'}, "
            f"compression={'enabled' if self.config.enable_compression else 'disabled'}"
        )

    # ============================================
    # System Prompt (Long-Term)
    # ============================================

    def build_system_prompt(self, base_prompt: str) -> str:
        """
        Build system prompt with long-term memory

        Args:
            base_prompt: Base system prompt

        Returns:
            Enhanced system prompt with project context
        """
        if not self.long_term:
            return base_prompt

        long_term_context = self.long_term.get_context_for_system_prompt()

        if long_term_context:
            return f"{base_prompt}\n\n## Project Context\n{long_term_context}"

        return base_prompt

    # ============================================
    # Message Management (Short-Term)
    # ============================================

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryMessage:
        """
        Add message to short-term memory

        Automatically triggers compression if threshold reached.

        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
            metadata: Optional metadata

        Returns:
            Created message
        """
        message = MemoryMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        self._messages.append(message)
        self._total_tokens += message.token_count

        logger.debug(
            f"Message added: role={role}, "
            f"tokens={message.token_count}, "
            f"total={self._total_tokens}"
        )

        # Check if compression needed
        if self._should_compress():
            self._compress()

        return message

    def add_user_message(self, content: str, **metadata) -> MemoryMessage:
        """Add user message"""
        return self.add_message("user", content, metadata)

    def add_assistant_message(self, content: str, **metadata) -> MemoryMessage:
        """Add assistant message"""
        return self.add_message("assistant", content, metadata)

    def add_tool_result(
        self,
        tool_use_id: str,
        content: str,
        tool_name: Optional[str] = None,
    ) -> MemoryMessage:
        """Add tool result message"""
        return self.add_message(
            "tool",
            content,
            {"tool_use_id": tool_use_id, "tool_name": tool_name},
        )

    # ============================================
    # Compression (Mid-Term)
    # ============================================

    def _should_compress(self) -> bool:
        """Check if compression is needed"""
        if not self.config.enable_compression:
            return False

        usage_rate = self._total_tokens / self.config.max_context_tokens
        return usage_rate >= self.config.compression_threshold

    def _compress(self):
        """
        Execute AU2 compression

        Compresses older messages while keeping recent ones intact.
        """
        if len(self._messages) <= self.config.keep_recent_messages:
            logger.debug("Not enough messages to compress")
            return

        logger.info(f"Starting compression: {len(self._messages)} messages, {self._total_tokens} tokens")

        # Separate messages
        recent = self._messages[-self.config.keep_recent_messages:]
        to_compress = self._messages[:-self.config.keep_recent_messages]

        # Convert to dict format for AU2
        messages_dict = [m.to_dict() for m in to_compress]

        # Execute AU2 8-segment compression
        context = ExecutionContext(session_id="memory_compress")
        compressed_text = self.au2.compress(messages_dict, context)

        # Calculate tokens saved
        old_tokens = sum(m.token_count for m in to_compress)
        new_tokens = estimate_token_count(compressed_text)
        tokens_saved = old_tokens - new_tokens

        # Create compressed message
        compressed_message = MemoryMessage(
            role="system",
            content=compressed_text,
            metadata={"compressed": True, "original_count": len(to_compress)},
        )

        # Rebuild message list
        self._messages = [compressed_message] + recent

        # Recalculate total tokens
        self._total_tokens = sum(m.token_count for m in self._messages)

        # Update stats
        self._compression_count += 1
        self._tokens_saved += tokens_saved

        logger.info(
            f"Compression complete: "
            f"{len(to_compress)} -> 1 messages, "
            f"saved {tokens_saved} tokens, "
            f"new total: {self._total_tokens}"
        )

    # ============================================
    # API Integration
    # ============================================

    def get_messages_for_api(self) -> List[Dict[str, Any]]:
        """
        Get messages formatted for Claude API

        Returns:
            List of message dicts
        """
        return [m.to_dict() for m in self._messages]

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get conversation history (alias for get_messages_for_api)
        """
        return self.get_messages_for_api()

    # ============================================
    # State Management
    # ============================================

    def clear(self):
        """Clear short-term memory"""
        self._messages = []
        self._total_tokens = 0
        logger.info("Short-term memory cleared")

    def clear_all(self):
        """Clear all memory including compression stats"""
        self.clear()
        self._compression_count = 0
        self._tokens_saved = 0
        logger.info("All memory cleared")

    # ============================================
    # Statistics
    # ============================================

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "message_count": len(self._messages),
            "total_tokens": self._total_tokens,
            "usage_rate": self._total_tokens / self.config.max_context_tokens,
            "compression_count": self._compression_count,
            "tokens_saved": self._tokens_saved,
            "long_term_enabled": self.long_term is not None,
            "compression_enabled": self.config.enable_compression,
        }

    def get_summary(self) -> str:
        """Get human-readable memory summary"""
        stats = self.get_stats()
        lines = [
            "## Memory Status",
            f"- Messages: {stats['message_count']}",
            f"- Tokens: {stats['total_tokens']:,} / {self.config.max_context_tokens:,}",
            f"- Usage: {stats['usage_rate']:.1%}",
            f"- Compressions: {stats['compression_count']}",
            f"- Tokens Saved: {stats['tokens_saved']:,}",
        ]
        return "\n".join(lines)

    # ============================================
    # Dunder Methods
    # ============================================

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"SDKMemoryManager("
            f"messages={stats['message_count']}, "
            f"tokens={stats['total_tokens']}, "
            f"usage={stats['usage_rate']:.1%})"
        )


# ============================================
# Factory Function
# ============================================

def create_memory_manager(
    project_root: Optional[Path] = None,
    config: Optional[MemoryConfig] = None,
) -> SDKMemoryManager:
    """
    Create a new memory manager instance

    Args:
        project_root: Project root for CLAUDE.md
        config: Memory configuration

    Returns:
        Configured memory manager
    """
    return SDKMemoryManager(
        config=config,
        project_root=project_root,
    )
