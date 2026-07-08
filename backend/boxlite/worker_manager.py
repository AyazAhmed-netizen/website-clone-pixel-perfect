"""
BoxLite Worker Manager

Manages multiple Worker Agents for parallel task execution in BoxLite sandbox.

Key features:
- Parallel worker execution with shared sandbox
- Concurrency control (semaphore)
- Result collection
- WebSocket event emission for UI visibility

Key differences from WebContainer Worker Manager:
- Workers share same BoxLite sandbox instance
- Tools execute directly on backend (no file collection)
- Concurrent-safe file operations
"""

from __future__ import annotations
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

from .worker_agent import (
    BoxLiteWorkerAgent,
    BoxLiteWorkerConfig,
    BoxLiteWorkerResult,
)
from .sandbox_manager import BoxLiteSandboxManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================
# Manager Configuration
# ============================================

@dataclass
class BoxLiteWorkerManagerConfig:
    """Worker Manager configuration"""
    # Maximum concurrent workers (0 = unlimited)
    max_concurrent: int = 0

    # Timeout per worker (seconds)
    worker_timeout: float = 600.0  # 10 minutes default

    # Whether to continue on worker failure
    continue_on_failure: bool = True


@dataclass
class BoxLiteTask:
    """
    Task definition for BoxLite worker
    """
    # Task identification
    task_id: str
    task_name: str

    # Task description (what to do)
    task_description: str

    # Context data for the task
    context_data: Dict[str, Any] = field(default_factory=dict)

    # Target files (informational)
    target_files: List[str] = field(default_factory=list)

    # Display name for UI
    display_name: str = ""


@dataclass
class BoxLiteWorkerManagerResult:
    """Combined result from all workers"""
    # Overall status
    success: bool
    total_workers: int
    successful_workers: int
    failed_workers: int

    # All files created/modified (path -> content)
    # Files are stored in memory, not yet written to sandbox
    files: Dict[str, str] = field(default_factory=dict)

    # Individual worker results
    worker_results: List[BoxLiteWorkerResult] = field(default_factory=list)

    # Errors from failed workers
    errors: List[str] = field(default_factory=list)

    # Timing
    total_duration_ms: int = 0


# ============================================
# Event Sender Type
# ============================================

EventSender = Callable[[Dict[str, Any]], Awaitable[None]]


# ============================================
# BoxLite Worker Manager
# ============================================

class BoxLiteWorkerManager:
    """
    BoxLite Worker Manager

    Orchestrates multiple Worker Agents:
    - Creates workers from tasks
    - Runs workers in parallel with concurrency control
    - Collects results
    - Emits WebSocket events for visibility
    """

    def __init__(
        self,
        sandbox: BoxLiteSandboxManager,
        send_event: Optional[EventSender] = None,
        config: Optional[BoxLiteWorkerManagerConfig] = None,
    ):
        """
        Initialize BoxLite Worker Manager

        Args:
            sandbox: Shared BoxLite sandbox manager
            send_event: Async function to send WebSocket events
            config: Manager configuration
        """
        self.sandbox = sandbox
        self.send_event = send_event
        self.config = config or BoxLiteWorkerManagerConfig()

        # Concurrency control
        effective_concurrent = self.config.max_concurrent if self.config.max_concurrent > 0 else 10000
        self.semaphore = asyncio.Semaphore(effective_concurrent)

        concurrent_info = "unlimited" if self.config.max_concurrent <= 0 else str(self.config.max_concurrent)
        logger.info(f"BoxLiteWorkerManager initialized: max_concurrent={concurrent_info}")

    # ============================================
    # Main Entry Point
    # ============================================

    async def run_workers(
        self,
        tasks: List[BoxLiteTask],
    ) -> BoxLiteWorkerManagerResult:
        """
        Run workers for all tasks

        Args:
            tasks: List of tasks to execute

        Returns:
            Combined result from all workers
        """
        if not tasks:
            return BoxLiteWorkerManagerResult(
                success=True,
                total_workers=0,
                successful_workers=0,
                failed_workers=0,
            )

        start_time = datetime.now()

        logger.info(f"Starting {len(tasks)} workers: {[t.task_name for t in tasks]}")

        # Create worker configs
        worker_configs = [
            self._create_worker_config(task, i)
            for i, task in enumerate(tasks)
        ]

        # Run workers in parallel
        results = await self._run_parallel(worker_configs)

        # Merge results
        merged_result = self._merge_results(results)

        # Add timing
        merged_result.total_duration_ms = int(
            (datetime.now() - start_time).total_seconds() * 1000
        )

        logger.info(
            f"Workers completed: {merged_result.successful_workers}/{merged_result.total_workers} successful, "
            f"{len(merged_result.files)} files, "
            f"duration={merged_result.total_duration_ms}ms"
        )

        return merged_result

    # ============================================
    # Worker Creation
    # ============================================

    def _create_worker_config(
        self,
        task: BoxLiteTask,
        index: int,
    ) -> BoxLiteWorkerConfig:
        """Create worker config from task"""
        return BoxLiteWorkerConfig(
            worker_id=f"worker_{index}_{task.task_id}",
            section_name=task.task_name,
            task_description=task.task_description,
            context_data=task.context_data,
            target_files=task.target_files,
            display_name=task.display_name or task.task_name,
        )

    # ============================================
    # Parallel Execution
    # ============================================

    async def _run_parallel(
        self,
        configs: List[BoxLiteWorkerConfig],
    ) -> List[BoxLiteWorkerResult]:
        """Run workers in parallel with concurrency control"""
        total_workers = len(configs)

        async def run_worker_with_semaphore(config: BoxLiteWorkerConfig) -> BoxLiteWorkerResult:
            """Run a single worker with semaphore"""
            async with self.semaphore:
                return await self._run_single_worker(config, total_workers)

        # Create tasks
        tasks = [
            asyncio.create_task(run_worker_with_semaphore(config))
            for config in configs
        ]

        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(BoxLiteWorkerResult(
                    worker_id=configs[i].worker_id,
                    section_name=configs[i].section_name,
                    success=False,
                    error=str(result),
                ))
            else:
                processed_results.append(result)

        return processed_results

    async def _run_single_worker(
        self,
        config: BoxLiteWorkerConfig,
        total_workers: int,
    ) -> BoxLiteWorkerResult:
        """Run a single worker with timeout and event emission"""
        logger.info(f"Starting worker: {config.worker_id} for '{config.section_name}'")

        # Emit worker spawned event
        await self._emit_worker_spawned(config, total_workers)

        try:
            # Emit worker started event
            await self._emit_worker_started(config)

            # Create callbacks for tool events
            on_tool_call = self._create_tool_call_callback()
            on_tool_result = self._create_tool_result_callback()
            on_iteration = self._create_iteration_callback()
            on_text_delta = self._create_text_delta_callback()
            on_file_written = self._create_file_written_callback()  # NEW

            # Create worker with shared sandbox and callbacks
            worker = BoxLiteWorkerAgent(
                config,
                sandbox=self.sandbox,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_iteration=on_iteration,
                on_text_delta=on_text_delta,
                on_file_written=on_file_written,  # NEW: real-time file sync
            )

            # Run with timeout
            result = await asyncio.wait_for(
                worker.run(),
                timeout=self.config.worker_timeout,
            )

            # Emit worker completed event
            await self._emit_worker_completed(config, result)

            logger.info(
                f"Worker {config.worker_id} completed: success={result.success}, "
                f"files={len(result.files)}, iterations={result.iterations}"
            )

            return result

        except asyncio.TimeoutError:
            logger.error(f"Worker {config.worker_id} timed out after {self.config.worker_timeout}s")

            error_msg = f"Worker timed out after {self.config.worker_timeout}s"
            await self._emit_worker_error(config, error_msg)

            return BoxLiteWorkerResult(
                worker_id=config.worker_id,
                section_name=config.section_name,
                success=False,
                error=error_msg,
            )

        except Exception as e:
            logger.error(f"Worker {config.worker_id} error: {e}", exc_info=True)

            await self._emit_worker_error(config, str(e))

            return BoxLiteWorkerResult(
                worker_id=config.worker_id,
                section_name=config.section_name,
                success=False,
                error=str(e),
            )

    # ============================================
    # WebSocket Event Emission
    # ============================================

    def _create_tool_call_callback(self):
        """Create callback for worker tool calls"""
        async def callback(worker_id: str, section_name: str, tool_name: str, tool_input: Dict[str, Any]):
            if self.send_event:
                try:
                    await self.send_event({
                        "type": "worker_tool_call",
                        "payload": {
                            "worker_id": worker_id,
                            "section_name": section_name,
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit tool call event: {e}")
        return callback

    def _create_tool_result_callback(self):
        """Create callback for worker tool results"""
        async def callback(worker_id: str, section_name: str, tool_name: str, result: str, success: bool):
            if self.send_event:
                try:
                    await self.send_event({
                        "type": "worker_tool_result",
                        "payload": {
                            "worker_id": worker_id,
                            "section_name": section_name,
                            "tool_name": tool_name,
                            "result": result,
                            "success": success,
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit tool result event: {e}")
        return callback

    def _create_iteration_callback(self):
        """Create callback for worker iteration events"""
        async def callback(worker_id: str, section_name: str, iteration: int, max_iterations: int):
            if self.send_event:
                try:
                    await self.send_event({
                        "type": "worker_iteration",
                        "payload": {
                            "worker_id": worker_id,
                            "section_name": section_name,
                            "iteration": iteration,
                            "max_iterations": max_iterations,
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit iteration event: {e}")
        return callback

    def _create_text_delta_callback(self):
        """Create callback for worker text delta events"""
        async def callback(worker_id: str, section_name: str, text: str, iteration: int):
            if self.send_event:
                try:
                    await self.send_event({
                        "type": "worker_text_delta",
                        "payload": {
                            "worker_id": worker_id,
                            "section_name": section_name,
                            "text": text,
                            "iteration": iteration,
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit text delta event: {e}")
        return callback

    def _create_file_written_callback(self):
        """
        Create callback for real-time file written events.

        This sends file_written to frontend immediately when a worker writes a file,
        so the file tree and editor can update in real-time.
        """
        async def callback(worker_id: str, path: str, content: str):
            if self.send_event:
                try:
                    # Send file_written event
                    await self.send_event({
                        "type": "file_written",
                        "payload": {
                            "worker_id": worker_id,
                            "path": path,
                            "content": content,
                            "size": len(content),
                        }
                    })

                    # Also send state_update so file tree updates
                    state_dict = self.sandbox.get_state_dict()
                    await self.send_event({
                        "type": "state_update",
                        "payload": state_dict
                    })

                    logger.info(f"[WorkerManager] Sent file_written + state_update: {path}")
                except Exception as e:
                    logger.warning(f"Failed to emit file_written event: {e}")
        return callback

    async def _emit_worker_spawned(self, config: BoxLiteWorkerConfig, total_workers: int):
        """Emit worker spawned event"""
        if self.send_event:
            try:
                # Extract section data from context for detailed event info
                section_data = config.context_data.get("section_data", {})
                raw_html = section_data.get("raw_html", "")
                html_lines = raw_html.count('\n') + 1 if raw_html else 0
                html_chars = len(raw_html) if raw_html else 0

                # Get html_range info
                html_range = section_data.get("html_range", {})
                start_line = html_range.get("start_line", 0)
                end_line = html_range.get("end_line", 0)
                char_start = html_range.get("char_start", 0)
                char_end = html_range.get("char_end", 0)

                # Estimate tokens (approx 4 chars per token)
                estimated_tokens = html_chars // 4 if html_chars else 0

                input_summary = {
                    "section_data_keys": list(section_data.keys()) if section_data else list(config.context_data.keys()),
                    "target_files": config.target_files,
                    "has_layout_context": bool(section_data.get("styles", {}).get("layout")),
                    "has_style_context": bool(section_data.get("styles")),
                    # Data size info for UI display
                    "html_lines": html_lines,
                    "html_chars": html_chars,
                    "html_range": {"start": start_line, "end": end_line} if start_line or end_line else None,
                    "char_start": char_start,
                    "char_end": char_end,
                    "estimated_tokens": estimated_tokens,
                    "images_count": len(section_data.get("images", [])),
                    "links_count": len(section_data.get("links", [])),
                }
                await self.send_event({
                    "type": "worker_spawned",
                    "payload": {
                        "worker_id": config.worker_id,
                        "section_name": config.section_name,
                        "display_name": config.display_name,
                        "task_description": config.task_description[:200],
                        "input_data": input_summary,
                        "total_workers": total_workers,
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to emit worker spawned event: {e}")

    async def _emit_worker_started(self, config: BoxLiteWorkerConfig):
        """Emit worker started event"""
        if self.send_event:
            try:
                await self.send_event({
                    "type": "worker_started",
                    "payload": {
                        "worker_id": config.worker_id,
                        "section_name": config.section_name,
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to emit worker started event: {e}")

    async def _emit_worker_completed(self, config: BoxLiteWorkerConfig, result: BoxLiteWorkerResult):
        """Emit worker completed event"""
        if self.send_event:
            try:
                await self.send_event({
                    "type": "worker_completed",
                    "payload": {
                        "worker_id": config.worker_id,
                        "section_name": config.section_name,
                        "success": result.success,
                        "files": result.files,
                        "file_count": len(result.files),
                        "summary": result.summary,
                        "error": result.error,
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to emit worker completed event: {e}")

    async def _emit_worker_error(self, config: BoxLiteWorkerConfig, error: str):
        """Emit worker error event"""
        if self.send_event:
            try:
                await self.send_event({
                    "type": "worker_error",
                    "payload": {
                        "worker_id": config.worker_id,
                        "section_name": config.section_name,
                        "error": error,
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to emit worker error event: {e}")

    # ============================================
    # Result Merging
    # ============================================

    def _merge_results(self, results: List[BoxLiteWorkerResult]) -> BoxLiteWorkerManagerResult:
        """Merge results from all workers"""
        all_files: Dict[str, str] = {}  # path -> content
        errors: List[str] = []
        successful_count = 0
        failed_count = 0

        logger.info(f"[_merge_results] Merging {len(results)} worker results")

        for result in results:
            logger.info(f"[_merge_results] Worker {result.worker_id}: success={result.success}, files_type={type(result.files)}")

            if result.success:
                successful_count += 1
                # Merge file dictionaries (path -> content)
                if isinstance(result.files, dict):
                    logger.info(f"[_merge_results] Worker {result.worker_id} has {len(result.files)} files: {list(result.files.keys())}")
                    all_files.update(result.files)
                else:
                    # Backward compatibility: if files is a list, log warning
                    logger.warning(f"[_merge_results] Worker {result.worker_id} returned files as list instead of dict: {result.files}")
            else:
                failed_count += 1
                if result.error:
                    errors.append(f"[{result.section_name}] {result.error}")
                logger.warning(f"[_merge_results] Worker {result.worker_id} failed: {result.error}")

        logger.info(f"[_merge_results] Total merged files: {len(all_files)}, paths: {list(all_files.keys())}")

        return BoxLiteWorkerManagerResult(
            success=failed_count == 0 or self.config.continue_on_failure,
            total_workers=len(results),
            successful_workers=successful_count,
            failed_workers=failed_count,
            files=all_files,
            worker_results=results,
            errors=errors,
        )


# ============================================
# Factory Functions
# ============================================

def create_worker_manager(
    sandbox: BoxLiteSandboxManager,
    send_event: Optional[EventSender] = None,
    max_concurrent: int = 0,
    worker_timeout: float = 600.0,
    continue_on_failure: bool = True,
) -> BoxLiteWorkerManager:
    """
    Create a BoxLite Worker Manager

    Args:
        sandbox: Shared BoxLite sandbox manager
        send_event: Async function to send WebSocket events
        max_concurrent: Maximum concurrent workers (0 = unlimited)
        worker_timeout: Timeout per worker in seconds
        continue_on_failure: Whether to continue on worker failure

    Returns:
        Configured BoxLiteWorkerManager
    """
    config = BoxLiteWorkerManagerConfig(
        max_concurrent=max_concurrent,
        worker_timeout=worker_timeout,
        continue_on_failure=continue_on_failure,
    )
    return BoxLiteWorkerManager(
        sandbox=sandbox,
        send_event=send_event,
        config=config,
    )


# ============================================
# Convenience Functions
# ============================================

async def run_boxlite_workers(
    sandbox: BoxLiteSandboxManager,
    tasks: List[BoxLiteTask],
    send_event: Optional[EventSender] = None,
    max_concurrent: int = 0,
) -> BoxLiteWorkerManagerResult:
    """
    Run BoxLite workers for tasks (convenience function)

    Args:
        sandbox: Shared BoxLite sandbox manager
        tasks: List of tasks to execute
        send_event: Async function to send WebSocket events
        max_concurrent: Maximum concurrent workers (0 = unlimited)

    Returns:
        Combined result from all workers
    """
    manager = create_worker_manager(
        sandbox=sandbox,
        send_event=send_event,
        max_concurrent=max_concurrent,
    )

    return await manager.run_workers(tasks)
