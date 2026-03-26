# 19wisecoin_options_client_arbitrage.py - 开发文档

## 文件概述

期权套利策略模块，分析期权市场中的套利机会。

## 作者

playbonze

## 功能描述

1. 读取期权和期货行情数据
2. 分析套利机会
3. 生成套利策略建议

## 核心功能

**注意：此文件较大（超过 50000 tokens），以下是功能概述：**

### 套利类型

- 时间价值套利
- 转换/逆转套利
- 跨式/宽跨式套利
- 日历价差套利

### 输出文件

| 文件名 | 说明 |
|--------|------|
| wisecoin-期权套利.xlsx | 套利机会分析结果 |

## 使用方式

```bash
python 19wisecoin_options_client_arbitrage.py
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理
- `openpyxl`: Excel 操作

## 注意事项

- 需要先运行行情获取脚本
- 套利机会基于实时数据分析