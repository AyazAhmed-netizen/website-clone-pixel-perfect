"""
WebSocket Routes
WebSocket 路由

FastAPI WebSocket endpoint for Clone Agent.
移除了 Supabase 认证，简化为开源版本。

Handles:
- WebSocket connection lifecycle
- Message routing
- Agent processing
- Error handling

ARCHITECTURE NOTE:
The key challenge is that Agent processing and WebSocket message receiving
must be CONCURRENT. When Agent calls a tool (e.g., shell), it sends
`execute_action` to frontend and waits for `action_result`. If the message
loop is blocked by Agent processing, `action_result` cannot be received,
causing timeouts.

Solution: Use asyncio.create_task to run message receiving in background
while Agent processing happens in the main flow.
"""

from __future__ import annotations
import os
import asyncio
import logging
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Header
from pydantic import BaseModel

from .websocket_manager import (
    get_ws_manager,
    WebSocketManager,
    ClientMessageType,
)
from .claude_agent import (
    get_or_create_agent,
    unregister_agent,
    ClaudeAgent,
)

logger = logging.getLogger(__name__)

# Create router - use /api/nexting-agent to match frontend
router = APIRouter(prefix="/api/nexting-agent", tags=["agent-ws"])


# ============================================
# WebSocket Endpoint (No Auth Required)
# ============================================

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: Optional[str] = Query(default=None),
):
    """
    Main WebSocket endpoint for agent communication.
    No authentication required for open-source version.

    Query params:
    - session_id: Optional session ID (generated if not provided)

    Message protocol:

    Client -> Server:
    - chat: { message: string, webcontainer_state?: object }
    - action_result: { action_id: string, success: boolean, result: string }
    - state_update: { ...webcontainer_state }
    - ping: {}

    Server -> Client:
    - text: { content: string }
    - text_delta: { delta: string }
    - tool_call: { id: string, name: string, input: object }
    - tool_result: { id: string, success: boolean, result: string }
    - execute_action: { action_id: string, action_type: string, payload: object }
    - error: { error: string }
    - done: {}
    - pong: {}
    """
    ws_manager = get_ws_manager()

    # No auth - use anonymous user
    user_id = "anonymous"

    # Accept connection
    session = await ws_manager.connect(
        websocket=websocket,
        session_id=session_id,
        user_id=user_id,
    )

    logger.info(f"WebSocket connected: session={session.session_id}")

    # Create/get agent for this session
    agent = get_or_create_agent(
        session_id=session.session_id,
        user_id=user_id,
    )

    # Queue for chat messages (non-chat messages are handled immediately)
    chat_queue: asyncio.Queue = asyncio.Queue()

    # Flag to signal shutdown
    shutdown_event = asyncio.Event()

    async def message_receiver():
        """
        Background task to receive WebSocket messages.

        CRITICAL: This runs concurrently with Agent processing so that
        action_result messages can be received while Agent is waiting.
        """
        try:
            while not shutdown_event.is_set():
                try:
                    # Use wait_for to allow checking shutdown periodically
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=1.0  # Check shutdown every second
                    )
                except asyncio.TimeoutError:
                    continue  # Just check shutdown flag and continue
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON received")
                    try:
                        await ws_manager.send_error(session.session_id, "Invalid JSON")
                    except Exception:
                        pass
                    continue
                except RuntimeError as e:
                    if "not connected" in str(e).lower():
                        logger.info(f"[Receiver] Connection closed: session={session.session_id}")
                        shutdown_event.set()
                        break
                    raise
                except WebSocketDisconnect:
                    logger.info(f"[Receiver] WebSocket disconnected: session={session.session_id}")
                    shutdown_event.set()
                    break

                # Handle message
                result = await ws_manager.handle_message(session.session_id, data)

                # If chat message, put in queue for main loop
                if result and result.get("type") == "chat":
                    await chat_queue.put(result)
                # Other messages (action_result, state_update, ping) are handled
                # immediately by handle_message, no queuing needed

        except asyncio.CancelledError:
            logger.info(f"[Receiver] Task cancelled: session={session.session_id}")
        except Exception as e:
            error_msg = str(e).lower()
            if "not connected" not in error_msg and "closed" not in error_msg:
                logger.error(f"[Receiver] Error: {e}", exc_info=True)
            shutdown_event.set()

    # Start message receiver in background
    receiver_task = asyncio.create_task(message_receiver())

    try:
        while not shutdown_event.is_set():
            try:
                # Wait for chat message with timeout to check shutdown
                chat_data = await asyncio.wait_for(
                    chat_queue.get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue  # Check shutdown flag and continue

            # Process chat message with agent
            # While this runs, message_receiver continues to receive messages
            # including action_result responses from frontend
            await _process_chat(
                agent=agent,
                ws_manager=ws_manager,
                session_id=session.session_id,
                message=chat_data.get("message", ""),
                webcontainer_state=chat_data.get("webcontainer_state"),
                selected_source_id=chat_data.get("selected_source_id"),
            )

    except asyncio.CancelledError:
        logger.info(f"Main loop cancelled: session={session.session_id}")

    except Exception as e:
        error_msg = str(e).lower()
        if "not connected" not in error_msg and "closed" not in error_msg:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await ws_manager.send_error(session.session_id, str(e))
        except Exception:
            pass

    finally:
        # Signal shutdown and cleanup
        shutdown_event.set()
        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass

        await ws_manager.disconnect(session.session_id)
        unregister_agent(session.session_id)
        logger.info(f"WebSocket cleanup complete: session={session.session_id}")


async def _process_chat(
    agent: ClaudeAgent,
    ws_manager: WebSocketManager,
    session_id: str,
    message: str,
    webcontainer_state: Optional[dict] = None,
    selected_source_id: Optional[str] = None,
):
    """
    Process chat message with agent

    Args:
        agent: Claude agent instance
        ws_manager: WebSocket manager
        session_id: Session ID
        message: User message
        webcontainer_state: WebContainer state
        selected_source_id: Selected cache source ID for context
    """
    try:
        async for event in agent.process_message(
            message=message,
            webcontainer_state=webcontainer_state,
            selected_source_id=selected_source_id,
        ):
            event_type = event.get("type")

            if event_type == "text":
                await ws_manager.send_text(session_id, event.get("content", ""))

            elif event_type == "text_delta":
                await ws_manager.send_text_delta(session_id, event.get("delta", ""))

            elif event_type == "tool_call":
                await ws_manager.send_tool_call(
                    session_id=session_id,
                    tool_id=event.get("id", ""),
                    tool_name=event.get("name", ""),
                    tool_input=event.get("input", {}),
                )

            elif event_type == "tool_result":
                await ws_manager.send_tool_result(
                    session_id=session_id,
                    tool_id=event.get("id", ""),
                    success=event.get("success", True),
                    result=event.get("result", ""),
                )

            elif event_type == "error":
                await ws_manager.send_error(session_id, event.get("error", "Unknown error"))

            elif event_type == "done":
                await ws_manager.send_done(session_id)

            elif event_type == "iteration":
                # Optional: Send iteration info for debugging
                pass

    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        await ws_manager.send_error(session_id, str(e))
        await ws_manager.send_done(session_id)


# ============================================
# HTTP Endpoints (for compatibility)
# ============================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "clone-agent",
        "protocol": "websocket",
    }


@router.get("/tools")
async def get_tools():
    """Get available tools"""
    from .mcp_tools import TOOL_DEFINITIONS

    return [
        {"name": t["name"], "description": t["description"]}
        for t in TOOL_DEFINITIONS
    ]


@router.get("/sessions")
async def get_sessions():
    """Get active sessions (for debugging)"""
    ws_manager = get_ws_manager()
    return ws_manager.get_stats()


# ============================================
# Request Models
# ============================================

class ActionResultRequest(BaseModel):
    """Action result from frontend (HTTP fallback)"""
    action_id: str
    success: bool
    result: str
    error: Optional[str] = None


@router.post("/action-result")
async def receive_action_result(
    request: ActionResultRequest,
    session_id: str = Query(...),
):
    """
    Receive action result via HTTP (fallback for WebSocket issues)

    Args:
        request: Action result
        session_id: Session ID

    Returns:
        Acknowledgment
    """
    ws_manager = get_ws_manager()

    ws_manager.resolve_action(
        session_id=session_id,
        action_id=request.action_id,
        success=request.success,
        result=request.result,
        error=request.error,
    )

    return {"status": "received", "action_id": request.action_id}
