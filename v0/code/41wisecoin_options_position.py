"""
期权持仓获取系统 by playbonze
功能：获取账户持仓信息并导出为 wisecoin-持仓.xlsx
"""

import asyncio
import logging
import pandas as pd
import numpy as np
import datetime
import os
import sys
import traceback
from tqsdk import TqApi, TqAuth, TqAccount, TqKq, TqSim

# 添加外部模块路径以支持 UnifiedLogger
sys.path.append(os.path.join(os.path.dirname(__file__), "wisecoin-catboost"))
try:
    from pb_quant_seektop_common import UnifiedLogger
    # 设置统一日志
    logger = UnifiedLogger.setup_logger_auto(__file__)
except ImportError:
    # 回退到基本日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

# 全局文件配置
OUTPUT_EXCEL_FILE = "wisecoin-持仓.xlsx"

async def export_positions(api):
    """获取所有持仓并导出到 Excel"""
    try:
        logger.info("正在获取账户持仓信息...")
        
        # 等待数据同步
        timeout = 10
        start_time = datetime.datetime.now()
        while True:
            # 持续调用 wait_update 以确保数据从服务器同步
            api.wait_update(deadline=datetime.datetime.now().timestamp() + 0.5)
            
            # 获取所有持仓
            # 不传 symbol 参数，返回包含用户所有持仓的一个 Entity 对象
            positions = api.get_position()
            
            # 检查是否有持仓数据（即使是空的，Entity 对象也应该存在）
            if positions:
                # 转换位列表以进行过滤
                pos_list = []
                for symbol, pos in positions.items():
                    # 过滤掉挂单量和持仓量都为0的合约（可选，但用户要求保留所有字段，这里先转为字典）
                    # TqSDK 的 Position 对象在 wait_update 后会包含很多字段
                    p_dict = dict(pos)
                    p_dict['symbol'] = symbol
                    pos_list.append(p_dict)
                
                if pos_list:
                    df = pd.DataFrame(pos_list)
                    
                    # 按照合约代码排序
                    if 'symbol' in df.columns:
                        df = df.sort_values('symbol')
                    
                    # 导出到 Excel
                    logger.info(f"正在导出 {len(df)} 条持仓记录到 {OUTPUT_EXCEL_FILE}...")
                    df.to_excel(OUTPUT_EXCEL_FILE, index=False)
                    logger.info("✅ 导出完成。")
                    break
            
            if (datetime.datetime.now() - start_time).seconds > timeout:
                logger.warning("等待持仓数据超时，导出当前快照（可能为空）。")
                break
                
    except Exception as e:
        logger.error(f"导出持仓失败：{e}")
        logger.error(traceback.format_exc())

# 运行模式
RUN_MODE = 9
if os.path.basename(__file__) in ['pb-quant-test-1.py', 'pb-quant-test-2.py']:
    RUN_MODE = 1
elif os.path.basename(__file__) in ['pb-quant-kq.py']:
    RUN_MODE = 2
elif os.path.basename(__file__) in ['pb-quant-bh.py']:
    RUN_MODE = 4
elif os.path.basename(__file__) in ['pb-quant-jx.py']:
    RUN_MODE = 6

def get_api():
    """根据 RUN_MODE 初始化 TqApi"""
    if RUN_MODE == 1:
        backtest_start_dt, backtest_end_dt = (datetime.date.today() + datetime.timedelta(days=-1), datetime.date.today() + datetime.timedelta(days=0))
        acc_sim = TqSim(init_balance=10000000)
        return TqApi(account=acc_sim, backtest=TqBacktest(start_dt=backtest_start_dt, end_dt=backtest_end_dt), debug=False, web_gui=False, auth=TqAuth('playbonze', 'abC!@#123'))
    elif RUN_MODE == 2:
        return TqApi(TqKq(), debug=False, web_gui=False, auth=TqAuth('huaying', 'bonze13'))
    elif RUN_MODE == 3:
        return TqApi(TqAccount('simnow', '207302', 'Bonze!0613'), debug=False, web_gui=False, auth=TqAuth('huaying', 'bonze13'))
    elif RUN_MODE == 4:
        return TqApi(TqAccount('B渤海期货', '98908572', 'bonze613'), debug=False, web_gui=False, auth=TqAuth('playbonze', 'bonze13'))
    elif RUN_MODE == 5:
        return TqApi(TqAccount('H华安期货', '100919200', 'bonze613'), debug=False, web_gui=False, auth=TqAuth('huaying', 'bonze13'))
    elif RUN_MODE == 6:
        return TqApi(TqAccount('J金信期货', '80016087', 'bonze613'), debug=False, web_gui=False, auth=TqAuth('playbonze', 'bonze13'))
    elif RUN_MODE == 7:
        return TqApi(TqAccount('D东吴期货', '526178061', 'bonze613'), debug=False, web_gui=False, auth=TqAuth('huaying', 'bonze13'))
    elif RUN_MODE == 8:
        return TqApi(TqAccount('H宏源期货', '901212925', 'bonze613'), debug=False, web_gui=False, auth=TqAuth('huaying', 'bonze13'))
    elif RUN_MODE == 9:
        return TqApi(TqAccount('H宏源期货', '901213262', 'bonze613'), debug=False, web_gui=False, auth=TqAuth('playbonze0722', 'bonze613'))
    else:
        return TqApi(TqKq(), debug=False, web_gui=False, auth=TqAuth('huaying', 'bonze13'))

async def main():
    try:
        api = get_api()
        logger.info(f"模式 {RUN_MODE}，连接成功。")
        
        # 执行持仓导出
        await export_positions(api)
        
        api.close()
        logger.info("脚本执行完毕，已退出。")
    except Exception as e:
        logger.error(f"运行异常: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
