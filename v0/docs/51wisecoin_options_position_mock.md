# 51wisecoin_options_position_mock.py - 开发文档

## 文件概述

期权模拟持仓生成器，根据策略和套利文件生成模拟持仓数据。

## 作者

playbonze

## 功能描述

1. 读取策略明细和套利文件
2. 解析交易指令生成持仓记录
3. 合并相同合约的持仓
4. 导出模拟持仓 Excel

## 核心配置

```python
TEMP_DIR = "wisecoin_options_client_live_temp"
TEMPLATE_FILE = "wisecoin-持仓.xlsx"
OUTPUT_EXCEL_FILE = "wisecoin-模拟持仓.xlsx"
STRATEGY_FILE = "wisecoin-期权策略.xlsx"
ARBITRAGE_FILE = "wisecoin-期权套利.xlsx"
```

## 核心函数

### `load_template()`

加载持仓模板文件，获取字段列表。

### `parse_legs_from_text(text)`

解析交易指令文本，提取腿合约信息。

**支持的格式：**
```
买入SHFE.cu2501C50000*1@100；卖出SHFE.cu2501P48000*1@80
```

**返回结构：**
```python
[
    {'action': 'buy', 'symbol': 'SHFE.cu2501C50000', 'qty': 1, 'price': 100},
    {'action': 'sell', 'symbol': 'SHFE.cu2501P48000', 'qty': 1, 'price': 80}
]
```

### `build_position_row_from_leg(leg, template_cols, defaults)`

根据腿合约信息构建持仓记录行。

### `load_strategy_positions(template_cols, defaults)`

从策略明细文件加载持仓。

### `load_arbitrage_positions(template_cols, defaults)`

从套利文件加载持仓。

### `merge_records(records)`

合并相同合约的多条持仓记录。

## 输出文件

**文件名：** `wisecoin-模拟持仓.xlsx`

**Sheet 结构：**
- 每个标的+策略组合一个 Sheet
- Sheet 名称格式：`标的_策略` 或 `标的_到期月_策略`

## 排除的套利 Sheet

```python
EXCLUDED_ARBITRAGE_SHEETS = {"套利汇总", "策略指南", "时间价值低估", "转换逆转套利"}
```

## 使用方式

```bash
python 51wisecoin_options_position_mock.py
```

## 输出示例

```
✅ 模拟持仓导出完成: wisecoin-模拟持仓.xlsx，分页数 12，记录数 35
```

## 依赖模块

- `pandas`/`numpy`: 数据处理
- `openpyxl`: Excel 操作
- `re`: 正则表达式

## 注意事项

- 需要持仓模板文件 `wisecoin-持仓.xlsx`
- 需要策略文件和套利文件
- 用于模拟交易测试