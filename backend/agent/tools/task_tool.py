"""
Task Tool (cX - SubAgent Launcher)

实现Task工具,用于动态启动SubAgent执行复杂任务。

功能:
- 启动不同类型的SubAgent (Explore, Plan, Debug, General)
- 支持同步和异步执行
- 提供SubAgent状态查询
- 最多10个并发SubAgent

SubAgent类型:
- explore: 快速探索代码库(只读)
- plan: 实施规划和架构设计
- debug-specialist: 错误调试和诊断
- general-purpose: 通用执行(完全工具访问)
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .webcontainer_tools import ToolResult


# ============================================
# SubAgent Types
# ============================================

class SubAgentType(str, Enum):
    """SubAgent类型"""
    EXPLORE = "explore"
    PLAN = "plan"
    DEBUG = "debug-specialist"
    GENERAL = "general-purpose"


# ============================================
# Task Tool (cX)
# ============================================

def task(
    agent_type: str,
    prompt: str,
    description: str = "",
    background: bool = False,
    max_iterations: int = 999999,  # No limit - SubAgent works until task is complete
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Task (cX) - Launch SubAgent to handle complex tasks

    启动一个SubAgent来自主处理复杂、多步骤的任务。

    SubAgent类型:
    - "explore": 快速探索代码库
      - 工具: list_files, read_file, get_project_structure, search_*
      - 用途: 了解代码结构、查找文件、快速调研
      - 速度: 快 (只读操作)

    - "plan": 实施规划
      - 工具: 所有只读工具 + 文件创建
      - 用途: 设计实现方案、架构规划
      - 速度: 中 (需要思考和设计)

    - "debug-specialist": 错误调试
      - 工具: 所有读取 + 诊断工具
      - 用途: 调查bug、分析错误、提供修复建议
      - 速度: 中 (需要深入分析)

    - "general-purpose": 通用执行
      - 工具: 所有工具 (完全自主)
      - 用途: 完整功能实现、复杂任务执行
      - 速度: 慢 (需要多步操作)

    并发限制:
    - 最多10个SubAgent同时运行 (gW5 = 10)
    - 超过限制时新SubAgent会排队
    - background=false 时会等待SubAgent完成

    Args:
        agent_type: SubAgent类型 ("explore", "plan", "debug-specialist", "general-purpose")
        prompt: 任务描述 (详细的任务指令)
        description: 简短描述 (3-5词,用于显示)
        background: 是否后台运行 (默认 False,前台会等待完成)
        max_iterations: 最大迭代次数 (默认 10)
        webcontainer_state: WebContainer状态

    Returns:
        ToolResult with SubAgent launch status (includes action)
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    # Validate agent_type
    valid_types = ["explore", "plan", "debug-specialist", "general-purpose"]
    if agent_type not in valid_types:
        return ToolResult(
            success=False,
            result=f"Invalid agent_type '{agent_type}'. Must be one of: {', '.join(valid_types)}"
        )

    # Validate prompt
    if not prompt or len(prompt.strip()) < 10:
        return ToolResult(
            success=False,
            result="Prompt is too short. Provide detailed task instructions (at least 10 characters)."
        )

    # Generate description if not provided
    if not description:
        description = f"{agent_type.replace('-', ' ').title()} Task"

    # Check concurrent limit
    active_subagents = webcontainer_state.get("active_subagents", [])
    if len(active_subagents) >= 10:
        return ToolResult(
            success=False,
            result=f"Maximum concurrent SubAgents (10) reached. Wait for some to complete or run in background."
        )

    # Create SubAgent launch action
    action = {
        "type": "launch_subagent",
        "payload": {
            "agent_type": agent_type,
            "prompt": prompt,
            "description": description,
            "background": background,
            "max_iterations": max_iterations,
        }
    }

    # Format result message
    mode = "background" if background else "foreground"
    result_lines = [
        f"🚀 Launching {agent_type} SubAgent ({mode})",
        f"📋 Description: {description}",
        f"📝 Task: {prompt[:100]}..." if len(prompt) > 100 else f"📝 Task: {prompt}",
        f"🔄 Max Iterations: {max_iterations}",
    ]

    if background:
        result_lines.append("\n⏳ SubAgent will run in background. Use get_subagent_status to check progress.")
    else:
        result_lines.append("\n⏳ Waiting for SubAgent to complete...")

    return ToolResult(
        success=True,
        result="\n".join(result_lines),
        action=action
    )


def get_subagent_status(
    agent_id: Optional[str] = None,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Get SubAgent Status - 查询SubAgent状态

    查询当前运行中或已完成的SubAgent状态。

    Args:
        agent_id: SubAgent ID (可选,不指定则显示所有)
        webcontainer_state: WebContainer状态

    Returns:
        ToolResult with SubAgent status
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    active_subagents = webcontainer_state.get("active_subagents", [])
    completed_subagents = webcontainer_state.get("completed_subagents", [])

    if not active_subagents and not completed_subagents:
        return ToolResult(
            success=True,
            result="No SubAgents running or completed."
        )

    lines = ["🤖 SubAgent Status\n"]
    lines.append("=" * 60)

    # Active SubAgents
    if active_subagents:
        lines.append("\n🔄 Running SubAgents:")
        for agent in active_subagents:
            aid = agent.get("id", "unknown")
            atype = agent.get("type", "unknown")
            desc = agent.get("description", "")
            progress = agent.get("progress", 0)

            if agent_id and aid != agent_id:
                continue

            lines.append(f"\n  ID: {aid}")
            lines.append(f"  Type: {atype}")
            lines.append(f"  Description: {desc}")
            lines.append(f"  Progress: {progress}%")

    # Completed SubAgents
    if completed_subagents:
        lines.append("\n✅ Completed SubAgents:")
        for agent in completed_subagents:
            aid = agent.get("id", "unknown")
            atype = agent.get("type", "unknown")
            desc = agent.get("description", "")
            success = agent.get("success", False)
            result = agent.get("result", "")

            if agent_id and aid != agent_id:
                continue

            status_icon = "✅" if success else "❌"
            lines.append(f"\n  ID: {aid} {status_icon}")
            lines.append(f"  Type: {atype}")
            lines.append(f"  Description: {desc}")
            if result:
                result_preview = result[:200] + "..." if len(result) > 200 else result
                lines.append(f"  Result: {result_preview}")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


# ============================================
# Tool Definitions
# ============================================

def get_task_tool_definitions() -> List[dict]:
    """
    获取Task工具定义

    Returns:
        List of tool definitions in Claude API format
    """
    return [
        {
            "name": "task",
            "description": """Launch a SubAgent to handle complex, multi-step tasks autonomously.

SubAgent Types:

1. **explore** - Fast codebase exploration (read-only)
   - Tools: list_files, read_file, search, get_project_structure
   - Use for: Understanding code, finding files, quick research
   - Speed: Fast (read-only operations)
   - Example: "Find all React components that use useState hook"

2. **plan** - Implementation planning
   - Tools: All read tools + planning
   - Use for: Designing implementation, architecture planning
   - Speed: Medium (requires thinking)
   - Example: "Plan the implementation of user authentication system"

3. **debug-specialist** - Bug investigation
   - Tools: All read + diagnostic tools
   - Use for: Investigating bugs, analyzing errors, suggesting fixes
   - Speed: Medium (requires analysis)
   - Example: "Debug the login failure error in authentication flow"

4. **general-purpose** - Full autonomy
   - Tools: All tools (complete access)
   - Use for: Complete feature implementation, complex tasks
   - Speed: Slow (multi-step operations)
   - Example: "Implement dark mode support across the entire application"

Concurrency:
- Max 10 SubAgents running simultaneously
- Exceeding limit queues new SubAgents
- Use background=true for async execution

WHEN TO USE:
- Task requires multiple steps (>3 operations)
- Task needs autonomous decision-making
- Task involves exploring unfamiliar code
- Task requires specialized expertise (debugging, planning)

WHEN NOT TO USE:
- Simple single-step operations
- Direct tool calls are sufficient
- Task is already well understood""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["explore", "plan", "debug-specialist", "general-purpose"],
                        "description": "Type of SubAgent to launch"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Detailed task instructions for the SubAgent (be specific and clear)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description (3-5 words) for display (optional, auto-generated if omitted)"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Run in background (true) or wait for completion (false). Default false."
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum iterations for the SubAgent (default: unlimited)"
                    }
                },
                "required": ["agent_type", "prompt"]
            }
        },
        {
            "name": "get_subagent_status",
            "description": """Get status of running or completed SubAgents.

Shows:
- Active SubAgents with progress
- Completed SubAgents with results
- SubAgent type and description

Use this to:
- Check progress of background SubAgents
- Get results from completed SubAgents
- Debug SubAgent issues""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "Specific SubAgent ID (optional, shows all if omitted)"
                    }
                },
                "required": []
            }
        }
    ]


# ============================================
# Tool Registry
# ============================================

TASK_TOOLS = {
    "task": task,
    "get_subagent_status": get_subagent_status,
}


def get_task_tools():
    """Get all task management tools"""
    return TASK_TOOLS
