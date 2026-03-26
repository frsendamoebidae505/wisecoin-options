"""
花氏量化pb-quant by playbonze
盘口挂单吃单操作脚本
"""

import asyncio
import logging
import sys
import os
import math
import numpy as np
from tqsdk import TqApi, TqAuth, TqAccount
from tqsdk.tafunc import time_to_datetime, time_to_str
from pb_quant_seektop_common import UnifiedLogger

# 设置统一日志
logger = UnifiedLogger.setup_logger_auto(__file__)

# ================= 配置区域 =================

# 1. 合约代码
# 比如: SHFE.ni2602C130000
# INSTRUMENT_ID = "SHFE.ni2609C150000"
INSTRUMENT_ID = "SHFE.ag2606C26000"

# 2. 盘口价格档位配置
# 监控的价格字段: 'ask_price1' (卖一价) 或 'bid_price1' (买一价)
# 如果我们要“吃单”买入，通常监控卖一价 (ask_price1)
# 如果我们要“吃单”卖出，通常监控买一价 (bid_price1)
CONF_PRICE_FIELD = "ask_price1" 
# CONF_TARGET_PRICE = 21240  # 目标价格
CONF_TARGET_PRICE = 4646  # 目标价格

# 3. 盘口挂单档位及数量配置
# 监控的数量字段: 'ask_volume1' 或 'bid_volume1'
CONF_VOLUME_FIELD = "ask_volume1"
CONF_TARGET_VOLUME = 1    # 最小符合数量

# 4. 交易动作配置
# 自动推断方向: True (根据价格字段自动判断 BUY/SELL), False (使用 CONF_DIRECTION)
AUTO_DIRECTION = True
CONF_DIRECTION = "BUY"    # 'BUY' or 'SELL'

# 开平配置: 'OPEN' (开仓), 'CLOSE' (平仓)
# 注意：脚本会自动处理上期所/能源中心的平今/平昨逻辑
CONF_OFFSET = "CLOSE" 

# 吃单数量 (通常等于或小于盘口挂单数量)
# 这里设置为 'MATCH' 则吃掉盘口符合的数量(最大为CONF_TARGET_VOLUME或更多)，或者指定具体数字
CONF_ORDER_VOLUME = 1

# ===========================================


def get_smart_offset(symbol, position, direction, requested_offset):
    """
    智能获取Offset，适配交易所逻辑（特别是上期所平今/平昨）
    
    Args:
        symbol: 合约代码
        position: 持仓对象
        direction: 下单方向 (BUY/SELL)
        requested_offset: 请求的开平操作 (OPEN/CLOSE)
    """
    if requested_offset == 'OPEN':
        return 'OPEN'
        
    exchange = symbol.split('.')[0]
    
    # 上期所和上期能源需要区分平今平昨
    if exchange in ['SHFE', 'INE']:
        # 如果是平仓
        # BUY (平空) -> 检查 short position
        # SELL (平多) -> 检查 long position
        if direction == 'BUY':
            pos_today = position.get('volume_short_today', 0)
        else:
            pos_today = position.get('volume_long_today', 0)
            
        if pos_today > 0:
            return 'CLOSETODAY'
            
    return 'CLOSE'


async def main(api):
    logger.info("=" * 80)
    logger.info("🥢 盘口吃单脚本启动")
    logger.info("-" * 80)
    logger.info(f"🎯 目标合约: {INSTRUMENT_ID}")
    
    try:
        # 获取行情
        logger.info("⏳ 正在获取盘口行情...")
        quote = await api.get_quote(INSTRUMENT_ID)
        
        # 确定交易方向
        direction = CONF_DIRECTION
        if AUTO_DIRECTION:
            if "ask" in CONF_PRICE_FIELD:
                direction = "BUY"
            elif "bid" in CONF_PRICE_FIELD:
                direction = "SELL"
            else:
                logger.error(f"❌ 无法自动推断交易方向 (字段: {CONF_PRICE_FIELD})，请检查配置")
                return

        direction_cn = "买入" if direction == "BUY" else "卖出"
        logger.info(f"🤖 交易意图: {direction_cn} (方向: {direction}, 开平: {CONF_OFFSET})")
        logger.info("-" * 80)

        # 获取当前盘口数据
        current_price = quote.get(CONF_PRICE_FIELD)
        current_volume = quote.get(CONF_VOLUME_FIELD)
        
        # 打印详细盘口
        logger.info(f"📊 实时盘口行情:")
        logger.info(f"   卖一价 (Ask1): {quote.ask_price1}  量: {quote.ask_volume1}")
        logger.info(f"   买一价 (Bid1): {quote.bid_price1}  量: {quote.bid_volume1}")
        logger.info(f"   最新价 (Last): {quote.last_price}")
        
        # 校验数据有效性
        if math.isnan(current_price):
            logger.warning(f"⚠️  盘口价格无效 ({CONF_PRICE_FIELD} is NaN)，无法执行")
            return
            
        # ================= 条件判断逻辑 =================
        condition_met = False
        price_msg = ""
        volume_msg = ""
        
        # 1. 价格条件判断
        # BUY: 市场卖价 <= 目标价 (便宜或相等)
        # SELL: 市场买价 >= 目标价 (贵或相等)
        if direction == "BUY":
            if current_price == CONF_TARGET_PRICE:
                condition_met = True
                price_msg = f"✅ 价格满足: {current_price} == {CONF_TARGET_PRICE}"
            else:
                condition_met = False
                price_msg = f"❌ 价格不满足: {current_price} != {CONF_TARGET_PRICE}"
        else: # SELL
            if current_price == CONF_TARGET_PRICE:
                condition_met = True
                price_msg = f"✅ 价格满足: {current_price} == {CONF_TARGET_PRICE}"
            else:
                condition_met = False
                price_msg = f"❌ 价格不满足: {current_price} != {CONF_TARGET_PRICE}"
                
        # 2. 数量条件判断
        # 如果价格满足，再看数量
        if condition_met:
            if current_volume == CONF_TARGET_VOLUME:
                volume_msg = f"✅ 数量满足: {current_volume} == {CONF_TARGET_VOLUME}"
            else:
                condition_met = False
                volume_msg = f"❌ 数量不满足: {current_volume} != {CONF_TARGET_VOLUME}"
        
        logger.info(f"\n🧐 条件检查结果:")
        logger.info(f"   1. {price_msg}")
        if "✅" in price_msg:
            logger.info(f"   2. {volume_msg}")
            
        # ================= 执行逻辑 =================
        if condition_met:
            logger.info("\n⚡ 条件完全符合，生成 Insert Order 并执行吃单！")
            
            # 确定 Offset (处理平今平昨)
            final_offset = CONF_OFFSET
            if CONF_OFFSET == 'CLOSE':
                position = api.get_position(INSTRUMENT_ID)
                final_offset = get_smart_offset(INSTRUMENT_ID, position, direction, CONF_OFFSET)
                
            offset_cn = "开仓" if final_offset == "OPEN" else ("平今" if final_offset == "CLOSETODAY" else "平仓")
            
            logger.info(f"发送订单: {INSTRUMENT_ID} {direction} {final_offset} ({offset_cn}) {CONF_ORDER_VOLUME}手 @ {current_price}")
            
            try:
                order = api.insert_order(
                    symbol=INSTRUMENT_ID,
                    direction=direction,
                    offset=final_offset,
                    volume=CONF_ORDER_VOLUME,
                    limit_price=current_price
                )
                
                logger.info(f"📝 订单已提交, OrderID: {order.order_id}")
                
                # 等待并检查状态
                logger.info("⏳ 等待订单回报...")
                check_count = 0
                while check_count < 10:
                    await asyncio.sleep(0.5)
                    check_count += 1
                    if order.status == 'FINISHED':
                        logger.info("✅ 吃单成功！订单已完全成交")
                        break
                
                if order.status != 'FINISHED':
                    logger.info(f"ℹ️  当前订单状态: {order.status}, 已成交: {order.volume_orign - order.volume_left}/{order.volume_orign}")
                    
            except Exception as e:
                logger.error(f"❌ 下单失败: {e}")
                
        else:
            logger.warning("\n⛔ 盘口挂单不符合条件，不予执行")
            logger.info(f"   配置要求: {CONF_PRICE_FIELD} { '==' if direction == 'BUY' else '==' } {CONF_TARGET_PRICE} 且 量 == {CONF_TARGET_VOLUME}")
            logger.info(f"   当前状态: {current_price} (量: {current_volume})")

    except Exception as e:
        logger.error(f"❌ 程序执行异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        logger.info("=" * 80)


# 运行模式，1-TqSim模拟, 2-TqKq ，3-simnow， 6-金信实盘
RUN_MODE = 6

if RUN_MODE == 6:
    api = TqApi(
        TqAccount('H宏源期货', '901213262', 'bonze613'),
        debug=False,
        web_gui=False,
        auth=TqAuth('playbonze0722', 'bonze613')
    )
elif RUN_MODE == 1:
    api = TqApi(TqAccount("simnow", "sim", "sim"), auth=TqAuth("信易账户", "信易密码")) # 请替换为实际模拟账号
else:
    logger.error("❌ 请配置正确的运行模式")
    sys.exit(1)

logger.info(f'模式{RUN_MODE}，吃单脚本开始运行')

try:
    # 创建异步任务运行主函数
    task = api.create_task(main(api))
    
    while not task.done():
        api.wait_update()
    
    # 等待一下确保日志输出
    import time
    time.sleep(1)
    
except KeyboardInterrupt:
    logger.info("\n⚠️  用户中断程序")
except Exception as e:
    logger.error(f'❌ 程序异常: {e}')
    import traceback
    logger.error(traceback.format_exc())
finally:
    try:
        api.close()
    except:
        pass
    logger.info("程序退出")
