# 33wisecoin_options_position_deal_2buy.py - 开发文档

## 文件概述

期权持仓买入处理模块，执行买入开仓操作。

## 作者

playbonze

## 功能描述

1. 读取策略建议文件
2. 筛选买入标的
3. 执行买入操作

## 核心功能

**注意：此文件较大（约 15000 tokens），以下是功能概述：**

### 买入条件筛选

- 符合策略条件
- 资金充足
- 风险可控

### 交易执行

使用 TqSDK 执行买入：
```python
order = api.insert_order(
    symbol=symbol,
    direction='BUY',
    offset='OPEN',
    volume=volume,
    limit_price=price
)
```

## 使用方式

```bash
python 33wisecoin_options_position_deal_2buy.py
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理

## 注意事项

- 需要设置正确的运行模式
- 注意保证金风险控制