"""
Tool Registry

统一的工具注册表,整合所有Claude Code风格的工具。

工具分类:
1. File Operations: Read, Write, Edit, Delete, Rename, CreateDirectory
2. Search & Discovery: Glob (FJ1), Grep (XJ1), LS
3. Task Management: TodoRead (oN), TodoWrite (yG), Task (cX)
4. System Execution: Bash
5. Network: WebFetch (IJ1), WebSearch
6. Terminal: RunCommand, InstallDependencies, CreateTerminal, etc.
7. Preview: TakeScreenshot, GetConsoleMessages, GetPreviewDOM
8. Diagnostic: VerifyChanges

工具命名规范:
- 遵循Claude Code的命名模式
- 使用snake_case (Python风格)
- 工具函数接收webcontainer_state参数
"""

from __future__ import annotations
from typing import Dict, List, Any, Callable, Optional

# Import all tool modules
from .webcontainer_tools import (
    # File operations
    read_file,
    write_file,
    edit_file,
    delete_file,
    rename_file,
    create_directory,
    list_files,
    file_exists,
    get_project_structure,
    search_in_file,
    search_in_project,

    # Terminal operations
    run_command,
    install_dependencies,
    start_dev_server,
    stop_server,
    create_terminal,
    switch_terminal,
    send_terminal_input,
    kill_terminal,
    get_terminal_output,
    get_terminal_history,
    list_terminals,

    # Preview operations
    take_screenshot,
    get_console_messages,
    get_preview_dom,
    clear_console,
    get_preview_status,

    # Diagnostic
    verify_changes,

    # Tool definitions
    get_tool_definitions as get_webcontainer_tool_definitions,
)

from .claude_code_tools import (
    glob,
    grep,
    ls,
    bash,
    get_claude_code_tool_definitions,
    CLAUDE_CODE_TOOLS,
)

from .todo_tools import (
    todo_read,
    todo_write,
    get_todo_tool_definitions,
    TODO_TOOLS,
)

from .task_tool import (
    task,
    get_subagent_status,
    get_task_tool_definitions,
    TASK_TOOLS,
)

from .network_tools import (
    web_fetch,
    web_search,
    get_network_tool_definitions,
    NETWORK_TOOLS,
)

from .terminal_preview_reader_tools import (
    get_all_terminals_output,
    get_preview_error_overlay,
    get_comprehensive_error_snapshot,
    get_terminal_preview_reader_tool_definitions,
    TERMINAL_PREVIEW_READER_TOOLS,
)

from .preview_diagnostic_tools import (
    diagnose_preview_state,
    get_preview_diagnostic_tool_definitions,
    PREVIEW_DIAGNOSTIC_TOOLS,
)

from .self_healing_tools import (
    start_healing_loop,
    verify_healing_progress,
    stop_healing_loop,
    get_healing_status,
    get_self_healing_tool_definitions,
    SELF_HEALING_TOOLS,
)

from .error_handling_tools import (
    analyze_build_error,
    get_error_handling_tool_definitions,
    ERROR_HANDLING_TOOLS,
)


# ============================================
# Tool Categories
# ============================================

# Category 1: File Operations (文件操作)
FILE_TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "rename_file": rename_file,
    "create_directory": create_directory,
    "file_exists": file_exists,
}

# Category 2: Search & Discovery (搜索和发现)
SEARCH_TOOLS = {
    "glob": glob,  # FJ1
    "grep": grep,  # XJ1
    "ls": ls,
    "list_files": list_files,
    "get_project_structure": get_project_structure,
    "search_in_file": search_in_file,
    "search_in_project": search_in_project,
}

# Category 3: Task Management (任务管理)
# Already imported from task_tool.py and todo_tools.py
TASK_MANAGEMENT_TOOLS = {
    **TODO_TOOLS,  # todo_read, todo_write
    **TASK_TOOLS,  # task, get_subagent_status
}

# Category 4: System Execution (系统执行)
SYSTEM_TOOLS = {
    "bash": bash,
    "run_command": run_command,
}

# Category 5: Network (网络)
# Already imported from network_tools.py

# Category 6: Terminal (终端管理)
TERMINAL_TOOLS = {
    "install_dependencies": install_dependencies,
    "start_dev_server": start_dev_server,
    "stop_server": stop_server,
    "create_terminal": create_terminal,
    "switch_terminal": switch_terminal,
    "send_terminal_input": send_terminal_input,
    "kill_terminal": kill_terminal,
    "get_terminal_output": get_terminal_output,
    "get_terminal_history": get_terminal_history,
    "list_terminals": list_terminals,
}

# Category 7: Preview (预览操作)
PREVIEW_TOOLS = {
    "take_screenshot": take_screenshot,
    "get_console_messages": get_console_messages,
    "get_preview_dom": get_preview_dom,
    "clear_console": clear_console,
    "get_preview_status": get_preview_status,
}

# Category 8: Diagnostic (诊断)
DIAGNOSTIC_TOOLS = {
    "verify_changes": verify_changes,
    # Terminal & Preview Reader Tools
    "get_all_terminals_output": get_all_terminals_output,
    "get_preview_error_overlay": get_preview_error_overlay,
    "get_comprehensive_error_snapshot": get_comprehensive_error_snapshot,
    # Preview Diagnostic Tool
    "diagnose_preview_state": diagnose_preview_state,
    # Error Handling Tools
    "analyze_build_error": analyze_build_error,
    # Self-Healing Tools
    "start_healing_loop": start_healing_loop,
    "verify_healing_progress": verify_healing_progress,
    "stop_healing_loop": stop_healing_loop,
    "get_healing_status": get_healing_status,
}


# ============================================
# Unified Tool Registry
# ============================================

ALL_TOOLS: Dict[str, Callable] = {
    **FILE_TOOLS,
    **SEARCH_TOOLS,
    **TASK_MANAGEMENT_TOOLS,
    **SYSTEM_TOOLS,
    **NETWORK_TOOLS,
    **TERMINAL_TOOLS,
    **PREVIEW_TOOLS,
    **DIAGNOSTIC_TOOLS,
}


# ============================================
# Tool Metadata
# ============================================

TOOL_CATEGORIES = {
    "file_operations": list(FILE_TOOLS.keys()),
    "search_discovery": list(SEARCH_TOOLS.keys()),
    "task_management": list(TASK_MANAGEMENT_TOOLS.keys()),
    "system_execution": list(SYSTEM_TOOLS.keys()),
    "network": list(NETWORK_TOOLS.keys()),
    "terminal": list(TERMINAL_TOOLS.keys()),
    "preview": list(PREVIEW_TOOLS.keys()),
    "diagnostic": list(DIAGNOSTIC_TOOLS.keys()),
}


# Concurrency safety metadata
# True = 并发安全 (可以同时调用多个)
# False = 非并发安全 (同一时间只能有一个在执行)
TOOL_CONCURRENCY_SAFE = {
    # File operations - most are safe (read-only or independent writes)
    "read_file": True,
    "write_file": False,  # Writing to same file not safe
    "edit_file": False,   # Editing same file not safe
    "delete_file": False,
    "rename_file": False,
    "create_directory": True,
    "file_exists": True,

    # Search - all read-only, safe
    "glob": True,
    "grep": True,
    "ls": True,
    "list_files": True,
    "get_project_structure": True,
    "search_in_file": True,
    "search_in_project": True,

    # Task management - state mutation, not safe
    "todo_read": True,
    "todo_write": False,
    "task": False,  # Launching SubAgent should be sequential
    "get_subagent_status": True,

    # System execution - not safe (commands may conflict)
    "bash": False,
    "run_command": False,

    # Network - safe (independent requests)
    "web_fetch": True,
    "web_search": True,

    # Terminal - mostly not safe (shared terminal state)
    "install_dependencies": False,
    "start_dev_server": False,
    "stop_server": False,
    "create_terminal": True,
    "switch_terminal": True,
    "send_terminal_input": False,
    "kill_terminal": False,
    "get_terminal_output": True,
    "get_terminal_history": True,
    "list_terminals": True,

    # Preview - read operations safe, mutations not safe
    "take_screenshot": True,
    "get_console_messages": True,
    "get_preview_dom": True,
    "clear_console": False,
    "get_preview_status": True,

    # Diagnostic - read-only, safe
    "verify_changes": True,
    "get_all_terminals_output": True,
    "get_preview_error_overlay": True,
    "get_comprehensive_error_snapshot": True,
    "diagnose_preview_state": True,
    "analyze_build_error": True,
    # Self-Healing - state mutation, not safe
    "start_healing_loop": False,  # Modifies healing state
    "verify_healing_progress": False,  # Modifies healing state
    "stop_healing_loop": False,  # Modifies healing state
    "get_healing_status": True,  # Read-only
}


# Priority levels (for scheduling)
# 1-10, 10 = highest priority
TOOL_PRIORITIES = {
    # High priority - critical operations
    "verify_changes": 10,  # Always verify after changes
    "get_comprehensive_error_snapshot": 10,  # Critical for error diagnosis
    "get_all_terminals_output": 9,  # Important for server status check
    "diagnose_preview_state": 9,  # Comprehensive preview diagnosis
    "get_preview_error_overlay": 8,  # Preview error details
    "todo_write": 9,       # Task tracking is important
    "bash": 8,             # System commands
    "run_command": 8,

    # Medium-high priority - important operations
    "write_file": 7,
    "edit_file": 7,
    "delete_file": 7,
    "task": 7,  # SubAgent launching

    # Medium priority - standard operations
    "read_file": 5,
    "grep": 5,
    "glob": 5,
    "install_dependencies": 5,
    "start_dev_server": 5,

    # Lower priority - auxiliary operations
    "take_screenshot": 3,
    "get_console_messages": 3,
    "web_search": 3,
    "web_fetch": 3,

    # Lowest priority - info queries
    "list_files": 1,
    "ls": 1,
    "get_project_structure": 1,
    "todo_read": 1,
    "get_subagent_status": 1,

    # Error handling and self-healing - high priority
    "analyze_build_error": 9,
    "start_healing_loop": 9,
    "verify_healing_progress": 9,
    "stop_healing_loop": 8,
    "get_healing_status": 7,
}


# ============================================
# Tool Definitions (for Claude API)
# ============================================

def get_all_tool_definitions() -> List[dict]:
    """
    获取所有工具的定义

    Returns:
        List of tool definitions in Claude API format
    """
    definitions = []

    # Add WebContainer tools
    definitions.extend(get_webcontainer_tool_definitions())

    # Add Claude Code style tools
    definitions.extend(get_claude_code_tool_definitions())

    # Add Todo tools
    definitions.extend(get_todo_tool_definitions())

    # Add Task tools
    definitions.extend(get_task_tool_definitions())

    # Add Network tools
    definitions.extend(get_network_tool_definitions())

    # Add Terminal/Preview Reader tools (重要的诊断工具)
    definitions.extend(get_terminal_preview_reader_tool_definitions())

    # Add Preview Diagnostic tools
    definitions.extend(get_preview_diagnostic_tool_definitions())

    # Add Error Handling tools
    definitions.extend(get_error_handling_tool_definitions())

    # Add Self-Healing tools
    definitions.extend(get_self_healing_tool_definitions())

    return definitions


def get_tool_by_name(name: str) -> Optional[Callable]:
    """
    根据名称获取工具函数

    Args:
        name: Tool name

    Returns:
        Tool function or None if not found
    """
    return ALL_TOOLS.get(name)


def is_tool_concurrency_safe(name: str) -> bool:
    """
    检查工具是否并发安全

    Args:
        name: Tool name

    Returns:
        True if tool is concurrency safe
    """
    return TOOL_CONCURRENCY_SAFE.get(name, False)


def get_tool_priority(name: str) -> int:
    """
    获取工具优先级

    Args:
        name: Tool name

    Returns:
        Priority level (1-10)
    """
    return TOOL_PRIORITIES.get(name, 5)


def get_tools_by_category(category: str) -> List[str]:
    """
    获取指定类别的工具列表

    Args:
        category: Category name

    Returns:
        List of tool names
    """
    return TOOL_CATEGORIES.get(category, [])


def get_subagent_tools(agent_type: str) -> List[str]:
    """
    获取SubAgent可用的工具列表

    Args:
        agent_type: SubAgent类型 ("explore", "plan", "debug", "general")

    Returns:
        List of allowed tool names
    """
    if agent_type == "explore":
        # Explore Agent: 只读工具(不包括写操作)
        read_only_file_tools = ["read_file", "file_exists"]
        return (
            read_only_file_tools +
            list(SEARCH_TOOLS.keys()) +
            ["todo_read", "get_subagent_status"] +
            ["get_terminal_output", "get_terminal_history", "list_terminals"] +
            list(PREVIEW_TOOLS.keys()) +
            list(DIAGNOSTIC_TOOLS.keys())
        )

    elif agent_type == "plan":
        # Plan Agent: 只读 + 计划工具
        return get_subagent_tools("explore") + [
            "write_file",  # Can create plan files
            "todo_write",
        ]

    elif agent_type == "debug-specialist":
        # Debug Agent: 只读 + 诊断工具
        return get_subagent_tools("explore") + [
            "bash",  # Can run diagnostic commands
            "run_command",
            "read_file",  # Additional read access for debugging
        ]

    elif agent_type == "general-purpose":
        # General Agent: 所有工具
        return list(ALL_TOOLS.keys())

    else:
        # Unknown type, return read-only tools
        return get_subagent_tools("explore")


# ============================================
# Tool Statistics
# ============================================

def get_tool_statistics() -> dict:
    """
    获取工具统计信息

    Returns:
        Statistics dict
    """
    return {
        "total_tools": len(ALL_TOOLS),
        "categories": {
            category: len(tools)
            for category, tools in TOOL_CATEGORIES.items()
        },
        "concurrency_safe_count": sum(1 for safe in TOOL_CONCURRENCY_SAFE.values() if safe),
        "high_priority_count": sum(1 for p in TOOL_PRIORITIES.values() if p >= 7),
    }


# ============================================
# Export
# ============================================

__all__ = [
    # Tool registry
    "ALL_TOOLS",
    "TOOL_CATEGORIES",
    "TOOL_CONCURRENCY_SAFE",
    "TOOL_PRIORITIES",

    # Tool getters
    "get_all_tool_definitions",
    "get_tool_by_name",
    "is_tool_concurrency_safe",
    "get_tool_priority",
    "get_tools_by_category",
    "get_subagent_tools",
    "get_tool_statistics",

    # Individual tool categories
    "FILE_TOOLS",
    "SEARCH_TOOLS",
    "TASK_MANAGEMENT_TOOLS",
    "SYSTEM_TOOLS",
    "NETWORK_TOOLS",
    "TERMINAL_TOOLS",
    "PREVIEW_TOOLS",
    "DIAGNOSTIC_TOOLS",
]
