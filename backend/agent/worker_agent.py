"""
Worker Agent

Lightweight agent for section-level code generation.

Features:
- Independent context (isolated from Master and other Workers)
- Section-specific tools only
- Direct Claude API calls
- Returns final code files to Master
- TaskContract-based file path isolation
- Path validation to prevent cross-worker conflicts

Architecture:
- Master Agent spawns Workers for each section
- Each Worker has its own context, no shared state
- Workers run in parallel with isolated file namespaces
- Only code results passed back to Master
"""

from __future__ import annotations
import os
import json
import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import anthropic
from openai import AsyncOpenAI, APIError as OpenAIAPIError

# Debug module (modular, controlled by SECTION_DEBUG env var)
from .section_debug import record_checkpoint, debug_log

logger = logging.getLogger(__name__)


# ============================================
# Image Proxy URL Rewriting
# ============================================

def _to_proxy_url(original_url: str) -> str:
    """
    Convert external image URL to WebContainer proxy URL.

    This enables images to load correctly in WebContainer environment
    by routing requests through the internal Vite proxy middleware.

    Args:
        original_url: Original external image URL

    Returns:
        Proxied URL or original URL if not applicable
    """
    if not original_url:
        return original_url

    # Skip data URLs (already embedded)
    if original_url.startswith("data:"):
        return original_url

    # Skip relative paths (already local)
    if original_url.startswith("/") and not original_url.startswith("//"):
        return original_url

    # Skip if already proxied
    if "/proxy-image?url=" in original_url:
        return original_url

    # Handle protocol-relative URLs (//example.com/image.jpg)
    if original_url.startswith("//"):
        original_url = "https:" + original_url

    # URL encode and create proxy URL
    from urllib.parse import quote
    return f"/proxy-image?url={quote(original_url, safe='')}"


def _rewrite_image_urls(images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rewrite all image URLs in the list to use the WebContainer proxy.

    Args:
        images: List of image objects with 'src' field

    Returns:
        List with 'src' fields converted to proxy URLs
    """
    rewritten = []
    for img in images:
        new_img = dict(img)  # Shallow copy
        if "src" in new_img:
            new_img["src"] = _to_proxy_url(new_img["src"])
        rewritten.append(new_img)
    return rewritten


# ============================================
# Event Callbacks Type Definitions
# ============================================

# Callback for tool call events
OnToolCallCallback = Callable[[str, str, str, Dict[str, Any]], Awaitable[None]]
# Args: worker_id, section_name, tool_name, tool_input

# Callback for tool result events
OnToolResultCallback = Callable[[str, str, str, str, bool], Awaitable[None]]
# Args: worker_id, section_name, tool_name, result, success

# Callback for iteration events (NEW)
OnIterationCallback = Callable[[str, str, int, int], Awaitable[None]]
# Args: worker_id, section_name, iteration, max_iterations

# Callback for text delta events (NEW)
OnTextDeltaCallback = Callable[[str, str, str, int], Awaitable[None]]
# Args: worker_id, section_name, text, iteration


# ============================================
# Configuration
# ============================================

@dataclass
class WorkerConfig:
    """
    Worker configuration from Master Agent

    Defines what the Worker should implement.
    """
    # Worker identification
    worker_id: str
    section_name: str

    # Task definition
    task_description: str
    design_requirements: str

    # Section-specific data (FULL data, no compression)
    section_data: Dict[str, Any] = field(default_factory=dict)

    # Reference context (layout info, style guide, etc.)
    layout_context: str = ""
    style_context: str = ""

    # Target files to generate/modify
    target_files: List[str] = field(default_factory=list)

    # Model configuration
    # Worker Agent uses Sonnet 3.5 for code generation
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 8192  # Max for sonnet 3.5 model
    max_iterations: int = 50  # Limit iterations for Workers

    # TaskContract-based path isolation (NEW)
    worker_namespace: str = ""  # e.g., "header", "hero", "footer"
    base_path: str = "/src/components/sections"  # Base path for all workers
    allowed_extensions: List[str] = field(default_factory=lambda: [".jsx", ".css", ".js", ".md"])

    # TaskContract prompt (if provided, overrides default prompt)
    task_contract_prompt: str = ""

    # Display name for UI (human-friendly, e.g., "Navigation", "Section 1")
    display_name: str = ""


class WorkerErrorType:
    """Error type categorization for Worker failures"""
    NONE = "none"                    # No error
    NO_FILES = "no_files"            # Worker completed but generated 0 files
    API_ERROR = "api_error"          # Claude API error
    VALIDATION_ERROR = "validation"  # Path or content validation failed
    TIMEOUT = "timeout"              # Max iterations reached without completion
    EMPTY_HTML = "empty_html"        # No HTML data provided to worker
    UNKNOWN = "unknown"              # Unknown error


@dataclass
class WorkerResult:
    """
    Worker result returned to Master Agent

    Contains only the final output, no intermediate state.
    """
    # Worker identification
    worker_id: str
    section_name: str

    # Status
    success: bool
    error: Optional[str] = None
    error_type: str = WorkerErrorType.NONE  # Categorized error type

    # Generated code files (path -> content)
    files: Dict[str, str] = field(default_factory=dict)

    # Summary of what was done
    summary: str = ""

    # Execution metadata
    iterations: int = 0
    duration_ms: int = 0
    retry_count: int = 0  # Number of retries attempted


# ============================================
# Worker Tools (Minimal Set)
# ============================================

# Worker 工具集 - 最小化，只保留必要工具
# Worker tools - minimal set, only essential tools
WORKER_TOOLS = [
    {
        "name": "write_code",
        "description": "Write code to a file. Use this to generate React component code for your assigned section.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root (e.g., src/components/sections/header_0/Header0Section.jsx)"
                },
                "content": {
                    "type": "string",
                    "description": "Complete file content to write"
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what this code does"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "complete_task",
        "description": "Mark the task as complete. Call this when you have finished implementing the section.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was implemented"
                }
            },
            "required": ["summary"]
        }
    }
]


def _is_proxy_enabled() -> bool:
    """Check if Claude proxy is enabled"""
    return os.getenv("USE_CLAUDE_PROXY", "").lower() in ("true", "1", "yes")


# Model max_tokens limits
MODEL_MAX_TOKENS = {
    # Haiku 4.5 - supports higher output
    "claude-haiku-4-5-20250011": 16384,
    # Haiku 3.5 - max 8192
    "claude-3-5-haiku-20241022": 8192,
    "claude-3-5-haiku-latest": 8192,
    # Sonnet 4.5 - supports 16384 output
    "claude-sonnet-4-5-20250929": 16384,
    # Sonnet 4 models
    "claude-sonnet-4-20250514": 16384,
    "claude-3-5-sonnet-20241022": 8192,
    "claude-3-5-sonnet-latest": 8192,
    # Default fallback
    "default": 8192,
}


def _get_max_tokens_for_model(model: str) -> int:
    """Get max_tokens limit for a specific model"""
    return MODEL_MAX_TOKENS.get(model, MODEL_MAX_TOKENS["default"])


# ============================================
# Worker Agent
# ============================================

class WorkerAgent:
    """
    Worker Agent for Section-Level Code Generation

    Key characteristics:
    - Completely isolated context
    - Event callbacks for debugging/visibility
    - Section-specific tools only
    - Returns final code files to Master
    """

    def __init__(
        self,
        config: WorkerConfig,
        on_tool_call: Optional[OnToolCallCallback] = None,
        on_tool_result: Optional[OnToolResultCallback] = None,
        on_iteration: Optional[OnIterationCallback] = None,
        on_text_delta: Optional[OnTextDeltaCallback] = None,
    ):
        """
        Initialize Worker Agent

        Args:
            config: Worker configuration from Master
            on_tool_call: Callback when worker calls a tool
            on_tool_result: Callback when tool execution completes
            on_iteration: Callback when worker starts a new iteration
            on_text_delta: Callback when worker receives reasoning text
        """
        self.config = config
        self.worker_id = config.worker_id
        self.section_name = config.section_name

        # Event callbacks for visibility
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_iteration = on_iteration
        self.on_text_delta = on_text_delta

        # Initialize API client
        self.use_proxy = _is_proxy_enabled()

        if self.use_proxy:
            proxy_api_key = os.getenv("CLAUDE_PROXY_API_KEY")
            proxy_base_url = os.getenv("CLAUDE_PROXY_BASE_URL", "")
            proxy_model = os.getenv("CLAUDE_PROXY_MODEL")

            if not proxy_api_key:
                raise ValueError("CLAUDE_PROXY_API_KEY not set")

            # Check if using Anthropic native format (URL contains /messages)
            if "/messages" in proxy_base_url.lower():
                # Anthropic native format - handle both /v1/messages and /V1/messages
                import re
                base_url = re.sub(r'/v1/messages', '', proxy_base_url, flags=re.IGNORECASE)
                base_url = re.sub(r'/messages', '', base_url, flags=re.IGNORECASE)
                self.anthropic_client = anthropic.AsyncAnthropic(
                    api_key=proxy_api_key,
                    base_url=base_url,
                    timeout=120.0,
                )
                self.openai_client = None
            else:
                # OpenAI-compatible format
                self.openai_client = AsyncOpenAI(
                    api_key=proxy_api_key,
                    base_url=proxy_base_url,
                    timeout=120.0,
                )
                self.anthropic_client = None

            # Override model if proxy model is configured
            # Priority: CLAUDE_PROXY_MODEL_WORKER > CLAUDE_PROXY_MODEL > default
            proxy_model_worker = os.getenv("CLAUDE_PROXY_MODEL_WORKER")
            effective_model = proxy_model_worker or proxy_model

            if effective_model:
                self.config.model = effective_model
                # Auto-adjust max_tokens based on model limits
                model_max = _get_max_tokens_for_model(effective_model)
                if self.config.max_tokens > model_max:
                    logger.info(f"[Worker {self.worker_id}] Adjusting max_tokens from {self.config.max_tokens} to {model_max} for model {effective_model}")
                    self.config.max_tokens = model_max
                logger.debug(f"[Worker {self.worker_id}] Using model: {effective_model} (max_tokens={self.config.max_tokens})")
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")

            self.anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)
            self.openai_client = None

        # Worker state (isolated)
        self.files: Dict[str, str] = {}
        self.is_complete = False
        self.completion_summary = ""
        self.iteration_count = 0

        # Path isolation settings
        self.namespace = config.worker_namespace or self._generate_namespace()
        self.base_path = config.base_path
        self.allowed_extensions = config.allowed_extensions
        self.path_violations: List[str] = []  # Track path violations

        logger.info(f"WorkerAgent initialized: {self.worker_id} for section '{self.section_name}' (namespace: {self.namespace})")

    def _generate_namespace(self) -> str:
        """Generate namespace from section name if not provided"""
        # Convert section_name to valid namespace: "header-0" -> "header_0"
        namespace = self.section_name.replace("-", "_").replace(".", "_").replace(" ", "_").lower()
        return namespace

    def _get_allowed_path(self, filename: str) -> str:
        """Get the full allowed path for a filename"""
        # Remove leading slash if present
        filename = filename.lstrip("/")
        # If filename already has full path, extract just the filename
        if "/" in filename:
            filename = filename.split("/")[-1]
        return f"{self.base_path}/{self.namespace}/{filename}"

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is allowed for this worker"""
        # Normalize path
        if not path.startswith("/"):
            path = "/" + path

        # Check forbidden paths
        forbidden = ["/src/App.jsx", "/src/main.jsx", "/src/index.css", "/package.json", "/vite.config.js"]
        for f in forbidden:
            if path == f or path.endswith(f):
                return False

        # Check if path is within worker's namespace
        expected_prefix = f"{self.base_path}/{self.namespace}/"
        alt_prefix = expected_prefix.lstrip("/")

        if path.startswith(expected_prefix) or path.lstrip("/").startswith(alt_prefix):
            # Check extension
            return any(path.endswith(ext) for ext in self.allowed_extensions)

        return False

    def _normalize_path(self, path: str) -> str:
        """Normalize and validate path, returning corrected path if needed"""
        original_path = path

        # Ensure leading slash
        if not path.startswith("/"):
            path = "/" + path

        # If path is outside namespace, relocate it
        expected_prefix = f"{self.base_path}/{self.namespace}/"

        if not path.startswith(expected_prefix):
            # Extract filename and put it in correct location
            filename = path.split("/")[-1]
            corrected_path = f"{self.base_path}/{self.namespace}/{filename}"

            logger.warning(f"Worker {self.worker_id}: Path '{original_path}' outside namespace, relocated to '{corrected_path}'")
            self.path_violations.append(f"Relocated: {original_path} -> {corrected_path}")

            return corrected_path

        return path

    # ============================================
    # Main Entry Point
    # ============================================

    async def run(self, max_retries: int = 3) -> WorkerResult:
        """
        Run the worker to generate code for assigned section.

        Includes retry mechanism: if worker fails to generate files,
        it will retry up to max_retries times before reporting failure.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            WorkerResult with generated files
        """
        start_time = datetime.now()
        retry_count = 0
        last_error = None
        last_error_type = WorkerErrorType.UNKNOWN

        # DEBUG: Record section data received by worker
        record_checkpoint(
            "worker_received_data",
            {
                "section_data": self.config.section_data,
                "worker_namespace": self.config.worker_namespace,
                "task_description": self.config.task_description[:200] if self.config.task_description else "",
            },
            {
                "worker_id": self.worker_id,
                "section_name": self.section_name,
            }
        )

        # Pre-validation: Check if we have HTML data
        raw_html = self.config.section_data.get("raw_html", "")
        if not raw_html or len(raw_html.strip()) < 50:
            logger.warning(f"Worker {self.worker_id}: No or minimal HTML data provided")
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return WorkerResult(
                worker_id=self.worker_id,
                section_name=self.section_name,
                success=False,
                error="No HTML data provided to convert",
                error_type=WorkerErrorType.EMPTY_HTML,
                files={},
                summary="Failed: No HTML data to convert",
                iterations=0,
                duration_ms=duration_ms,
                retry_count=0,
            )

        # Retry loop
        while retry_count <= max_retries:
            try:
                # Reset state for each attempt
                if retry_count > 0:
                    logger.info(f"Worker {self.worker_id}: Retry attempt {retry_count}/{max_retries}")
                    self._reset_state()

                # Build prompts
                system_prompt = self._build_system_prompt()
                messages = [{
                    "role": "user",
                    "content": self._build_initial_prompt(retry_attempt=retry_count)
                }]

                # Run agent loop
                await self._agent_loop(system_prompt, messages)

                # Validate result: Must have at least 1 file
                if len(self.files) == 0:
                    last_error = "Worker completed but generated 0 files"
                    last_error_type = WorkerErrorType.NO_FILES
                    logger.warning(f"Worker {self.worker_id}: {last_error} (attempt {retry_count + 1})")
                    retry_count += 1
                    continue

                # Success!
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                # Generate AGENT_LOG.md with thinking process
                self._generate_agent_log(
                    system_prompt=system_prompt,
                    duration_ms=duration_ms,
                    retry_count=retry_count,
                )

                return WorkerResult(
                    worker_id=self.worker_id,
                    section_name=self.section_name,
                    success=True,
                    error_type=WorkerErrorType.NONE,
                    files=self.files,
                    summary=self.completion_summary or f"Generated {len(self.files)} files",
                    iterations=self.iteration_count,
                    duration_ms=duration_ms,
                    retry_count=retry_count,
                )

            except anthropic.APIError as e:
                last_error = f"API Error: {str(e)}"
                last_error_type = WorkerErrorType.API_ERROR
                logger.error(f"Worker {self.worker_id} API error: {e}")
                retry_count += 1

            except OpenAIAPIError as e:
                last_error = f"Proxy API Error: {str(e)}"
                last_error_type = WorkerErrorType.API_ERROR
                logger.error(f"Worker {self.worker_id} proxy API error: {e}")
                retry_count += 1

            except Exception as e:
                last_error = str(e)
                last_error_type = WorkerErrorType.UNKNOWN
                logger.error(f"Worker {self.worker_id} error: {e}", exc_info=True)
                retry_count += 1

        # All retries exhausted
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.error(f"Worker {self.worker_id}: All {max_retries} retries exhausted. Last error: {last_error}")

        return WorkerResult(
            worker_id=self.worker_id,
            section_name=self.section_name,
            success=False,
            error=last_error,
            error_type=last_error_type,
            files=self.files,  # Return any partial results
            summary=f"Failed after {retry_count} attempts: {last_error}",
            iterations=self.iteration_count,
            duration_ms=duration_ms,
            retry_count=retry_count,
        )

    def _reset_state(self):
        """Reset worker state for retry attempt"""
        self.files = {}
        self.is_complete = False
        self.completion_summary = ""
        self.iteration_count = 0
        self.path_violations = []

    def _generate_agent_log(
        self,
        system_prompt: str,
        duration_ms: int,
        retry_count: int,
    ):
        """
        Generate AGENT_LOG.md with worker's thinking process and context.

        This file is placed in the same folder as the generated code,
        allowing users to understand what data the worker received
        and how it processed the task.
        """
        component_name = self._get_component_name()
        log_path = f"{self.base_path}/{self.namespace}/AGENT_LOG.md"

        # Extract key data from section_data
        section_data = self.config.section_data
        raw_html = section_data.get("raw_html", "")
        images = section_data.get("images", [])
        links = section_data.get("links", [])
        styles = section_data.get("styles", {})
        text_content_raw = section_data.get("text_content", "")
        headings = section_data.get("headings", [])
        html_range = section_data.get("html_range", {})

        # 计算 Worker 真正接收的行数
        start_line = html_range.get("start_line", 0)
        end_line = html_range.get("end_line", 0)
        html_lines_received = raw_html.count('\n') + 1 if raw_html else 0

        # 格式化行数范围显示
        if start_line > 0 and end_line > 0:
            html_range_display = f"Line {start_line} ~ Line {end_line} (from full page HTML)"
        else:
            html_range_display = "Full HTML content (no line range specified)"

        # text_content 可能是字典，需要转换为字符串
        if isinstance(text_content_raw, str):
            text_content = text_content_raw
        elif isinstance(text_content_raw, dict):
            text_content = json.dumps(text_content_raw, ensure_ascii=False)
        else:
            text_content = str(text_content_raw) if text_content_raw else ""

        # Build images section
        images_md = ""
        if images:
            images_md = "\n### Images Received\n\n"
            for i, img in enumerate(images[:10]):  # Limit to first 10
                src = img.get("src", "N/A")
                alt = img.get("alt", "")
                images_md += f"{i+1}. `{src}`"
                if alt:
                    images_md += f" - {alt}"
                images_md += "\n"
            if len(images) > 10:
                images_md += f"\n... and {len(images) - 10} more images\n"

        # Build links section
        links_md = ""
        if links:
            links_md = "\n### Links Received\n\n"
            for i, link in enumerate(links[:10]):  # Limit to first 10
                href = link.get("href", "N/A")
                text = link.get("text", "")
                links_md += f"{i+1}. `{href}`"
                if text:
                    links_md += f" - {text[:50]}"
                links_md += "\n"
            if len(links) > 10:
                links_md += f"\n... and {len(links) - 10} more links\n"

        # Build styles section
        styles_md = ""
        if styles:
            styles_md = "\n### Styles Received\n\n```json\n"
            styles_json = json.dumps(styles, ensure_ascii=False, indent=2)
            styles_md += styles_json[:1000]
            if len(styles_json) > 1000:
                styles_md += "\n... (truncated)"
            styles_md += "\n```\n"

        # Build headings section
        headings_md = ""
        if headings:
            headings_md = "\n### Headings Extracted\n\n"
            for h in headings[:10]:
                headings_md += f"- {h}\n"

        # Files generated
        files_md = "\n### Files Generated\n\n"
        for file_path in self.files.keys():
            files_md += f"- `{file_path}`\n"

        # Build the complete log
        log_content = f"""# Agent Log: {self.section_name}

> This file documents the Worker Agent's context and thinking process.
> Generated automatically - do not edit manually.

---

## 📋 Task Summary

| Property | Value |
|----------|-------|
| **Worker ID** | `{self.worker_id}` |
| **Section Name** | `{self.section_name}` |
| **Component** | `{component_name}` |
| **Namespace** | `{self.namespace}` |
| **Duration** | {duration_ms}ms |
| **Iterations** | {self.iteration_count} |
| **Retry Count** | {retry_count} |
| **Files Generated** | {len(self.files)} |

## 📥 Data Received

### HTML Content

- **Size**: {len(raw_html)} characters ({html_lines_received} lines)
- **Source Line Range**: {html_range_display}
- **Preview**:

```html
{raw_html[:2000]}{"..." if len(raw_html) > 2000 else ""}
```
{images_md}{links_md}{styles_md}{headings_md}
### Text Content Preview

```
{text_content[:500]}{"..." if len(text_content) > 500 else ""}
```

## 🎯 Task Description

{self.config.task_description or "Convert HTML to React JSX component"}

## 🔧 Design Requirements

{self.config.design_requirements or "Follow original HTML structure exactly"}

## 📤 Output
{files_md}
### Completion Summary

{self.completion_summary or "Task completed successfully"}

---

## 🤖 System Prompt (Full)

<details>
<summary>Click to expand system prompt</summary>

```
{system_prompt}
```

</details>

---

*Generated at: {datetime.now().isoformat()}*
"""

        # Add to files dict
        self.files[log_path] = log_content
        logger.info(f"Worker {self.worker_id}: Generated AGENT_LOG.md at {log_path}")

    # ============================================
    # System Prompt
    # ============================================

    def _build_system_prompt(self) -> str:
        """
        Build system prompt for worker with complete context injection

        Worker 不需要查询数据，所有数据已直接注入到 prompt 中
        """

        # Use TaskContract prompt if provided
        if self.config.task_contract_prompt:
            return self.config.task_contract_prompt

        # Get component name from namespace
        component_name = self._get_component_name()
        full_path = f"{self.base_path}/{self.namespace}/{component_name}.jsx"

        # 获取完整的 section 数据
        section_data = self.config.section_data

        # 提取关键数据
        raw_html = section_data.get("raw_html", "")
        styles = section_data.get("styles", {})
        text_content = section_data.get("text_content", "")
        headings = section_data.get("headings", [])

        # Media flags (images/links are in raw_html, not separate arrays)
        has_images = section_data.get("has_images", False)
        image_count = section_data.get("image_count", 0)
        has_links = section_data.get("has_links", False)
        link_count = section_data.get("link_count", 0)

        # 构建 HTML 部分
        html_section = ""
        if raw_html:
            html_section = f"""
## 📄 ORIGINAL HTML

This is the HTML you must replicate. Study it carefully:

```html
{raw_html}
```
"""

        # 构建 Media Info 部分 (images/links are in raw_html)
        media_section = ""
        if has_images or has_links:
            media_section = f"""
## 📦 MEDIA INFO

This section contains:
- **Images**: {image_count} (all `<img src="...">` URLs are in the HTML above)
- **Links**: {link_count} (all `<a href="...">` URLs are in the HTML above)

**CRITICAL**:
- Extract ALL image `src` and link `href` values directly from the HTML
- Use the EXACT URLs as they appear in the HTML
- For external images, convert to proxy format: `/proxy-image?url=<encoded_url>`
"""

        # 构建 Styles 部分
        styles_section = ""
        if styles:
            styles_json = json.dumps(styles, ensure_ascii=False, indent=2)
            styles_section = f"""
## 🎨 STYLES

```json
{styles_json}
```
"""

        # 构建 Text Content 部分
        text_section = ""
        if headings or text_content:
            # text_content 可能是字典，需要安全处理
            text_preview = ""
            if isinstance(text_content, str):
                text_preview = text_content[:500] + ("..." if len(text_content) > 500 else "")
            elif isinstance(text_content, dict):
                text_preview = json.dumps(text_content, ensure_ascii=False)[:500] + "..."
            else:
                text_preview = str(text_content)[:500]

            text_section = f"""
## 📝 TEXT CONTENT

**Headings**: {json.dumps(headings, ensure_ascii=False) if headings else "None"}

**Content Preview**: {text_preview}
"""

        return f"""You are an **HTML → JSX CONVERTER**, NOT a content creator.

## ⛔ CRITICAL RULE: YOU ARE A CONVERTER, NOT A CREATOR

**YOU MUST NOT:**
- ❌ Create new content, text, or URLs
- ❌ Imagine what the section "should" look like
- ❌ Use placeholder text like "Lorem ipsum" or "Sample text"
- ❌ Use placeholder URLs like "https://example.com"
- ❌ Add features not in the original HTML
- ❌ Simplify or summarize the content

**YOU MUST:**
- ✅ Convert the provided HTML to JSX syntax EXACTLY
- ✅ Keep ALL text content word-for-word
- ✅ Keep ALL URLs exactly as provided
- ✅ Keep ALL class names, IDs, and attributes
- ✅ Convert HTML attributes to JSX (class → className, for → htmlFor, etc.)

## 📋 YOUR ASSIGNMENT

- **Section**: `{self.section_name}`
- **Namespace**: `{self.namespace}`
- **Component Name**: `{component_name}`
- **Output Path**: `{full_path}`

## 📁 FILE PATH CONSTRAINTS

**You can ONLY write to:** `{self.base_path}/{self.namespace}/`

✅ ALLOWED: `{full_path}`
❌ FORBIDDEN: `/src/App.jsx`, `/src/main.jsx`, `/package.json`

## 🔄 CONVERSION RULES

| HTML | JSX |
|------|-----|
| `class="..."` | `className="..."` |
| `for="..."` | `htmlFor="..."` |
| `onclick="..."` | `onClick={{...}}` |
| `<img src="...">` | `<img src="..." />` |
| `<!--comment-->` | `{{/* comment */}}` |
| `style="color: red"` | `style={{{{ color: 'red' }}}}` |

## 🛠️ YOUR TOOLS

1. **write_code(path, content)**: Write your converted React component
2. **complete_task(summary)**: Mark task complete

{html_section}{media_section}{styles_section}{text_section}

## ✅ REQUIRED OUTPUT FORMAT

```jsx
// File: {full_path}
import React from 'react';

export default function {component_name}() {{
  return (
    // CONVERTED JSX from the HTML above
    // Every URL, every text, every attribute must match EXACTLY
  );
}}
```

## ⚠️ VALIDATION CHECKLIST

Before calling complete_task, verify:
1. [ ] All image `src` URLs are extracted from the HTML exactly
2. [ ] All link `href` URLs are extracted from the HTML exactly
3. [ ] All text content matches the HTML word-for-word
4. [ ] No placeholder content was added
5. [ ] No content was omitted or summarized
6. [ ] External image URLs use proxy format: `/proxy-image?url=<encoded_url>`

**BEGIN NOW**: Convert the HTML above to JSX and write the component."""

    def _get_component_name(self) -> str:
        """Generate component name from namespace"""
        # header_0 -> Header0Section
        parts = self.namespace.split("_")
        pascal = "".join(p.capitalize() for p in parts)
        if not pascal.endswith("Section"):
            pascal += "Section"
        return pascal

    def _build_initial_prompt(self, retry_attempt: int = 0) -> str:
        """
        Build initial user prompt - 简洁版，因为数据已在 System Prompt 中

        所有数据（HTML、images、links）已直接嵌入到 System Prompt，
        这里只需要简单的任务启动指令

        Args:
            retry_attempt: Current retry attempt number (0 = first attempt)
        """
        component_name = self._get_component_name()
        full_path = f"{self.base_path}/{self.namespace}/{component_name}.jsx"

        # 获取数据统计
        images = self.config.section_data.get("images", [])
        links = self.config.section_data.get("links", [])
        raw_html = self.config.section_data.get("raw_html", "")

        # Retry warning
        retry_warning = ""
        if retry_attempt > 0:
            retry_warning = f"""
⚠️ **RETRY ATTEMPT {retry_attempt}**

Previous attempt failed to generate any files. You MUST:
1. Call `write_code` with actual code content
2. Do NOT skip the write_code step
3. Do NOT call complete_task without writing code first

"""

        return f"""{retry_warning}## Task: Implement "{self.section_name}" Component

**Output**: `{full_path}`
**Component**: `{component_name}`

### Data Summary
- HTML: {len(raw_html)} characters
- Images: {len(images)} items (URLs provided in system prompt)
- Links: {len(links)} items (URLs provided in system prompt)

### Instructions

1. **Read** the HTML, images, and links data in the system prompt above
2. **Create** a React component that exactly replicates the original
3. **Write** to `{full_path}` using `write_code` ⚠️ REQUIRED
4. **Complete** using `complete_task`

**Begin now** - all the data you need is in the system prompt above."""

    # ============================================
    # Agent Loop
    # ============================================

    async def _agent_loop(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
    ):
        """
        Worker agent loop

        Runs until:
        - complete_task is called
        - Max iterations reached
        - Error occurs
        """
        tools = self._get_tools_for_api()

        while self.iteration_count < self.config.max_iterations and not self.is_complete:
            self.iteration_count += 1
            logger.debug(f"Worker {self.worker_id} iteration {self.iteration_count}")

            # Emit iteration event (NEW)
            if self.on_iteration:
                try:
                    await self.on_iteration(
                        self.worker_id,
                        self.section_name,
                        self.iteration_count,
                        self.config.max_iterations,
                    )
                except Exception as e:
                    logger.warning(f"Iteration callback error: {e}")

            try:
                # Call Claude API
                response = await self._call_claude(system_prompt, messages, tools)

                # Process response
                assistant_content = []
                has_tool_use = False

                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({
                            "type": "text",
                            "text": block.text,
                        })

                        # Emit text delta event (NEW)
                        if self.on_text_delta:
                            try:
                                await self.on_text_delta(
                                    self.worker_id,
                                    self.section_name,
                                    block.text,
                                    self.iteration_count,
                                )
                            except Exception as e:
                                logger.warning(f"Text delta callback error: {e}")

                    elif block.type == "tool_use":
                        has_tool_use = True

                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

                        # Emit tool call event
                        if self.on_tool_call:
                            try:
                                await self.on_tool_call(
                                    self.worker_id,
                                    self.section_name,
                                    block.name,
                                    block.input,
                                )
                            except Exception as e:
                                logger.warning(f"Tool call callback error: {e}")

                        # Execute tool
                        tool_result = await self._execute_tool(block.name, block.input)

                        # Emit tool result event
                        if self.on_tool_result:
                            try:
                                # Truncate result for visibility (don't send full file content)
                                result_preview = tool_result[:500] + "..." if len(tool_result) > 500 else tool_result
                                await self.on_tool_result(
                                    self.worker_id,
                                    self.section_name,
                                    block.name,
                                    result_preview,
                                    True,  # success
                                )
                            except Exception as e:
                                logger.warning(f"Tool result callback error: {e}")

                        # Add to messages
                        messages.append({
                            "role": "assistant",
                            "content": assistant_content,
                        })
                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_result,
                            }],
                        })

                        assistant_content = []

                        # Check if complete
                        if self.is_complete:
                            break

                # Check if should continue
                if not has_tool_use or self.is_complete:
                    break

                if response.stop_reason == "end_turn":
                    break

            except Exception as e:
                logger.error(f"Worker {self.worker_id} API error: {e}")
                raise

    # ============================================
    # Tool Execution
    # ============================================

    async def _execute_tool(self, name: str, input_data: Dict[str, Any]) -> str:
        """
        Execute a worker tool

        Worker 工具集已简化，只支持 write_code 和 complete_task
        所有数据已在 System Prompt 中注入，无需查询工具
        """

        if name == "write_code":
            return self._tool_write_code(
                path=input_data.get("path", ""),
                content=input_data.get("content", ""),
                description=input_data.get("description", ""),
            )

        elif name == "complete_task":
            return self._tool_complete(
                summary=input_data.get("summary", ""),
            )

        else:
            return f"Unknown tool: {name}. Available tools: write_code, complete_task"

    def _tool_write_code(self, path: str, content: str, description: str = "") -> str:
        """Write code to a file with path validation and normalization"""
        if not path:
            return "Error: path is required"
        if not content:
            return "Error: content is required"

        # Normalize and validate path
        original_path = path
        path = self._normalize_path(path)

        # Store file with normalized path
        self.files[path] = content

        desc_msg = f" ({description})" if description else ""

        # Provide feedback about path normalization
        if path != original_path and not original_path.startswith(self.base_path):
            return f"Successfully wrote {len(content)} characters to {path}{desc_msg}\n" \
                   f"Note: Path was normalized from '{original_path}' to stay within namespace '{self.namespace}'."

        return f"Successfully wrote {len(content)} characters to {path}{desc_msg}"

    def _tool_complete(self, summary: str) -> str:
        """
        Mark task as complete.

        Note: If no files were written, the run() method will trigger a retry.
        This allows the LLM to complete even with 0 files, but retry logic
        will catch this case.
        """
        self.is_complete = True
        self.completion_summary = summary

        # Warn if no files were written (retry will handle this)
        if len(self.files) == 0:
            logger.warning(f"Worker {self.worker_id}: complete_task called with 0 files written")
            return f"⚠️ WARNING: No files were written! You must call write_code before complete_task. " \
                   f"Task marked complete but will likely fail validation. Summary: {summary}"

        return f"Task marked complete. Generated {len(self.files)} file(s). Summary: {summary}"

    # ============================================
    # API Calls
    # ============================================

    def _get_tools_for_api(self) -> List[Dict[str, Any]]:
        """Get tools in Claude API format"""
        return WORKER_TOOLS

    async def _call_claude(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ):
        """Call Claude API"""
        # Use Anthropic client if available (either direct or native proxy)
        if self.anthropic_client:
            return await self._call_anthropic_direct(system_prompt, messages, tools)
        else:
            # Use OpenAI-compatible proxy
            return await self._call_openai_proxy(system_prompt, messages, tools)

    async def _call_anthropic_direct(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ):
        """Call direct Anthropic API"""
        return await self.anthropic_client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )

    async def _call_openai_proxy(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ):
        """Call OpenAI-compatible proxy"""
        # Convert messages
        openai_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if isinstance(content, str):
                openai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                converted = self._convert_content_to_openai(content, role)
                if converted:
                    openai_messages.append(converted)

        # Convert tools
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                }
            }
            for t in tools
        ]

        # Call API
        response = await self.openai_client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            messages=openai_messages,
            tools=openai_tools,
        )

        return self._convert_openai_response(response)

    def _convert_content_to_openai(
        self,
        content: List[Dict[str, Any]],
        role: str,
    ):
        """Convert Anthropic content to OpenAI format"""
        if role == "assistant":
            text_parts = []
            tool_calls = []

            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {})),
                        }
                    })

            result = {"role": "assistant", "content": " ".join(text_parts) if text_parts else None}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result

        elif role == "user":
            for block in content:
                if block.get("type") == "tool_result":
                    return {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": block.get("content", ""),
                    }

            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            return {"role": "user", "content": " ".join(text_parts)}

        return None

    def _convert_openai_response(self, response):
        """Convert OpenAI response to Anthropic format"""
        choice = response.choices[0] if response.choices else None
        if not choice:
            raise ValueError("No response from API")

        message = choice.message
        content = []

        if message.content:
            content.append(_MockBlock("text", text=message.content))

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    input_data = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    input_data = {}

                content.append(_MockBlock(
                    "tool_use",
                    id=tc.id,
                    name=tc.function.name,
                    input=input_data,
                ))

        return _MockResponse(content=content, stop_reason=choice.finish_reason)


# ============================================
# Mock Classes
# ============================================

class _MockBlock:
    """Mock content block"""
    def __init__(self, block_type: str, **kwargs):
        self.type = block_type
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockResponse:
    """Mock API response"""
    def __init__(self, content: List, stop_reason: str):
        self.content = content
        self.stop_reason = stop_reason
