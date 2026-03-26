#!/bin/bash

################################################################################
#  WiseCoin 一键执行脚本 - 30分钟K线版本
#  功能：调用 wisecoin_trade_05_oneclick.py 并执行完整流程
################################################################################

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 执行Python脚本，运行完整流程（默认使用30min周期）
/usr/local/bin/python3 18wisecoin_options_client_live.py

# 脚本执行完成
EXIT_CODE=$?

# 【优化】不自动关闭窗口，让用户决定是否关闭
# 这样可以避免影响其他窗口的问题
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ 脚本执行成功"
else
    echo ""
    echo "❌ 脚本执行出错，退出码: $EXIT_CODE"
fi

echo ""
# exit 0
echo "按 Enter 键关闭此窗口..."
read -p ""


