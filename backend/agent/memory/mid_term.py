"""
Mid-Term Memory Manager

实现中期记忆层 - AU2 8段式结构化压缩。

核心功能：
- 整合 AU2 压缩算法
- 压缩历史管理
- 智能压缩触发
- 上下文连续性维护
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..core.compressor import MessageCompressor, AU2Algorithm
from ..core.constants import ExecutionContext, CompressionConfig

logger = logging.getLogger(__name__)


@dataclass
class CompressionRecord:
    """
    压缩记录

    记录每次压缩的详细信息
    """

    # 压缩 ID
    compression_id: str

    # 压缩时间
    timestamp: datetime = field(default_factory=datetime.now)

    # 原始消息数
    original_count: int = 0

    # 压缩后消息数
    compressed_count: int = 0

    # 原始 Token 数
    original_tokens: int = 0

    # 压缩后 Token 数
    compressed_tokens: int = 0

    # 压缩比例
    compression_ratio: float = 0.0

    # Token 节省数
    tokens_saved: int = 0

    # 压缩摘要
    summary: str = ""

    # 压缩的消息段落
    segments: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "compression_id": self.compression_id,
            "timestamp": self.timestamp.isoformat(),
            "original_count": self.original_count,
            "compressed_count": self.compressed_count,
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "compression_ratio": self.compression_ratio,
            "tokens_saved": self.tokens_saved,
            "summary": self.summary,
            "segments": self.segments,
        }


class MidTermMemory:
    """
    中期记忆管理器

    使用 AU2 8段式结构化压缩算法，在 Token 使用率达到阈值时自动压缩历史消息。
    """

    def __init__(
        self,
        config: Optional[CompressionConfig] = None,
        max_compression_history: int = 10,
    ):
        """
        初始化中期记忆

        Args:
            config: 压缩配置
            max_compression_history: 最大压缩历史记录数
        """
        self.config = config or CompressionConfig()
        self.max_compression_history = max_compression_history

        # 消息压缩器
        self.compressor = MessageCompressor(self.config)

        # AU2 算法
        self.au2 = AU2Algorithm(self.config)

        # 压缩历史记录
        self._compression_history: List[CompressionRecord] = []

        # 统计信息
        self._stats = {
            "total_compressions": 0,
            "total_tokens_saved": 0,
            "avg_compression_ratio": 0.0,
        }

        logger.info(
            f"MidTermMemory 初始化："
            f"threshold={self.config.threshold}, "
            f"keep_recent={self.config.keep_recent_messages}"
        )

    async def compress_if_needed(
        self,
        messages: List[Dict[str, Any]],
        context: ExecutionContext,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        检查并在需要时压缩消息

        Args:
            messages: 消息列表
            context: 执行上下文

        Returns:
            (处理后的消息列表, 是否执行了压缩)
        """
        # 调用核心压缩器
        compressed_messages, did_compress = await self.compressor.compress_if_needed(
            messages, context
        )

        if did_compress:
            # 记录压缩信息
            await self._record_compression(
                messages,
                compressed_messages,
                context,
            )

        return compressed_messages, did_compress

    async def force_compress(
        self,
        messages: List[Dict[str, Any]],
        context: ExecutionContext,
    ) -> List[Dict[str, Any]]:
        """
        强制压缩消息（不检查阈值）

        Args:
            messages: 消息列表
            context: 执行上下文

        Returns:
            压缩后的消息列表
        """
        logger.info(f"强制压缩：{len(messages)} 条消息")

        # 分离系统消息和对话消息
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        conversation_messages = [msg for msg in messages if msg.get("role") != "system"]

        if len(conversation_messages) <= self.config.keep_recent_messages:
            logger.warning("消息数量不足，无需压缩")
            return messages

        # 保留最近的消息
        recent_messages = conversation_messages[-self.config.keep_recent_messages:]
        messages_to_compress = conversation_messages[:-self.config.keep_recent_messages]

        # 执行 AU2 压缩
        compressed_text = self.au2.compress(messages_to_compress, context)

        # 创建压缩摘要消息
        summary_message = {
            "role": "system",
            "content": compressed_text,
        }

        # 组合最终消息列表
        compressed_messages = (
            system_messages +
            [summary_message] +
            recent_messages
        )

        # 记录压缩信息
        await self._record_compression(
            messages,
            compressed_messages,
            context,
        )

        return compressed_messages

    async def _record_compression(
        self,
        original_messages: List[Dict[str, Any]],
        compressed_messages: List[Dict[str, Any]],
        context: ExecutionContext,
    ):
        """
        记录压缩信息

        Args:
            original_messages: 原始消息
            compressed_messages: 压缩后消息
            context: 执行上下文
        """
        # 估算 Token 数
        from ..core.constants import estimate_token_count

        original_tokens = sum(
            estimate_token_count(str(msg.get("content", "")))
            for msg in original_messages
        )

        compressed_tokens = sum(
            estimate_token_count(str(msg.get("content", "")))
            for msg in compressed_messages
        )

        tokens_saved = original_tokens - compressed_tokens
        compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 0

        # 创建压缩记录
        record = CompressionRecord(
            compression_id=f"compress_{int(datetime.now().timestamp() * 1000)}",
            original_count=len(original_messages),
            compressed_count=len(compressed_messages),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compression_ratio,
            tokens_saved=tokens_saved,
            summary=f"Compressed {len(original_messages)} -> {len(compressed_messages)} messages",
        )

        # 添加到历史
        self._compression_history.append(record)

        # 限制历史记录数量
        if len(self._compression_history) > self.max_compression_history:
            self._compression_history.pop(0)

        # 更新统计
        self._stats["total_compressions"] += 1
        self._stats["total_tokens_saved"] += tokens_saved
        self._stats["avg_compression_ratio"] = (
            sum(r.compression_ratio for r in self._compression_history) /
            len(self._compression_history)
        )

        logger.info(
            f"压缩记录已保存："
            f"{record.original_count} -> {record.compressed_count} 条消息, "
            f"节省 {tokens_saved} tokens ({compression_ratio:.1%})"
        )

    def get_compression_history(self) -> List[CompressionRecord]:
        """
        获取压缩历史

        Returns:
            压缩记录列表
        """
        return self._compression_history.copy()

    def get_latest_compression(self) -> Optional[CompressionRecord]:
        """
        获取最新的压缩记录

        Returns:
            最新的压缩记录，如果没有则返回 None
        """
        return self._compression_history[-1] if self._compression_history else None

    def get_compression_summary(self) -> str:
        """
        获取压缩摘要（文本格式）

        Returns:
            格式化的压缩摘要
        """
        if not self._compression_history:
            return "No compression history available."

        lines = ["## Compression History\n"]

        for i, record in enumerate(self._compression_history, 1):
            lines.append(
                f"{i}. [{record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{record.original_count} -> {record.compressed_count} messages, "
                f"saved {record.tokens_saved} tokens ({record.compression_ratio:.1%})"
            )

        lines.append(f"\n**Total Compressions:** {self._stats['total_compressions']}")
        lines.append(f"**Total Tokens Saved:** {self._stats['total_tokens_saved']:,}")
        lines.append(f"**Avg Compression Ratio:** {self._stats['avg_compression_ratio']:.1%}")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据字典
        """
        return {
            **self._stats,
            "compression_history_count": len(self._compression_history),
            "latest_compression": (
                self._compression_history[-1].to_dict()
                if self._compression_history else None
            ),
        }

    def clear_history(self):
        """清空压缩历史"""
        self._compression_history.clear()
        logger.info("压缩历史已清空")

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"MidTermMemory("
            f"compressions={stats['total_compressions']}, "
            f"tokens_saved={stats['total_tokens_saved']})"
        )
