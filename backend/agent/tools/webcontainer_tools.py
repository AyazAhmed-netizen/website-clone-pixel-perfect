"""
WebContainer Tools

Complete toolset for Agent to interact with the WebContainer environment.

Tool Categories:
1. State Query Tools - Read from current state, no frontend action needed
2. File Operation Tools - Read/write/delete/edit files
3. Terminal Tools - Execute commands, manage multiple terminals
4. Preview Tools - Screenshots, console messages, DOM inspection

Enhanced Features:
- Multi-terminal support with session management
- Precise file editing (search & replace)
- Preview screenshot and console capture
- Cross-file search capabilities
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
import re
import fnmatch


# ============================================
# Constants
# ============================================

MAX_TERMINALS = 5  # Maximum number of concurrent terminals
MAX_CONSOLE_MESSAGES = 100  # Maximum console messages to return
MAX_SEARCH_RESULTS = 50  # Maximum search results to return
MAX_HISTORY_LINES = 500  # Maximum terminal history lines


# ============================================
# Tool Result Types
# ============================================

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


# ============================================
# State Query Tools (No frontend action needed)
# ============================================

def read_file(path: str, webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Read a file's content from the WebContainer.

    Args:
        path: Path to the file (e.g., "/src/App.jsx")
        webcontainer_state: Current WebContainer state (injected by tool_node)

    Returns:
        ToolResult with file content or error
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    # Normalize path
    normalized_path = path if path.startswith("/") else f"/{path}"

    files = webcontainer_state.get("files", {})

    if normalized_path in files:
        content = files[normalized_path]
        return ToolResult(
            success=True,
            result=f"Content of {normalized_path}:\n```\n{content}\n```"
        )

    # Try without leading slash
    alt_path = path.lstrip("/")
    if alt_path in files:
        content = files[alt_path]
        return ToolResult(
            success=True,
            result=f"Content of {alt_path}:\n```\n{content}\n```"
        )

    return ToolResult(
        success=False,
        result=f"File not found: {path}. Available files: {list(files.keys())[:10]}"
    )


def list_files(path: str = "/", webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    List files and directories at the given path.

    Args:
        path: Directory path (default "/")
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with list of files/directories
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    files = webcontainer_state.get("files", {})

    # Normalize path
    base_path = path.rstrip("/")
    if not base_path:
        base_path = ""

    # Find all files/dirs at this level
    entries: Dict[str, str] = {}  # name -> type

    for file_path in files.keys():
        # Normalize file path
        norm_file_path = file_path if file_path.startswith("/") else f"/{file_path}"

        # Check if file is under the requested path
        if base_path and not norm_file_path.startswith(base_path + "/"):
            if norm_file_path != base_path:
                continue

        # Get relative path
        if base_path:
            rel_path = norm_file_path[len(base_path):].lstrip("/")
        else:
            rel_path = norm_file_path.lstrip("/")

        if not rel_path:
            continue

        # Get first component
        parts = rel_path.split("/")
        first = parts[0]

        if len(parts) == 1:
            entries[first] = "file"
        else:
            entries[first] = "directory"

    if not entries:
        return ToolResult(
            success=True,
            result=f"Directory {path} is empty or does not exist."
        )

    # Format output
    output_lines = [f"Contents of {path}:"]
    for name, entry_type in sorted(entries.items()):
        icon = "📁" if entry_type == "directory" else "📄"
        output_lines.append(f"  {icon} {name}")

    return ToolResult(
        success=True,
        result="\n".join(output_lines)
    )


def file_exists(path: str, webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Check if a file or directory exists.

    Args:
        path: Path to check
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult indicating existence
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    files = webcontainer_state.get("files", {})
    normalized_path = path if path.startswith("/") else f"/{path}"
    alt_path = path.lstrip("/")

    if normalized_path in files or alt_path in files:
        return ToolResult(
            success=True,
            result=f"File exists: {path}"
        )

    # Check if it's a directory (any file starts with this path)
    for file_path in files.keys():
        norm_file = file_path if file_path.startswith("/") else f"/{file_path}"
        if norm_file.startswith(normalized_path + "/"):
            return ToolResult(
                success=True,
                result=f"Directory exists: {path}"
            )

    return ToolResult(
        success=True,
        result=f"Path does not exist: {path}"
    )


def get_terminal_output(
    lines: int = 50,
    terminal_id: Optional[str] = None,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Get recent terminal output.

    Args:
        lines: Number of lines to retrieve (default 50)
        terminal_id: Specific terminal ID (default: active terminal)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with terminal output
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    terminals = webcontainer_state.get("terminals", [])

    if not terminals:
        return ToolResult(
            success=True,
            result="No terminal sessions available. Run a command to create one."
        )

    # Find the target terminal
    target = None
    if terminal_id:
        for t in terminals:
            if t.get("id") == terminal_id:
                target = t
                break
        if not target:
            return ToolResult(
                success=False,
                result=f"Terminal {terminal_id} not found"
            )
    else:
        target = terminals[0]  # Use first/active terminal

    output = target.get("last_output", [])
    is_running = target.get("is_running", False)

    if not output:
        status = "running" if is_running else "idle"
        return ToolResult(
            success=True,
            result=f"Terminal {target.get('id', 'default')} ({status}): No output yet."
        )

    recent = output[-lines:] if len(output) > lines else output
    status = "🟢 Running" if is_running else "⚫ Idle"

    return ToolResult(
        success=True,
        result=f"Terminal output ({status}):\n" + "\n".join(recent)
    )


def get_preview_status(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Get the current preview/dev server status.

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with preview status
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    status = webcontainer_state.get("status", "unknown")
    preview_url = webcontainer_state.get("preview_url")
    preview = webcontainer_state.get("preview", {})
    error = webcontainer_state.get("error")

    lines = [f"## Preview Status\n"]
    lines.append(f"**WebContainer**: {status}")

    if error:
        lines.append(f"❌ **System Error**: {error}")
    elif preview_url:
        # Dev server IS running!
        lines.append(f"✅ **Dev Server**: Running")
        lines.append(f"🌐 **URL**: {preview_url}")

        # Check if preview iframe has loaded
        is_loading = preview.get("is_loading", False)
        has_error = preview.get("has_error", False)
        error_overlay = preview.get("error_overlay")

        if has_error:
            lines.append(f"❌ **Preview**: Error (see get_preview_errors() for details)")
        elif is_loading:
            lines.append(f"🔄 **Preview**: Loading...")
        elif error_overlay:
            lines.append(f"❌ **Build Error**: Vite error overlay present (call get_preview_error_overlay())")
        else:
            lines.append(f"✅ **Preview**: Rendering normally")

        lines.append(f"\n💡 **Recommendation**: Since dev server is running, use diagnose_preview_state() for detailed analysis instead of repeatedly checking status.")
    else:
        # Dev server NOT running
        lines.append(f"⏳ **Dev Server**: Not started")
        lines.append(f"\n💡 **Next Step**: Call start_dev_server() to start it (or it may auto-start if files are detected).")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


def get_project_structure(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Get the complete project file structure as a tree.

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with project tree
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    files = webcontainer_state.get("files", {})

    if not files:
        return ToolResult(
            success=True,
            result="Project is empty. No files have been created yet."
        )

    # Build tree structure
    def build_tree(paths: List[str]) -> Dict:
        tree: Dict[str, Any] = {}
        for path in paths:
            parts = path.lstrip("/").split("/")
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
        return tree

    def format_tree(tree: Dict, prefix: str = "") -> List[str]:
        lines = []
        items = sorted(tree.items())
        for i, (name, subtree) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + name)
            if subtree:
                extension = "    " if is_last else "│   "
                lines.extend(format_tree(subtree, prefix + extension))
        return lines

    tree = build_tree(list(files.keys()))
    tree_lines = format_tree(tree)

    return ToolResult(
        success=True,
        result="Project Structure:\n" + "\n".join(tree_lines)
    )


# ============================================
# File Operation Tools (Require frontend action)
# ============================================

def write_file(path: str, content: str) -> ToolResult:
    """
    Write content to a file. Creates parent directories if needed.

    Args:
        path: File path (e.g., "/src/components/Button.jsx")
        content: File content to write

    Returns:
        ToolResult with action for frontend
    """
    normalized_path = path if path.startswith("/") else f"/{path}"

    action = {
        "type": "write_file",
        "payload": {
            "path": normalized_path,
            "content": content
        }
    }

    return ToolResult(
        success=True,
        result=f"Writing file: {normalized_path} ({len(content)} bytes)",
        action=action
    )


def delete_file(path: str) -> ToolResult:
    """
    Delete a file from the WebContainer.

    Args:
        path: File path to delete

    Returns:
        ToolResult with action for frontend
    """
    normalized_path = path if path.startswith("/") else f"/{path}"

    action = {
        "type": "delete_file",
        "payload": {
            "path": normalized_path
        }
    }

    return ToolResult(
        success=True,
        result=f"Deleting file: {normalized_path}",
        action=action
    )


def create_directory(path: str) -> ToolResult:
    """
    Create a directory (and parent directories if needed).

    Args:
        path: Directory path to create

    Returns:
        ToolResult with action for frontend
    """
    normalized_path = path if path.startswith("/") else f"/{path}"

    action = {
        "type": "create_directory",
        "payload": {
            "path": normalized_path
        }
    }

    return ToolResult(
        success=True,
        result=f"Creating directory: {normalized_path}",
        action=action
    )


# ============================================
# Terminal Tools (Require frontend action)
# ============================================

def run_command(command: str, args: Optional[List[str]] = None) -> ToolResult:
    """
    Run a shell command in the WebContainer terminal.

    Args:
        command: Command to run (e.g., "npm", "node", "ls")
        args: Command arguments (e.g., ["install", "react"])

    Returns:
        ToolResult with action for frontend
    """
    args = args or []

    action = {
        "type": "run_command",
        "payload": {
            "command": command,
            "args": args
        }
    }

    cmd_str = f"{command} {' '.join(args)}".strip()
    return ToolResult(
        success=True,
        result=f"Executing: {cmd_str}",
        action=action
    )


def install_dependencies(packages: List[str], dev: bool = False) -> ToolResult:
    """
    Install npm packages.

    Args:
        packages: List of packages to install (empty for install all)
        dev: Install as dev dependencies

    Returns:
        ToolResult with action for frontend
    """
    action = {
        "type": "install_dependencies",
        "payload": {
            "packages": packages,
            "dev": dev
        }
    }

    if packages:
        pkg_str = ", ".join(packages)
        dev_str = " (dev)" if dev else ""
        result = f"Installing packages{dev_str}: {pkg_str}"
    else:
        result = "Installing all dependencies from package.json"

    return ToolResult(
        success=True,
        result=result,
        action=action
    )


def start_dev_server() -> ToolResult:
    """
    Start the development server (npm run dev).

    Returns:
        ToolResult with action for frontend
    """
    action = {
        "type": "start_dev_server",
        "payload": {}
    }

    return ToolResult(
        success=True,
        result="Starting development server... The preview will be available once the server is ready.",
        action=action
    )


def stop_server() -> ToolResult:
    """
    Stop the running development server.

    Returns:
        ToolResult with action for frontend
    """
    action = {
        "type": "stop_process",
        "payload": {}
    }

    return ToolResult(
        success=True,
        result="Stopping the server...",
        action=action
    )


# ============================================
# Enhanced Terminal Tools
# ============================================

def create_terminal(name: Optional[str] = None, webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Create a new terminal session.

    Args:
        name: Optional name for the terminal (auto-generated if not provided)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action to create terminal
    """
    if webcontainer_state:
        terminals = webcontainer_state.get("terminals", [])
        if len(terminals) >= MAX_TERMINALS:
            return ToolResult(
                success=False,
                result=f"Maximum number of terminals ({MAX_TERMINALS}) reached. Close an existing terminal first."
            )

        # Check for duplicate name
        if name:
            existing_names = [t.get("name", "") for t in terminals]
            if name in existing_names:
                name = f"{name}-{len(terminals) + 1}"

    action = {
        "type": "create_terminal",
        "payload": {
            "name": name or f"Terminal {len(webcontainer_state.get('terminals', [])) + 1 if webcontainer_state else 1}"
        }
    }

    return ToolResult(
        success=True,
        result=f"Creating new terminal: {action['payload']['name']}",
        action=action
    )


def list_terminals(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    List all terminal sessions with their status.

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with terminal list
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    terminals = webcontainer_state.get("terminals", [])

    if not terminals:
        return ToolResult(
            success=True,
            result="No terminal sessions. Use create_terminal to create one, or run_command to automatically create one."
        )

    lines = ["Terminal Sessions:"]
    active_id = webcontainer_state.get("active_terminal_id")

    for t in terminals:
        status = "🟢 Running" if t.get("is_running") else "⚫ Idle"
        active = " (active)" if t.get("id") == active_id else ""
        name = t.get("name", t.get("id", "unknown"))
        cmd = t.get("command", "")
        cmd_str = f" - {cmd}" if cmd else ""
        lines.append(f"  [{t.get('id', 'unknown')}] {name}{active}: {status}{cmd_str}")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


def switch_terminal(terminal_id: str, webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Switch to a different terminal session.

    Args:
        terminal_id: ID of the terminal to switch to
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action to switch terminal
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    terminals = webcontainer_state.get("terminals", [])
    terminal_ids = [t.get("id") for t in terminals]

    if terminal_id not in terminal_ids:
        return ToolResult(
            success=False,
            result=f"Terminal '{terminal_id}' not found. Available: {terminal_ids}"
        )

    action = {
        "type": "switch_terminal",
        "payload": {
            "terminal_id": terminal_id
        }
    }

    return ToolResult(
        success=True,
        result=f"Switching to terminal: {terminal_id}",
        action=action
    )


def send_terminal_input(
    terminal_id: str,
    input_text: str,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Send input to a running terminal process.

    Args:
        terminal_id: ID of the terminal
        input_text: Text to send (supports special chars: \\n for Enter, \\x03 for Ctrl+C)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action to send input
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    terminals = webcontainer_state.get("terminals", [])
    target = None
    for t in terminals:
        if t.get("id") == terminal_id:
            target = t
            break

    if not target:
        terminal_ids = [t.get("id") for t in terminals]
        terminal_details = []
        for t in terminals:
            tid = t.get("id", "unknown")
            cmd = t.get("command", "idle")
            running = "running" if t.get("is_running") else "idle"
            terminal_details.append(f"{tid} ({running}, last cmd: {cmd})")

        return ToolResult(
            success=False,
            result=f"❌ Terminal '{terminal_id}' not found.\n\n"
                   f"📋 Available terminals ({len(terminals)}):\n" +
                   "\n".join(f"  • {detail}" for detail in terminal_details) + "\n\n"
                   f"💡 Hint: Use list_terminals() to see all terminals, or use the actual terminal ID from the list above."
        )

    if not target.get("is_running"):
        return ToolResult(
            success=False,
            result=f"Terminal '{terminal_id}' has no running process. Use run_command to start one."
        )

    # Process escape sequences
    processed_input = input_text.replace("\\n", "\n").replace("\\x03", "\x03")

    action = {
        "type": "send_terminal_input",
        "payload": {
            "terminal_id": terminal_id,
            "input": processed_input
        }
    }

    return ToolResult(
        success=True,
        result=f"Sending input to terminal '{terminal_id}': {repr(input_text)}",
        action=action
    )


def kill_terminal(terminal_id: str, webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Kill a terminal session and its process.

    Args:
        terminal_id: ID of the terminal to kill
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action to kill terminal
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    terminals = webcontainer_state.get("terminals", [])
    terminal_ids = [t.get("id") for t in terminals]

    if terminal_id not in terminal_ids:
        return ToolResult(
            success=False,
            result=f"Terminal '{terminal_id}' not found. Available: {terminal_ids}"
        )

    action = {
        "type": "kill_terminal",
        "payload": {
            "terminal_id": terminal_id
        }
    }

    return ToolResult(
        success=True,
        result=f"Killing terminal: {terminal_id}",
        action=action
    )


def get_terminal_history(
    terminal_id: Optional[str] = None,
    lines: int = 100,
    search: Optional[str] = None,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Get the complete command history of a terminal.

    Args:
        terminal_id: ID of the terminal (uses active if not specified)
        lines: Number of lines to retrieve (default 100, max 500)
        search: Optional search pattern to filter output
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with terminal history
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    terminals = webcontainer_state.get("terminals", [])

    if not terminals:
        return ToolResult(
            success=True,
            result="No terminal sessions available."
        )

    # Find target terminal
    target = None
    if terminal_id:
        for t in terminals:
            if t.get("id") == terminal_id:
                target = t
                break
        if not target:
            return ToolResult(
                success=False,
                result=f"Terminal '{terminal_id}' not found"
            )
    else:
        # Use active terminal or first one
        active_id = webcontainer_state.get("active_terminal_id")
        if active_id:
            for t in terminals:
                if t.get("id") == active_id:
                    target = t
                    break
        if not target:
            target = terminals[0]

    # Get history
    history = target.get("history", [])
    if not history:
        return ToolResult(
            success=True,
            result=f"Terminal '{target.get('id')}' has no output history."
        )

    # Extract text from history
    output_lines = []
    for entry in history:
        if isinstance(entry, dict):
            data = entry.get("data", "")
        else:
            data = str(entry)
        output_lines.extend(data.split("\n"))

    # Apply search filter if provided
    if search:
        try:
            pattern = re.compile(search, re.IGNORECASE)
            output_lines = [line for line in output_lines if pattern.search(line)]
        except re.error as e:
            return ToolResult(
                success=False,
                result=f"Invalid search pattern: {e}"
            )

    # Limit lines
    lines = min(lines, MAX_HISTORY_LINES)
    if len(output_lines) > lines:
        output_lines = output_lines[-lines:]
        truncated = True
    else:
        truncated = False

    # Format output
    status = "🟢 Running" if target.get("is_running") else "⚫ Idle"
    header = f"Terminal '{target.get('id')}' ({status}) - {len(output_lines)} lines"
    if truncated:
        header += f" (truncated, showing last {lines})"
    if search:
        header += f" [filtered by: {search}]"

    result = header + "\n" + "-" * 40 + "\n" + "\n".join(output_lines)

    return ToolResult(
        success=True,
        result=result
    )


# ============================================
# Enhanced File Tools
# ============================================

def edit_file(
    path: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Edit specific content in a file without rewriting the whole file.

    Args:
        path: File path
        old_text: Text to find and replace
        new_text: Replacement text
        replace_all: Replace all occurrences (default: first only)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action for frontend
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    normalized_path = path if path.startswith("/") else f"/{path}"
    files = webcontainer_state.get("files", {})

    # Check file exists
    if normalized_path not in files and path not in files:
        available = list(files.keys())[:10]
        return ToolResult(
            success=False,
            result=f"File not found: {path}. Available files: {available}"
        )

    content = files.get(normalized_path) or files.get(path)

    # Check if old_text exists
    if old_text not in content:
        # Try to find similar text for helpful error
        lines = content.split("\n")
        preview = "\n".join(lines[:20])
        return ToolResult(
            success=False,
            result=f"Text not found in {path}. The text to replace does not exist.\n\nFile preview (first 20 lines):\n```\n{preview}\n```"
        )

    # Count occurrences
    count = content.count(old_text)

    if count > 1 and not replace_all:
        # Find line numbers of occurrences
        line_nums = []
        for i, line in enumerate(content.split("\n"), 1):
            if old_text in line:
                line_nums.append(i)

        return ToolResult(
            success=False,
            result=f"Found {count} occurrences of the text at lines {line_nums}. Use replace_all=true to replace all, or provide more context to make the match unique."
        )

    action = {
        "type": "edit_file",
        "payload": {
            "path": normalized_path,
            "old_text": old_text,
            "new_text": new_text,
            "replace_all": replace_all
        }
    }

    replaced_count = count if replace_all else 1
    return ToolResult(
        success=True,
        result=f"Editing {path}: replacing {replaced_count} occurrence(s)",
        action=action
    )


def rename_file(old_path: str, new_path: str, webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Rename or move a file.

    Args:
        old_path: Current file path
        new_path: New file path
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action for frontend
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    old_normalized = old_path if old_path.startswith("/") else f"/{old_path}"
    new_normalized = new_path if new_path.startswith("/") else f"/{new_path}"

    files = webcontainer_state.get("files", {})

    # Check source exists
    if old_normalized not in files and old_path not in files:
        return ToolResult(
            success=False,
            result=f"Source file not found: {old_path}"
        )

    # Check destination doesn't exist
    if new_normalized in files or new_path in files:
        return ToolResult(
            success=False,
            result=f"Destination file already exists: {new_path}. Delete it first or choose a different name."
        )

    action = {
        "type": "rename_file",
        "payload": {
            "old_path": old_normalized,
            "new_path": new_normalized
        }
    }

    return ToolResult(
        success=True,
        result=f"Renaming {old_path} -> {new_path}",
        action=action
    )


def search_in_file(
    path: str,
    pattern: str,
    context: int = 0,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Search for a pattern in a file with optional context lines.

    Args:
        path: File path to search in
        pattern: Regex pattern to search for
        context: Number of lines to show before and after each match (0-5, default 0)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with matching lines, line numbers, and optional context
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    normalized_path = path if path.startswith("/") else f"/{path}"
    files = webcontainer_state.get("files", {})

    content = files.get(normalized_path) or files.get(path)
    if content is None:
        return ToolResult(
            success=False,
            result=f"File not found: {path}"
        )

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return ToolResult(
            success=False,
            result=f"Invalid regex pattern: {e}"
        )

    # Clamp context to 0-5 range
    context = max(0, min(5, context))

    lines = content.split("\n")
    total_lines = len(lines)

    # Find all matching line indices (0-based)
    match_indices = []
    for i, line in enumerate(lines):
        if regex.search(line):
            match_indices.append(i)

    if not match_indices:
        return ToolResult(
            success=True,
            result=f"No matches found for '{pattern}' in {path}"
        )

    # Build output with context
    output_parts = []
    shown_lines = set()  # Track which lines have been shown to avoid duplicates

    for match_idx in match_indices[:MAX_SEARCH_RESULTS]:
        # Calculate context range
        start = max(0, match_idx - context)
        end = min(total_lines, match_idx + context + 1)

        # Add separator if there's a gap from previous output
        if shown_lines and start > max(shown_lines) + 1:
            output_parts.append("  ---")

        # Add context lines before, match line, and context lines after
        for i in range(start, end):
            if i not in shown_lines:
                line_num = i + 1  # 1-based line number
                line_content = lines[i].rstrip()

                if i == match_idx:
                    # Highlight matching line with arrow
                    output_parts.append(f"→ L{line_num}: {line_content}")
                else:
                    # Context line
                    output_parts.append(f"  L{line_num}: {line_content}")

                shown_lines.add(i)

    match_count = len(match_indices)
    truncated = ""
    if match_count > MAX_SEARCH_RESULTS:
        truncated = f"\n... and {match_count - MAX_SEARCH_RESULTS} more matches"

    return ToolResult(
        success=True,
        result=f"Found {match_count} matches in {path}:\n" + "\n".join(output_parts) + truncated
    )


def search_in_project(
    pattern: str,
    file_pattern: str = "*",
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Search for a pattern across all project files.

    Args:
        pattern: Regex pattern to search for
        file_pattern: Glob pattern to filter files (e.g., "*.jsx", "src/**/*.ts")
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with matches grouped by file
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    files = webcontainer_state.get("files", {})

    if not files:
        return ToolResult(
            success=True,
            result="Project is empty. No files to search."
        )

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return ToolResult(
            success=False,
            result=f"Invalid regex pattern: {e}"
        )

    # Filter files by pattern
    matched_files = []
    for file_path in files.keys():
        # Normalize path for matching
        normalized = file_path.lstrip("/")

        # Skip node_modules by default
        if "node_modules" in normalized:
            continue

        # Apply glob pattern
        if file_pattern != "*":
            if not fnmatch.fnmatch(normalized, file_pattern):
                continue

        matched_files.append(file_path)

    # Search in matched files
    results = []
    total_matches = 0

    for file_path in matched_files:
        content = files[file_path]
        lines = content.split("\n")
        file_matches = []

        for i, line in enumerate(lines, 1):
            if regex.search(line):
                file_matches.append(f"    L{i}: {line.strip()[:80]}")
                total_matches += 1

        if file_matches:
            results.append(f"  {file_path}:")
            results.extend(file_matches[:5])  # Max 5 matches per file
            if len(file_matches) > 5:
                results.append(f"    ... and {len(file_matches) - 5} more matches")

    if not results:
        return ToolResult(
            success=True,
            result=f"No matches found for '{pattern}' in project files matching '{file_pattern}'"
        )

    if len(results) > MAX_SEARCH_RESULTS:
        results = results[:MAX_SEARCH_RESULTS]
        results.append(f"... truncated (showing first {MAX_SEARCH_RESULTS} results)")

    return ToolResult(
        success=True,
        result=f"Found {total_matches} matches across project:\n" + "\n".join(results)
    )


def read_lines(
    path: str,
    start_line: int,
    end_line: int = None,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Read specific lines from a file by line number range.

    Useful for examining code around a specific line (e.g., after finding an error at line 45).
    More efficient than read_file when you only need a portion of a file.

    Args:
        path: File path to read from
        start_line: First line to read (1-based, inclusive)
        end_line: Last line to read (1-based, inclusive). If omitted, reads only start_line.
                  If negative, reads from start_line to (total_lines + end_line).
                  Example: end_line=-1 reads to the last line.
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with the requested lines and their line numbers

    Examples:
        read_lines("/src/App.jsx", 45)           → Read only line 45
        read_lines("/src/App.jsx", 40, 50)       → Read lines 40-50
        read_lines("/src/App.jsx", 1, 20)        → Read first 20 lines
        read_lines("/src/App.jsx", 100, -1)      → Read from line 100 to end
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    normalized_path = path if path.startswith("/") else f"/{path}"
    files = webcontainer_state.get("files", {})

    content = files.get(normalized_path) or files.get(path)
    if content is None:
        return ToolResult(
            success=False,
            result=f"File not found: {path}"
        )

    lines = content.split("\n")
    total_lines = len(lines)

    # Validate start_line
    if start_line < 1:
        return ToolResult(
            success=False,
            result=f"start_line must be >= 1, got {start_line}"
        )

    if start_line > total_lines:
        return ToolResult(
            success=False,
            result=f"start_line {start_line} exceeds file length ({total_lines} lines)"
        )

    # Handle end_line
    if end_line is None:
        end_line = start_line  # Read only one line
    elif end_line < 0:
        # Negative end_line: relative to end of file
        end_line = total_lines + end_line + 1

    # Clamp end_line to valid range
    end_line = max(start_line, min(end_line, total_lines))

    # Limit to 100 lines max to prevent excessive output
    max_lines = 100
    if end_line - start_line + 1 > max_lines:
        end_line = start_line + max_lines - 1

    # Extract lines (convert to 0-based index)
    output_parts = []
    for i in range(start_line - 1, end_line):
        line_num = i + 1
        line_content = lines[i].rstrip()
        output_parts.append(f"L{line_num}: {line_content}")

    lines_read = end_line - start_line + 1
    header = f"{path} (lines {start_line}-{end_line} of {total_lines}):\n"

    return ToolResult(
        success=True,
        result=header + "\n".join(output_parts)
    )


# ============================================
# Preview Tools
# ============================================

def take_screenshot(
    selector: Optional[str] = None,
    full_page: bool = False,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Capture a screenshot of the preview.

    Args:
        selector: CSS selector to screenshot specific element (optional)
        full_page: Capture full scrollable page (default: viewport only)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action for frontend
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    preview_url = webcontainer_state.get("preview_url")
    preview = webcontainer_state.get("preview", {})

    if not preview_url:
        return ToolResult(
            success=False,
            result="Preview is not available. Start the dev server first with start_dev_server."
        )

    if preview.get("is_loading"):
        return ToolResult(
            success=False,
            result="Preview is still loading. Wait a moment and try again."
        )

    if preview.get("has_error"):
        error_msg = preview.get("error_message", "Unknown error")
        return ToolResult(
            success=False,
            result=f"Preview has an error: {error_msg}. Fix the error first."
        )

    action = {
        "type": "take_screenshot",
        "payload": {
            "selector": selector,
            "full_page": full_page
        }
    }

    target = f"element '{selector}'" if selector else ("full page" if full_page else "viewport")
    return ToolResult(
        success=True,
        result=f"Taking screenshot of {target}...",
        action=action
    )


def get_preview_errors(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Get detailed error information from the preview iframe.
    This includes Vite build errors, runtime errors, and any error overlay messages.

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with detailed error information
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    preview = webcontainer_state.get("preview", {})
    errors_found = []

    # Check for preview-level errors
    if preview.get("has_error"):
        error_msg = preview.get("error_message", "Unknown preview error")
        error_stack = preview.get("error_stack", "")
        errors_found.append(f"🔴 Preview Error: {error_msg}")
        if error_stack:
            errors_found.append(f"   Stack: {error_stack[:200]}")

    # Check for Vite build errors in error_overlay
    error_overlay = preview.get("error_overlay")
    if error_overlay:
        overlay_msg = error_overlay.get("message", "")
        overlay_stack = error_overlay.get("stack", "")
        if overlay_msg:
            errors_found.append(f"🔴 Build Error (Vite): {overlay_msg[:300]}")
        if overlay_stack:
            # Extract file path and line number from stack
            stack_lines = overlay_stack.split("\n")[:5]
            errors_found.append("   Stack trace:")
            for line in stack_lines:
                errors_found.append(f"      {line.strip()}")

    # Check console messages for errors
    console_messages = preview.get("console_messages", [])
    error_msgs = [m for m in console_messages if m.get("type") == "error"]

    if error_msgs:
        errors_found.append(f"\n🔴 Console Errors ({len(error_msgs)} found):")
        for msg in error_msgs[-3:]:  # Last 3 errors
            args = msg.get("args", [])
            content = " ".join(str(arg) for arg in args)[:200]
            errors_found.append(f"   • {content}")
            stack = msg.get("stack", "")
            if stack:
                first_line = stack.split("\n")[0]
                errors_found.append(f"     {first_line}")

    if not errors_found:
        preview_url = webcontainer_state.get("preview_url")
        if preview_url:
            return ToolResult(
                success=True,
                result="✅ No preview errors found. The app is running without errors."
            )
        else:
            return ToolResult(
                success=True,
                result="ℹ️ Preview not started yet. No errors to report."
            )

    return ToolResult(
        success=True,
        result="Preview Errors Detected:\n" + "\n".join(errors_found) + "\n\nℹ️ Use verify_changes() for a complete diagnostic report."
    )


def get_console_messages(
    types: Optional[List[str]] = None,
    limit: int = 50,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Get console messages from the preview.

    Args:
        types: Filter by message types ("log", "warn", "error", "info")
        limit: Maximum number of messages to return (default 50)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with console messages
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    preview = webcontainer_state.get("preview", {})
    messages = preview.get("console_messages", [])

    if not messages:
        preview_url = webcontainer_state.get("preview_url")
        if not preview_url:
            return ToolResult(
                success=True,
                result="No console messages. Preview is not running."
            )
        return ToolResult(
            success=True,
            result="No console messages recorded yet."
        )

    # Filter by types
    if types:
        valid_types = {"log", "warn", "error", "info", "debug"}
        types = [t for t in types if t in valid_types]
        if types:
            messages = [m for m in messages if m.get("type") in types]

    # Limit
    limit = min(limit, MAX_CONSOLE_MESSAGES)
    if len(messages) > limit:
        messages = messages[-limit:]
        truncated = True
    else:
        truncated = False

    if not messages:
        return ToolResult(
            success=True,
            result=f"No console messages of types {types} found."
        )

    # Format messages
    lines = []
    type_icons = {
        "log": "📝",
        "info": "ℹ️",
        "warn": "⚠️",
        "error": "❌",
        "debug": "🔍"
    }

    for msg in messages:
        icon = type_icons.get(msg.get("type", "log"), "📝")
        msg_type = msg.get("type", "log").upper()
        args = msg.get("args", [])

        # Format args
        try:
            content = " ".join(str(arg) for arg in args)
        except Exception:
            content = str(args)

        # Truncate long messages
        if len(content) > 200:
            content = content[:200] + "..."

        lines.append(f"{icon} [{msg_type}] {content}")

        # Include stack for errors
        if msg.get("stack") and msg.get("type") == "error":
            stack_lines = msg["stack"].split("\n")[:3]
            for sl in stack_lines:
                lines.append(f"      {sl.strip()}")

    header = f"Console Messages ({len(messages)} shown)"
    if truncated:
        header += f" [truncated to last {limit}]"
    if types:
        header += f" [filtered: {', '.join(types)}]"

    return ToolResult(
        success=True,
        result=header + "\n" + "-" * 40 + "\n" + "\n".join(lines)
    )


def get_preview_dom(
    selector: str = "body",
    depth: int = 3,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Get the DOM structure of a preview element.

    Args:
        selector: CSS selector (default "body")
        depth: Maximum nesting depth to return (default 3)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action for frontend
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    preview_url = webcontainer_state.get("preview_url")

    if not preview_url:
        return ToolResult(
            success=False,
            result="Preview is not available. Start the dev server first."
        )

    action = {
        "type": "get_preview_dom",
        "payload": {
            "selector": selector,
            "depth": min(depth, 10)  # Cap depth at 10
        }
    }

    return ToolResult(
        success=True,
        result=f"Getting DOM structure for '{selector}' (depth: {depth})...",
        action=action
    )


def clear_console(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Clear console messages from the preview.

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with action for frontend
    """
    action = {
        "type": "clear_console",
        "payload": {}
    }

    return ToolResult(
        success=True,
        result="Clearing console messages...",
        action=action
    )


# ============================================
# Diagnostic Tools
# ============================================

def verify_changes(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Verify if recent changes caused any errors.
    Checks terminal output, console messages, and preview status.

    This is a CRITICAL tool that should be called after making changes
    to detect and fix issues early.

    **BEST PRACTICE**: After making file changes, wait 3-5 seconds before calling
    this tool to allow Vite HMR to detect changes and output any errors.

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with diagnostic report
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    issues_found = []
    warnings = []
    info = []

    # 1. Check terminal output for errors
    terminals = webcontainer_state.get("terminals", [])
    for terminal in terminals:
        history = terminal.get("history", [])
        last_output = terminal.get("last_output", [])

        # Combine outputs
        all_output = []
        for entry in history[-30:]:  # Check last 30 entries
            if isinstance(entry, dict):
                all_output.append(entry.get("data", ""))
            else:
                all_output.append(str(entry))
        all_output.extend(last_output[-20:] if last_output else [])

        output_text = "\n".join(all_output).lower()

        # Check for common error patterns
        error_patterns = [
            ("error:", "Build/compile error"),
            ("syntaxerror", "Syntax error"),
            ("typeerror", "Type error"),
            ("referenceerror", "Reference error (undefined variable)"),
            ("cannot find module", "Missing module/import"),
            ("module not found", "Module not found"),
            ("failed to compile", "Compilation failed"),
            ("enoent", "File not found"),
            ("permission denied", "Permission error"),
            ("npm err!", "NPM error"),
            ("error: expected", "Parse error"),
        ]

        for pattern, desc in error_patterns:
            if pattern in output_text:
                # Extract relevant error lines
                error_lines = []
                for line in all_output:
                    if pattern in line.lower():
                        error_lines.append(line.strip())
                if error_lines:
                    issues_found.append(f"🔴 {desc} in terminal:\n   {error_lines[0][:200]}")
                break

    # 2. Check preview for Vite build errors (error_overlay)
    preview = webcontainer_state.get("preview", {})
    error_overlay = preview.get("error_overlay")

    if error_overlay:
        overlay_msg = error_overlay.get("message", "")
        overlay_stack = error_overlay.get("stack", "")
        if overlay_msg:
            # This is a Vite build error - very important!
            issues_found.append(f"🔴 BUILD ERROR (Vite): {overlay_msg[:300]}")
            if overlay_stack:
                stack_lines = overlay_stack.split("\n")[:3]
                for line in stack_lines:
                    if line.strip():
                        issues_found.append(f"   {line.strip()[:150]}")

            # Add helpful hint for common errors
            if "Failed to resolve import" in overlay_msg or "Cannot find module" in overlay_msg:
                issues_found.append("   💡 Hint: A file is importing something that doesn't exist.")
                issues_found.append("   → Use file_exists() to check, then create the missing file or remove the import")

    # 3. Check console messages for runtime errors
    console_messages = preview.get("console_messages", [])

    error_count = 0
    warn_count = 0
    for msg in console_messages[-20:]:  # Check last 20 messages
        msg_type = msg.get("type", "log")
        args = msg.get("args", [])
        content = " ".join(str(arg) for arg in args)[:150]

        if msg_type == "error":
            error_count += 1
            if error_count <= 3:  # Show first 3 errors
                stack = msg.get("stack", "")
                stack_preview = stack.split("\n")[0] if stack else ""
                issues_found.append(f"🔴 Runtime error: {content}")
                if stack_preview:
                    issues_found.append(f"   Stack: {stack_preview[:100]}")
        elif msg_type == "warn":
            warn_count += 1
            if warn_count <= 2:  # Show first 2 warnings
                warnings.append(f"⚠️ Warning: {content}")

    if error_count > 3:
        issues_found.append(f"   ... and {error_count - 3} more errors")
    if warn_count > 2:
        warnings.append(f"   ... and {warn_count - 2} more warnings")

    # 3. Check preview status
    preview_url = webcontainer_state.get("preview_url")
    if preview.get("has_error"):
        error_msg = preview.get("error_message", "Unknown preview error")
        issues_found.append(f"🔴 Preview error: {error_msg}")
    elif preview.get("is_loading"):
        info.append("⏳ Preview is still loading...")
    elif preview_url:
        info.append(f"✅ Preview is running at {preview_url}")
    else:
        info.append("ℹ️ Preview not started (run start_dev_server to start)")

    # 4. Check WebContainer status
    status = webcontainer_state.get("status", "unknown")
    error = webcontainer_state.get("error")
    if error:
        issues_found.append(f"🔴 WebContainer error: {error}")
    elif status == "ready":
        info.append("✅ WebContainer is ready")
    elif status == "booting":
        info.append("⏳ WebContainer is starting...")

    # Build report
    report_lines = ["## Verification Report\n"]

    if issues_found:
        report_lines.append("### ❌ Issues Found (Need to Fix)")
        report_lines.extend(issues_found)
        report_lines.append("")

    if warnings:
        report_lines.append("### ⚠️ Warnings")
        report_lines.extend(warnings)
        report_lines.append("")

    if info:
        report_lines.append("### ℹ️ Status")
        report_lines.extend(info)
        report_lines.append("")

    if not issues_found and not warnings:
        report_lines.append("### ✅ All Clear!")
        report_lines.append("No errors or warnings detected. Changes appear successful.")
    elif issues_found:
        report_lines.append("### 🔧 Recommended Actions")
        report_lines.append("1. Read the file mentioned in the error")
        report_lines.append("2. Use edit_file to fix the specific issue")
        report_lines.append("3. Run verify_changes again to confirm the fix")

    return ToolResult(
        success=True,
        result="\n".join(report_lines)
    )


# ============================================
# Context Understanding Tools (New)
# ============================================

def get_webcontainer_state(webcontainer_state: Optional[dict] = None) -> ToolResult:
    """
    Get complete WebContainer state for context understanding.

    Returns comprehensive information about:
    - File system structure and active files
    - Terminal sessions and their status
    - Preview/dev server status
    - Console messages and errors
    - Overall system health

    Use this tool when you need to:
    - Understand the current project state
    - Get full context before making decisions
    - Debug complex issues
    - Verify what the user is working on

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with complete state summary
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    lines = ["# WebContainer Complete State\n"]

    # 1. System Status
    status = webcontainer_state.get("status", "unknown")
    error = webcontainer_state.get("error")
    lines.append("## System Status")
    lines.append(f"- Status: {status}")
    if error:
        lines.append(f"- Error: {error}")
    lines.append("")

    # 2. File System
    files = webcontainer_state.get("files", {})
    active_file = webcontainer_state.get("active_file")
    lines.append("## File System")
    lines.append(f"- Total Files: {len(files)}")
    lines.append(f"- Active File: {active_file or 'None'}")

    # Show recent files
    if files:
        file_list = sorted(files.keys())
        lines.append("\n### Recent Files:")
        for f in file_list[:15]:
            marker = " ← (active)" if f == active_file else ""
            lines.append(f"  - {f}{marker}")
        if len(file_list) > 15:
            lines.append(f"  ... and {len(file_list) - 15} more files")
    lines.append("")

    # 3. Terminals
    terminals = webcontainer_state.get("terminals", [])
    active_terminal_id = webcontainer_state.get("active_terminal_id")
    lines.append("## Terminal Sessions")
    lines.append(f"- Total Terminals: {len(terminals)}")

    if terminals:
        for t in terminals:
            tid = t.get("id", "unknown")
            name = t.get("name", tid)
            is_running = t.get("is_running", False)
            is_active = tid == active_terminal_id

            status_icon = "🟢" if is_running else "⚫"
            active_marker = " (active)" if is_active else ""

            lines.append(f"\n### {name}{active_marker}")
            lines.append(f"  - ID: {tid}")
            lines.append(f"  - Status: {status_icon} {'Running' if is_running else 'Idle'}")

            cmd = t.get("command", "")
            if cmd:
                lines.append(f"  - Last Command: {cmd}")

            history = t.get("history", [])
            if history:
                lines.append(f"  - Output Lines: {len(history)}")
                last_outputs = []
                for entry in history[-5:]:
                    if isinstance(entry, dict):
                        data = entry.get("data", "")
                    else:
                        data = str(entry)
                    if data.strip():
                        last_outputs.append(data.strip()[:80])

                if last_outputs:
                    lines.append("  - Recent Output:")
                    for out in last_outputs:
                        lines.append(f"      {out}")
    else:
        lines.append("- No terminal sessions")
    lines.append("")

    # 4. Preview/Dev Server
    preview = webcontainer_state.get("preview", {})
    preview_url = webcontainer_state.get("preview_url")
    lines.append("## Preview/Dev Server")
    lines.append(f"- URL: {preview_url or 'Not running'}")
    lines.append(f"- Loading: {preview.get('is_loading', False)}")
    lines.append(f"- Has Error: {preview.get('has_error', False)}")

    if preview.get("has_error"):
        error_msg = preview.get("error_message", "Unknown error")
        lines.append(f"- Error Message: {error_msg}")

    console_msgs = preview.get("console_messages", [])
    if console_msgs:
        error_count = sum(1 for m in console_msgs if m.get("type") == "error")
        warn_count = sum(1 for m in console_msgs if m.get("type") == "warn")
        log_count = len(console_msgs) - error_count - warn_count

        lines.append(f"\n### Console Messages:")
        lines.append(f"  - Errors: {error_count}")
        lines.append(f"  - Warnings: {warn_count}")
        lines.append(f"  - Logs: {log_count}")

        recent_errors = [m for m in console_msgs if m.get("type") == "error"][-3:]
        if recent_errors:
            lines.append("\n  Recent Errors:")
            for msg in recent_errors:
                args = msg.get("args", [])
                content = " ".join(str(arg) for arg in args)[:100]
                lines.append(f"    • {content}")

    viewport = preview.get("viewport", {})
    if viewport:
        lines.append(f"\n### Viewport:")
        lines.append(f"  - Size: {viewport.get('width', 0)}x{viewport.get('height', 0)}")

    lines.append("")

    # 5. Action Results Feedback (from previous interaction)
    action_results = webcontainer_state.get("action_results", [])
    if action_results:
        lines.append("## 🔄 Previous Action Results (IMPORTANT!)")
        lines.append("These are results from your previous commands - check for failures!\n")

        failed_actions = [a for a in action_results if not a.get("success", True)]
        successful_actions = [a for a in action_results if a.get("success", True)]

        if failed_actions:
            lines.append("### ❌ Failed Actions:")
            for action in failed_actions:
                action_type = action.get("type", "unknown")
                error = action.get("error", "Unknown error")
                lines.append(f"  - **{action_type}**: {error}")
            lines.append("")
            lines.append("⚠️ **You must address these failures before proceeding!**")
            lines.append("")

        if successful_actions:
            lines.append("### ✅ Successful Actions:")
            for action in successful_actions:
                action_type = action.get("type", "unknown")
                result = action.get("result", "Completed")[:100]
                lines.append(f"  - {action_type}: {result}")
        lines.append("")

    # 6. Summary
    lines.append("## Summary")

    health_issues = []
    if status != "ready":
        health_issues.append(f"WebContainer not ready (status: {status})")
    if error:
        health_issues.append(f"System error: {error}")
    if preview.get("has_error"):
        health_issues.append("Preview has errors")

    error_msgs = [m for m in console_msgs if m.get("type") == "error"]
    if error_msgs:
        health_issues.append(f"{len(error_msgs)} console errors")

    # Check for failed actions from previous interaction
    if action_results:
        failed_count = sum(1 for a in action_results if not a.get("success", True))
        if failed_count > 0:
            health_issues.append(f"⚠️ {failed_count} previous action(s) FAILED - must address!")

    if health_issues:
        lines.append("### ⚠️ Issues Detected:")
        for issue in health_issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("### ✅ All Systems Healthy")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


def understand_user_context(
    include_screenshot: bool = True,
    webcontainer_state: Optional[dict] = None
) -> ToolResult:
    """
    Comprehensive tool to understand what the user is currently working on.

    Combines multiple data sources:
    - WebContainer state (files, terminals, preview)
    - Preview screenshot (if available)
    - Console errors and warnings
    - Recent terminal output

    This is the PRIMARY tool for understanding user intent and context.
    Use it when:
    - Starting a conversation
    - User asks about "this" or "current state"
    - Need to understand what user is seeing
    - Before making suggestions or changes

    Args:
        include_screenshot: Whether to capture a preview screenshot (default: true)
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with comprehensive context, may include action for screenshot
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    state_result = get_webcontainer_state(webcontainer_state)

    preview_url = webcontainer_state.get("preview_url")
    preview = webcontainer_state.get("preview", {})
    can_screenshot = (
        preview_url and
        not preview.get("is_loading") and
        not preview.get("has_error")
    )

    context_lines = [
        "# User Context Analysis\n",
        "## Current State",
        state_result.result,
        ""
    ]

    action = None
    if include_screenshot and can_screenshot:
        context_lines.append("## Visual Preview")
        context_lines.append("📸 Taking screenshot of current preview...")
        context_lines.append("(Screenshot will be included in response)\n")

        action = {
            "type": "take_screenshot",
            "payload": {
                "selector": None,
                "full_page": False
            }
        }
    elif include_screenshot and preview_url:
        context_lines.append("## Visual Preview")
        if preview.get("is_loading"):
            context_lines.append("⏳ Preview is still loading, screenshot not available yet")
        elif preview.get("has_error"):
            context_lines.append(f"❌ Preview has error: {preview.get('error_message', 'Unknown')}")
        context_lines.append("")
    else:
        context_lines.append("## Visual Preview")
        context_lines.append("ℹ️ Preview not running, no screenshot available")
        context_lines.append("(Start dev server to enable visual preview)\n")

    context_lines.append("## Interpretation")

    active_file = webcontainer_state.get("active_file")
    if active_file:
        context_lines.append(f"- User is currently viewing: `{active_file}`")

    terminals = webcontainer_state.get("terminals", [])
    running_terminals = [t for t in terminals if t.get("is_running")]
    if running_terminals:
        context_lines.append(f"- {len(running_terminals)} terminal(s) running processes")
        for t in running_terminals:
            cmd = t.get("command", "unknown")
            context_lines.append(f"  - Running: {cmd}")

    files = webcontainer_state.get("files", {})
    file_paths = list(files.keys())

    has_react = any("react" in files.get(f, "").lower() for f in file_paths)
    has_vite = any("vite" in f.lower() for f in file_paths)
    has_package_json = "/package.json" in file_paths or "package.json" in file_paths

    if has_package_json:
        pkg_content = files.get("/package.json") or files.get("package.json", "")
        if "react" in pkg_content.lower():
            has_react = True
        if "vite" in pkg_content.lower():
            has_vite = True

    project_type = []
    if has_react:
        project_type.append("React")
    if has_vite:
        project_type.append("Vite")

    if project_type:
        context_lines.append(f"- Project type: {' + '.join(project_type)}")

    return ToolResult(
        success=True,
        result="\n".join(context_lines),
        action=action
    )


# ============================================
# Tool Registry
# ============================================

# Tools that read from state (no frontend action needed)
STATE_QUERY_TOOLS = {
    # File reading
    "read_file": read_file,
    "read_lines": read_lines,
    "list_files": list_files,
    "file_exists": file_exists,
    "get_project_structure": get_project_structure,
    "search_in_file": search_in_file,
    "search_in_project": search_in_project,
    # Terminal reading
    "get_terminal_output": get_terminal_output,
    "get_terminal_history": get_terminal_history,
    "list_terminals": list_terminals,
    # Preview reading
    "get_preview_status": get_preview_status,
    "get_preview_errors": get_preview_errors,
    "get_console_messages": get_console_messages,
    # Diagnostic
    "verify_changes": verify_changes,
    # Context understanding (NEW)
    "get_webcontainer_state": get_webcontainer_state,
    "understand_user_context": understand_user_context,
}

# Tools that require frontend action
ACTION_TOOLS = {
    # File operations
    "write_file": write_file,
    "delete_file": delete_file,
    "create_directory": create_directory,
    "edit_file": edit_file,
    "rename_file": rename_file,
    # Terminal operations
    "run_command": run_command,
    "install_dependencies": install_dependencies,
    "start_dev_server": start_dev_server,
    "stop_server": stop_server,
    "create_terminal": create_terminal,
    "switch_terminal": switch_terminal,
    "send_terminal_input": send_terminal_input,
    "kill_terminal": kill_terminal,
    # Preview operations
    "take_screenshot": take_screenshot,
    "get_preview_dom": get_preview_dom,
    "clear_console": clear_console,
}

# All tools
ALL_TOOLS = {**STATE_QUERY_TOOLS, **ACTION_TOOLS}


def get_all_tools():
    """Get list of all tool functions"""
    return list(ALL_TOOLS.values())


def get_tool_definitions() -> List[dict]:
    """
    Get tool definitions in Claude API format.

    Returns:
        List of tool definition dicts
    """
    return [
        # ============================================
        # STATE QUERY TOOLS - File Reading
        # ============================================
        {
            "name": "read_file",
            "description": "Read the content of a file. Returns the full file content.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file (e.g., '/src/App.jsx' or 'package.json')"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "list_files",
            "description": "List files and directories at a path. Shows icons for files (📄) and directories (📁).",
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
        {
            "name": "file_exists",
            "description": "Check if a file or directory exists at the given path.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to check"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "get_project_structure",
            "description": "Get the complete project file tree. Shows all files and directories in a tree format.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "search_in_file",
            "description": "Search for a pattern (regex) in a specific file. Returns matching lines with line numbers. Use context parameter to see surrounding code - very useful for understanding error context.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to search in"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for"
                    },
                    "context": {
                        "type": "integer",
                        "description": "Number of lines to show before and after each match (0-5, default 0). Use 2-3 for error debugging."
                    }
                },
                "required": ["path", "pattern"]
            }
        },
        {
            "name": "search_in_project",
            "description": "Search for a pattern across all project files. Excludes node_modules by default.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.jsx', 'src/**/*.ts'). Default '*'"
                    }
                },
                "required": ["pattern"]
            }
        },
        {
            "name": "read_lines",
            "description": "Read specific lines from a file by line number range. More efficient than read_file when you only need a portion. Perfect for examining code around error line numbers.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read from"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-based, inclusive)"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (1-based, inclusive). Omit to read only start_line. Use -1 to read to end of file."
                    }
                },
                "required": ["path", "start_line"]
            }
        },

        # ============================================
        # STATE QUERY TOOLS - Terminal Reading
        # ============================================
        {
            "name": "get_terminal_output",
            "description": "Get recent terminal output. Useful for checking command results and errors.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to retrieve (default 50)"
                    },
                    "terminal_id": {
                        "type": "string",
                        "description": "Specific terminal ID (optional, uses active terminal by default)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_terminal_history",
            "description": "Get the complete command history of a terminal. Supports filtering by search pattern.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "terminal_id": {
                        "type": "string",
                        "description": "Terminal ID (uses active if not specified)"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to retrieve (default 100, max 500)"
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional regex pattern to filter output"
                    }
                },
                "required": []
            }
        },
        {
            "name": "list_terminals",
            "description": "List all terminal sessions with their status (running/idle).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },

        # ============================================
        # STATE QUERY TOOLS - Preview Reading
        # ============================================
        {
            "name": "get_preview_status",
            "description": "Get the current status of the preview/dev server. Shows if the server is running and the preview URL.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_preview_errors",
            "description": "Get detailed error information from the preview iframe, including Vite build errors, runtime errors, and error overlay messages. Use this to quickly check what's broken in the preview. More focused than get_console_messages for error debugging.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_console_messages",
            "description": "Get console messages (log/warn/error/info) from the preview. Useful for debugging runtime issues.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by message types: 'log', 'warn', 'error', 'info' (default: all)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return (default 50)"
                    }
                },
                "required": []
            }
        },

        # ============================================
        # ACTION TOOLS - File Operations
        # ============================================
        {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist, and creates parent directories automatically. Use for creating new files or completely replacing file contents.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (e.g., '/src/components/Button.jsx')"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "edit_file",
            "description": "Edit specific content in a file by search and replace. More precise than write_file for small changes. If the old_text appears multiple times, use replace_all=true or provide more context.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Text to find and replace"
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text"
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default: false, replaces first only)"
                    }
                },
                "required": ["path", "old_text", "new_text"]
            }
        },
        {
            "name": "delete_file",
            "description": "Delete a file from the project.",
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
            "name": "rename_file",
            "description": "Rename or move a file to a new path.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "old_path": {
                        "type": "string",
                        "description": "Current file path"
                    },
                    "new_path": {
                        "type": "string",
                        "description": "New file path"
                    }
                },
                "required": ["old_path", "new_path"]
            }
        },
        {
            "name": "create_directory",
            "description": "Create a directory. Parent directories are created automatically.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to create"
                    }
                },
                "required": ["path"]
            }
        },

        # ============================================
        # ACTION TOOLS - Terminal Operations
        # ============================================
        {
            "name": "run_command",
            "description": "Run a shell command in the terminal. Use this for npm commands, running scripts, etc.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to run (e.g., 'npm', 'node', 'ls')"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command arguments (e.g., ['install', 'react'])"
                    }
                },
                "required": ["command"]
            }
        },
        {
            "name": "install_dependencies",
            "description": "Install npm packages. If no packages specified, installs all from package.json.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "packages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Packages to install (empty for all)"
                    },
                    "dev": {
                        "type": "boolean",
                        "description": "Install as dev dependencies"
                    }
                },
                "required": []
            }
        },
        {
            "name": "start_dev_server",
            "description": "Start the development server (runs npm install + npm run dev). IMPORTANT: This is a LONG-RUNNING async operation that takes 10-30 seconds. DO NOT call multiple times - once is enough! After calling, the preview will automatically become available when the server is ready. You can check get_terminal_output to see progress.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "stop_server",
            "description": "Stop the running development server.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "create_terminal",
            "description": "Create a new terminal session. Maximum 5 terminals allowed.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the terminal (auto-generated if not provided)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "switch_terminal",
            "description": "Switch to a different terminal session.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "terminal_id": {
                        "type": "string",
                        "description": "ID of the terminal to switch to"
                    }
                },
                "required": ["terminal_id"]
            }
        },
        {
            "name": "send_terminal_input",
            "description": "Send input to a running terminal process. Use \\\\n for Enter, \\\\x03 for Ctrl+C.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "terminal_id": {
                        "type": "string",
                        "description": "ID of the terminal"
                    },
                    "input_text": {
                        "type": "string",
                        "description": "Text to send to the terminal"
                    }
                },
                "required": ["terminal_id", "input_text"]
            }
        },
        {
            "name": "kill_terminal",
            "description": "Kill a terminal session and its running process.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "terminal_id": {
                        "type": "string",
                        "description": "ID of the terminal to kill"
                    }
                },
                "required": ["terminal_id"]
            }
        },

        # ============================================
        # ACTION TOOLS - Preview Operations
        # ============================================
        {
            "name": "take_screenshot",
            "description": "Capture a screenshot of the preview. Use this to verify visual changes. Returns a base64 encoded image.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to screenshot specific element (optional)"
                    },
                    "full_page": {
                        "type": "boolean",
                        "description": "Capture full scrollable page (default: viewport only)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_preview_dom",
            "description": "Get the DOM structure of a preview element. Useful for verifying element rendering.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector (default 'body')"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum nesting depth to return (default 3, max 10)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "clear_console",
            "description": "Clear all console messages from the preview.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },

        # ============================================
        # DIAGNOSTIC TOOLS
        # ============================================
        {
            "name": "verify_changes",
            "description": """CRITICAL: Use this tool after making file changes to detect errors.

This is the MOST IMPORTANT diagnostic tool. It checks:
1. Terminal output for build/compile errors
2. Console messages for runtime errors
3. Preview status for loading/error states
4. WebContainer health

**IMPORTANT TIMING**:
- After writing/editing files, you should call get_terminal_output first to check errors
- Or wait a moment for Vite HMR to process changes before calling verify_changes
- Calling verify_changes immediately after file changes may miss errors that haven't appeared yet

ALWAYS call verify_changes after:
- Writing or editing files (check terminal output first!)
- Installing dependencies
- Starting the dev server
- Any code modification

If errors are found, the tool provides specific guidance on how to fix them.
If verify_changes returns "All Clear" but you know you made changes, call get_terminal_output to check for recent errors.""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },

        # ============================================
        # CONTEXT UNDERSTANDING TOOLS (NEW)
        # ============================================
        {
            "name": "get_webcontainer_state",
            "description": """Get complete WebContainer state for context understanding.

Returns comprehensive information about:
- File system structure and active files
- Terminal sessions and their status
- Preview/dev server status
- Console messages and errors
- Overall system health

Use this tool when you need to:
- Understand the current project state before making decisions
- Get full context about what the user is working on
- Debug complex issues requiring system overview
- Verify the state after making changes

This is a READ-ONLY tool that provides a snapshot of the entire system state.""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "understand_user_context",
            "description": """PRIMARY tool for understanding what the user is currently working on.

Combines multiple data sources:
- Complete WebContainer state (files, terminals, preview)
- Visual preview screenshot (if dev server is running)
- Console errors and warnings
- Recent terminal output
- Project type detection

This tool provides the MOST COMPREHENSIVE view of user context.

Use this tool when:
- Starting a conversation to understand user's current work
- User asks about "this", "current state", or references their screen
- Need to understand what user is seeing before making suggestions
- Planning changes that depend on current project state
- Debugging issues that require full context

The tool will automatically:
1. Gather complete system state
2. Attempt to capture a preview screenshot (if available)
3. Analyze project type and active work
4. Provide interpretation and context

Args:
- include_screenshot: Whether to capture preview screenshot (default: true)

Returns:
- Comprehensive context analysis with visual preview if available""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "include_screenshot": {
                        "type": "boolean",
                        "description": "Whether to capture a screenshot of the preview (default: true). Set to false to skip screenshot."
                    }
                },
                "required": []
            }
        }
    ]
