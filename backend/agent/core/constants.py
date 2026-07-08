"""
Core Constants Module

定义 Claude Code 风格的技术参数常量。
参考混淆名称映射：
- h11: 压缩阈值 (0.92)
- _W5: 警告阈值 (0.6)
- jW5: 错误阈值 (0.8)
- gW5: 并发限制 (10)
- CU2: 最大输出 (16384)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


# ============================================
# Token 使用阈值常量
# ============================================

# h11: 压缩阈值 - 当 token 使用率达到 92% 时触发自动压缩
COMPRESSION_THRESHOLD = 0.92

# _W5: 警告阈值 - 当 token 使用率达到 60% 时显示警告
WARNING_THRESHOLD = 0.6

# jW5: 错误阈值 - 当 token 使用率达到 80% 时显示错误
ERROR_THRESHOLD = 0.8

# gW5: 并发限制 - 最大同时执行工具数（与 Claude Code 一致）
MAX_CONCURRENT_TOOLS = 10

# CU2: 最大输出 - 单次响应最大 Token 数
MAX_OUTPUT_TOKENS = 16384


# ============================================
# 模型配置常量
# ============================================

# 模型最大上下文 Token 数
MODEL_CONTEXT_LIMITS = {
    "claude-3-5-haiku-20241022": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-opus-4-5-20251101": 200000,
}

# 默认模型 (使用 Sonnet 3.5)
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

# Fallback 模型链
FALLBACK_MODEL_CHAIN = [
    "claude-3-5-sonnet-20241022",
]


# ============================================
# 压缩配置
# ============================================

@dataclass
class CompressionConfig:
    """
    消息压缩配置

    实现 Claude Code 的 AU2 8段式结构化压缩算法
    """

    # 是否启用压缩
    enabled: bool = True

    # 压缩阈值（token 使用率）
    threshold: float = COMPRESSION_THRESHOLD

    # 保留最近消息数（不压缩）
    keep_recent_messages: int = 10

    # 压缩目标使用率
    target_usage_rate: float = 0.5

    # AU2 算法 8 段结构
    au2_segments: List[str] = field(default_factory=lambda: [
        "background_context",      # 背景上下文
        "key_decisions",           # 关键决策
        "tool_usage_records",      # 工具使用记录
        "user_intent_evolution",   # 用户意图演变
        "execution_results",       # 执行结果
        "error_handling",          # 错误处理
        "open_issues",             # 未解决问题
        "future_plans",            # 未来计划
    ])

    # 每段最大 token 数
    max_tokens_per_segment: int = 500


# ============================================
# 执行上下文
# ============================================

@dataclass
class ExecutionContext:
    """
    Agent 执行上下文

    贯穿整个执行流程的共享上下文
    """

    # 会话 ID
    session_id: str

    # 用户 ID
    user_id: Optional[str] = None

    # 当前模型
    model: str = DEFAULT_MODEL

    # Token 使用统计
    token_usage: Dict[str, int] = field(default_factory=dict)

    # 上下文窗口大小
    context_window: int = 200000

    # 当前 token 使用率
    usage_rate: float = 0.0

    # 是否已压缩
    is_compressed: bool = False

    # 压缩历史
    compression_history: List[Dict[str, Any]] = field(default_factory=list)

    # 轮次状态
    turn_state: Dict[str, Any] = field(default_factory=dict)

    # 工具配置
    tools_config: Dict[str, Any] = field(default_factory=dict)

    # WebContainer 状态
    webcontainer_state: Dict[str, Any] = field(default_factory=dict)

    # 中断信号
    abort_signal: Optional[Any] = None

    # 执行开始时间
    started_at: datetime = field(default_factory=datetime.now)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_token_usage(self, input_tokens: int = 0, output_tokens: int = 0):
        """更新 token 使用统计"""
        self.token_usage["input"] = self.token_usage.get("input", 0) + input_tokens
        self.token_usage["output"] = self.token_usage.get("output", 0) + output_tokens
        self.token_usage["total"] = self.token_usage.get("input", 0) + self.token_usage.get("output", 0)

        # 更新使用率
        self.usage_rate = self.token_usage["total"] / self.context_window

    def should_compress(self) -> bool:
        """判断是否应该压缩"""
        return (
            not self.is_compressed
            and self.usage_rate >= COMPRESSION_THRESHOLD
        )

    def should_warn(self) -> bool:
        """判断是否应该警告"""
        return self.usage_rate >= WARNING_THRESHOLD

    def should_error(self) -> bool:
        """判断是否应该报错"""
        return self.usage_rate >= ERROR_THRESHOLD


# ============================================
# 工具执行阶段
# ============================================

class ToolExecutionStage:
    """
    工具执行 6 阶段流程（MH1）

    Claude Code 的工具执行管道：
    1. Discovery - 工具发现
    2. Validation - Schema 验证
    3. Permission - 权限检查
    4. Abort Check - 中断信号检查
    5. Execution - 实际执行
    6. Formatting - 结果格式化
    """

    DISCOVERY = "discovery"
    VALIDATION = "validation"
    PERMISSION = "permission"
    ABORT_CHECK = "abort_check"
    EXECUTION = "execution"
    FORMATTING = "formatting"

    ALL_STAGES = [
        DISCOVERY,
        VALIDATION,
        PERMISSION,
        ABORT_CHECK,
        EXECUTION,
        FORMATTING,
    ]


# ============================================
# 事件类型
# ============================================

class StreamEventType:
    """流式事件类型"""

    # 请求相关
    REQUEST_START = "stream_request_start"
    REQUEST_END = "stream_request_end"

    # 压缩相关
    COMPRESSION_START = "compression_start"
    COMPRESSION_SUCCESS = "compression_success"
    COMPRESSION_FAILED = "compression_failed"

    # Token 使用
    TOKEN_WARNING = "token_warning"
    TOKEN_ERROR = "token_error"
    TOKEN_USAGE = "token_usage"

    # 文本输出
    TEXT = "text"
    TEXT_DELTA = "text_delta"

    # 工具相关
    TOOL_CALLS = "tool_calls"
    TOOL_EXECUTING = "tool_executing"
    TOOL_RESULT = "tool_result"

    # SubAgent 相关
    SUBAGENT_START = "subagent_start"
    SUBAGENT_COMPLETE = "subagent_complete"

    # 错误相关
    ERROR = "error"
    WARNING = "warning"

    # 迭代相关
    ITERATION = "iteration"
    LOOP_COMPLETE = "loop_complete"

    # 完成
    DONE = "done"


# ============================================
# 权限行为
# ============================================

class PermissionBehavior:
    """
    工具权限行为（三态模型）

    Claude Code 的 allow/deny/ask 模型
    """

    ALLOW = "allow"   # 允许执行
    DENY = "deny"     # 拒绝执行
    ASK = "ask"       # 询问用户


# ============================================
# 分析事件名称
# ============================================

class AnalyticsEvent:
    """分析事件名称（用于追踪）"""

    # 压缩事件
    AUTO_COMPACT_SUCCEEDED = "tengu_auto_compact_succeeded"
    AUTO_COMPACT_FAILED = "tengu_auto_compact_failed"

    # Token 使用事件
    TOKEN_LIMIT_WARNING = "token_limit_warning"
    TOKEN_LIMIT_ERROR = "token_limit_error"

    # 工具执行事件
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_SUCCESS = "tool_execution_success"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"

    # SubAgent 事件
    SUBAGENT_LAUNCHED = "subagent_launched"
    SUBAGENT_COMPLETED = "subagent_completed"


# ============================================
# 帮助函数
# ============================================

def estimate_token_count(text: str) -> int:
    """
    估算文本的 token 数量

    简单估算：1 token ≈ 4 字符
    更准确的方法需要使用 tiktoken
    """
    return len(text) // 4


def get_model_context_limit(model: str) -> int:
    """获取模型的上下文限制"""
    return MODEL_CONTEXT_LIMITS.get(model, 200000)
