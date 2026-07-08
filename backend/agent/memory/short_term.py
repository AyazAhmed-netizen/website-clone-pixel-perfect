"""
Short-Term Memory Manager

实现短期记忆层 - 当前会话上下文管理。

核心功能：
- 实时消息数组管理
- O(1) 查找性能
- 自动 Token 统计
- 消息角色分类
- 历史记录追踪
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..core.constants import estimate_token_count

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """消息角色类型"""
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class Message:
    """
    单条消息对象

    封装消息的所有元信息
    """

    # 消息角色
    role: MessageRole

    # 消息内容
    content: str | List[Dict[str, Any]]

    # 消息 ID
    message_id: str = ""

    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)

    # Token 数量（估算）
    token_count: int = 0

    # 工具调用 ID（仅 tool 角色）
    tool_use_id: Optional[str] = None

    # 工具名称（仅 tool 角色）
    tool_name: Optional[str] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        # 自动估算 Token 数量
        if self.token_count == 0:
            self.token_count = self._estimate_tokens()

        # 生成消息 ID
        if not self.message_id:
            self.message_id = f"{self.role}_{int(self.timestamp.timestamp() * 1000)}"

    def _estimate_tokens(self) -> int:
        """估算消息的 Token 数量"""
        if isinstance(self.content, str):
            return estimate_token_count(self.content)
        elif isinstance(self.content, list):
            # 列表格式（例如包含工具调用的内容）
            total = 0
            for item in self.content:
                if isinstance(item, dict):
                    # 估算字典内容的 Token
                    total += estimate_token_count(str(item))
                else:
                    total += estimate_token_count(str(item))
            return total
        return 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "role": self.role.value,
            "content": self.content,
        }

        # 添加可选字段
        if self.tool_use_id:
            result["tool_use_id"] = self.tool_use_id

        if self.tool_name:
            result["tool_name"] = self.tool_name

        return result


class ShortTermMemory:
    """
    短期记忆管理器

    管理当前会话的实时消息数组，提供 O(1) 查找和自动 Token 统计。
    """

    def __init__(self, max_messages: int = 1000):
        """
        初始化短期记忆

        Args:
            max_messages: 最大消息数量
        """
        self.max_messages = max_messages

        # 消息数组（按时间顺序）
        self._messages: List[Message] = []

        # 消息索引（message_id -> Message）O(1) 查找
        self._message_index: Dict[str, Message] = {}

        # 角色统计
        self._role_counts: Dict[MessageRole, int] = {
            role: 0 for role in MessageRole
        }

        # Token 统计
        self._total_tokens = 0

        logger.info(f"ShortTermMemory 初始化：max_messages={max_messages}")

    def add_message(
        self,
        role: str | MessageRole,
        content: str | List[Dict[str, Any]],
        **kwargs
    ) -> Message:
        """
        添加消息

        Args:
            role: 消息角色
            content: 消息内容
            **kwargs: 其他消息属性

        Returns:
            添加的消息对象
        """
        # 转换角色类型
        if isinstance(role, str):
            role = MessageRole(role)

        # 创建消息对象
        message = Message(
            role=role,
            content=content,
            **kwargs
        )

        # 检查容量限制
        if len(self._messages) >= self.max_messages:
            # 移除最早的消息
            self._remove_oldest()

        # 添加到数组
        self._messages.append(message)

        # 添加到索引
        self._message_index[message.message_id] = message

        # 更新统计
        self._role_counts[role] += 1
        self._total_tokens += message.token_count

        logger.debug(
            f"消息已添加：{role} ({message.token_count} tokens), "
            f"total={len(self._messages)}"
        )

        return message

    def add_user_message(self, content: str, **kwargs) -> Message:
        """添加用户消息"""
        return self.add_message(MessageRole.USER, content, **kwargs)

    def add_assistant_message(
        self,
        content: str | List[Dict[str, Any]],
        **kwargs
    ) -> Message:
        """添加助手消息"""
        return self.add_message(MessageRole.ASSISTANT, content, **kwargs)

    def add_tool_result(
        self,
        content: str,
        tool_use_id: str,
        tool_name: Optional[str] = None,
        **kwargs
    ) -> Message:
        """添加工具结果"""
        return self.add_message(
            MessageRole.TOOL,
            content,
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            **kwargs
        )

    def add_system_message(self, content: str, **kwargs) -> Message:
        """添加系统消息"""
        return self.add_message(MessageRole.SYSTEM, content, **kwargs)

    def get_message(self, message_id: str) -> Optional[Message]:
        """
        根据 ID 获取消息（O(1)）

        Args:
            message_id: 消息 ID

        Returns:
            消息对象，如果不存在则返回 None
        """
        return self._message_index.get(message_id)

    def get_messages(
        self,
        role: Optional[MessageRole] = None,
        limit: Optional[int] = None,
        reverse: bool = False,
    ) -> List[Message]:
        """
        获取消息列表

        Args:
            role: 按角色筛选（可选）
            limit: 限制数量（可选）
            reverse: 是否逆序（默认否，即从旧到新）

        Returns:
            消息列表
        """
        messages = self._messages

        # 按角色筛选
        if role is not None:
            messages = [msg for msg in messages if msg.role == role]

        # 逆序
        if reverse:
            messages = list(reversed(messages))

        # 限制数量
        if limit is not None:
            messages = messages[:limit]

        return messages

    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """
        获取最近的 N 条消息

        Args:
            count: 消息数量

        Returns:
            最近的消息列表
        """
        return self._messages[-count:]

    def get_messages_as_dicts(
        self,
        role: Optional[MessageRole] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取消息的字典格式（用于 API 调用）

        Args:
            role: 按角色筛选
            limit: 限制数量

        Returns:
            消息字典列表
        """
        messages = self.get_messages(role=role, limit=limit)
        return [msg.to_dict() for msg in messages]

    def get_conversation_context(self) -> str:
        """
        获取完整的对话上下文（文本格式）

        Returns:
            格式化的对话历史
        """
        lines = ["## Conversation History\n"]

        for msg in self._messages:
            timestamp = msg.timestamp.strftime("%H:%M:%S")
            role = msg.role.value.upper()

            if isinstance(msg.content, str):
                content = msg.content[:200]  # 截断长内容
            else:
                content = f"[Complex content with {len(msg.content)} items]"

            lines.append(f"[{timestamp}] {role}: {content}")

        return "\n".join(lines)

    def clear(self):
        """清空所有消息"""
        self._messages.clear()
        self._message_index.clear()
        self._role_counts = {role: 0 for role in MessageRole}
        self._total_tokens = 0

        logger.info("短期记忆已清空")

    def _remove_oldest(self):
        """移除最早的消息"""
        if not self._messages:
            return

        oldest = self._messages.pop(0)

        # 从索引移除
        self._message_index.pop(oldest.message_id, None)

        # 更新统计
        self._role_counts[oldest.role] -= 1
        self._total_tokens -= oldest.token_count

        logger.debug(f"移除最早消息：{oldest.message_id}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据字典
        """
        return {
            "total_messages": len(self._messages),
            "total_tokens": self._total_tokens,
            "role_counts": {
                role.value: count
                for role, count in self._role_counts.items()
            },
            "avg_tokens_per_message": (
                self._total_tokens / len(self._messages)
                if self._messages else 0
            ),
            "oldest_message": (
                self._messages[0].timestamp.isoformat()
                if self._messages else None
            ),
            "newest_message": (
                self._messages[-1].timestamp.isoformat()
                if self._messages else None
            ),
        }

    def __len__(self) -> int:
        """返回消息数量"""
        return len(self._messages)

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"ShortTermMemory("
            f"messages={stats['total_messages']}, "
            f"tokens={stats['total_tokens']})"
        )
