"""
BoxLite MCP Server

MCP Server implementation for BoxLite sandbox.
This is the BoxLite equivalent of WebContainerMCPServer from agent/mcp_server.py.

The server provides the same tool interface but executes tools
directly on the backend BoxLite sandbox instead of sending to frontend.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

# Import tool definitions from original agent (same tools, different execution)
from agent.mcp_tools import TOOL_DEFINITIONS

from .boxlite_mcp_executor import BoxLiteMCPExecutor

if TYPE_CHECKING:
    from .sandbox_manager import BoxLiteSandboxManager

logger = logging.getLogger(__name__)


class BoxLiteMCPServer:
    """
    MCP Server for BoxLite sandbox operations.

    This server provides the same tools as WebContainerMCPServer
    but executes them directly on the backend BoxLite sandbox.

    Key difference:
    - WebContainer: Tools send execute_action to frontend WebSocket
    - BoxLite: Tools execute directly on backend sandbox
    """

    def __init__(
        self,
        sandbox: "BoxLiteSandboxManager",
        session_id: str,
        on_worker_event: Optional[callable] = None,
    ):
        """
        Initialize BoxLite MCP server.

        Args:
            sandbox: BoxLite sandbox manager instance
            session_id: Current session ID
            on_worker_event: Callback for worker events (WebSocket broadcast)
        """
        self.sandbox = sandbox
        self.session_id = session_id

        # Tool executor
        self._executor = BoxLiteMCPExecutor(
            sandbox=sandbox,
            session_id=session_id,
            on_worker_event=on_worker_event,
        )

        # Tool registry (same tools as WebContainer)
        self._tools: Dict[str, Dict[str, Any]] = {
            tool["name"]: tool for tool in TOOL_DEFINITIONS
        }

        logger.info(
            f"BoxLiteMCPServer initialized: "
            f"session={session_id}, tools={len(self._tools)}"
        )

    # ============================================
    # Tool Management
    # ============================================

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions for Claude API.

        Returns:
            List of tool definitions in Claude API format
        """
        return TOOL_DEFINITIONS

    def get_tool_names(self) -> List[str]:
        """Get list of available tool names"""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Check if tool exists"""
        return name in self._tools

    def get_tool_definition(self, name: str) -> Optional[Dict[str, Any]]:
        """Get specific tool definition"""
        return self._tools.get(name)

    # ============================================
    # Tool Execution
    # ============================================

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool on BoxLite sandbox.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters

        Returns:
            Tool result in MCP format:
            {
                "content": [{"type": "text", "text": "..."}],
                "is_error": False
            }
        """
        if not self.has_tool(tool_name):
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "is_error": True,
            }

        logger.info(f"[BoxLite] Executing tool: {tool_name}")

        return await self._executor.execute(tool_name, tool_input)

    # ============================================
    # Claude API Integration
    # ============================================

    def get_tools_for_claude_api(self) -> List[Dict[str, Any]]:
        """
        Get tools formatted for Claude API.

        Returns:
            Tools in Anthropic API format
        """
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
            for tool in TOOL_DEFINITIONS
        ]

    async def handle_tool_use(
        self,
        tool_use_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle tool_use block from Claude API response.

        Args:
            tool_use_id: Tool use ID from Claude
            tool_name: Name of the tool
            tool_input: Tool input

        Returns:
            Tool result for tool_result message
        """
        result = await self.execute_tool(tool_name, tool_input)

        # Format for Claude API tool_result
        content = ""
        if result["content"]:
            first_content = result["content"][0]
            if isinstance(first_content, dict):
                if first_content.get("type") == "text":
                    content = first_content.get("text", "")
                elif first_content.get("type") == "image":
                    # Return image content for screenshot
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": [first_content],
                        "is_error": result.get("is_error", False),
                    }
            else:
                content = str(first_content)

        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
            "is_error": result.get("is_error", False),
        }


# ============================================
# Factory Function
# ============================================

def create_boxlite_mcp_server(
    sandbox: "BoxLiteSandboxManager",
    session_id: str,
    on_worker_event: Optional[callable] = None,
) -> BoxLiteMCPServer:
    """
    Create BoxLite MCP server instance.

    Args:
        sandbox: BoxLite sandbox manager
        session_id: Session ID
        on_worker_event: Callback for worker events

    Returns:
        Configured BoxLite MCP server
    """
    return BoxLiteMCPServer(
        sandbox=sandbox,
        session_id=session_id,
        on_worker_event=on_worker_event,
    )
