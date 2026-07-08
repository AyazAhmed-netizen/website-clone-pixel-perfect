#!/usr/bin/env python3
"""
BoxLite 工具测试运行脚本

使用方法：
    python tests/run_tests.py              # 运行所有测试
    python tests/run_tests.py -v           # 详细输出
    python tests/run_tests.py -k write     # 只运行包含 "write" 的测试
    python tests/run_tests.py --fast       # 跳过慢速测试
    python tests/run_tests.py --report     # 生成 HTML 报告

快速开始：
    cd backend
    pip install pytest pytest-asyncio pytest-html
    python tests/run_tests.py
"""

import subprocess
import sys
import os
from pathlib import Path

# 切换到 backend 目录
backend_dir = Path(__file__).parent.parent
os.chdir(backend_dir)

def main():
    """运行测试"""
    # 基础命令
    cmd = [sys.executable, "-m", "pytest", "tests/"]

    # 解析参数
    args = sys.argv[1:]

    # 默认选项
    if not any(arg.startswith("-v") for arg in args):
        cmd.append("-v")  # 默认详细输出

    # 处理自定义参数
    if "--fast" in args:
        args.remove("--fast")
        cmd.extend(["-m", "not slow"])  # 跳过慢速测试

    if "--report" in args:
        args.remove("--report")
        cmd.extend(["--html=tests/report.html", "--self-contained-html"])

    # 添加其他参数
    cmd.extend(args)

    # 显示要运行的命令
    print(f"\n{'='*60}")
    print("BoxLite 工具测试")
    print(f"{'='*60}")
    print(f"运行命令: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    # 运行测试
    result = subprocess.run(cmd)

    # 返回退出码
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
