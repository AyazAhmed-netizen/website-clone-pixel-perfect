"""
System Prompt Generator (ga0)

实现 Claude Code 的动态系统提示生成器。

核心功能：
- 动态生成系统提示
- 工具描述注入
- 上下文信息整合
- SubAgent 能力说明
- 代码风格指导
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .constants import ExecutionContext

logger = logging.getLogger(__name__)


class SystemPromptGenerator:
    """
    系统提示生成器（ga0）

    根据执行上下文动态生成系统提示
    """

    def __init__(self, base_prompt: Optional[str] = None):
        """
        初始化提示生成器

        Args:
            base_prompt: 基础系统提示（可选）
        """
        self.base_prompt = base_prompt or self._get_default_base_prompt()

        logger.info("SystemPromptGenerator 初始化完成")

    def generate(
        self,
        context: ExecutionContext,
        tools: Optional[List[Dict[str, Any]]] = None,
        include_subagent_info: bool = True,
        include_compression_info: bool = True,
    ) -> str:
        """
        生成完整的系统提示

        Args:
            context: 执行上下文
            tools: 工具定义列表
            include_subagent_info: 是否包含 SubAgent 信息
            include_compression_info: 是否包含压缩信息

        Returns:
            完整的系统提示文本
        """
        sections = []

        # 1. 基础提示
        sections.append(self.base_prompt)

        # 2. 当前环境信息
        sections.append(self._generate_environment_section(context))

        # 3. 工具信息
        if tools:
            sections.append(self._generate_tools_section(tools))

        # 4. SubAgent 能力说明
        if include_subagent_info:
            sections.append(self._generate_subagent_section())

        # 5. 压缩信息（如果已压缩）
        if include_compression_info and context.is_compressed:
            sections.append(self._generate_compression_section(context))

        # 6. Token 使用警告
        if context.should_warn():
            sections.append(self._generate_token_warning(context))

        # 组合所有段落
        full_prompt = "\n\n".join(filter(None, sections))

        logger.debug(f"生成系统提示：{len(full_prompt)} 字符")

        return full_prompt

    def _get_default_base_prompt(self) -> str:
        """获取默认基础提示"""
        return """You are Nexting Agent, an advanced AI development assistant powered by Claude.

You are an expert software engineer with deep knowledge of:
- Full-stack web development
- System architecture design
- Code analysis and debugging
- Best practices and design patterns

Your capabilities:
- Understand and analyze codebases
- Plan and implement features
- Debug and fix issues
- Provide technical guidance
- Work autonomously on complex tasks

Core principles:
- Write clean, modular, well-documented code
- Follow best practices and coding standards
- Think carefully before acting
- Explain your reasoning when needed
- Ask for clarification when requirements are unclear"""

    def _generate_environment_section(self, context: ExecutionContext) -> str:
        """
        生成环境信息段落

        Args:
            context: 执行上下文

        Returns:
            环境信息文本
        """
        cwd = Path.cwd()

        sections = [
            "## Current Environment",
            "",
            f"- **Session ID**: {context.session_id}",
            f"- **Model**: {context.model}",
            f"- **Working Directory**: {cwd}",
            f"- **Timestamp**: {datetime.now().isoformat()}",
        ]

        # Token 使用信息
        if context.token_usage:
            sections.extend([
                "",
                "### Token Usage",
                f"- **Input**: {context.token_usage.get('input', 0):,}",
                f"- **Output**: {context.token_usage.get('output', 0):,}",
                f"- **Total**: {context.token_usage.get('total', 0):,}",
                f"- **Usage Rate**: {context.usage_rate:.1%}",
            ])

        return "\n".join(sections)

    def _generate_tools_section(self, tools: List[Dict[str, Any]]) -> str:
        """
        生成工具信息段落

        Args:
            tools: 工具定义列表

        Returns:
            工具信息文本
        """
        sections = [
            "## Available Tools",
            "",
            f"You have access to {len(tools)} tools:",
            "",
        ]

        # 工具分类
        tool_categories = self._categorize_tools(tools)

        for category, category_tools in tool_categories.items():
            sections.append(f"### {category}")
            sections.append("")

            for tool in category_tools[:5]:  # 只列出前 5 个
                name = tool.get("name", "unknown")
                description = tool.get("description", "")[:100]
                sections.append(f"- **{name}**: {description}")

            if len(category_tools) > 5:
                sections.append(f"- ... and {len(category_tools) - 5} more")

            sections.append("")

        return "\n".join(sections)

    def _categorize_tools(
        self,
        tools: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        将工具分类

        Args:
            tools: 工具列表

        Returns:
            分类后的工具字典
        """
        categories: Dict[str, List[Dict[str, Any]]] = {
            "File Operations": [],
            "Code Analysis": [],
            "SubAgent Management": [],
            "System Operations": [],
            "Other": [],
        }

        for tool in tools:
            name = tool.get("name", "").lower()

            if any(kw in name for kw in ["file", "read", "write", "edit"]):
                categories["File Operations"].append(tool)
            elif any(kw in name for kw in ["search", "analyze", "grep", "glob"]):
                categories["Code Analysis"].append(tool)
            elif "subagent" in name:
                categories["SubAgent Management"].append(tool)
            elif any(kw in name for kw in ["run", "command", "bash", "shell"]):
                categories["System Operations"].append(tool)
            else:
                categories["Other"].append(tool)

        # 移除空分类
        return {k: v for k, v in categories.items() if v}

    def _generate_subagent_section(self) -> str:
        """
        生成 SubAgent 能力说明段落

        Returns:
            SubAgent 信息文本
        """
        return """## SubAgent Capabilities

You can launch specialized SubAgents to handle complex tasks autonomously:

### Available SubAgent Types

1. **Explore Agent** (`agent_type="explore"`)
   - Fast codebase exploration and search
   - Read-only operations (list_files, read_file, grep, glob)
   - Use for: Finding files, searching code, understanding structure

2. **Plan Agent** (`agent_type="plan"`)
   - Implementation planning and architecture design
   - Read-only analysis
   - Use for: Planning features, designing solutions, analyzing approaches

3. **Debug Agent** (`agent_type="debug-specialist"`)
   - Bug investigation and diagnosis
   - Read-only + diagnostic tools
   - Use for: Debugging errors, tracing issues, analyzing failures

4. **General Agent** (`agent_type="general-purpose"`)
   - Full autonomy with all tools
   - Can modify files, run commands, etc.
   - Use for: Complete feature implementation, complex multi-step tasks

### When to Launch SubAgents

- **Exploration tasks**: Use Explore Agent for quick searches
- **Planning tasks**: Use Plan Agent before major implementations
- **Debugging**: Use Debug Agent when encountering errors
- **Complex implementations**: Use General Agent for autonomous execution

### How to Launch

Use the `launch_subagent` tool:

```python
launch_subagent(
    agent_type="explore",  # or "plan", "debug-specialist", "general-purpose"
    prompt="Your detailed task description",
    description="Short task summary",
    background=False  # Set true for async execution
)
```

**Note**: SubAgents run until task completion (no iteration limit).
**Concurrency Limit**: Maximum 10 SubAgents can run concurrently."""

    def _generate_compression_section(self, context: ExecutionContext) -> str:
        """
        生成压缩信息段落

        Args:
            context: 执行上下文

        Returns:
            压缩信息文本
        """
        if not context.compression_history:
            return ""

        last_compression = context.compression_history[-1]

        return f"""## Conversation Compression Notice

⚠️ **The conversation history has been compressed** to manage token usage.

- **Compression Count**: {len(context.compression_history)}
- **Last Compression**: {last_compression.get('timestamp', 'N/A')}
- **Original Messages**: {last_compression.get('original_count', 0)}
- **Compressed To**: {last_compression.get('compressed_count', 0)}

The compressed history contains a structured summary of:
- Background context
- Key decisions made
- Tool usage records
- User intent evolution
- Execution results
- Error handling
- Open issues
- Future plans

Recent messages are preserved in full."""

    def _generate_token_warning(self, context: ExecutionContext) -> str:
        """
        生成 Token 使用警告

        Args:
            context: 执行上下文

        Returns:
            警告文本
        """
        usage_rate = context.usage_rate

        if context.should_error():
            level = "🚨 CRITICAL"
            message = "Token usage is very high. Compression will trigger soon."
        elif context.should_warn():
            level = "⚠️ WARNING"
            message = "Token usage is elevated. Consider being more concise."
        else:
            return ""

        return f"""## Token Usage Alert

{level}: {message}

- **Current Usage**: {usage_rate:.1%}
- **Total Tokens**: {context.token_usage.get('total', 0):,}
- **Context Window**: {context.context_window:,}"""

    def add_custom_section(
        self,
        title: str,
        content: str,
        position: int = -1
    ):
        """
        添加自定义段落到基础提示

        Args:
            title: 段落标题
            content: 段落内容
            position: 插入位置（-1 表示末尾）
        """
        section = f"\n\n## {title}\n\n{content}"

        if position == -1:
            self.base_prompt += section
        else:
            # TODO: 实现指定位置插入
            self.base_prompt += section

        logger.info(f"添加自定义段落：{title}")

    def update_base_prompt(self, new_base: str):
        """
        更新基础提示

        Args:
            new_base: 新的基础提示
        """
        self.base_prompt = new_base
        logger.info("基础提示已更新")

    def __repr__(self) -> str:
        return f"SystemPromptGenerator(base_prompt_length={len(self.base_prompt)})"
