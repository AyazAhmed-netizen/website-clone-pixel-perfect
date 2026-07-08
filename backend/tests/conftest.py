"""
BoxLite 测试配置文件

这个文件包含 pytest fixtures（测试夹具）。
Fixtures 是测试的"准备工作"——在测试运行前创建所需的对象和环境。

关键概念：
- @pytest.fixture：标记一个函数为 fixture
- scope="function"：每个测试函数运行时都重新创建（默认）
- scope="module"：整个测试文件共享一个实例
- scope="session"：整个测试会话共享一个实例
"""

import pytest
import asyncio
import sys
import os
import shutil
from pathlib import Path

# 添加 backend 目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from boxlite.sandbox_manager import BoxLiteSandboxManager


# ============================================
# 事件循环配置
# ============================================

@pytest.fixture(scope="session")
def event_loop():
    """
    创建一个事件循环供所有异步测试使用。

    为什么需要这个：
    - Python 的 async/await 需要事件循环
    - pytest-asyncio 需要这个 fixture 来运行异步测试
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================
# Sandbox Fixtures
# ============================================

@pytest.fixture
def sandbox_id():
    """
    为每个测试生成一个唯一的 sandbox ID。

    使用唯一 ID 的好处：
    - 测试之间相互隔离
    - 不会相互干扰
    """
    import uuid
    return f"test-sandbox-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def sandbox(sandbox_id):
    """
    创建一个初始化好的 BoxLite sandbox 实例。

    这是最常用的 fixture：
    - 自动创建 sandbox
    - 测试结束后自动清理

    使用方式：
    ```python
    async def test_write_file(sandbox):
        result = await write_file("/test.txt", "content", sandbox)
        assert result.success
    ```
    """
    # 创建 sandbox manager
    manager = BoxLiteSandboxManager(sandbox_id)

    # 初始化（创建工作目录，写入默认文件）
    await manager.initialize(reset=True)

    # yield 返回 fixture 值，测试结束后继续执行清理代码
    yield manager

    # 清理：删除测试目录
    if manager.work_dir.exists():
        shutil.rmtree(manager.work_dir)


@pytest.fixture
async def sandbox_with_files(sandbox):
    """
    创建一个包含测试文件的 sandbox。

    预置文件：
    - /test.txt: 简单文本
    - /src/app.js: JavaScript 文件
    - /src/utils.js: 工具函数
    """
    # 写入测试文件
    await sandbox.write_file("/test.txt", "Hello World\nLine 2\nLine 3")
    await sandbox.write_file("/src/app.js", """
function main() {
    console.log("Hello");
    return 42;
}

export default main;
""".strip())
    await sandbox.write_file("/src/utils.js", """
export function add(a, b) {
    return a + b;
}

export function multiply(a, b) {
    return a * b;
}
""".strip())

    return sandbox


# ============================================
# Helper Functions
# ============================================

def assert_tool_success(result):
    """
    断言工具执行成功。

    使用方式：
    ```python
    result = await write_file(...)
    assert_tool_success(result)
    ```
    """
    assert result.success, f"Tool failed: {result.result}"


def assert_tool_failure(result, error_contains=None):
    """
    断言工具执行失败。

    使用方式：
    ```python
    result = await read_file("/nonexistent", sandbox)
    assert_tool_failure(result, "not found")
    ```
    """
    assert not result.success, f"Tool should have failed but succeeded: {result.result}"
    if error_contains:
        assert error_contains.lower() in result.result.lower(), \
            f"Error message should contain '{error_contains}', got: {result.result}"
