"""
Error Handling & Self-Healing Tools for Nexting Agent

Provides intelligent error analysis, categorization, and self-healing guidance.
These tools help the Agent understand and fix errors more effectively.

Tools:
1. analyze_build_error() - Analyze build/runtime errors with smart categorization
2. suggest_error_fix() - Get AI-powered fix suggestions for specific errors
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict, Tuple
from dataclasses import dataclass
import os
import logging
import re

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
# Error Pattern Definitions
# ============================================

# Error patterns with category, severity, and fix hints
ERROR_PATTERNS = [
    # Import/Module Errors
    {
        "pattern": r"Cannot find module ['\"]([^'\"]+)['\"]",
        "category": "MISSING_IMPORT",
        "severity": "HIGH",
        "extract_file": lambda m: m.group(1),
        "description": "Missing module or import path",
        "fix_strategy": [
            "1. Check if the imported file exists using file_exists()",
            "2. If file doesn't exist:",
            "   - Create it with write_file() if it's a component you need, OR",
            "   - Remove/replace the import with edit_file()",
            "3. If it's a package:",
            "   - Install it with install_dependencies(['package-name'])",
        ]
    },
    {
        "pattern": r"Module not found: Error: Can't resolve ['\"]([^'\"]+)['\"]",
        "category": "MISSING_IMPORT",
        "severity": "HIGH",
        "extract_file": lambda m: m.group(1),
        "description": "Webpack/Vite can't resolve module",
        "fix_strategy": [
            "1. Check if the imported file exists",
            "2. Verify the import path is correct (relative vs absolute)",
            "3. For npm packages, check if installed in package.json",
        ]
    },

    # CSS/Asset Errors
    {
        "pattern": r"Failed to resolve import ['\"]([^'\"]+\.css)['\"]",
        "category": "MISSING_CSS",
        "severity": "MEDIUM",
        "extract_file": lambda m: m.group(1),
        "description": "Missing CSS file",
        "fix_strategy": [
            "1. Create the missing CSS file:",
            "   write_file('src/path/to/file.css', '/* Styles */')",
            "2. Or remove the import if CSS is not needed",
        ]
    },

    # Syntax Errors
    {
        "pattern": r"SyntaxError: (.+)",
        "category": "SYNTAX_ERROR",
        "severity": "HIGH",
        "extract_file": lambda m: m.group(1),
        "description": "JavaScript/JSX syntax error",
        "fix_strategy": [
            "1. Read the file mentioned in the error",
            "2. Check for common issues:",
            "   - Missing semicolons or commas",
            "   - Unclosed brackets/parentheses",
            "   - Invalid JSX syntax",
            "3. Fix with edit_file()",
        ]
    },

    # React/JSX Errors
    {
        "pattern": r"React is not defined",
        "category": "MISSING_REACT_IMPORT",
        "severity": "MEDIUM",
        "extract_file": lambda m: None,
        "description": "Missing React import in JSX file",
        "fix_strategy": [
            "1. Add import to the top of the file:",
            "   edit_file(path, old_content, \"import React from 'react';\\n\" + old_content)",
            "Note: This is rare in React 17+ with new JSX transform",
        ]
    },
    {
        "pattern": r"(.+) is not defined",
        "category": "UNDEFINED_VARIABLE",
        "severity": "MEDIUM",
        "extract_file": lambda m: m.group(1),
        "description": "Undefined variable or function",
        "fix_strategy": [
            "1. Check if variable/function is imported",
            "2. Check if variable is declared before use",
            "3. Check spelling and case sensitivity",
        ]
    },

    # Type Errors
    {
        "pattern": r"TypeError: (.+)",
        "category": "TYPE_ERROR",
        "severity": "MEDIUM",
        "extract_file": lambda m: m.group(1),
        "description": "Type-related runtime error",
        "fix_strategy": [
            "1. Check the error message for which operation failed",
            "2. Verify data types match expected types",
            "3. Add null/undefined checks if needed",
        ]
    },

    # Build/Compilation Errors
    {
        "pattern": r"Failed to compile",
        "category": "BUILD_FAILED",
        "severity": "HIGH",
        "extract_file": lambda m: None,
        "description": "Vite/Webpack compilation failed",
        "fix_strategy": [
            "1. Read terminal output for specific error",
            "2. Fix the root cause error first",
            "3. Run verify_changes() to confirm fix",
        ]
    },

    # NPM/Package Errors
    {
        "pattern": r"npm ERR!",
        "category": "NPM_ERROR",
        "severity": "HIGH",
        "extract_file": lambda m: None,
        "description": "NPM installation or execution error",
        "fix_strategy": [
            "1. Check package.json for syntax errors",
            "2. Try clearing node_modules and reinstalling",
            "3. Check if package versions are compatible",
        ]
    },

    # Process Exit Errors
    {
        "pattern": r"Process exited with code (\d+)",
        "category": "PROCESS_EXIT",
        "severity": "HIGH",
        "extract_file": lambda m: None,
        "description": f"Process exited with non-zero exit code",
        "fix_strategy": [
            "1. Check terminal output for the specific error",
            "2. Common causes: missing dependencies, syntax errors, invalid config",
            "3. Run the command again after fixing the issue",
        ]
    },
    {
        "pattern": r"npm ERR! code E(\d+)",
        "category": "NPM_ERROR",
        "severity": "HIGH",
        "extract_file": lambda m: None,
        "description": "NPM error with error code",
        "fix_strategy": [
            "1. Clear node_modules: shell('rm -rf node_modules')",
            "2. Reinstall dependencies: install_dependencies()",
            "3. Check package.json for version conflicts",
        ]
    },
    {
        "pattern": r"ENOENT|EACCES|EPERM",
        "category": "FILESYSTEM_ERROR",
        "severity": "HIGH",
        "extract_file": lambda m: None,
        "description": "File system permission or missing file error",
        "fix_strategy": [
            "1. Check if the file/directory exists",
            "2. Verify file paths are correct",
            "3. Ensure proper permissions for file operations",
        ]
    },

    # White Screen Detection
    {
        "pattern": r"WHITE_SCREEN",
        "category": "WHITE_SCREEN",
        "severity": "CRITICAL",
        "extract_file": lambda m: None,
        "description": "Page loaded but no visible content rendered",
        "fix_strategy": [
            "1. Check if App/main component renders properly",
            "2. Verify ReactDOM.createRoot() or render() is called",
            "3. Check for silent errors in component lifecycle",
            "4. Take screenshot and analyze what's visible",
        ]
    },

    # Vite/Build Specific Errors
    {
        "pattern": r"\[plugin:vite:([^\]]+)\]",
        "category": "VITE_PLUGIN_ERROR",
        "severity": "HIGH",
        "extract_file": lambda m: m.group(1),
        "description": "Vite plugin compilation error",
        "fix_strategy": [
            "1. Check the file mentioned in the error",
            "2. Fix the syntax or import issue",
            "3. Verify JSX/TSX syntax is correct",
        ]
    },
    {
        "pattern": r"Unexpected token",
        "category": "SYNTAX_ERROR",
        "severity": "HIGH",
        "extract_file": lambda m: None,
        "description": "Unexpected token in JavaScript/JSX",
        "fix_strategy": [
            "1. Look for missing/extra brackets, parentheses, or braces",
            "2. Check for invalid JSX syntax (e.g., class vs className)",
            "3. Verify all strings are properly quoted",
        ]
    },
    {
        "pattern": r"Invalid hook call",
        "category": "REACT_HOOK_ERROR",
        "severity": "HIGH",
        "extract_file": lambda m: None,
        "description": "React hook called incorrectly",
        "fix_strategy": [
            "1. Ensure hooks are called at the top level of function components",
            "2. Don't call hooks inside loops, conditions, or nested functions",
            "3. Make sure you're using the same React version everywhere",
        ]
    },
]


# ============================================
# Error Priority and Fix Command Generation
# ============================================

# Priority order for fixing errors (lower = higher priority)
ERROR_PRIORITY_ORDER = {
    "BUILD_FAILED": 1,
    "VITE_PLUGIN_ERROR": 2,
    "MISSING_IMPORT": 3,
    "MISSING_CSS": 4,
    "SYNTAX_ERROR": 5,
    "REACT_HOOK_ERROR": 6,
    "TYPE_ERROR": 7,
    "UNDEFINED_VARIABLE": 8,
    "NPM_ERROR": 9,
    "PROCESS_EXIT": 10,
    "WHITE_SCREEN": 11,
    "FILESYSTEM_ERROR": 12,
    "MISSING_REACT_IMPORT": 13,
}


def get_fix_priority(errors: List[Dict]) -> List[Dict]:
    """
    Sort errors by fix priority.

    Fix order: BUILD_ERROR > VITE_PLUGIN > IMPORT > SYNTAX > TYPE > others

    Args:
        errors: List of error dictionaries with 'category' field

    Returns:
        Sorted list of errors (highest priority first)
    """
    return sorted(
        errors,
        key=lambda e: ERROR_PRIORITY_ORDER.get(e.get("category", "UNKNOWN"), 99)
    )


def get_related_files(error: Dict, webcontainer_state: Dict) -> List[str]:
    """
    Find files related to an error for context.

    Args:
        error: Error dictionary with affected_file and context
        webcontainer_state: Current WebContainer state with files

    Returns:
        List of related file paths
    """
    related = []
    affected_file = error.get("affected_file")
    files = webcontainer_state.get("files", {})

    if affected_file:
        # Add the affected file itself
        related.append(affected_file)

        # Try to find files that might import the affected file
        file_basename = affected_file.split("/")[-1].replace(".jsx", "").replace(".tsx", "").replace(".js", "").replace(".ts", "")
        for path in files.keys():
            if file_basename in path and path != affected_file:
                related.append(path)

    # Look for common entry points if no specific file
    if not related:
        for common_file in ["src/App.jsx", "src/App.tsx", "src/main.jsx", "src/main.tsx", "src/index.jsx", "src/index.tsx"]:
            if common_file in files:
                related.append(common_file)
                break

    return related[:5]  # Limit to 5 related files


def generate_fix_command(error: Dict, webcontainer_state: Dict) -> Optional[str]:
    """
    Generate an executable fix command for a specific error.

    Args:
        error: Error dictionary with category, affected_file, message
        webcontainer_state: Current WebContainer state

    Returns:
        String with suggested tool call(s) or None
    """
    category = error.get("category", "UNKNOWN")
    affected_file = error.get("affected_file")
    message = error.get("message", error.get("description", ""))

    if category == "MISSING_IMPORT":
        # Extract the missing module name
        match = re.search(r"['\"]([^'\"]+)['\"]", message)
        if match:
            missing_module = match.group(1)

            # Local file import
            if missing_module.startswith(".") or missing_module.startswith("/"):
                # Guess the full path
                if affected_file:
                    base_dir = "/".join(affected_file.split("/")[:-1])
                    full_path = f"{base_dir}/{missing_module.lstrip('./')}"
                    if not full_path.endswith(('.jsx', '.tsx', '.js', '.ts')):
                        full_path += ".jsx"
                else:
                    full_path = f"src/{missing_module.lstrip('./')}.jsx"

                return f"""# Option 1: Create the missing file
write_file(path="{full_path}", content=\"\"\"
export default function Component() {{
  return <div>Component</div>;
}}
\"\"\")

# Option 2: Remove the import (if not needed)
# edit_file(path="{affected_file or 'src/App.jsx'}", old_text="import ... from '{missing_module}';", new_text="")"""
            else:
                # NPM package
                return f"""# Install the missing package
install_dependencies(packages=["{missing_module}"])"""

    elif category == "MISSING_CSS":
        if affected_file:
            return f"""# Create the missing CSS file
write_file(path="{affected_file}", content=\"\"\"
/* Auto-generated CSS file */
\"\"\")"""

    elif category == "SYNTAX_ERROR":
        if affected_file:
            return f"""# First, read the file to see the error
read_file(path="{affected_file}")

# Then fix with edit_file()
# edit_file(path="{affected_file}", old_text="problematic code", new_text="fixed code")"""

    elif category == "WHITE_SCREEN":
        return """# Diagnose white screen
1. take_screenshot()  # See what's actually rendered
2. read_file(path="src/main.jsx")  # Check entry point
3. read_file(path="src/App.jsx")  # Check main component
4. get_console_messages()  # Check for silent errors"""

    elif category == "NPM_ERROR":
        return """# Fix NPM errors
shell("rm -rf node_modules")
install_dependencies()"""

    elif category == "BUILD_FAILED" or category == "VITE_PLUGIN_ERROR":
        return f"""# Get more details about the build error
get_all_terminals_output()
diagnose_preview_state()

# Then fix the specific file mentioned in the error
# read_file(path="{affected_file or 'src/App.jsx'}")
# edit_file(path="{affected_file or 'src/App.jsx'}", old_text="...", new_text="...")"""

    return None


# ============================================
# Error Analysis Functions
# ============================================

def categorize_error(error_text: str) -> Tuple[Optional[Dict], Optional[re.Match]]:
    """
    Categorize an error based on patterns.

    Returns:
        Tuple of (error_pattern_dict, regex_match) or (None, None) if no match
    """
    for pattern_info in ERROR_PATTERNS:
        pattern = pattern_info["pattern"]
        match = re.search(pattern, error_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return pattern_info, match
    return None, None


def extract_error_context(error_text: str, max_lines: int = 10) -> List[str]:
    """
    Extract relevant context lines from error text.

    Returns:
        List of relevant lines (error message, file path, stack trace)
    """
    lines = error_text.split("\n")
    relevant_lines = []

    # Keywords that indicate important context
    important_keywords = [
        "error",
        "failed",
        "cannot",
        "undefined",
        "missing",
        "at ",  # Stack trace line
        "in ",  # File location
        "from",
        "import",
    ]

    for line in lines[:50]:  # Check first 50 lines
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in important_keywords):
            relevant_lines.append(line.strip())
            if len(relevant_lines) >= max_lines:
                break

    return relevant_lines


def analyze_error_severity(errors: List[Dict]) -> str:
    """
    Determine overall severity of multiple errors.

    Returns:
        "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    """
    if not errors:
        return "LOW"

    severities = [e.get("severity", "MEDIUM") for e in errors]

    if "CRITICAL" in severities or severities.count("HIGH") > 2:
        return "CRITICAL"
    elif "HIGH" in severities:
        return "HIGH"
    elif "MEDIUM" in severities:
        return "MEDIUM"
    else:
        return "LOW"


# ============================================
# Error Handling Tools
# ============================================

def analyze_build_error(
    webcontainer_state: Optional[dict] = None,
    error_source: str = "all",
    **kwargs
) -> ToolResult:
    """
    Analyze build/runtime errors with intelligent categorization and fix suggestions.

    This tool provides deeper error analysis than verify_changes():
    - Smart error categorization (MISSING_IMPORT, SYNTAX_ERROR, etc.)
    - Severity assessment (CRITICAL, HIGH, MEDIUM, LOW)
    - Specific fix strategies for each error type
    - Extracted file/module names from errors

    **Use this when:**
    - verify_changes() shows errors but you need more guidance
    - You're stuck on how to fix a specific error
    - You want to understand error patterns to prevent future issues

    Args:
        webcontainer_state: Current WebContainer state
        error_source: Where to look - "terminal", "preview", "console", or "all" (default)

    Returns:
        ToolResult with detailed error analysis and fix recommendations
    """
    if not webcontainer_state:
        return ToolResult(
            success=False,
            result="WebContainer state not available"
        )

    analyzed_errors = []

    # 1. Analyze terminal errors
    if error_source in ["all", "terminal"]:
        terminals = webcontainer_state.get("terminals", [])
        for terminal in terminals:
            terminal_id = terminal.get("id", "unknown")
            history = terminal.get("history", [])
            last_output = terminal.get("last_output", [])

            # Combine outputs
            all_output = []
            for entry in history[-30:]:
                if isinstance(entry, dict):
                    all_output.append(entry.get("data", ""))
                else:
                    all_output.append(str(entry))
            all_output.extend(last_output[-20:] if last_output else [])

            output_text = "\n".join(all_output)

            # Categorize errors in terminal output
            pattern_info, match = categorize_error(output_text)
            if pattern_info:
                error_context = extract_error_context(output_text, max_lines=5)
                extracted_file = None
                if match and pattern_info.get("extract_file"):
                    try:
                        extracted_file = pattern_info["extract_file"](match)
                    except:
                        pass

                analyzed_errors.append({
                    "source": f"Terminal {terminal_id}",
                    "category": pattern_info["category"],
                    "severity": pattern_info["severity"],
                    "description": pattern_info["description"],
                    "context": error_context,
                    "affected_file": extracted_file,
                    "fix_strategy": pattern_info["fix_strategy"],
                })

    # 2. Analyze preview build errors
    if error_source in ["all", "preview"]:
        preview = webcontainer_state.get("preview", {})
        error_overlay = preview.get("error_overlay")

        if error_overlay:
            overlay_msg = error_overlay.get("message", "")
            overlay_stack = error_overlay.get("stack", "")
            full_error = f"{overlay_msg}\n{overlay_stack}"

            pattern_info, match = categorize_error(full_error)
            if pattern_info:
                error_context = [overlay_msg] + overlay_stack.split("\n")[:4]
                extracted_file = None
                if match and pattern_info.get("extract_file"):
                    try:
                        extracted_file = pattern_info["extract_file"](match)
                    except:
                        pass

                analyzed_errors.append({
                    "source": "Vite Build Error",
                    "category": pattern_info["category"],
                    "severity": "HIGH",  # Build errors are always high priority
                    "description": pattern_info["description"],
                    "context": error_context,
                    "affected_file": extracted_file,
                    "fix_strategy": pattern_info["fix_strategy"],
                })

    # 3. Analyze console errors
    if error_source in ["all", "console"]:
        preview = webcontainer_state.get("preview", {})
        console_messages = preview.get("console_messages", [])

        for msg in console_messages[-20:]:
            msg_type = msg.get("type", "log")
            if msg_type in ["error", "warning"]:
                args = msg.get("args", [])
                content = " ".join(str(arg) for arg in args)

                pattern_info, match = categorize_error(content)
                if pattern_info:
                    analyzed_errors.append({
                        "source": "Console",
                        "category": pattern_info["category"],
                        "severity": "MEDIUM" if msg_type == "warning" else pattern_info["severity"],
                        "description": pattern_info["description"],
                        "context": [content[:200]],
                        "affected_file": None,
                        "fix_strategy": pattern_info["fix_strategy"],
                    })

    # Build response
    if not analyzed_errors:
        return ToolResult(
            success=True,
            result="✅ No errors detected. All systems operational!"
        )

    overall_severity = analyze_error_severity(analyzed_errors)

    lines = [f"## 🔍 Error Analysis Report\n"]
    lines.append(f"**Overall Severity:** {overall_severity}")
    lines.append(f"**Errors Found:** {len(analyzed_errors)}\n")
    lines.append("---\n")

    # Group errors by category
    by_category = {}
    for error in analyzed_errors:
        category = error["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(error)

    # Output errors by category
    for category, errors in by_category.items():
        lines.append(f"### {category.replace('_', ' ').title()} ({len(errors)} error{'s' if len(errors) > 1 else ''})\n")

        for i, error in enumerate(errors, 1):
            lines.append(f"**Error {i}:** {error['description']}")
            lines.append(f"- **Source:** {error['source']}")
            lines.append(f"- **Severity:** {error['severity']}")

            if error.get("affected_file"):
                lines.append(f"- **Affected File:** `{error['affected_file']}`")

            if error.get("context"):
                lines.append(f"- **Error Details:**")
                for ctx_line in error["context"][:3]:
                    if ctx_line.strip():
                        lines.append(f"  ```")
                        lines.append(f"  {ctx_line.strip()[:150]}")
                        lines.append(f"  ```")

            lines.append(f"\n**🔧 Fix Strategy:**")
            for step in error["fix_strategy"]:
                lines.append(f"{step}")

            lines.append("")

    lines.append("---\n")
    lines.append("### 🎯 Recommended Action Plan\n")

    if overall_severity in ["CRITICAL", "HIGH"]:
        lines.append("**Priority:** FIX IMMEDIATELY - Build is broken!")
        lines.append("\n1. Start with the first error listed above")
        lines.append("2. Follow the fix strategy step by step")
        lines.append("3. Call verify_changes() after each fix")
        lines.append("4. Repeat until all errors are resolved")
        lines.append("\n⚠️ **Do not move on to other tasks until errors are fixed!**")
    else:
        lines.append("**Priority:** Address when convenient")
        lines.append("\nThese are lower-priority issues that can be fixed incrementally.")

    return ToolResult(
        success=True,
        result="\n".join(lines)
    )


# ============================================
# Tool Registry
# ============================================

ERROR_HANDLING_TOOLS = {
    "analyze_build_error": analyze_build_error,
}


def get_error_handling_tool_definitions() -> List[dict]:
    """
    Get tool definitions in Claude API format for error handling tools.

    Returns:
        List of tool definition dicts
    """
    return [
        {
            "name": "analyze_build_error",
            "description": """Analyze build/runtime errors with intelligent categorization and fix recommendations.

**Use this tool when:**
- verify_changes() shows errors but you need specific guidance on how to fix them
- You're encountering unfamiliar errors
- You want to understand error patterns better
- You need a structured approach to fixing multiple errors

**What this tool provides:**
1. **Smart Categorization**: Groups errors by type (MISSING_IMPORT, SYNTAX_ERROR, etc.)
2. **Severity Assessment**: Tells you which errors to fix first (CRITICAL > HIGH > MEDIUM > LOW)
3. **Fix Strategies**: Step-by-step instructions for each error type
4. **File Extraction**: Automatically identifies affected files from error messages
5. **Action Plan**: Prioritized list of what to do next

**Example workflow:**
```
1. verify_changes() → Shows errors exist
2. analyze_build_error() → Get detailed analysis and fix plan
3. Follow fix strategy for each error
4. verify_changes() → Confirm fixes worked
```

This tool is especially useful for:
- Missing import errors (tells you exact file to create/fix)
- CSS file errors (guides you to create missing CSS)
- Syntax errors (points to problematic code)
- Build failures (explains root cause)""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "error_source": {
                        "type": "string",
                        "enum": ["all", "terminal", "preview", "console"],
                        "description": "Where to look for errors: 'all' (default), 'terminal', 'preview', or 'console'",
                        "default": "all"
                    }
                },
                "required": []
            }
        }
    ]
