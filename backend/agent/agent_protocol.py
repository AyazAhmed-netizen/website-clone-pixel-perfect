"""
Agent Communication Protocol

Defines structured data types for communication between Main Agent and Worker Agents.
This module establishes a clear protocol for:
1. Worker reports (individual worker -> manager)
2. Tool results (manager -> main agent)
3. Next action signals (what the main agent should do next)

Design Philosophy:
- Agent-to-Agent communication should be structured, not prose
- Clear status signals enable reliable multi-agent coordination
- Next actions are part of the protocol, not suggestions
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import json


# ============================================
# Status Enums
# ============================================

class ToolStatus(str, Enum):
    """Status of a tool execution"""
    COMPLETE = "complete"      # All tasks finished successfully
    PARTIAL = "partial"        # Some tasks succeeded, some failed
    FAILED = "failed"          # All tasks failed
    IN_PROGRESS = "in_progress"  # Still running (for async operations)


class WorkerStatus(str, Enum):
    """Status of an individual worker"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


# ============================================
# Worker Report (Worker -> Manager)
# ============================================

@dataclass
class WorkerReport:
    """
    Report from a single Worker Agent to the Manager.

    This is the structured message a worker sends back after completing
    (or failing) its task.
    """
    section_name: str
    status: WorkerStatus

    # What was created
    files_created: List[str] = field(default_factory=list)

    # Brief message for the main agent
    message: str = ""

    # Error info (if failed)
    error: Optional[str] = None
    error_type: Optional[str] = None

    # Metrics
    duration_ms: int = 0
    iterations: int = 0
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "section": self.section_name,
            "status": self.status.value if isinstance(self.status, WorkerStatus) else self.status,
            "files": self.files_created,
            "message": self.message,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


# ============================================
# Next Action (What Main Agent Should Do)
# ============================================

@dataclass
class NextAction:
    """
    Specifies what the Main Agent should do next.

    This is NOT a suggestion - it's part of the tool protocol.
    The main agent should execute this action.
    """
    required: bool = True
    tool: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required": self.required,
            "tool": self.tool,
            "params": self.params,
            "reason": self.reason,
        }

    def to_instruction(self) -> str:
        """Convert to a clear instruction string"""
        if not self.tool:
            return ""

        # Format params for display
        if self.params:
            params_str = ", ".join(f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}'
                                   for k, v in self.params.items())
            return f'{self.tool}({params_str})'
        return f'{self.tool}()'


# ============================================
# Tool Result (Manager -> Main Agent)
# ============================================

@dataclass
class SpawnWorkersResult:
    """
    Result from spawn_section_workers tool.

    This is the structured response that the Main Agent receives
    after all workers have completed.
    """
    # Overall status
    status: ToolStatus

    # Summary counts
    workers_total: int = 0
    workers_success: int = 0
    workers_failed: int = 0

    # Files created by all workers
    files_created: List[str] = field(default_factory=list)

    # Individual worker reports
    worker_reports: List[WorkerReport] = field(default_factory=list)

    # What to do next
    next_action: Optional[NextAction] = None

    # Total duration
    duration_ms: int = 0

    # Any errors at the manager level
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "tool_status": self.status.value if isinstance(self.status, ToolStatus) else self.status,
            "result": {
                "workers_total": self.workers_total,
                "workers_success": self.workers_success,
                "workers_failed": self.workers_failed,
                "files_created": self.files_created,
                "duration_ms": self.duration_ms,
            },
            "worker_reports": [wr.to_dict() for wr in self.worker_reports],
            "next_action": self.next_action.to_dict() if self.next_action else None,
            "errors": self.errors if self.errors else None,
        }

    def to_agent_message(self) -> str:
        """
        Convert to a message string for the Main Agent.

        Format: Brief summary + JSON data + clear next action
        """
        lines = []

        # Status header
        if self.status == ToolStatus.COMPLETE:
            lines.append(f"## TOOL COMPLETE: spawn_section_workers")
        elif self.status == ToolStatus.PARTIAL:
            lines.append(f"## TOOL PARTIAL: spawn_section_workers ({self.workers_success}/{self.workers_total} succeeded)")
        else:
            lines.append(f"## TOOL FAILED: spawn_section_workers")

        lines.append("")

        # Result summary
        lines.append(f"Workers: {self.workers_success}/{self.workers_total} successful")
        lines.append(f"Files created: {len(self.files_created)}")
        lines.append(f"Duration: {self.duration_ms}ms")
        lines.append("")

        # Worker reports (brief)
        if self.worker_reports:
            lines.append("### Worker Reports:")
            for wr in self.worker_reports:
                status_icon = "✓" if wr.status == WorkerStatus.SUCCESS else "✗"
                files_count = len(wr.files_created)
                lines.append(f"  {status_icon} {wr.section_name}: {files_count} file(s)")
            lines.append("")

        # Errors (if any)
        if self.errors:
            lines.append("### Errors:")
            for err in self.errors:
                lines.append(f"  - {err}")
            lines.append("")

        # Next actions (CRITICAL - error checking required!)
        lines.append("---")
        lines.append("### ⚠️ REQUIRED NEXT STEPS (DO NOT SKIP!):")
        lines.append("")
        lines.append("```")
        lines.append("1. [Dev server auto-started - wait 3-5 seconds for HMR to reload]")
        lines.append("2. get_build_errors()  ← CRITICAL: Check for compilation errors!")
        lines.append("3. If errors found → fix them → get_build_errors() again")
        lines.append("```")
        lines.append("")
        lines.append("⛔ **DO NOT declare task complete without checking get_build_errors()!**")
        lines.append("⛔ **DO NOT skip error checking even if workers succeeded!**")

        return "\n".join(lines)


# ============================================
# Factory Functions
# ============================================

def create_shell_action(command: str, background: bool = True, reason: str = "") -> NextAction:
    """Create a NextAction for shell command"""
    return NextAction(
        required=True,
        tool="shell",
        params={"command": command, "background": background},
        reason=reason or "Execute shell command",
    )


def create_screenshot_action(reason: str = "") -> NextAction:
    """Create a NextAction for taking screenshot"""
    return NextAction(
        required=True,
        tool="take_screenshot",
        params={},
        reason=reason or "Verify the visual result",
    )


def create_diagnose_action(reason: str = "") -> NextAction:
    """Create a NextAction for diagnosing preview state"""
    return NextAction(
        required=True,
        tool="diagnose_preview_state",
        params={},
        reason=reason or "Check for build or runtime errors",
    )


def create_get_build_errors_action(reason: str = "") -> NextAction:
    """Create a NextAction for checking build errors"""
    return NextAction(
        required=True,
        tool="get_build_errors",
        params={},
        reason=reason or "Check for compilation errors after workers completed",
    )


# ============================================
# Result Builders
# ============================================

def build_spawn_workers_result(
    worker_results: List[Any],  # List of WorkerResult from worker_agent.py
    written_files: List[str],
    duration_ms: int,
    errors: List[str] = None,
) -> SpawnWorkersResult:
    """
    Build a SpawnWorkersResult from worker execution results.

    Args:
        worker_results: List of WorkerResult objects from workers
        written_files: List of file paths that were written
        duration_ms: Total execution duration
        errors: Any manager-level errors

    Returns:
        SpawnWorkersResult ready to send to main agent
    """
    # Convert WorkerResult to WorkerReport
    reports = []
    success_count = 0
    failed_count = 0

    for wr in worker_results:
        # Determine status
        if wr.success:
            status = WorkerStatus.SUCCESS
            success_count += 1
        elif "timeout" in str(wr.error or "").lower():
            status = WorkerStatus.TIMEOUT
            failed_count += 1
        else:
            status = WorkerStatus.FAILED
            failed_count += 1

        report = WorkerReport(
            section_name=wr.section_name,
            status=status,
            files_created=list(wr.files.keys()) if wr.files else [],
            message=wr.summary or ("Component created" if wr.success else "Failed"),
            error=wr.error if not wr.success else None,
            error_type=getattr(wr, 'error_type', None),
            duration_ms=wr.duration_ms,
            iterations=wr.iterations,
            retry_count=wr.retry_count,
        )
        reports.append(report)

    # Determine overall status
    total = len(worker_results)
    if failed_count == 0:
        status = ToolStatus.COMPLETE
    elif success_count == 0:
        status = ToolStatus.FAILED
    else:
        status = ToolStatus.PARTIAL

    # Create next action based on status
    # NOTE: Dev server is auto-started by WebContainer, no need to call shell
    # Instead, we tell Agent to check for build errors
    if status in (ToolStatus.COMPLETE, ToolStatus.PARTIAL):
        next_action = create_get_build_errors_action(
            reason="Dev server auto-reloads via HMR. Check for compilation errors now!"
        )
    else:
        next_action = None  # All failed, no point checking errors

    return SpawnWorkersResult(
        status=status,
        workers_total=total,
        workers_success=success_count,
        workers_failed=failed_count,
        files_created=written_files,
        worker_reports=reports,
        next_action=next_action,
        duration_ms=duration_ms,
        errors=errors or [],
    )
