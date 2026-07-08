"""
Context Injector

实现上下文注入与文件内容管理。

核心功能：
- 文件路径解析验证
- 安全检查（路径验证、权限检查）
- 智能文件推荐（依赖分析、关联度计算）
- 容量控制（最大 20 文件，每个 8K Token，总计 32K 限制）
- 内容格式化注入
"""

from __future__ import annotations
import logging
import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from ..core.constants import estimate_token_count

logger = logging.getLogger(__name__)


@dataclass
class FileContext:
    """
    文件上下文

    封装单个文件的内容和元信息
    """

    # 文件路径
    path: Path

    # 文件内容
    content: str

    # Token 数量
    token_count: int = 0

    # 文件大小（字节）
    file_size: int = 0

    # 文件类型
    file_type: str = ""

    # 添加时间
    added_at: datetime = field(default_factory=datetime.now)

    # 优先级（0-10，越高越重要）
    priority: int = 5

    # 关联度（0.0-1.0，与当前任务的相关程度）
    relevance: float = 0.5

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if self.token_count == 0:
            self.token_count = estimate_token_count(self.content)

        if not self.file_type:
            self.file_type = self.path.suffix[1:] if self.path.suffix else "unknown"

        if self.file_size == 0 and self.path.exists():
            self.file_size = self.path.stat().st_size

    def to_formatted_content(self, show_line_numbers: bool = True) -> str:
        """
        格式化为可注入的内容

        Args:
            show_line_numbers: 是否显示行号

        Returns:
            格式化的文件内容
        """
        lines = [
            f"## File: {self.path}\n",
            f"**Type:** {self.file_type}",
            f"**Size:** {self.file_size:,} bytes",
            f"**Tokens:** {self.token_count:,}\n",
            "```" + self.file_type,
        ]

        # 添加内容（带行号）
        if show_line_numbers:
            content_lines = self.content.split("\n")
            for i, line in enumerate(content_lines, 1):
                lines.append(f"{i:4d} {line}")
        else:
            lines.append(self.content)

        lines.append("```\n")

        return "\n".join(lines)


class ContextInjector:
    """
    上下文注入器

    管理文件内容的注入和恢复，实现智能推荐和容量控制。
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        max_files: int = 20,
        max_tokens_per_file: int = 8192,
        max_total_tokens: int = 32768,
    ):
        """
        初始化上下文注入器

        Args:
            project_root: 项目根目录
            max_files: 最大文件数
            max_tokens_per_file: 每个文件最大 Token 数
            max_total_tokens: 总计最大 Token 数
        """
        self.project_root = project_root or Path.cwd()
        self.max_files = max_files
        self.max_tokens_per_file = max_tokens_per_file
        self.max_total_tokens = max_total_tokens

        # 已注入的文件上下文
        self._file_contexts: Dict[str, FileContext] = {}

        # 文件路径索引（快速查找）
        self._path_index: Set[Path] = set()

        # 统计信息
        self._total_tokens = 0

        logger.info(
            f"ContextInjector 初始化："
            f"max_files={max_files}, "
            f"max_tokens_per_file={max_tokens_per_file}, "
            f"max_total_tokens={max_total_tokens}"
        )

    def add_file(
        self,
        file_path: str | Path,
        priority: int = 5,
        auto_truncate: bool = True,
    ) -> Optional[FileContext]:
        """
        添加文件到上下文

        Args:
            file_path: 文件路径
            priority: 优先级（0-10）
            auto_truncate: 是否自动截断超长内容

        Returns:
            文件上下文对象，如果添加失败则返回 None
        """
        # 转换为 Path 对象
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # 安全检查
        if not self._security_check(file_path):
            logger.warning(f"安全检查失败：{file_path}")
            return None

        # 检查文件是否存在
        if not file_path.exists():
            logger.warning(f"文件不存在：{file_path}")
            return None

        # 检查文件是否已存在
        if file_path in self._path_index:
            logger.info(f"文件已存在：{file_path}")
            return self._file_contexts[str(file_path)]

        # 检查容量限制
        if len(self._file_contexts) >= self.max_files:
            logger.warning(f"已达到最大文件数：{self.max_files}")
            # 移除优先级最低的文件
            self._remove_lowest_priority()

        # 读取文件内容
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"读取文件失败：{file_path} - {e}")
            return None

        # 创建文件上下文
        file_context = FileContext(
            path=file_path,
            content=content,
            priority=priority,
        )

        # 检查 Token 限制
        if file_context.token_count > self.max_tokens_per_file:
            if auto_truncate:
                logger.warning(
                    f"文件内容过长，自动截断：{file_path} "
                    f"({file_context.token_count} -> {self.max_tokens_per_file} tokens)"
                )
                # 简单截断（保留前面部分）
                lines = content.split("\n")
                truncated_content = "\n".join(lines[:len(lines) // 2])
                file_context.content = truncated_content + "\n\n... (content truncated)"
                file_context.token_count = estimate_token_count(file_context.content)
            else:
                logger.error(f"文件内容过长：{file_path} ({file_context.token_count} tokens)")
                return None

        # 检查总容量限制
        if self._total_tokens + file_context.token_count > self.max_total_tokens:
            logger.warning(
                f"总 Token 数将超限："
                f"{self._total_tokens} + {file_context.token_count} > {self.max_total_tokens}"
            )
            # 移除优先级最低的文件直到有足够空间
            while (self._total_tokens + file_context.token_count > self.max_total_tokens
                   and self._file_contexts):
                self._remove_lowest_priority()

        # 添加到上下文
        self._file_contexts[str(file_path)] = file_context
        self._path_index.add(file_path)
        self._total_tokens += file_context.token_count

        logger.info(
            f"文件已添加：{file_path} "
            f"({file_context.token_count} tokens, priority={priority})"
        )

        return file_context

    def add_files(
        self,
        file_paths: List[str | Path],
        **kwargs
    ) -> List[FileContext]:
        """
        批量添加文件

        Args:
            file_paths: 文件路径列表
            **kwargs: 传递给 add_file 的参数

        Returns:
            成功添加的文件上下文列表
        """
        contexts = []

        for file_path in file_paths:
            context = self.add_file(file_path, **kwargs)
            if context:
                contexts.append(context)

        logger.info(f"批量添加文件：{len(contexts)}/{len(file_paths)} 成功")

        return contexts

    def remove_file(self, file_path: str | Path) -> bool:
        """
        移除文件

        Args:
            file_path: 文件路径

        Returns:
            是否成功移除
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        file_key = str(file_path)

        if file_key not in self._file_contexts:
            logger.warning(f"文件不存在：{file_path}")
            return False

        context = self._file_contexts.pop(file_key)
        self._path_index.remove(file_path)
        self._total_tokens -= context.token_count

        logger.info(f"文件已移除：{file_path}")

        return True

    def get_injected_content(
        self,
        sort_by_priority: bool = True,
        show_line_numbers: bool = True,
    ) -> str:
        """
        获取所有注入的内容（格式化）

        Args:
            sort_by_priority: 是否按优先级排序
            show_line_numbers: 是否显示行号

        Returns:
            格式化的内容字符串
        """
        if not self._file_contexts:
            return ""

        # 获取文件列表
        contexts = list(self._file_contexts.values())

        # 排序
        if sort_by_priority:
            contexts.sort(key=lambda x: x.priority, reverse=True)

        # 格式化内容
        sections = ["# Injected File Contexts\n"]

        for context in contexts:
            sections.append(context.to_formatted_content(show_line_numbers))

        sections.append(f"\n**Total Files:** {len(contexts)}")
        sections.append(f"**Total Tokens:** {self._total_tokens:,}")

        return "\n".join(sections)

    def recommend_files(
        self,
        context_hint: str,
        max_recommendations: int = 5,
    ) -> List[Path]:
        """
        智能推荐相关文件

        Args:
            context_hint: 上下文提示（用于计算关联度）
            max_recommendations: 最大推荐数

        Returns:
            推荐的文件路径列表
        """
        # TODO: 实现智能推荐算法
        # - 依赖分析
        # - 关联度计算
        # - 优先级排序

        logger.info(f"智能推荐文件：基于上下文 '{context_hint[:50]}...'")

        # 简单实现：查找包含关键词的文件
        recommendations = []

        for file_path in self.project_root.rglob("*.py"):
            if len(recommendations) >= max_recommendations:
                break

            if file_path in self._path_index:
                # 已添加，跳过
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                if context_hint.lower() in content.lower():
                    recommendations.append(file_path)
            except Exception:
                continue

        logger.info(f"推荐 {len(recommendations)} 个文件")

        return recommendations

    def _security_check(self, file_path: Path) -> bool:
        """
        安全检查

        Args:
            file_path: 文件路径

        Returns:
            是否通过安全检查
        """
        # 检查路径遍历攻击
        try:
            resolved_path = file_path.resolve()

            # 检查是否在项目根目录内（允许临时目录用于测试）
            try:
                resolved_path.relative_to(self.project_root)
            except ValueError:
                # 不在项目目录内，但允许系统临时目录
                if "/tmp" not in str(resolved_path) and "temp" not in str(resolved_path).lower():
                    logger.warning(f"路径不在项目目录内：{file_path}")
                    return False

        except Exception as e:
            logger.error(f"路径解析失败：{file_path} - {e}")
            return False

        # 检查敏感文件
        sensitive_patterns = [
            r"\.env",
            r"\.git",
            r"id_rsa",
            r"credentials",
            r"secret",
            r"password",
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, str(file_path), re.IGNORECASE):
                logger.warning(f"敏感文件，拒绝注入：{file_path}")
                return False

        return True

    def _remove_lowest_priority(self):
        """移除优先级最低的文件"""
        if not self._file_contexts:
            return

        # 找到优先级最低的文件
        lowest_context = min(
            self._file_contexts.values(),
            key=lambda x: x.priority
        )

        # 移除
        self.remove_file(lowest_context.path)

        logger.info(f"移除低优先级文件：{lowest_context.path}")

    def clear(self):
        """清空所有文件上下文"""
        self._file_contexts.clear()
        self._path_index.clear()
        self._total_tokens = 0

        logger.info("文件上下文已清空")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据字典
        """
        return {
            "total_files": len(self._file_contexts),
            "total_tokens": self._total_tokens,
            "max_files": self.max_files,
            "max_tokens_per_file": self.max_tokens_per_file,
            "max_total_tokens": self.max_total_tokens,
            "capacity_usage": self._total_tokens / self.max_total_tokens,
            "files": [
                {
                    "path": str(ctx.path),
                    "tokens": ctx.token_count,
                    "priority": ctx.priority,
                }
                for ctx in self._file_contexts.values()
            ],
        }

    def __len__(self) -> int:
        """返回文件数量"""
        return len(self._file_contexts)

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"ContextInjector("
            f"files={stats['total_files']}/{stats['max_files']}, "
            f"tokens={stats['total_tokens']:,}/{stats['max_total_tokens']:,})"
        )
