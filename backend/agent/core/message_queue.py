"""
Async Message Queue (h2A)

实现 Claude Code 的异步消息队列机制。
使用 Promise-based 模式处理消息流。

核心功能：
- 异步消息入队/出队
- 消息优先级管理
- 背压控制（backpressure）
- 消息批处理
"""

from __future__ import annotations
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MessagePriority(int, Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class QueueMessage:
    """
    队列消息结构

    包含消息内容、优先级、时间戳等元数据
    """

    # 消息内容
    content: Dict[str, Any]

    # 优先级
    priority: MessagePriority = MessagePriority.NORMAL

    # 消息 ID
    message_id: str = ""

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    # 处理状态
    processed: bool = False

    # 错误信息
    error: Optional[str] = None

    # 重试次数
    retry_count: int = 0

    # 最大重试次数
    max_retries: int = 3

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class AsyncMessageQueue:
    """
    异步消息队列（h2A）

    实现 Claude Code 的消息队列机制：
    - Promise-based 异步处理
    - 优先级队列
    - 背压控制
    - 批处理支持
    """

    def __init__(
        self,
        max_size: int = 1000,
        batch_size: int = 10,
        batch_timeout: float = 0.1,
    ):
        """
        初始化消息队列

        Args:
            max_size: 队列最大容量
            batch_size: 批处理大小
            batch_timeout: 批处理超时（秒）
        """
        self.max_size = max_size
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout

        # 优先级队列（延迟初始化）
        self._queues: Optional[Dict[MessagePriority, asyncio.Queue]] = None
        self._queues_initialized = False

        # 消息处理器
        self._handlers: List[Callable[[QueueMessage], Awaitable[None]]] = []

        # 统计信息
        self._stats = {
            "enqueued": 0,
            "dequeued": 0,
            "processed": 0,
            "failed": 0,
            "retried": 0,
        }

        # 运行状态
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        logger.info(
            f"AsyncMessageQueue 初始化："
            f"max_size={max_size}, batch_size={batch_size}"
        )

    def _ensure_queues_initialized(self):
        """确保队列已初始化"""
        if not self._queues_initialized:
            self._queues = {
                priority: asyncio.Queue(maxsize=self.max_size)
                for priority in MessagePriority
            }
            self._queues_initialized = True

    async def enqueue(
        self,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        message_id: str = "",
    ) -> bool:
        """
        将消息加入队列

        Args:
            content: 消息内容
            priority: 优先级
            message_id: 消息 ID

        Returns:
            是否成功入队
        """
        # 确保队列已初始化
        self._ensure_queues_initialized()

        # 检查队列是否已满
        queue = self._queues[priority]
        if queue.full():
            logger.warning(f"队列已满（优先级 {priority}），无法入队")
            return False

        # 创建消息
        message = QueueMessage(
            content=content,
            priority=priority,
            message_id=message_id or f"msg_{self._stats['enqueued']}",
        )

        # 入队
        await queue.put(message)
        self._stats["enqueued"] += 1

        logger.debug(f"消息入队：{message.message_id} (priority={priority})")

        return True

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[QueueMessage]:
        """
        从队列取出消息（按优先级）

        Args:
            timeout: 超时时间（秒）

        Returns:
            消息对象，如果超时则返回 None
        """
        # 确保队列已初始化
        self._ensure_queues_initialized()

        # 按优先级顺序尝试获取消息
        for priority in sorted(MessagePriority, reverse=True):
            queue = self._queues[priority]

            if not queue.empty():
                try:
                    if timeout is not None:
                        message = await asyncio.wait_for(
                            queue.get(),
                            timeout=timeout
                        )
                    else:
                        message = await queue.get()

                    self._stats["dequeued"] += 1
                    logger.debug(f"消息出队：{message.message_id}")

                    return message

                except asyncio.TimeoutError:
                    continue

        return None

    async def dequeue_batch(
        self,
        max_size: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[QueueMessage]:
        """
        批量取出消息

        Args:
            max_size: 最大批量大小
            timeout: 超时时间

        Returns:
            消息列表
        """
        batch_size = max_size or self.batch_size
        batch_timeout = timeout or self.batch_timeout

        batch: List[QueueMessage] = []
        deadline = asyncio.get_event_loop().time() + batch_timeout

        while len(batch) < batch_size:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break

            message = await self.dequeue(timeout=remaining)
            if message is None:
                break

            batch.append(message)

        if batch:
            logger.debug(f"批量出队：{len(batch)} 条消息")

        return batch

    def register_handler(
        self,
        handler: Callable[[QueueMessage], Awaitable[None]]
    ):
        """
        注册消息处理器

        Args:
            handler: 异步处理函数
        """
        self._handlers.append(handler)
        logger.info(f"注册消息处理器：{handler.__name__}")

    async def _process_message(self, message: QueueMessage) -> bool:
        """
        处理单条消息

        Args:
            message: 消息对象

        Returns:
            是否处理成功
        """
        try:
            # 调用所有处理器
            for handler in self._handlers:
                await handler(message)

            # 标记为已处理
            message.processed = True
            self._stats["processed"] += 1

            logger.debug(f"消息处理成功：{message.message_id}")
            return True

        except Exception as e:
            logger.error(
                f"消息处理失败：{message.message_id} - {e}",
                exc_info=True
            )

            message.error = str(e)
            message.retry_count += 1

            # 检查是否需要重试
            if message.retry_count < message.max_retries:
                logger.info(
                    f"消息将重试：{message.message_id} "
                    f"({message.retry_count}/{message.max_retries})"
                )
                # 重新入队
                await self.enqueue(
                    content=message.content,
                    priority=message.priority,
                    message_id=message.message_id,
                )
                self._stats["retried"] += 1
            else:
                logger.error(f"消息重试次数已达上限：{message.message_id}")
                self._stats["failed"] += 1

            return False

    async def _worker_loop(self):
        """
        后台工作循环

        持续处理队列中的消息
        """
        logger.info("消息队列工作循环启动")

        while self._running:
            try:
                # 批量取出消息
                batch = await self.dequeue_batch()

                if not batch:
                    # 队列为空，短暂休眠
                    await asyncio.sleep(0.01)
                    continue

                # 并发处理批量消息
                await asyncio.gather(
                    *[self._process_message(msg) for msg in batch],
                    return_exceptions=True
                )

            except Exception as e:
                logger.error(f"工作循环错误：{e}", exc_info=True)
                await asyncio.sleep(0.1)

        logger.info("消息队列工作循环停止")

    async def start(self):
        """启动消息队列处理"""
        if self._running:
            logger.warning("消息队列已在运行中")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

        logger.info("消息队列已启动")

    async def stop(self):
        """停止消息队列处理"""
        if not self._running:
            return

        self._running = False

        # 等待工作任务完成
        if self._worker_task:
            await self._worker_task

        logger.info("消息队列已停止")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取队列统计信息

        Returns:
            统计数据字典
        """
        total_queued = sum(
            queue.qsize() for queue in self._queues.values()
        )

        return {
            **self._stats,
            "queued": total_queued,
            "running": self._running,
            "handlers": len(self._handlers),
        }

    def is_full(self) -> bool:
        """检查队列是否已满"""
        return any(queue.full() for queue in self._queues.values())

    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return all(queue.empty() for queue in self._queues.values())

    async def clear(self):
        """清空所有队列"""
        for queue in self._queues.values():
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        logger.info("队列已清空")

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"AsyncMessageQueue("
            f"queued={stats['queued']}, "
            f"processed={stats['processed']}, "
            f"failed={stats['failed']}, "
            f"running={stats['running']})"
        )
