"""
MCP Server for WebContainer

Creates an MCP server that bridges Claude Agent SDK with frontend WebContainer.

Note: This is a simplified implementation that works with the Claude API directly,
rather than the full MCP protocol. The tools are registered with Claude API format
and executed via WebSocket bridge to frontend.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .websocket_manager import WebSocketManager

from .mcp_tools import TOOL_DEFINITIONS, MCPToolExecutor

logger = logging.getLogger(__name__)


# ============================================
# MCP Server
# ============================================

class WebContainerMCPServer:
    """
    MCP Server for WebContainer operations

    This server provides tools that bridge the Claude Agent SDK
    with the frontend WebContainer environment.

    Tools are executed by sending requests to the frontend via WebSocket
    and waiting for the results.
    """

    def __init__(
        self,
        ws_manager: "WebSocketManager",
        session_id: str,
    ):
        """
        Initialize MCP server

        Args:
            ws_manager: WebSocket manager for frontend communication
            session_id: Current session ID
        """
        self.ws_manager = ws_manager
        self.session_id = session_id

        # Tool executor
        self._executor = MCPToolExecutor(ws_manager, session_id)

        # Tool registry
        self._tools: Dict[str, Dict[str, Any]] = {
            tool["name"]: tool for tool in TOOL_DEFINITIONS
        }

        logger.info(
            f"WebContainerMCPServer initialized: "
            f"session={session_id}, tools={len(self._tools)}"
        )

    # ============================================
    # Tool Management
    # ============================================

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions for Claude API

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
        Execute a tool

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

        logger.info(f"Executing tool via MCP: {tool_name}")

        return await self._executor.execute(tool_name, tool_input)

    # ============================================
    # Claude API Integration
    # ============================================

    def get_tools_for_claude_api(self) -> List[Dict[str, Any]]:
        """
        Get tools formatted for Claude API

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
        Handle tool_use block from Claude API response

        Args:
            tool_use_id: Tool use ID from Claude
            tool_name: Name of the tool
            tool_input: Tool input

        Returns:
            Tool result for tool_result message
        """
        result = await self.execute_tool(tool_name, tool_input)

        # Format for Claude API tool_result
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": result["content"][0]["text"] if result["content"] else "",
            "is_error": result.get("is_error", False),
        }


# ============================================
# Factory Function
# ============================================

def create_mcp_server(
    ws_manager: "WebSocketManager",
    session_id: str,
) -> WebContainerMCPServer:
    """
    Create MCP server instance

    Args:
        ws_manager: WebSocket manager
        session_id: Session ID

    Returns:
        Configured MCP server
    """
    return WebContainerMCPServer(ws_manager, session_id)
