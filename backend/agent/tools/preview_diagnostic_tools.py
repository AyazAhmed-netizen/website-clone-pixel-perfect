"""
Preview Diagnostic Tools for Nexting Agent

Provides comprehensive preview state diagnosis including visual inspection,
error detection, and actionable recommendations.

Tools:
1. diagnose_preview_state() - Complete preview diagnosis with screenshot + errors
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
# Preview Diagnostic Tool
# ============================================

def diagnose_preview_state(
    webcontainer_state: Optional[dict] = None,
    **kwargs
) -> ToolResult:
    """
    Comprehensive preview state diagnosis.

    This tool combines multiple checks into a single comprehensive diagnosis:
    1. Preview server status (running/loading/error)
    2. Build errors from Vite (error_overlay)
    3. Console errors and warnings
    4. Visual inspection via screenshot (tells you what user actually sees)
    5. Actionable recommendations

    **Use this instead of repeatedly calling get_preview_status()!**

    **When to use:**
    - After starting dev server to check if it loaded correctly
    - When preview seems broken (white screen, errors)
    - Before telling user "preview is ready" - verify it ACTUALLY looks good
    - When stuck in a loop checking preview status

    **What you get:**
    - ✅/❌ Status of each check
    - Visual description of what's rendered (or if it's blank)
    - Specific errors with file names and line numbers
    - Priority-ordered fix recommendations

    Args:
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with comprehensive preview diagnosis
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    lines = ["## 🔍 Preview State Diagnosis\n"]

    issues = []
    warnings = []
    info = []

    # 1. Check basic preview status
    preview = webcontainer_state.get("preview", {})
    preview_url = preview.get("url")
    is_loading = preview.get("is_loading", False)
    has_error = preview.get("has_error", False)
    error_message = preview.get("error_message", "")

    lines.append("### 1️⃣ Server Status\n")

    if not preview_url:
        lines.append("❌ **Preview server not started**")
        issues.append({
            "severity": "HIGH",
            "category": "SERVER_NOT_STARTED",
            "message": "Dev server hasn't been started yet",
            "fix": "Call start_dev_server() to start it"
        })
    elif is_loading:
        lines.append("🔄 **Preview is loading...**")
        info.append("Server is booting up, may take 10-30 seconds")
    elif has_error:
        lines.append(f"❌ **Preview has error**: {error_message}")
        issues.append({
            "severity": "HIGH",
            "category": "PREVIEW_ERROR",
            "message": error_message,
            "fix": "Check terminal output and console messages for details"
        })
    else:
        lines.append(f"✅ **Server running**: {preview_url}")

    lines.append("")

    # 2. Check for Vite build errors (error_overlay)
    lines.append("### 2️⃣ Build Status (Vite)\n")

    error_overlay = preview.get("error_overlay")
    if error_overlay:
        overlay_msg = error_overlay.get("message", "Unknown error")
        overlay_stack = error_overlay.get("stack", "")
        overlay_plugin = error_overlay.get("plugin", "")
        overlay_file = error_overlay.get("file", "")
        overlay_line = error_overlay.get("line")
        overlay_column = error_overlay.get("column")
        overlay_frame = error_overlay.get("frame", "")

        lines.append(f"❌ **BUILD ERROR**")
        if overlay_plugin:
            lines.append(f"**Plugin:** `{overlay_plugin}`")
        if overlay_file:
            location = f"{overlay_file}"
            if overlay_line:
                location += f":{overlay_line}"
                if overlay_column:
                    location += f":{overlay_column}"
            lines.append(f"**File:** `{location}`")

        lines.append("")
        lines.append("**Error Message:**")
        lines.append(f"```")
        # Truncate very long messages
        lines.append(overlay_msg[:1500] if len(overlay_msg) > 1500 else overlay_msg)
        lines.append(f"```")

        # Show code frame if available (most helpful for fixing)
        if overlay_frame:
            lines.append("")
            lines.append("**Code Frame:**")
            lines.append("```jsx")
            lines.append(overlay_frame)
            lines.append("```")

        if overlay_stack:
            lines.append("")
            lines.append("**Stack Trace (first 5 lines):**")
            lines.append("```")
            stack_lines = overlay_stack.split("\n")[:5]
            for line in stack_lines:
                if line.strip():
                    lines.append(line)
            lines.append("```")

        lines.append("")

        # Use extracted file from overlay if available
        affected_file = overlay_file
        if not affected_file and "Failed to resolve import" in overlay_msg:
            # Fallback: Extract imported module name
            import re
            match = re.search(r'import ["\']([^"\']+)["\']', overlay_msg)
            if match:
                affected_file = match.group(1)

        issues.append({
            "severity": "CRITICAL",
            "category": "BUILD_ERROR",
            "message": overlay_msg[:200],
            "affected_file": affected_file,
            "line": overlay_line,
            "column": overlay_column,
            "fix": f"Fix the error in {affected_file or 'the affected file'}. This is blocking the preview."
        })
    else:
        lines.append("✅ **No build errors**\n")

    # 3. Check console messages
    lines.append("### 3️⃣ Console Messages\n")

    console_messages = preview.get("console_messages", [])

    error_count = 0
    warn_count = 0
    recent_errors = []
    recent_warnings = []

    for msg in console_messages[-30:]:  # Check last 30 messages
        msg_type = msg.get("type", "log")
        args = msg.get("args", [])
        content = " ".join(str(arg) for arg in args)

        if msg_type == "error":
            error_count += 1
            if len(recent_errors) < 3:
                recent_errors.append(content[:150])
        elif msg_type == "warning":
            warn_count += 1
            if len(recent_warnings) < 2:
                recent_warnings.append(content[:150])

    if error_count > 0:
        lines.append(f"❌ **{error_count} console error(s)**")
        for err in recent_errors:
            lines.append(f"  - {err}")
        lines.append("")

        issues.append({
            "severity": "HIGH",
            "category": "CONSOLE_ERROR",
            "message": f"{error_count} runtime errors in console",
            "fix": "Check the errors above and fix the underlying issues"
        })
    else:
        lines.append(f"✅ **No console errors**")

    if warn_count > 0:
        lines.append(f"⚠️  **{warn_count} console warning(s)**")
        for warn in recent_warnings:
            lines.append(f"  - {warn}")
        warnings.append(f"{warn_count} console warnings (non-blocking)")
    else:
        lines.append(f"✅ **No console warnings**")

    lines.append("")

    # 4. Visual state analysis
    lines.append("### 4️⃣ Visual State\n")

    # Check if we have screenshot action available
    lines.append("**Recommendation**: Call `take_screenshot()` to see what's actually rendered.")
    lines.append("This is CRITICAL - you need to verify the visual appearance, not just check status!")
    lines.append("")

    info.append("After fixing errors, take screenshot to verify visual appearance")

    # 5. Terminal status
    terminals = webcontainer_state.get("terminals", [])
    lines.append("### 5️⃣ Terminal Status\n")

    if terminals:
        lines.append(f"**Active terminals**: {len(terminals)}")
        for terminal in terminals:
            terminal_id = terminal.get("id", "unknown")
            is_running = terminal.get("is_running", False)
            status = "🟢 Running" if is_running else "⚪ Idle"
            lines.append(f"  - Terminal {terminal_id}: {status}")
    else:
        lines.append("No active terminals")

    lines.append("")

    # 6. Build actionable recommendations
    lines.append("---\n")
    lines.append("## 🎯 Action Plan\n")

    if not issues:
        lines.append("✅ **All checks passed!**\n")
        lines.append("**Next steps:**")
        lines.append("1. Call `take_screenshot()` to verify visual appearance")
        lines.append("2. If screenshot looks good, task is complete!")
        lines.append("3. If screenshot is blank or wrong, investigate further")
    else:
        # Sort by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        issues.sort(key=lambda x: severity_order.get(x["severity"], 99))

        lines.append(f"**Found {len(issues)} issue(s) - Priority order:**\n")

        for i, issue in enumerate(issues, 1):
            lines.append(f"{i}. **[{issue['severity']}] {issue['category']}**")
            lines.append(f"   - {issue['message']}")
            if issue.get("affected_file"):
                lines.append(f"   - Affected: `{issue['affected_file']}`")
            lines.append(f"   - **Fix**: {issue['fix']}")
            lines.append("")

        lines.append("**Recommended workflow:**")
        lines.append("1. Fix the CRITICAL/HIGH issues above (in order)")
        lines.append("2. Call `verify_changes()` after each fix")
        lines.append("3. Call `diagnose_preview_state()` again to re-check")
        lines.append("4. Once all issues resolved, take screenshot to verify")

    if warnings:
        lines.append(f"\n⚠️  **Warnings (non-blocking):**")
        for warn in warnings:
            lines.append(f"- {warn}")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


# ============================================
# Tool Registry
# ============================================

PREVIEW_DIAGNOSTIC_TOOLS = {
    "diagnose_preview_state": diagnose_preview_state,
}


def get_preview_diagnostic_tool_definitions() -> List[dict]:
    """
    Get tool definitions in Claude API format for preview diagnostic tools.

    Returns:
        List of tool definition dicts
    """
    return [
        {
            "name": "diagnose_preview_state",
            "description": """Comprehensive preview diagnosis - the BEST tool to check preview state.

**CRITICAL**: Use this INSTEAD of repeatedly calling get_preview_status()!

**Why this tool is better:**
- Combines server status + build errors + console errors + visual analysis
- Tells you EXACTLY what's wrong with specific fix recommendations
- Reminds you to take screenshot to see actual visual state
- Provides priority-ordered action plan
- One call instead of 5+ separate tool calls

**Use this tool when:**
- After calling start_dev_server() - check if it worked
- Preview seems broken (white screen, not loading, errors)
- Before telling user "preview is ready" - verify it ACTUALLY works
- You're stuck calling get_preview_status() multiple times

**What you get back:**
1. ✅/❌ Server Status - is it running?
2. ✅/❌ Build Status - any Vite compilation errors?
3. ✅/❌ Console Status - any runtime errors?
4. 🎯 Visual State - reminder to take screenshot
5. 📋 Action Plan - exactly what to do next

**Typical workflow:**
```
1. start_dev_server()
2. diagnose_preview_state() → Check if started correctly
3. If errors found → fix them → verify_changes()
4. diagnose_preview_state() → Re-check
5. If all clear → take_screenshot() → Verify visual appearance
6. Done!
```

**Common scenarios:**

**Scenario 1: White screen**
- diagnose_preview_state() will show you:
  - If there's a build error blocking render
  - If there are console errors
  - Remind you to take screenshot to see what's rendered

**Scenario 2: Stuck waiting**
- Instead of calling get_preview_status() 10 times
- Call diagnose_preview_state() ONCE
- It tells you if server is loading, errored, or ready
- Gives you actionable next steps

**Scenario 3: Preview "ready" but broken**
- diagnose_preview_state() checks console errors
- Reminds you to take screenshot to verify
- Catches issues that status check misses""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]
