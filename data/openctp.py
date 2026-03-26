# data/openctp.py
"""
OpenCTP 数据源适配模块。

提供从 OpenCTP API 获取期货/期权合约信息的功能，
以及保证金比率检查和自动更新功能。

Example:
    >>> from data.openctp import OpenCTPClient
    >>> client = OpenCTPClient()
    >>> client.fetch_and_save()
    >>> client.check_margin_ratios(auto_update=True)
"""
import json
import os
import re
import shutil
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import requests

from common.logger import StructuredLogger


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


# 交易所名称映射
EXCHANGE_NAMES = {
    "CFFEX": "中国金融期货交易所",
    "CZCE": "郑州商品交易所",
    "DCE": "大连商品交易所",
    "GFEX": "广州期货交易所",
    "INE": "上海国际能源交易中心",
    "SHFE": "上海期货交易所"
}

# API 端点
OPENCTP_FUTURES_URL = "http://dict.openctp.cn/instruments?types=futures&areas=China"
OPENCTP_OPTIONS_URL = "http://dict.openctp.cn/instruments?types=option&areas=China"

# 默认文件名
DEFAULT_OUTPUT_FILE = "wisecoin-openctp数据.xlsx"
DEFAULT_SYMBOL_PARAMS_FILE = "wisecoin-symbol-params.json"
DEFAULT_MARKET_FILE_OPT = "wisecoin-期货行情.xlsx"
DEFAULT_MARKET_FILE_NO_OPT = "wisecoin-期货行情-无期权.xlsx"


class OpenCTPClient:
    """
    OpenCTP 数据客户端。

    提供从 OpenCTP API 获取合约信息、检查保证金比率、
    自动更新品种参数配置等功能。

    Attributes:
        logger: 结构化日志器。
        output_file: 输出 Excel 文件路径。
        symbol_params_file: 品种参数 JSON 文件路径。
        market_file_opt: 含期权的期货行情文件路径。
        market_file_no_opt: 无期权的期货行情文件路径。

    Example:
        >>> client = OpenCTPClient()
        >>> client.fetch_and_save()
        >>> client.check_margin_ratios(auto_update=True)
    """

    def __init__(
        self,
        output_file: str = None,
        symbol_params_file: str = None,
        market_file_opt: str = None,
        market_file_no_opt: str = None,
        log_file: Optional[str] = None
    ):
        """
        初始化 OpenCTP 客户端。

        Args:
            output_file: 输出 Excel 文件路径。
            symbol_params_file: 品种参数 JSON 文件路径。
            market_file_opt: 含期权的期货行情文件路径。
            market_file_no_opt: 无期权的期货行情文件路径。
            log_file: 日志文件路径（可选）。
        """
        self.logger = StructuredLogger("openctp", log_file=log_file)
        # 默认使用项目根目录
        self.output_file = output_file or str(PROJECT_ROOT / DEFAULT_OUTPUT_FILE)
        self.symbol_params_file = symbol_params_file or str(PROJECT_ROOT / DEFAULT_SYMBOL_PARAMS_FILE)
        self.market_file_opt = market_file_opt or str(PROJECT_ROOT / DEFAULT_MARKET_FILE_OPT)
        self.market_file_no_opt = market_file_no_opt or str(PROJECT_ROOT / DEFAULT_MARKET_FILE_NO_OPT)

    def fetch_data(self, url: str, description: str) -> pd.DataFrame:
        """
        从 OpenCTP API 获取数据。

        Args:
            url: API 端点 URL。
            description: 数据描述（用于日志）。

        Returns:
            包含获取数据的 DataFrame，失败时返回空 DataFrame。
        """
        self.logger.info(f"Fetching {description} from {url}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and 'data' in data:
                df = pd.DataFrame(data['data'])
                self.logger.info(f"Successfully fetched {len(df)} records for {description}")
                return df
            else:
                self.logger.warning(f"Unexpected data format for {description}")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to fetch {description}: {e}")
            return pd.DataFrame()

    def fetch_and_save(self) -> bool:
        """
        获取期货和期权合约信息并保存到 Excel 文件。

        Returns:
            成功返回 True，失败返回 False。
        """
        start_time = time.time()
        self.logger.info("Starting OpenCTP data fetch...")

        # 获取数据
        df_futures = self.fetch_data(OPENCTP_FUTURES_URL, "Futures Contract Info")
        df_options = self.fetch_data(OPENCTP_OPTIONS_URL, "Options Contract Info")

        # 保存到 Excel
        self.logger.info(f"Saving data to {self.output_file}...")
        try:
            with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
                if not df_futures.empty:
                    df_futures.to_excel(writer, sheet_name="期货合约信息", index=False)
                    self.logger.info("Saved '期货合约信息' sheet")
                else:
                    self.logger.warning("Skipping '期货合约信息' sheet (empty data)")

                if not df_options.empty:
                    df_options.to_excel(writer, sheet_name="期权合约信息", index=False)
                    self.logger.info("Saved '期权合约信息' sheet")
                else:
                    self.logger.warning("Skipping '期权合约信息' sheet (empty data)")

            elapsed = time.time() - start_time
            self.logger.info(f"DONE! Total time: {elapsed:.2f}s. File: {self.output_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save Excel file: {e}")
            return False

    def check_margin_ratios(self, auto_update: bool = False) -> bool:
        """
        检查并比较 OpenCTP 数据与本地配置的保证金比率。

        逻辑：
        1. 读取市场数据（期权 + 无期权汇总）。
        2. 找出每个品种的主力合约（成交量和持仓量最大）。
        3. 从 OpenCTP 数据获取主力合约的 LongMarginRatioByMoney。
        4. 与 wisecoin-symbol-params.json 中的 margin_ratio 比较。
        5. 对 JSON 中没有配置的品种，自动新增到对应交易所下。

        Args:
            auto_update: 是否自动更新 JSON 文件。

        Returns:
            检查成功返回 True，否则返回 False。
        """
        self.logger.info("Checking margin ratios...")

        # 1. 加载市场数据
        dfs = []
        if os.path.exists(self.market_file_opt):
            try:
                dfs.append(pd.read_excel(self.market_file_opt, sheet_name='Summary'))
            except Exception as e:
                self.logger.error(f"Failed to read {self.market_file_opt}: {e}")

        if os.path.exists(self.market_file_no_opt):
            try:
                dfs.append(pd.read_excel(self.market_file_no_opt, sheet_name='Summary'))
            except Exception as e:
                self.logger.error(f"Failed to read {self.market_file_no_opt}: {e}")

        if not dfs:
            self.logger.warning("No market data found to identify main contracts.")
            return False

        df_market = pd.concat(dfs, ignore_index=True)

        if df_market.empty:
            self.logger.warning("Market data is empty.")
            return False

        # 辅助函数：清理合约代码（移除交易所前缀）
        def clean_instrument_id(inst_id):
            if pd.isna(inst_id):
                return ""
            s = str(inst_id)
            if '.' in s:
                return s.split('.')[-1]
            return s

        df_market['clean_inst_id'] = df_market['instrument_id'].apply(clean_instrument_id)

        # 辅助函数：从合约代码提取交易所
        def get_exchange(inst_id):
            if pd.isna(inst_id):
                return ""
            s = str(inst_id)
            if '.' in s:
                return s.split('.')[0].upper()
            return ""

        df_market['exchange'] = df_market['instrument_id'].apply(get_exchange)

        # 辅助函数：获取品种代码
        def get_product_code(inst_id):
            match = re.match(r'^[a-zA-Z]+', inst_id)
            if match:
                return match.group(0).upper()
            return ""

        df_market['product_code'] = df_market['clean_inst_id'].apply(get_product_code)

        # 计算活跃度（成交量 + 持仓量）
        df_market['volume'] = pd.to_numeric(df_market['volume'], errors='coerce')
        df_market['volume'] = df_market['volume'].fillna(0)

        df_market['open_interest'] = pd.to_numeric(df_market['open_interest'], errors='coerce')
        df_market['open_interest'] = df_market['open_interest'].fillna(0)

        df_market['activity'] = df_market['volume'] + df_market['open_interest']

        # 找出每个品种的主力合约
        main_contracts = df_market.sort_values('activity', ascending=False).drop_duplicates('product_code')

        self.logger.info(f"Identified {len(main_contracts)} main contracts from market data.")

        # 2. 加载 OpenCTP 数据
        if not os.path.exists(self.output_file):
            self.logger.warning(f"{self.output_file} not found. Skipping check.")
            return False

        try:
            df_openctp = pd.read_excel(self.output_file, sheet_name='期货合约信息')
        except Exception as e:
            self.logger.error(f"Failed to read {self.output_file}: {e}")
            return False

        if 'InstrumentID' not in df_openctp.columns or 'LongMarginRatioByMoney' not in df_openctp.columns:
            self.logger.error("OpenCTP data missing required columns (InstrumentID, LongMarginRatioByMoney).")
            return False

        # 获取产品名称列（如果存在）
        product_name_col = 'ProductName' if 'ProductName' in df_openctp.columns else None

        # 3. 加载参数配置
        if not os.path.exists(self.symbol_params_file):
            self.logger.info(f"{self.symbol_params_file} not found, creating new file...")
            # 创建空的配置结构
            params = {
                "_comment": "品种参数配置文件，由 data.openctp 模块自动生成和维护",
                "CFFEX": {},
                "CZCE": {},
                "DCE": {},
                "GFEX": {},
                "INE": {},
                "SHFE": {}
            }
            try:
                with open(self.symbol_params_file, 'w', encoding='utf-8') as f:
                    json.dump(params, f, indent=2, ensure_ascii=False)
                self.logger.info(f"Created new {self.symbol_params_file}")
            except Exception as e:
                self.logger.error(f"Failed to create {self.symbol_params_file}: {e}")
                return False
        else:
            try:
                with open(self.symbol_params_file, 'r', encoding='utf-8') as f:
                    params = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load params: {e}")
                return False

        # 扁平化参数以便查找：品种 -> (交易所, 配置)
        product_params = {}
        for exchange, prods in params.items():
            if exchange.startswith('_'):
                continue
            if not isinstance(prods, dict):
                continue
            for prod, config in prods.items():
                if prod.startswith('_'):
                    continue
                product_params[prod.upper()] = (exchange, config)

        # 4. 比较并收集结果
        mismatches = []
        new_products = []

        # 预计算品种顺序（用于排序）
        product_order = []
        for exchange, prods in params.items():
            if exchange.startswith('_') or not isinstance(prods, dict):
                continue
            for prod in prods.keys():
                if prod.startswith('_'):
                    continue
                product_order.append(prod.upper())

        def get_order_index(prod_code):
            try:
                return product_order.index(prod_code)
            except ValueError:
                return 999999

        for _, row in main_contracts.iterrows():
            # 处理可能的 Series 重复列
            raw_product = row['product_code']
            if hasattr(raw_product, 'iloc'):
                raw_product = raw_product.iloc[0]

            product = str(raw_product) if raw_product and not pd.isna(raw_product) else ""
            inst_id = row['clean_inst_id']
            exchange = row['exchange']

            if not product or not exchange:
                continue

            # 在 OpenCTP 数据中查找
            ctp_row = df_openctp[df_openctp['InstrumentID'] == inst_id]
            if ctp_row.empty:
                continue

            try:
                openctp_margin = float(ctp_row.iloc[0]['LongMarginRatioByMoney'])
                openctp_fee = float(ctp_row.iloc[0].get('OpenRatioByMoney', 0.0001)) if 'OpenRatioByMoney' in ctp_row.columns else 0.0001
                openctp_vol_mult = int(ctp_row.iloc[0]['VolumeMultiple']) if 'VolumeMultiple' in ctp_row.columns else 1

                # --- 优化 name 逻辑 ---
                # 优先从市场数据获取 instrument_name
                market_name = row.get('instrument_name', '')
                if pd.isna(market_name):
                    market_name = ""

                # 去除数字部分
                if market_name:
                    market_name = re.sub(r'\d+$', '', str(market_name)).strip()

                # 如果市场数据中没有，尝试使用 OpenCTP 中的 ProductName
                if not market_name and product_name_col and product_name_col in ctp_row.columns:
                    ctp_name = ctp_row.iloc[0][product_name_col]
                    if not pd.isna(ctp_name):
                        market_name = str(ctp_name).strip()

                # 如果还是没有，使用品种代码
                if not market_name:
                    market_name = product

                product_name = market_name
                # ---------------------

                # 在参数配置中查找
                if product in product_params:
                    # 已存在的品种：检查是否需要更新
                    config_exchange, config = product_params[product]
                    json_margin = config.get('margin_ratio')
                    json_vol_mult = config.get('volume_multiple')

                    # 检查是否需要更新
                    needs_update = False

                    if json_margin is not None:
                        json_val = float(json_margin)
                        if abs(openctp_margin - json_val) > 1e-6:
                            needs_update = True

                    if json_vol_mult is None or int(json_vol_mult) != openctp_vol_mult:
                        needs_update = True

                    # 检查名称更新
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
                            'name': product_name,
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
                self.logger.debug(f"Error checking {product}: {e}")

        # 按配置顺序排序
        mismatches.sort(key=lambda x: get_order_index(x['product']))

        mismatch_count = len(mismatches)
        new_count = len(new_products)

        # 检测新品种（即使 auto_update=False 也要统计）
        new_products_detected = []
        if not auto_update:
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
                        except Exception:
                            pass

        # 输出更新品种信息
        for m in mismatches:
            self.logger.warning(f"Mismatch for [{m['product']}] (Main: {m['inst_id']}):")
            if abs(m['openctp'] - float(m['json'] if m['json'] is not None else 0)) > 1e-6:
                self.logger.warning(f"    Margin: OpenCTP {m['openctp']} | JSON {m['json']}")
            if m['openctp_vol_mult'] != m['json_vol_mult']:
                self.logger.warning(f"    VolMult: OpenCTP {m['openctp_vol_mult']} | JSON {m['json_vol_mult']}")
            if m['name'] and m['name'] != m['current_name']:
                self.logger.warning(f"    Name: Market '{m['name']}' | JSON '{m['current_name']}'")

        # 如果未启用 auto_update 但检测到新品种，给出提示
        if not auto_update and new_products_detected:
            self.logger.info(f"Detected {len(new_products_detected)} new products not in config:")
            for np in new_products_detected[:5]:
                margin_str = f"{np['margin']:.10f}".rstrip('0').rstrip('.')
                self.logger.info(f"    [{np['exchange']}] {np['product']} (Main: {np['inst_id']}) - Margin: {margin_str}")
            if len(new_products_detected) > 5:
                self.logger.info(f"    ... and {len(new_products_detected) - 5} more")
            self.logger.info("Run with auto_update=True to add these products automatically.")

        if mismatch_count == 0 and new_count == 0 and not new_products_detected:
            self.logger.info("All margin ratios and names match, and no new products found.")
        else:
            if mismatch_count > 0:
                self.logger.info(f"Found {mismatch_count} items to update.")
            if new_count > 0:
                self.logger.info(f"Found {new_count} new products not in config.")

            if auto_update:
                self.logger.info("Auto-update is enabled. Applying changes...")
                update_count = 0
                add_count = 0

                # 应用更新
                for m in mismatches:
                    prod = m['product']
                    new_margin = m['openctp']
                    new_name = m['name']
                    new_vol_mult = m['openctp_vol_mult']

                    if prod in product_params:
                        exchange, config = product_params[prod]
                        config['margin_ratio'] = new_margin
                        config['volume_multiple'] = new_vol_mult
                        if new_name and new_name != prod:
                            config['name'] = new_name
                        update_count += 1

                # 添加新品种
                for new_prod in new_products:
                    prod = new_prod['product']
                    exchange = new_prod['exchange']
                    margin = new_prod['openctp']
                    fee = new_prod['fee']
                    vol_mult = new_prod['vol_mult']
                    name = new_prod['name']

                    # 确保交易所存在于 params 中
                    if exchange not in params:
                        params[exchange] = OrderedDict()
                        params[exchange]["_交易所"] = EXCHANGE_NAMES.get(exchange, exchange)
                        self.logger.info(f"Created new exchange section: {exchange}")

                    # 根据交易所决定品种代码大小写
                    if exchange in ["CFFEX", "CZCE"]:
                        prod_key = prod.upper()
                    else:
                        prod_key = prod.lower()

                    # 添加新产品配置
                    if prod_key not in params[exchange]:
                        params[exchange][prod_key] = OrderedDict([
                            ("margin_ratio", margin),
                            ("fee_ratio", fee),
                            ("volume_multiple", vol_mult),
                            ("name", name)
                        ])
                        add_count += 1
                        margin_str = f"{margin:.10f}".rstrip('0').rstrip('.')
                        fee_str = f"{fee:.10f}".rstrip('0').rstrip('.')
                        self.logger.info(f"Added new product: [{exchange}] {prod_key} - margin: {margin_str}, fee: {fee_str}, vol_mult: {vol_mult}, name: {name}")

                if update_count > 0 or add_count > 0:
                    try:
                        # 确保所有交易所的 _交易所 字段在最前面
                        sorted_params = OrderedDict()

                        # 先添加元数据字段
                        for key in ["_说明", "_字段说明", "_更新日期"]:
                            if key in params:
                                sorted_params[key] = params[key]

                        # 再按顺序添加交易所
                        exchange_order = ["CFFEX", "CZCE", "DCE", "GFEX", "INE", "SHFE"]
                        for exchange in exchange_order:
                            if exchange in params:
                                sorted_params[exchange] = params[exchange]

                        # 添加其他可能存在的交易所
                        for exchange in params:
                            if exchange not in sorted_params and not exchange.startswith('_'):
                                sorted_params[exchange] = params[exchange]

                        # 保存 JSON 文件
                        json_str = json.dumps(sorted_params, indent=2, ensure_ascii=False)

                        # 修复科学计数法
                        def replace_sci(match):
                            try:
                                val = float(match.group(0))
                                return "{:.10f}".format(val).rstrip('0').rstrip('.')
                            except Exception:
                                return match.group(0)

                        sci_pattern = re.compile(r'\b-?\d+(\.\d+)?[eE][+-]?\d+\b')
                        json_str = sci_pattern.sub(replace_sci, json_str)

                        # 修复过长浮点数
                        def replace_long(match):
                            try:
                                val = float(match.group(0))
                                return "{:.10f}".format(val).rstrip('0').rstrip('.')
                            except Exception:
                                return match.group(0)

                        long_pattern = re.compile(r'\b-?\d+\.\d{10,}\b')
                        json_str = long_pattern.sub(replace_long, json_str)

                        with open(self.symbol_params_file, 'w', encoding='utf-8') as f:
                            f.write(json_str)

                        self.logger.info(f"Successfully updated {update_count} products and added {add_count} new products in {self.symbol_params_file}")

                    except Exception as e:
                        self.logger.error(f"Failed to write updates to {self.symbol_params_file}: {e}")
                else:
                    self.logger.warning("No updates could be applied.")

        return True


def fetch_openctp_data(url: str, description: str) -> pd.DataFrame:
    """
    从 OpenCTP API 获取数据的便捷函数。

    Args:
        url: API 端点 URL。
        description: 数据描述。

    Returns:
        包含获取数据的 DataFrame。
    """
    client = OpenCTPClient()
    return client.fetch_data(url, description)


def check_margin_ratios(auto_update: bool = False) -> bool:
    """
    检查保证金比率的便捷函数。

    Args:
        auto_update: 是否自动更新配置文件。

    Returns:
        检查成功返回 True。
    """
    client = OpenCTPClient()
    return client.check_margin_ratios(auto_update=auto_update)


def main():
    """命令行入口函数。"""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch OpenCTP data and check margin ratios.")
    parser.add_argument("--no-auto-update", action="store_true",
                        help="Disable automatic update of wisecoin-symbol-params.json.")
    args = parser.parse_args()

    client = OpenCTPClient()
    success = client.fetch_and_save()

    if success:
        # 默认自动更新，除非指定 --no-auto-update
        client.check_margin_ratios(auto_update=not args.no_auto_update)


if __name__ == "__main__":
    main()