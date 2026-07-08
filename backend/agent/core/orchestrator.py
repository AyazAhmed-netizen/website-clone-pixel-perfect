"""
Main Orchestrator (nO)

实现 Claude Code 的主编排循环。

核心流程（6 阶段）：
1. 消息预处理
2. 压缩检查
3. 系统提示生成
4. 对话流生成
5. 工具执行
6. 结果收集

整合所有核心组件：
- h2A: AsyncMessageQueue
- wU2: MessageCompressor
- ga0: SystemPromptGenerator
- wu: StreamGenerator
- nE2: ConversationPipeline
- MH1: ToolExecutor
- UH1: ConcurrencyScheduler
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from .constants import ExecutionContext, StreamEventType
from .message_queue import AsyncMessageQueue
from .compressor import MessageCompressor
from .prompt_generator import SystemPromptGenerator
from .stream_generator import StreamGenerator
from .conversation_pipeline import ConversationPipeline
from .tool_executor import ToolExecutor, ToolCall
from .concurrency_scheduler import ConcurrencyScheduler, TaskPriority

logger = logging.getLogger(__name__)


class MainOrchestrator:
    """
    主编排器（nO）

    整合所有核心组件，实现完整的 Agent 执行循环
    """

    def __init__(
        self,
        tools_registry: Dict[str, Any],
        tool_schemas: List[Dict[str, Any]],
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        初始化主编排器

        Args:
            tools_registry: 工具注册表
            tool_schemas: 工具 Schema 列表
            api_key: Anthropic API Key
            base_url: API 基础 URL
        """
        # 初始化所有核心组件
        self.message_queue = AsyncMessageQueue()
        self.compressor = MessageCompressor()
        self.prompt_generator = SystemPromptGenerator()
        self.conversation_pipeline = ConversationPipeline(
            api_key=api_key,
            base_url=base_url,
        )
        self.tool_executor = ToolExecutor(
            tools_registry=tools_registry,
            tool_schemas=tool_schemas,
        )
        self.concurrency_scheduler = ConcurrencyScheduler()

        # 统计信息
        self._stats = {
            "iterations": 0,
            "messages_processed": 0,
            "tools_executed": 0,
            "compressions": 0,
        }

        logger.info("MainOrchestrator 初始化完成")

    async def run(
        self,
        user_message: str,
        context: ExecutionContext,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: int = 999999,  # No limit - Agent works until task is complete
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        运行主编排循环

        这是核心执行流程，按照 Claude Code 的 6 阶段处理：
        1. 消息预处理
        2. 压缩检查
        3. 系统提示生成
        4. 对话流生成
        5. 工具执行
        6. 结果收集

        Args:
            user_message: 用户消息
            context: 执行上下文
            conversation_history: 对话历史
            max_iterations: 最大迭代次数

        Yields:
            流式事件字典
        """
        # 初始化流生成器
        stream_gen = StreamGenerator(
            session_id=context.session_id,
            format_sse=False,  # 返回字典格式
        )

        # 准备消息历史
        messages = conversation_history or []
        messages.append({
            "role": "user",
            "content": user_message,
        })

        # 主循环
        for iteration in range(max_iterations):
            self._stats["iterations"] += 1

            logger.info(
                f"主循环 - 迭代 {iteration + 1}/{max_iterations}"
            )

            # 发送迭代事件
            yield {
                "type": StreamEventType.ITERATION,
                "data": {
                    "iteration": iteration + 1,
                    "max_iterations": max_iterations,
                }
            }

            # ============================================
            # Stage 1: 消息预处理
            # ============================================
            messages = await self._stage_preprocess_messages(messages, context)
            self._stats["messages_processed"] += len(messages)

            # ============================================
            # Stage 2: 压缩检查
            # ============================================
            messages, compressed = await self._stage_compression_check(
                messages, context, stream_gen
            )

            if compressed:
                self._stats["compressions"] += 1
                yield {
                    "type": StreamEventType.COMPRESSION_SUCCESS,
                    "data": {
                        "message_count": len(messages),
                    }
                }

            # ============================================
            # Stage 3: 系统提示生成
            # ============================================
            system_prompt = await self._stage_generate_system_prompt(
                context, self.tool_executor.tool_schemas
            )

            # ============================================
            # Stage 4: 对话流生成
            # ============================================
            assistant_message = None

            async for event in self._stage_conversation_stream(
                messages, context, system_prompt, stream_gen
            ):
                # 转发流式事件
                yield event

                # 收集完整消息
                if event["type"] == "message_complete":
                    assistant_message = event["data"]["message"]

            if assistant_message is None:
                logger.error("未收到助手响应")
                break

            # 添加助手消息到历史
            messages.append({
                "role": "assistant",
                "content": assistant_message["content"],
            })

            # ============================================
            # Stage 5: 工具执行
            # ============================================
            tool_calls = self._extract_tool_calls(assistant_message)

            if not tool_calls:
                # 没有工具调用，对话结束
                logger.info("没有工具调用，对话结束")
                yield {
                    "type": StreamEventType.DONE,
                    "data": {
                        "final_message": assistant_message,
                        "stats": self.get_stats(),
                    }
                }
                break

            # 执行工具
            tool_results = []

            async for event in self._stage_tool_execution(
                tool_calls, context, stream_gen
            ):
                yield event

                # 收集工具结果
                if event["type"] == StreamEventType.TOOL_RESULT:
                    tool_results.append(event["data"])

            self._stats["tools_executed"] += len(tool_calls)

            # ============================================
            # Stage 6: 结果收集
            # ============================================
            messages = await self._stage_collect_results(
                messages, tool_results
            )

            # 检查中断信号
            if context.abort_signal:
                logger.warning("检测到中断信号，停止执行")
                yield {
                    "type": StreamEventType.WARNING,
                    "data": {
                        "message": "Execution aborted by user",
                    }
                }
                break

        # 最终完成事件
        yield {
            "type": StreamEventType.LOOP_COMPLETE,
            "data": {
                "iterations": iteration + 1,
                "stats": self.get_stats(),
            }
        }

    # ============================================
    # 6 阶段实现
    # ============================================

    async def _stage_preprocess_messages(
        self,
        messages: List[Dict[str, Any]],
        context: ExecutionContext,
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: 消息预处理

        清理和标准化消息格式

        Args:
            messages: 原始消息列表
            context: 执行上下文

        Returns:
            处理后的消息列表
        """
        logger.debug(f"[Preprocess] 处理 {len(messages)} 条消息")

        # TODO: 实现消息清理逻辑
        # - 移除空消息
        # - 合并连续的同角色消息
        # - 格式标准化

        return messages

    async def _stage_compression_check(
        self,
        messages: List[Dict[str, Any]],
        context: ExecutionContext,
        stream_gen: StreamGenerator,
    ) -> tuple[List[Dict[str, Any]], bool]:
        """
        Stage 2: 压缩检查

        检查是否需要压缩消息历史

        Args:
            messages: 消息列表
            context: 执行上下文
            stream_gen: 流生成器

        Returns:
            (处理后的消息列表, 是否执行了压缩)
        """
        if not context.should_compress():
            return messages, False

        logger.info("开始消息压缩...")

        # 发送压缩开始事件
        await stream_gen.stream_compression(status="start")

        try:
            # 执行压缩
            compressed_messages, compressed = await self.compressor.compress_if_needed(
                messages, context
            )

            if compressed:
                logger.info(
                    f"压缩完成：{len(messages)} -> {len(compressed_messages)} 条消息"
                )

            return compressed_messages, compressed

        except Exception as e:
            logger.error(f"压缩失败：{e}", exc_info=True)
            await stream_gen.stream_compression(status="failed", error=str(e))
            return messages, False

    async def _stage_generate_system_prompt(
        self,
        context: ExecutionContext,
        tool_schemas: Dict[str, Any],
    ) -> str:
        """
        Stage 3: 系统提示生成

        动态生成系统提示

        Args:
            context: 执行上下文
            tool_schemas: 工具 Schema 字典

        Returns:
            系统提示文本
        """
        logger.debug("[System Prompt] 生成系统提示")

        tools_list = list(tool_schemas.values())

        system_prompt = self.prompt_generator.generate(
            context=context,
            tools=tools_list,
            include_subagent_info=True,
            include_compression_info=context.is_compressed,
        )

        return system_prompt

    async def _stage_conversation_stream(
        self,
        messages: List[Dict[str, Any]],
        context: ExecutionContext,
        system_prompt: str,
        stream_gen: StreamGenerator,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stage 4: 对话流生成

        调用 LLM 生成响应

        Args:
            messages: 消息列表
            context: 执行上下文
            system_prompt: 系统提示
            stream_gen: 流生成器

        Yields:
            流式事件
        """
        logger.debug("[Conversation] 开始生成响应")

        async for event in self.conversation_pipeline.stream_conversation(
            messages=messages,
            context=context,
            system_prompt=system_prompt,
            tools=list(self.tool_executor.tool_schemas.values()),
        ):
            # 转换为统一事件格式
            yield {
                "type": self._map_api_event_type(event.get("type")),
                "data": event,
            }

    def _map_api_event_type(self, api_event_type: str) -> str:
        """
        映射 API 事件类型到内部事件类型

        Args:
            api_event_type: API 事件类型

        Returns:
            内部事件类型
        """
        mapping = {
            "content_block_delta": StreamEventType.TEXT_DELTA,
            "message_complete": "message_complete",
            "message_start": "message_start",
        }

        return mapping.get(api_event_type, api_event_type)

    async def _stage_tool_execution(
        self,
        tool_calls: List[ToolCall],
        context: ExecutionContext,
        stream_gen: StreamGenerator,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stage 5: 工具执行

        并发执行所有工具调用

        Args:
            tool_calls: 工具调用列表
            context: 执行上下文
            stream_gen: 流生成器

        Yields:
            流式事件
        """
        logger.info(f"[Tool Execution] 执行 {len(tool_calls)} 个工具调用")

        # 为每个工具调用创建任务
        for tool_call in tool_calls:
            # 发送工具执行开始事件
            yield {
                "type": StreamEventType.TOOL_EXECUTING,
                "data": {
                    "tool_name": tool_call.name,
                    "tool_input": tool_call.input,
                    "call_id": tool_call.call_id,
                }
            }

            # 调度任务
            await self.concurrency_scheduler.schedule(
                self.tool_executor.execute,
                tool_call,
                context,
                priority=TaskPriority.HIGH,
                task_id=tool_call.call_id,
            )

        # 执行所有待处理任务
        results = await self.concurrency_scheduler.execute_pending()

        # 发送工具结果事件
        for i, result in enumerate(results):
            tool_call = tool_calls[i]

            if isinstance(result, Exception):
                # 执行失败
                yield {
                    "type": StreamEventType.TOOL_RESULT,
                    "data": {
                        "tool_name": tool_call.name,
                        "call_id": tool_call.call_id,
                        "success": False,
                        "error": str(result),
                    }
                }
            else:
                # 执行成功
                yield {
                    "type": StreamEventType.TOOL_RESULT,
                    "data": {
                        "tool_name": tool_call.name,
                        "call_id": tool_call.call_id,
                        "success": result.success,
                        "result": result.result,
                    }
                }

    async def _stage_collect_results(
        self,
        messages: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Stage 6: 结果收集

        将工具执行结果添加到消息历史

        特殊处理：
        - 检测 spawn_section_workers 结果
        - 如果 Workers 完成，强制添加验证提醒
        - 检测 is_task_complete 字段，注入后续步骤提示

        Args:
            messages: 消息列表
            tool_results: 工具结果列表

        Returns:
            更新后的消息列表
        """
        logger.debug(f"[Collect Results] 收集 {len(tool_results)} 个工具结果")

        # 标记是否需要添加验证提醒
        needs_verification_reminder = False

        # 添加工具结果到消息历史
        for tool_result in tool_results:
            result_content = str(tool_result.get("result", ""))
            tool_name = tool_result.get("tool_name", "")

            messages.append({
                "role": "tool",
                "tool_use_id": tool_result.get("call_id"),
                "content": result_content,
            })

            # 检测 spawn_section_workers 结果
            # 如果包含 WORKERS_COMPLETED 或 is_task_complete: False，需要强制验证
            if tool_name == "spawn_section_workers":
                logger.info("[Collect Results] 检测到 spawn_section_workers 完成，添加验证提醒")
                needs_verification_reminder = True
            elif "WORKERS_COMPLETED" in result_content or "is_task_complete" in result_content:
                logger.info("[Collect Results] 检测到 Worker 完成标记，添加验证提醒")
                needs_verification_reminder = True

        # 如果需要验证提醒，添加系统消息强调后续步骤
        if needs_verification_reminder:
            verification_reminder = (
                "\n\n🚨 SYSTEM REMINDER: Workers have completed, but the task is NOT done!\n\n"
                "You MUST execute these steps NOW:\n"
                "1. Wait 3-5 seconds for HMR to reload new files\n"
                "2. get_build_errors() - Check for compilation errors!\n"
                "3. If errors → fix them → get_build_errors() again\n\n"
                "⛔ DO NOT call shell('npm run dev') - Dev server is already running!\n"
                "⛔ DO NOT generate a final response until you have checked for errors!"
            )

            # 在最后一个工具结果后追加提醒
            if messages and messages[-1].get("role") == "tool":
                messages[-1]["content"] += verification_reminder
                logger.info("[Collect Results] 验证提醒已添加到工具结果")

        return messages

    # ============================================
    # 辅助方法
    # ============================================

    def _extract_tool_calls(
        self,
        assistant_message: Dict[str, Any]
    ) -> List[ToolCall]:
        """
        从助手消息中提取工具调用

        Args:
            assistant_message: 助手消息

        Returns:
            工具调用列表
        """
        tool_calls = []

        content = assistant_message.get("content", [])

        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_call = ToolCall(
                    name=block.get("name"),
                    input=block.get("input", {}),
                    call_id=block.get("id"),
                )
                tool_calls.append(tool_call)

        return tool_calls

    def get_stats(self) -> Dict[str, Any]:
        """
        获取编排器统计信息

        Returns:
            统计数据字典
        """
        return {
            **self._stats,
            "message_queue": self.message_queue.get_stats(),
            "conversation": self.conversation_pipeline.get_stats(),
            "tool_executor": self.tool_executor.get_stats(),
            "scheduler": self.concurrency_scheduler.get_stats(),
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"MainOrchestrator("
            f"iterations={stats['iterations']}, "
            f"messages={stats['messages_processed']}, "
            f"tools={stats['tools_executed']})"
        )
