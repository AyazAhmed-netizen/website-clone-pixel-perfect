"""
Todo Management Tools

实现TodoRead (oN) 和TodoWrite (yG) 工具,用于管理Agent的任务列表。

功能:
- 读取当前任务列表
- 更新任务状态(pending, in_progress, completed)
- 添加/删除任务
- 任务优先级管理

任务状态会持久化到WebContainer的state中。
"""

from __future__ import annotations
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from .webcontainer_tools import ToolResult


# ============================================
# Todo Models
# ============================================

class TodoStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class TodoItem:
    """单个任务项"""
    content: str
    status: TodoStatus = TodoStatus.PENDING
    activeForm: str = ""
    priority: int = 5  # 1-10, 10最高
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "content": self.content,
            "status": self.status.value if isinstance(self.status, TodoStatus) else self.status,
            "activeForm": self.activeForm,
            "priority": self.priority,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TodoItem':
        """从字典创建"""
        status = data.get("status", TodoStatus.PENDING)
        if isinstance(status, str):
            status = TodoStatus(status)

        return cls(
            content=data.get("content", ""),
            status=status,
            activeForm=data.get("activeForm", ""),
            priority=data.get("priority", 5),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            notes=data.get("notes", ""),
        )


# ============================================
# TodoRead Tool (oN)
# ============================================

def todo_read(
    status: Optional[str] = None,
    priority_min: Optional[int] = None,
    show_completed: bool = False,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    TodoRead (oN) - 读取任务列表

    读取当前的任务列表,可按状态和优先级过滤。

    Args:
        status: 过滤状态 ("pending", "in_progress", "completed")
        priority_min: 最小优先级 (1-10)
        show_completed: 是否显示已完成任务 (默认 False)
        webcontainer_state: WebContainer状态

    Returns:
        ToolResult with formatted todo list
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    # Get todos from state
    todos_data = webcontainer_state.get("todos", [])

    if not todos_data:
        return ToolResult(
            success=True,
            result="📋 Task List: Empty\n\nNo tasks yet. Use todo_write to create tasks."
        )

    # Parse todos
    todos = []
    for item in todos_data:
        if isinstance(item, dict):
            todos.append(TodoItem.from_dict(item))
        elif isinstance(item, TodoItem):
            todos.append(item)

    # Apply filters
    filtered_todos = todos

    if status:
        status_enum = TodoStatus(status)
        filtered_todos = [t for t in filtered_todos if t.status == status_enum]

    if priority_min is not None:
        filtered_todos = [t for t in filtered_todos if t.priority >= priority_min]

    if not show_completed:
        filtered_todos = [t for t in filtered_todos if t.status != TodoStatus.COMPLETED]

    # Format output
    lines = ["📋 Task List\n"]
    lines.append("=" * 60)

    # Group by status
    pending = [t for t in filtered_todos if t.status == TodoStatus.PENDING]
    in_progress = [t for t in filtered_todos if t.status == TodoStatus.IN_PROGRESS]
    completed = [t for t in filtered_todos if t.status == TodoStatus.COMPLETED]

    # In Progress (most important)
    if in_progress:
        lines.append("\n🔄 In Progress:")
        for i, todo in enumerate(in_progress, 1):
            priority_str = f"[P{todo.priority}]" if todo.priority > 5 else ""
            lines.append(f"  {i}. {priority_str} {todo.content}")
            if todo.activeForm:
                lines.append(f"     ➤ {todo.activeForm}")
            if todo.notes:
                lines.append(f"     💡 {todo.notes}")

    # Pending
    if pending:
        lines.append("\n⏳ Pending:")
        for i, todo in enumerate(pending, 1):
            priority_str = f"[P{todo.priority}]" if todo.priority > 5 else ""
            lines.append(f"  {i}. {priority_str} {todo.content}")
            if todo.notes:
                lines.append(f"     💡 {todo.notes}")

    # Completed (if shown)
    if show_completed and completed:
        lines.append("\n✅ Completed:")
        for i, todo in enumerate(completed, 1):
            lines.append(f"  {i}. {todo.content}")
            if todo.completed_at:
                lines.append(f"     ✓ Completed at: {todo.completed_at}")

    # Summary
    lines.append(f"\n{'-' * 60}")
    lines.append(f"Total: {len(filtered_todos)} tasks")
    lines.append(f"  🔄 In Progress: {len(in_progress)}")
    lines.append(f"  ⏳ Pending: {len(pending)}")
    if show_completed:
        lines.append(f"  ✅ Completed: {len(completed)}")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


# ============================================
# TodoWrite Tool (yG)
# ============================================

def todo_write(
    todos: List[Dict[str, Any]],
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    TodoWrite (yG) - 更新任务列表

    完全替换当前的任务列表。用于:
    - 添加新任务
    - 更新任务状态
    - 删除任务
    - 重新排序任务

    IMPORTANT:
    - 每个任务必须有 content, status, activeForm 字段
    - status 必须是 "pending", "in_progress", 或 "completed"
    - 同一时间应该只有一个任务是 "in_progress"

    Args:
        todos: 新的任务列表 (完整列表,会替换现有任务)
        webcontainer_state: WebContainer状态

    Returns:
        ToolResult with action to update state
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    # Validate todos
    if not isinstance(todos, list):
        return ToolResult(
            success=False,
            result="Invalid todos format. Must be a list of todo items."
        )

    # Parse and validate each todo
    validated_todos = []
    in_progress_count = 0

    for i, todo_data in enumerate(todos):
        if not isinstance(todo_data, dict):
            return ToolResult(
                success=False,
                result=f"Invalid todo at index {i}. Must be a dictionary with content, status, and activeForm."
            )

        # Required fields
        if "content" not in todo_data:
            return ToolResult(
                success=False,
                result=f"Todo at index {i} missing required field 'content'"
            )

        if "status" not in todo_data:
            return ToolResult(
                success=False,
                result=f"Todo at index {i} missing required field 'status'"
            )

        if "activeForm" not in todo_data:
            return ToolResult(
                success=False,
                result=f"Todo at index {i} missing required field 'activeForm'"
            )

        # Validate status
        status = todo_data["status"]
        if status not in ["pending", "in_progress", "completed"]:
            return ToolResult(
                success=False,
                result=f"Invalid status '{status}' at index {i}. Must be 'pending', 'in_progress', or 'completed'."
            )

        # Count in_progress tasks
        if status == "in_progress":
            in_progress_count += 1

        # Create TodoItem
        try:
            todo_item = TodoItem.from_dict(todo_data)
            validated_todos.append(todo_item)
        except Exception as e:
            return ToolResult(
                success=False,
                result=f"Error parsing todo at index {i}: {e}"
            )

    # Warn if multiple tasks are in progress
    if in_progress_count > 1:
        return ToolResult(
            success=False,
            result=f"Warning: {in_progress_count} tasks are marked as 'in_progress'. Only one task should be in progress at a time."
        )

    if in_progress_count == 0 and validated_todos:
        return ToolResult(
            success=False,
            result="Warning: No tasks are marked as 'in_progress'. At least one task should be in progress."
        )

    # Convert to dict format for action
    todos_dict = [todo.to_dict() for todo in validated_todos]

    # Create action to update WebContainer state
    action = {
        "type": "update_todos",
        "payload": {
            "todos": todos_dict
        }
    }

    # Format summary
    pending = sum(1 for t in validated_todos if t.status == TodoStatus.PENDING)
    in_progress = sum(1 for t in validated_todos if t.status == TodoStatus.IN_PROGRESS)
    completed = sum(1 for t in validated_todos if t.status == TodoStatus.COMPLETED)

    summary = f"Task list updated: {len(validated_todos)} total tasks\n"
    summary += f"  🔄 In Progress: {in_progress}\n"
    summary += f"  ⏳ Pending: {pending}\n"
    summary += f"  ✅ Completed: {completed}"

    return ToolResult(
        success=True,
        result=summary,
        action=action
    )


# ============================================
# Tool Definitions
# ============================================

def get_todo_tool_definitions() -> List[dict]:
    """
    获取Todo工具定义

    Returns:
        List of tool definitions in Claude API format
    """
    return [
        {
            "name": "todo_read",
            "description": """Read the current task list. Shows tasks organized by status (in progress, pending, completed).

Use this to:
- Check what tasks are currently active
- Review pending tasks
- See completed work (with show_completed=true)

The task list helps track progress and ensure nothing is forgotten.

Example:
- todo_read() - Show active and pending tasks
- todo_read(status="in_progress") - Show only in-progress tasks
- todo_read(show_completed=true) - Include completed tasks""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                        "description": "Filter by status (optional)"
                    },
                    "priority_min": {
                        "type": "integer",
                        "description": "Show only tasks with priority >= this value (1-10)"
                    },
                    "show_completed": {
                        "type": "boolean",
                        "description": "Include completed tasks (default false)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "todo_write",
            "description": """Update the task list. This REPLACES the entire task list with the new one.

CRITICAL RULES:
1. Each task must have: content, status, activeForm
2. status must be "pending", "in_progress", or "completed"
3. EXACTLY ONE task should be "in_progress" (not zero, not more)
4. Update tasks immediately:
   - Mark as in_progress BEFORE starting work
   - Mark as completed IMMEDIATELY after finishing
   - Don't batch updates

Task Structure:
{
  "content": "Task description (imperative: 'Fix bug', 'Add feature')",
  "status": "pending" | "in_progress" | "completed",
  "activeForm": "Present continuous form ('Fixing bug', 'Adding feature')",
  "priority": 5,  // Optional, 1-10
  "notes": ""  // Optional notes
}

Example:
todo_write(todos=[
  {"content": "Fix authentication bug", "status": "in_progress", "activeForm": "Fixing authentication bug"},
  {"content": "Add unit tests", "status": "pending", "activeForm": "Adding unit tests"},
  {"content": "Update documentation", "status": "completed", "activeForm": "Updating documentation"}
])

WHEN TO USE:
- After starting a new task - mark it in_progress
- After finishing a task - mark it completed immediately
- When discovering new tasks - add them as pending
- When tasks become irrelevant - remove them completely""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "Task description (imperative form)"
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "Task status"
                                },
                                "activeForm": {
                                    "type": "string",
                                    "description": "Present continuous form of the task"
                                },
                                "priority": {
                                    "type": "integer",
                                    "description": "Priority 1-10 (optional, default 5)"
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "Additional notes (optional)"
                                }
                            },
                            "required": ["content", "status", "activeForm"]
                        },
                        "description": "Complete task list (replaces existing)"
                    }
                },
                "required": ["todos"]
            }
        }
    ]


# ============================================
# Tool Registry
# ============================================

TODO_TOOLS = {
    "todo_read": todo_read,
    "todo_write": todo_write,
}


def get_todo_tools():
    """Get all todo management tools"""
    return TODO_TOOLS
