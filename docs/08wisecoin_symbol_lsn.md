# 08wisecoin_symbol_lsn.py - 开发文档

## 文件概述

期货开仓方向生成器，从市场概览数据中提取品种情绪并生成开仓方向配置文件。

## 作者

playbonze

## 功能描述

1. 读取市场概览 Excel 文件
2. 筛选沉淀资金大于 0.5 亿的品种
3. 根据品种情绪映射开仓方向
4. 输出 JSON 配置文件

## 核心函数

### `generate_symbol_lsn()`

主函数，执行开仓方向生成逻辑。

**流程：**
1. 读取 `wisecoin-市场概览.xlsx` 的 `期货品种` 分页
2. 筛选 `沉淀资金(亿) > 0.5` 的品种
3. 映射 `品种情绪` 到 `开仓方向`
4. 输出到 `wisecoin-symbol-lsn.json`

## 输入文件

| 文件名 | 分页 | 说明 |
|--------|------|------|
| wisecoin-市场概览.xlsx | 期货品种 | 市场概览数据 |

## 情绪映射规则

```python
sentiment_map = {
    '偏多': 'LONG',
    '偏空': 'SHORT',
    '中性': 'NONE'
}
```

## 输出文件

**文件名：** `../wisecoin-symbol-lsn.json`（上级目录）

**格式示例：**
```json
[
    {"品种代码": "cu", "开仓方向": "LONG"},
    {"品种代码": "au", "开仓方向": "SHORT"},
    {"品种代码": "rb", "开仓方向": "NONE"}
]
```

## 筛选条件

```python
# 沉淀资金(亿) > 0.5
filtered_df = df[df['沉淀资金(亿)'] > 0.5].copy()
```

## 使用方式

```bash
python 08wisecoin_symbol_lsn.py
```

## 输出示例

```
Successfully generated ../wisecoin-symbol-lsn.json with 45 symbols.
```

或

```
No symbols found with '沉淀资金(亿)' > 0.5.
```

## 依赖模块

- `pandas`: 数据处理
- `json`: JSON 文件操作
- `os`: 文件路径操作

## 注意事项

- 需要先运行市场概览数据生成脚本
- 输出文件在上级目录
- 沉淀资金阈值可在代码中调整