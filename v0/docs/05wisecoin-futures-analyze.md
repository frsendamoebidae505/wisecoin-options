# 05wisecoin-futures-analyze.py - 开发文档

## 文件概述

期货标的行情分析模块，分析期权标的期货合约的行情数据。

## 作者

playbonze

## 功能描述

1. 读取期货行情数据
2. 分析期货价格走势
3. 计算技术指标
4. 生成期货分析报告

## 核心功能

### 技术指标计算

使用 TqSDK 的技术分析函数：
```python
from tqsdk.ta import ATR, BOLL, MACD
from tqsdk.tafunc import ma, ema
```

### 输入文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期货行情.xlsx | 标的期货行情 |
| wisecoin-期货行情-无期权.xlsx | 非标的期货行情 |

### 输出文件

期货分析结果，包含技术指标和趋势判断。

## 运行模式

RUN_MODE = 2（TqKq 快期模拟）

## 使用方式

```bash
python 05wisecoin-futures-analyze.py
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理

## 注意事项

- 需要先运行行情获取脚本
- 分析结果用于期权策略参考