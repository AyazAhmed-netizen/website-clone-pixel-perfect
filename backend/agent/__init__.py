"""
Clone Agent Module
克隆代理模块

AI-powered web cloning agent that uses extracted page data
to generate code for WebContainer.

Features:
- Multi-agent architecture (Master + Workers)
- WebSocket real-time communication
- Memory system (short-term, mid-term, long-term)
- Tool execution for code generation
- Cache integration for page data access
"""

from .routes_websocket import router as agent_ws_router

__all__ = [
    "agent_ws_router",
]
