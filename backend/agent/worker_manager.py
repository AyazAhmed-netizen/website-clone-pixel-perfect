"""
Worker Manager

Manages multiple Worker Agents for parallel section implementation.

Features:
- Parallel worker execution
- Concurrency control (semaphore)
- Result collection and merging
- WebSocket event emission for debugging/visibility
"""

from __future__ import annotations
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

from .worker_agent import WorkerAgent, WorkerConfig, WorkerResult

if TYPE_CHECKING:
    from .websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


# ============================================
# Manager Configuration
# ============================================

@dataclass
class WorkerManagerConfig:
    """
    Worker Manager configuration

    Controls how workers are spawned and managed.
    """
    # Maximum concurrent workers (0 = unlimited)
    max_concurrent: int = 0

    # Timeout per worker (seconds) - increased for complex sections
    worker_timeout: float = 1200.0  # 20 minutes default

    # Whether to continue on worker failure
    continue_on_failure: bool = True


@dataclass
class SectionTask:
    """
    Section task definition

    Defines a single section to be implemented by a Worker.
    """
    section_name: str
    task_description: str
    design_requirements: str
    section_data: Dict[str, Any] = field(default_factory=dict)
    target_files: List[str] = field(default_factory=list)
    layout_context: str = ""
    style_context: str = ""

    # TaskContract-based path isolation (NEW)
    worker_namespace: str = ""  # e.g., "header_0", "hero_0"
    base_path: str = "/src/components/sections"
    task_contract_prompt: str = ""  # If provided, overrides default prompt

    # Display name for UI (human-friendly, e.g., "Navigation", "Section 1")
    display_name: str = ""


@dataclass
class WorkerManagerResult:
    """
    Combined result from all workers

    Aggregates results from all workers.
    """
    # Overall status
    success: bool
    total_workers: int
    successful_workers: int
    failed_workers: int

    # Combined files from all workers (path -> content)
    files: Dict[str, str] = field(default_factory=dict)

    # Individual worker results
    worker_results: List[WorkerResult] = field(default_factory=list)

    # Errors from failed workers
    errors: List[str] = field(default_factory=list)

    # Timing
    total_duration_ms: int = 0


# ============================================
# Worker Manager
# ============================================

class WorkerManager:
    """
    Worker Manager

    Orchestrates multiple Worker Agents:
    - Creates workers from section tasks
    - Runs workers in parallel with concurrency control
    - Collects and merges results
    - Emits WebSocket events for visibility/debugging
    """

    def __init__(
        self,
        config: Optional[WorkerManagerConfig] = None,
        ws_manager: Optional["WebSocketManager"] = None,
        session_id: Optional[str] = None,
    ):
        """
        Initialize Worker Manager

        Args:
            config: Manager configuration
            ws_manager: WebSocket manager for emitting events
            session_id: Session ID for WebSocket events
        """
        self.config = config or WorkerManagerConfig()

        # WebSocket for event emission
        self.ws_manager = ws_manager
        self.session_id = session_id

        # Semaphore for concurrency control (0 = unlimited, use large number)
        # When max_concurrent <= 0, allow unlimited parallelism
        effective_concurrent = self.config.max_concurrent if self.config.max_concurrent > 0 else 10000
        self.semaphore = asyncio.Semaphore(effective_concurrent)

        # Progress callback (legacy)
        self.on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None

        concurrent_info = "unlimited" if self.config.max_concurrent <= 0 else str(self.config.max_concurrent)
        logger.info(f"WorkerManager initialized: max_concurrent={concurrent_info}")

    # ============================================
    # Main Entry Point
    # ============================================

    async def run_workers(
        self,
        tasks: List[SectionTask],
        shared_context: Optional[Dict[str, Any]] = None,
    ) -> WorkerManagerResult:
        """
        Run workers for all section tasks

        Args:
            tasks: List of section tasks to implement
            shared_context: Optional shared context for all workers

        Returns:
            Combined result from all workers
        """
        if not tasks:
            return WorkerManagerResult(
                success=True,
                total_workers=0,
                successful_workers=0,
                failed_workers=0,
            )

        start_time = datetime.now()
        shared_context = shared_context or {}

        logger.info(f"Starting {len(tasks)} workers for sections: {[t.section_name for t in tasks]}")

        # Create worker configs
        worker_configs = [
            self._create_worker_config(task, i, shared_context)
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
            f"{len(merged_result.files)} files generated, "
            f"duration={merged_result.total_duration_ms}ms"
        )

        return merged_result

    # ============================================
    # Worker Creation
    # ============================================

    def _create_worker_config(
        self,
        task: SectionTask,
        index: int,
        shared_context: Dict[str, Any],
    ) -> WorkerConfig:
        """Create worker config from section task with namespace isolation"""
        # Generate namespace from section_name if not provided
        namespace = task.worker_namespace
        if not namespace:
            namespace = task.section_name.replace("-", "_").replace(".", "_").replace(" ", "_").lower()

        return WorkerConfig(
            worker_id=f"worker_{index}_{task.section_name}",
            section_name=task.section_name,
            task_description=task.task_description,
            design_requirements=task.design_requirements,
            section_data=task.section_data,
            layout_context=task.layout_context or shared_context.get("layout_context", ""),
            style_context=task.style_context or shared_context.get("style_context", ""),
            target_files=task.target_files,
            # TaskContract path isolation
            worker_namespace=namespace,
            base_path=task.base_path,
            task_contract_prompt=task.task_contract_prompt,
            # Display name for UI
            display_name=task.display_name or task.section_name,
        )

    # ============================================
    # Parallel Execution
    # ============================================

    async def _run_parallel(
        self,
        configs: List[WorkerConfig],
    ) -> List[WorkerResult]:
        """Run workers in parallel with concurrency control"""
        total_workers = len(configs)

        async def run_worker_with_semaphore(config: WorkerConfig) -> WorkerResult:
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
                # Convert exception to failed result
                processed_results.append(WorkerResult(
                    worker_id=configs[i].worker_id,
                    section_name=configs[i].section_name,
                    success=False,
                    error=str(result),
                ))
            else:
                processed_results.append(result)

        return processed_results

    async def _run_single_worker(self, config: WorkerConfig, total_workers: int) -> WorkerResult:
        """Run a single worker with timeout and event emission"""
        logger.info(f"Starting worker: {config.worker_id} for section '{config.section_name}'")

        # Emit worker spawned event
        await self._emit_worker_spawned(config, total_workers)

        # Notify progress (legacy)
        if self.on_progress:
            await self.on_progress(config.section_name, "started")

        try:
            # Emit worker started event
            await self._emit_worker_started(config)

            # Create callbacks for tool events
            on_tool_call = self._create_tool_call_callback()
            on_tool_result = self._create_tool_result_callback()
            on_iteration = self._create_iteration_callback()
            on_text_delta = self._create_text_delta_callback()

            # Create worker with callbacks
            worker = WorkerAgent(
                config,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_iteration=on_iteration,
                on_text_delta=on_text_delta,
            )

            # Run with timeout
            result = await asyncio.wait_for(
                worker.run(),
                timeout=self.config.worker_timeout,
            )

            # Emit worker completed event
            await self._emit_worker_completed(config, result)

            # Notify progress (legacy)
            if self.on_progress:
                status = "completed" if result.success else "failed"
                await self.on_progress(config.section_name, status)

            logger.info(
                f"Worker {config.worker_id} completed: success={result.success}, "
                f"files={len(result.files)}, iterations={result.iterations}"
            )

            return result

        except asyncio.TimeoutError:
            logger.error(f"Worker {config.worker_id} timed out after {self.config.worker_timeout}s")

            error_msg = f"Worker timed out after {self.config.worker_timeout}s"

            # Emit error event
            await self._emit_worker_error(config, error_msg)

            if self.on_progress:
                await self.on_progress(config.section_name, "timeout")

            return WorkerResult(
                worker_id=config.worker_id,
                section_name=config.section_name,
                success=False,
                error=error_msg,
            )

        except Exception as e:
            logger.error(f"Worker {config.worker_id} error: {e}", exc_info=True)

            # Emit error event
            await self._emit_worker_error(config, str(e))

            if self.on_progress:
                await self.on_progress(config.section_name, "error")

            return WorkerResult(
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
            if self.ws_manager and self.session_id:
                try:
                    await self.ws_manager.send_worker_tool_call(
                        self.session_id,
                        worker_id,
                        section_name,
                        tool_name,
                        tool_input,
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit tool call event: {e}")
        return callback

    def _create_tool_result_callback(self):
        """Create callback for worker tool results"""
        async def callback(worker_id: str, section_name: str, tool_name: str, result: str, success: bool):
            if self.ws_manager and self.session_id:
                try:
                    await self.ws_manager.send_worker_tool_result(
                        self.session_id,
                        worker_id,
                        section_name,
                        tool_name,
                        result,
                        success,
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit tool result event: {e}")
        return callback

    def _create_iteration_callback(self):
        """Create callback for worker iteration events"""
        async def callback(worker_id: str, section_name: str, iteration: int, max_iterations: int):
            if self.ws_manager and self.session_id:
                try:
                    await self.ws_manager.send_worker_iteration(
                        self.session_id,
                        worker_id,
                        section_name,
                        iteration,
                        max_iterations,
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit iteration event: {e}")
        return callback

    def _create_text_delta_callback(self):
        """Create callback for worker text delta events"""
        async def callback(worker_id: str, section_name: str, text: str, iteration: int):
            if self.ws_manager and self.session_id:
                try:
                    await self.ws_manager.send_worker_text_delta(
                        self.session_id,
                        worker_id,
                        section_name,
                        text,
                        iteration,
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit text delta event: {e}")
        return callback

    async def _emit_worker_spawned(self, config: WorkerConfig, total_workers: int):
        """Emit worker spawned event"""
        if self.ws_manager and self.session_id:
            try:
                # Calculate HTML lines received (from actual raw_html being sent to worker)
                raw_html = config.section_data.get("raw_html", "")
                html_lines = raw_html.count('\n') + 1 if raw_html else 0
                html_chars = len(raw_html) if raw_html else 0

                # Get html_range info
                html_range = config.section_data.get("html_range", {})
                start_line = html_range.get("start_line", 0)
                end_line = html_range.get("end_line", 0)
                char_start = html_range.get("char_start", 0)
                char_end = html_range.get("char_end", 0)

                # Use estimated_tokens from Playwright analysis if available
                # (this is based on cleaned HTML, not raw char range)
                # Otherwise, estimate from actual raw_html length
                playwright_tokens = html_range.get("estimated_tokens", 0)
                if playwright_tokens > 0 and html_chars > 50000:
                    # For large components, Playwright may have cleaned media content
                    # but if raw_html is still large, use actual size (media cleanup in spawn_section_workers)
                    estimated_tokens = html_chars // 4
                elif playwright_tokens > 0:
                    estimated_tokens = playwright_tokens
                else:
                    estimated_tokens = html_chars // 4 if html_chars else 0

                # Summarize input data for visibility
                input_summary = {
                    "section_data_keys": list(config.section_data.keys()),
                    "target_files": config.target_files,
                    "has_layout_context": bool(config.layout_context),
                    "has_style_context": bool(config.style_context),
                    # Data size info for UI display
                    "html_lines": html_lines,
                    "html_chars": html_chars,
                    "html_range": {"start": start_line, "end": end_line} if start_line or end_line else None,
                    "char_start": char_start,
                    "char_end": char_end,
                    "estimated_tokens": estimated_tokens,
                    "images_count": len(config.section_data.get("images", [])),
                    "links_count": len(config.section_data.get("links", [])),
                }
                await self.ws_manager.send_worker_spawned(
                    self.session_id,
                    config.worker_id,
                    config.section_name,
                    config.task_description,
                    input_summary,
                    total_workers,
                    display_name=config.display_name,  # Human-friendly name
                )
            except Exception as e:
                logger.warning(f"Failed to emit worker spawned event: {e}")

    async def _emit_worker_started(self, config: WorkerConfig):
        """Emit worker started event"""
        if self.ws_manager and self.session_id:
            try:
                await self.ws_manager.send_worker_started(
                    self.session_id,
                    config.worker_id,
                    config.section_name,
                )
            except Exception as e:
                logger.warning(f"Failed to emit worker started event: {e}")

    async def _emit_worker_completed(self, config: WorkerConfig, result: WorkerResult):
        """Emit worker completed event"""
        if self.ws_manager and self.session_id:
            try:
                await self.ws_manager.send_worker_completed(
                    self.session_id,
                    config.worker_id,
                    config.section_name,
                    result.success,
                    result.files,
                    result.summary,
                    result.error,
                )
            except Exception as e:
                logger.warning(f"Failed to emit worker completed event: {e}")

    async def _emit_worker_error(self, config: WorkerConfig, error: str):
        """Emit worker error event"""
        if self.ws_manager and self.session_id:
            try:
                await self.ws_manager.send_worker_error(
                    self.session_id,
                    config.worker_id,
                    config.section_name,
                    error,
                )
            except Exception as e:
                logger.warning(f"Failed to emit worker error event: {e}")

    # ============================================
    # Result Merging
    # ============================================

    def _merge_results(self, results: List[WorkerResult]) -> WorkerManagerResult:
        """Merge results from all workers"""
        merged_files: Dict[str, str] = {}
        errors: List[str] = []
        successful_count = 0
        failed_count = 0

        for result in results:
            if result.success:
                successful_count += 1
                # Merge files (later workers override earlier for same path)
                merged_files.update(result.files)
            else:
                failed_count += 1
                if result.error:
                    errors.append(f"[{result.section_name}] {result.error}")

        return WorkerManagerResult(
            success=failed_count == 0 or self.config.continue_on_failure,
            total_workers=len(results),
            successful_workers=successful_count,
            failed_workers=failed_count,
            files=merged_files,
            worker_results=results,
            errors=errors,
        )


# ============================================
# Factory Functions
# ============================================

def create_worker_manager(
    max_concurrent: int = 0,  # 0 = unlimited parallelism
    worker_timeout: float = 1200.0,  # 20 minutes - increased for complex sections with image downloads
    continue_on_failure: bool = True,
    ws_manager: Optional["WebSocketManager"] = None,
    session_id: Optional[str] = None,
) -> WorkerManager:
    """
    Create a Worker Manager

    Args:
        max_concurrent: Maximum concurrent workers (0 = unlimited)
        worker_timeout: Timeout per worker in seconds
        continue_on_failure: Whether to continue on worker failure
        ws_manager: WebSocket manager for event emission
        session_id: Session ID for WebSocket events

    Returns:
        Configured WorkerManager
    """
    config = WorkerManagerConfig(
        max_concurrent=max_concurrent,
        worker_timeout=worker_timeout,
        continue_on_failure=continue_on_failure,
    )
    return WorkerManager(
        config,
        ws_manager=ws_manager,
        session_id=session_id,
    )


# ============================================
# Convenience Functions
# ============================================

async def run_section_workers(
    tasks: List[SectionTask],
    shared_context: Optional[Dict[str, Any]] = None,
    max_concurrent: int = 0,  # 0 = unlimited parallelism
    on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ws_manager: Optional["WebSocketManager"] = None,
    session_id: Optional[str] = None,
) -> WorkerManagerResult:
    """
    Run workers for section tasks (convenience function)

    Args:
        tasks: List of section tasks
        shared_context: Optional shared context
        max_concurrent: Maximum concurrent workers (0 = unlimited)
        on_progress: Progress callback (section_name, status)
        ws_manager: WebSocket manager for event emission
        session_id: Session ID for WebSocket events

    Returns:
        Combined result from all workers
    """
    manager = create_worker_manager(
        max_concurrent=max_concurrent,
        ws_manager=ws_manager,
        session_id=session_id,
    )

    if on_progress:
        manager.on_progress = on_progress

    return await manager.run_workers(tasks, shared_context)
