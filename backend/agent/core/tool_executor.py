"""
Tool Executor (MH1)

实现 Claude Code 的工具执行引擎。

6 阶段执行管道：
1. Discovery - 工具发现
2. Validation - Schema 验证
3. Permission - 权限检查
4. Abort Check - 中断信号检查
5. Execution - 实际执行
6. Formatting - 结果格式化
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime

from .constants import (
    ToolExecutionStage,
    PermissionBehavior,
    ExecutionContext,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """
    工具调用请求

    封装单个工具调用的所有信息
    """

    # 工具名称
    name: str

    # 工具输入参数
    input: Dict[str, Any]

    # 调用 ID
    call_id: str

    # 执行阶段
    stage: str = ToolExecutionStage.DISCOVERY

    # 执行结果
    result: Optional[Any] = None

    # 错误信息
    error: Optional[str] = None

    # 权限决策
    permission: str = PermissionBehavior.ASK

    # 是否被中断
    aborted: bool = False

    # 元数据
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ToolExecutionResult:
    """
    工具执行结果

    包含执行状态、结果、错误等信息
    """

    # 工具调用
    tool_call: ToolCall

    # 是否成功
    success: bool

    # 结果数据
    result: Any = None

    # 错误信息
    error: Optional[str] = None

    # 执行时间（秒）
    execution_time: float = 0.0

    # 阶段追踪
    stages_completed: List[str] = None

    def __post_init__(self):
        if self.stages_completed is None:
            self.stages_completed = []


class ToolExecutor:
    """
    工具执行引擎（MH1）

    实现 Claude Code 的 6 阶段工具执行管道
    """

    def __init__(
        self,
        tools_registry: Dict[str, Callable],
        tool_schemas: List[Dict[str, Any]],
        default_permission: str = PermissionBehavior.ALLOW,
    ):
        """
        初始化工具执行器

        Args:
            tools_registry: 工具函数注册表 {name: function}
            tool_schemas: 工具 Schema 定义列表
            default_permission: 默认权限行为
        """
        self.tools_registry = tools_registry
        self.tool_schemas = {
            schema["name"]: schema for schema in tool_schemas
        }
        self.default_permission = default_permission

        # 权限配置（工具名 -> 权限行为）
        self.permission_config: Dict[str, str] = {}

        # 权限检查回调
        self.permission_checker: Optional[
            Callable[[ToolCall], Awaitable[str]]
        ] = None

        # 统计信息
        self._stats = {
            "executed": 0,
            "successful": 0,
            "failed": 0,
            "aborted": 0,
        }

        logger.info(
            f"ToolExecutor 初始化：{len(tools_registry)} 个工具已注册"
        )

    async def execute(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolExecutionResult:
        """
        执行单个工具调用（6 阶段管道）

        Args:
            tool_call: 工具调用对象
            context: 执行上下文

        Returns:
            工具执行结果
        """
        start_time = datetime.now()
        stages_completed = []

        try:
            # ============================================
            # Stage 1: Discovery - 工具发现
            # ============================================
            tool_call.stage = ToolExecutionStage.DISCOVERY
            await self._stage_discovery(tool_call)
            stages_completed.append(ToolExecutionStage.DISCOVERY)

            # ============================================
            # Stage 2: Validation - Schema 验证
            # ============================================
            tool_call.stage = ToolExecutionStage.VALIDATION
            await self._stage_validation(tool_call)
            stages_completed.append(ToolExecutionStage.VALIDATION)

            # ============================================
            # Stage 3: Permission - 权限检查
            # ============================================
            tool_call.stage = ToolExecutionStage.PERMISSION
            permission_granted = await self._stage_permission(tool_call)
            stages_completed.append(ToolExecutionStage.PERMISSION)

            if not permission_granted:
                return ToolExecutionResult(
                    tool_call=tool_call,
                    success=False,
                    error="Permission denied",
                    stages_completed=stages_completed,
                )

            # ============================================
            # Stage 4: Abort Check - 中断信号检查
            # ============================================
            tool_call.stage = ToolExecutionStage.ABORT_CHECK
            should_continue = await self._stage_abort_check(tool_call, context)
            stages_completed.append(ToolExecutionStage.ABORT_CHECK)

            if not should_continue:
                tool_call.aborted = True
                self._stats["aborted"] += 1
                return ToolExecutionResult(
                    tool_call=tool_call,
                    success=False,
                    error="Execution aborted",
                    stages_completed=stages_completed,
                )

            # ============================================
            # Stage 5: Execution - 实际执行
            # ============================================
            tool_call.stage = ToolExecutionStage.EXECUTION
            result = await self._stage_execution(tool_call)
            tool_call.result = result
            stages_completed.append(ToolExecutionStage.EXECUTION)

            # ============================================
            # Stage 6: Formatting - 结果格式化
            # ============================================
            tool_call.stage = ToolExecutionStage.FORMATTING
            formatted_result = await self._stage_formatting(tool_call, result)
            stages_completed.append(ToolExecutionStage.FORMATTING)

            # 记录成功
            self._stats["executed"] += 1
            self._stats["successful"] += 1

            execution_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"工具执行成功：{tool_call.name} "
                f"({execution_time:.2f}s)"
            )

            return ToolExecutionResult(
                tool_call=tool_call,
                success=True,
                result=formatted_result,
                execution_time=execution_time,
                stages_completed=stages_completed,
            )

        except Exception as e:
            logger.error(
                f"工具执行失败：{tool_call.name} - {e}",
                exc_info=True
            )

            self._stats["executed"] += 1
            self._stats["failed"] += 1

            tool_call.error = str(e)

            execution_time = (datetime.now() - start_time).total_seconds()

            return ToolExecutionResult(
                tool_call=tool_call,
                success=False,
                error=str(e),
                execution_time=execution_time,
                stages_completed=stages_completed,
            )

    # ============================================
    # 6 阶段实现
    # ============================================

    async def _stage_discovery(self, tool_call: ToolCall):
        """
        Stage 1: Discovery - 工具发现

        检查工具是否存在于注册表中

        Args:
            tool_call: 工具调用对象

        Raises:
            ValueError: 工具不存在
        """
        if tool_call.name not in self.tools_registry:
            raise ValueError(f"Unknown tool: {tool_call.name}")

        logger.debug(f"[Discovery] 工具已找到：{tool_call.name}")

    async def _stage_validation(self, tool_call: ToolCall):
        """
        Stage 2: Validation - Schema 验证

        验证工具输入是否符合 Schema

        Args:
            tool_call: 工具调用对象

        Raises:
            ValueError: Schema 验证失败
        """
        schema = self.tool_schemas.get(tool_call.name)

        if not schema:
            logger.warning(f"[Validation] 未找到 Schema：{tool_call.name}")
            return

        # 获取必需参数
        input_schema = schema.get("input_schema", {})
        required_params = input_schema.get("required", [])

        # 检查必需参数
        for param in required_params:
            if param not in tool_call.input:
                raise ValueError(
                    f"Missing required parameter: {param} "
                    f"for tool {tool_call.name}"
                )

        logger.debug(f"[Validation] Schema 验证通过：{tool_call.name}")

    async def _stage_permission(self, tool_call: ToolCall) -> bool:
        """
        Stage 3: Permission - 权限检查

        检查是否允许执行该工具

        Args:
            tool_call: 工具调用对象

        Returns:
            是否允许执行
        """
        # 获取工具的权限配置
        permission = self.permission_config.get(
            tool_call.name,
            self.default_permission
        )

        # 如果有自定义权限检查器，使用它
        if self.permission_checker:
            permission = await self.permission_checker(tool_call)

        tool_call.permission = permission

        if permission == PermissionBehavior.ALLOW:
            logger.debug(f"[Permission] 允许执行：{tool_call.name}")
            return True

        elif permission == PermissionBehavior.DENY:
            logger.warning(f"[Permission] 拒绝执行：{tool_call.name}")
            return False

        elif permission == PermissionBehavior.ASK:
            # TODO: 实现用户交互确认
            logger.warning(
                f"[Permission] 需要用户确认：{tool_call.name} "
                f"（当前自动允许）"
            )
            return True

        else:
            logger.error(f"[Permission] 未知权限行为：{permission}")
            return False

    async def _stage_abort_check(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> bool:
        """
        Stage 4: Abort Check - 中断信号检查

        检查是否有中断信号

        Args:
            tool_call: 工具调用对象
            context: 执行上下文

        Returns:
            是否应该继续执行
        """
        # 检查上下文中的中断信号
        if context.abort_signal:
            logger.warning(
                f"[Abort Check] 检测到中断信号：{tool_call.name}"
            )
            return False

        logger.debug(f"[Abort Check] 无中断信号：{tool_call.name}")
        return True

    async def _stage_execution(self, tool_call: ToolCall) -> Any:
        """
        Stage 5: Execution - 实际执行

        执行工具函数

        Args:
            tool_call: 工具调用对象

        Returns:
            工具执行结果

        Raises:
            Exception: 工具执行错误
        """
        tool_func = self.tools_registry[tool_call.name]

        logger.debug(
            f"[Execution] 开始执行：{tool_call.name} "
            f"with input: {tool_call.input}"
        )

        # 执行工具
        result = tool_func(**tool_call.input)

        # 如果是异步函数，await 它
        if hasattr(result, "__await__"):
            result = await result

        logger.debug(f"[Execution] 执行完成：{tool_call.name}")

        return result

    async def _stage_formatting(
        self,
        tool_call: ToolCall,
        result: Any,
    ) -> Dict[str, Any]:
        """
        Stage 6: Formatting - 结果格式化

        格式化工具执行结果为统一格式

        Args:
            tool_call: 工具调用对象
            result: 原始结果

        Returns:
            格式化的结果字典
        """
        # 如果结果已经是字典格式且有必要字段，直接返回
        if isinstance(result, dict) and "success" in result:
            formatted = result
        else:
            # 否则包装为标准格式
            formatted = {
                "success": True,
                "result": result,
                "tool_name": tool_call.name,
                "call_id": tool_call.call_id,
            }

        logger.debug(f"[Formatting] 结果已格式化：{tool_call.name}")

        return formatted

    # ============================================
    # 配置方法
    # ============================================

    def set_permission(self, tool_name: str, behavior: str):
        """
        设置工具权限

        Args:
            tool_name: 工具名称
            behavior: 权限行为 (allow/deny/ask)
        """
        self.permission_config[tool_name] = behavior
        logger.info(f"工具权限已设置：{tool_name} = {behavior}")

    def set_permission_checker(
        self,
        checker: Callable[[ToolCall], Awaitable[str]]
    ):
        """
        设置自定义权限检查器

        Args:
            checker: 异步权限检查函数
        """
        self.permission_checker = checker
        logger.info("自定义权限检查器已设置")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取执行统计

        Returns:
            统计信息字典
        """
        return {
            **self._stats,
            "tools_registered": len(self.tools_registry),
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"ToolExecutor("
            f"tools={stats['tools_registered']}, "
            f"executed={stats['executed']}, "
            f"success_rate={stats['successful']}/{stats['executed'] if stats['executed'] > 0 else 1})"
        )
