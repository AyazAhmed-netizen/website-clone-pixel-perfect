"""
WebContainer Tools V2 - Claude Code Style

Simplified, powerful tool system inspired by Claude Code's design:

Core Principles:
1. MINIMAL TOOLS - Only essential tools, shell is the universal tool
2. SYNCHRONOUS BLOCKING - Tools wait for execution results
3. CLEAR FEEDBACK - Tools return actual execution results, not promises

Core Tools:
1. shell - Execute any command (replaces run_command, start_dev_server, etc.)
2. write_file - Create or overwrite files
3. read_file - Read file content
4. edit_file - Search and replace (str_replace style)
5. list_files - List directory contents
6. get_state - Get current WebContainer state

Philosophy:
- shell("npm install") instead of install_dependencies()
- shell("npm run dev &") instead of start_dev_server()
- shell("mkdir -p src/components") instead of create_directory()
- One powerful shell tool > many specialized tools
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field
import re
import uuid
import time
import logging

logger = logging.getLogger(__name__)


# ============================================
# Tool Result Types
# ============================================

@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    result: str
    action: Optional[dict] = None
    # New: Action ID for tracking execution
    action_id: Optional[str] = None
    # New: Whether this action requires confirmation
    requires_confirmation: bool = False


@dataclass
class ActionRequest:
    """
    Request for frontend action execution.

    The backend sends this, frontend executes and POSTs result back.
    """
    id: str
    type: str
    payload: dict
    created_at: float = field(default_factory=time.time)


@dataclass
class ActionResult:
    """
    Result of frontend action execution.

    Frontend POSTs this back after executing an action.
    """
    id: str
    success: bool
    result: str
    error: Optional[str] = None
    completed_at: float = field(default_factory=time.time)


# ============================================
# Action Store (for tracking pending actions)
# ============================================

class ActionStore:
    """
    Store for tracking pending actions and their results.

    This enables synchronous tool behavior:
    1. Tool creates ActionRequest with unique ID
    2. Tool waits for ActionResult with matching ID
    3. Frontend executes and POSTs result
    4. Tool returns actual execution result
    """

    def __init__(self):
        self._pending: Dict[str, ActionRequest] = {}
        self._results: Dict[str, ActionResult] = {}
        self._waiters: Dict[str, Any] = {}  # asyncio.Future objects

    def create_action(self, action_type: str, payload: dict) -> ActionRequest:
        """Create a new action request"""
        action_id = f"action-{uuid.uuid4().hex[:12]}"
        action = ActionRequest(
            id=action_id,
            type=action_type,
            payload=payload
        )
        self._pending[action_id] = action
        logger.info(f"[ActionStore] Created action {action_id}: {action_type}")
        return action

    def set_result(self, action_id: str, result: ActionResult):
        """Set result for an action (called when frontend reports back)"""
        self._results[action_id] = result
        # Remove from pending
        self._pending.pop(action_id, None)
        # Wake up any waiters
        if action_id in self._waiters:
            future = self._waiters.pop(action_id)
            if not future.done():
                future.set_result(result)
        logger.info(f"[ActionStore] Result received for {action_id}: success={result.success}")

    def get_result(self, action_id: str) -> Optional[ActionResult]:
        """Get result for an action (non-blocking)"""
        return self._results.get(action_id)

    def is_pending(self, action_id: str) -> bool:
        """Check if action is still pending"""
        return action_id in self._pending

    async def wait_for_result(self, action_id: str, timeout: float = 30.0) -> Optional[ActionResult]:
        """
        Wait for action result (async, with timeout).

        This is the key to synchronous blocking behavior.
        """
        import asyncio

        # Check if already have result
        if action_id in self._results:
            return self._results[action_id]

        # Create future to wait on
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._waiters[action_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"[ActionStore] Timeout waiting for action {action_id}")
            self._waiters.pop(action_id, None)
            self._pending.pop(action_id, None)
            return None


# Global action store instance
_action_store = ActionStore()

def get_action_store() -> ActionStore:
    """Get the global action store"""
    return _action_store


# ============================================
# Core Tools - Claude Code Style
# ============================================

def shell(command: str, background: bool = False) -> ToolResult:
    """
    Execute a shell command in the WebContainer.

    This is the UNIVERSAL tool for command execution. Use it for:
    - Installing packages: shell("npm install react")
    - Running dev server: shell("npm run dev", background=True)
    - Creating directories: shell("mkdir -p src/components")
    - Listing files: shell("ls -la src/")
    - Any other shell command

    IMPORTANT:
    - Commands are executed in the WebContainer environment
    - Use background=True for long-running commands (dev server, etc.)
    - Output includes both stdout and stderr
    - Exit code is included in the result

    Examples:
        shell("npm install")                    # Install all dependencies
        shell("npm install react router-dom")   # Install specific packages
        shell("npm run dev", background=True)   # Start dev server in background
        shell("mkdir -p src/components")        # Create directory
        shell("ls -la")                         # List files
        shell("cat package.json")               # View file (prefer read_file)
        shell("rm -rf node_modules")            # Remove directory

    Args:
        command: The shell command to execute
        background: If True, run in background (for long-running commands)

    Returns:
        ToolResult with command output and exit status
    """
    # Parse command into program and args
    parts = command.strip().split()
    if not parts:
        return ToolResult(
            success=False,
            result="Error: Empty command"
        )

    program = parts[0]
    args = parts[1:] if len(parts) > 1 else []

    # Create action request
    action = {
        "type": "shell",
        "payload": {
            "command": program,
            "args": args,
            "raw_command": command,
            "background": background
        }
    }

    action_request = _action_store.create_action("shell", action["payload"])

    # For background commands, return immediately
    if background:
        return ToolResult(
            success=True,
            result=f"Started background process: {command}\nUse get_state() to check if server is ready.",
            action=action,
            action_id=action_request.id,
            requires_confirmation=False  # Don't wait for background
        )

    # For foreground commands, we need confirmation
    return ToolResult(
        success=True,
        result=f"Executing: {command}",
        action=action,
        action_id=action_request.id,
        requires_confirmation=True  # Wait for result
    )


def write_file(path: str, content: str) -> ToolResult:
    """
    Write content to a file. Creates the file if it doesn't exist.

    This tool:
    - Creates parent directories automatically
    - Overwrites existing files
    - Triggers Vite HMR for hot reload

    IMPORTANT:
    - You MUST call this tool to write files
    - Do NOT just describe the file content - actually call this tool
    - After writing, check for errors with get_state() or shell("cat file")

    Examples:
        write_file("/src/App.jsx", "import React from 'react';...")
        write_file("/package.json", '{"name": "my-app", ...}')
        write_file("/src/components/Button.jsx", "export function Button()...")

    Args:
        path: File path (e.g., "/src/App.jsx", "package.json")
        content: Complete file content to write

    Returns:
        ToolResult indicating success/failure
    """
    # Normalize path
    normalized_path = path if path.startswith("/") else f"/{path}"

    action = {
        "type": "write_file",
        "payload": {
            "path": normalized_path,
            "content": content
        }
    }

    action_request = _action_store.create_action("write_file", action["payload"])

    return ToolResult(
        success=True,
        result=f"Writing file: {normalized_path} ({len(content)} bytes)",
        action=action,
        action_id=action_request.id,
        requires_confirmation=True
    )


def read_file(path: str, webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Read a file's content from the WebContainer.

    This reads from the current state snapshot. For guaranteed fresh content,
    use shell("cat path/to/file").

    Args:
        path: Path to the file (e.g., "/src/App.jsx")
        webcontainer_state: Current WebContainer state (injected)

    Returns:
        ToolResult with file content or error
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available. Try shell('cat {path}') instead."
        )

    # Normalize path
    normalized_path = path if path.startswith("/") else f"/{path}"
    files = webcontainer_state.get("files", {})

    # Try both path formats
    content = files.get(normalized_path) or files.get(path.lstrip("/"))

    if content is not None:
        # Add line numbers for easier reference
        lines = content.split("\n")
        numbered_lines = [f"{i+1:4}| {line}" for i, line in enumerate(lines)]
        numbered_content = "\n".join(numbered_lines)

        return ToolResult(
            success=True,
            result=f"Content of {normalized_path}:\n```\n{numbered_content}\n```"
        )

    available = list(files.keys())[:15]
    return ToolResult(
        success=False,
        result=f"File not found: {path}\n\nAvailable files:\n" + "\n".join(f"  - {f}" for f in available)
    )


def edit_file(
    path: str,
    old_text: str,
    new_text: str,
    webcontainer_state: Optional[dict] = None,
    replace_all: bool = False,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None
) -> ToolResult:
    """
    Edit a file by replacing specific text (str_replace style).

    This is more precise than write_file for small changes.
    Supports multiple editing modes:

    MODE 1: Text replacement (default)
    - old_text must match (whitespace-normalized)
    - Finds and replaces the text

    MODE 2: Line-based editing (if line_start provided)
    - Replaces content from line_start to line_end
    - old_text is ignored in this mode
    - new_text becomes the new content for those lines

    EXAMPLES:
        # Replace text (auto-handles minor whitespace differences)
        edit_file("/src/App.jsx",
                  "function OldName()",
                  "function NewName()")

        # Replace all occurrences
        edit_file("/src/App.jsx",
                  "oldVar",
                  "newVar",
                  replace_all=True)

        # Replace specific lines (lines 10-15)
        edit_file("/src/App.jsx",
                  "",
                  "// New content here",
                  line_start=10,
                  line_end=15)

    Args:
        path: File path
        old_text: Text to find (or empty if using line_start)
        new_text: Replacement text
        webcontainer_state: Current state for validation
        replace_all: If True, replace all occurrences (default: False)
        line_start: Start line number for line-based edit (1-indexed)
        line_end: End line number (inclusive, defaults to line_start)

    Returns:
        ToolResult indicating success/failure
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    normalized_path = path if path.startswith("/") else f"/{path}"
    files = webcontainer_state.get("files", {})

    content = files.get(normalized_path) or files.get(path.lstrip("/"))

    if content is None:
        # File not found - list available files
        available = list(files.keys())[:20]
        return ToolResult(
            success=False,
            result=f"File not found: {path}\n\n"
                   f"Available files:\n" + "\n".join(f"  - {f}" for f in available)
        )

    lines = content.split("\n")

    # MODE 2: Line-based editing
    if line_start is not None:
        if line_end is None:
            line_end = line_start

        # Validate line numbers
        if line_start < 1 or line_end < 1:
            return ToolResult(
                success=False,
                result=f"Line numbers must be >= 1 (got start={line_start}, end={line_end})"
            )

        if line_start > len(lines):
            return ToolResult(
                success=False,
                result=f"line_start ({line_start}) exceeds file length ({len(lines)} lines)"
            )

        if line_end > len(lines):
            line_end = len(lines)  # Clamp to file end

        if line_start > line_end:
            return ToolResult(
                success=False,
                result=f"line_start ({line_start}) > line_end ({line_end})"
            )

        # Show what will be replaced
        old_lines = lines[line_start - 1:line_end]
        old_content_preview = "\n".join(f"{line_start + i:4}| {line}" for i, line in enumerate(old_lines))

        # Build new content
        new_lines = new_text.split("\n") if new_text else []
        new_content = "\n".join(
            lines[:line_start - 1] +
            new_lines +
            lines[line_end:]
        )

        action = {
            "type": "write_file",  # Line-based edit is effectively a rewrite
            "payload": {
                "path": normalized_path,
                "content": new_content
            }
        }

        action_request = _action_store.create_action("edit_file_lines", action["payload"])

        return ToolResult(
            success=True,
            result=f"Replacing lines {line_start}-{line_end} in {path}:\n"
                   f"OLD:\n```\n{old_content_preview}\n```\n"
                   f"NEW:\n```\n{new_text[:200]}{'...' if len(new_text) > 200 else ''}\n```",
            action=action,
            action_id=action_request.id,
            requires_confirmation=True
        )

    # MODE 1: Text replacement
    if not old_text:
        return ToolResult(
            success=False,
            result="old_text is required for text replacement mode.\n"
                   "Use line_start/line_end for line-based editing."
        )

    # Try exact match first
    if old_text in content:
        count = content.count(old_text)

        if count > 1 and not replace_all:
            # Find line numbers of all matches
            match_locations = _find_text_locations(content, old_text)
            locations_str = "\n".join(
                f"  Line {loc['line']}: {loc['preview'][:60]}..."
                for loc in match_locations[:5]
            )

            return ToolResult(
                success=False,
                result=f"Found {count} occurrences in {path}.\n\n"
                       f"Matches at:\n{locations_str}\n\n"
                       f"Options:\n"
                       f"1. Add more context to old_text to make it unique\n"
                       f"2. Use replace_all=True to replace all occurrences\n"
                       f"3. Use line_start/line_end to target specific lines"
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_text, new_text)
            msg = f"Replacing {count} occurrences in {path}"
        else:
            new_content = content.replace(old_text, new_text, 1)
            msg = f"Replacing 1 occurrence in {path}"

        action = {
            "type": "write_file",
            "payload": {
                "path": normalized_path,
                "content": new_content
            }
        }

        action_request = _action_store.create_action("edit_file", action["payload"])

        return ToolResult(
            success=True,
            result=msg,
            action=action,
            action_id=action_request.id,
            requires_confirmation=True
        )

    # Exact match failed - try normalized matching
    normalized_old = _normalize_whitespace(old_text)
    normalized_content = _normalize_whitespace(content)

    if normalized_old in normalized_content:
        # Found with normalized whitespace - help user fix it
        suggestion = _find_actual_text(content, old_text)

        return ToolResult(
            success=False,
            result=f"Whitespace mismatch in {path}.\n\n"
                   f"Your old_text (normalized) was found, but whitespace differs.\n\n"
                   f"Try using this exact text:\n```\n{suggestion}\n```"
        )

    # Text not found at all - show helpful context
    similar_lines = _find_similar_lines(lines, old_text)

    if similar_lines:
        similar_str = "\n".join(
            f"  {loc['line']:4}| {loc['text'][:80]}"
            for loc in similar_lines[:5]
        )
        return ToolResult(
            success=False,
            result=f"Text not found in {path}.\n\n"
                   f"Similar lines found:\n{similar_str}\n\n"
                   f"Tips:\n"
                   f"- Check exact whitespace/indentation\n"
                   f"- Use read_file('{path}') to see full content\n"
                   f"- Use line_start/line_end to edit by line number"
        )

    # No similar lines found - show file preview
    preview = "\n".join(f"{i+1:4}| {line}" for i, line in enumerate(lines[:40]))

    return ToolResult(
        success=False,
        result=f"Text not found in {path}.\n\n"
               f"The old_text does not appear in this file.\n\n"
               f"File preview ({len(lines)} lines total):\n```\n{preview}\n```\n"
               f"{'...(truncated)' if len(lines) > 40 else ''}"
    )


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace for comparison"""
    # Replace multiple spaces/tabs with single space
    text = re.sub(r'[ \t]+', ' ', text)
    # Remove trailing whitespace from lines
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    return text.strip()


def _find_text_locations(content: str, text: str) -> List[dict]:
    """Find all locations of text in content"""
    lines = content.split("\n")
    locations = []

    # Simple approach: find by line
    first_line_of_text = text.split("\n")[0] if text else ""

    for i, line in enumerate(lines, 1):
        if first_line_of_text in line or text in line:
            locations.append({
                "line": i,
                "preview": line.strip()
            })

    return locations


def _find_actual_text(content: str, target: str) -> str:
    """Find the actual text in content that matches target (with different whitespace)"""
    target_lines = target.split("\n")
    content_lines = content.split("\n")

    # Try to find starting line
    first_target = target_lines[0].strip()

    for i, line in enumerate(content_lines):
        if first_target in line.strip():
            # Found potential match - extract enough lines
            num_lines = len(target_lines)
            actual_lines = content_lines[i:i + num_lines]
            return "\n".join(actual_lines)

    return target  # Fallback


def _find_similar_lines(lines: List[str], target: str) -> List[dict]:
    """Find lines that partially match target"""
    similar = []
    target_lower = target.lower().strip()

    # Get keywords from target (words longer than 3 chars)
    keywords = [w for w in re.split(r'\W+', target_lower) if len(w) > 3]

    for i, line in enumerate(lines, 1):
        line_lower = line.lower()
        # Check if any keyword appears
        matches = sum(1 for kw in keywords if kw in line_lower)
        if matches >= 1 and len(keywords) > 0:
            similar.append({
                "line": i,
                "text": line,
                "score": matches / len(keywords)
            })

    # Sort by score descending
    similar.sort(key=lambda x: x["score"], reverse=True)
    return similar[:10]


def list_files(path: str = "/", webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    List files and directories at a path.

    Similar to 'ls -la' but reads from state.
    For real-time listing, use shell("ls -la path").

    Args:
        path: Directory path (default "/")
        webcontainer_state: Current state

    Returns:
        ToolResult with file listing
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available. Try shell('ls -la') instead."
        )

    files = webcontainer_state.get("files", {})

    if not files:
        return ToolResult(
            success=True,
            result="Project is empty. No files yet."
        )

    # Normalize base path
    base_path = path.rstrip("/")
    if not base_path:
        base_path = ""

    # Find entries at this level
    entries: Dict[str, str] = {}  # name -> type (file/dir)

    for file_path in files.keys():
        norm_path = file_path if file_path.startswith("/") else f"/{file_path}"

        # Check if under requested path
        if base_path:
            if not norm_path.startswith(base_path + "/"):
                continue
            rel_path = norm_path[len(base_path):].lstrip("/")
        else:
            rel_path = norm_path.lstrip("/")

        if not rel_path:
            continue

        # Get first component
        parts = rel_path.split("/")
        first = parts[0]

        if len(parts) == 1:
            entries[first] = "file"
        else:
            entries[first] = "dir"

    if not entries:
        return ToolResult(
            success=True,
            result=f"Directory {path} is empty or does not exist."
        )

    # Format output
    lines = [f"Contents of {path}:"]
    for name in sorted(entries.keys()):
        entry_type = entries[name]
        icon = "d " if entry_type == "dir" else "- "
        lines.append(f"  {icon}{name}{'/' if entry_type == 'dir' else ''}")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


def get_state(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Get current WebContainer state summary.

    Use this to:
    - Check if dev server is running (preview_url present)
    - See what files exist
    - Check terminal status
    - View recent errors

    This is the DIAGNOSTIC tool. Call it to understand what's happening.

    Args:
        webcontainer_state: Current state

    Returns:
        ToolResult with state summary
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    lines = ["# WebContainer State\n"]

    # Status
    status = webcontainer_state.get("status", "unknown")
    error = webcontainer_state.get("error")
    lines.append(f"## Status: {status}")
    if error:
        lines.append(f"**Error**: {error}")

    # Preview/Server
    preview_url = webcontainer_state.get("previewUrl") or webcontainer_state.get("preview_url")
    preview = webcontainer_state.get("preview", {})

    lines.append("\n## Dev Server")
    if preview_url:
        lines.append(f"**Running**: {preview_url}")
        if preview.get("hasError") or preview.get("has_error"):
            lines.append(f"**Preview Error**: {preview.get('errorMessage') or preview.get('error_message', 'Unknown')}")
    else:
        lines.append("**Not running** - Use shell('npm run dev', background=True) to start")

    # Files
    files = webcontainer_state.get("files", {})
    lines.append(f"\n## Files ({len(files)} total)")

    # Show key files
    key_files = ["package.json", "/package.json", "vite.config.js", "/vite.config.js"]
    for kf in key_files:
        if kf in files or kf.lstrip("/") in files:
            lines.append(f"  - {kf.lstrip('/')}")
            break

    # Show src files
    src_files = [f for f in files.keys() if "/src/" in f or f.startswith("src/")]
    if src_files:
        lines.append("  src/:")
        for f in sorted(src_files)[:10]:
            lines.append(f"    - {f.split('src/')[-1]}")
        if len(src_files) > 10:
            lines.append(f"    ... and {len(src_files) - 10} more")

    # Terminals
    terminals = webcontainer_state.get("terminals", [])
    lines.append(f"\n## Terminals ({len(terminals)})")
    for t in terminals:
        status_icon = "running" if t.get("isRunning") or t.get("is_running") else "idle"
        cmd = t.get("command", "")
        lines.append(f"  - [{t.get('id', 'unknown')}] {status_icon}: {cmd}")

        # Show recent output for running terminals
        history = t.get("history", [])
        if history and (t.get("isRunning") or t.get("is_running")):
            recent = history[-3:]
            for entry in recent:
                data = entry.get("data", "") if isinstance(entry, dict) else str(entry)
                data = data.strip()[:100]
                if data:
                    lines.append(f"      > {data}")

    # Console errors
    console_messages = preview.get("consoleMessages") or preview.get("console_messages", [])
    errors = [m for m in console_messages if m.get("type") == "error"]

    if errors:
        lines.append(f"\n## Console Errors ({len(errors)})")
        for err in errors[-3:]:
            args = err.get("args", [])
            msg = " ".join(str(a) for a in args)[:150]
            lines.append(f"  - {msg}")

    # Action results (from previous commands)
    action_results = webcontainer_state.get("action_results", [])
    if action_results:
        failed = [a for a in action_results if not a.get("success", True)]
        if failed:
            lines.append(f"\n## Previous Action Failures")
            for f in failed:
                lines.append(f"  - {f.get('type', 'unknown')}: {f.get('error', 'Failed')}")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


def delete_file(path: str) -> ToolResult:
    """
    Delete a file from the WebContainer.

    Args:
        path: File path to delete

    Returns:
        ToolResult
    """
    normalized_path = path if path.startswith("/") else f"/{path}"

    action = {
        "type": "delete_file",
        "payload": {
            "path": normalized_path
        }
    }

    action_request = _action_store.create_action("delete_file", action["payload"])

    return ToolResult(
        success=True,
        result=f"Deleting: {normalized_path}",
        action=action,
        action_id=action_request.id,
        requires_confirmation=True
    )


# ============================================
# Preview Inspection Tools
# ============================================

def get_preview_dom(selector: str = "body", depth: int = 5) -> ToolResult:
    """
    Get DOM structure from the preview iframe.

    This tool allows you to INSPECT what's actually rendered in the preview.
    Use this to understand the page structure and identify issues.

    Returns:
    - Element tree with tag names, classes, IDs
    - Text content of each element
    - Element dimensions and positions
    - Visibility status

    CRITICAL: Use this to verify your changes rendered correctly!
    This is how you "see" the preview without a screenshot.

    Examples:
        get_preview_dom()                  # Get full body DOM
        get_preview_dom("#root")           # Get React root only
        get_preview_dom(".header", depth=3) # Get header with limited depth

    Args:
        selector: CSS selector for root element (default: "body")
        depth: Maximum depth to traverse (default: 5)

    Returns:
        ToolResult with DOM structure and visual summary
    """
    action = {
        "type": "get_preview_dom",
        "payload": {
            "selector": selector,
            "depth": depth
        }
    }

    action_request = _action_store.create_action("get_preview_dom", action["payload"])

    return ToolResult(
        success=True,
        result=f"Requesting DOM snapshot (selector: {selector}, depth: {depth})",
        action=action,
        action_id=action_request.id,
        requires_confirmation=True
    )


def take_screenshot(selector: Optional[str] = None) -> ToolResult:
    """
    Take a screenshot of the preview iframe.

    This captures what the user actually sees in the preview.
    Use this to verify visual appearance, not just structure.

    If screenshot capture fails (due to cross-origin restrictions),
    a visual summary is returned instead containing:
    - Viewport and body dimensions
    - Number of visible elements
    - Text content preview
    - Background color

    Examples:
        take_screenshot()           # Screenshot of full page
        take_screenshot(".hero")    # Screenshot of specific element

    Args:
        selector: CSS selector for element to capture (default: full page)

    Returns:
        ToolResult with base64 image data or visual summary
    """
    action = {
        "type": "take_screenshot",
        "payload": {
            "selector": selector,
            "full_page": selector is None
        }
    }

    action_request = _action_store.create_action("take_screenshot", action["payload"])

    return ToolResult(
        success=True,
        result=f"Taking screenshot{' of ' + selector if selector else ''}...",
        action=action,
        action_id=action_request.id,
        requires_confirmation=True
    )


def get_visual_summary() -> ToolResult:
    """
    Get a quick visual summary of the preview page.

    This is a LIGHTWEIGHT alternative to DOM snapshot or screenshot.
    Use this for quick checks to see if the page has content.

    Returns:
    - Viewport dimensions
    - Body dimensions (including scroll height)
    - Number of visible elements
    - Whether page has meaningful content (hasContent)
    - Text content preview
    - Page title and URL

    Use cases:
    - Quick check if page is blank vs has content
    - Verify page dimensions
    - Get text content without full DOM tree
    - Faster than get_preview_dom() for simple checks

    Returns:
        ToolResult with visual summary JSON
    """
    action = {
        "type": "get_visual_summary",
        "payload": {}
    }

    action_request = _action_store.create_action("get_visual_summary", action["payload"])

    return ToolResult(
        success=True,
        result="Getting visual summary...",
        action=action,
        action_id=action_request.id,
        requires_confirmation=True
    )


def get_build_errors() -> ToolResult:
    """
    Get build/compilation errors from the preview iframe.

    CRITICAL: Use this to detect and fix code errors!
    This tool actively checks for:
    - Vite compilation errors (syntax errors, import errors)
    - React error boundaries
    - Runtime errors displayed in error overlays

    Returns:
    - hasErrors: true/false - are there build errors?
    - errorCount: number of errors detected
    - errors: array of error objects with:
      - type: error source (vite-overlay, react-error-boundary, console-error)
      - message: error message
      - file: affected file path (if available)
      - frame: code frame showing error location (if available)
      - stack: stack trace (if available)

    Use cases:
    - Check if your code changes caused build errors
    - Get detailed error messages to fix syntax issues
    - Verify code compiles successfully after edits

    Example response when errors exist:
    {
      "hasErrors": true,
      "errorCount": 1,
      "errors": [{
        "type": "vite-overlay",
        "message": "Unexpected token, expected \"}\"",
        "file": "/src/components/Header.jsx:42:15",
        "frame": "  40 |   return (\\n  41 |     <div>\\n> 42 |       {items.map(..."
      }]
    }

    Returns:
        ToolResult with build errors information
    """
    action = {
        "type": "get_build_errors",
        "payload": {}
    }

    action_request = _action_store.create_action("get_build_errors", action["payload"])

    return ToolResult(
        success=True,
        result="Checking for build errors...",
        action=action,
        action_id=action_request.id,
        requires_confirmation=True
    )


# ============================================
# Tool Registry (Claude Code Style - Minimal)
# ============================================

# State query tools (read from state, no frontend action)
STATE_TOOLS = {
    "read_file": read_file,
    "list_files": list_files,
    "get_state": get_state,
}

# Action tools (require frontend execution)
ACTION_TOOLS = {
    "shell": shell,
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
}

# Preview inspection tools (require frontend execution)
PREVIEW_TOOLS = {
    "get_preview_dom": get_preview_dom,
    "take_screenshot": take_screenshot,
    "get_visual_summary": get_visual_summary,
    "get_build_errors": get_build_errors,
}

# All tools
ALL_TOOLS = {**STATE_TOOLS, **ACTION_TOOLS, **PREVIEW_TOOLS}


def get_tool_definitions_v2() -> List[dict]:
    """
    Get tool definitions in Claude API format.

    Claude Code style - minimal, powerful tools.
    """
    return [
        # ============================================
        # UNIVERSAL COMMAND TOOL
        # ============================================
        {
            "name": "shell",
            "description": """Execute a shell command in WebContainer.

This is the UNIVERSAL tool for command execution. Use it instead of specialized tools:

COMMON COMMANDS:
- Install packages:     shell("npm install react")
- Start dev server:     shell("npm run dev", background=True)
- Create directories:   shell("mkdir -p src/components")
- List files:           shell("ls -la src/")
- View file:            shell("cat package.json")
- Remove files:         shell("rm -rf node_modules")

IMPORTANT:
- Use background=True for long-running commands (dev server)
- Commands run in WebContainer (Node.js environment)
- Output includes stdout/stderr

When to use:
- ANY shell command you would run in a terminal
- Installing dependencies
- Running scripts
- File system operations
- Starting/stopping servers""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute (e.g., 'npm install', 'ls -la')"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Run in background for long-running commands (default: false)"
                    }
                },
                "required": ["command"]
            }
        },

        # ============================================
        # FILE OPERATIONS
        # ============================================
        {
            "name": "write_file",
            "description": """Write content to a file. Creates file and parent directories.

CRITICAL: You MUST call this tool to write files.
Do NOT just describe the content - ACTUALLY CALL THIS TOOL.

Examples:
  write_file("/src/App.jsx", "import React...")
  write_file("/package.json", '{"name": "app"...}')

After writing:
  - Vite will hot reload automatically
  - Check for errors with get_state()""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (e.g., '/src/App.jsx')"
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file content"
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "read_file",
            "description": """Read a file's content with line numbers.

Returns file content with line numbers for easy reference.
For guaranteed fresh content, use shell("cat path").""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "edit_file",
            "description": """Edit a file by replacing text or editing specific lines.

TWO MODES:

MODE 1 - Text replacement (default):
  edit_file("/src/App.jsx",
            "function OldName()",
            "function NewName()")

  - Finds and replaces text
  - Use replace_all=True for multiple occurrences
  - Smart error messages when text not found

MODE 2 - Line-based editing:
  edit_file("/src/App.jsx", "", "// new content",
            line_start=10, line_end=15)

  - Replaces lines 10-15 with new content
  - old_text is ignored in this mode

FEATURES:
- Whitespace mismatch detection (suggests correct text)
- Similar line finding (helps locate target)
- Multiple occurrence handling (shows all locations)
- Line number support for precise edits""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Text to find (empty if using line_start)"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text"
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default: false)"
                    },
                    "line_start": {
                        "type": "integer",
                        "description": "Start line number for line-based edit (1-indexed)"
                    },
                    "line_end": {
                        "type": "integer",
                        "description": "End line number (inclusive, defaults to line_start)"
                    }
                },
                "required": ["path", "new_text"]
            }
        },
        {
            "name": "delete_file",
            "description": "Delete a file. For directories, use shell('rm -rf path').",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to delete"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "list_files",
            "description": """List files and directories at a path.

Like 'ls' but from state. For real-time: shell("ls -la")""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default '/')"
                    }
                },
                "required": []
            }
        },

        # ============================================
        # DIAGNOSTIC
        # ============================================
        {
            "name": "get_state",
            "description": """Get current WebContainer state summary.

Use this to:
- Check if dev server is running
- See what files exist
- Check terminal status
- View recent errors

CALL THIS after making changes to verify success.""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },

        # ============================================
        # PREVIEW INSPECTION TOOLS
        # ============================================
        {
            "name": "get_preview_dom",
            "description": """Get DOM structure from the preview iframe.

CRITICAL: Use this to "SEE" what's rendered in the preview!
This is how you verify your changes worked correctly.

Returns for each element:
- Tag name, classes, and IDs
- Text content
- Dimensions and position (x, y, width, height)
- Visibility status

Example output:
<body> [800x600 @0,0]
  <div id="root">
    <header class="nav"> "Navigation" [800x60 @0,0]
    <main> [800x540 @0,60]
      <h1> "Welcome" [200x40 @100,80]

Use cases:
- Verify component rendered correctly
- Check if page is blank (few/no elements)
- Find element positions for layout debugging
- Identify missing content""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector (default: 'body')"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Max depth to traverse (default: 5)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "take_screenshot",
            "description": """Take a screenshot of the preview.

Captures visual appearance as base64 PNG image.
Use when you need to verify visual styling, colors, layout.

If screenshot fails (cross-origin), returns visual summary instead:
- Viewport dimensions
- Number of visible elements
- Text content preview
- Background color

Note: get_preview_dom() is often more useful for debugging.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for element (default: full page)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_visual_summary",
            "description": """Quick check if preview has content.

LIGHTWEIGHT alternative to DOM snapshot or screenshot.
Use for fast checks before deeper inspection.

Returns:
- hasContent: true/false - does page have meaningful content?
- visibleElementCount: number of visible elements
- textPreview: sample of visible text
- viewport/body dimensions

Example:
{
  "hasContent": true,
  "visibleElementCount": 42,
  "textPreview": "Welcome to My App..."
}

Use when:
- Quick check if page is blank
- Verify content exists before detailed inspection
- Faster than get_preview_dom() for simple checks""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_build_errors",
            "description": """Get build/compilation errors from the preview.

CRITICAL: Use this to detect and fix code errors!

Actively checks for:
- Vite compilation errors (syntax, imports, JSX)
- React error boundaries
- Runtime errors in error overlays
- Console build errors

Returns:
{
  "hasErrors": true/false,
  "errorCount": number,
  "errors": [{
    "type": "vite-overlay",
    "message": "Unexpected token...",
    "file": "/src/App.jsx:42:15",
    "frame": "code context showing error",
    "stack": "optional stack trace"
  }]
}

Use cases:
- Check if your code changes caused build errors
- Get detailed error messages with file/line info
- Verify code compiles after edits
- Faster than screenshot for error detection

IMPORTANT: Call this after write_file or edit_file to verify
your changes compiled successfully.""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]


# ============================================
# Legacy Compatibility Wrappers
# ============================================

def start_dev_server() -> ToolResult:
    """Legacy wrapper - use shell("npm run dev", background=True) instead"""
    return shell("npm run dev", background=True)


def install_dependencies(packages: List[str] = None, dev: bool = False) -> ToolResult:
    """Legacy wrapper - use shell("npm install ...") instead"""
    if packages:
        pkg_str = " ".join(packages)
        if dev:
            return shell(f"npm install --save-dev {pkg_str}")
        return shell(f"npm install {pkg_str}")
    return shell("npm install")


def run_command(command: str, args: List[str] = None) -> ToolResult:
    """Legacy wrapper - use shell() instead"""
    if args:
        full_cmd = f"{command} {' '.join(args)}"
    else:
        full_cmd = command
    return shell(full_cmd)


def create_directory(path: str) -> ToolResult:
    """Legacy wrapper - use shell("mkdir -p path") instead"""
    normalized = path if path.startswith("/") else f"/{path}"
    return shell(f"mkdir -p {normalized}")


# Export legacy wrappers for backward compatibility
LEGACY_TOOLS = {
    "start_dev_server": start_dev_server,
    "install_dependencies": install_dependencies,
    "run_command": run_command,
    "create_directory": create_directory,
}
