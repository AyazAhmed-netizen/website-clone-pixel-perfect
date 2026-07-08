"""
Stream Generator (wu)

实现 Claude Code 的会话流生成器。

核心功能：
- 流式事件生成
- SSE 格式化
- 事件类型管理
- 流式内容分块
"""

from __future__ import annotations
import json
import logging
from typing import Dict, Any, AsyncGenerator, Optional, List
from datetime import datetime

from .constants import StreamEventType

logger = logging.getLogger(__name__)


class StreamEvent:
    """
    流式事件对象

    封装单个流式事件的所有信息
    """

    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None,
        retry: Optional[int] = None,
    ):
        """
        初始化流式事件

        Args:
            event_type: 事件类型
            data: 事件数据
            event_id: 事件 ID
            retry: 重试间隔（毫秒）
        """
        self.event_type = event_type
        self.data = data
        self.event_id = event_id
        self.retry = retry
        self.timestamp = datetime.now().isoformat()

    def to_sse_format(self) -> str:
        """
        转换为 SSE (Server-Sent Events) 格式

        Returns:
            SSE 格式的字符串
        """
        lines = []

        # Event ID
        if self.event_id:
            lines.append(f"id: {self.event_id}")

        # Retry interval
        if self.retry:
            lines.append(f"retry: {self.retry}")

        # Event type
        lines.append(f"event: {self.event_type}")

        # Event data (JSON)
        data_with_timestamp = {
            **self.data,
            "timestamp": self.timestamp,
        }
        lines.append(f"data: {json.dumps(data_with_timestamp)}")

        # Empty line (required by SSE spec)
        lines.append("")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            事件数据字典
        """
        return {
            "type": self.event_type,
            "data": self.data,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return f"StreamEvent(type={self.event_type}, data_keys={list(self.data.keys())})"


class StreamGenerator:
    """
    流生成器（wu）

    管理流式事件的生成和格式化
    """

    def __init__(
        self,
        session_id: str,
        format_sse: bool = True,
    ):
        """
        初始化流生成器

        Args:
            session_id: 会话 ID
            format_sse: 是否格式化为 SSE
        """
        self.session_id = session_id
        self.format_sse = format_sse

        # 事件计数器
        self._event_counter = 0

        # 统计信息
        self._stats = {
            "events_generated": 0,
            "bytes_sent": 0,
        }

        logger.info(f"StreamGenerator 初始化：session={session_id}")

    async def generate(
        self,
        event_type: str,
        data: Dict[str, Any],
        include_session_id: bool = True,
    ) -> str:
        """
        生成单个流式事件

        Args:
            event_type: 事件类型
            data: 事件数据
            include_session_id: 是否包含 session_id

        Returns:
            格式化的事件字符串
        """
        # 添加 session_id
        if include_session_id:
            data = {**data, "session_id": self.session_id}

        # 创建事件
        event = StreamEvent(
            event_type=event_type,
            data=data,
            event_id=f"{self.session_id}_{self._event_counter}",
        )

        self._event_counter += 1
        self._stats["events_generated"] += 1

        # 格式化
        if self.format_sse:
            formatted = event.to_sse_format()
        else:
            formatted = json.dumps(event.to_dict()) + "\n"

        self._stats["bytes_sent"] += len(formatted.encode())

        logger.debug(f"生成事件：{event_type}")

        return formatted

    async def stream_text(
        self,
        text: str,
        chunk_size: int = 1,
        event_type: str = StreamEventType.TEXT_DELTA,
    ) -> AsyncGenerator[str, None]:
        """
        流式输出文本

        Args:
            text: 要输出的文本
            chunk_size: 每次输出的字符数
            event_type: 事件类型

        Yields:
            格式化的事件字符串
        """
        # 分块发送
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]

            event = await self.generate(
                event_type=event_type,
                data={
                    "text": chunk,
                    "index": i,
                    "total_length": len(text),
                }
            )

            yield event

    async def stream_tool_execution(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式输出工具执行过程

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            tool_result: 工具结果（可选）

        Yields:
            格式化的事件字符串
        """
        # 工具调用开始
        yield await self.generate(
            event_type=StreamEventType.TOOL_EXECUTING,
            data={
                "tool_name": tool_name,
                "tool_input": tool_input,
                "status": "started",
            }
        )

        # 如果有结果，发送结果事件
        if tool_result is not None:
            yield await self.generate(
                event_type=StreamEventType.TOOL_RESULT,
                data={
                    "tool_name": tool_name,
                    "result": tool_result,
                    "status": "completed",
                }
            )

    async def stream_iteration(
        self,
        iteration: int,
        max_iterations: int,
        state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        流式输出迭代信息

        Args:
            iteration: 当前迭代次数
            max_iterations: 最大迭代次数
            state: 当前状态（可选）

        Returns:
            格式化的事件字符串
        """
        return await self.generate(
            event_type=StreamEventType.ITERATION,
            data={
                "iteration": iteration,
                "max_iterations": max_iterations,
                "state": state or {},
            }
        )

    async def stream_error(
        self,
        error: Exception,
        error_type: str = "general",
        recoverable: bool = True,
    ) -> str:
        """
        流式输出错误信息

        Args:
            error: 异常对象
            error_type: 错误类型
            recoverable: 是否可恢复

        Returns:
            格式化的事件字符串
        """
        return await self.generate(
            event_type=StreamEventType.ERROR,
            data={
                "error": str(error),
                "error_type": error_type,
                "error_class": type(error).__name__,
                "recoverable": recoverable,
            }
        )

    async def stream_completion(
        self,
        final_state: Dict[str, Any],
        success: bool = True,
    ) -> str:
        """
        流式输出完成信息

        Args:
            final_state: 最终状态
            success: 是否成功

        Returns:
            格式化的事件字符串
        """
        return await self.generate(
            event_type=StreamEventType.DONE,
            data={
                "final_state": final_state,
                "success": success,
                "stats": self.get_stats(),
            }
        )

    async def stream_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        usage_rate: float,
    ) -> str:
        """
        流式输出 Token 使用信息

        Args:
            input_tokens: 输入 Token 数
            output_tokens: 输出 Token 数
            total_tokens: 总 Token 数
            usage_rate: 使用率

        Returns:
            格式化的事件字符串
        """
        return await self.generate(
            event_type=StreamEventType.TOKEN_USAGE,
            data={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "usage_rate": usage_rate,
            }
        )

    async def stream_compression(
        self,
        status: str,  # "start", "success", "failed"
        original_count: Optional[int] = None,
        compressed_count: Optional[int] = None,
        error: Optional[str] = None,
    ) -> str:
        """
        流式输出压缩信息

        Args:
            status: 压缩状态
            original_count: 原始消息数
            compressed_count: 压缩后消息数
            error: 错误信息（如果失败）

        Returns:
            格式化的事件字符串
        """
        event_type_map = {
            "start": StreamEventType.COMPRESSION_START,
            "success": StreamEventType.COMPRESSION_SUCCESS,
            "failed": StreamEventType.COMPRESSION_FAILED,
        }

        data: Dict[str, Any] = {"status": status}

        if original_count is not None:
            data["original_count"] = original_count
        if compressed_count is not None:
            data["compressed_count"] = compressed_count
        if error is not None:
            data["error"] = error

        return await self.generate(
            event_type=event_type_map.get(status, StreamEventType.WARNING),
            data=data,
        )

    async def stream_subagent(
        self,
        action: str,  # "start", "complete"
        agent_id: str,
        agent_type: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        流式输出 SubAgent 事件

        Args:
            action: 动作类型
            agent_id: SubAgent ID
            agent_type: SubAgent 类型
            result: SubAgent 结果（可选）

        Returns:
            格式化的事件字符串
        """
        event_type_map = {
            "start": StreamEventType.SUBAGENT_START,
            "complete": StreamEventType.SUBAGENT_COMPLETE,
        }

        data: Dict[str, Any] = {
            "agent_id": agent_id,
            "agent_type": agent_type,
        }

        if result is not None:
            data["result"] = result

        return await self.generate(
            event_type=event_type_map.get(action, StreamEventType.WARNING),
            data=data,
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        获取流生成统计

        Returns:
            统计信息字典
        """
        return {
            **self._stats,
            "session_id": self.session_id,
        }

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "events_generated": 0,
            "bytes_sent": 0,
        }
        logger.info("流生成统计已重置")

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"StreamGenerator("
            f"session={self.session_id}, "
            f"events={stats['events_generated']}, "
            f"bytes={stats['bytes_sent']})"
        )
