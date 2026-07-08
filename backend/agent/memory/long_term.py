"""
Long-Term Memory Manager

实现长期记忆层 - CLAUDE.md 系统。

核心功能：
- CLAUDE.md 文件管理
- 项目上下文持久化
- 用户偏好存储
- 跨会话记忆恢复
- 代码风格指导
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ClaudeMdConfig:
    """
    CLAUDE.md 配置

    定义 CLAUDE.md 文件的标准结构
    """

    # 项目信息
    project_name: str = ""
    project_description: str = ""
    tech_stack: List[str] = field(default_factory=list)

    # 用户偏好
    language_preference: str = "中文"  # 默认中文回复
    code_style: Dict[str, str] = field(default_factory=dict)
    naming_conventions: Dict[str, str] = field(default_factory=dict)

    # 开发环境
    working_directory: str = ""
    python_version: str = ""
    node_version: str = ""
    environment_vars: Dict[str, str] = field(default_factory=dict)

    # 工作流程
    development_workflow: List[str] = field(default_factory=list)
    testing_strategy: str = ""
    deployment_process: str = ""

    # 安全配置
    security_notes: List[str] = field(default_factory=list)
    sensitive_files: List[str] = field(default_factory=list)

    # 自定义指令
    custom_instructions: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式

        Returns:
            CLAUDE.md 文件内容
        """
        sections = []

        # 标题
        sections.append("# Claude Project Instructions\n")
        sections.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 项目信息
        if self.project_name or self.project_description:
            sections.append("## 📋 Project Information\n")
            if self.project_name:
                sections.append(f"**Project Name:** {self.project_name}\n")
            if self.project_description:
                sections.append(f"**Description:** {self.project_description}\n")
            if self.tech_stack:
                sections.append("**Tech Stack:**")
                for tech in self.tech_stack:
                    sections.append(f"  - {tech}")
                sections.append("")

        # 用户偏好
        sections.append("## 🌍 User Preferences\n")
        sections.append(f"- **Language:** {self.language_preference}")
        sections.append("- **Response Style:** Concise and technical")
        if self.code_style:
            sections.append("\n**Code Style:**")
            for key, value in self.code_style.items():
                sections.append(f"  - {key}: {value}")
        sections.append("")

        # 开发环境
        if self.working_directory or self.python_version or self.node_version:
            sections.append("## 🔧 Development Environment\n")
            if self.working_directory:
                sections.append(f"**Working Directory:** `{self.working_directory}`")
            if self.python_version:
                sections.append(f"**Python Version:** {self.python_version}")
            if self.node_version:
                sections.append(f"**Node Version:** {self.node_version}")
            sections.append("")

        # 工作流程
        if self.development_workflow:
            sections.append("## 📝 Development Workflow\n")
            for step in self.development_workflow:
                sections.append(f"- {step}")
            sections.append("")

        # 安全配置
        if self.security_notes:
            sections.append("## 🔒 Security Guidelines\n")
            for note in self.security_notes:
                sections.append(f"- {note}")
            sections.append("")

        # 自定义指令
        if self.custom_instructions:
            sections.append("## 💡 Custom Instructions\n")
            for instruction in self.custom_instructions:
                sections.append(f"- {instruction}")
            sections.append("")

        return "\n".join(sections)

    @classmethod
    def from_markdown(cls, content: str) -> ClaudeMdConfig:
        """
        从 Markdown 内容解析配置

        Args:
            content: CLAUDE.md 文件内容

        Returns:
            配置对象
        """
        config = cls()

        # TODO: 实现 Markdown 解析逻辑
        # 这里可以使用正则表达式或 Markdown 解析库来提取各个部分

        return config


class LongTermMemory:
    """
    长期记忆管理器

    管理 CLAUDE.md 文件，实现跨会话的项目记忆和用户偏好持久化。
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        claude_md_path: Optional[Path] = None,
    ):
        """
        初始化长期记忆

        Args:
            project_root: 项目根目录
            claude_md_path: CLAUDE.md 文件路径（可选）
        """
        self.project_root = project_root or Path.cwd()
        self.claude_md_path = claude_md_path or self.project_root / "CLAUDE.md"

        # 配置对象
        self.config: Optional[ClaudeMdConfig] = None

        # 是否已加载
        self._loaded = False

        logger.info(f"LongTermMemory 初始化：{self.claude_md_path}")

    def load(self) -> ClaudeMdConfig:
        """
        加载 CLAUDE.md 文件

        Returns:
            配置对象
        """
        if self.claude_md_path.exists():
            logger.info(f"加载 CLAUDE.md：{self.claude_md_path}")

            try:
                content = self.claude_md_path.read_text(encoding="utf-8")
                self.config = ClaudeMdConfig.from_markdown(content)
                self._loaded = True

                logger.info("CLAUDE.md 加载成功")

            except Exception as e:
                logger.error(f"加载 CLAUDE.md 失败：{e}", exc_info=True)
                self.config = ClaudeMdConfig()

        else:
            logger.info("CLAUDE.md 不存在，使用默认配置")
            self.config = ClaudeMdConfig()

        return self.config

    def save(self, config: Optional[ClaudeMdConfig] = None):
        """
        保存配置到 CLAUDE.md 文件

        Args:
            config: 配置对象（可选，默认使用当前配置）
        """
        if config is not None:
            self.config = config

        if self.config is None:
            logger.warning("没有配置可保存")
            return

        try:
            # 生成 Markdown 内容
            content = self.config.to_markdown()

            # 确保目录存在
            self.claude_md_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            self.claude_md_path.write_text(content, encoding="utf-8")

            logger.info(f"CLAUDE.md 已保存：{self.claude_md_path}")

        except Exception as e:
            logger.error(f"保存 CLAUDE.md 失败：{e}", exc_info=True)

    def update_project_info(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tech_stack: Optional[List[str]] = None,
    ):
        """
        更新项目信息

        Args:
            name: 项目名称
            description: 项目描述
            tech_stack: 技术栈
        """
        if self.config is None:
            self.config = ClaudeMdConfig()

        if name is not None:
            self.config.project_name = name

        if description is not None:
            self.config.project_description = description

        if tech_stack is not None:
            self.config.tech_stack = tech_stack

        logger.info("项目信息已更新")

    def update_user_preferences(
        self,
        language: Optional[str] = None,
        code_style: Optional[Dict[str, str]] = None,
    ):
        """
        更新用户偏好

        Args:
            language: 语言偏好
            code_style: 代码风格
        """
        if self.config is None:
            self.config = ClaudeMdConfig()

        if language is not None:
            self.config.language_preference = language

        if code_style is not None:
            self.config.code_style.update(code_style)

        logger.info("用户偏好已更新")

    def add_custom_instruction(self, instruction: str):
        """
        添加自定义指令

        Args:
            instruction: 自定义指令
        """
        if self.config is None:
            self.config = ClaudeMdConfig()

        if instruction not in self.config.custom_instructions:
            self.config.custom_instructions.append(instruction)

            logger.info(f"自定义指令已添加：{instruction[:50]}...")

    def get_context_for_system_prompt(self) -> str:
        """
        获取用于系统提示的上下文

        Returns:
            格式化的上下文文本
        """
        if self.config is None:
            return ""

        sections = []

        # 项目信息
        if self.config.project_name:
            sections.append(f"**Project:** {self.config.project_name}")

        if self.config.tech_stack:
            sections.append(f"**Tech Stack:** {', '.join(self.config.tech_stack)}")

        # 用户偏好
        sections.append(f"**Language Preference:** {self.config.language_preference}")

        # 代码风格
        if self.config.code_style:
            style_items = [f"{k}: {v}" for k, v in self.config.code_style.items()]
            sections.append(f"**Code Style:** {', '.join(style_items)}")

        # 自定义指令
        if self.config.custom_instructions:
            sections.append("\n**Custom Instructions:**")
            for instruction in self.config.custom_instructions:
                sections.append(f"- {instruction}")

        return "\n".join(sections)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据字典
        """
        return {
            "claude_md_exists": self.claude_md_path.exists(),
            "claude_md_path": str(self.claude_md_path),
            "loaded": self._loaded,
            "project_name": self.config.project_name if self.config else None,
            "tech_stack_count": len(self.config.tech_stack) if self.config else 0,
            "custom_instructions_count": (
                len(self.config.custom_instructions) if self.config else 0
            ),
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"LongTermMemory("
            f"path={stats['claude_md_path']}, "
            f"loaded={stats['loaded']})"
        )
