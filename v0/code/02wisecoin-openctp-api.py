
import requests
import pandas as pd
import logging
import time
import os
import sys
import shutil

# 添加外部模块路径以支持 UnifiedLogger
sys.path.append(os.path.join(os.path.dirname(__file__), "wisecoin-akshare-api"))
try:
    from pb_quant_seektop_common import UnifiedLogger
    logger = UnifiedLogger.setup_logger_auto(__file__)
except ImportError:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

import json
import re
import argparse

OUTPUT_FILE = "wisecoin-openctp数据.xlsx"
SYMBOL_PARAMS_FILE = "wisecoin-symbol-params.json"
MARKET_FILE_OPT = "wisecoin-期货行情.xlsx"
MARKET_FILE_NO_OPT = "wisecoin-期货行情-无期权.xlsx"

# 交易所名称映射
EXCHANGE_NAMES = {
    "CFFEX": "中国金融期货交易所",
    "CZCE": "郑州商品交易所",
    "DCE": "大连商品交易所",
    "GFEX": "广州期货交易所",
    "INE": "上海国际能源交易中心",
    "SHFE": "上海期货交易所"
}


def check_margin_ratios(auto_update=False):
    """
    Check and compare margin ratios between OpenCTP data and local config.
    Logic:
    1. Read market data (opt + no_opt summary).
    2. Find main contract (max volume + OI) for each product.
    3. Get LongMarginRatioByMoney from OpenCTP data for the main contract.
    4. Compare with margin_ratio in wisecoin-symbol-params.json.
    5. 【新增】对 JSON 中没有配置的品种，自动新增到对应交易所下。
    
    If auto_update is True, it will automatically update the json file.
    """
    logger.info("🔍 Checking margin ratios...")
    
    # 1. Load Market Data
    dfs = []
    if os.path.exists(MARKET_FILE_OPT):
        try:
            dfs.append(pd.read_excel(MARKET_FILE_OPT, sheet_name='Summary'))
        except Exception as e:
            logger.error(f"Failed to read {MARKET_FILE_OPT}: {e}")
            
    if os.path.exists(MARKET_FILE_NO_OPT):
        try:
            dfs.append(pd.read_excel(MARKET_FILE_NO_OPT, sheet_name='Summary'))
        except Exception as e:
            logger.error(f"Failed to read {MARKET_FILE_NO_OPT}: {e}")
            
    if not dfs:
        logger.warning("No market data found to identify main contracts.")
        return

    df_market = pd.concat(dfs, ignore_index=True)
    
    if df_market.empty:
        logger.warning("Market data is empty.")
        return

    # Helper to clean instrument_id (remove exchange prefix)
    def clean_instrument_id(inst_id):
        if pd.isna(inst_id): return ""
        s = str(inst_id)
        if '.' in s:
            return s.split('.')[-1]
        return s

    df_market['clean_inst_id'] = df_market['instrument_id'].apply(clean_instrument_id)
    
    # Helper to extract exchange from instrument_id
    def get_exchange(inst_id):
        if pd.isna(inst_id): return ""
        s = str(inst_id)
        if '.' in s:
            return s.split('.')[0].upper()
        return ""
    
    df_market['exchange'] = df_market['instrument_id'].apply(get_exchange)
    
    # Helper to get product code
    def get_product_code(inst_id):
        match = re.match(r'^[a-zA-Z]+', inst_id)
        if match:
            return match.group(0).upper()
        return ""

    df_market['product_code'] = df_market['clean_inst_id'].apply(get_product_code)

    # Calculate activity (volume + open_interest)
    # Ensure numeric
    df_market['volume'] = pd.to_numeric(df_market['volume'], errors='coerce')
    df_market['volume'] = df_market['volume'].fillna(0)
    
    df_market['open_interest'] = pd.to_numeric(df_market['open_interest'], errors='coerce')
    df_market['open_interest'] = df_market['open_interest'].fillna(0)
    
    df_market['activity'] = df_market['volume'] + df_market['open_interest']
    
    # Find main contract for each product
    # Sort by activity desc to ensure we get the max when dropping duplicates or grouping
    main_contracts = df_market.sort_values('activity', ascending=False).drop_duplicates('product_code')
    
    logger.info(f"Identified {len(main_contracts)} main contracts from market data.")

    # 2. Load OpenCTP Data
    if not os.path.exists(OUTPUT_FILE):
        logger.warning(f"{OUTPUT_FILE} not found. Skipping check.")
        return
        
    try:
        # Load '期货合约信息' sheet
        df_openctp = pd.read_excel(OUTPUT_FILE, sheet_name='期货合约信息')
    except Exception as e:
        logger.error(f"Failed to read {OUTPUT_FILE}: {e}")
        return
        
    if 'InstrumentID' not in df_openctp.columns or 'LongMarginRatioByMoney' not in df_openctp.columns:
        logger.error("OpenCTP data missing required columns (InstrumentID, LongMarginRatioByMoney).")
        return
    
    # 获取产品名称（如果存在）
    product_name_col = 'ProductName' if 'ProductName' in df_openctp.columns else None

    # 3. Load Params
    if not os.path.exists(SYMBOL_PARAMS_FILE):
        logger.warning(f"{SYMBOL_PARAMS_FILE} not found.")
        return
        
    try:
        with open(SYMBOL_PARAMS_FILE, 'r', encoding='utf-8') as f:
            params = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load params: {e}")
        return
        
    # Flatten params for easy lookup: product -> (exchange, config)
    product_params = {}
    for exchange, prods in params.items():
        if exchange.startswith('_'): continue
        if not isinstance(prods, dict): continue
        for prod, config in prods.items():
            if prod.startswith('_'): continue
            product_params[prod.upper()] = (exchange, config)

    # 4. Compare and collect results
    mismatches = []
    new_products = []
    
    # Pre-calculate product order from JSON params for sorting
    product_order = []
    for exchange, prods in params.items():
        if exchange.startswith('_') or not isinstance(prods, dict): continue
        for prod in prods.keys():
            if prod.startswith('_'): continue
            product_order.append(prod.upper())

    def get_order_index(prod_code):
        try:
            return product_order.index(prod_code)
        except ValueError:
            return 999999

    for _, row in main_contracts.iterrows():
        # Handle potential Series if column is duplicated
        raw_product = row['product_code']
        if hasattr(raw_product, 'iloc'): 
            raw_product = raw_product.iloc[0]
            
        product = str(raw_product) if raw_product and not pd.isna(raw_product) else ""
        inst_id = row['clean_inst_id']
        exchange = row['exchange']
        
        if not product or not exchange: continue
        
        # Find in OpenCTP
        ctp_row = df_openctp[df_openctp['InstrumentID'] == inst_id]
        if ctp_row.empty:
            continue
            
        try:
            openctp_margin = float(ctp_row.iloc[0]['LongMarginRatioByMoney'])
            openctp_fee = float(ctp_row.iloc[0].get('OpenRatioByMoney', 0.0001)) if 'OpenRatioByMoney' in ctp_row.columns else 0.0001
            openctp_vol_mult = int(ctp_row.iloc[0]['VolumeMultiple']) if 'VolumeMultiple' in ctp_row.columns else 1
            
            # --- 优化 name 逻辑 ---
            # 优先从 market data 中获取 instrument_name
            market_name = row.get('instrument_name', '')
            if pd.isna(market_name): market_name = ""
            
            # 去除数字部分
            if market_name:
                market_name = re.sub(r'\d+$', '', str(market_name)).strip()
            
            # 如果 market data 中没有，尝试使用 OpenCTP 中的 ProductName (如果有)
            if not market_name and product_name_col and product_name_col in ctp_row.columns:
                ctp_name = ctp_row.iloc[0][product_name_col]
                if not pd.isna(ctp_name):
                    market_name = str(ctp_name).strip()
            
            # 如果还是没有，使用 product code
            if not market_name:
                market_name = product
            
            product_name = market_name
            # ---------------------
            
            # Find in Params
            if product in product_params:
                # 已存在的品种：检查是否需要更新
                config_exchange, config = product_params[product]
                json_margin = config.get('margin_ratio')
                json_vol_mult = config.get('volume_multiple')
                
                # Check for updates (margin ratio OR name OR volume_multiple)
                needs_update = False
                
                if json_margin is not None:
                    json_val = float(json_margin)
                    if abs(openctp_margin - json_val) > 1e-6:
                        needs_update = True
                
                if json_vol_mult is None or int(json_vol_mult) != openctp_vol_mult:
                     needs_update = True

                # Check name update (only if we have a valid name from market data)
                current_name = config.get('name', '')
                if product_name and product_name != current_name and product_name != product:
                     needs_update = True

                if needs_update:
                    mismatches.append({
                        'product': product,
                        'inst_id': inst_id,
                        'exchange': exchange,
                        'openctp': openctp_margin,
                        'json': json_margin,
                        'openctp_vol_mult': openctp_vol_mult,
                        'json_vol_mult': json_vol_mult,
                        'name': product_name, # New name
                        'current_name': current_name,
                        'action': 'update'
                    })
            else:
                # 新品种：只在 auto_update 时收集
                if auto_update:
                    new_products.append({
                        'product': product,
                        'inst_id': inst_id,
                        'exchange': exchange,
                        'openctp': openctp_margin,
                        'fee': openctp_fee,
                        'vol_mult': openctp_vol_mult,
                        'name': product_name,
                        'action': 'add'
                    })
                
        except Exception as e:
            logger.debug(f"Error checking {product}: {e}")

    # Sort mismatches by JSON order
    mismatches.sort(key=lambda x: get_order_index(x['product']))

    mismatch_count = len(mismatches)
    new_count = len(new_products)
    
    # 检测新品种（即使 auto_update=False 也要统计）
    new_products_detected = []
    if not auto_update:
        # 如果没有启用 auto_update，重新扫描一遍以检测新品种
        for _, row in main_contracts.iterrows():
            raw_product = row['product_code']
            if hasattr(raw_product, 'iloc'): 
                raw_product = raw_product.iloc[0]
            product = str(raw_product) if raw_product and not pd.isna(raw_product) else ""
            if product and product not in product_params:
                inst_id = row['clean_inst_id']
                exchange = row['exchange']
                ctp_row = df_openctp[df_openctp['InstrumentID'] == inst_id]
                if not ctp_row.empty:
                    try:
                        openctp_margin = float(ctp_row.iloc[0]['LongMarginRatioByMoney'])
                        new_products_detected.append({
                            'product': product,
                            'inst_id': inst_id,
                            'exchange': exchange,
                            'margin': openctp_margin
                        })
                    except:
                        pass
    
    # 输出更新品种信息
    for m in mismatches:
        logger.warning(f"⚠️  Mismatch for [{m['product']}] (Main: {m['inst_id']}):")
        if abs(m['openctp'] - float(m['json'] if m['json'] is not None else 0)) > 1e-6:
             logger.warning(f"    Margin: OpenCTP {m['openctp']} | JSON {m['json']}")
        if m['openctp_vol_mult'] != m['json_vol_mult']:
             logger.warning(f"    VolMult: OpenCTP {m['openctp_vol_mult']} | JSON {m['json_vol_mult']}")
        if m['name'] and m['name'] != m['current_name']:
             logger.warning(f"    Name: Market '{m['name']}' | JSON '{m['current_name']}'")
        
    # 如果未启用 auto_update 但检测到新品种，给出提示
    if not auto_update and new_products_detected:
        logger.info(f"💡 Detected {len(new_products_detected)} new products not in config:")
        for np in new_products_detected[:5]:  # 只显示前5个
            margin_str = f"{np['margin']:.10f}".rstrip('0').rstrip('.')
            logger.info(f"    [{np['exchange']}] {np['product']} (Main: {np['inst_id']}) - Margin: {margin_str}")
        if len(new_products_detected) > 5:
            logger.info(f"    ... and {len(new_products_detected) - 5} more")
        logger.info(f"💡 Run with --auto-update to add these products automatically.")

    if mismatch_count == 0 and new_count == 0 and not new_products_detected:
        logger.info("✅ All margin ratios and names match, and no new products found.")
    else:
        if mismatch_count > 0:
            logger.info(f"⚠️  Found {mismatch_count} items to update.")
        if new_count > 0:
            logger.info(f"🆕 Found {new_count} new products not in config.")

        if auto_update:
            logger.info("🔧 Auto-update is enabled. Applying changes...")
            update_count = 0
            add_count = 0
            
            # Apply updates for existing products
            for m in mismatches:
                prod = m['product']
                new_margin = m['openctp']
                new_name = m['name']
                new_vol_mult = m['openctp_vol_mult']
                
                # Update params dict
                if prod in product_params:
                    exchange, config = product_params[prod]
                    config['margin_ratio'] = new_margin
                    config['volume_multiple'] = new_vol_mult
                    if new_name and new_name != prod: # Only update name if valid and not just the code
                        config['name'] = new_name
                    update_count += 1
            
            # Add new products
            for new_prod in new_products:
                prod = new_prod['product']  # 已经是大写
                exchange = new_prod['exchange']
                margin = new_prod['openctp']
                fee = new_prod['fee']
                vol_mult = new_prod['vol_mult']
                name = new_prod['name']
                
                # 确保交易所存在于 params 中
                if exchange not in params:
                    # 使用 OrderedDict 确保 _交易所 在最前面
                    from collections import OrderedDict
                    params[exchange] = OrderedDict()
                    params[exchange]["_交易所"] = EXCHANGE_NAMES.get(exchange, exchange)
                    logger.info(f"🆕 Created new exchange section: {exchange}")
                
                # 根据交易所决定产品代码的大小写
                # CFFEX（金融期货）和 CZCE（郑商所）使用大写
                # 其他交易所使用小写
                if exchange in ["CFFEX", "CZCE"]:
                    prod_key = prod.upper()
                else:
                    prod_key = prod.lower()
                
                # 添加新产品配置（字段顺序：margin_ratio, fee_ratio, volume_multiple, name）
                if prod_key not in params[exchange]:
                    from collections import OrderedDict
                    params[exchange][prod_key] = OrderedDict([
                        ("margin_ratio", margin),
                        ("fee_ratio", fee),
                        ("volume_multiple", vol_mult),
                        ("name", name)
                    ])
                    add_count += 1
                    # 格式化数值避免科学计数法
                    margin_str = f"{margin:.10f}".rstrip('0').rstrip('.')
                    fee_str = f"{fee:.10f}".rstrip('0').rstrip('.')
                    logger.info(f"✅ Added new product: [{exchange}] {prod_key} - margin: {margin_str}, fee: {fee_str}, vol_mult: {vol_mult}, name: {name}")
            
            if update_count > 0 or add_count > 0:

                try:
                    # 在保存前，确保所有交易所的 _交易所 字段在最前面
                    from collections import OrderedDict
                    sorted_params = OrderedDict()
                    
                    # 先添加元数据字段
                    for key in ["_说明", "_字段说明", "_更新日期"]:
                        if key in params:
                            sorted_params[key] = params[key]
                    
                    # 再按顺序添加交易所（保持原有顺序）
                    exchange_order = ["CFFEX", "CZCE", "DCE", "GFEX", "INE", "SHFE"]
                    for exchange in exchange_order:
                        if exchange in params:
                            sorted_params[exchange] = params[exchange]
                    
                    # 添加其他可能存在的交易所
                    for exchange in params:
                        if exchange not in sorted_params and not exchange.startswith('_'):
                            sorted_params[exchange] = params[exchange]
                    
                    # Use a custom saving method to ensure floats are formatted correctly (decimal, not scientific)
                    json_str = json.dumps(sorted_params, indent=2, ensure_ascii=False)
                    
                    # 1. Fix scientific notation: 6.5e-05 -> 0.000065
                    def replace_sci(match):
                        try:
                            val = float(match.group(0))
                            return "{:.10f}".format(val).rstrip('0').rstrip('.')
                        except:
                            return match.group(0)
                            
                    # Pattern for sci notation: matches things like 1.2e-5, -3e4
                    # \b ensures word boundaries so we don't match inside other strings
                    sci_pattern = re.compile(r'\b-?\d+(\.\d+)?[eE][+-]?\d+\b')
                    json_str = sci_pattern.sub(replace_sci, json_str)

                    # 2. Fix long ugly floats: 0.00006499999999999999 -> 0.000065
                    def replace_long(match):
                        try:
                            val = float(match.group(0))
                            return "{:.10f}".format(val).rstrip('0').rstrip('.')
                        except:
                            return match.group(0)

                    # Look for numbers with > 10 decimal digits
                    long_pattern = re.compile(r'\b-?\d+\.\d{10,}\b')
                    json_str = long_pattern.sub(replace_long, json_str)

                    with open(SYMBOL_PARAMS_FILE, 'w', encoding='utf-8') as f:
                        f.write(json_str)
                        
                    logger.info(f"✅ Successfully updated {update_count} products and added {add_count} new products in {SYMBOL_PARAMS_FILE}")

                except Exception as e:
                    logger.error(f"❌ Failed to write updates to {SYMBOL_PARAMS_FILE}: {e}")
            else:
                logger.warning("No updates could be applied (possibly couldn't find config key).")
        
        # 无论是否有更新，都尝试拷贝一份至上级目录
        if auto_update:
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            target_path = os.path.join(parent_dir, SYMBOL_PARAMS_FILE)
            try:
                shutil.copy2(SYMBOL_PARAMS_FILE, target_path)
                logger.info(f"📋 Copied {SYMBOL_PARAMS_FILE} to parent directory: {target_path}")
            except Exception as e:
                logger.error(f"❌ Failed to copy {SYMBOL_PARAMS_FILE} to parent directory: {e}")


def fetch_openctp_data(url, description):
    """Fetch data from OpenCTP API."""
    logger.info(f"Fetching {description} from {url}...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and 'data' in data:
            df = pd.DataFrame(data['data'])
            logger.info(f"✅ Successfully fetched {len(df)} records for {description}")
            return df
        else:
            logger.warning(f"⚠️ Unexpected data format for {description}: {data}")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"❌ Failed to fetch {description}: {e}")
        return pd.DataFrame()

def main():
    parser = argparse.ArgumentParser(description="Fetch OpenCTP data and check margin ratios.")
    parser.add_argument("--auto-update", action="store_true", help="Automatically update wisecoin-symbol-params.json with new margin ratios.")
    args = parser.parse_args()

    start_time = time.time()
    logger.info("🚀 Starting OpenCTP data fetch...")
    
    # Define endpoints
    futures_url = "http://dict.openctp.cn/instruments?types=futures&areas=China"
    options_url = "http://dict.openctp.cn/instruments?types=option&areas=China"
    
    # Fetch data
    df_futures = fetch_openctp_data(futures_url, "Futures Contract Info")
    df_options = fetch_openctp_data(options_url, "Options Contract Info")
    
    # Save to Excel
    logger.info(f"Saving data to {OUTPUT_FILE}...")
    try:
        with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
            if not df_futures.empty:
                df_futures.to_excel(writer, sheet_name="期货合约信息", index=False)
                logger.info("✅ Saved '期货合约信息' sheet")
            else:
                logger.warning("⚠️ Skipping '期货合约信息' sheet (empty data)")
                
            if not df_options.empty:
                df_options.to_excel(writer, sheet_name="期权合约信息", index=False)
                logger.info("✅ Saved '期权合约信息' sheet")
            else:
                logger.warning("⚠️ Skipping '期权合约信息' sheet (empty data)")
                
        logger.info(f"✨ DONE! Total time: {time.time()-start_time:.2f}s. File: {OUTPUT_FILE}")
        
        # Check margin ratios
        check_margin_ratios(auto_update=True)
        
    except Exception as e:
        logger.error(f"❌ Failed to save Excel file: {e}")

if __name__ == "__main__":
    main()
