"""
BoxLite 工具测试

这个文件测试所有 22 个 BoxLite 工具的功能。

测试命名规则：
- test_<工具名>_<场景>
- 例如：test_write_file_success, test_write_file_creates_parent_dirs

运行测试：
    cd backend
    pytest tests/test_boxlite_tools.py -v

运行单个测试：
    pytest tests/test_boxlite_tools.py::test_write_file_success -v

运行某一类测试：
    pytest tests/test_boxlite_tools.py -k "write_file" -v
"""

import pytest
import sys
from pathlib import Path

# 确保可以导入 boxlite 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from boxlite.boxlite_tools import (
    write_file, read_file, delete_file, create_directory, rename_file,
    list_files, file_exists, edit_file, search_in_file, search_in_project,
    get_project_structure, shell, run_command, install_dependencies,
    start_dev_server, stop_server, get_terminal_output, get_state,
    get_preview_status, verify_changes, get_build_errors, get_visual_summary,
    ToolResult
)
from conftest import assert_tool_success, assert_tool_failure


# ============================================
# 1. write_file 测试
# ============================================

class TestWriteFile:
    """写入文件工具测试"""

    @pytest.mark.asyncio
    async def test_write_file_success(self, sandbox):
        """测试：成功写入文件"""
        result = await write_file("/test.txt", "Hello World", sandbox)

        assert_tool_success(result)
        assert "Successfully wrote" in result.result
        assert "11 bytes" in result.result  # len("Hello World") = 11

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self, sandbox):
        """测试：自动创建父目录"""
        result = await write_file("/a/b/c/deep.txt", "content", sandbox)

        assert_tool_success(result)
        # 验证文件确实存在
        content = await sandbox.read_file("a/b/c/deep.txt")
        assert content == "content"

    @pytest.mark.asyncio
    async def test_write_file_overwrites_existing(self, sandbox):
        """测试：覆盖已存在的文件"""
        await write_file("/test.txt", "original", sandbox)
        result = await write_file("/test.txt", "updated", sandbox)

        assert_tool_success(result)
        content = await sandbox.read_file("test.txt")
        assert content == "updated"

    @pytest.mark.asyncio
    async def test_write_file_normalizes_path(self, sandbox):
        """测试：路径标准化（带/和不带/都能工作）"""
        result1 = await write_file("no-slash.txt", "a", sandbox)
        result2 = await write_file("/with-slash.txt", "b", sandbox)

        assert_tool_success(result1)
        assert_tool_success(result2)


# ============================================
# 2. read_file 测试
# ============================================

class TestReadFile:
    """读取文件工具测试"""

    @pytest.mark.asyncio
    async def test_read_file_success(self, sandbox_with_files):
        """测试：成功读取文件"""
        result = await read_file("/test.txt", sandbox_with_files)

        assert_tool_success(result)
        assert "Hello World" in result.result
        assert result.data["lines"] == 3

    @pytest.mark.asyncio
    async def test_read_file_with_line_numbers(self, sandbox_with_files):
        """测试：返回带行号的内容"""
        result = await read_file("/test.txt", sandbox_with_files)

        assert_tool_success(result)
        # 检查行号格式
        assert "1|" in result.result or "   1|" in result.result

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, sandbox):
        """测试：文件不存在时返回错误"""
        result = await read_file("/nonexistent.txt", sandbox)

        assert_tool_failure(result, "not found")

    @pytest.mark.asyncio
    async def test_read_file_shows_available_files(self, sandbox_with_files):
        """测试：文件不存在时显示可用文件列表"""
        result = await read_file("/wrong.txt", sandbox_with_files)

        assert_tool_failure(result)
        assert "Available files" in result.result


# ============================================
# 3. delete_file 测试
# ============================================

class TestDeleteFile:
    """删除文件工具测试"""

    @pytest.mark.asyncio
    async def test_delete_file_success(self, sandbox_with_files):
        """测试：成功删除文件"""
        result = await delete_file("/test.txt", sandbox_with_files)

        assert_tool_success(result)
        # 验证文件已删除
        content = await sandbox_with_files.read_file("test.txt")
        assert content is None

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, sandbox):
        """测试：删除不存在的文件"""
        result = await delete_file("/nonexistent.txt", sandbox)

        # 根据实现，可能返回成功或失败
        # 这里只检查不会抛出异常
        assert isinstance(result, ToolResult)


# ============================================
# 4. create_directory 测试
# ============================================

class TestCreateDirectory:
    """创建目录工具测试"""

    @pytest.mark.asyncio
    async def test_create_directory_success(self, sandbox):
        """测试：成功创建目录"""
        result = await create_directory("/new-dir", sandbox)

        assert_tool_success(result)
        assert "Created directory" in result.result

    @pytest.mark.asyncio
    async def test_create_nested_directory(self, sandbox):
        """测试：创建嵌套目录"""
        result = await create_directory("/a/b/c", sandbox)

        assert_tool_success(result)


# ============================================
# 5. rename_file 测试
# ============================================

class TestRenameFile:
    """重命名文件工具测试"""

    @pytest.mark.asyncio
    async def test_rename_file_success(self, sandbox_with_files):
        """测试：成功重命名文件"""
        result = await rename_file("/test.txt", "/renamed.txt", sandbox_with_files)

        assert_tool_success(result)
        # 验证新文件存在
        content = await sandbox_with_files.read_file("renamed.txt")
        assert content is not None
        assert "Hello World" in content

    @pytest.mark.asyncio
    async def test_move_file_to_directory(self, sandbox_with_files):
        """测试：移动文件到另一个目录"""
        await create_directory("/dest", sandbox_with_files)
        result = await rename_file("/test.txt", "/dest/test.txt", sandbox_with_files)

        assert_tool_success(result)


# ============================================
# 6. list_files 测试
# ============================================

class TestListFiles:
    """列出文件工具测试"""

    @pytest.mark.asyncio
    async def test_list_files_root(self, sandbox_with_files):
        """测试：列出根目录文件"""
        result = await list_files("/", sandbox_with_files)

        assert_tool_success(result)
        assert "test.txt" in result.result or "src" in result.result

    @pytest.mark.asyncio
    async def test_list_files_subdirectory(self, sandbox_with_files):
        """测试：列出子目录文件"""
        result = await list_files("/src", sandbox_with_files)

        assert_tool_success(result)
        assert "app.js" in result.result


# ============================================
# 7. file_exists 测试
# ============================================

class TestFileExists:
    """检查文件存在工具测试"""

    @pytest.mark.asyncio
    async def test_file_exists_true(self, sandbox_with_files):
        """测试：文件存在"""
        result = await file_exists("/test.txt", sandbox_with_files)

        assert_tool_success(result)
        assert "exists" in result.result.lower()

    @pytest.mark.asyncio
    async def test_file_exists_false(self, sandbox):
        """测试：文件不存在"""
        result = await file_exists("/nonexistent.txt", sandbox)

        assert_tool_success(result)  # 这个工具总是返回成功
        assert "does not exist" in result.result

    @pytest.mark.asyncio
    async def test_directory_exists(self, sandbox_with_files):
        """测试：目录存在"""
        result = await file_exists("/src", sandbox_with_files)

        assert_tool_success(result)
        assert "exists" in result.result.lower()


# ============================================
# 8. edit_file 测试
# ============================================

class TestEditFile:
    """编辑文件工具测试"""

    @pytest.mark.asyncio
    async def test_edit_file_simple_replace(self, sandbox_with_files):
        """测试：简单替换"""
        result = await edit_file(
            "/test.txt",
            "Hello World",
            "Hello Universe",
            sandbox_with_files
        )

        assert_tool_success(result)
        content = await sandbox_with_files.read_file("test.txt")
        assert "Hello Universe" in content

    @pytest.mark.asyncio
    async def test_edit_file_text_not_found(self, sandbox_with_files):
        """测试：要替换的文本不存在"""
        result = await edit_file(
            "/test.txt",
            "nonexistent text",
            "replacement",
            sandbox_with_files
        )

        assert_tool_failure(result, "not found")

    @pytest.mark.asyncio
    async def test_edit_file_multiple_occurrences(self, sandbox):
        """测试：多次出现时需要 replace_all"""
        await write_file("/repeat.txt", "foo bar foo bar foo", sandbox)

        # 不使用 replace_all 应该失败
        result = await edit_file("/repeat.txt", "foo", "baz", sandbox)
        assert_tool_failure(result, "occurrences")

        # 使用 replace_all 应该成功
        result = await edit_file("/repeat.txt", "foo", "baz", sandbox, replace_all=True)
        assert_tool_success(result)


# ============================================
# 9. search_in_file 测试
# ============================================

class TestSearchInFile:
    """文件内搜索工具测试"""

    @pytest.mark.asyncio
    async def test_search_in_file_found(self, sandbox_with_files):
        """测试：找到匹配"""
        result = await search_in_file("/src/app.js", "console", sandbox_with_files)

        assert_tool_success(result)
        assert "console" in result.result.lower()

    @pytest.mark.asyncio
    async def test_search_in_file_not_found(self, sandbox_with_files):
        """测试：未找到匹配"""
        result = await search_in_file("/src/app.js", "nonexistent", sandbox_with_files)

        assert_tool_success(result)
        assert "No matches" in result.result

    @pytest.mark.asyncio
    async def test_search_in_file_regex(self, sandbox_with_files):
        """测试：正则表达式搜索"""
        result = await search_in_file("/src/app.js", r"function\s+\w+", sandbox_with_files)

        assert_tool_success(result)


# ============================================
# 10. search_in_project 测试
# ============================================

class TestSearchInProject:
    """项目搜索工具测试"""

    @pytest.mark.asyncio
    async def test_search_in_project_found(self, sandbox_with_files):
        """测试：在项目中找到匹配"""
        result = await search_in_project("function", sandbox_with_files)

        assert_tool_success(result)
        assert "function" in result.result.lower()

    @pytest.mark.asyncio
    async def test_search_in_project_with_file_pattern(self, sandbox_with_files):
        """测试：使用文件模式过滤"""
        result = await search_in_project("export", sandbox_with_files, file_pattern="*.js")

        assert_tool_success(result)


# ============================================
# 11. get_project_structure 测试
# ============================================

class TestGetProjectStructure:
    """获取项目结构工具测试"""

    @pytest.mark.asyncio
    async def test_get_project_structure(self, sandbox_with_files):
        """测试：获取项目树"""
        result = await get_project_structure(sandbox_with_files)

        assert_tool_success(result)
        assert "Project Structure" in result.result
        # 检查树形结构字符
        assert "├" in result.result or "└" in result.result


# ============================================
# 12. shell 测试
# ============================================

class TestShell:
    """Shell 命令工具测试"""

    @pytest.mark.asyncio
    async def test_shell_simple_command(self, sandbox):
        """测试：执行简单命令"""
        result = await shell("echo 'hello'", sandbox)

        assert_tool_success(result)
        assert "hello" in result.result

    @pytest.mark.asyncio
    async def test_shell_command_with_exit_code(self, sandbox):
        """测试：检查退出码"""
        result = await shell("ls", sandbox)

        assert_tool_success(result)
        assert result.data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_shell_failed_command(self, sandbox):
        """测试：失败的命令"""
        result = await shell("exit 1", sandbox)

        assert_tool_failure(result)


# ============================================
# 13. run_command 测试
# ============================================

class TestRunCommand:
    """运行命令工具测试（shell 的 wrapper）"""

    @pytest.mark.asyncio
    async def test_run_command_with_args(self, sandbox):
        """测试：带参数的命令"""
        result = await run_command("echo", ["hello", "world"], sandbox)

        assert_tool_success(result)
        assert "hello" in result.result


# ============================================
# 14. install_dependencies 测试
# ============================================

class TestInstallDependencies:
    """安装依赖工具测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow  # 标记为慢速测试
    async def test_install_all_dependencies(self, sandbox):
        """测试：安装所有依赖"""
        # 跳过如果没有 package.json
        state = sandbox.get_state()
        if "/package.json" not in state.files and "package.json" not in state.files:
            pytest.skip("No package.json in sandbox")

        result = await install_dependencies(sandbox=sandbox)
        # 只检查返回了结果，不检查成功（可能因为网络问题失败）
        assert isinstance(result, ToolResult)


# ============================================
# 15. start_dev_server 测试
# ============================================

class TestStartDevServer:
    """启动开发服务器工具测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_start_dev_server(self, sandbox):
        """测试：启动开发服务器"""
        # 这个测试需要 npm 和 package.json
        result = await start_dev_server(sandbox)

        # 只检查返回了结果
        assert isinstance(result, ToolResult)


# ============================================
# 16. stop_server 测试
# ============================================

class TestStopServer:
    """停止服务器工具测试"""

    @pytest.mark.asyncio
    async def test_stop_server_no_server(self, sandbox):
        """测试：没有服务器运行时停止"""
        result = await stop_server(sandbox)

        # 应该成功（即使没有服务器运行）
        assert_tool_success(result)


# ============================================
# 17. get_terminal_output 测试
# ============================================

class TestGetTerminalOutput:
    """获取终端输出工具测试"""

    @pytest.mark.asyncio
    async def test_get_terminal_output_empty(self, sandbox):
        """测试：没有终端时"""
        result = await get_terminal_output(sandbox)

        assert_tool_success(result)

    @pytest.mark.asyncio
    async def test_get_terminal_output_after_command(self, sandbox):
        """测试：命令执行后获取输出"""
        await shell("echo 'test output'", sandbox)
        result = await get_terminal_output(sandbox)

        assert_tool_success(result)


# ============================================
# 18. get_state 测试
# ============================================

class TestGetState:
    """获取状态工具测试"""

    @pytest.mark.asyncio
    async def test_get_state(self, sandbox_with_files):
        """测试：获取沙箱状态"""
        result = await get_state(sandbox_with_files)

        assert_tool_success(result)
        assert "BoxLite Sandbox State" in result.result
        assert "Status" in result.result
        assert "Files" in result.result

    @pytest.mark.asyncio
    async def test_get_state_has_data(self, sandbox):
        """测试：状态包含 data 字段"""
        result = await get_state(sandbox)

        assert result.data is not None
        assert "status" in result.data
        assert "files" in result.data


# ============================================
# 19. get_preview_status 测试
# ============================================

class TestGetPreviewStatus:
    """获取预览状态工具测试"""

    @pytest.mark.asyncio
    async def test_get_preview_status(self, sandbox):
        """测试：获取预览状态"""
        result = await get_preview_status(sandbox)

        assert_tool_success(result)
        assert "Preview Status" in result.result


# ============================================
# 20. verify_changes 测试
# ============================================

class TestVerifyChanges:
    """验证更改工具测试"""

    @pytest.mark.asyncio
    async def test_verify_changes(self, sandbox):
        """测试：验证更改"""
        result = await verify_changes(sandbox)

        # 应该返回验证报告
        assert "Verification Report" in result.result


# ============================================
# 21. get_build_errors 测试
# ============================================

class TestGetBuildErrors:
    """获取构建错误工具测试"""

    @pytest.mark.asyncio
    async def test_get_build_errors_none(self, sandbox):
        """测试：没有构建错误"""
        result = await get_build_errors(sandbox)

        assert_tool_success(result)
        assert "No build errors" in result.result


# ============================================
# 22. get_visual_summary 测试
# ============================================

class TestGetVisualSummary:
    """获取视觉摘要工具测试"""

    @pytest.mark.asyncio
    async def test_get_visual_summary(self, sandbox):
        """测试：获取视觉摘要"""
        result = await get_visual_summary(sandbox)

        assert_tool_success(result)
        assert "Visual Summary" in result.result


# ============================================
# 集成测试
# ============================================

class TestIntegration:
    """集成测试：测试多个工具组合使用"""

    @pytest.mark.asyncio
    async def test_write_read_edit_delete_flow(self, sandbox):
        """测试：完整的文件操作流程"""
        # 1. 写入文件
        result = await write_file("/flow-test.txt", "original content", sandbox)
        assert_tool_success(result)

        # 2. 读取文件
        result = await read_file("/flow-test.txt", sandbox)
        assert_tool_success(result)
        assert "original content" in result.result

        # 3. 编辑文件
        result = await edit_file(
            "/flow-test.txt",
            "original",
            "modified",
            sandbox
        )
        assert_tool_success(result)

        # 4. 验证编辑
        result = await read_file("/flow-test.txt", sandbox)
        assert "modified content" in result.result

        # 5. 删除文件
        result = await delete_file("/flow-test.txt", sandbox)
        assert_tool_success(result)

        # 6. 验证删除
        result = await file_exists("/flow-test.txt", sandbox)
        assert "does not exist" in result.result

    @pytest.mark.asyncio
    async def test_create_project_structure(self, sandbox):
        """测试：创建项目结构"""
        # 创建目录
        await create_directory("/src/components", sandbox)
        await create_directory("/src/utils", sandbox)

        # 创建文件
        await write_file("/src/components/Button.jsx", "export function Button() {}", sandbox)
        await write_file("/src/utils/helpers.js", "export const helper = () => {}", sandbox)

        # 获取项目结构
        result = await get_project_structure(sandbox)
        assert_tool_success(result)
        assert "components" in result.result
        assert "Button" in result.result

    @pytest.mark.asyncio
    async def test_search_and_edit(self, sandbox):
        """测试：搜索并编辑"""
        # 创建文件
        await write_file("/search-edit.js", """
function oldName() {
    return "old";
}
oldName();
""".strip(), sandbox)

        # 搜索
        result = await search_in_file("/search-edit.js", "oldName", sandbox)
        assert_tool_success(result)

        # 替换所有
        result = await edit_file(
            "/search-edit.js",
            "oldName",
            "newName",
            sandbox,
            replace_all=True
        )
        assert_tool_success(result)

        # 验证
        content = await sandbox.read_file("search-edit.js")
        assert "oldName" not in content
        assert "newName" in content
