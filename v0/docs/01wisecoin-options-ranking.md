# 01wisecoin-options-ranking.py - 开发文档

## 文件概述

期权趋势排名分析交易系统的核心数据获取模块，用于获取期权合约列表、详细信息、行情数据，并按产品分类导出。

## 作者

playbonze

## 功能描述

基于 TqSDK 的期权品种获取与行情同步系统，主要功能包括：

1. 获取所有期权合约信息
2. 过滤股票期权（只保留商品期权和股指期权）
3. 按产品分组导出到 Excel
4. 获取期权实时行情数据
5. 获取标的期货和非标的期货行情

## 核心配置

### 期权筛选参数

```python
OPTION_FILTER_CONFIG = {
    'exclude_exchanges': ['SSE', 'SZSE'],  # 排除的交易所（股票期权）
    'max_quote_num': 99999,                  # 获取的期权行情个数
}
```

### 运行模式配置

| RUN_MODE | 说明 |
|----------|------|
| 1 | TqSim 回测模式 |
| 2 | TqKq 快期模拟 |
| 3 | Simnow 模拟 |
| 4 | 渤海期货实盘 |
| 5 | 华安期货实盘 |
| 6 | 金信期货实盘 |
| 7 | 东吴期货实盘 |
| 8 | 宏源期货实盘 |

## 核心函数

### `get_all_option_symbols()`

获取所有期权合约并按产品分类导出。

**流程：**
1. 使用 `api.query_quotes(ins_class='OPTION')` 获取所有期权
2. 过滤掉 SSE、SZSE 交易所的股票期权
3. 加载 `wisecoin-symbol-live.json` 中的监控标的列表
4. 分批获取合约详细信息
5. 按 product 字段分组导出到 Excel

**输出文件：** `wisecoin-期权品种.xlsx`

### `get_option_quotes_from_excel()`

从 Excel 读取期权品种并获取实时行情。

**特性：**
- 支持"断点续传"：检测已有行情文件，只获取缺失的数据
- 分批订阅（每批 200 个）
- 定期保存（每 3000 个保存一次）
- API 重建机制（每 3000 个重建一次，防止连接超时）

**输出文件：** `wisecoin-期权行情.xlsx`

### `get_underlying_futures_quotes()`

获取标的期货的行情数据。

**流程：**
1. 读取期权行情文件，提取 `underlying_symbol` 列
2. 获取金融期货（CFFEX）合约
3. 批量获取合约信息和行情
4. 按产品分组导出

**输出文件：** `wisecoin-期货行情.xlsx`

**支持的金融期货：**
- 股指期货：IF, IC, IH, IM
- 国债期货：T, TF, TS, TL

### `get_not_underlying_futures_quotes()`

获取非期权标的的期货行情。

**流程：**
1. 获取全市场期货列表
2. 过滤掉期权标的
3. 获取详细信息和行情

**输出文件：** `wisecoin-期货行情-无期权.xlsx`

## 辅助函数

### `_save_quotes_to_excel()`

内部辅助函数，将行情数据保存到 Excel。

**参数：**
- `file_path`: 输出文件路径
- `sheet_df_map`: 工作表数据映射
- `all_quote_data`: 所有行情数据字典
- `current_count`: 当前进度
- `total_count`: 总数量

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理
- `openpyxl`: Excel操作
- `asyncio`: 异步编程

## 使用方式

```bash
python 01wisecoin-options-ranking.py
```

## 输出文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期权品种.xlsx | 期权合约列表（按产品分Sheet） |
| wisecoin-期权行情.xlsx | 期权实时行情数据 |
| wisecoin-期货行情.xlsx | 标的期货行情数据 |
| wisecoin-期货行情-无期权.xlsx | 非标的期货行情数据 |

## 注意事项

- 需要配置有效的 TqAuth 认证信息
- 大量数据获取时会有 API 重建机制
- 支持断点续传，中断后可继续获取