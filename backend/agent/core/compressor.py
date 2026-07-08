"""
Message Compressor (wU2)

实现 Claude Code 的 AU2 8段式结构化压缩算法。

当 token 使用率达到 92% 时自动触发压缩，将历史消息压缩为结构化摘要。

AU2 算法 8 段结构：
1. Background Context - 背景上下文
2. Key Decisions - 关键决策
3. Tool Usage Records - 工具使用记录
4. User Intent Evolution - 用户意图演变
5. Execution Results - 执行结果
6. Error Handling - 错误处理
7. Open Issues - 未解决问题
8. Future Plans - 未来计划
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime

from .constants import (
    CompressionConfig,
    ExecutionContext,
    estimate_token_count,
    AnalyticsEvent,
)

logger = logging.getLogger(__name__)


class AU2Algorithm:
    """
    AU2 8段式结构化压缩算法

    将对话历史压缩为 8 个语义段落
    """

    def __init__(self, config: CompressionConfig):
        """
        初始化 AU2 算法

        Args:
            config: 压缩配置
        """
        self.config = config

    def compress(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """
        执行 AU2 压缩

        Args:
            messages: 要压缩的消息列表
            context: 执行上下文

        Returns:
            压缩后的文本
        """
        logger.info(f"执行 AU2 压缩：{len(messages)} 条消息")

        # 提取各个段落
        segments = {}

        for segment_name in self.config.au2_segments:
            extractor = getattr(self, f"_extract_{segment_name}", None)
            if extractor:
                segments[segment_name] = extractor(messages, context)
            else:
                segments[segment_name] = ""

        # 组合为最终压缩文本
        compressed_text = self._format_compressed_text(segments)

        logger.info(f"AU2 压缩完成：{len(compressed_text)} 字符")

        return compressed_text

    # ============================================
    # 段落提取器
    # ============================================

    def _extract_background_context(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取背景上下文"""
        # 查找系统消息和最初的用户目标
        background = []

        for msg in messages[:5]:  # 只看前 5 条
            if msg.get("role") == "system":
                background.append(f"System: {msg.get('content', '')[:200]}")
            elif msg.get("role") == "user":
                background.append(f"Initial Goal: {msg.get('content', '')[:200]}")
                break

        return "\n".join(background) if background else "No background context"

    def _extract_key_decisions(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取关键决策"""
        decisions = []

        # 查找包含决策关键词的 assistant 消息
        decision_keywords = [
            "decided", "choose", "selected", "approach", "strategy",
            "plan", "will implement", "going to", "decided to"
        ]

        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                if any(keyword in content for keyword in decision_keywords):
                    decisions.append(msg.get("content", "")[:150])

        if decisions:
            return "Key decisions:\n- " + "\n- ".join(decisions[:5])
        return "No key decisions recorded"

    def _extract_tool_usage_records(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取工具使用记录"""
        tool_usage = []

        for msg in messages:
            if msg.get("role") == "tool":
                # Tool result message
                content = msg.get("content", "")
                # 提取工具名称和简短结果
                if content:
                    tool_usage.append(content[:100])

        if tool_usage:
            return f"Tools used ({len(tool_usage)} times):\n- " + "\n- ".join(tool_usage[-10:])
        return "No tools used"

    def _extract_user_intent_evolution(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取用户意图演变"""
        user_messages = [
            msg.get("content", "")[:150]
            for msg in messages
            if msg.get("role") == "user"
        ]

        if len(user_messages) > 1:
            return (
                f"User intent evolution ({len(user_messages)} requests):\n"
                f"1. Initial: {user_messages[0]}\n"
                f"2. Latest: {user_messages[-1]}"
            )
        elif user_messages:
            return f"User request: {user_messages[0]}"
        return "No user messages"

    def _extract_execution_results(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取执行结果"""
        results = []

        # 查找包含结果关键词的消息
        result_keywords = [
            "completed", "finished", "done", "success",
            "created", "updated", "modified", "implemented"
        ]

        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                if any(keyword in content for keyword in result_keywords):
                    results.append(msg.get("content", "")[:150])

        if results:
            return "Execution results:\n- " + "\n- ".join(results[-5:])
        return "No execution results"

    def _extract_error_handling(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取错误处理"""
        errors = []

        # 查找错误消息
        error_keywords = ["error", "failed", "exception", "bug", "issue"]

        for msg in messages:
            content = msg.get("content", "").lower()
            if any(keyword in content for keyword in error_keywords):
                errors.append(msg.get("content", "")[:150])

        if errors:
            return f"Errors encountered ({len(errors)} times):\n- " + "\n- ".join(errors[-3:])
        return "No errors encountered"

    def _extract_open_issues(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取未解决问题"""
        issues = []

        # 查找包含问题关键词的消息
        issue_keywords = [
            "todo", "need to", "should", "pending", "waiting",
            "incomplete", "not yet", "still need"
        ]

        for msg in messages[-20:]:  # 只看最近 20 条
            content = msg.get("content", "").lower()
            if any(keyword in content for keyword in issue_keywords):
                issues.append(msg.get("content", "")[:150])

        if issues:
            return "Open issues:\n- " + "\n- ".join(issues[:5])
        return "No open issues"

    def _extract_future_plans(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> str:
        """提取未来计划"""
        plans = []

        # 查找包含计划关键词的消息
        plan_keywords = [
            "next", "will", "going to", "plan to", "intend to",
            "future", "later", "upcoming"
        ]

        for msg in messages[-10:]:  # 只看最近 10 条
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                if any(keyword in content for keyword in plan_keywords):
                    plans.append(msg.get("content", "")[:150])

        if plans:
            return "Future plans:\n- " + "\n- ".join(plans[-3:])
        return "No future plans"

    # ============================================
    # 格式化
    # ============================================

    def _format_compressed_text(self, segments: Dict[str, str]) -> str:
        """
        将段落组合为最终压缩文本

        Args:
            segments: 各个段落的内容

        Returns:
            格式化的压缩文本
        """
        parts = ["## Compressed Conversation History (AU2 Algorithm)\n"]

        segment_titles = {
            "background_context": "📋 Background Context",
            "key_decisions": "🎯 Key Decisions",
            "tool_usage_records": "🔧 Tool Usage",
            "user_intent_evolution": "💭 User Intent Evolution",
            "execution_results": "✅ Execution Results",
            "error_handling": "❌ Error Handling",
            "open_issues": "⚠️  Open Issues",
            "future_plans": "📅 Future Plans",
        }

        for segment_name in self.config.au2_segments:
            title = segment_titles.get(segment_name, segment_name)
            content = segments.get(segment_name, "")

            if content and content != f"No {segment_name.replace('_', ' ')}":
                parts.append(f"\n### {title}\n{content}\n")

        return "\n".join(parts)


class MessageCompressor:
    """
    消息压缩器（wU2）

    当 token 使用率达到阈值时自动压缩历史消息
    """

    def __init__(self, config: CompressionConfig = None):
        """
        初始化消息压缩器

        Args:
            config: 压缩配置（可选）
        """
        self.config = config or CompressionConfig()
        self.au2 = AU2Algorithm(self.config)

    async def compress_if_needed(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> Tuple[List[Dict[str, str]], bool]:
        """
        检查并在需要时压缩消息

        Args:
            messages: 当前消息列表
            context: 执行上下文

        Returns:
            (处理后的消息列表, 是否执行了压缩)
        """
        # 检查是否启用压缩
        if not self.config.enabled:
            return messages, False

        # 检查是否需要压缩
        if not context.should_compress():
            return messages, False

        logger.info(
            f"Token 使用率 {context.usage_rate:.1%} 达到压缩阈值 "
            f"{self.config.threshold:.1%}，开始压缩..."
        )

        try:
            # 执行压缩
            compressed_messages = await self._compress(messages, context)

            # 记录压缩成功
            compression_record = {
                "timestamp": datetime.now().isoformat(),
                "original_count": len(messages),
                "compressed_count": len(compressed_messages),
                "original_usage": context.usage_rate,
            }
            context.compression_history.append(compression_record)
            context.is_compressed = True

            logger.info(
                f"压缩完成：{len(messages)} -> {len(compressed_messages)} 条消息"
            )

            # 触发分析事件
            self._record_analytics(
                AnalyticsEvent.AUTO_COMPACT_SUCCEEDED,
                {
                    "originalMessageCount": len(messages),
                    "compactedMessageCount": len(compressed_messages),
                    "tokenUsageRate": context.usage_rate,
                }
            )

            return compressed_messages, True

        except Exception as e:
            logger.error(f"消息压缩失败: {e}", exc_info=True)

            # 触发失败事件
            self._record_analytics(
                AnalyticsEvent.AUTO_COMPACT_FAILED,
                {"error": str(e)}
            )

            return messages, False

    async def _compress(
        self,
        messages: List[Dict[str, str]],
        context: ExecutionContext,
    ) -> List[Dict[str, str]]:
        """
        执行实际的压缩操作

        保留：
        1. 系统消息
        2. 最近 N 条消息
        3. 将其余消息压缩为单条摘要消息

        Args:
            messages: 原始消息列表
            context: 执行上下文

        Returns:
            压缩后的消息列表
        """
        # 分离系统消息和对话消息
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        conversation_messages = [msg for msg in messages if msg.get("role") != "system"]

        # 如果消息不够多，不压缩
        if len(conversation_messages) <= self.config.keep_recent_messages:
            return messages

        # 保留最近的消息
        recent_messages = conversation_messages[-self.config.keep_recent_messages:]

        # 要压缩的消息
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

        return compressed_messages

    def _record_analytics(self, event_name: str, data: Dict[str, Any]):
        """记录分析事件（占位符）"""
        logger.info(f"Analytics: {event_name} - {data}")
