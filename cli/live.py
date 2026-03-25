"""
WiseCoin 实时监控 GUI 入口。

启动 PyQt5 GUI 界面进行实时监控。
"""

import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入并运行 GUI
from cli.live_gui import main

if __name__ == "__main__":
    exit(main())