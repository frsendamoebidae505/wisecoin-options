# 32wisecoin_options_position_deal_1sell.py - 开发文档

## 文件概述

期权持仓卖出处理模块，执行卖出平仓操作。

## 作者

playbonze

## 功能描述

1. 读取持仓目标文件
2. 检查卖出条件
3. 执行卖出操作

## 核心功能

**注意：此文件较大（约 15000 tokens），以下是功能概述：**

### 卖出条件检查

- 止盈触发
- 止损触发
- 到期处理
- 策略调整

### 交易执行

使用 TqSDK 执行卖出：
```python
order = api.insert_order(
    symbol=symbol,
    direction='SELL',
    offset='CLOSE',  # 或 CLOSETODAY
    volume=volume,
    limit_price=price
)
```

## 使用方式

```bash
python 32wisecoin_options_position_deal_1sell.py
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `pandas`/`numpy`: 数据处理

## 注意事项

- 需要设置正确的运行模式
- 上期所/能源中心区分平今平昨