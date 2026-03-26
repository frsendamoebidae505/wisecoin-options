#!/bin/bash

################################################################################
#  WiseCoin 期权分析系统启动脚本
#  功能：检测并清理旧进程，然后启动 run.py
################################################################################

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "WiseCoin 期权分析系统"
echo "============================================================"
echo ""

# 检测运行中的 run.py 进程
RUNNING_PIDS=$(pgrep -f "python.*run\.py" 2>/dev/null | grep -v "$$" 2>/dev/null)

if [ -n "$RUNNING_PIDS" ]; then
    echo "⚠️  检测到运行中的 run.py 进程:"
    echo "$RUNNING_PIDS" | while read pid; do
        if [ -n "$pid" ]; then
            ps -p "$pid" -o pid,command 2>/dev/null | tail -1
        fi
    done
    echo ""
    echo "正在清理旧进程..."

    # 先尝试优雅终止
    echo "$RUNNING_PIDS" | xargs kill 2>/dev/null
    sleep 2

    # 检查是否还有残留进程
    REMAINING_PIDS=$(pgrep -f "python.*run\.py" 2>/dev/null | grep -v "$$" 2>/dev/null)
    if [ -n "$REMAINING_PIDS" ]; then
        echo "强制终止残留进程..."
        echo "$REMAINING_PIDS" | xargs kill -9 2>/dev/null
        sleep 1
    fi

    echo "✅ 旧进程已清理"
    echo ""
fi

# 检测运行中的 live_gui 进程
GUI_PIDS=$(pgrep -f "cli\.live_gui" 2>/dev/null)

if [ -n "$GUI_PIDS" ]; then
    echo "⚠️  检测到运行中的 GUI 进程:"
    echo "$GUI_PIDS" | while read pid; do
        if [ -n "$pid" ]; then
            ps -p "$pid" -o pid,command 2>/dev/null | tail -1
        fi
    done
    echo ""
    echo "正在清理 GUI 进程..."

    # 先尝试优雅终止
    echo "$GUI_PIDS" | xargs kill 2>/dev/null
    sleep 2

    # 检查是否还有残留
    REMAINING_GUI=$(pgrep -f "cli\.live_gui" 2>/dev/null)
    if [ -n "$REMAINING_GUI" ]; then
        echo "强制终止残留 GUI 进程..."
        echo "$REMAINING_GUI" | xargs kill -9 2>/dev/null
        sleep 1
    fi

    echo "✅ GUI 进程已清理"
    echo ""
fi

echo "============================================================"
echo "启动 WiseCoin 期权分析系统..."
echo "============================================================"
echo ""

# 执行 run.py
/usr/local/bin/python3 run.py

# 脚本执行完成
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 程序执行完成"
else
    echo "❌ 程序执行出错，退出码: $EXIT_CODE"
fi

echo ""
echo "按 Enter 键关闭此窗口..."
read -p ""