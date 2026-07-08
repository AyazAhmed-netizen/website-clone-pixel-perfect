"""
Section Tools for Master Agent

Tools for analyzing page layout and managing section workers.

Features:
- Layout analysis from screenshots/DOM
- Section division
- Worker spawning
- Result merging
"""

from __future__ import annotations
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable

from ..worker_manager import (
    WorkerManager,
    WorkerManagerConfig,
    SectionTask,
    WorkerManagerResult,
    create_worker_manager,
)

logger = logging.getLogger(__name__)


# ============================================
# Tool Definitions
# ============================================

SECTION_TOOL_DEFINITIONS = [
    {
        "name": "analyze_page_layout",
        "description": """Analyze the page layout structure to understand sections and their arrangement.

Use this before dividing work into sections. Returns:
- Page sections identified
- Visual hierarchy
- Component relationships
- Recommended implementation order""",
        "input_schema": {
            "type": "object",
            "properties": {
                "screenshot_base64": {
                    "type": "string",
                    "description": "Base64 encoded screenshot of the page"
                },
                "dom_summary": {
                    "type": "string",
                    "description": "DOM structure summary (optional)"
                },
                "design_description": {
                    "type": "string",
                    "description": "Description of the design to implement"
                }
            },
            "required": ["design_description"]
        }
    },
    {
        "name": "spawn_section_workers",
        "description": """Spawn Worker Agents to implement multiple sections in parallel.

⚠️ CRITICAL: Use EXACT section_name from get_layout()!
✅ Use: "header", "section_1", "section_2", "footer"
❌ DON'T invent: "Features Grid", "Hero Section", "Stats"

Each worker:
- Gets its own isolated context
- Receives full section data (no compression)
- Implements only its assigned section
- Returns generated code files

Use this to parallelize implementation of independent sections.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "description": "List of sections to implement",
                    "items": {
                        "type": "object",
                        "properties": {
                            "section_name": {
                                "type": "string",
                                "description": "MUST use EXACT name from get_layout() (e.g., 'header', 'section_1', 'footer'). DO NOT invent names!"
                            },
                            "task_description": {
                                "type": "string",
                                "description": "What the worker should implement"
                            },
                            "design_requirements": {
                                "type": "string",
                                "description": "Design requirements and specifications"
                            },
                            "section_data_keys": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Keys from source data to include for this section"
                            },
                            "target_files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Files to generate (e.g., ['src/components/Header.tsx'])"
                            }
                        },
                        "required": ["section_name", "task_description"]
                    }
                },
                "shared_layout_context": {
                    "type": "string",
                    "description": "Layout context shared with all workers"
                },
                "shared_style_context": {
                    "type": "string",
                    "description": "Style guidelines shared with all workers"
                },
                "source_id": {
                    "type": "string",
                    "description": "JSON source ID to query for section data"
                },
                "max_concurrent": {
                    "type": "integer",
                    "description": "Maximum concurrent workers (0 = unlimited, default: 0)",
                    "default": 0
                }
            },
            "required": ["sections"]
        }
    },
    {
        "name": "get_section_data",
        "description": """Get data for a specific section from the source.

Returns the full data for the specified keys, ready to pass to a worker.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "JSON source ID"
                },
                "data_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keys to extract (e.g., ['navigation', 'hero'])"
                }
            },
            "required": ["source_id", "data_keys"]
        }
    },
    {
        "name": "merge_worker_results",
        "description": """Merge code files from worker results and write them to WebContainer.

Use after spawn_section_workers completes to apply all generated code.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "worker_result_id": {
                    "type": "string",
                    "description": "ID of the worker result to merge"
                },
                "apply_to_webcontainer": {
                    "type": "boolean",
                    "description": "Whether to write files to WebContainer",
                    "default": True
                }
            },
            "required": ["worker_result_id"]
        }
    }
]


# ============================================
# Section Tool Executor
# ============================================

class SectionToolExecutor:
    """
    Executor for section-related tools

    Handles:
    - Layout analysis
    - Worker spawning
    - Data fetching
    - Result merging
    """

    def __init__(
        self,
        source_data: Optional[Dict[str, Any]] = None,
        on_file_write: Optional[Callable[[str, str], Awaitable[None]]] = None,
        on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ):
        """
        Initialize executor

        Args:
            source_data: Source data for sections (if pre-loaded)
            on_file_write: Callback for writing files
            on_progress: Callback for progress updates
        """
        self.source_data = source_data or {}
        self.on_file_write = on_file_write
        self.on_progress = on_progress

        # Store worker results
        self._worker_results: Dict[str, WorkerManagerResult] = {}
        self._result_counter = 0

    # ============================================
    # Tool Execution
    # ============================================

    async def execute(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a section tool

        Args:
            tool_name: Tool name
            tool_input: Tool input

        Returns:
            Tool result
        """
        try:
            if tool_name == "analyze_page_layout":
                return await self._analyze_layout(tool_input)

            elif tool_name == "spawn_section_workers":
                return await self._spawn_workers(tool_input)

            elif tool_name == "get_section_data":
                return await self._get_section_data(tool_input)

            elif tool_name == "merge_worker_results":
                return await self._merge_results(tool_input)

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Section tool error: {e}", exc_info=True)
            return {"error": str(e)}

    # ============================================
    # Tool Implementations
    # ============================================

    async def _analyze_layout(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze page layout

        This is primarily handled by the LLM itself using visual understanding.
        This tool provides structure for the response.
        """
        design_description = input_data.get("design_description", "")
        screenshot = input_data.get("screenshot_base64")
        dom_summary = input_data.get("dom_summary")

        # Return analysis structure
        return {
            "success": True,
            "message": "Layout analysis ready. Based on the design, identify the main sections.",
            "suggested_sections": [
                "Header/Navigation",
                "Hero Section",
                "Features Section",
                "Content Sections",
                "Footer"
            ],
            "analysis_tips": [
                "Look for clear visual boundaries",
                "Identify repeating patterns (cards, lists)",
                "Note the visual hierarchy",
                "Check for responsive considerations"
            ],
            "has_screenshot": screenshot is not None,
            "has_dom": dom_summary is not None,
        }

    async def _spawn_workers(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Spawn workers for sections with TaskContract support
        """
        sections = input_data.get("sections", [])
        if not sections:
            return {"error": "No sections provided"}

        source_id = input_data.get("source_id")
        shared_layout = input_data.get("shared_layout_context", "")
        shared_style = input_data.get("shared_style_context", "")
        max_concurrent = input_data.get("max_concurrent", 0)  # 0 = unlimited

        # Load source data if needed
        if source_id and not self.source_data:
            self.source_data = await self._load_source_data(source_id)

        # Create section tasks
        tasks: List[SectionTask] = []

        for section in sections:
            section_name = section.get("section_name", "Unknown")
            data_keys = section.get("section_data_keys", [])

            # Extract section-specific data
            section_data = {}
            for key in data_keys:
                if key in self.source_data:
                    section_data[key] = self.source_data[key]

            # Get TaskContract data if available (NEW)
            task_contract = section.get("_task_contract", {})
            namespace = task_contract.get("worker_namespace", "")
            if not namespace:
                # Generate namespace from section_name
                namespace = section_name.replace("-", "_").replace(".", "_").replace(" ", "_").lower()

            base_path = task_contract.get("scope", {}).get("base_path", "/src/components/sections")

            tasks.append(SectionTask(
                section_name=section_name,
                task_description=section.get("task_description", f"Implement {section_name}"),
                design_requirements=section.get("design_requirements", ""),
                section_data=section_data,
                target_files=section.get("target_files", []),
                layout_context=shared_layout,
                style_context=shared_style,
                # TaskContract path isolation
                worker_namespace=namespace,
                base_path=base_path,
            ))

        # Create and run manager
        manager = create_worker_manager(max_concurrent=max_concurrent)

        if self.on_progress:
            manager.on_progress = self.on_progress

        # Notify start
        if self.on_progress:
            await self.on_progress("workers", f"spawning {len(tasks)} workers")

        # Run workers
        result = await manager.run_workers(tasks)

        # Store result
        self._result_counter += 1
        result_id = f"result_{self._result_counter}"
        self._worker_results[result_id] = result

        # AUTO-WRITE: Write worker-generated files to WebContainer immediately
        # 自动写入：立即将Worker生成的文件写入WebContainer
        written_files = []
        if self.on_file_write and result.files:
            logger.info(f"Auto-writing {len(result.files)} files from workers to WebContainer")
            for path, content in result.files.items():
                try:
                    await self.on_file_write(path, content)
                    written_files.append(path)
                    logger.debug(f"Auto-wrote file: {path} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Failed to auto-write {path}: {e}")

        # Build response - Worker code is already written, no need for Main Agent to write again
        # 构建响应 - Worker代码已自动写入，主Agent不需要再写一遍

        # Determine next required action based on results
        # 根据结果确定下一步必须执行的操作
        has_errors = result.failed_workers > 0
        error_sections = [r.section_name for r in result.worker_results if not r.success]

        return {
            "success": result.success,
            "result_id": result_id,
            "total_workers": result.total_workers,
            "successful_workers": result.successful_workers,
            "failed_workers": result.failed_workers,
            "files_generated": len(result.files),
            "files_written": written_files,  # Files already written to WebContainer
            "errors": result.errors,
            "duration_ms": result.total_duration_ms,

            # ⚠️ CRITICAL: These fields tell Claude what to do next
            # ⚠️ 关键：这些字段告诉 Claude 下一步必须做什么
            "task_status": "WORKERS_COMPLETED_VERIFICATION_REQUIRED",
            "is_task_complete": False,  # 明确告诉 Claude：任务未完成！

            "REQUIRED_NEXT_ACTIONS": [
                "1. ⏳ WAIT: Wait 3-5 seconds for dev server HMR to reload new files",
                "2. 🔍 CHECK ERRORS: Call get_build_errors() to detect compilation errors",
                "3. 🔄 FIX IF NEEDED: If errors found, fix them and call get_build_errors() again",
            ],

            "warning": "⛔ DO NOT STOP HERE! Workers finishing ≠ Task complete. You MUST check for errors!",

            "message": (
                f"📦 Workers Phase Complete: {result.successful_workers}/{result.total_workers} succeeded, "
                f"{len(written_files)} files written.\n\n"
                f"⚠️ IMPORTANT: This is NOT the end! You must now:\n"
                f"1. Wait 3-5 seconds for HMR to reload\n"
                f"2. Call get_build_errors() to check for compilation errors\n"
                f"3. Fix any errors found\n\n"
                f"DO NOT stop until you have verified there are no build errors!"
            ),

            "worker_summaries": [
                {
                    "section": r.section_name,
                    "success": r.success,
                    "files": list(r.files.keys()),
                    "summary": r.summary,
                    "error": r.error,
                }
                for r in result.worker_results
            ],

            # Error recovery info
            "failed_sections": error_sections if has_errors else [],
            "recovery_hint": f"Failed sections: {', '.join(error_sections)}. Use read_file and edit_file to fix errors. Do NOT re-spawn workers." if has_errors else None,
        }

    async def _get_section_data(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get section data from source
        """
        source_id = input_data.get("source_id")
        data_keys = input_data.get("data_keys", [])

        # Load source if needed
        if source_id and not self.source_data:
            self.source_data = await self._load_source_data(source_id)

        # Extract requested data
        result_data = {}
        for key in data_keys:
            if key in self.source_data:
                result_data[key] = self.source_data[key]

        return {
            "success": True,
            "data": result_data,
            "keys_found": list(result_data.keys()),
            "keys_missing": [k for k in data_keys if k not in self.source_data],
        }

    async def _merge_results(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge worker results and optionally write to WebContainer
        """
        result_id = input_data.get("worker_result_id")
        apply_to_wc = input_data.get("apply_to_webcontainer", True)

        if result_id not in self._worker_results:
            return {"error": f"Result not found: {result_id}"}

        result = self._worker_results[result_id]

        # Write files if requested
        written_files = []
        if apply_to_wc and self.on_file_write:
            for path, content in result.files.items():
                try:
                    await self.on_file_write(path, content)
                    written_files.append(path)
                except Exception as e:
                    logger.error(f"Failed to write {path}: {e}")

        return {
            "success": True,
            "total_files": len(result.files),
            "written_files": written_files,
            "files": {
                path: {
                    "lines": len(content.split("\n")),
                    "chars": len(content),
                }
                for path, content in result.files.items()
            }
        }

    # ============================================
    # Helper Methods
    # ============================================

    async def _load_source_data(self, source_id: str) -> Dict[str, Any]:
        """Load source data from memory cache"""
        try:
            from cache.memory_store import extraction_cache

            entry = extraction_cache.get(source_id)

            if entry:
                return entry.data or {}

        except Exception as e:
            logger.error(f"Failed to load source: {e}")

        return {}

    def set_source_data(self, data: Dict[str, Any]):
        """Set source data directly"""
        self.source_data = data

    def get_worker_result(self, result_id: str) -> Optional[WorkerManagerResult]:
        """Get stored worker result"""
        return self._worker_results.get(result_id)


# ============================================
# Factory Functions
# ============================================

def create_section_executor(
    source_data: Optional[Dict[str, Any]] = None,
    on_file_write: Optional[Callable[[str, str], Awaitable[None]]] = None,
    on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> SectionToolExecutor:
    """
    Create a section tool executor

    Args:
        source_data: Pre-loaded source data
        on_file_write: Callback for writing files
        on_progress: Callback for progress updates

    Returns:
        Configured SectionToolExecutor
    """
    return SectionToolExecutor(
        source_data=source_data,
        on_file_write=on_file_write,
        on_progress=on_progress,
    )


def get_section_tool_definitions() -> List[Dict[str, Any]]:
    """Get section tool definitions"""
    return SECTION_TOOL_DEFINITIONS
