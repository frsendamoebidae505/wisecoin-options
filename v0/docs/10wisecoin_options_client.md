# 10wisecoin_options_client.py - 开发文档

## 文件概述

期权品种数据获取模块，获取所有期权合约并按产品分类导出。

## 作者

playbonze

## 功能描述

1. 使用 TqSDK 获取所有未到期的期权合约
2. 过滤股票期权（SSE、SZSE）
3. 获取合约详细信息
4. 按产品分组导出到 Excel

## 核心配置

```python
SYMBOL_EXCEL_FILE = "wisecoin-期权品种.xlsx"

OPTION_FILTER_CONFIG = {
    'exclude_exchanges': ['SSE', 'SZSE'],
    'max_quote_num': 99999,
}
```

## 核心函数

### `get_all_option_symbols()`

异步函数，获取所有期权合约信息。

**流程：**
1. 调用 `api.query_quotes(ins_class='OPTION', expired=False)`
2. 过滤掉股票期权
3. 分批获取合约详细信息（每批 500 个）
4. 按 `product` 字段分组
5. 导出 Excel

**产品提取逻辑：**
```python
def get_product(row):
    symbol = row['underlying_symbol']
    # SHFE.cu2401 -> SHFE.cu
    parts = str(symbol).split('.')
    exchange = parts[0]
    code_match = re.match(r'^[a-zA-Z]+', parts[1])
    return f"{exchange}.{code_match.group(0)}"
```

## 排序规则

导出时按 `underlying_symbol` 和 `strike_price` 排序：
```python
sort_cols = []
if 'underlying_symbol' in group.columns:
    sort_cols.append('underlying_symbol')
if 'strike_price' in group.columns:
    sort_cols.append('strike_price')
```

## 运行模式

RUN_MODE = 2（TqKq 快期模拟）

## 使用方式

```bash
python 10wisecoin_options_client.py
```

## 输出文件

`wisecoin-期权品种.xlsx` - 每个品种一个 Sheet

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`: 数据处理
- `openpyxl`: Excel 操作
- `asyncio`: 异步编程

## 注意事项

- 输出用于后续行情获取的输入
- Sheet 名称限制 31 字符
- 列宽自动调整