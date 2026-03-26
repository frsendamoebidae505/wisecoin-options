# 14wisecoin_options_client_data.py - 开发文档

## 文件概述

期权品种与行情获取模块（实时监控版本），在临时目录中获取期权品种和行情数据。

## 作者

playbonze

## 功能描述

1. 获取所有期权合约信息
2. 获取期权实时行情（支持断点续传）
3. 获取标的期货行情
4. 获取非标的期货行情

## 核心配置

```python
TEMP_DIR = "wisecoin_options_client_live_temp"
SYMBOL_EXCEL_FILE = os.path.join(TEMP_DIR, "wisecoin-期权品种.xlsx")

OPTION_FILTER_CONFIG = {
    'exclude_exchanges': ['SSE', 'SZSE'],
    'max_quote_num': 99999,
}
```

## 核心函数

### `get_all_option_symbols()`

获取所有期权合约并按产品分类导出。

**特性：**
- 加载 `wisecoin-symbol-live.json` 过滤监控标的
- 分批获取合约信息（每批 500 个）

### `get_option_quotes_from_excel()`

获取期权行情，支持断点续传。

**断点续传逻辑：**
```python
if os.path.exists(QUOTE_EXCEL_FILE):
    # 加载已有数据
    for _, row in existing_df.iterrows():
        all_quote_data[sym] = row.to_dict()
        already_fetched_symbols.add(sym)

# 只获取缺失的数据
symbols_to_fetch_now = [s for s in unique_symbols if s not in already_fetched_symbols]
```

**API 重建机制：**
- 每 3000 个合约保存一次
- 每 3000 个合约重建 TqApi 防止连接超时

### `get_underlying_futures_quotes()`

获取标的期货行情，包含金融期货。

**支持的金融期货：**
```python
financial_prefixes = ['CFFEX.IF', 'CFFEX.IC', 'CFFEX.IH', 'CFFEX.IM',
                      'CFFEX.T', 'CFFEX.TF', 'CFFEX.TS', 'CFFEX.TL']
```

### `get_not_underlying_futures_quotes()`

获取非期权标的的期货行情。

## 输出文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期权品种.xlsx | 期权合约列表 |
| wisecoin-期权行情.xlsx | 期权实时行情 |
| wisecoin-期货行情.xlsx | 标的期货行情 |
| wisecoin-期货行情-无期权.xlsx | 非标的期货行情 |

## 运行模式

RUN_MODE = 2（TqKq 快期模拟）

## 使用方式

```bash
python 14wisecoin_options_client_data.py
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理
- `openpyxl`: Excel 操作
- `asyncio`: 异步编程

## 注意事项

- 数据输出到临时目录 `wisecoin_options_client_live_temp`
- 支持断点续传，中断后可继续
- 完成标志：`所有期权及标的期货、非标的期货信息处理完成`