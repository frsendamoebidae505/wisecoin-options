# 18wisecoin_options_client_live.py - 开发文档

## 文件概述

实时监控一键执行脚本，整合所有实时监控版本的数据获取和分析模块。

## 作者

playbonze

## 功能描述

按顺序执行完整的实时监控数据获取和分析流程：

1. 获取期权品种数据
2. 获取期权行情数据
3. 获取标的期货行情
4. 获取非标的期货行情
5. 获取期货 K 线数据

## 执行流程

```python
async def run_sequence():
    await get_all_option_symbols()
    await get_option_quotes_from_excel()
    await get_underlying_futures_quotes()
    await get_not_underlying_futures_quotes()
    await get_underlying_futures_klines()
    logger.info("所有期权及标的期货、非标的期货信息处理完成。")
```

## 临时目录

所有数据输出到临时目录：
```python
TEMP_DIR = "wisecoin_options_client_live_temp"
```

## 运行模式

RUN_MODE = 2（TqKq 快期模拟）

## 使用方式

```bash
# 方式一：直接运行
python 18wisecoin_options_client_live.py

# 方式二：通过 .command 文件
./18wisecoin_options_client_live.command
```

## 输出文件

| 文件名 | 目录 | 说明 |
|--------|------|------|
| wisecoin-期权品种.xlsx | 临时目录 | 期权合约列表 |
| wisecoin-期权行情.xlsx | 临时目录 | 期权实时行情 |
| wisecoin-期货行情.xlsx | 临时目录 | 标的期货行情 |
| wisecoin-期货行情-无期权.xlsx | 临时目录 | 非标的期货行情 |
| wisecoin-期货K线.xlsx | 临时目录 | 期货 K 线数据 |

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理
- `openpyxl`: Excel 操作
- `asyncio`: 异步编程

## 注意事项

- 支持断点续传
- 包含 API 重建机制
- 完成后自动退出