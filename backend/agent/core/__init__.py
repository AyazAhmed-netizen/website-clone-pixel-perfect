"""
Agent Core Orchestration Layer

Claude Code 风格的核心调度层实现：
- nO: Main orchestrator loop (主循环编排器)
- h2A: Async message queue (异步消息队列)
- wU2: Message compressor with AU2 algorithm (消息压缩器)
- ga0: System prompt generator (系统提示生成器)
- wu: Stream generator (会话流生成器)
- nE2: Conversation pipeline (对话管道处理器)
- MH1: Tool execution engine (工具执行引擎)
- UH1: Concurrency scheduler (并发调度器)
"""

from .constants import (
    # Token 阈值
    COMPRESSION_THRESHOLD,
    WARNING_THRESHOLD,
    ERROR_THRESHOLD,
    MAX_CONCURRENT_TOOLS,
    MAX_OUTPUT_TOKENS,

    # 压缩配置
    CompressionConfig,

    # 执行上下文
    ExecutionContext,
)

from .orchestrator import MainOrchestrator
from .message_queue import AsyncMessageQueue, MessagePriority, QueueMessage
from .compressor import MessageCompressor, AU2Algorithm
from .prompt_generator import SystemPromptGenerator
from .stream_generator import StreamGenerator, StreamEvent
from .conversation_pipeline import ConversationPipeline
from .tool_executor import ToolExecutor, ToolCall, ToolExecutionResult
from .concurrency_scheduler import ConcurrencyScheduler, ScheduledTask, TaskPriority, TaskStatus

__all__ = [
    # Constants
    "COMPRESSION_THRESHOLD",
    "WARNING_THRESHOLD",
    "ERROR_THRESHOLD",
    "MAX_CONCURRENT_TOOLS",
    "MAX_OUTPUT_TOKENS",
    "CompressionConfig",
    "ExecutionContext",

    # Core Components
    "MainOrchestrator",
    "AsyncMessageQueue",
    "MessagePriority",
    "QueueMessage",
    "MessageCompressor",
    "AU2Algorithm",
    "SystemPromptGenerator",
    "StreamGenerator",
    "StreamEvent",
    "ConversationPipeline",
    "ToolExecutor",
    "ToolCall",
    "ToolExecutionResult",
    "ConcurrencyScheduler",
    "ScheduledTask",
    "TaskPriority",
    "TaskStatus",
]
