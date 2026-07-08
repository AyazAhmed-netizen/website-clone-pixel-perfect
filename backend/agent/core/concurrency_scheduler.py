"""
Concurrency Scheduler (UH1)

实现 Claude Code 的并发调度器。

核心功能：
- 并发限制控制（max 10）
- 任务队列管理
- 批量执行
- 优先级调度
"""

from __future__ import annotations
import asyncio
import logging
from typing import (
    Dict,
    Any,
    List,
    Optional,
    Callable,
    Awaitable,
    TypeVar,
    Generic,
)
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .constants import MAX_CONCURRENT_TOOLS

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TaskPriority(int, Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask(Generic[T]):
    """
    调度任务

    封装单个待执行任务的所有信息
    """

    # 任务 ID
    task_id: str

    # 任务函数
    func: Callable[..., Awaitable[T]]

    # 函数参数
    args: tuple = field(default_factory=tuple)

    # 函数关键字参数
    kwargs: Dict[str, Any] = field(default_factory=dict)

    # 优先级
    priority: TaskPriority = TaskPriority.NORMAL

    # 任务状态
    status: TaskStatus = TaskStatus.PENDING

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    # 开始时间
    started_at: Optional[datetime] = None

    # 完成时间
    completed_at: Optional[datetime] = None

    # 执行结果
    result: Optional[T] = None

    # 错误信息
    error: Optional[str] = None

    # asyncio.Task 对象
    asyncio_task: Optional[asyncio.Task] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_execution_time(self) -> Optional[float]:
        """
        获取执行时间（秒）

        Returns:
            执行时间，如果未完成则返回 None
        """
        if self.started_at is None or self.completed_at is None:
            return None

        return (self.completed_at - self.started_at).total_seconds()


class ConcurrencyScheduler:
    """
    并发调度器（UH1）

    管理并发任务执行，限制最大并发数
    """

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT_TOOLS,
    ):
        """
        初始化并发调度器

        Args:
            max_concurrent: 最大并发数
        """
        self.max_concurrent = max_concurrent

        # 信号量控制并发数（延迟初始化）
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._semaphore_initialized = False

        # 任务注册表
        self._tasks: Dict[str, ScheduledTask] = {}

        # 任务计数器
        self._task_counter = 0

        # 运行中的任务
        self._running_tasks: Dict[str, ScheduledTask] = {}

        # 等待队列（按优先级）
        self._pending_queue: List[ScheduledTask] = []

        # 统计信息
        self._stats = {
            "scheduled": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }

        logger.info(
            f"ConcurrencyScheduler 初始化：max_concurrent={max_concurrent}"
        )

    def _ensure_semaphore_initialized(self):
        """确保信号量已初始化"""
        if not self._semaphore_initialized:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
            self._semaphore_initialized = True

    async def schedule(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> ScheduledTask[T]:
        """
        调度单个任务

        Args:
            func: 异步函数
            *args: 函数参数
            priority: 任务优先级
            task_id: 任务 ID（可选）
            **kwargs: 函数关键字参数

        Returns:
            调度任务对象
        """
        # 生成任务 ID
        if task_id is None:
            task_id = f"task_{self._task_counter}"
            self._task_counter += 1

        # 创建任务
        task = ScheduledTask(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
        )

        # 注册任务
        self._tasks[task_id] = task
        self._stats["scheduled"] += 1

        # 添加到队列
        self._pending_queue.append(task)

        # 按优先级排序队列
        self._pending_queue.sort(
            key=lambda t: t.priority.value,
            reverse=True
        )

        logger.debug(
            f"任务已调度：{task_id} (priority={priority}, "
            f"queue_size={len(self._pending_queue)})"
        )

        return task

    async def execute_task(
        self,
        task: ScheduledTask[T],
    ) -> T:
        """
        执行单个任务（受并发限制）

        Args:
            task: 调度任务

        Returns:
            任务执行结果

        Raises:
            Exception: 任务执行错误
        """
        # 确保信号量已初始化
        self._ensure_semaphore_initialized()

        async with self._semaphore:
            # 更新状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self._running_tasks[task.task_id] = task

            logger.debug(
                f"任务开始执行：{task.task_id} "
                f"(running={len(self._running_tasks)}/{self.max_concurrent})"
            )

            try:
                # 执行函数
                result = await task.func(*task.args, **task.kwargs)

                # 记录成功
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()

                self._stats["completed"] += 1

                logger.debug(
                    f"任务执行成功：{task.task_id} "
                    f"({task.get_execution_time():.2f}s)"
                )

                return result

            except Exception as e:
                # 记录失败
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()

                self._stats["failed"] += 1

                logger.error(
                    f"任务执行失败：{task.task_id} - {e}",
                    exc_info=True
                )

                raise

            finally:
                # 从运行列表移除
                self._running_tasks.pop(task.task_id, None)

    async def execute_batch(
        self,
        tasks: List[ScheduledTask[T]],
        return_exceptions: bool = True,
    ) -> List[Any]:
        """
        批量执行任务

        Args:
            tasks: 任务列表
            return_exceptions: 是否返回异常对象而不是抛出

        Returns:
            结果列表
        """
        logger.info(f"批量执行 {len(tasks)} 个任务...")

        # 并发执行所有任务
        results = await asyncio.gather(
            *[self.execute_task(task) for task in tasks],
            return_exceptions=return_exceptions
        )

        logger.info(f"批量执行完成：{len(tasks)} 个任务")

        return results

    async def execute_pending(
        self,
        max_tasks: Optional[int] = None,
    ) -> List[Any]:
        """
        执行所有待处理任务

        Args:
            max_tasks: 最大执行任务数（None 表示全部）

        Returns:
            结果列表
        """
        # 获取待执行任务
        if max_tasks is None:
            tasks_to_execute = self._pending_queue[:]
            self._pending_queue.clear()
        else:
            tasks_to_execute = self._pending_queue[:max_tasks]
            self._pending_queue = self._pending_queue[max_tasks:]

        if not tasks_to_execute:
            logger.debug("没有待执行任务")
            return []

        logger.info(
            f"执行 {len(tasks_to_execute)} 个待处理任务 "
            f"(剩余 {len(self._pending_queue)} 个)"
        )

        # 批量执行
        return await self.execute_batch(tasks_to_execute)

    async def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        等待任务完成

        Args:
            task_id: 任务 ID
            timeout: 超时时间（秒）

        Returns:
            任务结果

        Raises:
            ValueError: 任务不存在
            asyncio.TimeoutError: 超时
        """
        task = self._tasks.get(task_id)

        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        # 如果任务还未开始，先执行它
        if task.status == TaskStatus.PENDING:
            # 从队列中移除
            if task in self._pending_queue:
                self._pending_queue.remove(task)

            # 执行任务
            return await asyncio.wait_for(
                self.execute_task(task),
                timeout=timeout
            )

        # 如果任务正在运行，等待完成
        elif task.status == TaskStatus.RUNNING:
            # 等待任务完成
            while task.status == TaskStatus.RUNNING:
                await asyncio.sleep(0.1)

                # 检查超时
                if timeout is not None:
                    elapsed = (datetime.now() - task.started_at).total_seconds()
                    if elapsed > timeout:
                        raise asyncio.TimeoutError(
                            f"Task {task_id} timed out after {timeout}s"
                        )

        # 返回结果或抛出错误
        if task.status == TaskStatus.COMPLETED:
            return task.result
        elif task.status == TaskStatus.FAILED:
            raise RuntimeError(f"Task {task_id} failed: {task.error}")
        elif task.status == TaskStatus.CANCELLED:
            raise RuntimeError(f"Task {task_id} was cancelled")

        return task.result

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        task = self._tasks.get(task_id)

        if task is None:
            logger.warning(f"任务不存在：{task_id}")
            return False

        # 如果任务在队列中，直接移除
        if task.status == TaskStatus.PENDING:
            if task in self._pending_queue:
                self._pending_queue.remove(task)

            task.status = TaskStatus.CANCELLED
            self._stats["cancelled"] += 1

            logger.info(f"任务已取消：{task_id}")
            return True

        # 如果任务正在运行，尝试取消
        elif task.status == TaskStatus.RUNNING:
            if task.asyncio_task and not task.asyncio_task.done():
                task.asyncio_task.cancel()
                task.status = TaskStatus.CANCELLED
                self._stats["cancelled"] += 1

                logger.info(f"运行中任务已取消：{task_id}")
                return True

        return False

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        获取任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态，如果任务不存在则返回 None
        """
        task = self._tasks.get(task_id)
        return task.status if task else None

    def get_stats(self) -> Dict[str, Any]:
        """
        获取调度器统计信息

        Returns:
            统计数据字典
        """
        return {
            **self._stats,
            "max_concurrent": self.max_concurrent,
            "running": len(self._running_tasks),
            "pending": len(self._pending_queue),
            "total_tasks": len(self._tasks),
        }

    def get_running_tasks(self) -> List[str]:
        """
        获取运行中的任务 ID 列表

        Returns:
            任务 ID 列表
        """
        return list(self._running_tasks.keys())

    def get_pending_tasks(self) -> List[str]:
        """
        获取待处理的任务 ID 列表

        Returns:
            任务 ID 列表
        """
        return [task.task_id for task in self._pending_queue]

    def clear_completed(self):
        """清除已完成的任务"""
        completed_ids = [
            task_id for task_id, task in self._tasks.items()
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]

        for task_id in completed_ids:
            del self._tasks[task_id]

        logger.info(f"已清除 {len(completed_ids)} 个已完成任务")

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"ConcurrencyScheduler("
            f"max={self.max_concurrent}, "
            f"running={stats['running']}, "
            f"pending={stats['pending']}, "
            f"completed={stats['completed']})"
        )
