# 09wisecoin-futures-klines.py - 开发文档

## 文件概述

标的期货 K 线数据获取模块，从期权行情中提取标的合约并获取其日 K 线数据。

## 作者

playbonze

## 功能描述

1. 读取期权行情文件，提取所有标的期货合约
2. 批量获取每个标的的日 K 线数据
3. 按合约分 Sheet 导出到 Excel

## 核心配置

```python
QUOTE_EXCEL_FILE = "wisecoin-期权行情.xlsx"
KLINES_EXCEL_FILE = "wisecoin-期货K线.xlsx"
KLINE_DATA_LENGTH = 250   # 获取最近250个日K
KLINE_DURATION = 24 * 60 * 60  # 日K线周期（秒）
```

## 核心函数

### `get_underlying_futures_klines()`

异步函数，获取所有标的期货的 K 线数据。

**流程：**
1. 读取期权行情 Excel，提取 `underlying_symbol` 列
2. 去重获取唯一标的合约列表
3. 遍历每个合约，调用 `api.get_kline_serial()` 获取 K 线
4. 导出到 Excel（含 Summary 汇总 Sheet）

**K 线数据结构：**
- 开盘价、最高价、最低价、收盘价
- 成交量、成交额
- 时间戳（转换为可读格式）
- 品种代码标识

### 输出 Excel 结构

| Sheet名称 | 说明 |
|-----------|------|
| Summary | 所有合约最新 K 线汇总 |
| SHFE_cu | 上期所铜期货 K 线 |
| DCE_m | 大商所豆粕期货 K 线 |
| ... | 其他品种 |

**列宽自动调整 + 表头冻结**

## 运行模式

RUN_MODE = 2（TqKq 快期模拟）

## 使用方式

```bash
python 09wisecoin-futures-klines.py
```

## 输出示例

```
正在读取 wisecoin-期权行情.xlsx 以获取标的期货列表...
获取到 50 个标的期货合约，准备获取日K线数据...
[1/50] 获取 SHFE.cu2501 的日K线数据...
[2/50] 获取 SHFE.au2502 的日K线数据...
...
正在将期货K线导出到 wisecoin-期货K线.xlsx...
🚀 期货K线保存完成: wisecoin-期货K线.xlsx
   成功: 48 个合约，失败: 2 个合约
   每个合约包含最近 250 个日K线全字段数据
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`: 数据处理
- `openpyxl`: Excel 操作
- `asyncio`: 异步编程

## 注意事项

- 需要先运行 `01wisecoin-options-ranking.py` 获取期权行情
- 输出完成标志：`所有标的期货K线数据获取完成`
- 部分合约可能因数据问题获取失败