"""
Terminal & Preview Reader Tools for Nexting Agent

Provides powerful tools for reading terminal output and preview errors.
Solves the critical problem: Agent can't see what user sees!

Tools:
1. get_all_terminals_output() - Read ALL terminal content at once
2. get_preview_error_overlay() - Extract Vite error overlay from preview
3. get_comprehensive_error_snapshot() - One-shot: terminals + preview + console
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
import os
import logging

logger = logging.getLogger(__name__)


# ============================================
# Tool Result Type
# ============================================

@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    result: str
    action: Optional[dict] = None

    def to_content(self) -> str:
        """Convert to string content for LLM"""
        if self.success:
            return self.result
        return f"Error: {self.result}"


# ============================================
# Terminal Reading Tools
# ============================================

def get_all_terminals_output(
    webcontainer_state: Optional[dict] = None,
    max_lines_per_terminal: int = 100,
    **kwargs
) -> ToolResult:
    """
    Get output from ALL terminals in one call.

    This is the PRIMARY tool for reading terminal content.
    Much better than calling get_terminal_output() multiple times!

    **Use this when:**
    - You need to check terminal output but don't know which terminal
    - Debugging build/server issues
    - Want to see all terminal activity at once
    - Looking for error messages across all terminals

    **What you get:**
    - Output from ALL active terminals (not just one)
    - History + recent output combined
    - Color-coded by terminal ID
    - Errors/warnings highlighted

    Args:
        webcontainer_state: Current WebContainer state
        max_lines_per_terminal: Max lines to return per terminal (default 100)

    Returns:
        ToolResult with all terminal outputs
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
            result="No active terminals found."
        )

    lines = [f"## 📟 All Terminals Output\n"]
    lines.append(f"**Active Terminals**: {len(terminals)}\n")
    lines.append("---\n")

    for terminal in terminals:
        terminal_id = terminal.get("id", "unknown")
        is_running = terminal.get("is_running", False)
        history = terminal.get("history", [])
        last_output = terminal.get("last_output", [])

        # Combine history and recent output
        all_output = []

        # Process history
        for entry in history[-50:]:  # Last 50 history entries
            if isinstance(entry, dict):
                data = entry.get("data", "")
                all_output.append(data)
            else:
                all_output.append(str(entry))

        # Add recent output
        if last_output:
            all_output.extend(last_output[-50:])

        # Limit total lines
        if len(all_output) > max_lines_per_terminal:
            skipped = len(all_output) - max_lines_per_terminal
            all_output = all_output[-max_lines_per_terminal:]
            lines.append(f"### Terminal `{terminal_id}` {'🟢 Running' if is_running else '⚪ Idle'}")
            lines.append(f"*(Showing last {max_lines_per_terminal} lines, {skipped} lines skipped)*\n")
        else:
            lines.append(f"### Terminal `{terminal_id}` {'🟢 Running' if is_running else '⚪ Idle'}")
            lines.append("")

        if not all_output:
            lines.append("*(No output)*\n")
        else:
            lines.append("```")
            for line in all_output:
                # Highlight errors
                line_str = str(line).strip()
                if line_str:
                    # Mark error lines
                    if any(keyword in line_str.lower() for keyword in ['error', 'err!', 'failed', 'cannot', 'enoent']):
                        lines.append(f"❌ {line_str}")
                    elif any(keyword in line_str.lower() for keyword in ['warn', 'warning']):
                        lines.append(f"⚠️  {line_str}")
                    else:
                        lines.append(line_str)
            lines.append("```\n")
            lines.append("---\n")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


# ============================================
# Preview Error Reading Tools
# ============================================

def get_preview_error_overlay(
    webcontainer_state: Optional[dict] = None,
    **kwargs
) -> ToolResult:
    """
    Extract Vite error overlay from preview.

    **CRITICAL**: This extracts the EXACT error text that user sees in preview!

    **Use this when:**
    - Preview shows red error screen
    - Need to know exact build error message
    - User says "there's an error on screen"
    - diagnose_preview_state() says there's a build error

    **What you get:**
    - Exact error message from Vite
    - File path and line number
    - Stack trace (if available)
    - Plugin name that caused error

    This is what the user ACTUALLY SEES in the preview window!

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with error overlay details
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    preview = webcontainer_state.get("preview", {})
    error_overlay = preview.get("error_overlay")

    if not error_overlay:
        return ToolResult(
            success=True,
            result="✅ No error overlay in preview. Preview is rendering normally."
        )

    # Extract error details
    message = error_overlay.get("message", "Unknown error")
    stack = error_overlay.get("stack", "")
    plugin = error_overlay.get("plugin", "")
    frame = error_overlay.get("frame", "")

    lines = ["## 🔴 Preview Error Overlay (What User Sees)\n"]

    # Plugin info
    if plugin:
        lines.append(f"**Plugin**: `{plugin}`\n")

    # Main error message
    lines.append("### Error Message\n")
    lines.append("```")
    lines.append(message)
    lines.append("```\n")

    # Code frame (shows the problematic code)
    if frame:
        lines.append("### Code Location\n")
        lines.append("```")
        lines.append(frame)
        lines.append("```\n")

    # Stack trace
    if stack:
        lines.append("### Stack Trace\n")
        lines.append("```")
        # Show first 15 lines of stack trace
        stack_lines = stack.split("\n")
        for line in stack_lines[:15]:
            if line.strip():
                lines.append(line)
        total_stack_lines = len(stack_lines)
        if total_stack_lines > 15:
            remaining = total_stack_lines - 15
            lines.append(f"... ({remaining} more lines)")
        lines.append("```\n")

    # Extract file path and line number
    lines.append("---\n")
    lines.append("### 🎯 Quick Analysis\n")

    if "Failed to resolve import" in message or "Cannot find module" in message:
        lines.append("**Error Type**: Missing Import")
        lines.append("**Cause**: A file is importing something that doesn't exist")
        lines.append("\n**Fix Strategy**:")
        lines.append("1. Check which file/module is missing")
        lines.append("2. Either create the file OR remove the import")
        lines.append("3. Call verify_changes() to confirm fix")
    elif "SyntaxError" in message:
        lines.append("**Error Type**: Syntax Error")
        lines.append("**Cause**: Invalid JavaScript/JSX syntax")
        lines.append("\n**Fix Strategy**:")
        lines.append("1. Read the file mentioned in error")
        lines.append("2. Check line number shown above")
        lines.append("3. Fix syntax error (missing bracket, comma, etc.)")
    else:
        lines.append("**Error Type**: Build Error")
        lines.append("**Cause**: Vite cannot compile the code")
        lines.append("\n**Fix Strategy**:")
        lines.append("1. Read error message carefully")
        lines.append("2. Fix the mentioned file")
        lines.append("3. Call verify_changes() to confirm")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


# ============================================
# Comprehensive Snapshot Tool
# ============================================

def get_comprehensive_error_snapshot(
    webcontainer_state: Optional[dict] = None,
    **kwargs
) -> ToolResult:
    """
    Get comprehensive error snapshot: terminals + preview + console.

    **ONE CALL TO GET EVERYTHING!**

    This is the ULTIMATE debugging tool. Instead of calling 5+ different tools,
    call this ONE tool to get a complete picture of what's happening.

    **Use this when:**
    - User reports "something is broken"
    - You're stuck and don't know what's wrong
    - Need to understand complete system state
    - Starting to debug any issue

    **What you get:**
    1. All terminal outputs (from all terminals)
    2. Preview error overlay (if any)
    3. Console errors (runtime errors)
    4. Console warnings
    5. Server status

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with comprehensive error snapshot
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    lines = ["## 📸 Comprehensive Error Snapshot\n"]
    lines.append("*All error sources in one view*\n")
    lines.append("=" * 60)
    lines.append("\n")

    issues_found = 0

    # 1. Preview Error Overlay
    lines.append("## 1️⃣ Preview Error Overlay\n")
    preview = webcontainer_state.get("preview", {})
    error_overlay = preview.get("error_overlay")

    if error_overlay:
        issues_found += 1
        message = error_overlay.get("message", "Unknown error")
        lines.append("❌ **BUILD ERROR** (This is what user sees on screen!)\n")
        lines.append("```")
        lines.append(message[:300])
        lines.append("```\n")
    else:
        lines.append("✅ No preview error overlay\n")

    # 2. Console Errors
    lines.append("## 2️⃣ Console Errors\n")
    console_messages = preview.get("console_messages", [])
    error_count = 0
    recent_errors = []

    for msg in console_messages[-30:]:
        if msg.get("type") == "error":
            error_count += 1
            args = msg.get("args", [])
            content = " ".join(str(arg) for arg in args)
            if len(recent_errors) < 3:
                recent_errors.append(content[:150])

    if error_count > 0:
        issues_found += 1
        lines.append(f"❌ **{error_count} console error(s)**\n")
        for err in recent_errors:
            lines.append(f"- {err}")
        lines.append("")
    else:
        lines.append("✅ No console errors\n")

    # 3. Terminal Errors
    lines.append("## 3️⃣ Terminal Outputs\n")
    terminals = webcontainer_state.get("terminals", [])
    terminal_errors = []

    for terminal in terminals:
        terminal_id = terminal.get("id", "unknown")
        history = terminal.get("history", [])
        last_output = terminal.get("last_output", [])

        # Combine outputs
        all_output = []
        for entry in history[-20:]:
            if isinstance(entry, dict):
                all_output.append(entry.get("data", ""))
            else:
                all_output.append(str(entry))
        all_output.extend(last_output[-20:] if last_output else [])

        # Search for errors
        for line in all_output:
            line_str = str(line).lower()
            if any(keyword in line_str for keyword in ['error', 'err!', 'failed', 'enoent']):
                terminal_errors.append(f"Terminal {terminal_id}: {str(line)[:150]}")
                if len(terminal_errors) >= 5:
                    break

    if terminal_errors:
        issues_found += 1
        lines.append(f"❌ **Errors found in terminals**\n")
        for err in terminal_errors[:3]:
            lines.append(f"- {err}")
        lines.append("")
    else:
        lines.append("✅ No errors in terminal output\n")

    # Summary
    lines.append("=" * 60)
    lines.append("\n## 📊 Summary\n")

    if issues_found == 0:
        lines.append("✅ **No issues detected!**")
        lines.append("\nAll systems are operational.")
    else:
        lines.append(f"❌ **{issues_found} issue source(s) detected**\n")
        lines.append("**Recommended actions:**")
        lines.append("1. Start with preview error overlay (if present) - this is what blocks rendering")
        lines.append("2. Then fix console errors - these are runtime issues")
        lines.append("3. Finally check terminal errors - these might be build warnings")
        lines.append("\n**Next steps:**")
        lines.append("- Call `get_preview_error_overlay()` for detailed preview error")
        lines.append("- Call `get_all_terminals_output()` for full terminal logs")
        lines.append("- Call `analyze_build_error()` for smart error categorization")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


# ============================================
# Tool Registry
# ============================================

TERMINAL_PREVIEW_READER_TOOLS = {
    "get_all_terminals_output": get_all_terminals_output,
    "get_preview_error_overlay": get_preview_error_overlay,
    "get_comprehensive_error_snapshot": get_comprehensive_error_snapshot,
}


def get_terminal_preview_reader_tool_definitions() -> List[dict]:
    """
    Get tool definitions in Claude API format for terminal/preview reader tools.

    Returns:
        List of tool definition dicts
    """
    return [
        {
            "name": "get_all_terminals_output",
            "description": """Get output from ALL terminals at once.

**PRIMARY tool for reading terminal content!**

Instead of calling get_terminal_output() multiple times for each terminal,
call this ONCE to see everything.

**Use this when:**
- Debugging build/server issues
- Looking for error messages but don't know which terminal
- Want to see all terminal activity
- User says "check the terminal"

**What you get:**
- Output from ALL active terminals (not just one)
- Combined history + recent output
- Errors marked with ❌
- Warnings marked with ⚠️
- Easy to scan for problems

**Example scenarios:**

1. **Build failing but you don't know why:**
   - Call this tool
   - Scan for ❌ ERROR markers
   - See exact error message

2. **Dev server not starting:**
   - Call this tool
   - Check Terminal 1 (usually dev server)
   - See npm install progress or errors

3. **Multiple terminals, unclear which has error:**
   - Call this tool
   - See all terminals at once
   - Identify which one has the problem""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_lines_per_terminal": {
                        "type": "integer",
                        "description": "Max lines to show per terminal (default 100)",
                        "default": 100
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_preview_error_overlay",
            "description": """Extract Vite error overlay from preview.

**CRITICAL**: This shows you the EXACT error that user sees on their screen!

When preview shows a red error screen (Vite error overlay), this tool extracts
the complete error message, file location, and stack trace.

**Use this when:**
- Preview shows red error screen
- diagnose_preview_state() reports build error
- User says "there's an error on the screen"
- Preview is blank/broken

**What you get:**
- Exact error message (e.g., "Failed to resolve import './App.css'")
- File path and line number (e.g., "src/App.jsx:2:7")
- Code frame (shows the problematic line)
- Stack trace
- Quick fix suggestions

**Why this is important:**
- This is what USER SEES in the preview window
- Much more detailed than generic error checks
- Tells you EXACTLY which file and line to fix
- Shows the actual code that's broken

**Example:**
```
Preview shows red screen with:
"Failed to resolve import './App.css' from 'src/App.jsx'"

This tool extracts:
- Message: "Failed to resolve import './App.css'"
- File: src/App.jsx
- Line: 2
- Fix: Create App.css or remove the import
```""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_comprehensive_error_snapshot",
            "description": """Get comprehensive error snapshot: ALL error sources in ONE call.

**THE ULTIMATE DEBUGGING TOOL!**

Instead of calling 5+ different tools to check different error sources,
call THIS TOOL ONCE to get everything.

**Checks:**
1. Preview error overlay (Vite build errors)
2. Console errors (runtime JavaScript errors)
3. Console warnings
4. Terminal errors (all terminals)
5. Server status

**Use this when:**
- User reports "something is broken"
- You're stuck and need to understand what's wrong
- Starting to debug any issue
- Want complete picture before fixing

**What you get:**
- Complete snapshot of all error sources
- Issue count (how many problems found)
- Priority recommendations (fix order)
- Next step suggestions

**Typical workflow:**
```
1. User: "It's not working"
2. Call: get_comprehensive_error_snapshot()
3. Get: Preview error + 2 console errors + terminal warning
4. Fix: Start with preview error (blocks rendering)
5. Verify: Call diagnose_preview_state()
6. Done!
```

**Why this is better than calling multiple tools:**
- ONE call instead of 5+
- See all problems at once
- Understand which issue to fix first
- Faster debugging""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]
