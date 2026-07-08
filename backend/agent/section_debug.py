"""
Section Debug Utilities
调试工具模块
"""

import logging
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Debug mode flag
DEBUG_MODE = False

# Checkpoint storage
_checkpoints: list[dict] = []


def debug_log(message: str, data: Optional[Any] = None, level: str = "info") -> None:
    """
    Log debug message
    记录调试信息
    """
    if not DEBUG_MODE:
        return

    log_func = getattr(logger, level, logger.info)
    if data is not None:
        log_func(f"[DEBUG] {message}: {data}")
    else:
        log_func(f"[DEBUG] {message}")


def record_checkpoint(
    name: str,
    data: Optional[Any] = None,
    worker_id: Optional[str] = None,
    section_name: Optional[str] = None
) -> None:
    """
    Record a debug checkpoint
    记录调试检查点
    """
    if not DEBUG_MODE:
        return

    checkpoint = {
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "worker_id": worker_id,
        "section_name": section_name,
        "data": data
    }
    _checkpoints.append(checkpoint)
    logger.debug(f"[CHECKPOINT] {name} - worker={worker_id}, section={section_name}")


def get_checkpoints() -> list[dict]:
    """
    Get all recorded checkpoints
    获取所有检查点
    """
    return _checkpoints.copy()


def clear_checkpoints() -> None:
    """
    Clear all checkpoints
    清除所有检查点
    """
    _checkpoints.clear()


def enable_debug() -> None:
    """Enable debug mode"""
    global DEBUG_MODE
    DEBUG_MODE = True


def disable_debug() -> None:
    """Disable debug mode"""
    global DEBUG_MODE
    DEBUG_MODE = False
