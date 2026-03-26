# 06wisecoin_oneclick.command - 开发文档

## 文件概述

macOS 可执行脚本，用于一键启动 WiseCoin 期权分析流程。

## 文件类型

Bash Shell 脚本（.command 文件在 macOS 上双击可执行）

## 功能描述

1. 切换到脚本所在目录
2. 调用 `06wisecoin_oneclick.py` 执行完整流程
3. 显示执行结果并等待用户确认关闭

## 脚本内容

```bash
#!/bin/bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 执行Python脚本
/usr/local/bin/python3 06wisecoin_oneclick.py

# 检查执行结果
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 脚本执行成功"
else
    echo "❌ 脚本执行出错，退出码: $EXIT_CODE"
fi

# 等待用户确认
echo "按 Enter 键关闭此窗口..."
read -p ""
```

## 使用方式

### 方式一：双击执行

在 Finder 中双击 `06wisecoin_oneclick.command` 文件。

### 方式二：终端执行

```bash
./06wisecoin_oneclick.command
```

## 执行权限

如遇到权限问题，执行：
```bash
chmod +x 06wisecoin_oneclick.command
```

## Python 路径

脚本使用固定路径：
```bash
/usr/local/bin/python3
```

如需修改，编辑脚本中的 Python 路径。

## 注意事项

- 窗口不会自动关闭，需按 Enter 键确认
- 方便查看执行结果和可能的错误信息