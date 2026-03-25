#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WiseCoin 期权分析系统入口。

Usage:
    python3 run.py              # 运行一键分析
    python3 run.py --scheduler  # 启动定时调度
    python3 run.py --live       # 启动实时监控 GUI
    python3 run.py --gui        # 启动实时监控 GUI (同 --live)
"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_oneclick():
    """运行一键分析。"""
    from cli.oneclick import OptionsOneClickExecutor

    executor = OptionsOneClickExecutor()
    executor.run()
    return 0


def run_scheduler():
    """启动定时调度器。"""
    from cli.scheduler import main
    return main()


def run_live():
    """启动实时监控 GUI。"""
    # 直接运行原有的 GUI 文件
    import subprocess
    script_path = os.path.join(os.path.dirname(__file__), '18wisecoin_options_client_live.py')
    if os.path.exists(script_path):
        return subprocess.call([sys.executable, script_path])
    else:
        print(f"❌ GUI 文件不存在: {script_path}")
        return 1


if __name__ == "__main__":
    if "--scheduler" in sys.argv:
        sys.exit(run_scheduler())
    elif "--live" in sys.argv or "--gui" in sys.argv:
        sys.exit(run_live())
    else:
        sys.exit(run_oneclick())