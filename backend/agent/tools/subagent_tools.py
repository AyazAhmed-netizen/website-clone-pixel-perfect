"""
SubAgent Tools

Tools for launching and managing SubAgents.
Similar to Claude Code's Task tool.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, Optional

from ..state import ToolResult

logger = logging.getLogger(__name__)


# Global SubAgent manager instance (will be injected by graph)
_subagent_manager = None


def set_subagent_manager(manager):
    """Set the global SubAgent manager instance"""
    global _subagent_manager
    _subagent_manager = manager


def launch_subagent(
    agent_type: str,
    prompt: str,
    description: str = "",
    background: bool = False,
    max_iterations: int = 999999,  # No limit - SubAgent works until task is complete
    **kwargs
) -> ToolResult:
    """
    Launch a SubAgent to handle complex tasks autonomously

    This tool allows you to delegate tasks to specialized SubAgents:

    **Available SubAgent Types:**

    1. **general-purpose**: General tasks, code writing, multi-step operations
       - Can modify files
       - Can run commands
       - Has access to all tools
       - Use for complex implementation tasks

    2. **explore**: Fast codebase exploration
       - Find files by patterns
       - Search code for keywords
       - Answer questions about code structure
       - Read-only operations
       - Use when you need to search the codebase

    3. **plan**: Implementation planning and architecture design
       - Design implementation strategies
       - Identify critical files
       - Consider trade-offs
       - Read-only operations
       - Use for planning before implementation

    4. **debug-specialist**: Bug investigation and error resolution
       - Investigate errors
       - Trace root causes
       - Run diagnostic commands
       - Suggest fixes
       - Use when encountering bugs or runtime issues

    **When to Use SubAgents:**

    - Task requires deep exploration (>3 files to search)
    - Multiple search/analysis rounds needed
    - Complex implementation requiring multiple steps
    - Bug investigation needed
    - Planning before major changes

    **Parameters:**

    - agent_type: One of "general-purpose", "explore", "plan", "debug-specialist"
    - prompt: Task description for the SubAgent
    - description: Short description for logging (optional)
    - background: Run in background without blocking (default: False)
    - max_iterations: Maximum agent loop iterations (default: 10)

    **Returns:**

    Tool result with:
    - agent_id: ID for tracking this SubAgent
    - status: "launched" or "queued" or "error"
    - message: Status message

    **Examples:**

    1. Explore codebase:
    ```
    launch_subagent(
        agent_type="explore",
        prompt="Find where API endpoints are defined",
        description="Search for API routes"
    )
    ```

    2. Plan implementation:
    ```
    launch_subagent(
        agent_type="plan",
        prompt="Design implementation plan for adding user authentication",
        description="Auth planning"
    )
    ```

    3. Debug issue:
    ```
    launch_subagent(
        agent_type="debug-specialist",
        prompt="Investigate why build is failing with import error",
        description="Debug build failure"
    )
    ```

    4. Implement feature (background):
    ```
    launch_subagent(
        agent_type="general-purpose",
        prompt="Add user authentication to the API",
        description="Implement auth",
        background=True
    )
    ```

    **Note:** If running in background, use `get_subagent_result` to check status and get results.
    """
    if not _subagent_manager:
        return ToolResult(
            success=False,
            result="SubAgent manager not initialized",
        )

    # Validate agent_type
    valid_types = ["general-purpose", "explore", "plan", "debug-specialist"]
    if agent_type not in valid_types:
        return ToolResult(
            success=False,
            result=f"Invalid agent_type '{agent_type}'. Must be one of: {', '.join(valid_types)}",
        )

    # Note: Actual launching is handled asynchronously by the graph
    # This tool just returns instruction to launch
    return ToolResult(
        success=True,
        result=f"SubAgent launch requested: {agent_type}",
        action={
            "type": "launch_subagent",
            "agent_type": agent_type,
            "prompt": prompt,
            "description": description,
            "background": background,
            "max_iterations": max_iterations,
        }
    )


def get_subagent_result(
    agent_id: str,
    block: bool = True,
    **kwargs
) -> ToolResult:
    """
    Get result from a SubAgent

    Use this tool to check the status and get results from a previously launched SubAgent.

    **Parameters:**

    - agent_id: The SubAgent ID (returned from launch_subagent)
    - block: Wait for completion if still running (default: True)

    **Returns:**

    Tool result with SubAgent's output if completed, or status if still running.

    **Example:**

    ```
    # Launch SubAgent (returns agent_id)
    result = launch_subagent(agent_type="explore", prompt="Find auth code", background=True)
    agent_id = result.agent_id

    # Later, get result
    result = get_subagent_result(agent_id=agent_id)
    # result contains the SubAgent's findings
    ```

    **Note:** If SubAgent is still running and block=False, returns status="running".
    If block=True, waits for completion (may take time).
    """
    if not _subagent_manager:
        return ToolResult(
            success=False,
            result="SubAgent manager not initialized",
        )

    # Get result (non-blocking since this is a sync function)
    result = _subagent_manager.get_result(agent_id, block=False)

    if result is None:
        # Check if running
        running_agents = _subagent_manager.list_running()
        if agent_id in running_agents:
            return ToolResult(
                success=True,
                result=f"SubAgent {agent_id} is still running (iteration {running_agents[agent_id]['iterations']})",
            )
        else:
            return ToolResult(
                success=False,
                result=f"SubAgent {agent_id} not found",
            )

    # Result available
    if result.success:
        return ToolResult(
            success=True,
            result=f"SubAgent completed successfully:\n\n{result.output}",
        )
    else:
        return ToolResult(
            success=False,
            result=f"SubAgent failed: {result.error}\n\nPartial output:\n{result.output}",
        )


# Tool definitions for registration
SUBAGENT_TOOLS = {
    "launch_subagent": {
        "function": launch_subagent,
        "definition": {
            "name": "launch_subagent",
            "description": "Launch a specialized SubAgent to handle complex tasks autonomously. Available types: general-purpose (full autonomy), explore (codebase search), plan (implementation planning), debug-specialist (bug investigation). Use when tasks require deep exploration, planning, or multi-step execution.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["general-purpose", "explore", "plan", "debug-specialist"],
                        "description": "Type of SubAgent to launch"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Task description for the SubAgent"
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description for logging (optional)"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Run in background without blocking (default: false)"
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum agent loop iterations (default: unlimited)"
                    }
                },
                "required": ["agent_type", "prompt"]
            }
        }
    },
    "get_subagent_result": {
        "function": get_subagent_result,
        "definition": {
            "name": "get_subagent_result",
            "description": "Get result from a previously launched SubAgent. Use to check status and retrieve output from background SubAgents.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "SubAgent ID returned from launch_subagent"
                    },
                    "block": {
                        "type": "boolean",
                        "description": "Wait for completion if still running (default: true)"
                    }
                },
                "required": ["agent_id"]
            }
        }
    }
}
