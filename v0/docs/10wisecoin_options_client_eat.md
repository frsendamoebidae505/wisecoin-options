# 吃单脚本 (10wisecoin_options_client吃单相关) - 开发文档

## 文件概述

盘口挂单吃单操作脚本，用于监控盘口并自动吃单交易。

## 作者

playbonze

## 功能描述

1. 监控指定合约的盘口行情
2. 检测符合条件的挂单
3. 自动执行吃单交易

## 核心配置

```python
# 合约代码
INSTRUMENT_ID = "SHFE.ag2606C26000"

# 盘口价格档位
CONF_PRICE_FIELD = "bid_price1"  # 监控买一价
CONF_TARGET_PRICE = 1111          # 目标价格

# 盘口挂单数量
CONF_VOLUME_FIELD = "bid_volume1"
CONF_TARGET_VOLUME = 1            # 目标数量

# 交易动作
AUTO_DIRECTION = True             # 自动推断方向
CONF_DIRECTION = "SELL"           # BUY 或 SELL
CONF_OFFSET = "OPEN"              # OPEN 或 CLOSE
CONF_ORDER_VOLUME = 1             # 下单数量
```

## 核心函数

### `get_smart_offset(symbol, position, direction, requested_offset)`

智能获取 Offset，处理上期所/能源中心的平今平昨逻辑。

**逻辑：**
```python
if exchange in ['SHFE', 'INE']:
    if direction == 'BUY':
        pos_today = position.get('volume_short_today', 0)
    else:
        pos_today = position.get('volume_long_today', 0)
    if pos_today > 0:
        return 'CLOSETODAY'
return 'CLOSE'
```

### `main(api)`

异步主函数，执行吃单逻辑。

**流程：**
1. 获取合约行情
2. 确定交易方向
3. 检查价格和数量条件
4. 条件满足时下单

## 条件判断逻辑

```python
# 价格条件
if current_price == CONF_TARGET_PRICE:
    price_condition = True

# 数量条件
if current_volume == CONF_TARGET_VOLUME:
    volume_condition = True

# 满足条件则下单
if price_condition and volume_condition:
    api.insert_order(...)
```

## 运行模式

| RUN_MODE | 说明 |
|----------|------|
| 1 | TqSim 回测 |
| 2 | TqKq 快期模拟 |
| 6 | 实盘（金信期货等） |

## 使用方式

```bash
python 10wisecoin_options_client吃单相关.py
```

## 输出示例

```
================================================================================
🥢 盘口吃单脚本启动
--------------------------------------------------------------------------------
🎯 目标合约: SHFE.ag2606C26000
🤖 交易意图: 卖出 (方向: SELL, 开平: OPEN)
--------------------------------------------------------------------------------
📊 实时盘口行情:
   卖一价 (Ask1): 120  量: 5
   买一价 (Bid1): 1111  量: 1
   最新价 (Last): 1100

🧐 条件检查结果:
   1. ✅ 价格满足: 1111 == 1111
   2. ✅ 数量满足: 1 == 1

⚡ 条件完全符合，生成 Insert Order 并执行吃单！
发送订单: SHFE.ag2606C26000 SELL OPEN (开仓) 1手 @ 1111
📝 订单已提交, OrderID: 123456
⏳ 等待订单回报...
✅ 吃单成功！订单已完全成交
================================================================================
```

## 依赖模块

- `tqsdk`: 天勤量化SDK
- `asyncio`: 异步编程
- `math`: 数学计算

## 注意事项

- 需要配置正确的账户信息
- 上期所/能源中心区分平今平昨
- 盘口数据实时变化，条件可能快速失效