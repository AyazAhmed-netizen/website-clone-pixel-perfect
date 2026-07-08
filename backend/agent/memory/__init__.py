"""
Memory & Context Management System

实现 Claude Code 风格的三层记忆架构：
- 短期记忆层：当前会话上下文（实时消息数组）
- 中期记忆层：AU2 8段式结构化压缩
- 长期记忆层：CLAUDE.md 系统（跨会话持久化）

核心组件：
- ShortTermMemory: 短期记忆管理器
- MidTermMemory: 中期记忆管理器（整合 AU2 压缩）
- LongTermMemory: 长期记忆管理器（CLAUDE.md）
- ContextInjector: 上下文注入器（文件内容管理）
- MemoryManager: 统一记忆管理器
"""

from .short_term import ShortTermMemory
from .mid_term import MidTermMemory
from .long_term import LongTermMemory, ClaudeMdConfig
from .context_injector import ContextInjector, FileContext
from .memory_manager import MemoryManager

__all__ = [
    # 短期记忆
    "ShortTermMemory",

    # 中期记忆
    "MidTermMemory",

    # 长期记忆
    "LongTermMemory",
    "ClaudeMdConfig",

    # 上下文注入
    "ContextInjector",
    "FileContext",

    # 统一管理器
    "MemoryManager",
]
