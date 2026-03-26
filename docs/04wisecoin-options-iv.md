# 04wisecoin-options-iv.py - 开发文档

## 文件概述

期权隐含波动率计算模块，用于计算期权隐含波动率并生成波动率微笑曲线。

## 作者

playbonze

## 功能描述

1. 读取期权行情和参考数据
2. 计算各期权的隐含波动率（IV）
3. 生成波动率微笑曲线数据
4. 输出波动率分析结果

## 核心功能

### 隐含波动率计算

使用 TqSDK 提供的期权定价函数计算 IV：

```python
from tqsdk.ta import OPTION_IMPV, OPTION_GREEKS
```

### 输入文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期权行情.xlsx | 期权实时行情 |
| wisecoin-期权参考.xlsx | 期权参考数据 |

### 输出文件

包含隐含波动率数据的 Excel 文件，支持：
- 波动率微笑曲线
- 各行权价的 IV 数据
- 分品种的波动率分析

## 依赖模块

- `tqsdk`: 天勤量化SDK（期权定价函数）
- `pandas`/`numpy`: 数据处理
- `scipy`: 数值计算（如需要）

## 使用方式

```bash
python 04wisecoin-options-iv.py
```

## 运行时机

在一键执行流程中位于期权分析之后：
```
01wisecoin-options-ranking.py -> 03wisecoin-options-analyze.py -> 04wisecoin-options-iv.py
```

## 注意事项

- 需要标的期货价格数据
- IV 计算对价格敏感，需确保行情数据有效