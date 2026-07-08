"""
WebSocket Manager

WebSocket connection management and session state.

Core functions:
- Connection lifecycle management
- Session state maintenance
- Message routing
- Tool execution result waiting queue
"""

from __future__ import annotations
import asyncio
import logging
import json
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


# ============================================
# Message Types
# ============================================

class ClientMessageType(str, Enum):
    """Messages from frontend to backend"""
    CHAT = "chat"                    # User chat message
    ACTION_RESULT = "action_result"  # Tool execution result
    STATE_UPDATE = "state_update"    # WebContainer state update
    PING = "ping"                    # Heartbeat


class ServerMessageType(str, Enum):
    """Messages from backend to frontend"""
    TEXT = "text"                    # Agent text response
    TEXT_DELTA = "text_delta"        # Streaming text delta
    TOOL_CALL = "tool_call"          # Tool call notification
    TOOL_RESULT = "tool_result"      # Tool execution result
    EXECUTE_ACTION = "execute_action"  # Request frontend to execute action
    ERROR = "error"                  # Error message
    DONE = "done"                    # Completion signal
    PONG = "pong"                    # Heartbeat response
    # Worker Agent events (Multi-Agent communication)
    WORKER_SPAWNED = "worker_spawned"        # Worker created
    WORKER_STARTED = "worker_started"        # Worker started processing
    WORKER_ITERATION = "worker_iteration"    # Worker iteration update (NEW)
    WORKER_TEXT_DELTA = "worker_text_delta"  # Worker reasoning text (NEW)
    WORKER_TOOL_CALL = "worker_tool_call"    # Worker called a tool
    WORKER_TOOL_RESULT = "worker_tool_result"  # Worker tool result
    WORKER_COMPLETED = "worker_completed"    # Worker finished
    WORKER_ERROR = "worker_error"            # Worker error


# ============================================
# Data Classes
# ============================================

@dataclass
class PendingAction:
    """Pending action waiting for frontend result"""
    action_id: str
    action_type: str
    payload: Dict[str, Any]
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.now)
    timeout: float = 60.0


@dataclass
class WebContainerState:
    """Current WebContainer state from frontend"""
    status: str = "idle"
    files: Dict[str, str] = field(default_factory=dict)
    active_file: Optional[str] = None
    terminals: list = field(default_factory=list)
    preview_url: Optional[str] = None
    preview: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)
    # 新增：状态版本号，用于防止旧状态覆盖新状态
    version: int = 0
    # 新增：是否过期标志
    stale: bool = False


@dataclass
class Session:
    """WebSocket session"""
    session_id: str
    websocket: WebSocket
    user_id: Optional[str] = None
    webcontainer_state: WebContainerState = field(default_factory=WebContainerState)
    pending_actions: Dict[str, PendingAction] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    is_processing: bool = False


# ============================================
# WebSocket Manager
# ============================================

class WebSocketManager:
    """
    WebSocket connection and session manager

    Features:
    - Multi-session support
    - Bidirectional communication
    - Tool execution result waiting
    - Automatic cleanup
    """

    def __init__(self):
        # Active sessions: session_id -> Session
        self._sessions: Dict[str, Session] = {}

        # Message handlers
        self._message_handlers: Dict[str, Callable] = {}

        logger.info("WebSocketManager initialized")

    # ============================================
    # Connection Management
    # ============================================

    async def connect(
        self,
        websocket: WebSocket,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Session:
        """
        Accept WebSocket connection and create session

        Args:
            websocket: FastAPI WebSocket instance
            session_id: Optional session ID (generate if not provided)
            user_id: Optional user ID for authentication

        Returns:
            Created session
        """
        await websocket.accept()

        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        # Create session
        session = Session(
            session_id=session_id,
            websocket=websocket,
            user_id=user_id,
        )

        self._sessions[session_id] = session

        logger.info(f"WebSocket connected: session={session_id}, user={user_id}")

        # Don't send initial message - let the client initiate communication
        # This avoids race conditions where the connection closes before the message is sent

        return session

    async def disconnect(self, session_id: str):
        """
        Disconnect session and cleanup

        Args:
            session_id: Session ID to disconnect
        """
        session = self._sessions.pop(session_id, None)

        if session:
            # Cancel pending actions
            for action in session.pending_actions.values():
                if not action.future.done():
                    action.future.cancel()

            logger.info(f"WebSocket disconnected: session={session_id}")

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> Dict[str, Session]:
        """Get all active sessions"""
        return self._sessions.copy()

    # ============================================
    # Message Sending
    # ============================================

    async def send(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Send message to specific session

        Args:
            session_id: Target session ID
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return False

        try:
            await session.websocket.send_json(message)
            return True
        except Exception as e:
            # Don't log empty errors (connection closed gracefully)
            error_msg = str(e)
            if error_msg and "close" not in error_msg.lower():
                logger.warning(f"Failed to send message to {session_id}: {e}")
            return False

    async def send_text(self, session_id: str, content: str):
        """Send text message"""
        await self.send(session_id, {
            "type": ServerMessageType.TEXT.value,
            "payload": {"content": content}
        })

    async def send_text_delta(self, session_id: str, delta: str):
        """Send streaming text delta"""
        await self.send(session_id, {
            "type": ServerMessageType.TEXT_DELTA.value,
            "payload": {"delta": delta}
        })

    async def send_tool_call(
        self,
        session_id: str,
        tool_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
    ):
        """Send tool call notification"""
        await self.send(session_id, {
            "type": ServerMessageType.TOOL_CALL.value,
            "payload": {
                "id": tool_id,
                "name": tool_name,
                "input": tool_input,
            }
        })

    async def send_tool_result(
        self,
        session_id: str,
        tool_id: str,
        success: bool,
        result: str,
    ):
        """Send tool result"""
        await self.send(session_id, {
            "type": ServerMessageType.TOOL_RESULT.value,
            "payload": {
                "id": tool_id,
                "success": success,
                "result": result,
            }
        })

    async def send_error(self, session_id: str, error: str):
        """Send error message"""
        await self.send(session_id, {
            "type": ServerMessageType.ERROR.value,
            "payload": {"error": error}
        })

    async def send_done(self, session_id: str):
        """Send completion signal"""
        await self.send(session_id, {
            "type": ServerMessageType.DONE.value,
            "payload": {}
        })

    # ============================================
    # Worker Agent Events (Multi-Agent Communication)
    # ============================================

    async def send_worker_spawned(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
        task_description: str,
        input_data: Dict[str, Any],
        total_workers: int,
        display_name: str = "",
    ):
        """
        Send worker spawned event

        Called when Master Agent creates a new Worker.
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_SPAWNED.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
                "display_name": display_name or section_name,  # Human-friendly name
                "task_description": task_description,
                "input_data": input_data,
                "total_workers": total_workers,
            }
        })

    async def send_worker_started(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
    ):
        """
        Send worker started event

        Called when Worker begins processing.
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_STARTED.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
            }
        })

    async def send_worker_iteration(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
        iteration: int,
        max_iterations: int,
    ):
        """
        Send worker iteration update event

        Called when Worker starts a new iteration in the agent loop.
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_ITERATION.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
                "iteration": iteration,
                "max_iterations": max_iterations,
            }
        })

    async def send_worker_text_delta(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
        text: str,
        iteration: int,
    ):
        """
        Send worker reasoning text delta

        Called when Worker receives text from Claude (reasoning/thinking).
        This allows frontend to show the Worker's thought process.
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_TEXT_DELTA.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
                "text": text,
                "iteration": iteration,
            }
        })

    async def send_worker_tool_call(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
        tool_name: str,
        tool_input: Dict[str, Any],
    ):
        """
        Send worker tool call event

        Called when Worker calls a tool.
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_TOOL_CALL.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
                "tool_name": tool_name,
                "tool_input": tool_input,
            }
        })

    async def send_worker_tool_result(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
        tool_name: str,
        result: str,
        success: bool = True,
    ):
        """
        Send worker tool result event

        Called when Worker tool execution completes.
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_TOOL_RESULT.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
                "tool_name": tool_name,
                "result": result,
                "success": success,
            }
        })

    async def send_worker_completed(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
        success: bool,
        files: Dict[str, str],
        summary: str,
        error: Optional[str] = None,
    ):
        """
        Send worker completed event

        Called when Worker finishes (success or failure).
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_COMPLETED.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
                "success": success,
                "files": list(files.keys()),  # Only send file paths
                "file_count": len(files),
                "summary": summary,
                "error": error,
            }
        })

    async def send_worker_error(
        self,
        session_id: str,
        worker_id: str,
        section_name: str,
        error: str,
    ):
        """
        Send worker error event

        Called when Worker encounters an error.
        """
        await self.send(session_id, {
            "type": ServerMessageType.WORKER_ERROR.value,
            "payload": {
                "worker_id": worker_id,
                "section_name": section_name,
                "error": error,
            }
        })

    # ============================================
    # Tool Execution (Frontend Bridge)
    # ============================================

    async def execute_action(
        self,
        session_id: str,
        action_type: str,
        payload: Dict[str, Any],
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """
        Request frontend to execute action and wait for result

        This is the key mechanism for MCP tools to interact with WebContainer.

        Args:
            session_id: Target session ID
            action_type: Action type (shell, write_file, etc.)
            payload: Action payload
            timeout: Timeout in seconds

        Returns:
            Action result from frontend

        Raises:
            asyncio.TimeoutError: If timeout reached
            RuntimeError: If session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Session not found: {session_id}")

        # Generate action ID
        action_id = str(uuid.uuid4())

        # Create future for waiting result
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # Register pending action
        pending = PendingAction(
            action_id=action_id,
            action_type=action_type,
            payload=payload,
            future=future,
            timeout=timeout,
        )
        session.pending_actions[action_id] = pending

        logger.info(f"Executing action: {action_type} ({action_id})")

        try:
            # Send execute request to frontend
            await self.send(session_id, {
                "type": ServerMessageType.EXECUTE_ACTION.value,
                "payload": {
                    "action_id": action_id,
                    "action_type": action_type,
                    "payload": payload,
                }
            })

            # Wait for result with timeout
            result = await asyncio.wait_for(future, timeout=timeout)

            logger.info(f"Action completed: {action_id}")

            return result

        except asyncio.TimeoutError:
            logger.error(f"Action timeout: {action_id}")
            raise

        except asyncio.CancelledError:
            logger.warning(f"Action cancelled: {action_id}")
            raise

        finally:
            # Cleanup
            session.pending_actions.pop(action_id, None)

    def resolve_action(
        self,
        session_id: str,
        action_id: str,
        success: bool,
        result: str,
        error: Optional[str] = None,
    ):
        """
        Resolve pending action with result from frontend

        Called when frontend sends action_result message.

        Args:
            session_id: Session ID
            action_id: Action ID to resolve
            success: Whether action succeeded
            result: Action result
            error: Error message if failed
        """
        logger.info(f"[WS] resolve_action called: session={session_id}, action_id={action_id}")

        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"[WS] Session not found for action resolution: {session_id}")
            logger.warning(f"[WS] Available sessions: {list(self._sessions.keys())}")
            return

        pending = session.pending_actions.get(action_id)
        if not pending:
            logger.warning(f"[WS] Pending action not found: {action_id}")
            logger.warning(f"[WS] Available pending actions: {list(session.pending_actions.keys())}")
            return

        if not pending.future.done():
            pending.future.set_result({
                "success": success,
                "result": result,
                "error": error,
            })
            logger.info(f"[WS] Action resolved successfully: {action_id}, success={success}")
        else:
            logger.warning(f"[WS] Future already done for action: {action_id}")

    # ============================================
    # State Management
    # ============================================

    def update_webcontainer_state(
        self,
        session_id: str,
        state: Dict[str, Any],
    ):
        """
        Update WebContainer state from frontend

        Args:
            session_id: Session ID
            state: New state from frontend
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"[StateUpdate] Session not found: {session_id}")
            return

        # 获取新状态的版本号
        new_version = state.get("version", 0)
        current_version = session.webcontainer_state.version

        # 只接受更新或相同版本的状态
        if new_version < current_version:
            logger.warning(
                f"[StateUpdate] Ignoring stale state: version {new_version} < {current_version}"
            )
            return

        # Update state fields
        session.webcontainer_state.status = state.get("status", "idle")
        session.webcontainer_state.files = state.get("files", {})
        session.webcontainer_state.active_file = state.get("active_file")
        session.webcontainer_state.terminals = state.get("terminals", [])
        session.webcontainer_state.preview_url = state.get("preview_url")
        session.webcontainer_state.preview = state.get("preview", {})
        session.webcontainer_state.error = state.get("error")
        session.webcontainer_state.last_updated = datetime.now()
        session.webcontainer_state.version = new_version
        session.webcontainer_state.stale = False

        file_count = len(session.webcontainer_state.files)
        logger.info(
            f"[StateUpdate] Updated: session={session_id[:8]}, "
            f"version={new_version}, files={file_count}"
        )

    def get_webcontainer_state(self, session_id: str) -> Optional[WebContainerState]:
        """Get current WebContainer state for session"""
        session = self._sessions.get(session_id)
        if session:
            return session.webcontainer_state
        return None

    async def request_state_refresh(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        请求前端发送最新的 WebContainer 状态

        用于确保 Agent 在每轮对话开始时拥有最新的文件系统状态。
        这解决了多轮对话时状态不同步的问题。

        Args:
            session_id: Session ID

        Returns:
            最新的状态数据，如果失败则返回 None
        """
        session = self._sessions.get(session_id)
        if not session or not session.websocket:
            logger.warning(f"[StateRefresh] Session not connected: {session_id}")
            return None

        try:
            # 生成请求 ID
            request_id = f"refresh_{uuid.uuid4().hex[:8]}"

            # 创建等待响应的 Future
            loop = asyncio.get_event_loop()
            future = loop.create_future()

            # 注册待处理请求
            pending = PendingAction(
                action_id=request_id,
                action_type="state_refresh",
                payload={},
                future=future,
                timeout=10.0,
            )
            session.pending_actions[request_id] = pending

            logger.info(f"[StateRefresh] Requesting state refresh: {session_id[:8]}")

            # 发送刷新请求到前端
            await self.send(session_id, {
                "type": "request_state_refresh",
                "payload": {
                    "request_id": request_id,
                }
            })

            # 等待前端响应（带超时）
            result = await asyncio.wait_for(future, timeout=10.0)

            # 更新状态
            if result and isinstance(result, dict):
                state_data = result.get("state", result)
                self.update_webcontainer_state(session_id, state_data)
                logger.info(f"[StateRefresh] State refreshed successfully: {session_id[:8]}")
                return state_data

            return None

        except asyncio.TimeoutError:
            logger.warning(f"[StateRefresh] Timeout waiting for state: {session_id[:8]}")
            return None
        except Exception as e:
            logger.error(f"[StateRefresh] Error: {e}")
            return None
        finally:
            # 清理待处理请求
            session.pending_actions.pop(request_id, None)

    def mark_state_stale(self, session_id: str):
        """标记状态为过期（当检测到文件变化时调用）"""
        session = self._sessions.get(session_id)
        if session:
            session.webcontainer_state.stale = True
            logger.debug(f"[State] Marked stale: {session_id[:8]}")

    # ============================================
    # Message Handling
    # ============================================

    async def handle_message(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Handle incoming message from frontend

        Args:
            session_id: Session ID
            message: Received message

        Returns:
            Response data if applicable
        """
        msg_type = message.get("type")
        payload = message.get("payload", {})

        # Log all messages for debugging
        logger.info(f"[WS] Received message: type={msg_type}, session={session_id}")

        if msg_type == ClientMessageType.PING.value:
            # Respond to heartbeat
            await self.send(session_id, {
                "type": ServerMessageType.PONG.value,
                "payload": {}
            })
            return None

        elif msg_type == ClientMessageType.ACTION_RESULT.value:
            # Resolve pending action
            action_id = payload.get("action_id")
            success = payload.get("success", False)
            result = payload.get("result", "")
            error = payload.get("error")

            logger.info(f"[WS] ACTION_RESULT received: action_id={action_id}, success={success}, result_len={len(result) if result else 0}")

            self.resolve_action(
                session_id=session_id,
                action_id=action_id,
                success=success,
                result=result,
                error=error,
            )
            return None

        elif msg_type == ClientMessageType.STATE_UPDATE.value:
            # Update WebContainer state
            self.update_webcontainer_state(session_id, payload)
            return None

        elif msg_type == ClientMessageType.CHAT.value:
            # Chat message - return for processing
            return {
                "type": "chat",
                "message": payload.get("message", ""),
                "webcontainer_state": payload.get("webcontainer_state"),
                "selected_source_id": payload.get("selected_source_id"),
            }

        elif msg_type == "state_refresh_response":
            # 响应状态刷新请求
            request_id = payload.get("request_id")
            state = payload.get("state", {})

            logger.info(f"[WS] State refresh response: request_id={request_id}")

            # 解析待处理的刷新请求
            session = self._sessions.get(session_id)
            if session and request_id in session.pending_actions:
                pending = session.pending_actions[request_id]
                if not pending.future.done():
                    pending.future.set_result({"state": state})
            return None

        elif msg_type == "file_changed":
            # 前端文件发生变化通知
            event = payload.get("event")
            filename = payload.get("filename")

            logger.info(f"[WS] File changed: {event} - {filename}")

            # 标记状态为过期，下次读取时会刷新
            self.mark_state_stale(session_id)
            return None

        else:
            logger.warning(f"Unknown message type: {msg_type}")
            return None

    # ============================================
    # Utility Methods
    # ============================================

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            "active_sessions": len(self._sessions),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "pending_actions": len(s.pending_actions),
                    "is_processing": s.is_processing,
                    "created_at": s.created_at.isoformat(),
                }
                for s in self._sessions.values()
            ]
        }


# ============================================
# Global Instance
# ============================================

# Singleton instance
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    """Get or create WebSocket manager singleton"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
