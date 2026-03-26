#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WiseCoin 期权分析系统入口。

功能：
1. 检查当前目录是否有完整的 xlsx 文件
2. 如果没有，先运行 oneclick 生成数据
3. 自动启动实时监控 GUI

Usage:
    python3 run.py              # 智能模式：检查数据 -> 生成数据 -> 启动GUI
    python3 run.py --force      # 强制重新生成数据，然后启动GUI
    python3 run.py --no-gui     # 只生成数据，不启动GUI
    python3 run.py --scheduler  # 启动定时调度
    python3 run.py --live       # 仅启动实时监控 GUI
"""
import sys
import os
import subprocess
import time
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))


# 必需的 xlsx 文件列表
REQUIRED_XLSX_FILES = [
    "wisecoin-期权行情.xlsx",
    "wisecoin-期权排行.xlsx",
    "wisecoin-期权参考.xlsx",
    "wisecoin-货权联动.xlsx",
    "wisecoin-市场概览.xlsx",
    "wisecoin-期货K线.xlsx",
]


def check_xlsx_files() -> tuple:
    """
    检查必需的 xlsx 文件是否存在。

    Returns:
        (存在数量, 缺失文件列表)
    """
    missing = []
    for f in REQUIRED_XLSX_FILES:
        if not (PROJECT_ROOT / f).exists():
            missing.append(f)
    return len(REQUIRED_XLSX_FILES) - len(missing), missing


def run_oneclick():
    """运行一键分析生成数据。"""
    print("=" * 60)
    print("开始执行一键数据生成...")
    print("=" * 60)

    try:
        # 使用 subprocess 调用模块
        result = subprocess.run(
            [sys.executable, "-m", "cli.oneclick"],
            cwd=str(PROJECT_ROOT),
            check=False
        )
        return result.returncode
    except Exception as e:
        print(f"❌ 执行一键分析失败: {e}")
        return 1


def run_scheduler():
    """启动定时调度器。"""
    try:
        from cli.scheduler import main
        return main()
    except ImportError:
        print("❌ scheduler 模块未找到")
        return 1


def is_gui_running() -> bool:
    """检查 GUI 是否已经在运行。"""
    try:
        # 检查是否有 Python 进程在运行 live_gui
        result = subprocess.run(
            ["pgrep", "-f", "cli.live_gui"],
            capture_output=True,
            text=True
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def run_live():
    """启动实时监控 GUI。"""
    print("=" * 60)
    print("启动实时监控 GUI...")
    print("=" * 60)

    # 检查是否已经在运行
    if is_gui_running():
        print("⚠️ GUI 已经在运行中")
        return 0

    try:
        result = subprocess.run(
            [sys.executable, "-m", "cli.live_gui"],
            cwd=str(PROJECT_ROOT),
            check=False
        )
        return result.returncode
    except Exception as e:
        print(f"❌ 启动 GUI 失败: {e}")
        return 1


def main():
    """主入口。"""
    force_mode = "--force" in sys.argv
    no_gui = "--no-gui" in sys.argv
    scheduler_mode = "--scheduler" in sys.argv
    live_only = "--live" in sys.argv or "--gui" in sys.argv

    # 移除参数
    for arg in ["--force", "--no-gui", "--scheduler", "--live", "--gui"]:
        if arg in sys.argv:
            sys.argv.remove(arg)

    # 模式1：仅启动调度器
    if scheduler_mode:
        return run_scheduler()

    # 模式2：仅启动 GUI（不检查数据）
    if live_only:
        return run_live()

    # 模式3：智能模式（检查数据 -> 生成数据 -> 启动GUI）
    print("=" * 60)
    print("WiseCoin 期权分析系统")
    print("=" * 60)

    # 检查数据文件
    existing_count, missing_files = check_xlsx_files()
    total_count = len(REQUIRED_XLSX_FILES)

    print(f"\n📊 数据文件检查: {existing_count}/{total_count} 个文件存在")

    if missing_files:
        print(f"❌ 缺失文件:")
        for f in missing_files:
            print(f"   - {f}")

    # 判断是否需要生成数据
    need_generate = force_mode or len(missing_files) > 0

    if need_generate:
        print(f"\n{'🔄 强制重新生成数据...' if force_mode else '⏳ 开始生成数据...'}")

        start_time = time.time()
        ret = run_oneclick()
        elapsed = time.time() - start_time

        if ret != 0:
            print(f"\n❌ 数据生成失败 (耗时 {elapsed:.1f}s)")
            return ret

        print(f"\n✅ 数据生成完成 (耗时 {elapsed:.1f}s)")

        # 再次检查
        existing_count, missing_files = check_xlsx_files()
        if missing_files:
            print(f"\n⚠️ 仍有 {len(missing_files)} 个文件缺失")
            for f in missing_files:
                print(f"   - {f}")
    else:
        print("\n✅ 所有数据文件完整，无需重新生成")

    # 启动 GUI
    if no_gui:
        print("\n📝 --no-gui 模式，跳过 GUI 启动")
        return 0

    print("\n" + "=" * 60)
    return run_live()


if __name__ == "__main__":
    sys.exit(main())