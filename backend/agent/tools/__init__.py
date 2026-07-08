"""
Nexting Agent Tools

Complete Claude Code-style tool system integrated with WebContainer.

Tool Categories:
1. File Operations - Read, Write, Edit, Delete, etc.
2. Search & Discovery - Glob (FJ1), Grep (XJ1), LS
3. Task Management - TodoRead (oN), TodoWrite (yG), Task (cX)
4. System Execution - Bash, RunCommand
5. Network - WebFetch (IJ1), WebSearch
6. Terminal - Terminal management and execution
7. Preview - Screenshot, Console, DOM inspection
8. Diagnostic - Verification and error checking
9. JSON Source - Query saved website data
10. SubAgent - Dynamic agent launching

Architecture:
- All tools use webcontainer_state parameter
- Tools return ToolResult with optional action
- Actions are sent to frontend via SSE stream
- Tool execution goes through MH1 6-stage pipeline
- Max 10 concurrent tools (UH1 scheduler)
"""

# Import tool registry (unified Claude Code-style registry)
from .tool_registry import (
    # Tool registry
    ALL_TOOLS as REGISTRY_ALL_TOOLS,
    TOOL_CATEGORIES,
    TOOL_CONCURRENCY_SAFE,
    TOOL_PRIORITIES,

    # Tool getters
    get_all_tool_definitions as get_registry_tool_definitions,
    get_tool_by_name,
    is_tool_concurrency_safe,
    get_tool_priority,
    get_tools_by_category,
    get_subagent_tools,
    get_tool_statistics,

    # Individual tool categories
    FILE_TOOLS,
    SEARCH_TOOLS,
    TASK_MANAGEMENT_TOOLS,
    SYSTEM_TOOLS,
    NETWORK_TOOLS,
    TERMINAL_TOOLS,
    PREVIEW_TOOLS,
    DIAGNOSTIC_TOOLS,
)

# Import legacy tools for backward compatibility
from .webcontainer_tools import (
    # Types
    ToolResult,

    # Legacy registries (for backward compatibility)
    STATE_QUERY_TOOLS as _WEBCONTAINER_STATE_TOOLS,
    ACTION_TOOLS as _WEBCONTAINER_ACTION_TOOLS,
)

from .json_source_tools import (
    # JSON Source Query Tools
    list_saved_sources,
    get_source_overview,
    query_source_json,

    # Tool Registry
    JSON_SOURCE_TOOLS,
    get_json_source_tool_definitions,
)

from .code_generation_tools import (
    # Code Generation Tools
    generate_component_from_json,
    extract_design_tokens,

    # Tool Registry
    CODE_GENERATION_TOOLS,
    get_code_generation_tool_definitions,
)

from .error_handling_tools import (
    # Error Handling Tools
    analyze_build_error,

    # Tool Registry
    ERROR_HANDLING_TOOLS,
    get_error_handling_tool_definitions,
)

from .preview_diagnostic_tools import (
    # Preview Diagnostic Tools
    diagnose_preview_state,

    # Tool Registry
    PREVIEW_DIAGNOSTIC_TOOLS,
    get_preview_diagnostic_tool_definitions,
)

from .terminal_preview_reader_tools import (
    # Terminal & Preview Reader Tools
    get_all_terminals_output,
    get_preview_error_overlay,
    get_comprehensive_error_snapshot,

    # Tool Registry
    TERMINAL_PREVIEW_READER_TOOLS,
    get_terminal_preview_reader_tool_definitions,
)

from .subagent_tools import (
    # SubAgent Tools (legacy tool-based launching)
    launch_subagent,
    get_subagent_result,

    # Tool Registry
    SUBAGENT_TOOLS,
)

# V2 Tools - Claude Code Style (Simplified)
from .webcontainer_tools_v2 import (
    # Core V2 Tools
    shell,
    write_file as v2_write_file,
    read_file as v2_read_file,
    edit_file as v2_edit_file,
    list_files as v2_list_files,
    get_state as v2_get_state,
    delete_file as v2_delete_file,

    # V2 Tool Definitions
    get_tool_definitions_v2,

    # V2 Tool Registries
    ALL_TOOLS as V2_ALL_TOOLS,
    STATE_TOOLS as V2_STATE_TOOLS,
    ACTION_TOOLS as V2_ACTION_TOOLS,

    # Action Store for bidirectional communication
    get_action_store,
    ActionStore,
    ActionRequest,
    ActionResult as ActionResultV2,
)

# Unified ALL_TOOLS including JSON source tools, code generation tools, error handling tools, preview diagnostic tools, terminal/preview readers, and legacy SubAgent tools
ALL_TOOLS = {
    **REGISTRY_ALL_TOOLS,
    **JSON_SOURCE_TOOLS,
    **CODE_GENERATION_TOOLS,
    **ERROR_HANDLING_TOOLS,
    **PREVIEW_DIAGNOSTIC_TOOLS,
    **TERMINAL_PREVIEW_READER_TOOLS,
    **SUBAGENT_TOOLS,
}

# Legacy STATE_QUERY_TOOLS and ACTION_TOOLS (for backward compatibility)
STATE_QUERY_TOOLS = {**_WEBCONTAINER_STATE_TOOLS, **JSON_SOURCE_TOOLS, **CODE_GENERATION_TOOLS, **ERROR_HANDLING_TOOLS, **PREVIEW_DIAGNOSTIC_TOOLS, **TERMINAL_PREVIEW_READER_TOOLS}
ACTION_TOOLS = _WEBCONTAINER_ACTION_TOOLS


def get_all_tools():
    """Get list of all tool functions"""
    return list(ALL_TOOLS.values())


def get_tool_definitions(use_v2: bool = False):
    """
    Get tool definitions in Claude API format.

    Args:
        use_v2: If True, return simplified V2 tools (Claude Code style).
                If False, return full tool set (default).

    Returns:
        List of tool definition dicts
    """
    if use_v2:
        # V2 Tools - Claude Code Style (Simplified)
        # Only 7 core tools: shell, write_file, read_file, edit_file, delete_file, list_files, get_state
        definitions = get_tool_definitions_v2()

        # Also add JSON source tools for querying saved data
        definitions.extend(get_json_source_tool_definitions())

        return definitions

    # Full Tool Set (Legacy)
    # Combine all tool definitions
    definitions = get_registry_tool_definitions()  # Claude Code-style tools
    definitions.extend(get_json_source_tool_definitions())  # JSON source tools
    definitions.extend(get_code_generation_tool_definitions())  # Code generation tools
    definitions.extend(get_error_handling_tool_definitions())  # Error handling tools
    definitions.extend(get_preview_diagnostic_tool_definitions())  # Preview diagnostic tools
    definitions.extend(get_terminal_preview_reader_tool_definitions())  # Terminal/preview reader tools

    # Add SubAgent tools (legacy)
    subagent_tool_defs = [tool_info["definition"] for tool_info in SUBAGENT_TOOLS.values()]
    definitions.extend(subagent_tool_defs)

    return definitions


def get_simplified_tools():
    """
    Get simplified V2 tools (Claude Code style).

    This is a convenience function that returns only the core tools:
    - shell: Execute any command
    - write_file: Create/overwrite files
    - read_file: Read file content
    - edit_file: Search and replace
    - delete_file: Delete files
    - list_files: List directory contents
    - get_state: Get WebContainer state

    Returns:
        Dict of tool name -> function
    """
    return V2_ALL_TOOLS


__all__ = [
    # Tool Registry
    "ALL_TOOLS",
    "TOOL_CATEGORIES",
    "TOOL_CONCURRENCY_SAFE",
    "TOOL_PRIORITIES",

    # Tool Category Registries
    "FILE_TOOLS",
    "SEARCH_TOOLS",
    "TASK_MANAGEMENT_TOOLS",
    "SYSTEM_TOOLS",
    "NETWORK_TOOLS",
    "TERMINAL_TOOLS",
    "PREVIEW_TOOLS",
    "DIAGNOSTIC_TOOLS",
    "JSON_SOURCE_TOOLS",
    "CODE_GENERATION_TOOLS",
    "ERROR_HANDLING_TOOLS",
    "PREVIEW_DIAGNOSTIC_TOOLS",
    "TERMINAL_PREVIEW_READER_TOOLS",
    "SUBAGENT_TOOLS",

    # Legacy Registries (backward compatibility)
    "STATE_QUERY_TOOLS",
    "ACTION_TOOLS",

    # Tool Utility Functions
    "get_all_tools",
    "get_tool_definitions",
    "get_tool_by_name",
    "is_tool_concurrency_safe",
    "get_tool_priority",
    "get_tools_by_category",
    "get_subagent_tools",
    "get_tool_statistics",

    # JSON Source Tools
    "list_saved_sources",
    "get_source_overview",
    "query_source_json",
    "get_json_source_tool_definitions",

    # Code Generation Tools
    "generate_component_from_json",
    "extract_design_tokens",
    "get_code_generation_tool_definitions",

    # Error Handling Tools
    "analyze_build_error",
    "get_error_handling_tool_definitions",

    # Preview Diagnostic Tools
    "diagnose_preview_state",
    "get_preview_diagnostic_tool_definitions",

    # Terminal & Preview Reader Tools
    "get_all_terminals_output",
    "get_preview_error_overlay",
    "get_comprehensive_error_snapshot",
    "get_terminal_preview_reader_tool_definitions",

    # Legacy SubAgent Tools
    "launch_subagent",
    "get_subagent_result",

    # Types
    "ToolResult",

    # V2 Tools (Claude Code Style - Simplified)
    "V2_ALL_TOOLS",
    "V2_STATE_TOOLS",
    "V2_ACTION_TOOLS",
    "shell",
    "v2_write_file",
    "v2_read_file",
    "v2_edit_file",
    "v2_list_files",
    "v2_get_state",
    "v2_delete_file",
    "get_tool_definitions_v2",
    "get_simplified_tools",

    # V2 Action Store (bidirectional communication)
    "get_action_store",
    "ActionStore",
    "ActionRequest",
    "ActionResultV2",
]
