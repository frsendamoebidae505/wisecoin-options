# 14wisecoin_options_client_data_klines.py - 开发文档

## 文件概述

期货 K 线数据获取模块（实时监控版本），获取标的期货的日 K 线数据。

## 作者

playbonze

## 功能描述

1. 读取临时目录中的期权行情文件
2. 提取所有标的期货合约
3. 获取每个合约的日 K 线数据
4. 导出到 Excel

## 核心配置

```python
TEMP_DIR = "wisecoin_options_client_live_temp"
QUOTE_EXCEL_FILE = os.path.join(TEMP_DIR, "wisecoin-期权行情.xlsx")
KLINES_EXCEL_FILE = os.path.join(TEMP_DIR, "wisecoin-期货K线.xlsx")
KLINE_DATA_LENGTH = 250  # 获取最近250个日K
KLINE_DURATION = 24 * 60 * 60  # 日K线周期（秒）
```

## 核心函数

### `get_underlying_futures_klines()`

异步函数，获取标的期货 K 线数据。

**流程：**
1. 读取期权行情文件，提取 `underlying_symbol`
2. 去重获取唯一标的列表
3. 遍历获取 K 线数据
4. 导出到 Excel（含 Summary Sheet）

**K 线数据字段：**
- datetime：时间戳
- open/high/low/close：OHLC
- volume：成交量
- open_interest：持仓量
- symbol：合约代码
- product：品种代码

## Excel 输出结构

| Sheet名称 | 说明 |
|-----------|------|
| Summary | 所有合约最新 K 线汇总 |
| 合约分页 | 每个合约一个 Sheet |

**格式优化：**
- 列宽自动调整
- 表头冻结（freeze_panes）

## 运行模式

RUN_MODE = 2（TqKq 快期模拟）

## 使用方式

```bash
python 14wisecoin_options_client_data_klines.py
```

## 输出示例

```
正在读取 wisecoin_options_client_live_temp/wisecoin-期权行情.xlsx 以获取标的期货列表...
获取到 50 个标的期货合约，准备获取日K线数据...
[1/50] 获取 SHFE.cu2501 的日K线数据...
...
🚀 期货K线保存完成: wisecoin_options_client_live_temp/wisecoin-期货K线.xlsx
   成功: 48 个合约，失败: 2 个合约
   每个合约包含最近 250 个日K线全字段数据
所有标的期货K线数据获取完成。
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`: 数据处理
- `openpyxl`: Excel 操作
- `asyncio`: 异步编程

## 注意事项

- 需要先运行 `14wisecoin_options_client_data.py`
- 数据输出到临时目录