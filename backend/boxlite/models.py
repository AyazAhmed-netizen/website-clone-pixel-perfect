"""
BoxLite Models

Pydantic models for BoxLite sandbox operations.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ============================================
# Enums
# ============================================

class SandboxStatus(str, Enum):
    """Sandbox lifecycle status"""
    CREATING = "creating"
    BOOTING = "booting"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class ToolType(str, Enum):
    """Available tool types"""
    # File operations
    WRITE_FILE = "write_file"
    READ_FILE = "read_file"
    DELETE_FILE = "delete_file"
    CREATE_DIRECTORY = "create_directory"
    RENAME_FILE = "rename_file"
    EDIT_FILE = "edit_file"
    LIST_FILES = "list_files"

    # Terminal operations
    SHELL = "shell"
    RUN_COMMAND = "run_command"
    INSTALL_DEPENDENCIES = "install_dependencies"
    START_DEV_SERVER = "start_dev_server"
    STOP_PROCESS = "stop_process"

    # Preview operations
    TAKE_SCREENSHOT = "take_screenshot"
    GET_PREVIEW_DOM = "get_preview_dom"
    GET_VISUAL_SUMMARY = "get_visual_summary"
    GET_BUILD_ERRORS = "get_build_errors"
    GET_CONSOLE_MESSAGES = "get_console_messages"


# ============================================
# File Models
# ============================================

class FileEntry(BaseModel):
    """A file or directory entry"""
    name: str
    path: str
    type: Literal["file", "directory"]
    size: Optional[int] = None
    modified_at: Optional[datetime] = None


class FileContent(BaseModel):
    """File with content"""
    path: str
    content: str
    encoding: str = "utf-8"


# ============================================
# Terminal Models
# ============================================

class TerminalSession(BaseModel):
    """Terminal session info"""
    id: str
    name: str = "Terminal"
    is_running: bool = False
    command: Optional[str] = None
    exit_code: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ProcessOutput(BaseModel):
    """Output from a process"""
    terminal_id: str
    data: str
    stream: Literal["stdout", "stderr"] = "stdout"
    timestamp: datetime = Field(default_factory=datetime.now)


class CommandResult(BaseModel):
    """Result of command execution"""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


# ============================================
# Preview Models
# ============================================

class PreviewState(BaseModel):
    """State of the preview/dev server"""
    url: Optional[str] = None
    is_loading: bool = False
    has_error: bool = False
    error_message: Optional[str] = None


class ConsoleMessage(BaseModel):
    """Console message from preview"""
    type: Literal["log", "info", "warn", "error", "debug"] = "log"
    args: List[Any] = []
    timestamp: datetime = Field(default_factory=datetime.now)
    stack: Optional[str] = None


class DOMNode(BaseModel):
    """DOM node from preview"""
    tag: str
    id: Optional[str] = None
    classes: List[str] = []
    text: Optional[str] = None
    rect: Optional[Dict[str, float]] = None  # x, y, width, height
    children: List["DOMNode"] = []


# Enable self-referencing
DOMNode.model_rebuild()


class VisualSummary(BaseModel):
    """Quick visual summary of preview"""
    has_content: bool
    visible_element_count: int = 0
    text_preview: str = ""
    viewport: Dict[str, int] = {"width": 1280, "height": 720}
    body_size: Dict[str, int] = {"width": 1280, "height": 720}
    background_color: Optional[str] = None
    # Additional fields for diagnostics
    preview_url: Optional[str] = None
    screenshot_base64: Optional[str] = None
    page_title: Optional[str] = None
    visible_text: Optional[str] = None
    error: Optional[str] = None


class ErrorSource(str, Enum):
    """Error detection source"""
    TERMINAL = "terminal"
    BROWSER = "browser"
    STATIC = "static"


class BuildError(BaseModel):
    """Build/compilation error"""
    type: str  # vite-overlay, react-error-boundary, syntax-error, etc.
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    frame: Optional[str] = None  # Code context
    stack: Optional[str] = None
    suggestion: Optional[str] = None  # Auto-generated fix suggestion
    source: ErrorSource = ErrorSource.TERMINAL  # Which detector found this


# ============================================
# Sandbox State Models
# ============================================

class SandboxState(BaseModel):
    """Complete sandbox state"""
    sandbox_id: str
    status: SandboxStatus = SandboxStatus.CREATING
    error: Optional[str] = None

    # File system
    files: Dict[str, str] = {}  # path -> content
    active_file: Optional[str] = None

    # Terminals
    terminals: List[TerminalSession] = []
    active_terminal_id: Optional[str] = None

    # Preview
    preview_url: Optional[str] = None
    preview: PreviewState = Field(default_factory=PreviewState)
    console_messages: List[ConsoleMessage] = []

    # Port forwarding
    forwarded_ports: Dict[int, str] = {}  # internal_port -> external_url

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ============================================
# Tool Request/Response Models
# ============================================

class ToolRequest(BaseModel):
    """Request to execute a tool"""
    tool_type: ToolType
    payload: Dict[str, Any]
    request_id: Optional[str] = None


class ToolResponse(BaseModel):
    """Response from tool execution"""
    success: bool
    result: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    execution_time_ms: Optional[int] = None


# ============================================
# WebSocket Message Models
# ============================================

class WSMessageType(str, Enum):
    """WebSocket message types"""
    # Client -> Server
    CHAT = "chat"
    EXECUTE_TOOL = "execute_tool"
    STATE_REQUEST = "state_request"
    PING = "ping"

    # Server -> Client
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE_UPDATE = "state_update"
    TERMINAL_OUTPUT = "terminal_output"
    ERROR = "error"
    DONE = "done"
    PONG = "pong"


class WSMessage(BaseModel):
    """WebSocket message"""
    type: WSMessageType
    payload: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================
# Action Models (for Agent)
# ============================================

class ActionPayload(BaseModel):
    """Payload for an action"""
    action_type: ToolType
    params: Dict[str, Any] = {}


class ActionResult(BaseModel):
    """Result of an action"""
    action_id: str
    success: bool
    result: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
