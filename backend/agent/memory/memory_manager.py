"""
Memory Manager

统一的记忆管理器，整合三层记忆架构。

核心功能：
- 短期记忆管理（实时消息）
- 中期记忆管理（AU2 压缩）
- 长期记忆管理（CLAUDE.md）
- 上下文注入管理（文件内容）
- 智能记忆切换和恢复
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from .short_term import ShortTermMemory, MessageRole
from .mid_term import MidTermMemory
from .long_term import LongTermMemory, ClaudeMdConfig
from .context_injector import ContextInjector, FileContext
from ..core.constants import ExecutionContext

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    统一记忆管理器

    整合三层记忆架构，提供统一的记忆管理接口。
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        enable_long_term: bool = True,
        enable_context_injection: bool = True,
    ):
        """
        初始化记忆管理器

        Args:
            project_root: 项目根目录
            enable_long_term: 是否启用长期记忆
            enable_context_injection: 是否启用上下文注入
        """
        self.project_root = project_root or Path.cwd()
        self.enable_long_term = enable_long_term
        self.enable_context_injection = enable_context_injection

        # 三层记忆
        self.short_term = ShortTermMemory(max_messages=1000)
        self.mid_term = MidTermMemory()
        self.long_term = None
        self.context_injector = None

        # 初始化长期记忆
        if self.enable_long_term:
            self.long_term = LongTermMemory(project_root=self.project_root)
            # 自动加载 CLAUDE.md
            self.long_term.load()

        # 初始化上下文注入器
        if self.enable_context_injection:
            self.context_injector = ContextInjector(project_root=self.project_root)

        logger.info(
            f"MemoryManager 初始化："
            f"long_term={enable_long_term}, "
            f"context_injection={enable_context_injection}"
        )

    async def add_user_message(self, content: str, **kwargs):
        """
        添加用户消息

        Args:
            content: 消息内容
            **kwargs: 其他消息属性
        """
        self.short_term.add_user_message(content, **kwargs)

        logger.debug(f"用户消息已添加：{content[:50]}...")

    async def add_assistant_message(
        self,
        content: str | List[Dict[str, Any]],
        **kwargs
    ):
        """
        添加助手消息

        Args:
            content: 消息内容
            **kwargs: 其他消息属性
        """
        self.short_term.add_assistant_message(content, **kwargs)

        logger.debug("助手消息已添加")

    async def add_tool_result(
        self,
        content: str,
        tool_use_id: str,
        tool_name: Optional[str] = None,
        **kwargs
    ):
        """
        添加工具结果

        Args:
            content: 结果内容
            tool_use_id: 工具调用 ID
            tool_name: 工具名称
            **kwargs: 其他消息属性
        """
        self.short_term.add_tool_result(
            content,
            tool_use_id,
            tool_name=tool_name,
            **kwargs
        )

        logger.debug(f"工具结果已添加：{tool_name}")

    async def get_messages_for_api(
        self,
        context: ExecutionContext,
        include_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取用于 API 调用的消息列表

        自动处理压缩和上下文注入

        Args:
            context: 执行上下文
            include_system: 是否包含系统消息

        Returns:
            消息列表
        """
        # 获取短期记忆中的消息
        messages = self.short_term.get_messages_as_dicts()

        # 检查是否需要压缩
        compressed_messages, did_compress = await self.mid_term.compress_if_needed(
            messages, context
        )

        if did_compress:
            logger.info("消息已自动压缩")
            messages = compressed_messages

        # 如果启用了上下文注入，添加文件上下文
        if self.enable_context_injection and self.context_injector:
            if len(self.context_injector) > 0:
                # 生成注入的内容
                injected_content = self.context_injector.get_injected_content()

                # 添加为系统消息
                if include_system:
                    messages.insert(0, {
                        "role": "system",
                        "content": f"## File Contexts\n\n{injected_content}",
                    })

                logger.info(
                    f"已注入 {len(self.context_injector)} 个文件上下文 "
                    f"({self.context_injector._total_tokens} tokens)"
                )

        return messages

    async def inject_file(
        self,
        file_path: str | Path,
        priority: int = 5,
    ) -> Optional[FileContext]:
        """
        注入文件内容到上下文

        Args:
            file_path: 文件路径
            priority: 优先级

        Returns:
            文件上下文对象
        """
        if not self.enable_context_injection or not self.context_injector:
            logger.warning("上下文注入未启用")
            return None

        return self.context_injector.add_file(file_path, priority=priority)

    async def inject_files(
        self,
        file_paths: List[str | Path],
        **kwargs
    ) -> List[FileContext]:
        """
        批量注入文件

        Args:
            file_paths: 文件路径列表
            **kwargs: 传递给 add_file 的参数

        Returns:
            成功添加的文件上下文列表
        """
        if not self.enable_context_injection or not self.context_injector:
            logger.warning("上下文注入未启用")
            return []

        return self.context_injector.add_files(file_paths, **kwargs)

    def get_long_term_context(self) -> str:
        """
        获取长期记忆上下文（用于系统提示）

        Returns:
            格式化的长期记忆上下文
        """
        if not self.enable_long_term or not self.long_term:
            return ""

        return self.long_term.get_context_for_system_prompt()

    def update_long_term_memory(
        self,
        project_name: Optional[str] = None,
        description: Optional[str] = None,
        tech_stack: Optional[List[str]] = None,
        custom_instruction: Optional[str] = None,
    ):
        """
        更新长期记忆

        Args:
            project_name: 项目名称
            description: 项目描述
            tech_stack: 技术栈
            custom_instruction: 自定义指令
        """
        if not self.enable_long_term or not self.long_term:
            logger.warning("长期记忆未启用")
            return

        # 更新项目信息
        if project_name or description or tech_stack:
            self.long_term.update_project_info(
                name=project_name,
                description=description,
                tech_stack=tech_stack,
            )

        # 添加自定义指令
        if custom_instruction:
            self.long_term.add_custom_instruction(custom_instruction)

        # 保存到文件
        self.long_term.save()

        logger.info("长期记忆已更新")

    def clear_short_term(self):
        """清空短期记忆"""
        self.short_term.clear()
        logger.info("短期记忆已清空")

    def clear_mid_term(self):
        """清空中期记忆（压缩历史）"""
        self.mid_term.clear_history()
        logger.info("中期记忆已清空")

    def clear_injected_files(self):
        """清空注入的文件"""
        if self.enable_context_injection and self.context_injector:
            self.context_injector.clear()
            logger.info("注入的文件已清空")

    def clear_all(self):
        """清空所有记忆"""
        self.clear_short_term()
        self.clear_mid_term()
        self.clear_injected_files()
        logger.info("所有记忆已清空")

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        获取完整的记忆统计信息

        Returns:
            统计数据字典
        """
        stats = {
            "short_term": self.short_term.get_stats(),
            "mid_term": self.mid_term.get_stats(),
        }

        if self.enable_long_term and self.long_term:
            stats["long_term"] = self.long_term.get_stats()
        else:
            stats["long_term"] = None

        if self.enable_context_injection and self.context_injector:
            stats["context_injection"] = self.context_injector.get_stats()
        else:
            stats["context_injection"] = None

        return stats

    def get_memory_summary(self) -> str:
        """
        获取记忆摘要（文本格式）

        Returns:
            格式化的记忆摘要
        """
        lines = ["# Memory System Summary\n"]

        # 短期记忆
        short_stats = self.short_term.get_stats()
        lines.append("## 📋 Short-Term Memory")
        lines.append(f"- **Messages:** {short_stats['total_messages']}")
        lines.append(f"- **Tokens:** {short_stats['total_tokens']:,}")
        lines.append(f"- **User Messages:** {short_stats['role_counts']['user']}")
        lines.append(f"- **Assistant Messages:** {short_stats['role_counts']['assistant']}\n")

        # 中期记忆
        mid_stats = self.mid_term.get_stats()
        lines.append("## 🗜️  Mid-Term Memory")
        lines.append(f"- **Total Compressions:** {mid_stats['total_compressions']}")
        lines.append(f"- **Tokens Saved:** {mid_stats['total_tokens_saved']:,}")
        lines.append(f"- **Avg Compression Ratio:** {mid_stats['avg_compression_ratio']:.1%}\n")

        # 长期记忆
        if self.enable_long_term and self.long_term:
            long_stats = self.long_term.get_stats()
            lines.append("## 💾 Long-Term Memory")
            lines.append(f"- **CLAUDE.md Exists:** {long_stats['claude_md_exists']}")
            lines.append(f"- **Project:** {long_stats['project_name'] or 'N/A'}")
            lines.append(f"- **Tech Stack Items:** {long_stats['tech_stack_count']}")
            lines.append(f"- **Custom Instructions:** {long_stats['custom_instructions_count']}\n")

        # 上下文注入
        if self.enable_context_injection and self.context_injector:
            ctx_stats = self.context_injector.get_stats()
            lines.append("## 📁 Context Injection")
            lines.append(f"- **Injected Files:** {ctx_stats['total_files']}/{ctx_stats['max_files']}")
            lines.append(f"- **Tokens:** {ctx_stats['total_tokens']:,}/{ctx_stats['max_total_tokens']:,}")
            lines.append(f"- **Capacity Usage:** {ctx_stats['capacity_usage']:.1%}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        stats = self.get_memory_stats()
        short = stats.get("short_term", {})
        mid = stats.get("mid_term", {})

        return (
            f"MemoryManager("
            f"short={short.get('total_messages', 0)}msg, "
            f"mid={mid.get('total_compressions', 0)}comp, "
            f"long={'✓' if self.enable_long_term else '✗'}, "
            f"inject={'✓' if self.enable_context_injection else '✗'})"
        )
