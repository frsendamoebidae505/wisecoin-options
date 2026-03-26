# 13wisecoin_options_live_symbol.py - 开发文档

## 文件概述

实时监控配置生成系统，从货权联动数据中提取标的合约并生成监控配置文件。

## 作者

playbonze

## 功能描述

1. 读取货权联动 Excel 文件
2. 筛选符合资金条件的标的合约
3. 生成 JSON 格式的监控标的列表

## 核心配置

```python
INPUT_EXCEL_FILE = "wisecoin-货权联动.xlsx"
SHEET_NAME = "货权联动"
OUTPUT_JSON_FILE = "wisecoin-symbol-live.json"
MIN_OPTION_OPEN_INTEREST = 0.3   # 最小期权沉淀(亿)
MIN_FUTURE_OPEN_INTEREST = 8.0   # 最小期货沉淀(亿)
```

## 核心函数

### `generate_live_symbol_config()`

主函数，生成监控配置。

**筛选逻辑：**
```python
condition = (df['期权沉淀(亿)'] > MIN_OPTION_OPEN_INTEREST) | \
            (df['期货沉淀(亿)'] > MIN_FUTURE_OPEN_INTEREST)
```

**去重规则：**
- 保持原有顺序
- 使用 `seen_symbols` 集合去重

## 输出文件

**文件名：** `wisecoin-symbol-live.json`

**格式示例：**
```json
[
    "SHFE.cu2501",
    "SHFE.au2502",
    "DCE.m2505"
]
```

## 使用方式

```bash
python 13wisecoin_options_live_symbol.py
```

## 输出示例

```
正在读取 wisecoin-货权联动.xlsx...
筛选条件: 期权沉淀(亿) > 0.3 或 期货沉淀(亿) > 8.0
原始记录数: 80, 筛选后记录数: 45
正在导出 45 个标的合约到 wisecoin-symbol-live.json...
✅ 配置文件生成成功。
```

## 依赖模块

- `pandas`: 数据处理
- `json`: JSON 操作
- `os`: 文件操作

## 注意事项

- 需要先运行货权联动数据生成
- 输出用于 `01wisecoin-options-ranking.py` 的监控标的过滤