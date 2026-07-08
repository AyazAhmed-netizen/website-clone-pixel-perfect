"""
Self-Healing Tools for Nexting Agent

Provides automatic error detection, diagnosis, and fix suggestions.
Implements Bolt.new-style self-healing loop capabilities.

Tools:
1. start_healing_loop() - Start automatic healing loop
2. verify_healing_progress() - Check healing progress and get next fix
3. stop_healing_loop() - Stop healing loop
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field
import hashlib
import time
import logging
import re

from .error_handling_tools import (
    ToolResult,
    categorize_error,
    extract_error_context,
    get_fix_priority,
    generate_fix_command,
    ERROR_PRIORITY_ORDER,
)

logger = logging.getLogger(__name__)


# ============================================
# Data Structures
# ============================================

@dataclass
class FixAttempt:
    """Record of a fix attempt"""
    error_hash: str
    category: str
    fix_strategy: str
    files_modified: List[str]
    timestamp: float
    success: bool
    result_message: str


@dataclass
class HealingState:
    """Self-healing loop state"""
    is_healing: bool = False
    current_error: Optional[Dict] = None
    fix_attempts: List[FixAttempt] = field(default_factory=list)
    max_attempts: int = 5
    attempt_count: int = 0
    started_at: float = 0.0
    last_error_hash: str = ""


# Global healing states per session
_healing_states: Dict[str, HealingState] = {}


# ============================================
# Helper Functions
# ============================================

def _hash_error(error: Dict) -> str:
    """Generate a hash for an error for deduplication"""
    key = f"{error.get('category', '')}:{error.get('message', '')[:100]}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _collect_all_errors(webcontainer_state: Dict) -> List[Dict]:
    """
    Collect all errors from all sources in WebContainer state.

    Sources:
    - Terminal output
    - Preview error overlay
    - Console messages

    Returns:
        List of error dictionaries with category, severity, message, etc.
    """
    errors = []

    if not webcontainer_state:
        return errors

    # 1. Check preview error overlay (highest priority)
    preview = webcontainer_state.get("preview", {})
    error_overlay = preview.get("error_overlay")

    if error_overlay:
        message = error_overlay.get("message", "Unknown error")
        pattern_info, match = categorize_error(message)

        errors.append({
            "source": "preview",
            "category": pattern_info["category"] if pattern_info else "BUILD_FAILED",
            "severity": "CRITICAL",
            "message": message[:500],
            "affected_file": error_overlay.get("file"),
            "line": error_overlay.get("line"),
            "column": error_overlay.get("column"),
            "stack": error_overlay.get("stack"),
            "plugin": error_overlay.get("plugin"),
            "frame": error_overlay.get("frame"),
            "fix_strategy": pattern_info["fix_strategy"] if pattern_info else [
                "1. Check the error message for details",
                "2. Fix the affected file",
                "3. Verify with verify_changes()",
            ],
        })

    # 2. Check console errors
    console_messages = preview.get("console_messages", [])
    seen_errors = set()

    for msg in console_messages[-30:]:
        msg_type = msg.get("type", "log")
        if msg_type not in ["error"]:
            continue

        args = msg.get("args", [])
        content = " ".join(str(arg) for arg in args)[:500]

        # Skip duplicate messages
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        if content_hash in seen_errors:
            continue
        seen_errors.add(content_hash)

        # Skip React development warnings (noise)
        if "Warning:" in content or "DevTools" in content:
            continue

        pattern_info, match = categorize_error(content)

        errors.append({
            "source": "console",
            "category": pattern_info["category"] if pattern_info else "RUNTIME_ERROR",
            "severity": pattern_info["severity"] if pattern_info else "HIGH",
            "message": content,
            "affected_file": None,
            "fix_strategy": pattern_info["fix_strategy"] if pattern_info else [
                "1. Check the console error details",
                "2. Trace the error to its source",
                "3. Fix the underlying issue",
            ],
        })

    # 3. Check terminal output for errors
    terminals = webcontainer_state.get("terminals", [])
    for terminal in terminals:
        history = terminal.get("history", [])
        last_output = terminal.get("last_output", [])

        # Combine outputs
        all_output = []
        for entry in history[-20:]:
            if isinstance(entry, dict):
                all_output.append(entry.get("data", ""))
            else:
                all_output.append(str(entry))
        all_output.extend(last_output[-10:] if last_output else [])

        output_text = "\n".join(all_output)

        # Look for error patterns in terminal
        pattern_info, match = categorize_error(output_text)
        if pattern_info and pattern_info["severity"] in ["HIGH", "CRITICAL"]:
            context = extract_error_context(output_text, max_lines=3)

            errors.append({
                "source": "terminal",
                "category": pattern_info["category"],
                "severity": pattern_info["severity"],
                "message": "\n".join(context)[:500],
                "affected_file": None,
                "fix_strategy": pattern_info["fix_strategy"],
            })

    return errors


def _deduplicate_errors(errors: List[Dict]) -> List[Dict]:
    """Remove duplicate errors based on hash"""
    seen = set()
    unique = []

    for error in errors:
        error_hash = _hash_error(error)
        if error_hash not in seen:
            seen.add(error_hash)
            error["hash"] = error_hash
            unique.append(error)

    return unique


# ============================================
# Self-Healing Tools
# ============================================

def start_healing_loop(
    session_id: str = "default",
    max_attempts: int = 5,
    webcontainer_state: Optional[Dict] = None,
    **kwargs
) -> ToolResult:
    """
    Start self-healing loop for automatic error fixing.

    The loop:
    1. Detect errors
    2. Prioritize by severity
    3. Generate fix suggestion
    4. Return to Agent for fix execution
    5. Agent calls verify_healing_progress() after fix

    Args:
        session_id: Session identifier for tracking state
        max_attempts: Maximum fix attempts before stopping
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with first error to fix and suggested command
    """
    global _healing_states

    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    # Initialize or get healing state
    if session_id not in _healing_states:
        _healing_states[session_id] = HealingState()

    state = _healing_states[session_id]

    if state.is_healing:
        return ToolResult(
            success=False,
            result=f"⚠️ Healing loop already in progress.\n\nAttempt {state.attempt_count}/{state.max_attempts}\n\nCall `verify_healing_progress()` to continue or `stop_healing_loop()` to abort."
        )

    # Collect errors
    errors = _collect_all_errors(webcontainer_state)
    errors = _deduplicate_errors(errors)

    if not errors:
        return ToolResult(
            success=True,
            result="## 🎉 Healing Loop\n\n✅ **No errors to fix.** System is already healthy!\n\nCall `take_screenshot()` to verify visual appearance."
        )

    # Sort by priority
    prioritized = get_fix_priority(errors)
    first_error = prioritized[0]

    # Start healing mode
    state.is_healing = True
    state.attempt_count = 0
    state.max_attempts = max_attempts
    state.current_error = first_error
    state.started_at = time.time()
    state.last_error_hash = first_error.get("hash", "")

    # Build response
    lines = ["## 🔧 Self-Healing Loop Started\n"]
    lines.append(f"**Total Errors**: {len(prioritized)}")
    lines.append(f"**Max Attempts**: {max_attempts}")
    lines.append(f"**Started**: Now\n")
    lines.append("---\n")

    # First error to fix
    severity_icon = "🔴" if first_error["severity"] == "CRITICAL" else "🟠"
    lines.append(f"### {severity_icon} Target: {first_error['category'].replace('_', ' ')}")

    if first_error.get("affected_file"):
        lines.append(f"**File**: `{first_error['affected_file']}`")

    lines.append(f"\n**Message**:")
    lines.append("```")
    lines.append(first_error["message"][:300])
    lines.append("```\n")

    # Fix suggestion
    fix_cmd = generate_fix_command(first_error, webcontainer_state)
    if fix_cmd:
        lines.append("**Apply this fix**:")
        lines.append("```")
        lines.append(fix_cmd)
        lines.append("```\n")
    else:
        lines.append("**Fix Strategy**:")
        for step in first_error.get("fix_strategy", [])[:3]:
            lines.append(f"  {step}")
        lines.append("")

    lines.append("---\n")
    lines.append("**Next**: After applying the fix, call `verify_healing_progress()` to check result.")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


def verify_healing_progress(
    session_id: str = "default",
    webcontainer_state: Optional[Dict] = None,
    **kwargs
) -> ToolResult:
    """
    Verify if the last fix attempt succeeded.

    - If no errors: Mark healing complete ✅
    - If still errors: Increment counter, suggest next fix
    - If max attempts reached: Stop and report failure

    Args:
        session_id: Session identifier
        webcontainer_state: Current WebContainer state

    Returns:
        ToolResult with healing status and next action
    """
    global _healing_states

    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    state = _healing_states.get(session_id)
    if not state or not state.is_healing:
        return ToolResult(
            success=True,
            result="ℹ️ No active healing loop.\n\nCall `start_healing_loop()` to begin automatic error fixing."
        )

    state.attempt_count += 1

    # Collect current errors
    errors = _collect_all_errors(webcontainer_state)
    errors = _deduplicate_errors(errors)

    if not errors:
        # Success!
        elapsed = time.time() - state.started_at
        attempts_used = state.attempt_count
        state.is_healing = False

        return ToolResult(
            success=True,
            result=f"""## 🎉 Healing Complete!

✅ **All errors have been resolved.**

**Stats**:
- Attempts used: {attempts_used}/{state.max_attempts}
- Time elapsed: {elapsed:.1f}s

**Next step**: Call `take_screenshot()` to verify the visual appearance."""
        )

    if state.attempt_count >= state.max_attempts:
        # Max attempts reached
        state.is_healing = False

        return ToolResult(
            success=False,
            result=f"""## ❌ Healing Failed

**Attempts**: {state.attempt_count}/{state.max_attempts} exhausted

**Remaining errors**: {len(errors)}

The self-healing loop could not resolve all errors automatically.

**Manual intervention required**:
1. Call `diagnose_preview_state()` for detailed error analysis
2. Fix errors manually based on the suggestions
3. Call `verify_changes()` after each fix"""
        )

    # Continue with next error
    prioritized = get_fix_priority(errors)
    next_error = prioritized[0]
    state.current_error = next_error

    # Check if we're stuck on the same error
    next_hash = next_error.get("hash", "")
    is_same_error = next_hash == state.last_error_hash
    state.last_error_hash = next_hash

    lines = [f"## 🔄 Healing Progress: Attempt {state.attempt_count}/{state.max_attempts}\n"]

    if is_same_error:
        lines.append("⚠️ **Same error persists** - previous fix may not have worked.\n")
    else:
        lines.append("✅ **Previous error resolved!** Moving to next error.\n")

    lines.append(f"**Remaining Errors**: {len(errors)}")
    lines.append("---\n")

    # Next error to fix
    severity_icon = "🔴" if next_error["severity"] == "CRITICAL" else "🟠"
    lines.append(f"### {severity_icon} Next Target: {next_error['category'].replace('_', ' ')}")

    if next_error.get("affected_file"):
        lines.append(f"**File**: `{next_error['affected_file']}`")

    lines.append(f"\n**Message**:")
    lines.append("```")
    lines.append(next_error["message"][:300])
    lines.append("```\n")

    # Fix suggestion
    fix_cmd = generate_fix_command(next_error, webcontainer_state)
    if fix_cmd:
        lines.append("**Apply this fix**:")
        lines.append("```")
        lines.append(fix_cmd)
        lines.append("```\n")
    else:
        lines.append("**Fix Strategy**:")
        for step in next_error.get("fix_strategy", [])[:3]:
            lines.append(f"  {step}")
        lines.append("")

    lines.append("---\n")
    lines.append("**Next**: Apply the fix, then call `verify_healing_progress()` again.")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


def stop_healing_loop(
    session_id: str = "default",
    **kwargs
) -> ToolResult:
    """
    Stop the current healing loop.

    Args:
        session_id: Session identifier

    Returns:
        ToolResult confirming stop
    """
    global _healing_states

    if session_id in _healing_states:
        state = _healing_states[session_id]
        was_healing = state.is_healing
        attempts = state.attempt_count
        state.is_healing = False

        if was_healing:
            return ToolResult(
                success=True,
                result=f"🛑 Healing loop stopped.\n\n**Attempts made**: {attempts}/{state.max_attempts}\n\nYou can restart with `start_healing_loop()` or fix errors manually."
            )

    return ToolResult(
        success=True,
        result="ℹ️ No active healing loop to stop."
    )


def get_healing_status(
    session_id: str = "default",
    **kwargs
) -> ToolResult:
    """
    Get current healing loop status.

    Args:
        session_id: Session identifier

    Returns:
        ToolResult with current status
    """
    global _healing_states

    if session_id not in _healing_states:
        return ToolResult(
            success=True,
            result="ℹ️ No healing session found. Call `start_healing_loop()` to begin."
        )

    state = _healing_states[session_id]

    if not state.is_healing:
        return ToolResult(
            success=True,
            result=f"ℹ️ Healing loop is **inactive**.\n\nLast session: {state.attempt_count} attempts made."
        )

    elapsed = time.time() - state.started_at
    current_category = state.current_error.get("category", "Unknown") if state.current_error else "None"

    return ToolResult(
        success=True,
        result=f"""## 🔧 Healing Loop Status

**Status**: 🟢 Active
**Attempt**: {state.attempt_count}/{state.max_attempts}
**Elapsed**: {elapsed:.1f}s
**Current Target**: {current_category}

Call `verify_healing_progress()` to continue or `stop_healing_loop()` to abort."""
    )


# ============================================
# Tool Registry
# ============================================

SELF_HEALING_TOOLS = {
    "start_healing_loop": start_healing_loop,
    "verify_healing_progress": verify_healing_progress,
    "stop_healing_loop": stop_healing_loop,
    "get_healing_status": get_healing_status,
}


def get_self_healing_tool_definitions() -> List[dict]:
    """
    Get tool definitions in Claude API format for self-healing tools.

    Returns:
        List of tool definition dicts
    """
    return [
        {
            "name": "start_healing_loop",
            "description": """Start automatic self-healing loop to fix errors.

**Use for automated error fixing!**

The healing loop:
1. Detects all errors
2. Prioritizes by severity
3. Suggests fix for highest priority error
4. You apply the fix
5. Call verify_healing_progress() to check and continue
6. Repeats until all fixed or max attempts reached

**When to use:**
- Multiple errors to fix
- Want automated guidance through fixes
- Preview is broken and needs systematic repair

**Example workflow:**
```
start_healing_loop()
→ Target: MISSING_IMPORT
  Fix: write_file(...)

write_file(...)  # Apply fix

verify_healing_progress()
→ ✅ Previous error resolved! Next: SYNTAX_ERROR
  Fix: edit_file(...)

edit_file(...)  # Apply fix

verify_healing_progress()
→ 🎉 Healing Complete! All errors resolved.
```

**Max 5 attempts** by default to prevent infinite loops.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_attempts": {
                        "type": "integer",
                        "description": "Maximum fix attempts (default: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": []
            }
        },
        {
            "name": "verify_healing_progress",
            "description": """Check healing progress and get next fix suggestion.

**Call this after applying each fix in the healing loop.**

Returns:
- ✅ All fixed → Healing complete!
- 🔄 More errors → Suggests next fix
- ❌ Max attempts → Stops and reports failure

**Always call this after applying a fix** during healing loop.""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "stop_healing_loop",
            "description": """Stop the current healing loop.

Use when:
- You want to fix errors manually
- The loop is stuck
- You need to abort healing""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_healing_status",
            "description": """Get current healing loop status.

Shows:
- Whether healing is active
- Current attempt count
- Current target error
- Elapsed time""",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]
