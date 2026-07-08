"""
Agent State Types
代理状态类型定义
"""

from dataclasses import dataclass
from typing import Optional, Any, Dict, List


@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    result: str
    action: Optional[dict] = None  # Action to send to frontend (if needed)

    def to_content(self) -> str:
        """Convert to string content for LLM"""
        if self.success:
            return self.result
        return f"Error: {self.result}"


@dataclass
class AgentState:
    """Agent execution state"""
    messages: List[Dict[str, Any]]
    webcontainer_state: Optional[Dict[str, Any]] = None
    current_tool: Optional[str] = None
    iteration: int = 0
    max_iterations: int = 50
    is_complete: bool = False
    error: Optional[str] = None


@dataclass
class WorkerState:
    """Worker agent state"""
    worker_id: str
    section_name: str
    status: str = "pending"  # pending, running, completed, error
    files_written: List[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.files_written is None:
            self.files_written = []
