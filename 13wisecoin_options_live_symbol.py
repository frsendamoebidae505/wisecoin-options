"""
实时监控配置生成系统 by playbonze
功能：从 wisecoin-重要期权.xlsx 提取标的合约并生成 wisecoin-symbol-live.json 配置文件
"""

import os
import sys
import json
import pandas as pd
import logging
import traceback

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
INPUT_EXCEL_FILE = "wisecoin-货权联动.xlsx"
SHEET_NAME = "货权联动"
OUTPUT_JSON_FILE = "wisecoin-symbol-live.json"
MIN_OPTION_OPEN_INTEREST = 0.3   # 最小期权沉淀(亿)
MIN_FUTURE_OPEN_INTEREST = 8.0   # 最小期货沉淀(亿)

def generate_live_symbol_config():
    """读取 Excel 并生成 JSON 配置文件"""
    try:
        if not os.path.exists(INPUT_EXCEL_FILE):
            logger.error(f"未找到核心文件: {INPUT_EXCEL_FILE}")
            return

        logger.info(f"正在读取 {INPUT_EXCEL_FILE}...")
        
        # 读取指定分页
        df = pd.read_excel(INPUT_EXCEL_FILE, sheet_name=SHEET_NAME)
        
        if df.empty:
            logger.warning(f"分页 {SHEET_NAME} 为空")
            return
            
        # 检查必要的列是否存在
        required_cols = ["标的合约", "期权沉淀(亿)", "期货沉淀(亿)"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"缺失必要的列: {missing_cols}")
            return
            
        # 筛选数据
        # 确保数值类型
        df['期权沉淀(亿)'] = pd.to_numeric(df['期权沉淀(亿)'], errors='coerce')
        df['期货沉淀(亿)'] = pd.to_numeric(df['期货沉淀(亿)'], errors='coerce')
        
        # 筛选: 期权沉淀(亿) > 0.30 OR 期货沉淀(亿) > 8
        condition = (df['期权沉淀(亿)'] > MIN_OPTION_OPEN_INTEREST) | (df['期货沉淀(亿)'] > MIN_FUTURE_OPEN_INTEREST)
        filtered_df = df[condition].copy()
        
        logger.info(f"筛选条件: 期权沉淀(亿) > {MIN_OPTION_OPEN_INTEREST} 或 期货沉淀(亿) > {MIN_FUTURE_OPEN_INTEREST}")
        logger.info(f"原始记录数: {len(df)}, 筛选后记录数: {len(filtered_df)}")
        
        live_symbols = []
        seen_symbols = set()
        
        # 提取标的合约并去重，保持原有顺序
        for symbol in filtered_df['标的合约']:
            symbol = str(symbol).strip()
            if symbol and symbol != "nan" and symbol not in seen_symbols:
                live_symbols.append(symbol)
                seen_symbols.add(symbol)
                # logger.debug(f"添加标的: {symbol}")
        
        if not live_symbols:
            logger.warning("未能在 Excel 中提取到任何有效标的合约。")
            return
            
        # 保存到 JSON
        logger.info(f"正在导出 {len(live_symbols)} 个标的合约到 {OUTPUT_JSON_FILE}...")
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(live_symbols, f, ensure_ascii=False, indent=4)
            
        logger.info("✅ 配置文件生成成功。")
        
    except Exception as e:
        logger.error(f"生成配置文件失败：{e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    generate_live_symbol_config()
