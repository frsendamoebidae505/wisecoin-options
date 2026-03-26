# 17wisecoin_options_client_analyze_futures.py - 开发文档

## 文件概述

期货分析模块（实时监控版本），分析期权标的期货的行情数据。

## 作者

playbonze

## 功能描述

1. 读取临时目录中的期货行情数据
2. 计算技术指标
3. 分析期货价格走势
4. 生成期货分析报告

## 核心配置

```python
TEMP_DIR = "wisecoin_options_client_live_temp"
```

## 技术指标

使用 TqSDK 技术分析函数：
```python
from tqsdk.ta import ATR, BOLL, MACD
from tqsdk.tafunc import ma, ema
```

## 输入文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期货行情.xlsx | 标的期货行情 |
| wisecoin-期货K线.xlsx | 期货 K 线数据 |

## 使用方式

```bash
python 17wisecoin_options_client_analyze_futures.py
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理

## 注意事项

- 需要先运行数据获取和 K 线获取脚本
- 分析结果用于期权策略参考